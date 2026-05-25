#!/usr/bin/env python3
"""Test writing to potential lightbar zone 2 registers."""
from pathlib import Path
import time

# Use the ec module directly
EC_WRITE = Path("/sys/devices/platform/nuc_wmi/debug_ec")

def ec_write(addr, value):
    """Write via the driver's ec_write mechanism."""
    # We need to write through the driver. Let's use the lightbar LED sysfs instead.
    pass

# Actually let's just set the known lightbar to full RED and see what happens
# Then probe by writing to 074C, 074D, 074E as a potential zone 2

# First, set current lightbar to bright RED via multi_intensity
LED_PATH = Path("/sys/class/leds/uniwill:multicolor:status/")
MI = LED_PATH / "multi_intensity"
BRIGHTNESS = LED_PATH / "brightness"

print("Setting lightbar to full RED via sysfs...")
BRIGHTNESS.write_text("255")
MI.write_text("255 0 0")
print(f"multi_intensity set to: {MI.read_text().strip()}")
print(f"brightness: {BRIGHTNESS.read_text().strip()}")
print()
print("Check: is the LEFT side red? Is the RIGHT side still dim/off?")
print()
print("Now let's try writing to potential zone 2 addresses (0x074C-0x074E)...")
print("We'll need to add write support to debug_ec, or use a different approach.")
print()
print("Alternative: Let's check if there's a pattern in the EC dump.")
print("The lightbar might use a WMI method instead of raw EC registers for zone 2.")

