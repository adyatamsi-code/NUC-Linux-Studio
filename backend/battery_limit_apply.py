#!/usr/bin/env python3
"""
Apply saved battery charge limit at boot.
Reads charge_limit from the user's settings.json and writes it to sysfs.
Designed to be run as a systemd service (as root) at boot.

Search order: real user home dirs first, then /root last.
This ensures the actual user's preference wins over any stale root config.

Write order: charging_profile first, charge_control_end_threshold last.
On this hardware (nuc_wmi) writing charging_profile resets the numeric
threshold back to the firmware default for that profile (e.g. "stationary"
resets to 80).  Writing the numeric threshold after charging_profile ensures
the exact value the user chose is what the kernel enforces.
"""
import json
import sys
from pathlib import Path

# Real user home dirs first — root config is a last resort fallback only
CONFIG_PATHS = []
try:
    for user_dir in sorted(Path("/home").iterdir()):
        cfg = user_dir / ".config" / "nuc_linux_studio" / "settings.json"
        CONFIG_PATHS.append(cfg)
except Exception:
    pass
CONFIG_PATHS.append(Path("/root/.config/nuc_linux_studio/settings.json"))


def find_battery_paths():
    threshold_paths = []
    profile_paths = []
    base = Path("/sys/class/power_supply")
    if base.exists():
        for entry in base.iterdir():
            t = entry / "charge_control_end_threshold"
            if t.exists():
                threshold_paths.append(t)
    for driver in ["nuc_wmi", "qc71_laptop"]:
        cp = Path(f"/sys/devices/platform/{driver}/charging_profile")
        if cp.exists():
            profile_paths.append(cp)
            break
    # Return profile paths first so they're written before the numeric threshold.
    # The numeric threshold must be written LAST because writing charging_profile
    # on this hardware resets charge_control_end_threshold to the profile default.
    return profile_paths + threshold_paths


def apply_limit(limit: int):
    paths = find_battery_paths()
    if not paths:
        print("No battery threshold sysfs paths found", file=sys.stderr)
        return
    for path in paths:
        try:
            if path.name == "charging_profile":
                if limit <= 60:
                    val = "stationary"
                elif limit <= 80:
                    val = "balanced"
                else:
                    val = "high_capacity"
            elif path.name == "charge_control_end_threshold":
                val = str(limit)
            else:
                continue
            path.write_text(val)
            print(f"Set {path} = {val}")
        except Exception as e:
            print(f"Failed to write {path}: {e}", file=sys.stderr)


def main():
    limit = None
    for cfg in CONFIG_PATHS:
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text())
                if "charge_limit" in data:
                    limit = int(data["charge_limit"])
                    print(f"Found charge_limit={limit} in {cfg}")
                    break
            except Exception as e:
                print(f"Failed to read {cfg}: {e}", file=sys.stderr)

    if limit is None:
        print("No charge_limit found in any config file — defaulting to 80%")
        limit = 80

    apply_limit(limit)

if __name__ == "__main__":
    main()
