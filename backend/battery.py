from pathlib import Path
from typing import Dict, List
import subprocess
from .core import BackendError, read_text, write_multiple

class BatteryController:
    def __init__(self):
        self.battery_paths = self._find_battery_paths()

    def _find_battery_paths(self) -> List[Path]:
        result: List[Path] = []
        base = Path("/sys/class/power_supply")
        if not base.exists():
            return result
        for entry in base.iterdir():
            threshold = entry / "charge_control_end_threshold"
            if threshold.exists():
                result.append(threshold)

        # Also check for TongFang/Uniwill specific sysfs attributes on nuc_wmi or qc71_laptop
        for driver in ["nuc_wmi", "qc71_laptop"]:
            charging_profile = Path(f"/sys/devices/platform/{driver}/charging_profile")
            if charging_profile.exists():
                result.append(charging_profile)
                break

        return result

    def get_info(self) -> Dict[str, object]:
        info: Dict[str, object] = {
            "paths": [str(p) for p in self.battery_paths],
            "battery_count": len(self.battery_paths),
        }
        battery_dir = None
        base = Path("/sys/class/power_supply")
        if base.exists():
            for entry in base.iterdir():
                if entry.name.startswith("BAT") and entry.is_dir():
                    battery_dir = entry
                    break
        if battery_dir:
            for k in ["capacity", "status", "charge_control_end_threshold", "manufacturer",
                      "model_name", "cycle_count", "voltage_now", "voltage_min_design",
                      "charge_full", "charge_full_design", "current_now", "technology"]:
                if (battery_dir / k).exists(): info[k] = read_text(battery_dir / k)
            # Calculate battery health percentage
            try:
                full = int(info.get("charge_full", 0))
                design = int(info.get("charge_full_design", 0))
                if design > 0:
                    info["health_pct"] = round((full / design) * 100, 1)
                    info["wear_pct"] = round(100 - (full / design) * 100, 1)
            except Exception:
                pass

        for driver in ["nuc_wmi", "qc71_laptop"]:
            charging_profile = Path(f"/sys/devices/platform/{driver}/charging_profile")
            if charging_profile.exists():
                info["charging_profile"] = read_text(charging_profile)
                break

        return info

    def set_charge_limit(self, limit: int) -> None:
        if limit < 20 or limit > 100: raise BackendError("Battery charge limit must be between 20 and 100")
        if not self.battery_paths:
            raise BackendError("No battery threshold control file is available on this system. Battery limit is not supported via sysfs here.")

        writes = {}
        for path in self.battery_paths:
            if path.name == "charging_profile":
                # Translate percentage to Uniwill charging profile
                if limit <= 60: val = "stationary"
                elif limit <= 80: val = "balanced"
                else: val = "high_capacity"
                writes[path] = val
            elif path.name == "charge_control_end_threshold":
                writes[path] = str(limit)

        write_multiple(writes)

    def get_ssd_info(self) -> Dict[str, object]:
        """Collect NVMe SMART data for all NVMe drives using `nvme smart-log`."""
        import json as _json
        drives = []
        # Enumerate NVMe devices
        nvme_devs = sorted(Path("/dev").glob("nvme[0-9]n[0-9]"))
        for dev in nvme_devs:
            info: Dict[str, object] = {"device": str(dev)}
            # Try nvme smart-log --output-format=json
            try:
                result = subprocess.run(
                    ["nvme", "smart-log", "--output-format=json", str(dev)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    d = _json.loads(result.stdout)
                    info["temperature"] = d.get("temperature", d.get("Temperature Sensor 1", None))
                    # Convert Kelvin to Celsius if value > 200 (raw K reading)
                    if info["temperature"] is not None and int(info["temperature"]) > 200:
                        info["temperature"] = int(info["temperature"]) - 273
                    info["available_spare"] = d.get("avail_spare", d.get("available_spare"))
                    info["available_spare_threshold"] = d.get("spare_thresh", d.get("available_spare_threshold"))
                    info["percentage_used"] = d.get("percent_used", d.get("percentage_used"))
                    info["power_on_hours"] = d.get("power_on_hours")
                    info["power_cycles"] = d.get("power_cycles")
                    info["unsafe_shutdowns"] = d.get("unsafe_shutdowns")
                    info["media_errors"] = d.get("media_errors")
                    info["num_err_log_entries"] = d.get("num_err_log_entries")
                    # Data written/read in 512KB units
                    units_written = d.get("data_units_written")
                    units_read = d.get("data_units_read")
                    if units_written is not None:
                        info["data_written_tb"] = round(int(units_written) * 512 * 1000 / 1e12, 2)
                    if units_read is not None:
                        info["data_read_tb"] = round(int(units_read) * 512 * 1000 / 1e12, 2)
                    info["critical_warning"] = d.get("critical_warning", 0)
                    # Health score: 100 - percentage_used, capped at avail_spare
                    pct_used = info.get("percentage_used")
                    spare = info.get("available_spare")
                    if pct_used is not None:
                        info["health_pct"] = max(0, 100 - int(pct_used))
                    elif spare is not None:
                        info["health_pct"] = int(spare)
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass

            # Try to get model name from nvme id-ctrl
            try:
                r2 = subprocess.run(
                    ["nvme", "id-ctrl", "--output-format=json", str(dev)],
                    capture_output=True, text=True, timeout=5
                )
                if r2.returncode == 0 and r2.stdout.strip():
                    d2 = _json.loads(r2.stdout)
                    mn = d2.get("mn", "").strip()
                    sn = d2.get("sn", "").strip()
                    cap_bytes = d2.get("tnvmcap") or d2.get("unvmcap")
                    if mn:
                        info["model"] = mn
                    if sn:
                        info["serial"] = sn
                    if cap_bytes:
                        info["capacity_gb"] = round(int(cap_bytes) / 1e9, 0)
            except Exception:
                pass

            drives.append(info)

        # Add disk space usage for the root filesystem (storage used/free)
        import shutil as _shutil
        try:
            total, used, free = _shutil.disk_usage("/")
            gb = 1024 ** 3
            for drive in drives:
                drive["disk_total_gb"] = round(total / gb, 1)
                drive["disk_used_gb"]  = round(used  / gb, 1)
                drive["disk_free_gb"]  = round(free  / gb, 1)
                drive["disk_used_pct"] = round(used * 100 / total, 1) if total > 0 else 0
        except Exception:
            pass

        return {"drives": drives}

