#!/usr/bin/env python3
import sys
from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Skipping old test script code to fix pytest collection
# from linux_nuc_studio.backend import UniwillBackend
# backend = UniwillBackend()
# print("Current profile:", backend.get_power_profile())
# print("Setting to benchmark (3)...")
# backend.set_power_profile(3)
# print("New profile:", backend.get_power_profile())
