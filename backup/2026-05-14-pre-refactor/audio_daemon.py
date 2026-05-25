#!/usr/bin/env python3
"""
Keyboard audio-reactive daemon for NUC Linux Studio.

Watches /var/lib/nuc-linux-studio/audio_mode for activation.
When active, captures system audio via PipeWire/PulseAudio and drives
per-key RGB on the ITE8291R3 keyboard backlight via USB HID.

State file format (JSON):
  {"active": true, "brightness": 100, "direction": "up"}

Install as systemd service: kbd-audio.service
"""
import json
import os
import sys
import subprocess
import time
import signal
import glob
import select
from pathlib import Path

STATE_FILE = Path("/var/lib/nuc-linux-studio/audio_mode")
POLL_INTERVAL = 1.0  # seconds between state file checks

_running = True
_parec_proc = None
_ite_dev = None


def _signal_handler(sig, frame):
    global _running
    _running = False


def _active_session_uid():
    """Find the UID of the active graphical session user."""
    for bus in sorted(glob.glob("/run/user/*/bus")):
        try:
            uid = int(bus.split("/")[3])
            if uid > 0:
                return uid
        except Exception:
            continue
    return 1000  # fallback


def _unbind_kernel_driver():
    """Unbind ite8291r3 kernel driver from USB interface to allow userspace access."""
    try:
        for dev_path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            vendor = Path(dev_path).read_text().strip()
            if vendor == "048d":
                dev_dir = Path(dev_path).parent
                intf = dev_dir.name + ":1.1"
                for drv in ["ite8291r3", "usbfs", "usbhid"]:
                    unbind = Path(f"/sys/bus/usb/drivers/{drv}/unbind")
                    if unbind.exists():
                        try:
                            unbind.write_text(intf)
                        except Exception:
                            pass
                time.sleep(0.5)
                return True
    except Exception:
        pass
    return False


def _rebind_kernel_driver():
    """Rebind USB interface to the ite8291r3 kernel driver."""
    try:
        for dev_path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            vendor = Path(dev_path).read_text().strip()
            if vendor == "048d":
                dev_dir = Path(dev_path).parent
                intf = dev_dir.name + ":1.1"
                usbfs_unbind = Path("/sys/bus/usb/drivers/usbfs/unbind")
                if usbfs_unbind.exists():
                    try:
                        usbfs_unbind.write_text(intf)
                    except Exception:
                        pass
                time.sleep(0.1)
                bind = Path("/sys/bus/usb/drivers/ite8291r3/bind")
                if bind.exists():
                    try:
                        bind.write_text(intf)
                    except Exception:
                        pass
                time.sleep(0.2)
                return
    except Exception:
        pass


def _cleanup_usb():
    """Release USB device and rebind kernel driver."""
    global _ite_dev
    if _ite_dev:
        try:
            import usb.util
            usb.util.dispose_resources(_ite_dev._ite8291r3__channel)
        except Exception:
            pass
        _ite_dev = None
    time.sleep(0.1)
    _rebind_kernel_driver()


def _run_audio_loop(brightness=100, direction="up"):
    """Main audio-reactive loop. Blocks until state file says inactive or daemon stops."""
    global _parec_proc, _ite_dev, _running

    print("Audio mode: starting...", flush=True)
    _unbind_kernel_driver()

    try:
        import numpy as np
        sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
        from ite8291r3_ctl.ite8291r3 import (
            get as ite_get, NUM_ROWS, NUM_COLS,
            ROW_BUFFER_LEN, ROW_RED_OFFSET, ROW_GREEN_OFFSET, ROW_BLUE_OFFSET
        )
    except ImportError as e:
        print(f"Audio mode: missing dependency: {e}", flush=True)
        _cleanup_usb()
        return

    _ite_dev = ite_get()
    if not _ite_dev:
        print("Audio mode: ITE8291R3 device not found", flush=True)
        _cleanup_usb()
        return

    hw_brightness = max(1, min(50, brightness * 50 // 100))
    _ite_dev.enable_user_mode(brightness=hw_brightness, save=False)
    time.sleep(0.2)

    bottom_to_top = (direction != "down")

    # PulseAudio env for root
    uid = _active_session_uid()
    pulse_env = os.environ.copy()
    pulse_env['PULSE_SERVER'] = f'unix:/run/user/{uid}/pulse/native'
    pulse_env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'

    # Find monitor source
    result = subprocess.run(['pactl', 'list', 'short', 'sinks'],
                            capture_output=True, text=True, env=pulse_env)
    monitor_source = None
    for line in result.stdout.strip().split('\n'):
        if 'easyeffects_sink' in line:
            monitor_source = 'easyeffects_sink.monitor'
            break
    if not monitor_source:
        result2 = subprocess.run(['pactl', 'get-default-sink'],
                                 capture_output=True, text=True, env=pulse_env)
        monitor_source = f"{result2.stdout.strip()}.monitor"

    parec = subprocess.Popen(
        ['parec', '--format=s16le', '--rate=44100', '--channels=1',
         '-d', monitor_source],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=pulse_env)
    _parec_proc = parec

    print(f"Audio mode: active (brightness={brightness}, direction={direction}, source={monitor_source})", flush=True)

    CHUNK = 2048
    peak_level = 0.001
    last_state_check = time.time()

    try:
        while _running:
            # Check state file frequently for fast deactivation
            now = time.time()
            if now - last_state_check > 0.3:
                last_state_check = now
                if not _is_audio_active():
                    print("Audio mode: deactivated via state file", flush=True)
                    break

            ready, _, _ = select.select([parec.stdout], [], [], 0.1)
            if not ready:
                continue
            raw = parec.stdout.read(CHUNK * 2)
            if not raw or len(raw) < CHUNK * 2:
                time.sleep(0.01)
                continue

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            fft = np.abs(np.fft.rfft(samples))
            freq_bins = len(fft)
            band_edges = np.logspace(np.log10(1), np.log10(freq_bins), NUM_COLS + 1, dtype=int)
            band_edges = np.clip(band_edges, 0, freq_bins - 1)

            bands = np.zeros(NUM_COLS)
            for i in range(NUM_COLS):
                start = band_edges[i]
                end = max(band_edges[i + 1], start + 1)
                bands[i] = np.mean(fft[start:end])

            peak_level = max(peak_level * 0.995, np.max(bands), 0.001)
            bands_norm = np.clip(bands / peak_level, 0, 1.0) ** 0.7

            for row in range(NUM_ROWS):
                arr = [0] * ROW_BUFFER_LEN
                if bottom_to_top:
                    threshold = row / NUM_ROWS
                else:
                    threshold = (NUM_ROWS - 1 - row) / NUM_ROWS
                for col in range(NUM_COLS):
                    if bands_norm[col] > threshold:
                        intensity = min(1.0, (bands_norm[col] - threshold) * NUM_ROWS)
                        hue = (col / NUM_COLS + time.time() * 0.1) % 1.0
                        h = hue * 6
                        c = intensity
                        x = c * (1 - abs(h % 2 - 1))
                        if h < 1: r, g, b = c, x, 0
                        elif h < 2: r, g, b = x, c, 0
                        elif h < 3: r, g, b = 0, c, x
                        elif h < 4: r, g, b = 0, x, c
                        elif h < 5: r, g, b = x, 0, c
                        else: r, g, b = c, 0, x
                        arr[ROW_RED_OFFSET + col] = int(r * 255)
                        arr[ROW_GREEN_OFFSET + col] = int(g * 255)
                        arr[ROW_BLUE_OFFSET + col] = int(b * 255)
                _ite_dev._ite8291r3__set_row_index(row)
                _ite_dev._ite8291r3__send_data(bytearray(arr))

            time.sleep(0.03)

    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        if _parec_proc:
            try:
                _parec_proc.kill()
                _parec_proc.wait(timeout=2)
            except Exception:
                pass
            _parec_proc = None
        _cleanup_usb()
        print("Audio mode: stopped", flush=True)


def _read_state():
    """Read the state file. Returns dict or None."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return None


def _is_audio_active():
    """Check if audio mode is currently requested."""
    state = _read_state()
    return state is not None and state.get("active", False)


def main():
    global _running

    # === Singleton lock ===
    import fcntl as _fcntl
    _lock_path = "/run/nuc-audio-daemon.lock"
    try:
        _lock_fd = open(_lock_path, 'w')
        _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
    except (OSError, IOError):
        print("ERROR: Another instance of audio_daemon is already running. Exiting.", flush=True)
        sys.exit(1)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    print("kbd-audio daemon started", flush=True)

    # Ensure state directory exists
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    while _running:
        state = _read_state()
        if state and state.get("active", False):
            brightness = state.get("brightness", 100)
            direction = state.get("direction", "up")
            _run_audio_loop(brightness=brightness, direction=direction)
        else:
            time.sleep(POLL_INTERVAL)

    print("kbd-audio daemon exiting", flush=True)


if __name__ == "__main__":
    main()

