#!/usr/bin/env python3
"""Test ITE8291R3 grid mapping. Lights up one key per row to identify the grid layout."""
import sys
sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
from ite8291r3_ctl import ite8291r3

print("Opening device...")
dev = ite8291r3.get()

# Test ESC row (hw 5) right side — find INS, SCRLK, DEL
color_map = {
    (5, 12): (255, 0, 0),     # col 12 = RED (F12?)
    (5, 13): (0, 255, 0),     # col 13 = GREEN
    (5, 14): (0, 0, 255),     # col 14 = BLUE
    (5, 15): (255, 255, 0),   # col 15 = YELLOW
    (5, 16): (255, 0, 255),   # col 16 = MAGENTA
    (5, 17): (0, 255, 255),   # col 17 = CYAN
}

dev.set_key_colors(color_map, brightness=50, save=True)
print("ESC row (hw5) cols 12-17:")
print("  12=RED, 13=GREEN, 14=BLUE, 15=YELLOW, 16=MAGENTA, 17=CYAN")
print("Tell me which keys (F12, Ins, ScrLk, Del) light up and what color!")

