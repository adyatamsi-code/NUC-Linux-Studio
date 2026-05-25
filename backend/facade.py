from .battery import BatteryController
from .fans import FanController
from .keyboard import KeyboardController, StatusLedController, LightbarController
from .power import PowerController
from .core import BackendError, find_uniwill_hwmon

class UniwillBackend:
    def __init__(self):
        try:
            self._battery = BatteryController()
        except Exception:
            self._battery = None

        try:
            self._fans = FanController(find_uniwill_hwmon())
            self.hwmon_path = self._fans.hwmon_path
        except Exception:
            self._fans = None
            self.hwmon_path = None

        try:
            self._keyboard = KeyboardController()
        except Exception:
            self._keyboard = None

        try:
            self._status_led = StatusLedController()
        except Exception:
            self._status_led = None

        try:
            self._lightbar = LightbarController()
        except Exception:
            self._lightbar = None

        try:
            self._power = PowerController()
        except Exception:
            self._power = None


    # --- Battery ---
    def get_battery_info(self):
        if not self._battery: return {}
        return self._battery.get_info()

    def get_battery_charge_limit(self):
        if not self._battery: return 100
        info = self._battery.get_info()
        threshold = info.get("charge_control_end_threshold")
        if threshold:
            try: return int(threshold.strip())
            except (ValueError, AttributeError): pass
        return 100

    def set_battery_charge_limit(self, limit):
        if not self._battery: return
        self._battery.set_charge_limit(limit)

    def get_ssd_info(self):
        if not self._battery: return {"drives": []}
        return self._battery.get_ssd_info()

    # --- Fans ---
    def get_fan_speed(self, fan_idx):
        if not self._fans: return 0
        return self._fans.get_fan_speed(fan_idx) if hasattr(self._fans, 'get_fan_speed') else 0

    def get_fan_status(self):
        if not self._fans: return {}
        return self._fans.get_status()

    def apply_fan_override(self, cpu_percent, dgpu_percent):
        if not self._fans: return
        self._fans.apply_fan_override(cpu_percent, dgpu_percent)

    def set_fan_curve(self, curve_data):
        if not self._fans: return
        if hasattr(self._fans, 'set_fan_curve'):
            self._fans.set_fan_curve(curve_data)

    def enable_manual_fan_control(self):
        if not self._fans: return
        self._fans.enable_manual_control()

    def disable_manual_fan_control(self):
        if not self._fans: return
        self._fans.disable_manual_control()

    # --- Power ---
    def get_power_profile(self):
        """Read hardware power profile from EC via nuc_wmi driver."""
        from pathlib import Path
        pm_path = Path("/sys/devices/platform/nuc_wmi/pm_profile")
        if pm_path.exists():
            try:
                val = int(pm_path.read_text().strip())
                # EC values: 0=Silent, 1=Balanced, 2=Performance
                if val in (0, 1, 2):
                    return val
            except (ValueError, OSError):
                pass
        # Fallback to CPU energy preference
        if not self._power: return 1
        pref = self._power.get_cpu_energy_preference()
        pref_map = {"power": 0, "power-saver": 0, "balance_power": 1, "balanced": 1,
                    "default": 1, "balance_performance": 1, "performance": 2}
        return pref_map.get(pref.strip() if pref else "", 1)

    def set_power_profile(self, profile):
        """Write hardware power profile to EC via nuc_wmi driver."""
        from pathlib import Path
        pm_path = Path("/sys/devices/platform/nuc_wmi/pm_profile")
        if pm_path.exists():
            try:
                pm_path.write_text(str(profile))
                return
            except OSError:
                pass
        if not self._power: return
        profile_map = {0: "power", 1: "balance_power", 2: "performance"}
        pref = profile_map.get(profile, "balance_power") if isinstance(profile, int) else profile
        self._power.set_cpu_energy_preference(pref)

    # --- Keyboard ---
    def set_keyboard_backlight_brightness(self, percent):
        """Sets brightness and caches the value in the state file so the daemon stays in sync."""
        if not self._keyboard: return
        self._keyboard.set_backlight_brightness(percent)
        try:
            with open("/tmp/nuc_kbd_brightness", "w") as f:
                f.write(str(percent))
        except Exception:
            pass

    def set_keyboard_backlight_color(self, color_tuple):
        if not self._keyboard: return
        self._keyboard.set_backlight_color(color_tuple)

    def set_keyboard_effect(self, effect_name, color=None, speed=5, brightness=100, reactive=False, direction=None):
        if not self._keyboard: return
        self._keyboard.set_effect(effect_name, color or "random", speed, brightness, reactive=reactive, direction=direction)

    def set_per_key_colors(self, key_color_map, brightness=100):
        if not self._keyboard: return
        self._keyboard.set_per_key_colors(key_color_map, brightness)

    # --- Toggles ---
    def get_fn_lock_toggle_state(self):
        if not self._keyboard: return None
        return self._keyboard.get_fn_lock_toggle_state()

    def set_fn_lock_toggle_state(self, enabled):
        if not self._keyboard: return
        self._keyboard.set_fn_lock_toggle_state(enabled)

    def get_super_key_toggle_state(self):
        if not self._keyboard: return None
        return self._keyboard.get_super_key_toggle_state()

    def set_super_key_toggle_state(self, enabled):
        if not self._keyboard: return
        self._keyboard.set_super_key_toggle_state(enabled)

    def get_touchpad_toggle_state(self):
        if not self._keyboard: return None
        return self._keyboard.get_touchpad_toggle_state()

    # --- Lightbar ---
    def set_lightbar_color(self, color_tuple, brightness=100):
        if self._lightbar:
            self._lightbar.set_color(color_tuple, brightness)
        elif self._status_led:
            self._status_led.set_color(color_tuple)

    def supports_lightbar_rainbow(self):
        if self._lightbar:
            return self._lightbar.supports_rainbow()
        return False

    def set_lightbar_effect(self, effect_name, color=None, brightness=100):
        if self._lightbar:
            self._lightbar.set_effect(effect_name, color or (255, 255, 255), brightness)
        elif self._status_led:
            self._status_led.set_color(color or (255, 255, 255))

    def reset_lightbar(self):
        """Reset the lightbar to a clean off state (flush all EC settings)."""
        if self._lightbar:
            self._lightbar.reset()

    def set_touchpad_toggle_state(self, enabled):
        if not self._keyboard: return
        self._keyboard.set_touchpad_toggle_state(enabled)

