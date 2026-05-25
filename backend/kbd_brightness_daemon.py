#!/usr/bin/env python3
"""
Keyboard backlight Fn+F8 handler daemon.
Uses a hybrid detection approach:
  1. Monitor /dev/kmsg for WMI "keyboard backlight changed" events
  2. Poll sysfs LED brightness as fallback
  3. Poll ite8291r3-ctl query --brightness as last resort
  4. Detect suspend/resume and re-apply brightness + saved per-key colors

Install as a systemd service: kbd-brightness.service
"""
import os
import sys
import subprocess
import time
import select
import json
import glob
import pwd
from pathlib import Path

# 3 levels: Off, 50%, 100%  (hw values: 0, 128, 255)
BRIGHTNESS_LEVELS = [0, 128, 255]
BRIGHTNESS_LABELS = ["Off", "50%", "100%"]
BRIGHTNESS_PERCENTS = [0, 50, 100]
current_index = 2  # Start at max

STATE_FILE = "/tmp/nuc_kbd_brightness"
PERSISTENT_STATE_FILE = "/var/lib/nuc-linux-studio/kbd_brightness"
SYSFS_LED_GLOB = "/sys/class/leds/*kbd_backlight/brightness"


def _ensure_effect_on():
    """Ensure the keyboard has the correct effect from saved config.
    Restores per-key colors, animated effects, or monocolor+color as appropriate."""
    effect_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/effect")
    if not effect_path.exists():
        return
    try:
        current = effect_path.read_text().strip()
    except Exception:
        return

    # Read saved config
    config_path = _find_config_file()
    saved_effect = None
    saved_speed = None
    saved_colors = {}
    if config_path:
        try:
            with open(config_path) as f:
                config = json.load(f)
            saved_effect = config.get("keyboard_effect")
            saved_speed = config.get("keyboard_speed")
            saved_colors = _migrate_key_names(config.get("keyboard_colors", {}))
        except Exception:
            pass

    if saved_effect == "per-key":
        # Always re-apply per-key colors (they're lost on any effect change or driver reload)
        _restore_per_key_from_config(config_path)
    elif saved_effect in ("gaming", "coding", "writing", "glow"):
        # App-managed per-key themes: the keyboard_colors in config hold the generated
        # per-key RGB map. Restore exactly the same way as "per-key".
        # Do NOT restore as monocolor — that would pick the first orange/green/etc
        # color and show a flat single-color keyboard instead of the theme.
        _restore_per_key_from_config(config_path)
        print(f"  Restored app-managed theme '{saved_effect}' as per-key colors", flush=True)
    elif saved_effect == "audio":
        # Audio mode is handled by the kbd-audio daemon; just ensure state file is active
        try:
            import json as _json
            audio_state = Path("/var/lib/nuc-linux-studio/audio_mode")
            brightness_pct = config.get("keyboard_brightness", 100)
            direction = None
            effect_settings = config.get("keyboard_effect_settings", {})
            if "audio" in effect_settings:
                direction = effect_settings["audio"].get("direction", "up")
            audio_state.write_text(_json.dumps({
                "active": True,
                "brightness": brightness_pct,
                "direction": direction or "up",
            }))
            print(f"  Restored audio mode via state file", flush=True)
        except Exception as e:
            print(f"  Warning: Could not restore audio mode: {e}", flush=True)
    elif saved_effect in ("breathing", "wave", "random", "rainbow", "ripple",
                          "marquee", "raindrop", "aurora", "fireworks",
                          "breathing (multi)", "wave (multi)", "ripple (multi)",
                          "raindrop (multi)", "aurora (multi)", "fireworks (multi)"):
        # Restore animated effect with speed and color_index
        speed_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/speed")
        color_index_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/color_index")
        try:
            if saved_speed is not None and speed_path.exists():
                hw_speed = 10 - int(saved_speed)
                speed_path.write_text(str(max(0, min(9, hw_speed))))
            if color_index_path.exists():
                ci = 8 if "(multi)" in saved_effect else _color_index_from_config(saved_colors)
                color_index_path.write_text(str(ci))
            clean_effect = saved_effect.replace(" (multi)", "")
            effect_path.write_text(clean_effect)
            print(f"  Restored effect={saved_effect} speed={saved_speed}", flush=True)
        except Exception as e:
            print(f"  Warning: Could not restore animated effect: {e}", flush=True)
            try:
                effect_path.write_text("monocolor")
            except Exception:
                pass
    elif current == "off":
        # Restore monocolor with saved color
        color_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/color")
        color_hex = None
        for key, c in saved_colors.items():
            if c and c != "#1a1a1a" and c != "#262D33" and len(c) == 7:
                color_hex = c
                break
        try:
            if color_hex and color_path.exists():
                r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
                color_path.write_text(f"{r} {g} {b}")
            effect_path.write_text("monocolor")
            print(f"  Restored effect=monocolor color={color_hex or 'default'}", flush=True)
        except Exception as e:
            print(f"  Warning: Could not restore effect: {e}", flush=True)


# Color name → hardware index for the ITE8291R3
_COLOR_NAME_TO_INDEX = {
    "none": 0, "white": 1, "orange": 2, "yellow": 3, "green": 4,
    "blue": 5, "purple": 6, "pink": 7, "random": 8,
}

def _color_index_from_config(saved_colors):
    """Determine the best color index from saved keyboard colors."""
    import math
    COLOR_TABLE = {
        0: (255, 0, 0), 1: (255, 128, 0), 2: (255, 255, 0), 3: (0, 255, 0),
        4: (0, 0, 255), 5: (0, 255, 255), 6: (128, 0, 128), 7: (255, 255, 255),
    }
    # Find first non-default color
    for key, c in saved_colors.items():
        if c and c not in ("#1a1a1a", "#262D33", "#2d2640") and len(c) == 7:
            r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
            best = min(COLOR_TABLE.keys(),
                       key=lambda k: (r - COLOR_TABLE[k][0])**2 + (g - COLOR_TABLE[k][1])**2 + (b - COLOR_TABLE[k][2])**2)
            return best
    return 8  # default to random/multi


_KEY_NAME_ALIASES = {
    "Esc": "ESC", "Backspace": "BACKSPACE", "Tab": "TAB", "Caps": "CAPS",
    "Enter": "ENTER", "Shift": "SHIFT", "Ctrl": "CTRL", "Alt": "ALT",
    "Win": "WIN", "Space": "SPACE", "Fn": "FN", "Menu": "MENU",
    "Ins": "INS", "Del": "DEL", "Home": "HOME", "End": "END",
    "PgUp": "PGUP", "PgDn": "PGDN", "ScrLk": "SCRLK", "PrtSc": "INS",
    "Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
}

def _migrate_key_names(colors):
    migrated = {}
    for key, val in colors.items():
        canonical = _KEY_NAME_ALIASES.get(key, key)
        if canonical in migrated and val in ("#262D33", "#1a1a1a"):
            continue
        migrated[canonical] = val
    return migrated


def _restore_per_key_from_config(config_path):
    """Restore per-key colors from the app's saved config."""
    if not config_path:
        return
    try:
        with open(config_path) as f:
            config = json.load(f)
        colors = _migrate_key_names(config.get("keyboard_colors", {}))
        if not colors:
            return
        # Per-key brightness map (factor 0.0-1.0 per key, saved by UI)
        perkey_brightness = config.get("keyboard_perkey_brightness", {})
        key_colors_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/key_colors")
        if not key_colors_path.exists():
            return

        # Import KeyboardController to get KEY_GRID_MAP
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        # Also try /opt path
        opt_parent = "/opt/nuc-linux-studio"
        if opt_parent not in sys.path:
            sys.path.insert(0, opt_parent)

        from backend.keyboard import KeyboardController
        KEY_GRID_MAP = KeyboardController.KEY_GRID_MAP
        WIDE_KEY_EXTRA_COLS = KeyboardController.WIDE_KEY_EXTRA_COLS

        parts = []
        for key_name, hex_color in colors.items():
            if not hex_color or hex_color in ("#1a1a1a", "#262D33") or len(hex_color) != 7:
                continue
            grid_pos = KEY_GRID_MAP.get(key_name)
            if grid_pos:
                r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                # Apply per-key brightness factor if saved
                factor = perkey_brightness.get(key_name, 1.0)
                r, g, b = int(r * factor), int(g * factor), int(b * factor)
                parts.append(f"{grid_pos[0]} {grid_pos[1]} {r} {g} {b}")
                for pos in WIDE_KEY_EXTRA_COLS.get(key_name, []):
                    parts.append(f"{pos[0]} {pos[1]} {r} {g} {b}")
        if parts:
            key_colors_path.write_text(" ".join(parts))
            print(f"  Restored per-key colors ({len(parts)} entries) from config", flush=True)
    except Exception as e:
        print(f"  Warning: Could not restore per-key colors: {e}", flush=True)
        try:
            Path("/sys/class/leds/ite8291r3::kbd_backlight/effect").write_text("monocolor")
        except Exception:
            pass


def set_brightness(hw_value, restore_effect=False):
    """Set ITE8291R3 brightness via kernel sysfs LED interface.
    restore_effect=True: full restore from config (boot/resume only).
    Otherwise: just ensure the sysfs effect isn't 'off' when turning on."""
    global _last_self_write_time
    sysfs = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")
    if sysfs.exists():
        try:
            # Skip redundant write when value is identical and effect is per-key/app-managed.
            # Writing brightness in per-key mode triggers a full 6-row re-push in the driver
            # (ite8291r3_led_set → software RGB scaling → 6×usb_interrupt_msg). This is
            # wasteful and adds unnecessary USB traffic + 2×15ms delays every 5 seconds.
            if not restore_effect:
                try:
                    current_hw = int(sysfs.read_text().strip())
                    if current_hw == hw_value:
                        effect_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/effect")
                        if effect_path.exists():
                            eff = effect_path.read_text().strip()
                            if eff == "per-key":
                                # Nothing changed, no-op — avoid the 6-row USB re-push.
                                return
                except Exception:
                    pass
            sysfs.write_text(str(hw_value))
            _last_self_write_time = time.time()  # stamp so WMI echo is suppressed
            if hw_value > 0:
                if restore_effect:
                    _ensure_effect_on()
                else:
                    # Lightweight: just make sure effect isn't "off"
                    _ensure_effect_not_off()
            return
        except Exception:
            pass
    # Fallback to ite8291r3-ctl if kernel driver not loaded
    try:
        subprocess.run(
            ["ite8291r3-ctl", "brightness", str(hw_value)],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


def _ensure_effect_not_off():
    """Lightweight check when Fn+F8 turns brightness on from off.
    Just make sure the effect sysfs isn't 'off'. Don't do full config restore
    (that's _ensure_effect_on's job, only called on boot/resume).
    If effect is 'per-key', re-apply per-key colors (ITE chip loses buffer at brightness=0)."""
    effect_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/effect")
    if not effect_path.exists():
        return
    try:
        current = effect_path.read_text().strip()
        if current == "off":
            effect_path.write_text("monocolor")
            print("  Effect was 'off', set to 'monocolor'", flush=True)
        elif current == "per-key":
            # ITE8291R3 loses per-key data at brightness=0; restore from config
            config_path = _find_config_file()
            if config_path:
                _restore_per_key_from_config(config_path)
                print("  Re-applied per-key colors after brightness restore", flush=True)
        else:
            # ITE8291R3 loses effect state when brightness goes to 0.
            # Re-write the current effect to the chip so it actually activates.
            effect_path.write_text(current)
            print(f"  Re-applied effect '{current}' after brightness restore", flush=True)
            # Also check if saved config uses per-key — chip volatile buffer is gone.
            config_path = _find_config_file()
            if config_path:
                try:
                    import json as _json
                    with open(config_path) as _f:
                        _cfg = _json.load(_f)
                    if _cfg.get("keyboard_effect") == "per-key":
                        _restore_per_key_from_config(config_path)
                        print("  Re-applied per-key colors (config effect=per-key)", flush=True)
                except Exception:
                    pass
    except Exception:
        pass


def query_brightness():
    """Query current ITE8291R3 brightness via kernel sysfs or ite8291r3-ctl."""
    sysfs = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")
    if sysfs.exists():
        try:
            return int(sysfs.read_text().strip())
        except Exception:
            pass
    # Fallback
    try:
        result = subprocess.run(
            ["ite8291r3-ctl", "query", "--brightness"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


def _hw_to_index(hw_value):
    """Map hardware brightness (0-255) to our 3-level index."""
    if hw_value <= 10:
        return 0  # Off
    elif hw_value <= 180:
        return 1  # 50%
    else:
        return 2  # 100%


def _send_osd(event_type, value, label):
    """Send an OSD message to the NUC OSD service via Unix socket.
    Retries up to 3 times with short backoff if socket not yet available (early boot)."""
    import socket as _socket
    msg = json.dumps({"type": event_type, "value": value, "label": label}).encode("utf-8")
    for attempt in range(3):
        try:
            sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_DGRAM)
            sock.sendto(msg, "/tmp/nuc-osd.sock")
            sock.close()
            return
        except Exception:
            sock.close() if 'sock' in dir() else None
            if attempt < 2:
                time.sleep(0.5)  # OSD may not be ready yet on first boot


def show_osd(label, index):
    """Show keyboard brightness OSD."""
    _send_osd("kbd-brightness", BRIGHTNESS_PERCENTS[index], label)

_uinput_dev = None


def _emit_osd_key(keycode_name):
    """Emit a virtual key to let desktop show native OSD when supported."""
    if _uinput_dev is None:
        return
    try:
        import evdev
        keycode = getattr(evdev.ecodes, keycode_name, None)
        if keycode is None:
            return
        _uinput_dev.write(evdev.ecodes.EV_KEY, keycode, 1)
        _uinput_dev.syn()
        _uinput_dev.write(evdev.ecodes.EV_KEY, keycode, 0)
        _uinput_dev.syn()
    except Exception:
        pass

def _setup_uinput():
    """Create a uinput device that can emit keyboard brightness keys."""
    global _uinput_dev
    try:
        import evdev
        from evdev import UInput, ecodes
        cap = {
            ecodes.EV_KEY: [
                ecodes.KEY_KBDILLUMUP,
                ecodes.KEY_KBDILLUMDOWN,
                ecodes.KEY_KBDILLUMTOGGLE,
                ecodes.KEY_MICMUTE,
                ecodes.KEY_RFKILL,
            ]
        }
        _uinput_dev = UInput(cap, name="nuc-kbd-brightness", bustype=evdev.ecodes.BUS_VIRTUAL)
        print("  Created uinput device for OSD notifications", flush=True)
    except Exception as e:
        print(f"  Warning: Could not create uinput device for OSD: {e}", flush=True)
        _uinput_dev = None


def _find_sysfs_led():
    """Find the sysfs LED brightness file for the keyboard backlight."""
    import glob
    matches = glob.glob(SYSFS_LED_GLOB)
    if matches:
        return matches[0]
    return None


def _wait_for_led_sysfs(timeout_sec=15):
    """Wait for keyboard LED sysfs files to become available after boot/reload."""
    deadline = time.time() + timeout_sec
    brightness_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")
    effect_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/effect")
    key_colors_path = Path("/sys/class/leds/ite8291r3::kbd_backlight/key_colors")
    while time.time() < deadline:
        if brightness_path.exists() and effect_path.exists() and key_colors_path.exists():
            return True
        time.sleep(0.25)
    return brightness_path.exists() and effect_path.exists() and key_colors_path.exists()


def _ensure_ite_driver_bound():
    """Best-effort bind of ITE keyboard USB interfaces to ite8291r3.
    This recovers cases where udev missed the bind during early boot."""
    try:
        subprocess.run(["modprobe", "ite8291r3"], capture_output=True, timeout=5)
    except Exception:
        pass

    bind_path = Path("/sys/bus/usb/drivers/ite8291r3/bind")
    if not bind_path.exists():
        return

    target_pids = {"6004", "6006", "ce00"}
    usb_root = Path("/sys/bus/usb/devices")
    bound_any = False

    for dev in usb_root.glob("*"):
        id_vendor = dev / "idVendor"
        id_product = dev / "idProduct"
        if not id_vendor.exists() or not id_product.exists():
            continue
        try:
            vid = id_vendor.read_text().strip().lower()
            pid = id_product.read_text().strip().lower()
        except Exception:
            continue
        if vid != "048d" or pid not in target_pids:
            continue

        base = dev.name
        for iface in ("1.1", "1.0"):
            iface_name = f"{base}:{iface}"
            iface_path = usb_root / iface_name
            if not iface_path.exists():
                continue

            # If interface is already bound to usbhid, rebind it to ite8291r3.
            drv_link = iface_path / "driver"
            if drv_link.exists():
                try:
                    drv_name = os.path.basename(os.path.realpath(str(drv_link)))
                except Exception:
                    drv_name = ""
                if drv_name == "ite8291r3":
                    continue
                if drv_name == "usbhid":
                    try:
                        Path("/sys/bus/usb/drivers/usbhid/unbind").write_text(iface_name)
                        time.sleep(0.05)
                        print(f"  Unbound usbhid from {iface_name}", flush=True)
                    except Exception:
                        pass
                else:
                    continue

            try:
                bind_path.write_text(iface_name)
                bound_any = True
                print(f"  Bound ite8291r3 to {iface_name}", flush=True)
            except Exception:
                pass

    if bound_any:
        # Allow sysfs/udev to populate class LED nodes.
        time.sleep(0.5)


def _write_state(index):
    """Write current brightness percent to tmp + persistent state files."""
    pct = str(BRIGHTNESS_PERCENTS[index])
    try:
        with open(STATE_FILE, "w") as f:
            f.write(pct)
    except Exception:
        pass
    try:
        p = Path(PERSISTENT_STATE_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(pct)
    except Exception:
        pass


def _percent_to_index(percent):
    try:
        val = int(percent)
    except Exception:
        return None
    if val <= 10:
        return 0
    if val <= 75:
        return 1
    return 2


def _load_index_from_state_files():
    """Load daemon-managed brightness first (persistent, then tmp)."""
    for path in (PERSISTENT_STATE_FILE, STATE_FILE):
        try:
            p = Path(path)
            if not p.exists():
                continue
            idx = _percent_to_index(p.read_text().strip())
            if idx is not None:
                print(f"  Initial brightness from state file {path}: {BRIGHTNESS_LABELS[idx]}", flush=True)
                return idx
        except Exception:
            pass
    return None


def _find_config_file():
    """Find the app config file. Checks both user homes and /root.
    Returns the most recently modified one."""
    import glob
    all_matches = []
    for pattern in [
        "/home/*/.config/nuc_linux_studio/settings.json",
        "/root/.config/nuc_linux_studio/settings.json",
    ]:
        all_matches.extend(glob.glob(pattern))
    if not all_matches:
        return None
    # Return the most recently modified config
    all_matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return all_matches[0]


def _active_session_user():
    """Return (uid, username) for an active graphical user session if available."""
    # Prefer users that have a session bus available.
    for bus in sorted(glob.glob("/run/user/*/bus")):
        try:
            uid = int(bus.split("/")[3])
            if uid == 0:
                continue
            username = pwd.getpwuid(uid).pw_name
            return uid, username
        except Exception:
            continue
    return None, None


def _run_as_active_user(argv):
    uid, username = _active_session_user()
    if not username:
        return False
    env = [
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
    ]
    cmd = ["runuser", "-u", username, "--", "env", *env, *argv]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=8)
        return result.returncode == 0
    except Exception:
        return False


def _run_as_active_user_capture(argv):
    """Run command as active user and return stdout text on success, else None."""
    uid, username = _active_session_user()
    if not username:
        return None
    env = [
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
    ]
    cmd = ["runuser", "-u", username, "--", "env", *env, *argv]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _notify_user(summary, body):
    """Show feedback via our custom OSD, with notify-send as fallback."""
    _osd_type_map = {
        "Microphone": "mic-mute",
        "Airplane Mode": "airplane",
        "Touchpad": "touchpad",
        "Performance": "perf-mode",
    }
    osd_type = _osd_type_map.get(summary, "kbd-brightness")
    osd_value = True if "On" in body or "Muted" in body else False
    _send_osd(osd_type, osd_value, f"{summary}: {body}")


def _get_mic_muted_state():
    """Return True/False for default input mute state, or None if unknown."""
    wp = _run_as_active_user_capture(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]) or ""
    if wp:
        return "MUTED" in wp.upper()
    pa = _run_as_active_user_capture(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"]) or ""
    if pa:
        return pa.strip().lower().endswith("yes")
    return None


def _set_mic_muted_state(target_muted):
    """Set default input mute explicitly. Returns True on success."""
    val = "1" if target_muted else "0"
    ok = _run_as_active_user(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", val])
    if not ok:
        ok = _run_as_active_user(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", val])
    return ok


def _set_gnome_airplane_mode(airplane_on):
    """Set GNOME airplane-mode in the active user session."""
    value = "true" if airplane_on else "false"
    return _run_as_active_user([
        "gsettings", "set",
        "org.gnome.settings-daemon.plugins.rfkill", "airplane-mode", value,
    ])


def _toggle_gnome_airplane_mode():
    """Toggle GNOME airplane-mode in the active user session."""
    uid, username = _active_session_user()
    if not username:
        return False
    env = [
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
    ]
    get_cmd = [
        "runuser", "-u", username, "--", "env", *env,
        "gsettings", "get", "org.gnome.settings-daemon.plugins.rfkill", "airplane-mode",
    ]
    try:
        res = subprocess.run(get_cmd, capture_output=True, text=True, timeout=8)
        if res.returncode != 0:
            return False
        current = res.stdout.strip().lower() == "true"
        return _set_gnome_airplane_mode(not current)
    except Exception:
        return False


def _set_airplane_mode(airplane_on):
    """Set airplane mode state (GNOME first, NetworkManager fallback)."""
    target = "off" if airplane_on else "on"
    gnome_ok = _set_gnome_airplane_mode(airplane_on)
    try:
        s = subprocess.run(["nmcli", "radio", "all", target], capture_output=True, text=True, timeout=8)
        if s.returncode == 0 or gnome_ok:
            print(f"Airplane mode -> {'ON' if airplane_on else 'OFF'}", flush=True)
            _emit_osd_key("KEY_RFKILL")
            _notify_user("Airplane Mode", "On" if airplane_on else "Off")
            return True
    except Exception as e:
        print(f"  Airplane set error: {e}", flush=True)
    return False


def _toggle_airplane_mode():
    """Toggle airplane mode (GNOME first, NetworkManager fallback)."""
    if _toggle_gnome_airplane_mode():
        _emit_osd_key("KEY_RFKILL")
        print("Airplane mode toggled via GNOME", flush=True)
        return True
    try:
        # Use Wi-Fi state as a practical proxy for current radio mode.
        q = subprocess.run(["nmcli", "-t", "-f", "WIFI", "radio"], capture_output=True, text=True, timeout=5)
        if q.returncode != 0:
            return False
        wifi_state = q.stdout.strip().lower()
        return _set_airplane_mode(wifi_state == "enabled")
    except Exception as e:
        print(f"  Airplane toggle error: {e}", flush=True)
    return False


def _toggle_mic_mute():
    """Toggle mic mute directly via wpctl/pactl and show our OSD (not GNOME's)."""
    before = _get_mic_muted_state()

    # Direct toggle — do NOT emit KEY_MICMUTE via uinput (that triggers GNOME's OSD).
    ok = _run_as_active_user(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
    if not ok:
        ok = _run_as_active_user(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"])

    time.sleep(0.15)
    after = _get_mic_muted_state()

    if after is not None:
        target_muted = after
    elif before is not None:
        target_muted = not before
    else:
        target_muted = True  # assume muted if we can't tell

    label = "Microphone: Muted" if target_muted else "Microphone: Active"
    # value=False means "is muted" in the OSD visuals (icon_off when muted)
    _send_osd("mic-mute", not target_muted, label)
    print(f"Mic mute -> {'ON' if target_muted else 'OFF'} (direct)", flush=True)
    return ok


def _restore_keyboard_on_resume():
    """Re-apply keyboard brightness after resume from suspend."""
    global current_index
    print("Resume detected — restoring keyboard brightness...", flush=True)

    # Re-bind on resume in case udev missed it during USB re-enumeration.
    _ensure_ite_driver_bound()

    # Wait for LED sysfs to reappear; keep retrying bind while waiting.
    led_ready = False
    for _ in range(40):
        if _wait_for_led_sysfs(timeout_sec=0.25):
            led_ready = True
            break
        _ensure_ite_driver_bound()

    if not led_ready:
        print("  Warning: ITE8291R3 LED not found after resume", flush=True)
        return

    # Restore brightness/effect/colors through normal path.
    set_brightness(BRIGHTNESS_LEVELS[current_index], restore_effect=True)
    print(f"  Restored brightness: {BRIGHTNESS_LABELS[current_index]}", flush=True)


def _on_brightness_change(new_index):
    """Handle a brightness change: update state, show OSD, set hardware."""
    global current_index
    if new_index == current_index:
        return
    current_index = new_index
    print(f"Kbd brightness -> {BRIGHTNESS_LABELS[current_index]}", flush=True)
    _write_state(current_index)
    show_osd(BRIGHTNESS_LABELS[current_index], current_index)
    set_brightness(BRIGHTNESS_LEVELS[current_index])


def _sync_brightness_from_sysfs():
    """Read actual hardware brightness and sync daemon state.
    Returns True if state changed.

    If something external (gsd-power idle dim, stale WMI event, login screen blanker, etc.)
    sets brightness to 0, we FIGHT BACK and immediately restore the user's chosen brightness.
    During the boot immunity window (first 20s after daemon start) we are extra aggressive
    because gsd-power on the login screen always dims the keyboard when GNOME starts."""
    global current_index, _idle_dimmed, _boot_immunity_until
    hw = query_brightness()
    if hw is None:
        return False
    new_index = _hw_to_index(hw)
    if new_index == current_index:
        if _idle_dimmed and new_index > 0:
            _idle_dimmed = False
        return False
    if new_index == 0 and current_index > 0:
        # Something external turned off the keyboard — restore immediately.
        _idle_dimmed = True
        in_immunity = time.time() < _boot_immunity_until
        reason = "boot-immunity" if in_immunity else "external dim"
        print(f"Kbd brightness: hw=0 ({reason} detected, restoring {BRIGHTNESS_LABELS[current_index]})", flush=True)
        set_brightness(BRIGHTNESS_LEVELS[current_index], restore_effect=in_immunity)
        return False
    if _idle_dimmed and new_index > 0:
        # External agent restored some brightness — re-apply our saved level.
        _idle_dimmed = False
        if new_index != current_index:
            set_brightness(BRIGHTNESS_LEVELS[current_index])
            print(f"Kbd brightness: un-dim detected, re-applied {BRIGHTNESS_LABELS[current_index]}", flush=True)
        return False
    old_label = BRIGHTNESS_LABELS[current_index]
    current_index = new_index
    _write_state(current_index)
    print(f"Kbd brightness sync: {old_label} -> {BRIGHTNESS_LABELS[current_index]} (hw={hw})", flush=True)
    return True

_idle_dimmed = False
_boot_immunity_until = 0.0   # Ignore external hw=0 signals until this timestamp
_last_self_write_time = 0.0  # Timestamp of last daemon-initiated brightness sysfs write
_SELF_WRITE_SUPPRESS_SEC = 1.5  # Suppress WMI echo events for this long after a self-write


def _cycle_brightness():
    """Cycle to the next brightness level and write to sysfs."""
    global current_index
    new_index = (current_index + 1) % len(BRIGHTNESS_LEVELS)
    _on_brightness_change(new_index)


def main():
    global current_index

    # === Singleton lock ===
    import fcntl as _fcntl
    _lock_path = "/run/nuc-kbd-brightness-daemon.lock"
    try:
        _lock_fd = open(_lock_path, 'w')
        _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
    except (OSError, IOError):
        print("ERROR: Another instance of kbd_brightness_daemon is already running. Exiting.", flush=True)
        sys.exit(1)

    print("kbd-brightness daemon started (dmesg mode)", flush=True)

    _setup_uinput()

    last_toggle_time = 0
    last_mic_toggle_time = 0
    last_airplane_toggle_time = 0

    # Read initial brightness from daemon state first (survives app restarts).
    state_idx = _load_index_from_state_files()
    if state_idx is not None and state_idx > 0:
        # Only trust the persistent state if it's a non-zero (non-OFF) value.
        # A persisted 0 is almost always from an external zeroing event (GNOME blanker,
        # service restart after hardware reset) rather than a deliberate user choice.
        current_index = state_idx

    # Fallback: read initial brightness from saved app config.
    # Also used when persistent state is 0 (OFF) — config wins so keyboard is
    # always ON after a daemon restart unless the user explicitly chose OFF via config.
    config_path = _find_config_file()
    if config_path and (state_idx is None or state_idx == 0):
        try:
            with open(config_path) as f:
                config = json.load(f)
            saved_brightness = config.get("keyboard_brightness", None)
            # Treat 0 in config as "not set" — default to 100% so keyboard
            # is always on after restart unless user explicitly chose a level > 0.
            if saved_brightness == 0:
                saved_brightness = 100
            idx = _percent_to_index(saved_brightness)
            if idx is not None:
                current_index = idx
                print(f"  Initial brightness from config: {saved_brightness}% -> {BRIGHTNESS_LABELS[current_index]}", flush=True)
        except Exception as e:
            print(f"  Warning: Could not read config: {e}", flush=True)

    # Ensure device is bound before first restore attempt.
    _ensure_ite_driver_bound()

    # Apply brightness from config to hardware (boot — restore effect)
    set_brightness(BRIGHTNESS_LEVELS[current_index], restore_effect=True)
    _write_state(current_index)
    print(f"  Initial brightness: {BRIGHTNESS_LABELS[current_index]}", flush=True)

    # Service can start before LED sysfs is ready; retry restore once nodes appear.
    if _wait_for_led_sysfs(timeout_sec=20):
        try:
            set_brightness(BRIGHTNESS_LEVELS[current_index], restore_effect=True)
            print("  Boot restore retry: LED sysfs ready", flush=True)
        except Exception as e:
            print(f"  Boot restore retry failed: {e}", flush=True)
    else:
        _ensure_ite_driver_bound()
        print("  Warning: LED sysfs not ready during boot restore window", flush=True)

    # Set boot immunity window — gsd-power and the GNOME login screen blanker
    # both send brightness=0 during the first ~15s after session start.
    # During this window _sync_brightness_from_sysfs will restore without cycling.
    _boot_immunity_until = time.time() + 20.0
    print(f"  Boot immunity window: {20}s (protects against login-screen blanker)", flush=True)

    # Track suspend/resume
    last_suspend_count = None
    try:
        last_suspend_count = int(Path("/sys/power/suspend_stats/success").read_text().strip())
    except Exception:
        try:
            last_suspend_count = int(Path("/sys/power/wakeup_count").read_text().strip())
        except Exception:
            pass

    # Use dmesg --follow as event source (keyd grabs evdev devices, /dev/kmsg select() broken)
    import threading

    def _dmesg_reader():
        """Read dmesg --follow in a thread, push events to the main loop."""
        nonlocal last_toggle_time, last_mic_toggle_time, last_airplane_toggle_time
        proc = subprocess.Popen(
            ["dmesg", "--follow"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1
        )
        print("  Monitoring dmesg --follow for WMI events", flush=True)
        grace_end = time.time() + 2  # ignore first 2 seconds (buffer replay)
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                if time.time() < grace_end:
                    continue
                try:
                    if "keyboard backlight changed" in line:
                        now = time.time()
                        gap = now - last_toggle_time
                        if gap < 0.3:  # debounce rapid-fire cluster
                            continue
                        # Suppress EC-echo events: the EC firmware fires event_72
                        # ("keyboard backlight changed") as a SIDE EFFECT of many
                        # unrelated register writes — fan manual_control, pm_profile,
                        # our own brightness writes, etc. We must not blindly cycle on it.
                        #
                        # Strategy: read the actual hw brightness NOW (before any delay).
                        # A real Fn+F8 press causes the EC to change the hw brightness
                        # register immediately. An EC echo from fan/PM writes does NOT
                        # change the hw brightness. So if hw brightness == what we expect,
                        # this is an echo — skip it.
                        try:
                            _sysfs_bri = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")
                            _hw_now = int(_sysfs_bri.read_text().strip()) if _sysfs_bri.exists() else None
                            _expected = BRIGHTNESS_LEVELS[current_index]
                            if _hw_now is not None and _hw_now == _expected:
                                # hw brightness unchanged — EC echo from fan/PM, not user Fn+F8
                                print(f"  WMI kbd event suppressed (hw={_hw_now} == expected={_expected}, EC echo)", flush=True)
                                continue
                        except Exception:
                            pass
                        # Also suppress if we recently wrote to brightness sysfs ourselves
                        if (now - _last_self_write_time) < _SELF_WRITE_SUPPRESS_SEC:
                            print(f"  WMI kbd event suppressed (EC echo, {now - _last_self_write_time:.2f}s after self-write)", flush=True)
                            continue
                        last_toggle_time = now
                        # If we're in idle-dimmed state, this is likely a spurious
                        # WMI event from gsd-power — just restore brightness, don't cycle.
                        if _idle_dimmed:
                            print("  WMI kbd event during idle-dim — restoring brightness", flush=True)
                            set_brightness(BRIGHTNESS_LEVELS[current_index])
                            continue
                        # Let GNOME/gsd-power handle the toggle first
                        time.sleep(0.15)
                        changed = _sync_brightness_from_sysfs()
                        if not changed:
                            # GNOME didn't change brightness — cycle ourselves.
                            _cycle_brightness()
                    elif "toggle airplane mode" in line or "radio off" in line or "radio on" in line:
                        print(f"  Airplane event line: {line.strip()}", flush=True)
                        now = time.time()
                        if (now - last_airplane_toggle_time) < 0.8:
                            continue
                        last_airplane_toggle_time = now
                        if "radio off" in line:
                            if not _set_airplane_mode(True):
                                print("  Warning: airplane mode set(ON) failed", flush=True)
                        elif "radio on" in line:
                            if not _set_airplane_mode(False):
                                print("  Warning: airplane mode set(OFF) failed", flush=True)
                        else:
                            if not _toggle_airplane_mode():
                                print("  Warning: airplane mode toggle failed", flush=True)
                    elif "mic mute" in line:
                        now = time.time()
                        if (now - last_mic_toggle_time) < 1.5:
                            continue
                        last_mic_toggle_time = now
                        if not _toggle_mic_mute():
                            print("  Warning: mic mute toggle failed", flush=True)
                    elif "change perf mode" in line:
                        # Poll pm_profile until the value changes from what it was
                        # before the button press (EC settles within ~400ms).
                        # This is race-free: we see the actual new value, not a guess.
                        try:
                            _PERF_NAMES = {0: "Silent", 1: "Balanced", 2: "Performance", 3: "Extreme"}
                            pm_path = Path("/sys/devices/platform/nuc_wmi/pm_profile")
                            old_pm = int(pm_path.read_text().strip())
                            new_pm = old_pm
                            deadline = time.time() + 1.0  # wait up to 1 second
                            while new_pm == old_pm and time.time() < deadline:
                                time.sleep(0.05)
                                new_pm = int(pm_path.read_text().strip())
                            profile_name = _PERF_NAMES.get(new_pm, f"Profile {new_pm}")
                            _send_osd("perf-mode", True, f"⚡ {profile_name}")
                            print(f"  Perf mode -> {profile_name} ({new_pm})", flush=True)
                        except Exception as e:
                            print(f"  Warning: could not read perf profile: {e}", flush=True)
                    elif "caps lock" in line:
                        # Small delay: WMI fires on keydown; LED state updates on keyup.
                        time.sleep(0.08)
                        # Glob for any input*::capslock — the node number varies by system.
                        # Prefer keyd's virtual keyboard (highest input number) as it
                        # always reflects the true logical state when keyd is in use.
                        caps_on = None
                        try:
                            import glob as _glob
                            led_paths = sorted(_glob.glob("/sys/class/leds/input*::capslock/brightness"))
                            if led_paths:
                                # Read the last entry (highest input number = keyd virtual kbd)
                                caps_on = Path(led_paths[-1]).read_text().strip() != "0"
                        except Exception:
                            pass
                        if caps_on is not None:
                            label = "Caps Lock On" if caps_on else "Caps Lock Off"
                            _send_osd("caps-lock", caps_on, label)
                            print(f"  {label}", flush=True)
                    elif "AC plugged/unplugged" in line:
                        # Read actual AC state from power supply sysfs
                        try:
                            import glob as _g
                            ac_on = None
                            for ac_path in _g.glob("/sys/class/power_supply/*/online"):
                                try:
                                    ac_on = Path(ac_path).read_text().strip() == "1"
                                    break
                                except Exception:
                                    pass
                            if ac_on is not None:
                                label = "AC Connected" if ac_on else "On Battery"
                                _send_osd("ac-power", ac_on, label)
                                print(f"  {label}", flush=True)
                        except Exception as e:
                            print(f"  Warning: AC state read failed: {e}", flush=True)
                    elif "fan boost state changed" in line:
                        # Fan boost OSD is now driven by /tmp/nuc_fan_boost_active
                        # written by fan_curve_daemon when temp >= 90C. Ignore EC echo.
                        print("  fan boost state changed (handled by fan_curve_daemon)", flush=True)
                    elif "increase screen brightness" in line or "decrease screen brightness" in line:
                        try:
                            bl = Path("/sys/class/backlight/intel_backlight/brightness")
                            mx = Path("/sys/class/backlight/intel_backlight/max_brightness")
                            pct = round(int(bl.read_text()) / int(mx.read_text()) * 100)
                            _send_osd("screen-brightness", pct, f"Brightness {pct}%")
                            print(f"  Screen brightness -> {pct}%", flush=True)
                        except Exception as e:
                            print(f"  Warning: screen brightness read failed: {e}", flush=True)
                    elif "toggle mute" in line or "increase volume" in line or "decrease volume" in line:
                        time.sleep(0.05)  # let GNOME update PipeWire first
                        try:
                            out = _run_as_active_user_capture(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
                            if out:
                                muted = "MUTED" in out.upper()
                                # parse "Volume: 0.37" or "Volume: 0.37 [MUTED]"
                                vol_pct = round(float(out.split()[1]) * 100)
                                if muted:
                                    _send_osd("volume", 0, f"Volume: Muted")
                                else:
                                    _send_osd("volume", min(vol_pct, 100), f"Volume {vol_pct}%")
                                print(f"  Volume -> {vol_pct}%{' [MUTED]' if muted else ''}", flush=True)
                        except Exception as e:
                            print(f"  Warning: volume read failed: {e}", flush=True)
                    elif "toggle Fn lock" in line:
                        try:
                            fn_on = Path("/sys/devices/platform/nuc_wmi/fn_lock").read_text().strip() == "1"
                            label = "Fn Lock On" if fn_on else "Fn Lock Off"
                            _send_osd("fn-lock", fn_on, label)
                            print(f"  {label}", flush=True)
                        except Exception as e:
                            print(f"  Warning: fn lock read failed: {e}", flush=True)
                    elif "super key lock state changed" in line:
                        try:
                            sk_on = Path("/sys/devices/platform/nuc_wmi/super_key_lock").read_text().strip() == "1"
                            label = "Super Key Locked" if sk_on else "Super Key Unlocked"
                            _send_osd("super-key-lock", sk_on, label)
                            print(f"  {label}", flush=True)
                        except Exception as e:
                            print(f"  Warning: super key lock read failed: {e}", flush=True)
                    elif "lightbar on" in line or "lightbar off" in line or "lightbar state changed" in line:
                        try:
                            # Suppress OSD if the app wrote to the lightbar within the last 2s
                            # (EC echoes a state-changed event on every register write)
                            _lb_ts_path = Path("/tmp/nuc_lightbar_write_ts")
                            if _lb_ts_path.exists():
                                try:
                                    _lb_age = time.time() - float(_lb_ts_path.read_text().strip())
                                    if _lb_age < 2.0:
                                        print(f"  lightbar OSD suppressed (app write {_lb_age:.2f}s ago)", flush=True)
                                        pass
                                    else:
                                        raise ValueError("outside window")
                                except ValueError:
                                    # Read lightbar state from LED brightness
                                    lb_bright = 0
                                    for p in ["/sys/class/leds/nuc_wmi:lightbar:right/brightness",
                                              "/sys/class/leds/nuc_wmi::lightbar/brightness"]:
                                        try:
                                            lb_bright = int(Path(p).read_text().strip())
                                            break
                                        except Exception:
                                            pass
                                    lb_on = lb_bright > 0
                                    label = "Lightbar On" if lb_on else "Lightbar Off"
                                    _send_osd("lightbar", lb_on, label)
                                    print(f"  {label}", flush=True)
                            else:
                                lb_bright = 0
                                for p in ["/sys/class/leds/nuc_wmi:lightbar:right/brightness",
                                          "/sys/class/leds/nuc_wmi::lightbar/brightness"]:
                                    try:
                                        lb_bright = int(Path(p).read_text().strip())
                                        break
                                    except Exception:
                                        pass
                                lb_on = lb_bright > 0
                                label = "Lightbar On" if lb_on else "Lightbar Off"
                                _send_osd("lightbar", lb_on, label)
                                print(f"  {label}", flush=True)
                        except Exception as e:
                            print(f"  Warning: lightbar state read failed: {e}", flush=True)
                except Exception as e:
                    print(f"  Event handler error: {e}", flush=True)
        except Exception as e:
            print(f"  dmesg reader error: {e}", flush=True)
        finally:
            proc.kill()

    dmesg_thread = threading.Thread(target=_dmesg_reader, daemon=True)
    dmesg_thread.start()

    _fan_boost_was_active = False
    _fan_boost_on_since = None        # time() when boost flag first appeared
    _fan_boost_osd_last = 0.0         # time() of last "fans full blast" OSD
    _FAN_BOOST_SUSTAIN_SEC = 15       # must stay active this long before OSD fires
    _FAN_BOOST_COOLDOWN_SEC = 300     # 5-minute cooldown between OSD notifications

    try:
        while True:
            time.sleep(5)

            # Periodic sync: read actual hardware brightness and update state files.
            _sync_brightness_from_sysfs()

            # Fan boost OSD: poll flag file written by fan_curve_daemon when temp >= 90C
            try:
                _fb_path = Path("/tmp/nuc_fan_boost_active")
                _fb_now = _fb_path.exists()
                now = time.time()
                if _fb_now:
                    if _fan_boost_on_since is None:
                        _fan_boost_on_since = now
                    sustained = (now - _fan_boost_on_since) >= _FAN_BOOST_SUSTAIN_SEC
                    cooldown_ok = (now - _fan_boost_osd_last) >= _FAN_BOOST_COOLDOWN_SEC
                    if sustained and cooldown_ok and not _fan_boost_was_active:
                        _fan_boost_was_active = True
                        _fan_boost_osd_last = now
                        _send_osd("fan-boost", True, "🌡 Thermal: Fans Full Blast")
                        print("  fan boost: ACTIVE (temp >= 90C sustained)", flush=True)
                else:
                    _fan_boost_on_since = None
                    if _fan_boost_was_active:
                        _fan_boost_was_active = False
                        _send_osd("fan-boost", False, "✅ Thermal: Cooling Down")
                        print("  fan boost: cleared (temp normal)", flush=True)
            except Exception as e:
                print(f"  Warning: fan boost poll failed: {e}", flush=True)


            # Check for resume from suspend
            try:
                suspend_path = Path("/sys/power/suspend_stats/success")
                if suspend_path.exists():
                    count = int(suspend_path.read_text().strip())
                else:
                    count = int(Path("/sys/power/wakeup_count").read_text().strip())
                if last_suspend_count is not None and count != last_suspend_count:
                    last_suspend_count = count
                    time.sleep(2)
                    _restore_keyboard_on_resume()
                last_suspend_count = count
            except Exception:
                pass
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
