#!/usr/bin/env python3
"""Test if the UNIW0001 touchpad emits HID input reports on double-tap.

Run as root:  sudo python3 tools/test_hidraw_read.py

Then double-tap the touchpad LED corner and watch for output.
Press Ctrl+C to stop.
"""
import os
import sys
import select
from pathlib import Path

def find_touchpad_hidraws():
    hidraws = []
    base = Path("/sys/class/hidraw")
    if not base.exists():
        return hidraws
    for d in base.iterdir():
        uevent = d / "device" / "uevent"
        try:
            if uevent.exists() and "UNIW0001" in uevent.read_text():
                hidraws.append(f"/dev/{d.name}")
        except Exception:
            continue
    return hidraws

def main():
    devs = find_touchpad_hidraws()
    if not devs:
        print("No UNIW0001 hidraw devices found!")
        sys.exit(1)

    print(f"Found touchpad hidraw devices: {devs}")
    print("Opening all for blocking read. Double-tap the touchpad LED corner now...")
    print("Press Ctrl+C to stop.\n")

    fds = {}
    for dev in devs:
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            fds[fd] = dev
            print(f"  Opened {dev} (fd={fd})")
        except Exception as e:
            print(f"  Failed to open {dev}: {e}")

    if not fds:
        print("No devices could be opened!")
        sys.exit(1)

    # Use select/poll to wait for data on any of them
    poll = select.poll()
    for fd in fds:
        poll.register(fd, select.POLLIN)

    try:
        while True:
            events = poll.poll(5000)  # 5s timeout
            if not events:
                print("  ... waiting (no data yet, try double-tapping) ...", flush=True)
                continue
            for fd, event in events:
                if event & select.POLLIN:
                    data = os.read(fd, 256)
                    dev = fds[fd]
                    hex_str = ' '.join(f'{b:02x}' for b in data)
                    print(f"  [{dev}] Received {len(data)} bytes: {hex_str}", flush=True)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        for fd in fds:
            os.close(fd)

if __name__ == "__main__":
    main()

