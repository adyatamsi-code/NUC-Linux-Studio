#!/usr/bin/env python3
"""Test EC CTRL_4 bit 7 for independent LED control.

Uses the existing debug_ec sysfs — NO driver rebuild needed.
This only reads/writes EC register 0x07A6 via the safe WMI interface.

Run as root:  sudo python3 tools/test_ec_led_bit7.py
"""
import sys
import time
from pathlib import Path

DEBUG_EC = Path("/sys/devices/platform/nuc_wmi/debug_ec")

def ec_read_byte(offset):
    """Read a single byte from EC page 0x07, given offset."""
    raw = DEBUG_EC.read_text()
    for part in raw.split():
        if '=' in part:
            addr, val = part.split('=')
            if int(addr, 16) == offset:
                return int(val, 16)
    return None

def ec_write_byte(offset, value):
    """Write a byte to EC page 0x07 at offset."""
    DEBUG_EC.write_text(f"{offset:02x} {value:02x}")

def main():
    if not DEBUG_EC.exists():
        print("ERROR: debug_ec sysfs not found. Is nuc_wmi driver loaded?")
        sys.exit(1)

    # Read current CTRL_4 (offset 0xA6)
    current = ec_read_byte(0xA6)
    if current is None:
        print("ERROR: Could not read EC register 0xA6")
        sys.exit(1)

    print(f"Current CTRL_4 (0x07A6) = 0x{current:02x} = {current:08b}")
    print(f"  Bit 6 (TOUCHPAD_TOGGLE_OFF) = {(current >> 6) & 1}")
    print(f"  Bit 7 = {(current >> 7) & 1}")
    print()

    # Test: set bit 7 WITHOUT touching bit 6
    # This should (hopefully) turn the LED on without disabling the touchpad
    test_val = current | 0x80  # set bit 7
    print(f"TEST: Writing 0x{test_val:02x} (bit 7 = 1, bit 6 unchanged)")
    print("Watch the touchpad LED for 10 seconds...")
    print("  - Is the LED ON?")
    print("  - Can you still move the cursor?")
    ec_write_byte(0xA6, test_val)

    time.sleep(10)

    # Restore
    print(f"\nRestoring original value: 0x{current:02x}")
    ec_write_byte(0xA6, current)
    print("Done. Was the LED on during those 10 seconds?")

if __name__ == "__main__":
    main()

