#!/usr/bin/env python3
"""Test per-key brightness on ITE8291R3.

The ITE8291R3 doesn't have a separate per-key brightness channel —
brightness is controlled by the RGB values themselves. This script
tests whether dimming individual keys by scaling their RGB produces
visible per-key brightness differences.

Usage (as root):
  python3 tools/test_perkey_brightness.py

This writes directly to /sys/class/leds/ite8291r3::kbd_backlight/key_colors
"""

import sys
import time
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KEY_COLORS_PATH = Path("/sys/class/leds/ite8291r3::kbd_backlight/key_colors")
BRIGHTNESS_PATH = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")

if not KEY_COLORS_PATH.exists():
    print("ERROR: ITE8291R3 sysfs not found. Is the driver loaded?")
    sys.exit(1)

# Set global brightness to max
BRIGHTNESS_PATH.write_text("255")

# KEY_GRID_MAP subset for top row (F-keys) — hw row 5
# ESC=col0, F1=col1, F2=col2, ... F12=col12
TOP_ROW = 5
COLS = list(range(16))  # ESC through DEL


def write_keys(entries):
    """Write key color entries. Each entry: (row, col, r, g, b)"""
    parts = [f"{r} {c} {rv} {gv} {bv}" for r, c, rv, gv, bv in entries]
    KEY_COLORS_PATH.write_text(" ".join(parts))


def test_gradient():
    """Test 1: Brightness gradient across top row.
    Left = dim (10%), right = full (100%)."""
    print("\n=== Test 1: Brightness Gradient (top row) ===")
    print("Left keys should be dim, right keys bright.")
    entries = []
    for i, col in enumerate(COLS):
        # Scale from 10% to 100%
        factor = 0.1 + 0.9 * (i / max(len(COLS) - 1, 1))
        r = int(255 * factor)
        g = int(100 * factor)
        b = int(0 * factor)  # orange gradient
        entries.append((TOP_ROW, col, r, g, b))
    write_keys(entries)
    input("Press Enter to continue...")


def test_checkerboard():
    """Test 2: Alternating bright/dim in checkerboard pattern."""
    print("\n=== Test 2: Checkerboard Bright/Dim ===")
    print("Alternating keys at 100% and 20% brightness.")
    entries = []
    for row in range(6):
        for col in range(21):
            is_bright = (row + col) % 2 == 0
            factor = 1.0 if is_bright else 0.2
            r = int(0 * factor)
            g = int(200 * factor)
            b = int(255 * factor)  # cyan
            entries.append((row, col, r, g, b))
    write_keys(entries)
    input("Press Enter to continue...")


def test_three_levels():
    """Test 3: Three distinct brightness levels on rows."""
    print("\n=== Test 3: Three Brightness Levels ===")
    print("Row 5 (top)=100%, Row 3 (QWERTY)=50%, Row 1 (ZXCV)=15%")
    entries = []
    levels = {5: 1.0, 4: 0.75, 3: 0.50, 2: 0.35, 1: 0.15, 0: 0.05}
    for row in range(6):
        factor = levels.get(row, 0.5)
        for col in range(21):
            r = int(255 * factor)
            g = int(180 * factor)
            b = int(60 * factor)  # warm gold
            entries.append((row, col, r, g, b))
    write_keys(entries)
    input("Press Enter to continue...")


def test_single_key_levels():
    """Test 4: Single key at different brightness levels."""
    print("\n=== Test 4: Stepping brightness on ESC key ===")
    for pct in [100, 75, 50, 25, 10, 5, 2, 0]:
        factor = pct / 100.0
        r = int(255 * factor)
        g = int(255 * factor)
        b = int(255 * factor)
        write_keys([(TOP_ROW, 0, r, g, b)])
        print(f"  ESC at {pct}% -> RGB({r},{g},{b})")
        time.sleep(1.5)
    print("  Done stepping.")
    input("Press Enter to continue...")


def cleanup():
    """Turn off all keys."""
    entries = [(r, c, 0, 0, 0) for r in range(6) for c in range(21)]
    write_keys(entries)
    print("\nAll keys off.")


if __name__ == "__main__":
    print("ITE8291R3 Per-Key Brightness Test")
    print("=" * 40)
    print("This tests whether per-key brightness works by scaling RGB values.")
    print("The ITE8291R3 has no separate brightness-per-key channel;")
    print("dimming is achieved by reducing RGB intensity.\n")

    try:
        test_gradient()
        test_checkerboard()
        test_three_levels()
        test_single_key_levels()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        print("\nResults: If you saw visible brightness differences between keys,")
        print("per-key brightness is viable! We just scale each key's RGB by a")
        print("per-key brightness factor (0.0-1.0) before sending to hardware.")

