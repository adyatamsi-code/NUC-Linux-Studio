from pathlib import Path
from typing import Dict, List, Optional
from .core import BackendError, read_text, write_multiple

class FanController:
    def __init__(self, hwmon_path: Path):
        self.hwmon_path = hwmon_path
        self.ctrl_hwmon = self._get_ctrl_hwmon() or hwmon_path
        self._last_cpu_pwm = None
        self._last_dgpu_pwm = None

    def _get_ctrl_hwmon(self) -> Optional[Path]:
        qc71_base = Path("/sys/devices/platform/nuc_wmi/hwmon")
        if not qc71_base.exists():
            qc71_base = Path("/sys/devices/platform/qc71_laptop/hwmon")
        if qc71_base.exists():
            for entry in sorted(qc71_base.iterdir()):
                if entry.is_dir() and entry.name.startswith("hwmon"):
                    # Only return the hwmon that actually has PWM control files
                    if (entry / "pwm1").exists():
                        return entry
        return None

    def _parse_fan_entry(self, fan_label: str, temp_label: str, fan_input: str, pwm_path: Path) -> Dict[str, object]:
        temp_path = self.hwmon_path / f"temp{temp_label}_input"
        fan_value = self.hwmon_path / f"fan{fan_input}_input"
        
        def safe_read(p: Path) -> int:
            try:
                if p.exists():
                    val = read_text(p)
                    return int(val) if val else 0
            except Exception:
                pass
            return 0

        temp_mc = safe_read(temp_path)
        # Sanity: reject corrupt readings (> 150°C or negative)
        if temp_mc > 150000 or temp_mc < 0:
            temp_mc = 0

        return {
            "label": fan_label,
            "temperature_mC": temp_mc,
            "fan_rpm": safe_read(fan_value),
            "pwm_value": safe_read(pwm_path),
            "pwm_path": str(pwm_path),
        }

    def get_status(self) -> Dict[str, Dict[str, object]]:
        status = {}
        cpu_pwm = self.ctrl_hwmon / "pwm1"
        dgpu_pwm = self.ctrl_hwmon / "pwm2"
        
        cpu_pwm_path = cpu_pwm if cpu_pwm.exists() else self.hwmon_path / "pwm1"
        if (self.hwmon_path / "fan1_input").exists() or (self.hwmon_path / "temp1_input").exists() or cpu_pwm_path.exists():
            status["CPU"] = self._parse_fan_entry("CPU", "1", "1", cpu_pwm_path)
            
        dgpu_pwm_path = dgpu_pwm if dgpu_pwm.exists() else self.hwmon_path / "pwm2"
        if (self.hwmon_path / "fan2_input").exists() or (self.hwmon_path / "temp2_input").exists() or dgpu_pwm_path.exists():
            status["dGPU"] = self._parse_fan_entry("dGPU", "2", "2", dgpu_pwm_path)
            
        return status

    FAN_PROFILE_LABELS = {
        "balanced": 1,
        "balanced (1)": 1,
        "silent": 0,
        "silent (0)": 0,
        "performance": 2,
        "performance (2)": 2,
        "benchmark": 3,
        "benchmark (3)": 3,
    }

    PROFILE_FALLBACK_SPEEDS = {
        0: 50,
        1: 25,
        2: 90,
        3: 100,
    }

    def _scale_pwm(self, value: int) -> int:
        if 0 <= value <= 100: return int(round(value * 255 / 100))
        if 0 <= value <= 255: return value
        raise BackendError("Fan PWM value must be 0-100 or 0-255")

    def get_manual_control_path(self) -> Optional[Path]:
        for path in Path("/sys/devices/platform").glob("*/manual_control"):
            return path
        return None

    def enable_manual_control(self) -> bool:
        manual_path = self.get_manual_control_path()
        if not manual_path:
            return False
        try:
            current = read_text(manual_path)
            if current.strip() != "1":
                write_multiple({manual_path: "1"})
            return True
        except Exception:
            return False

    def disable_manual_control(self):
        """Disable manual fan control, letting the EC handle fans natively."""
        manual_path = self.get_manual_control_path()
        if manual_path:
            try:
                write_multiple({manual_path: "0"})
            except Exception:
                pass

    def set_fan_profile(self, profile_name: str) -> None:
        profile_key = profile_name.strip().lower()
        profile = self.FAN_PROFILE_LABELS.get(profile_key)
        if profile is None:
            raise BackendError(
                f"Unknown fan profile '{profile_name}'. Supported profiles: Balanced, Silent, Performance, Benchmark."
            )
        
        last_error = None
        try:
            self.set_power_profile(profile)
            # Disable manual control so hardware takes over
            manual_path = self.get_manual_control_path()
            if manual_path:
                try: write_multiple({manual_path: "0"})
                except Exception: pass
            return
        except BackendError as e:
            last_error = str(e)

        if not self.enable_manual_control():
            if last_error:
                raise BackendError(f"Failed to set hardware profile: {last_error}\nAlso could not enable manual fan control via sysfs.")
            else:
                raise BackendError("Could not enable manual fan control via sysfs.")

        fallback = self.PROFILE_FALLBACK_SPEEDS.get(profile, 100)
        self._last_cpu_pwm = None  # Force write by bypassing cache
        self._last_dgpu_pwm = None
        self.set_pwm(cpu_percent=fallback, dgpu_percent=fallback)

    def set_pwm(self, cpu_percent: Optional[int] = None, dgpu_percent: Optional[int] = None) -> None:
        if cpu_percent is None and dgpu_percent is None: raise BackendError("At least one of cpu_percent or dgpu_percent must be provided")

        if cpu_percent == self._last_cpu_pwm and dgpu_percent == self._last_dgpu_pwm:
            return  # Skip redundant writes to avoid kernel WMI spam

        writes = {}
        if cpu_percent is not None:
            enable_path = self.ctrl_hwmon / "pwm1_enable"
            if enable_path.exists(): writes[enable_path] = "1"
            writes[self.ctrl_hwmon / "pwm1"] = str(self._scale_pwm(cpu_percent))
        if dgpu_percent is not None:
            enable_path = self.ctrl_hwmon / "pwm2_enable"
            if enable_path.exists(): writes[enable_path] = "1"
            writes[self.ctrl_hwmon / "pwm2"] = str(self._scale_pwm(dgpu_percent))
            
        if not writes and (cpu_percent is not None or dgpu_percent is not None):
            raise BackendError("Could not find valid CPU/dGPU PWM control paths.")

        try:
            write_multiple(writes)
            self._last_cpu_pwm = cpu_percent
            self._last_dgpu_pwm = dgpu_percent
        except BackendError as exc:
            if "Permission denied" in str(exc) and self.supports_hardware_fan_curves():
                if cpu_percent is not None: self.set_hardware_fan_curve("CPU", [cpu_percent] * 4)
                if dgpu_percent is not None: self.set_hardware_fan_curve("dGPU", [dgpu_percent] * 4)
                self._last_cpu_pwm = cpu_percent
                self._last_dgpu_pwm = dgpu_percent
            else: raise exc

    def get_profile_path(self) -> Optional[Path]:
        for p in [self.hwmon_path / "device" / "profile", self.hwmon_path / "profile"]:
            if p.exists(): return p
        for alt in [
            Path("/sys/devices/platform/nuc_wmi/pm_profile"),
            Path("/sys/devices/platform/qc71_laptop/pm_profile"),
            Path("/sys/devices/platform/qc71_laptop/performance_level"),
            Path("/sys/devices/platform/qc71_laptop/performance_profile"),
            Path("/sys/devices/platform/qc71_laptop/profile"),
            Path("/sys/firmware/acpi/pm_profile"),
            Path("/sys/devices/platform/tuxedo_keyboard/profile"),
            Path("/sys/devices/platform/uniwill/profile"),
            Path("/sys/devices/platform/uniwill/performance_level"),
            Path("/sys/devices/platform/uniwill-laptop/profile"),
            Path("/sys/devices/platform/uniwill-laptop/performance_level"),
            Path("/sys/firmware/acpi/platform_profile")
        ]:
            if alt.exists(): return alt
        return None

    def get_power_profile(self) -> Optional[int]:
        p = self.get_profile_path()
        if p:
            try:
                if p.name == "platform_profile":
                    val = read_text(p)
                    if val in ("quiet", "low-power"): return 1
                    if val == "performance": return 2
                    return 0
                return int(read_text(p))
            except Exception:
                pass
        return None

    def set_power_profile(self, profile: int) -> None:
        """Write profile to EC register (used by driver when physical button cycles).
        Clears manual_control so EC's built-in fan curve takes effect immediately."""
        p = self.get_profile_path()
        if p and p.name != "platform_profile":
            write_multiple({p: str(profile)})

    def apply_fan_override(self, cpu_percent: int, dgpu_percent: int) -> None:
        """Set PWM to the specified percentages.
        We do NOT set manual_control=1 here because that disables the EC's
        profile button handling. Writing to pwm1/pwm2 via hwmon is sufficient
        for manual fan speed control."""
        self._last_cpu_pwm = None
        self._last_dgpu_pwm = None
        self.set_pwm(cpu_percent=cpu_percent, dgpu_percent=dgpu_percent)

    def release_fan_control(self) -> None:
        """Disable manual fan control, let EC handle fans."""
        manual_path = self.get_manual_control_path()
        if manual_path:
            write_multiple({manual_path: "0"})
        self._last_cpu_pwm = None
        self._last_dgpu_pwm = None

    def enforce_benchmark(self) -> None:
        """Re-enforce 100% fans for benchmark mode. Called every poll cycle."""
        manual_path = self.get_manual_control_path()
        if manual_path:
            write_multiple({manual_path: "1"})
        self._last_cpu_pwm = None
        self._last_dgpu_pwm = None
        self.set_pwm(cpu_percent=100, dgpu_percent=100)

    def supports_hardware_fan_curves(self) -> bool:
        device_dir = self.hwmon_path / "device"
        return (device_dir / "custom_fan_curve_cpu").exists() or (device_dir / "fan_curve_cpu").exists()

    def set_hardware_fan_curve(self, label: str, speeds: List[int]) -> None:
        self._last_cpu_pwm = None
        self._last_dgpu_pwm = None
        
        device_dir = self.hwmon_path / "device"
        curve_file = device_dir / f"custom_fan_curve_{label.lower()}"
        if not curve_file.exists():
            curve_file = device_dir / f"fan_curve_{label.lower()}"
        if not curve_file.exists():
            raise BackendError(f"Hardware fan curve file for {label} not found.")

        writes = {}
        if (device_dir / "profile").exists(): writes[device_dir / "profile"] = "3"
        if (device_dir / "fan_mode").exists(): writes[device_dir / "fan_mode"] = "1"
        writes[curve_file] = " ".join(str(s) for s in speeds)
        write_multiple(writes)
