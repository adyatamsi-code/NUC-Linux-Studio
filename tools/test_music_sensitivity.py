#!/usr/bin/env python3
"""
ITE8291R3 Music Mode - Sensitivity Finder & Software Audio Reactive Mode

Mode 0x01 uses the hardware ADC (Realtek ALC269 line-in) — it only reacts to
audio passing through the physical analog pins. If you're using Bluetooth
speakers or any output that bypasses the analog path, the hardware ADC sees
silence.

This script has TWO modes:
  1) HARDWARE MODE: Cycles through sensitivity values for CMD 0x02 mode=0x01
     (only works if audio goes through the internal codec analog path)
  2) SOFTWARE MODE: Captures system audio (PulseAudio/PipeWire monitor) and
     drives the keyboard via USB — works with Bluetooth, HDMI, any output.

Usage:
  sudo python3 test_music_sensitivity.py          # hardware mode
  sudo python3 test_music_sensitivity.py --sw     # software audio-reactive mode
"""

import usb.core
import usb.util
import sys
import time
import struct
import signal
import argparse

VENDOR_ID = 0x048D
PRODUCT_IDS = [0x6004, 0x6006, 0xCE00]

# ITE8291R3 has 6 rows x 21 columns
ROWS = 6
COLS = 21


def find_device():
    for pid in PRODUCT_IDS:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=pid)
        if dev:
            print(f"Found ITE8291R3: VID={VENDOR_ID:#06x} PID={pid:#06x}")
            return dev
    return None


def send_ctrl(dev, *payload):
    payload = list(payload)
    if len(payload) < 8:
        payload += [0] * (8 - len(payload))
    dev.ctrl_transfer(
        usb.util.build_request_type(
            usb.util.CTRL_OUT,
            usb.util.CTRL_TYPE_CLASS,
            usb.util.CTRL_RECIPIENT_INTERFACE),
        0x09, 0x0300, 0x0001, payload)


def send_row(dev, row, colors):
    """Send a row of RGB data in direct/per-key mode.
    colors: list of (r,g,b) tuples, length COLS."""
    # Protocol: 0x16, row, 0x00, then 7 bytes per packet (R,G,B triples)
    # Actually the ITE protocol sends rows as:
    # Header: [0x16, row_idx, 0x00, ...colors...]
    # Each row packet is 1+1+1 + 21*3 = 66 bytes? Let's use the known format.
    # Typical format: report with [0x16, row, R0,G0,B0, R1,G1,B1, ...]
    pkt = [0x16, row, 0x00]
    for r, g, b in colors[:COLS]:
        pkt.extend([r, g, b])
    # Pad to expected size
    while len(pkt) < 65:
        pkt.append(0)
    dev.ctrl_transfer(
        usb.util.build_request_type(
            usb.util.CTRL_OUT,
            usb.util.CTRL_TYPE_CLASS,
            usb.util.CTRL_RECIPIENT_INTERFACE),
        0x09, 0x0300, 0x0001, pkt[:65])


def flush_frame(dev):
    """Signal end of frame update."""
    send_ctrl(dev, 0x16, 0x00, 0x00)


def setup_device(dev):
    for cfg in dev:
        for intf in cfg:
            if intf.bInterfaceNumber == 1:
                if dev.is_kernel_driver_active(1):
                    dev.detach_kernel_driver(1)
                    print("Detached kernel driver from interface 1")
    usb.util.claim_interface(dev, 1)
    print("Claimed interface 1")


def hardware_mode(dev):
    """Interactive hardware audio mode sensitivity tester."""
    print("\n" + "=" * 60)
    print("  HARDWARE AUDIO MODE (ADC) - SENSITIVITY SWEEP")
    print("  NOTE: This only works if audio passes through the")
    print("  internal Realtek ALC269 analog path (3.5mm jack, etc.)")
    print("  Bluetooth/HDMI audio will NOT trigger this!")
    print("=" * 60)

    sensitivities = [
        0x01, 0x02, 0x03, 0x05, 0x08, 0x0A, 0x10, 0x15,
        0x20, 0x30, 0x40, 0x50, 0x60, 0x80, 0xA0, 0xC0, 0xFF
    ]

    print("\nPlay audio through the 3.5mm jack or internal speakers.")
    print("Press Enter to advance, 'q' to quit, number to jump.\n")

    for i, sens in enumerate(sensitivities):
        # Disable first
        send_ctrl(dev, 0x02, 0x00, 0x00)
        time.sleep(0.1)

        # Set aurora as base effect
        send_ctrl(dev, 0x08, 0x02, 0x0E, 0x05, 0x32, 0x08, 0x00, 0x01)
        time.sleep(0.3)

        # Enable audio mode with this sensitivity
        send_ctrl(dev, 0x02, 0x01, sens)

        print(f"  [{i+1}/{len(sensitivities)}] Sensitivity: 0x{sens:02X} ({sens}/255)"
              f"  {'▁▂▃▄▅▆▇█'[min(sens * 8 // 256, 7)] * 10}")

        resp = input("    → Enter=next, q=quit, 's'=save this value: ").strip().lower()
        if resp == 'q':
            break
        elif resp == 's':
            print(f"\n  ★ SAVED: Best sensitivity = 0x{sens:02X} ({sens})")
            print(f"    Use: send_ctrl(dev, 0x02, 0x01, 0x{sens:02X})")

    # Cleanup
    send_ctrl(dev, 0x02, 0x00, 0x00)
    send_ctrl(dev, 0x08, 0x02, 0x02, 0x05, 0x32, 0x08, 0x00, 0x01)
    print("\nRestored to breathing. Done!")


def software_mode(dev=None):
    """Software audio-reactive mode using PulseAudio/PipeWire monitor.
    Works with ALL audio outputs including Bluetooth."""
    try:
        import numpy as np
    except ImportError:
        print("ERROR: numpy required. Install with: pip install numpy")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  SOFTWARE AUDIO-REACTIVE MODE")
    print("  Captures system audio (works with Bluetooth, HDMI, etc.)")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Use the ite8291r3 Python library for proper USB communication
    sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
    from ite8291r3_ctl.ite8291r3 import ite8291r3 as ITE_CLASS, get as ite_get, NUM_ROWS, NUM_COLS, ROW_BUFFER_LEN, ROW_RED_OFFSET, ROW_GREEN_OFFSET, ROW_BLUE_OFFSET

    ite_dev = ite_get()
    if not ite_dev:
        print("ERROR: Could not get ITE8291R3 device via library")
        sys.exit(1)

    # Enter user/direct mode
    ite_dev.enable_user_mode(brightness=50, save=False)
    time.sleep(0.3)

    import subprocess
    import os

    # When running as sudo, we need to access the user's PulseAudio session
    sudo_user = os.environ.get('SUDO_USER', '')
    pulse_env = os.environ.copy()
    if sudo_user:
        uid = subprocess.run(['id', '-u', sudo_user], capture_output=True, text=True).stdout.strip()
        pulse_env['PULSE_SERVER'] = f'unix:/run/user/{uid}/pulse/native'
        pulse_env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
        print(f"  Using PulseAudio of user: {sudo_user} (uid {uid})")

    # Find the best monitor source (captures what's playing)
    # Prefer easyeffects_sink if present (routes all audio), otherwise default sink
    result = subprocess.run(
        ['pactl', 'list', 'short', 'sinks'],
        capture_output=True, text=True, env=pulse_env)

    monitor_source = None
    for line in result.stdout.strip().split('\n'):
        if 'easyeffects_sink' in line:
            monitor_source = 'easyeffects_sink.monitor'
            break

    if not monitor_source:
        result2 = subprocess.run(
            ['pactl', 'get-default-sink'],
            capture_output=True, text=True, env=pulse_env)
        default_sink = result2.stdout.strip()
        monitor_source = f"{default_sink}.monitor"
    print(f"  Capturing from: {monitor_source}")
    print(f"  (This captures ALL audio output including Bluetooth)")

    # Start parec to capture audio
    parec = subprocess.Popen(
        ['parec', '--format=s16le', '--rate=44100', '--channels=1',
         '-d', monitor_source],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=pulse_env)

    CHUNK = 2048  # samples per frame
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    def level_to_color(level, col):
        """Convert audio level (0-1) to RGB with position-based hue."""
        hue = (col / NUM_COLS + time.time() * 0.1) % 1.0
        h = hue * 6
        c = level
        x = c * (1 - abs(h % 2 - 1))
        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        return (int(r * 255), int(g * 255), int(b * 255))

    print("\n  ♪ Playing audio will light up the keyboard! ♪\n")

    peak_level = 0.001
    bands = np.zeros(NUM_COLS)

    try:
        while running:
            raw = parec.stdout.read(CHUNK * 2)  # 2 bytes per s16le sample
            if not raw or len(raw) < CHUNK * 2:
                time.sleep(0.01)
                continue

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            # Compute FFT and split into bands
            fft = np.abs(np.fft.rfft(samples))
            freq_bins = len(fft)
            band_edges = np.logspace(
                np.log10(1), np.log10(freq_bins), NUM_COLS + 1, dtype=int)
            band_edges = np.clip(band_edges, 0, freq_bins - 1)

            for i in range(NUM_COLS):
                start = band_edges[i]
                end = max(band_edges[i + 1], start + 1)
                bands[i] = np.mean(fft[start:end])

            # Normalize
            peak_level = max(peak_level * 0.995, np.max(bands), 0.001)
            bands_norm = np.clip(bands / peak_level, 0, 1.0)
            smooth_bands = bands_norm ** 0.7  # gamma for visual pop

            # Build color map for all rows
            color_map = {}
            for row in range(NUM_ROWS):
                threshold = (NUM_ROWS - 1 - row) / NUM_ROWS
                for col in range(NUM_COLS):
                    if smooth_bands[col] > threshold:
                        intensity = min(1.0, (smooth_bands[col] - threshold) * NUM_ROWS)
                        color_map[(row, col)] = level_to_color(intensity, col)
                    else:
                        color_map[(row, col)] = (0, 0, 0)

            # Send to keyboard using proper protocol
            for row in range(NUM_ROWS):
                arr = [0] * ROW_BUFFER_LEN
                for col in range(NUM_COLS):
                    r, g, b = color_map[(row, col)]
                    arr[ROW_RED_OFFSET + col] = r
                    arr[ROW_GREEN_OFFSET + col] = g
                    arr[ROW_BLUE_OFFSET + col] = b
                ite_dev._ite8291r3__set_row_index(row)
                ite_dev._ite8291r3__send_data(bytearray(arr))

            time.sleep(0.03)  # ~30fps

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        parec.terminate()
        parec.wait()
        # Restore
        print("\n  Restoring keyboard...")
        try:
            from ite8291r3_ctl.ite8291r3 import effects as ite_effects
            ite_dev.set_effect(ite_effects["breathing"](speed=5, brightness=50, color=8, save=1))
        except:
            pass
        print("  Done! Restored to breathing.")


def main():
    parser = argparse.ArgumentParser(description="ITE8291R3 Music Mode Tester")
    parser.add_argument('--sw', '--software', action='store_true',
                        help='Use software audio capture (works with Bluetooth/HDMI)')
    parser.add_argument('--hw', '--hardware', action='store_true',
                        help='Test hardware ADC mode sensitivity (default)')
    args = parser.parse_args()

    if args.sw:
        software_mode(None)
    else:
        dev = find_device()
        if not dev:
            print("Device not found!")
            sys.exit(1)
        setup_device(dev)
        hardware_mode(dev)


if __name__ == '__main__':
    main()

