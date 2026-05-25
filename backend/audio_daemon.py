#!/usr/bin/env python3
"""
Keyboard audio-reactive daemon for NUC Linux Studio.

Watches /var/lib/nuc-linux-studio/audio_mode for activation.
When active, captures system audio via PipeWire/PulseAudio and drives
per-key RGB on the ITE8291R3 keyboard backlight via USB HID.

State file format (JSON):
  {"active": true, "brightness": 100, "direction": "up", "color": [R, G, B] or null}

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

# Shared USB helpers — works both as installed service (/opt/.../backend/) and direct run
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
try:
    from backend.usb_utils import unbind_ite_driver, rebind_ite_driver
except ImportError:
    # Already inside the package directory
    from usb_utils import unbind_ite_driver, rebind_ite_driver

STATE_FILE = Path("/var/lib/nuc-linux-studio/audio_mode")
POLL_INTERVAL = 1.0  # seconds between state file checks
WATCHDOG_TIMEOUT = 30.0  # seconds: self-stop if state file mtime hasn't changed (app crash)

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
    rebind_ite_driver()


def _run_audio_loop(brightness=100, direction="up", color=None, _skip_unbind=False):
    """Main audio-reactive loop. Blocks until state file says inactive or daemon stops.

    color: [R, G, B] list for single-color mode, or None for rainbow (default).
    _skip_unbind: True when restarting with new params (USB already owned by this process).
    Returns True if stopped cleanly (full cleanup needed), False if restarting with new params.
    """
    global _parec_proc, _ite_dev, _running

    print("Audio mode: starting...", flush=True)
    if not _skip_unbind:
        unbind_ite_driver()

    try:
        import numpy as np
        from ite8291r3_ctl.ite8291r3 import (
            get as ite_get, NUM_ROWS, NUM_COLS,
            ROW_BUFFER_LEN, ROW_RED_OFFSET, ROW_GREEN_OFFSET, ROW_BLUE_OFFSET
        )
    except ImportError as e:
        print(f"Audio mode: missing dependency: {e}", flush=True)
        _cleanup_usb()
        return True  # full stop

    # GPU acceleration — try CuPy (CUDA), fall back to NumPy silently
    # Must do a real GPU op to verify CUDA runtime (libnvrtc) is available
    USE_GPU = False
    cp = np
    try:
        import cupy as _cp
        # Verify the GPU runtime actually works before committing
        _test = _cp.array([1.0], dtype=_cp.float32) * 2.0
        _ = float(_test[0])
        cp = _cp
        USE_GPU = True
        print("Audio mode: GPU acceleration enabled (CuPy/CUDA)", flush=True)
    except Exception as _gpu_err:
        print(f"Audio mode: GPU unavailable ({type(_gpu_err).__name__}), using CPU", flush=True)

    # Reuse existing device handle on param-restart, otherwise open fresh
    if _skip_unbind and _ite_dev is not None:
        dev = _ite_dev
    else:
        dev = ite_get()
        if not dev:
            print("Audio mode: ITE8291R3 device not found", flush=True)
            _cleanup_usb()
            return True  # full stop
        _ite_dev = dev

    hw_brightness = max(1, min(50, brightness * 50 // 100))
    dev.enable_user_mode(brightness=hw_brightness, save=False)
    time.sleep(0.2)

    bottom_to_top = (direction != "down")

    # PulseAudio env for root
    uid = _active_session_uid()
    pulse_env = os.environ.copy()
    pulse_env['PULSE_SERVER'] = f'unix:/run/user/{uid}/pulse/native'
    pulse_env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'

    # Find monitor source
    # Always follow the default sink — that's where the user's audio actually goes
    result2 = subprocess.run(['pactl', 'get-default-sink'],
                             capture_output=True, text=True, env=pulse_env)
    default_sink = result2.stdout.strip()
    monitor_source = f"{default_sink}.monitor" if default_sink else "easyeffects_sink.monitor"

    parec = subprocess.Popen(
        ['parec', '--format=s16le', '--rate=44100', '--channels=1',
         '-d', monitor_source],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=pulse_env)
    _parec_proc = parec

    print(f"Audio mode: active (brightness={brightness}, direction={direction}, "
          f"source={monitor_source}, color={'single' if color else 'rainbow'})", flush=True)

    CHUNK = 2048
    peak_level = 0.001
    last_state_check = time.time()
    _last_heartbeat = time.time()

    # Pre-compute log-spaced band edges once (on GPU if available)
    band_edges = np.logspace(np.log10(1), np.log10(CHUNK // 2 + 1), NUM_COLS + 1, dtype=int)
    band_edges = np.clip(band_edges, 0, CHUNK // 2)
    if USE_GPU:
        band_edges_gpu = cp.array(band_edges)

    # Pre-normalise fixed color to 0-1 floats once
    fixed_r = fixed_g = fixed_b = None
    if color:
        fixed_r = color[0] / 255.0
        fixed_g = color[1] / 255.0
        fixed_b = color[2] / 255.0

    # Pre-build column hue offsets for rainbow mode
    col_hue_offsets = np.array([c / NUM_COLS for c in range(NUM_COLS)], dtype=np.float32)
    if USE_GPU:
        col_hue_offsets_gpu = cp.array(col_hue_offsets)

    # Snapshot of params this loop was started with — detect changes
    _loop_params = {"brightness": brightness, "direction": direction, "color": color}
    _param_restart = False  # set True when breaking due to param change (skip USB cleanup)

    try:
        while _running:
            # Check state file frequently for fast deactivation or param changes
            now = time.time()
            if now - last_state_check > 0.3:
                last_state_check = now
                # Heartbeat: touch mtime every 10s so watchdog knows app is alive
                if now - _last_heartbeat > 10.0:
                    _last_heartbeat = now
                    try:
                        STATE_FILE.touch()
                    except Exception:
                        pass
                cur = _read_state()
                if not cur or not cur.get("active", False):
                    print("Audio mode: deactivated via state file", flush=True)
                    break
                # Restart loop if color/brightness/direction changed
                new_params = {
                    "brightness": cur.get("brightness", 100),
                    "direction": cur.get("direction", "up"),
                    "color": cur.get("color", None),
                }
                if new_params != _loop_params:
                    print("Audio mode: params changed, restarting loop...", flush=True)
                    _param_restart = True
                    break

            ready, _, _ = select.select([parec.stdout], [], [], 0.1)
            if not ready:
                continue
            raw = parec.stdout.read(CHUNK * 2)
            if not raw or len(raw) < CHUNK * 2:
                time.sleep(0.01)
                continue

            # --- GPU hot path ---
            if USE_GPU:
                samples_gpu = cp.frombuffer(raw, dtype=cp.int16).astype(cp.float32) / 32768.0
                fft_gpu = cp.abs(cp.fft.rfft(samples_gpu))
                freq_bins = len(fft_gpu)

                bands_gpu = cp.zeros(NUM_COLS, dtype=cp.float32)
                for i in range(NUM_COLS):
                    start = int(band_edges[i])
                    end = max(int(band_edges[i + 1]), start + 1)
                    end = min(end, freq_bins)
                    bands_gpu[i] = cp.mean(fft_gpu[start:end])

                peak_level = float(max(peak_level * 0.995,
                                       float(cp.max(bands_gpu).get()), 0.001))
                bands_norm_gpu = cp.clip(bands_gpu / peak_level, 0.0, 1.0) ** 0.7

                # Build full frame buffer on GPU: shape (NUM_ROWS, ROW_BUFFER_LEN)
                frame_gpu = cp.zeros((NUM_ROWS, ROW_BUFFER_LEN), dtype=cp.uint8)

                hue_time_offset = (float(time.time()) * 0.1) % 1.0
                for row in range(NUM_ROWS):
                    threshold = float(row) / NUM_ROWS if bottom_to_top else float(NUM_ROWS - 1 - row) / NUM_ROWS
                    mask = bands_norm_gpu > threshold
                    intensity = cp.clip((bands_norm_gpu - threshold) * NUM_ROWS, 0.0, 1.0)

                    if fixed_r is not None:
                        r_vals = (intensity * fixed_r * 255).astype(cp.uint8)
                        g_vals = (intensity * fixed_g * 255).astype(cp.uint8)
                        b_vals = (intensity * fixed_b * 255).astype(cp.uint8)
                    else:
                        hue = (col_hue_offsets_gpu + hue_time_offset) % 1.0
                        h6 = hue * 6
                        c = intensity
                        x = c * (1 - cp.abs(h6 % 2 - 1))
                        h6i = h6.astype(cp.int32)
                        r_ch = cp.where(h6i < 1, c, cp.where(h6i < 2, x, cp.where(h6i < 3, cp.zeros_like(c),
                               cp.where(h6i < 4, cp.zeros_like(c), cp.where(h6i < 5, x, c)))))
                        g_ch = cp.where(h6i < 1, x, cp.where(h6i < 2, c, cp.where(h6i < 3, c,
                               cp.where(h6i < 4, x, cp.zeros_like(c)))))
                        b_ch = cp.where(h6i < 3, cp.zeros_like(c), cp.where(h6i < 4, c,
                               cp.where(h6i < 5, c, x)))
                        r_vals = (r_ch * mask * 255).astype(cp.uint8)
                        g_vals = (g_ch * mask * 255).astype(cp.uint8)
                        b_vals = (b_ch * mask * 255).astype(cp.uint8)

                    frame_gpu[row, ROW_RED_OFFSET:ROW_RED_OFFSET + NUM_COLS] = r_vals * mask
                    frame_gpu[row, ROW_GREEN_OFFSET:ROW_GREEN_OFFSET + NUM_COLS] = g_vals * mask
                    frame_gpu[row, ROW_BLUE_OFFSET:ROW_BLUE_OFFSET + NUM_COLS] = b_vals * mask

                # Transfer entire frame to CPU in one shot
                frame_cpu = cp.asnumpy(frame_gpu)
                for row in range(NUM_ROWS):
                    dev._ite8291r3__set_row_index(row)
                    dev._ite8291r3__send_data(bytearray(frame_cpu[row].tolist()))

            else:
                # --- CPU fallback (NumPy) ---
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                fft = np.abs(np.fft.rfft(samples))
                freq_bins = len(fft)
                be = np.clip(band_edges, 0, freq_bins - 1)

                bands = np.zeros(NUM_COLS)
                for i in range(NUM_COLS):
                    start = be[i]
                    end = max(be[i + 1], start + 1)
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
                            if fixed_r is not None:
                                r = fixed_r * intensity
                                g = fixed_g * intensity
                                b = fixed_b * intensity
                            else:
                                hue = (col / NUM_COLS + (time.time() * 0.1) % 1.0) % 1.0
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
                    dev._ite8291r3__set_row_index(row)
                    dev._ite8291r3__send_data(bytearray(arr))

            time.sleep(0.016)  # ~60fps target

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
        if not _param_restart:
            _cleanup_usb()
            print("Audio mode: stopped", flush=True)
        else:
            print("Audio mode: restarting with new params (keeping USB open)", flush=True)
    return not _param_restart


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
            # --- Watchdog: check state file mtime before entering audio loop ---
            # If mtime is stale (app crashed and isn't updating the file), self-stop.
            try:
                age = time.time() - STATE_FILE.stat().st_mtime
                if age > WATCHDOG_TIMEOUT:
                    print(f"kbd-audio: state file stale ({age:.0f}s) — app may have crashed. Self-stopping.", flush=True)
                    try:
                        STATE_FILE.write_text('{"active": false}')
                    except Exception:
                        pass
                    _running = False
                    break
            except Exception:
                pass

            brightness = state.get("brightness", 100)
            direction = state.get("direction", "up")
            color = state.get("color", None)  # [R,G,B] or null
            skip = False
            while _running:
                full_stop = _run_audio_loop(brightness=brightness, direction=direction,
                                             color=color, _skip_unbind=skip)
                if full_stop:
                    break  # fully deactivated, go back to outer poll loop
                # Param restart — re-read latest state
                state = _read_state()
                if not state or not state.get("active", False):
                    break
                brightness = state.get("brightness", 100)
                direction = state.get("direction", "up")
                color = state.get("color", None)
                skip = True  # USB already owned
        else:
            # --- Watchdog: if state file exists and active=false, check for stale active=true ---
            # Periodically check if state file disappeared (edge case: deleted, not written false)
            if STATE_FILE.exists():
                try:
                    age = time.time() - STATE_FILE.stat().st_mtime
                    if age > WATCHDOG_TIMEOUT * 2:
                        # File is very old and inactive — clean exit, nothing to do
                        print("kbd-audio: idle for extended period, exiting cleanly.", flush=True)
                        _running = False
                        break
                except Exception:
                    pass
            time.sleep(POLL_INTERVAL)

    print("kbd-audio daemon exiting", flush=True)


if __name__ == "__main__":
    main()
