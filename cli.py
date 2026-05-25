#!/usr/bin/env python3
"""Uniwill Linux backend for NUC hardware features.

This module exposes the actual Linux sysfs interfaces discovered on the fedora
system with the UniWill ACPI/hwmon driver.

Features:
- Battery charge limit via /sys/class/power_supply/*/charge_control_end_threshold
- CPU and dGPU fan control via /sys/class/hwmon/*/pwm*
- Status LED color via /sys/class/leds/uniwill:multicolor:status/multi_intensity
- Optional keyboard backlight control via /sys/class/leds/*::kbd_backlight
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BackendError(RuntimeError):
    pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _write_multiple(writes: Dict[Path, str]) -> None:
    needs_elevation = False
    for p in writes.keys():
        if p.exists() and not os.access(p, os.W_OK):
            needs_elevation = True
            break

    if not needs_elevation:
        try:
            for p, v in writes.items():
                if p.exists():
                    p.write_text(v, encoding="utf-8")
            return
        except PermissionError:
            needs_elevation = True
        except Exception as e:
            raise BackendError(f"Failed writing to sysfs: {e}")

    import subprocess
    import shutil

    cmds = []
    for p, v in writes.items():
        if p.exists():
            # Use tee to avoid shell redirection permission errors and capture output cleanly
            cmds.append(f"echo '{v}' | tee '{p}' > /dev/null")
    if not cmds:
        return

    script = " ; ".join(cmds)
    cmd = "pkexec" if shutil.which("pkexec") else "sudo"
    try:
        # Run script and capture all output
        res = subprocess.run([cmd, "sh", "-c", script], capture_output=True, text=True)
        
        if res.stderr and "Permission denied" in res.stderr:
            raise BackendError(f"Kernel rejected write (Permission Denied). Driver mode locked or unsupported. ({res.stderr.strip()})")
        if res.returncode != 0:
            raise BackendError(f"Elevation ({cmd}) failed (code {res.returncode}): {res.stderr.strip()}")
            
    except subprocess.CalledProcessError as exc:
        raise BackendError(f"Command failed: {exc}")


def _write_text(path: Path, value: str) -> None:
    _write_multiple({path: value})


class UniwillBackend:
    def __init__(self) -> None:
        self.hwmon_path = self._find_uniwill_hwmon()
        self.battery_paths = self._find_battery_paths()
        self.status_led_path = self._find_status_led()
        self.keyboard_led_path = self._find_keyboard_backlight()

    def _check_acpi_presence(self) -> bool:
        """Check if the Uniwill ACPI device (INOU0000) is physically present."""
        acpi_dir = Path("/sys/bus/acpi/devices")
        if acpi_dir.exists():
            for entry in acpi_dir.iterdir():
                if entry.name.startswith("INOU0000"):
                    return True
        return False

    def _find_uniwill_hwmon(self) -> Path:
        base = Path("/sys/class/hwmon")
        if not base.exists():
            if self._check_acpi_presence():
                raise BackendError("/sys/class/hwmon is not available, but Uniwill INOU0000 ACPI device is present.")
            raise BackendError("/sys/class/hwmon is not available")

        for entry in base.iterdir():
            name_file = entry / "name"
            if name_file.exists() and _read_text(name_file) == "uniwill":
                return entry

        if self._check_acpi_presence():
            raise BackendError("Uniwill hwmon not found, but INOU0000 ACPI device detected. Is the 'uniwill' driver loaded?")

        raise BackendError("Uniwill hwmon device not found (INOU0000 ACPI device also not detected)")

    def _find_battery_paths(self) -> List[Path]:
        result: List[Path] = []
        base = Path("/sys/class/power_supply")
        if not base.exists():
            return result

        for entry in base.iterdir():
            threshold = entry / "charge_control_end_threshold"
            if threshold.exists():
                result.append(threshold)
        return result

    def _find_status_led(self) -> Optional[Path]:
        candidate = Path("/sys/class/leds/uniwill:multicolor:status")
        if candidate.exists() and (candidate / "multi_intensity").exists():
            return candidate
        return None

    def _find_keyboard_backlight(self) -> Optional[str]:
        """Check if ite8291r3-ctl tool is available for keyboard control."""
        import subprocess
        try:
            result = subprocess.run(
                ["which", "ite8291r3-ctl"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def is_root(self) -> bool:
        return os.geteuid() == 0

    def get_battery_info(self) -> Dict[str, object]:
        info: Dict[str, object] = {
            "paths": [str(p) for p in self.battery_paths],
            "battery_count": len(self.battery_paths),
        }

        # Always attempt to find a battery for monitoring, regardless of threshold support
        battery_dir = None
        base = Path("/sys/class/power_supply")
        if base.exists():
            for entry in base.iterdir():
                if entry.name.startswith("BAT") and entry.is_dir():
                    battery_dir = entry
                    break
                    
        if battery_dir:
            info.update(
                {
                    "capacity": _read_text(battery_dir / "capacity") if (battery_dir / "capacity").exists() else "",
                    "status": _read_text(battery_dir / "status") if (battery_dir / "status").exists() else "",
                    "charge_control_end_threshold": _read_text(battery_dir / "charge_control_end_threshold") if (battery_dir / "charge_control_end_threshold").exists() else "N/A",
                    "manufacturer": _read_text(battery_dir / "manufacturer") if (battery_dir / "manufacturer").exists() else "",
                    "model_name": _read_text(battery_dir / "model_name") if (battery_dir / "model_name").exists() else "",
                }
            )
        return info

    def set_battery_charge_limit(self, limit: int) -> None:
        if limit < 50 or limit > 100:
            raise BackendError("Battery charge limit must be between 50 and 100")

        if not self.battery_paths:
            raise BackendError(
                "No battery threshold control file is available on this system. "
                "Battery limit is not supported via sysfs here."
            )

        writes = {path: str(limit) for path in self.battery_paths}
        _write_multiple(writes)

    def _get_fan_line(self, label: str) -> Optional[Path]:
        if label == "CPU":
            return self.hwmon_path / "pwm1"
        if label == "dGPU":
            return self.hwmon_path / "pwm2"
        return None

    def _parse_fan_entry(self, fan_label: str, temp_label: str, fan_input: str, pwm_path: Path) -> Dict[str, object]:
        temp_path = self.hwmon_path / f"temp{temp_label}_input"
        fan_value = self.hwmon_path / f"fan{fan_input}_input"
        return {
            "label": fan_label,
            "temperature_mC": int(_read_text(temp_path)),
            "fan_rpm": int(_read_text(fan_value)),
            "pwm_value": int(_read_text(pwm_path)),
            "pwm_path": str(pwm_path),
        }

    def get_fan_status(self) -> Dict[str, Dict[str, object]]:
        cpu_pwm = self.hwmon_path / "pwm1"
        dgpu_pwm = self.hwmon_path / "pwm2"
        status = {}
        if cpu_pwm.exists():
            status["CPU"] = self._parse_fan_entry("CPU", "1", "1", cpu_pwm)
        if dgpu_pwm.exists():
            status["dGPU"] = self._parse_fan_entry("dGPU", "2", "2", dgpu_pwm)
        return status

    def _scale_pwm(self, value: int) -> int:
        if 0 <= value <= 100:
            return int(round(value * 255 / 100))
        if 0 <= value <= 255:
            return value
        raise BackendError("Fan PWM value must be 0-100 or 0-255")

    def set_fan_pwm(self, cpu_percent: Optional[int] = None, dgpu_percent: Optional[int] = None) -> None:
        if cpu_percent is None and dgpu_percent is None:
            raise BackendError("At least one of cpu_percent or dgpu_percent must be provided")

        writes = {}
        if cpu_percent is not None:
            enable_path = self.hwmon_path / "pwm1_enable"
            if enable_path.exists():
                writes[enable_path] = "1"  # 1 = Manual mode
            writes[self.hwmon_path / "pwm1"] = str(self._scale_pwm(cpu_percent))
        if dgpu_percent is not None:
            enable_path = self.hwmon_path / "pwm2_enable"
            if enable_path.exists():
                writes[enable_path] = "1"  # 1 = Manual mode
            writes[self.hwmon_path / "pwm2"] = str(self._scale_pwm(dgpu_percent))
            
        _write_multiple(writes)

    def get_profile_path(self) -> Optional[Path]:
        for p in [self.hwmon_path / "device" / "profile", self.hwmon_path / "profile"]:
            if p.exists():
                return p
        for alt in [
            Path("/sys/devices/platform/tuxedo_keyboard/profile"),
            Path("/sys/devices/platform/uniwill/profile"),
            Path("/sys/devices/platform/uniwill/performance_level"),
            Path("/sys/devices/platform/uniwill-laptop/profile"),
            Path("/sys/devices/platform/uniwill-laptop/performance_level"),
            Path("/sys/firmware/acpi/platform_profile")
        ]:
            if alt.exists():
                return alt
        return None

    def get_power_profile(self) -> Optional[int]:
        p = self.get_profile_path()
        if p:
            try:
                if p.name == "platform_profile":
                    val = _read_text(p)
                    if val in ("quiet", "low-power"): return 1
                    if val == "performance": return 2
                    return 0
                return int(_read_text(p))
            except Exception:
                pass
        return None

    def set_power_profile(self, profile: int) -> None:
        p = self.get_profile_path()
        if p:
            if p.name == "platform_profile":
                choices_path = p.parent / "platform_profile_choices"
                choices = _read_text(choices_path).split() if choices_path.exists() else ["balanced", "quiet", "performance"]
                
                val = "balanced"
                if profile == 1:
                    val = "quiet" if "quiet" in choices else "low-power"
                elif profile >= 2:
                    val = "performance"
                
                if val not in choices and "balanced" in choices:
                    val = "balanced"
                _write_multiple({p: val})
            else:
                _write_multiple({p: str(profile)})
        else:
            acpi_call = Path("/proc/acpi/call")
            if acpi_call.exists():
                # Direct EC call for TongFang/Uniwill INOU0000 devices
                _write_multiple({acpi_call: f"\\_SB.PCI0.LPCB.EC0.SPRO {profile}"})
            else:
                raise BackendError(
                    "Hardware power profiles are currently locked by the Linux kernel.\n\n"
                    "To unlock native PL1/PL2 power limits on this TongFang/NUC chassis, "
                    "please compile the official tuxedo-drivers module by running:\n\n"
                    "git clone https://github.com/tuxedocomputers/tuxedo-drivers.git\n"
                    "cd tuxedo-drivers && make && sudo make dkmsinstall"
                )

    def supports_hardware_fan_curves(self) -> bool:
        device_dir = self.hwmon_path / "device"
        return (device_dir / "custom_fan_curve_cpu").exists() or (device_dir / "fan_curve_cpu").exists()

    def set_hardware_fan_curve(self, label: str, speeds: List[int]) -> None:
        device_dir = self.hwmon_path / "device"
        
        curve_file = device_dir / f"custom_fan_curve_{label.lower()}"
        if not curve_file.exists():
            curve_file = device_dir / f"fan_curve_{label.lower()}"
            
        if not curve_file.exists():
            raise BackendError(f"Hardware fan curve file for {label} not found.")

        writes = {}
        if (device_dir / "profile").exists():
            writes[device_dir / "profile"] = "3"
        if (device_dir / "fan_mode").exists():
            writes[device_dir / "fan_mode"] = "1"
            
        writes[curve_file] = " ".join(str(s) for s in speeds)
        _write_multiple(writes)

    def get_status_led_color(self) -> Optional[Tuple[int, int, int]]:
        if self.status_led_path is None:
            return None

        intensity = _read_text(self.status_led_path / "multi_intensity").split()
        if len(intensity) != 3:
            return None
        return tuple(int(x) for x in intensity)

    def set_status_led_color(self, rgb: Tuple[int, int, int]) -> None:
        if self.status_led_path is None:
            raise BackendError("Uniwill status LED is not available")

        max_brightness = int(_read_text(self.status_led_path / "max_brightness"))
        converted = [str(int(round(min(max(c, 0), 255) * max_brightness / 255))) for c in rgb]
        _write_text(self.status_led_path / "multi_intensity", " ".join(converted))

    def get_keyboard_backlight(self) -> Optional[Dict[str, object]]:
        """Get keyboard backlight status using ite8291r3-ctl."""
        if self.keyboard_led_path is None:
            return None

        import subprocess
        try:
            # Get brightness
            brightness_result = subprocess.run(
                ["ite8291r3-ctl", "query", "--brightness"],
                capture_output=True,
                text=True,
                check=True
            )
            brightness = int(brightness_result.stdout.strip())
            percent = int(round(brightness * 100 / 50))
            
            # Get state (effect/color information)
            state_result = subprocess.run(
                ["ite8291r3-ctl", "query", "--state"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse state output - this might need adjustment based on actual output format
            state_info = state_result.stdout.strip()
            
            return {
                "brightness": percent,
                "max_brightness": 100,  # Exposed as percentage
                "state": state_info,
                "available": True
            }
        except subprocess.CalledProcessError:
            return {"available": False, "error": "Failed to query keyboard backlight"}
        except FileNotFoundError:
            return {"available": False, "error": "ite8291r3-ctl tool not found"}

    def set_keyboard_backlight_color(self, rgb: Tuple[int, int, int]) -> None:
        """Set keyboard backlight to a solid RGB color using ite8291r3-ctl."""
        import subprocess
        r, g, b = rgb
        try:
            result = subprocess.run(
                ["ite8291r3-ctl", "monocolor", "--rgb", f"{r},{g},{b}"],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as exc:
            raise BackendError(f"Failed to set keyboard color: {exc.stderr.strip()}") from exc
        except FileNotFoundError:
            raise BackendError("ite8291r3-ctl tool not found. Install it for keyboard RGB control.")

    def set_keyboard_backlight_brightness(self, percent: int) -> None:
        """Set keyboard backlight brightness using ite8291r3-ctl."""
        import subprocess
        if percent < 0 or percent > 100:
            raise BackendError("Brightness must be between 0 and 100")

        # Scale 0-100% to hardware 0-50 range
        hw_brightness = int(round(percent * 50 / 100))
        try:
            result = subprocess.run(
                ["ite8291r3-ctl", "brightness", str(hw_brightness)],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as exc:
            raise BackendError(f"Failed to set keyboard brightness: {exc.stderr.strip()}") from exc
        except FileNotFoundError:
            raise BackendError("ite8291r3-ctl tool not found. Install it for keyboard brightness control.")

    def set_keyboard_effect(self, effect: str, color: str = "random", speed: int = 3, brightness: int = 50) -> None:
        """Set keyboard lighting effect using ite8291r3-ctl."""
        import subprocess
        valid_effects = ["breathing", "wave", "random", "rainbow", "ripple", "marquee", "raindrop", "aurora", "fireworks"]
        if effect not in valid_effects:
            raise BackendError(f"Invalid effect. Valid effects: {', '.join(valid_effects)}")
        
        # Scale 0-100% to hardware 0-50 range
        hw_brightness = int(round(brightness * 50 / 100))
        
        cmd_args = {"speed": ["-s", str(speed)], "color": ["-c", color]}
        
        for _ in range(3):
            cmd = ["ite8291r3-ctl", "effect", effect, "-b", str(hw_brightness)]
            if "speed" in cmd_args:
                cmd.extend(cmd_args["speed"])
            if "color" in cmd_args:
                cmd.extend(cmd_args["color"])
            
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                return
            except subprocess.CalledProcessError as exc:
                err_msg = exc.stderr.strip()
                if "'speed' attr is not needed" in err_msg and "speed" in cmd_args:
                    del cmd_args["speed"]
                    continue
                if "'color' attr is not needed" in err_msg and "color" in cmd_args:
                    del cmd_args["color"]
                    continue
                raise BackendError(f"Failed to set keyboard effect: {err_msg}") from exc
            except FileNotFoundError:
                raise BackendError("ite8291r3-ctl tool not found. Install it for keyboard effects.")


def _parse_rgb(value: str) -> Tuple[int, int, int]:
    parts = [int(x) for x in value.split(",") if x.strip()]
    if len(parts) != 3:
        raise ValueError("Color must be R,G,B")
    return tuple(min(max(v, 0), 255) for v in parts)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Uniwill Linux backend tester")
    parser.add_argument("--battery-limit", type=int, help="Set battery charge limit to 50-100")
    parser.add_argument("--cpu-fan", type=int, help="Set CPU fan PWM percent (0-100)")
    parser.add_argument("--dgpu-fan", type=int, help="Set dGPU fan PWM percent (0-100)")
    parser.add_argument("--status-led", type=str, help="Set status LED color as R,G,B")
    parser.add_argument("--keyboard-color", type=str, help="Set keyboard backlight color as R,G,B using ite8291r3-ctl")
    parser.add_argument("--keyboard-brightness", type=int, help="Set keyboard backlight brightness percent using ite8291r3-ctl")
    parser.add_argument("--keyboard-effect", type=str, help="Set keyboard lighting effect (breathing, wave, rainbow, etc.)")
    parser.add_argument("--keyboard-effect-color", type=str, default="random", help="Color for keyboard effect")
    parser.add_argument("--keyboard-effect-speed", type=int, default=3, help="Speed for keyboard effect")
    parser.add_argument("--keyboard-effect-brightness", type=int, default=50, help="Brightness for keyboard effect")
    parser.add_argument("--lightbar-color", type=str, help="Set lightbar color as R,G,B")
    parser.add_argument("--lightbar-brightness", type=int, default=100, help="Set lightbar brightness percent")
    parser.add_argument("--lightbar-effect", type=str, help="Set lightbar effect (monocolor, rainbow, off)")
    args = parser.parse_args()

    backend = UniwillBackend()
    print("Detected hwmon:", backend.hwmon_path)
    print("Battery paths:", backend.battery_paths)
    print("Status led:", backend.status_led_path)
    print("Keyboard led:", backend.keyboard_led_path)
    print("Battery info:", backend.get_battery_info())
    print("Fan status:", backend.get_fan_status())

    if args.battery_limit is not None:
        try:
            backend.set_battery_charge_limit(args.battery_limit)
            print("Battery limit set to", args.battery_limit)
        except BackendError as exc:
            print("Battery error:", exc)

    if args.cpu_fan is not None or args.dgpu_fan is not None:
        try:
            backend.set_fan_pwm(cpu_percent=args.cpu_fan, dgpu_percent=args.dgpu_fan)
            print("Fan PWM updated")
        except BackendError as exc:
            print("Fan error:", exc)

    if args.status_led is not None:
        try:
            rgb = _parse_rgb(args.status_led)
            backend.set_status_led_color(rgb)
            print("Status LED set to", rgb)
        except BackendError as exc:
            print("Status LED error:", exc)

    if args.keyboard_color is not None:
        try:
            rgb = _parse_rgb(args.keyboard_color)
            backend.set_keyboard_backlight_color(rgb)
            print("Keyboard backlight color set to", rgb)
        except BackendError as exc:
            print("Keyboard color error:", exc)

    if args.keyboard_brightness is not None:
        try:
            backend.set_keyboard_backlight_brightness(args.keyboard_brightness)
            print("Keyboard backlight brightness set to", args.keyboard_brightness)
        except BackendError as exc:
            print("Keyboard brightness error:", exc)

    if args.keyboard_effect is not None:
        try:
            backend.set_keyboard_effect(
                args.keyboard_effect,
                color=args.keyboard_effect_color,
                speed=args.keyboard_effect_speed,
                brightness=args.keyboard_effect_brightness
            )
            print(f"Keyboard effect set to {args.keyboard_effect}")
        except BackendError as exc:
            print("Keyboard effect error:", exc)

    if args.lightbar_color is not None:
        try:
            rgb = _parse_rgb(args.lightbar_color)
            backend.set_lightbar_color(rgb, brightness=args.lightbar_brightness)
            print("Lightbar color set to", rgb)
        except BackendError as exc:
            print("Lightbar color error:", exc)

    if args.lightbar_effect is not None:
        try:
            rgb = (255, 255, 255)
            if args.lightbar_color is not None:
                rgb = _parse_rgb(args.lightbar_color)
            backend.set_lightbar_effect(args.lightbar_effect, rgb, brightness=args.lightbar_brightness)
            print(f"Lightbar effect set to {args.lightbar_effect}")
        except BackendError as exc:
            print("Lightbar effect error:", exc)
