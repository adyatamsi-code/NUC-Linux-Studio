#!/usr/bin/env python3
"""
Probe the ITE8291R3 6×21 grid row by row.
Lights up each row with a color gradient so you can identify which column
maps to which physical key.

Usage: sudo python3 tools/probe_grid_full.py [row]
  - No arg: interactive, goes row by row
  - With arg: lights up only that row (0-5)
"""
import sys, time
sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
from ite8291r3_ctl import ite8291r3

# Distinct colors for columns 0-20
COL_COLORS = [
    (255,   0,   0),  # 0  red
    (255, 128,   0),  # 1  orange
    (255, 255,   0),  # 2  yellow
    (128, 255,   0),  # 3  lime
    (  0, 255,   0),  # 4  green
    (  0, 255, 128),  # 5  spring
    (  0, 255, 255),  # 6  cyan
    (  0, 128, 255),  # 7  azure
    (  0,   0, 255),  # 8  blue
    (128,   0, 255),  # 9  violet
    (255,   0, 255),  # 10 magenta
    (255,   0, 128),  # 11 rose
    (255, 255, 255),  # 12 white
    (128, 128, 255),  # 13 light blue
    (255, 128, 128),  # 14 light red
    (128, 255, 128),  # 15 light green
    (255, 255, 128),  # 16 light yellow
    (128, 255, 255),  # 17 light cyan
    (255, 128, 255),  # 18 light magenta
    (200, 200, 200),  # 19 grey
    (100, 100, 100),  # 20 dark grey
]

PHYSICAL_ROWS = {
    5: "ESC / F1-F12 / INS / SCRLK / DEL",
    4: "` 1-0 - = BKSP HOME",
    3: "TAB QWERTYUIOP [] \\ PGUP",
    2: "CAPS ASDFGHJKL ;' ENTER PGDN",
    1: "SHIFT ZXCVBNM ,./ SHIFT ↑ END",
    0: "CTRL FN WIN ALT SPACE ALT MENU CTRL ← ↓ →",
}

def light_row(dev, row):
    cmap = {}
    for col in range(21):
        cmap[(row, col)] = COL_COLORS[col]
    dev.set_key_colors(cmap, brightness=50, save=True)

def print_legend():
    print("\nColumn color legend:")
    names = ["red","orange","yellow","lime","green","spring","cyan","azure",
             "blue","violet","magenta","rose","white","lt-blue","lt-red",
             "lt-green","lt-yellow","lt-cyan","lt-magenta","grey","dk-grey"]
    for i, n in enumerate(names):
        print(f"  col {i:2d} = {n}")

dev = ite8291r3.get()
if not dev:
    print("ERROR: ITE8291R3 device not found"); sys.exit(1)

print_legend()

if len(sys.argv) > 1:
    row = int(sys.argv[1])
    print(f"\n=== HW Row {row} — expected physical: {PHYSICAL_ROWS.get(row, '?')} ===")
    light_row(dev, row)
    print("Look at the keyboard and note which key has which color.")
else:
    for row in [5, 4, 3, 2, 1, 0]:
        print(f"\n=== HW Row {row} — expected physical: {PHYSICAL_ROWS.get(row, '?')} ===")
        light_row(dev, row)
        print("Look at the keyboard. Note which physical key has which color.")
        input("Press Enter for next row...")
    print("\nDone! Now tell me what you see for each row.")

