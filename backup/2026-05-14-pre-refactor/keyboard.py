import subprocess
import time
import sys
import math
import os
import signal
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from .core import BackendError, read_text, write_text, write_multiple

class KeyboardController:
    # Sysfs path for the kernel ite8291r3 driver
    _SYSFS_LED = Path("/sys/class/leds/ite8291r3::kbd_backlight")

    def __init__(self):
        self.kernel_driver = self._SYSFS_LED.exists()
        self.tool_available = self._check_tool() if not self.kernel_driver else False
        self._ite_dev = None  # Cached ITE8291R3 device instance
        self._audio_thread = None
        self._audio_stop = threading.Event()

    def _check_tool(self) -> bool:
        """Check if ite8291r3 Python library is importable."""
        try:
            sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
            from ite8291r3_ctl import ite8291r3
            return True
        except ImportError:
            return False

    def get_backlight(self) -> Optional[Dict[str, object]]:
        if self.kernel_driver:
            try:
                brightness = int(read_text(self._SYSFS_LED / "brightness"))
                percent = brightness * 100 // 255
                return {"brightness": percent, "max_brightness": 100, "state": "on" if brightness > 0 else "off", "available": True}
            except Exception:
                return {"available": False, "error": "Failed to read keyboard backlight from sysfs"}
        if not self.tool_available: return None
        try:
            dev = self._get_ite_device()
            brightness = dev.get_brightness()
            state = "off" if dev.is_off() else "on"
            return {"brightness": brightness, "max_brightness": 100, "state": state, "available": True}
        except Exception:
            return {"available": False, "error": "Failed to query keyboard backlight"}

    def set_backlight_color(self, rgb: Tuple[int, int, int]) -> None:
        r, g, b = rgb
        if self.kernel_driver:
            write_text(self._SYSFS_LED / "color", f"{r} {g} {b}")
            return
        try:
            dev = self._get_ite_device()
            dev.set_color((r, g, b), save=True)
        except Exception as exc:
            self._ite_dev = None
            raise BackendError(f"Failed to set keyboard color: {exc}")

    def set_backlight_brightness(self, percent: int) -> None:
        if percent < 0 or percent > 100: raise BackendError("Brightness must be between 0 and 100")
        if self.kernel_driver:
            hw = percent * 255 // 100
            write_text(self._SYSFS_LED / "brightness", str(hw))
            return
        try:
            dev = self._get_ite_device()
            dev.set_brightness(percent)
        except Exception as exc:
            self._ite_dev = None
            raise BackendError(f"Failed to set keyboard brightness: {exc}")

    # ITE8291R3 color name → hardware color index mapping
    # Hardware palette (hardcoded in FW 16.04, cannot be reprogrammed)
    # Hardware palette (ITE8291R3 FW 16.04, matches ite8291r3_ctl library)
    _COLOR_NAME_TO_INDEX = {
        "none": 0, "red": 1, "orange": 2, "yellow": 3, "green": 4,
        "blue": 5, "teal": 6, "purple": 7, "random": 8,
    }

    _DIRECTION_MAP = {"none": 0, "right": 1, "left": 2, "up": 3, "down": 4}

    def set_effect(self, effect: str, color: str = "random", speed: int = 3, brightness: int = 50, reactive: bool = False, direction: str = None) -> None:
        valid_effects = ["off", "breathing", "wave", "random", "rainbow", "ripple", "marquee", "raindrop", "aurora", "fireworks", "reactive", "audio"]
        if effect not in valid_effects:
            raise BackendError(f"Invalid effect. Valid effects: {', '.join(valid_effects)}")
        
        # Map "reactive" to "random" with reactive=True (ITE library has no separate "reactive" effect)
        if effect == "reactive":
            effect = "random"
            reactive = True
        # Stop audio thread if switching away from audio
        if effect != "audio":
            self._stop_audio_reactive()
        # Handle audio mode — software audio-reactive via PipeWire capture
        if effect == "audio":
            self._start_audio_reactive(brightness, direction=direction)
            return
        self._stop_audio_reactive()
        # Re-check kernel driver availability (may have been restored by _stop_audio_reactive)
        if not self.kernel_driver:
            self.kernel_driver = self._SYSFS_LED.exists()
        if self.kernel_driver:
            # Set speed, color_index, and reactive before effect so the driver uses them
            if effect != "off":
                speed_path = self._SYSFS_LED / "speed"
                color_index_path = self._SYSFS_LED / "color_index"
                reactive_path = self._SYSFS_LED / "reactive"
                if speed_path.exists():
                    write_text(speed_path, str(max(0, min(9, speed))))
                if color_index_path.exists():
                    ci = self._COLOR_NAME_TO_INDEX.get(color, 8)
                    write_text(color_index_path, str(ci))
                if reactive_path.exists():
                    write_text(reactive_path, "1" if reactive else "0")
                # Set direction for wave effect
                direction_path = self._SYSFS_LED / "direction"
                if direction and direction_path.exists():
                    di = self._DIRECTION_MAP.get(direction, 1)
                    write_text(direction_path, str(di))
            write_text(self._SYSFS_LED / "effect", effect)
            return
        if effect == "off":
            try:
                dev = self._get_ite_device()
                dev.turn_off()
                return
            except Exception as exc:
                raise BackendError(f"Failed to turn keyboard off: {exc}")
        # Use the Python library directly
        try:
            sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
            from ite8291r3_ctl.ite8291r3 import effects as ite_effects, colors as ite_colors, directions as ite_directions
            dev = self._get_ite_device()
            if effect not in ite_effects:
                raise BackendError(f"Effect '{effect}' not supported by ITE8291R3 library")
            # Brightness: library expects 0-50, UI sends 0-100
            hw_brightness = max(0, min(50, brightness * 50 // 100))
            # Build kwargs for the effect
            kwargs = {"brightness": hw_brightness, "save": 1}
            effect_fn = ite_effects[effect]
            # Try adding speed
            try:
                test = effect_fn(speed=speed, brightness=hw_brightness, save=1)
                kwargs["speed"] = speed
            except (ValueError, TypeError):
                pass
            # Try adding color
            color_idx = ite_colors.get(color, ite_colors.get("random", 8))
            try:
                test = effect_fn(color=color_idx, brightness=hw_brightness, save=1)
                kwargs["color"] = color_idx
            except (ValueError, TypeError):
                pass
            # Try adding direction
            if direction:
                dir_idx = ite_directions.get(direction, 1)
                try:
                    test = effect_fn(direction=dir_idx, brightness=hw_brightness, save=1)
                    kwargs["direction"] = dir_idx
                except (ValueError, TypeError):
                    pass
            # Try adding reactive
            if reactive:
                try:
                    test = effect_fn(reactive=1, brightness=hw_brightness, save=1)
                    kwargs["reactive"] = 1
                except (ValueError, TypeError):
                    pass
            effect_data = effect_fn(**kwargs)
            dev.set_effect(effect_data)
        except BackendError:
            raise
        except Exception as exc:
            self._ite_dev = None
            raise BackendError(f"Failed to set keyboard effect: {exc}")

    _AUDIO_STATE_FILE = Path("/var/lib/nuc-linux-studio/audio_mode")

    def _stop_audio_reactive(self):
        """Stop audio-reactive mode by clearing the daemon state file."""
        # Legacy: stop in-process thread if still running
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_stop.set()
            self._audio_thread.join(timeout=2)
        self._audio_stop.clear()
        # Release USB device so kernel can reclaim
        if self._ite_dev:
            try:
                import usb.util
                usb.util.dispose_resources(self._ite_dev._ite8291r3__channel)
            except Exception:
                pass
        self._ite_dev = None
        # Signal the audio daemon to stop
        try:
            import json
            self._AUDIO_STATE_FILE.write_text(json.dumps({"active": False}))
        except Exception:
            pass
        # Wait for the audio daemon to release the USB device and rebind kernel driver
        key_colors_path = self._SYSFS_LED / "key_colors"
        for _ in range(50):  # up to 5 seconds
            time.sleep(0.1)
            if key_colors_path.exists():
                break
        else:
            # Force rebind if daemon didn't release in time
            self._rebind_kernel_driver()
            time.sleep(0.5)
        # Refresh kernel_driver flag
        self.kernel_driver = self._SYSFS_LED.exists()
        # Clear legacy state file
        try:
            Path("/tmp/nuc_audio_mode").unlink(missing_ok=True)
        except Exception:
            pass

    def _rebind_kernel_driver(self):
        """Rebind the ITE8291R3 USB interface to the kernel driver."""
        try:
            import glob
            for dev_path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
                vendor = Path(dev_path).read_text().strip()
                if vendor == "048d":
                    dev_dir = Path(dev_path).parent
                    intf = dev_dir.name + ":1.1"
                    # First unbind from usbfs if stuck there
                    usbfs_unbind = Path("/sys/bus/usb/drivers/usbfs/unbind")
                    if usbfs_unbind.exists():
                        try:
                            usbfs_unbind.write_text(intf)
                        except Exception:
                            pass
                    time.sleep(0.1)
                    # Now bind to kernel driver
                    bind_path = Path("/sys/bus/usb/drivers/ite8291r3/bind")
                    if bind_path.exists():
                        try:
                            bind_path.write_text(intf)
                        except Exception:
                            pass
                    time.sleep(0.2)
                    self.kernel_driver = self._SYSFS_LED.exists()
                    break
        except Exception:
            pass

    def _start_audio_reactive(self, brightness=100, direction=None):
        """Start software audio-reactive mode by signalling the audio daemon."""
        self._stop_audio_reactive()
        import json
        state = {
            "active": True,
            "brightness": brightness,
            "direction": direction or "up",
        }
        try:
            self._AUDIO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._AUDIO_STATE_FILE.write_text(json.dumps(state))
            print(f"Audio mode: signalled daemon (brightness={brightness}, direction={direction})", flush=True)
        except Exception as e:
            print(f"Audio mode: failed to write state file: {e}", flush=True)

    # Per-key RGB via ite8291r3 Python library (6 rows × 21 cols grid)
    # Key name → (row, col) mapping for the NUC X15 / TongFang 15.6" ANSI keyboard
    # Row 0 = F-key row, Row 1 = number row, Row 2 = QWERTY, Row 3 = ASDF, Row 4 = ZXCV, Row 5 = bottom
    KEY_GRID_MAP = {
        # ITE8291R3 6×21 grid — rows are INVERTED (hw row 5 = physical top row)
        # Column positions account for wider keys taking multiple LED columns
        #
        # Hardware row 5 = Physical row 0 (ESC/F-keys)
        "ESC": (5, 0),
        "F1": (5, 1), "F2": (5, 2), "F3": (5, 3), "F4": (5, 4),
        "F5": (5, 5), "F6": (5, 6), "F7": (5, 7), "F8": (5, 8),
        "F9": (5, 9), "F10": (5, 10), "F11": (5, 11), "F12": (5, 12),
        "INS": (5, 13), "SCRLK": (5, 14), "DEL": (5, 15),
        # Hardware row 4 = Physical row 1 (number row)
        "`": (4, 0), "1": (4, 1), "2": (4, 2), "3": (4, 3), "4": (4, 4),
        "5": (4, 5), "6": (4, 6), "7": (4, 7), "8": (4, 8), "9": (4, 9),
        "0": (4, 10), "-": (4, 11), "=": (4, 12),
        "BACKSPACE": (4, 14), "HOME": (4, 15),
        # Hardware row 3 = Physical row 2 (QWERTY) — Tab=col0-1, Q starts at col 2
        "TAB": (3, 0),
        "Q": (3, 2), "W": (3, 3), "E": (3, 4), "R": (3, 5), "T": (3, 6),
        "Y": (3, 7), "U": (3, 8), "I": (3, 9), "O": (3, 10), "P": (3, 11),
        "[": (3, 12), "]": (3, 13), "\\": (3, 14), "PGUP": (3, 15),
        # Hardware row 2 = Physical row 3 (ASDF) — Caps=col0-1, A starts at col 2
        "CAPS": (2, 0),
        "A": (2, 2), "S": (2, 3), "D": (2, 4), "F": (2, 5), "G": (2, 6),
        "H": (2, 7), "J": (2, 8), "K": (2, 9), "L": (2, 10),
        ";": (2, 11), "'": (2, 12), "ENTER": (2, 14), "PGDN": (2, 15),
        # Hardware row 1 = Physical row 4 (ZXCV) — LShift=col0-2, Z starts at col 3
        "SHIFT": (1, 2), "SHIFT_L": (1, 2),
        "Z": (1, 3), "X": (1, 4), "C": (1, 5), "V": (1, 6), "B": (1, 7),
        "N": (1, 8), "M": (1, 9), ",": (1, 10), ".": (1, 11), "/": (1, 12),
        "SHIFT_R": (1, 13), "↑": (1, 14), "END": (1, 15),
        # Hardware row 0 = Physical row 5 (bottom) — Ctrl=col0-1, Fn=col2, Win=col3
        "CTRL": (0, 0), "CTRL_L": (0, 0),
        "FN": (0, 2), "WIN": (0, 3), "ALT": (0, 4), "ALT_L": (0, 4),
        "SPACE": (0, 7),
        "ALT_R": (0, 10), "MENU": (0, 11), "CTRL_R": (0, 12),
        "←": (0, 13), "↓": (0, 14), "→": (0, 15),
    }

    # Wide keys that span multiple LED columns — all columns get the same color
    WIDE_KEY_EXTRA_COLS = {
        "TAB": [(3, 1)],
        "CAPS": [(2, 1)],
        "SHIFT": [(1, 0), (1, 1)], "SHIFT_L": [(1, 0), (1, 1)],
        "SHIFT_R": [],
        "BACKSPACE": [],
        "ENTER": [(2, 13)],
        "CTRL": [(0, 1)], "CTRL_L": [(0, 1)],
        "SPACE": [(0, 5), (0, 6), (0, 8), (0, 9)],
    }

    def _get_ite_device(self):
        """Get or reuse cached ITE8291R3 device to avoid Resource busy errors."""
        if self._ite_dev is not None:
            return self._ite_dev
        sys.path.insert(0, "/home/adriansandru/Downloads/ite8291r3-ctl")
        from ite8291r3_ctl import ite8291r3
        self._ite_dev = ite8291r3.get()
        if not self._ite_dev:
            raise BackendError("ITE8291R3 device not found")
        return self._ite_dev

    def set_per_key_colors(self, key_colors: Dict[str, Tuple[int, int, int]], brightness: int = 50) -> None:
        """Set per-key RGB colors. key_colors = {"KEY_NAME": (r, g, b), ...}"""
        color_map = {}
        for key_name, rgb in key_colors.items():
            grid_pos = self.KEY_GRID_MAP.get(key_name)
            if grid_pos:
                color_map[grid_pos] = rgb
                extra = self.WIDE_KEY_EXTRA_COLS.get(key_name, [])
                for pos in extra:
                    color_map[pos] = rgb

        if self.kernel_driver:
            # Write via sysfs: "row col r g b row col r g b ..."
            parts = []
            for (row, col), (r, g, b) in color_map.items():
                parts.append(f"{row} {col} {r} {g} {b}")
            payload = " ".join(parts)
            # Retry up to 3 times if device is busy (e.g. after audio mode release)
            for attempt in range(3):
                try:
                    write_text(self._SYSFS_LED / "key_colors", payload)
                    return
                except Exception as e:
                    if attempt < 2 and "Resource busy" in str(e):
                        time.sleep(0.5)
                        self._rebind_kernel_driver()
                        self.kernel_driver = self._SYSFS_LED.exists()
                        time.sleep(0.3)
                        continue
                    raise

        hw_brightness = brightness

        try:
            dev = self._get_ite_device()
            dev.set_key_colors(color_map, brightness=hw_brightness, save=True)
        except (OSError, FileNotFoundError) as exc:
            # Device lost or busy — reset cache and retry once
            self._ite_dev = None
            try:
                time.sleep(0.2)
                dev = self._get_ite_device()
                dev.set_key_colors(color_map, brightness=hw_brightness, save=True)
            except Exception as exc2:
                self._ite_dev = None
                raise BackendError(f"Per-key RGB failed: {exc2}")
        except Exception as exc:
            raise BackendError(f"Per-key RGB failed: {exc}")

    def _qc71_sysfs_path(self, name: str) -> Optional[Path]:
        path = Path("/sys/devices/platform/nuc_wmi") / name
        if not path.exists():
            path = Path("/sys/devices/platform/qc71_laptop") / name
        return path if path.exists() else None

    def _inou_sysfs_path(self, name: str) -> Optional[Path]:
        path = Path("/sys/devices/platform/INOU0000:00") / name
        if path.exists():
            return path
        # Fallback for consolidated driver
        path = Path("/sys/devices/platform/nuc_wmi") / name
        if path.exists():
            return path
        path = Path("/sys/devices/platform/qc71_laptop") / name
        if path.exists():
            return path
        return None

    def get_fn_lock_state(self) -> Optional[bool]:
        path = self._qc71_sysfs_path("fn_lock")
        if path and path.exists():
            return read_text(path).strip() == "1"
        return None

    def set_fn_lock_state(self, enabled: bool) -> None:
        path = self._qc71_sysfs_path("fn_lock")
        if not path or not path.exists():
            raise BackendError("Fn lock sysfs entry is not available on this system.")
        write_text(path, "1" if enabled else "0")

    def get_fn_lock_toggle_state(self) -> Optional[bool]:
        # First try the direct fn_lock state (nuc_wmi driver)
        path = self._qc71_sysfs_path("fn_lock")
        if path and path.exists():
            return read_text(path).strip() == "1"
        path = self._inou_sysfs_path("fn_lock_toggle_enable")
        if path:
            return read_text(path).strip() == "1"
        return None

    def set_fn_lock_toggle_state(self, enabled: bool) -> None:
        # Write to fn_lock directly (nuc_wmi driver)
        path = self._qc71_sysfs_path("fn_lock")
        if path and path.exists():
            write_text(path, "1" if enabled else "0")
            return
        path = self._inou_sysfs_path("fn_lock_toggle_enable")
        if path:
            write_text(path, "1" if enabled else "0")
            return
        raise BackendError("Fn lock sysfs entry not available on this system.")

    def get_super_key_toggle_state(self) -> Optional[bool]:
        path = self._qc71_sysfs_path("super_key_lock")
        if path and path.exists():
            return read_text(path).strip() == "1"
        path = self._inou_sysfs_path("super_key_toggle_enable")
        if path:
            return read_text(path).strip() == "1"
        return None

    def set_super_key_toggle_state(self, enabled: bool) -> None:
        path = self._qc71_sysfs_path("super_key_lock")
        if path and path.exists():
            write_text(path, "1" if enabled else "0")
            return
        path = self._inou_sysfs_path("super_key_toggle_enable")
        if path:
            write_text(path, "1" if enabled else "0")
            return
        raise BackendError("Super key lock not available on this system.")

    def get_touchpad_toggle_state(self) -> Optional[bool]:
        """Get touchpad enabled state. Returns True if touchpad is enabled."""
        # Primary: read from the daemon's persistent state file
        persistent = Path("/var/lib/nuc-linux-studio/touchpad_state")
        if persistent.exists():
            try:
                return persistent.read_text().strip() == "1"
            except Exception:
                pass
        # Fallback: temp state file
        state_file = Path("/tmp/nuc_touchpad_state")
        if state_file.exists():
            try:
                return state_file.read_text().strip() == "1"
            except Exception:
                pass
        # Fallback: read EC sysfs directly
        path = self._qc71_sysfs_path("touchpad_enabled")
        if path and path.exists():
            try:
                return read_text(path).strip() == "1"
            except Exception:
                pass
        return None

    def set_touchpad_toggle_state(self, enabled: bool) -> None:
        """Toggle the touchpad using HID + EC sysfs for reliability.
        
        HID controls the LED and digitizer together, but on some firmware
        states only the LED responds. EC sysfs (touchpad_enabled) provides
        a reliable backup to actually enable/disable the digitizer.
        Writing EC sysfs does NOT trigger dmesg "touchpad toggle pressed"
        (that only fires from i8042 keyboard sequence / Fn+F7).
        """
        from .touchpad_daemon import set_touchpad_led
        try:
            set_touchpad_led(enabled)
        except Exception as exc:
            raise BackendError(f"Failed to toggle touchpad: {exc}")
        # Also write EC sysfs as backup — ensures digitizer state is correct
        # even if HID feature report only affects the LED
        path = self._qc71_sysfs_path("touchpad_enabled")
        if path and path.exists():
            try:
                write_text(path, "1" if enabled else "0")
            except Exception:
                pass

class LightbarController:
    def __init__(self):
        candidate_paths = [
            Path("/sys/devices/platform/INOU0000:00/leds/uniwill:multicolor:status"),
            Path("/sys/class/leds/uniwill:multicolor:status"),
            Path("/sys/class/leds/uniwill:multicolor:status_1"),
            Path("/sys/class/leds/rgb:lightbar"),
            Path("/sys/class/leds/tuxedo:rgb:lightbar"),
            Path("/sys/class/leds/rgb:status"),
            Path("/sys/class/leds/tuxedo:rgb:status"),
            Path("/sys/class/leds/system76::lightbar"),
            Path("/sys/class/leds/system76_acpi::lightbar")
        ]
        # Prefer a path that has animation controls (breathing_animation or rainbow_animation)
        self.path = None
        fallback = None
        for p in candidate_paths:
            if p.exists() and (p / "multi_intensity").exists():
                if fallback is None:
                    fallback = p
                if (p / "rainbow_animation").exists() or (p / "breathing_animation").exists():
                    self.path = p
                    break
        if self.path is None:
            self.path = fallback or Path("/sys/devices/platform/INOU0000:00/leds/uniwill:multicolor:status")

        self.rainbow_path = self.path / "rainbow_animation"
        if not self.rainbow_path.exists():
            for p in [Path("/sys/devices/platform/INOU0000:00/rainbow_animation"),
                      Path("/sys/devices/platform/nuc_wmi/rainbow_animation"),
                      Path("/sys/devices/platform/qc71_laptop/rainbow_animation")]:
                if p.exists():
                    self.rainbow_path = p
                    break

        self.breathing_path = self.path / "breathing_animation"
        if not self.breathing_path.exists():
            self.breathing_path = None
            for p in [Path("/sys/devices/platform/INOU0000:00/breathing_animation"),
                      Path("/sys/devices/platform/nuc_wmi/breathing_animation"),
                      Path("/sys/devices/platform/qc71_laptop/breathing_animation")]:
                if p.exists():
                    self.breathing_path = p
                    break

        self.available = self.path.exists() and (self.path / "multi_intensity").exists()
        self._breathing_thread = None
        self._breathing_stop = threading.Event()

    def reset(self) -> None:
        """Reset the lightbar to a clean off state by flushing all EC settings."""
        self._stop_breathing()
        if not self.available:
            raise BackendError("Uniwill lightbar is not available")
        writes = {self.path / "multi_intensity": "0 0 0"}
        if (self.path / "brightness").exists():
            writes[self.path / "brightness"] = "0"
        if self.rainbow_path.exists():
            writes[self.rainbow_path] = "0"
        if self.breathing_path and self.breathing_path.exists():
            writes[self.breathing_path] = "0"
        write_multiple(writes)

    def get_color(self) -> Optional[Tuple[int, int, int]]:
        if not self.available:
            return None
        intensity = read_text(self.path / "multi_intensity").split()
        return tuple(int(x) for x in intensity) if len(intensity) == 3 else None

    def set_color(self, rgb: Tuple[int, int, int], brightness: int = 100) -> None:
        self._stop_breathing()
        if not self.available:
            raise BackendError("Uniwill lightbar is not available")
        if brightness < 0 or brightness > 100:
            raise BackendError("Lightbar brightness must be between 0 and 100")
        max_brightness = int(read_text(self.path / "max_brightness"))
        scaled = [int(round(min(max(c, 0), 255) * brightness / 100 * max_brightness / 255)) for c in rgb]

        writes = {}
        # Disable rainbow and breathing before setting static color
        if self.rainbow_path.exists():
            writes[self.rainbow_path] = "0"
        if self.breathing_path and self.breathing_path.exists():
            writes[self.breathing_path] = "0"
        writes[self.path / "multi_intensity"] = " ".join(str(v) for v in scaled)
        if (self.path / "brightness").exists():
            writes[self.path / "brightness"] = str(int(round(brightness * max_brightness / 100)))
        write_multiple(writes)

    def set_effect(self, effect: str, color: Optional[Tuple[int, int, int]] = None, brightness: int = 100) -> None:
        if not self.available:
            raise BackendError("Uniwill lightbar is not available")
        effect = effect.lower()
        if effect not in ["breathing", "breathing (asleep)"]:
            self._stop_breathing()
        if effect == "monocolor":
            if color: self.set_color(color, brightness)
            return
        if effect == "off":
            self._stop_breathing()
            writes = {self.path / "multi_intensity": "0 0 0"}
            if (self.path / "brightness").exists():
                writes[self.path / "brightness"] = "0"
            if self.rainbow_path.exists():
                writes[self.rainbow_path] = "0"
            if self.breathing_path and self.breathing_path.exists():
                writes[self.breathing_path] = "0"
            write_multiple(writes)
            return
        if effect == "rainbow":
            if not self.rainbow_path.exists():
                raise BackendError("Rainbow lightbar effect is not supported on this system")
            writes = {}
            if self.breathing_path and self.breathing_path.exists():
                writes[self.breathing_path] = "0"
            writes[self.rainbow_path] = "1"
            write_multiple(writes)
            return
        if effect in ["breathing", "breathing (asleep)"]:
            self._stop_breathing()
            # Try hardware breathing first
            if self.breathing_path and self.breathing_path.exists():
                if color:
                    # Set color without resetting animations
                    self._set_color_for_breathing(color, brightness)
                writes = {}
                if self.rainbow_path.exists():
                    writes[self.rainbow_path] = "0"
                writes[self.breathing_path] = "1"
                write_multiple(writes)
                return
            # Fallback: software breathing
            writes = {}
            if self.rainbow_path.exists():
                writes[self.rainbow_path] = "0"
            if writes:
                write_multiple(writes)
            speed = 4.0 if "asleep" in effect else 2.5
            self._start_breathing(color or (255, 255, 255), brightness, speed)
            return
        # Fallback to static color for unsupported effects
        if color: self.set_color(color, brightness)

    def _set_color_for_breathing(self, rgb: Tuple[int, int, int], brightness: int = 100) -> None:
        """Set color/brightness without disabling animations. Used before enabling breathing."""
        if not self.available:
            return
        max_brightness = int(read_text(self.path / "max_brightness"))
        scaled = [int(round(min(max(c, 0), 255) * brightness / 100 * max_brightness / 255)) for c in rgb]
        writes = {self.path / "multi_intensity": " ".join(str(v) for v in scaled)}
        if (self.path / "brightness").exists():
            writes[self.path / "brightness"] = str(int(round(brightness * max_brightness / 100)))
        write_multiple(writes)

    def supports_rainbow(self) -> bool:
        return self.available and self.rainbow_path.exists()

    def _stop_breathing(self):
        """Stop software breathing thread if running."""
        if self._breathing_thread and self._breathing_thread.is_alive():
            self._breathing_stop.set()
            self._breathing_thread.join(timeout=2)
        self._breathing_stop.clear()

    def _start_breathing(self, rgb: Tuple[int, int, int], brightness: int, period: float):
        """Start a software breathing effect thread."""
        self._stop_breathing()
        self._breathing_stop.clear()
        intensity_path = self.path / "multi_intensity"

        def _breathe():
            max_brightness = 255
            try:
                max_brightness = int(read_text(self.path / "max_brightness"))
            except Exception:
                pass
            step_ms = 50  # 20 fps
            steps_per_half = max(1, int(period * 1000 / step_ms / 2))
            while not self._breathing_stop.is_set():
                # Ramp up
                for i in range(steps_per_half + 1):
                    if self._breathing_stop.is_set():
                        return
                    t = i / steps_per_half
                    factor = (math.sin(t * math.pi - math.pi / 2) + 1) / 2
                    scaled = [int(round(min(max(c, 0), 255) * brightness / 100 * factor * max_brightness / 255)) for c in rgb]
                    try:
                        intensity_path.write_text(" ".join(str(v) for v in scaled))
                    except Exception:
                        return
                    self._breathing_stop.wait(step_ms / 1000)
                # Ramp down
                for i in range(steps_per_half + 1):
                    if self._breathing_stop.is_set():
                        return
                    t = i / steps_per_half
                    factor = (math.sin(t * math.pi + math.pi / 2) + 1) / 2
                    scaled = [int(round(min(max(c, 0), 255) * brightness / 100 * factor * max_brightness / 255)) for c in rgb]
                    try:
                        intensity_path.write_text(" ".join(str(v) for v in scaled))
                    except Exception:
                        return
                    self._breathing_stop.wait(step_ms / 1000)

        self._breathing_thread = threading.Thread(target=_breathe, daemon=True)
        self._breathing_thread.start()



class StatusLedController:
    def __init__(self):
        candidate_paths = [
            Path("/sys/class/leds/uniwill:multicolor:status"),
            Path("/sys/class/leds/rgb:status"),
            Path("/sys/class/leds/tuxedo:rgb:status")
        ]
        self.path = next((p for p in candidate_paths if p.exists() and (p / "multi_intensity").exists()), None)

    def get_color(self) -> Optional[Tuple[int, int, int]]:
        if not self.path: return None
        intensity = read_text(self.path / "multi_intensity").split()
        return tuple(int(x) for x in intensity) if len(intensity) == 3 else None

    def set_color(self, rgb: Tuple[int, int, int], brightness: int = 100) -> None:
        if not self.path: raise BackendError("Uniwill status LED is not available")
        max_brightness = int(read_text(self.path / "max_brightness"))
        converted = [str(int(round(min(max(c, 0), 255) * max_brightness / 255))) for c in rgb]
        write_text(self.path / "multi_intensity", " ".join(converted))

    def set_effect(self, effect: str, color: Optional[Tuple[int, int, int]] = None, brightness: int = 100) -> None:
        if color: self.set_color(color, brightness)
