from pathlib import Path
from typing import Optional
import subprocess
from .core import BackendError, read_text, write_multiple

class PowerController:
    def get_cpu_energy_preference(self) -> str:
        path = Path("/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference")
        if path.exists():
            return read_text(path)
        return "unsupported"

    def set_cpu_energy_preference(self, preference: str) -> None:
        try:
            pp_map = {
                "power": "power-saver",
                "balance_power": "balanced",
                "balance_performance": "balanced",
                "default": "balanced",
                "performance": "performance"
            }
            mapped = pp_map.get(preference, "balanced")
            subprocess.run(["powerprofilesctl", "set", mapped], check=True, capture_output=True)
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise BackendError("Could not set CPU preference via powerprofilesctl. The daemon is likely stopped.")

    def get_manual_control(self) -> bool:
        for path in Path("/sys/devices/platform").glob("*/manual_control"):
            if path.exists():
                return read_text(path).strip() == "1"
        return False

    def set_manual_control(self, enabled: bool) -> None:
        writes = {}
        for path in Path("/sys/devices/platform").glob("*/manual_control"):
            writes[path] = "1" if enabled else "0"
        if not writes:
            raise BackendError("EC Manual Control is not supported on this system.")
        write_multiple(writes)