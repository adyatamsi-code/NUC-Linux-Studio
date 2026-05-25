#!/usr/bin/env python3
"""Test EC CTRL_4 bit 7 with bit 6 CLEARED (touchpad enabled).

This is the critical test: can bit 7 control the LED independently
while the touchpad hardware stays alive?

Step 1: Enable touchpad via HID (write 0x03) and EC (clear bit 6)
Step 2: Verify cursor works
Step 3: Set bit 7 only (bit 6 stays 0) → does LED turn on? Does cursor still work?

Run as root:  sudo python3 tools/test_ec_bit7_clean.py
"""
import os, sys, time, struct, fcntl
from pathlib import Path

DEBUG_EC = Path("/sys/devices/platform/nuc_wmi/debug_ec")
TP_ENABLED = Path("/sys/devices/platform/nuc_wmi/touchpad_enabled")

def HIDIOCSFEATURE(length):
    return 0xc0004806 | (length << 16)

def ec_read():
    raw = DEBUG_EC.read_text()
    for part in raw.split():
        if '=' in part:
            addr, val = part.split('=')
            if int(addr, 16) == 0xA6:
                return int(val, 16)
    return None

def ec_write(value):
    DEBUG_EC.write_text(f"a6 {value:02x}")

def hid_write(val):
    """Write HID feature report."""
    fd = os.open("/dev/hidraw3", os.O_RDWR | os.O_NONBLOCK)
    buf = struct.pack('2B', 7, val)
    fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)
    os.close(fd)

def main():
    if os.getuid() != 0:
        print("Run as root!"); sys.exit(1)

    # Step 1: Enable touchpad fully
    print("=== Step 1: Enable touchpad fully ===")
    hid_write(0x03)
    TP_ENABLED.write_text("1")
    time.sleep(0.5)

    ctrl4 = ec_read()
    print(f"CTRL_4 after enable = 0x{ctrl4:02x} = {ctrl4:08b}")
    print(f"  bit 6 = {(ctrl4 >> 6) & 1}  (should be 0 = touchpad on)")
    print(f"  bit 7 = {(ctrl4 >> 7) & 1}  (should be 0)")
    print()
    print(">>> Move your cursor now to confirm touchpad works! (5 sec)")
    time.sleep(5)

    # Step 2: Set ONLY bit 7, keep bit 6 = 0
    new_val = (ctrl4 | 0x80) & ~0x40  # bit7=1, bit6=0
    print(f"=== Step 2: Set bit 7 only ===")
    print(f"Writing CTRL_4 = 0x{new_val:02x} = {new_val:08b}")
    print(f"  bit 6 = {(new_val >> 6) & 1}  (0 = touchpad should stay on)")
    print(f"  bit 7 = {(new_val >> 7) & 1}  (1 = hopefully LED on)")
    ec_write(new_val)
    print()
    print(">>> Check now (10 sec):")
    print("  1. Is the LED ON?")
    print("  2. Can you still move the cursor?")
    time.sleep(10)

    # Read back
    ctrl4_after = ec_read()
    print(f"\nCTRL_4 readback = 0x{ctrl4_after:02x} = {ctrl4_after:08b}")

    # Step 3: Restore
    print(f"\n=== Step 3: Restore original = 0x{ctrl4:02x} ===")
    ec_write(ctrl4)
    print("Done. Report results!")

if __name__ == "__main__":
    main()

