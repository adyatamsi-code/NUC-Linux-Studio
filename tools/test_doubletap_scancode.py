ng#!/usr/bin/env python3
"""Test if double-tap emits a scancode on the keyboard evdev device.

Run as root:  sudo python3 tools/test_doubletap_scancode.py

Then double-tap the touchpad LED corner and watch for output.
Also try Fn+F7 for comparison.
Press Ctrl+C to stop.
"""
import subprocess
import sys

def find_keyboard_event():
    """Find AT Translated Set 2 keyboard event device."""
    try:
        result = subprocess.run(
            ["grep", "-l", "AT Translated Set 2", "/sys/class/input/event*/device/name"],
            capture_output=True, text=True, shell=False
        )
    except Exception:
        pass

    # Alternative: parse /proc/bus/input/devices
    try:
        with open("/proc/bus/input/devices") as f:
            content = f.read()
        blocks = content.split("\n\n")
        for block in blocks:
            if "AT Translated Set 2" in block:
                for line in block.splitlines():
                    if line.startswith("H: Handlers="):
                        for part in line.split():
                            if part.startswith("event"):
                                return f"/dev/input/{part}"
    except Exception:
        pass

    return None

def main():
    ev = find_keyboard_event()
    if ev:
        print(f"Found keyboard: {ev}")
    else:
        print("Could not find AT Translated Set 2 keyboard, listing all:")
        subprocess.run(["cat", "/proc/bus/input/devices"], text=True)
        print("\nPlease run: sudo evtest /dev/input/eventN  (pick the keyboard)")
        sys.exit(1)

    print(f"\nRunning evtest on {ev}")
    print("Double-tap the touchpad LED corner and watch for scancodes.")
    print("Also try Fn+F7 for comparison. Press Ctrl+C to stop.\n")

    try:
        subprocess.run(["evtest", ev])
    except KeyboardInterrupt:
        print("\nStopped.")
    except FileNotFoundError:
        print("evtest not installed. Install with: sudo dnf install evtest")

if __name__ == "__main__":
    main()

