#!/usr/bin/env python3
"""Probe EC registers around lightbar area to find additional LED zones."""
from pathlib import Path

# debug_ec dumps EC registers 0x0740-0x07AF in "offset=value" format
DEBUG_EC = Path("/sys/devices/platform/nuc_wmi/debug_ec")

data = DEBUG_EC.read_text().strip()
print("EC Register Dump (page 0x07, offsets 0x40–0xAF):")
print(data)
print()
print("Key registers:")
print("  0x0748 = LIGHTBAR_CTRL")
print("  0x0749 = RED")
print("  0x074A = GREEN")
print("  0x074B = BLUE")
print()
print("Look for other non-zero values that might be additional LED zones.")

