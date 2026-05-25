import os
import fcntl
import struct
import subprocess
import time
from pathlib import Path

def HIDIOCSFEATURE(length):
    return 0xc0004806 | (length << 16)

def HIDIOCGFEATURE(length):
    return 0xc0004807 | (length << 16)

def _find_touchpad_hidraws():
    hidraws = []
    base_path = Path("/sys/class/hidraw")
    if not base_path.exists():
        return hidraws
    for hidraw_dir in base_path.iterdir():
        device_path = hidraw_dir / "device"
        try:
            uevent_path = device_path / "uevent"
            if uevent_path.exists():
                content = uevent_path.read_text()
                if "UNIW0001:00" in content or "UNIW0001" in content:
                    hidraws.append(f"/dev/{hidraw_dir.name}")
        except Exception:
            continue
    return hidraws

def _get_report_id(hidraw_path):
    sysfs_name = Path(hidraw_path).name
    desc_path = Path(f"/sys/class/hidraw/{sysfs_name}/device/report_descriptor")
    if not desc_path.exists():
        return -1
    try:
        desc = desc_path.read_bytes()
    except Exception:
        return -1
    pattern = bytes([0x05, 0x0d, 0x09, 0x22, 0xa1, 0x00, 0x09, 0x57, 0x09, 0x58])
    idx = desc.find(pattern)
    if idx == -1:
        return -1
    for i in range(idx + len(pattern), len(desc) - 1):
        if desc[i] == 0x85:
            return desc[i+1]
    return -1


STATE_FILE = Path("/tmp/nuc_touchpad_state")
PERSISTENT_STATE_FILE = Path("/var/lib/nuc-linux-studio/touchpad_state")


def _get_login_user():
    """Get the first logged-in user and their UID."""
    try:
        result = subprocess.run(["who"], capture_output=True, text=True, timeout=3)
        for line in result.stdout.splitlines():
            user = line.split()[0]
            id_result = subprocess.run(["id", "-u", user], capture_output=True, text=True, timeout=3)
            uid = id_result.stdout.strip()
            return user, uid
    except Exception:
        pass
    try:
        import pwd
        for home in sorted(Path("/home").iterdir()):
            if home.is_dir() and home.name != "lost+found":
                try:
                    pw = pwd.getpwnam(home.name)
                    return pw.pw_name, str(pw.pw_uid)
                except KeyError:
                    continue
    except Exception:
        pass
    return os.environ.get("USER", "root"), str(os.getuid())


def _write_hid(enabled: bool):
    """Write HID feature report.
    0x03 = touchpad ON, LED OFF
    0x00 = touchpad OFF, LED ON
    """
    target_val = 0x03 if enabled else 0x00
    devs = _find_touchpad_hidraws()
    success = False
    for dev in devs:
        report_id = _get_report_id(dev)
        if report_id < 0:
            continue
        try:
            fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
            buf = struct.pack('2B', report_id, target_val)
            fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf)
            os.close(fd)
            print(f"  -> HID = 0x{target_val:02x} on {dev}", flush=True)
            success = True
        except Exception as e:
            print(f"  -> HID write failed on {dev}: {e}", flush=True)
            try:
                os.close(fd)
            except Exception:
                pass
    return success


def _read_hid():
    """Read HID feature report. Returns raw value (0x00 or 0x03), or None on error."""
    devs = _find_touchpad_hidraws()
    for dev in devs:
        report_id = _get_report_id(dev)
        if report_id < 0:
            continue
        try:
            fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
            buf = bytearray(2)
            buf[0] = report_id
            fcntl.ioctl(fd, HIDIOCGFEATURE(2), buf)
            os.close(fd)
            return buf[1]
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
    return None


def _write_state_files(enabled: bool):
    """Write state to temp and persistent files."""
    try:
        STATE_FILE.write_text("1" if enabled else "0")
    except Exception:
        pass
    try:
        PERSISTENT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERSISTENT_STATE_FILE.write_text("1" if enabled else "0")
    except Exception:
        pass


def show_touchpad_osd(enabled: bool):
    """Show GNOME Shell OSD."""
    icon = "input-touchpad-symbolic" if enabled else "touchpad-disabled-symbolic"
    user, uid = _get_login_user()
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    env["DISPLAY"] = ":0"
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    cmd = [
        "gdbus", "call", "--session",
        "--dest", "org.gnome.Shell",
        "--object-path", "/org/gnome/Shell",
        "--method", "org.gnome.Shell.ShowOSD",
        "{'icon': <'" + icon + "'>}"
    ]
    try:
        subprocess.Popen(
            ["runuser", "-u", user, "--"] + cmd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
    except Exception:
        pass


def _write_ec_sysfs(enabled: bool):
    """Write EC sysfs touchpad_enabled as backup — ensures digitizer state
    even if HID feature report only affects the LED.
    Writing EC sysfs does NOT trigger dmesg 'touchpad toggle pressed'
    (that only fires from i8042 keyboard Fn+F7 sequence)."""
    for base in ("/sys/devices/platform/nuc_wmi",
                 "/sys/devices/platform/qc71_laptop"):
        path = Path(base) / "touchpad_enabled"
        if path.exists():
            try:
                path.write_text("1" if enabled else "0")
                print(f"  -> EC sysfs = {'1' if enabled else '0'} ({path})", flush=True)
                return
            except Exception as e:
                print(f"  -> EC sysfs write failed ({path}): {e}", flush=True)


def _apply_full_state(enabled: bool):
    """Apply touchpad state via HID + EC sysfs.
    
    HID 0x03 = touchpad ON, LED OFF
    HID 0x00 = touchpad OFF, LED ON
    EC sysfs touchpad_enabled: 1 = ON, 0 = OFF (backup for digitizer)
    
    The firmware handles double-tap detection at hardware level
    even when HID is 0x00 (digitizer off). When user double-taps,
    firmware toggles HID value which our poller detects.
    """
    _write_hid(enabled)
    _write_ec_sysfs(enabled)
    _write_state_files(enabled)


# Public API used by other modules
def read_touchpad_led_state():
    """Read touchpad state from persistent file. Returns True=enabled, False=disabled."""
    try:
        if PERSISTENT_STATE_FILE.exists():
            return PERSISTENT_STATE_FILE.read_text().strip() == "1"
    except Exception:
        pass
    return True

def set_touchpad_led(enabled: bool):
    """Set touchpad state (public API for UI/CLI)."""
    _apply_full_state(enabled)
    show_touchpad_osd(enabled)
    return True


def main():
    """Touchpad daemon — HID-only architecture.

    LED is controlled by HID: 0x00 = LED ON + touchpad OFF, 0x03 = LED OFF + touchpad ON.
    Firmware detects double-tap at hardware level and toggles HID.
    
    Detection methods:
    - dmesg watcher: Fn+F7 via "touchpad toggle pressed"
    - HID poller: detects firmware double-tap (HID value changes)
    """
    # === Singleton lock — prevent multiple instances ===
    import sys
    LOCK_FILE = Path("/run/nuc-touchpad-daemon.lock")
    try:
        lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(lock_fd, str(os.getpid()).encode())
        os.ftruncate(lock_fd, len(str(os.getpid())))
    except (OSError, IOError):
        print("ERROR: Another instance of touchpad_daemon is already running. Exiting.", flush=True)
        sys.exit(1)

    print("Starting Touchpad Daemon (HID-only mode)...", flush=True)

    devs = _find_touchpad_hidraws()
    if devs:
        print(f"Found touchpad HID devices: {', '.join(devs)}", flush=True)
    else:
        print("WARNING: No touchpad HID devices found!", flush=True)

    import threading

    # Load saved state
    current_state = True  # default: enabled
    if PERSISTENT_STATE_FILE.exists():
        try:
            current_state = PERSISTENT_STATE_FILE.read_text().strip() == "1"
            print(f"  Saved state: {'ON' if current_state else 'OFF'}", flush=True)
        except Exception:
            pass

    # Apply initial state
    print(f"  Applying initial state: {'ON' if current_state else 'OFF'}", flush=True)
    _apply_full_state(current_state)

    # Track suspend
    last_suspend_count = None
    try:
        last_suspend_count = int(Path("/sys/power/suspend_stats/success").read_text().strip())
    except Exception:
        try:
            last_suspend_count = int(Path("/sys/power/wakeup_count").read_text().strip())
        except Exception:
            pass

    state_lock = threading.Lock()
    last_toggle_time = 0.0
    resume_suppress_until = 0.0  # suppress HID poller after resume

    def _toggle(source):
        """Toggle touchpad state. Thread-safe."""
        nonlocal current_state, last_toggle_time
        now = time.time()
        with state_lock:
            elapsed = now - last_toggle_time
            if elapsed < 0.5:
                print(f"  [debounce] Ignored {source} ({elapsed:.2f}s < 0.5s)", flush=True)
                return
            current_state = not current_state
            last_toggle_time = now
            new_state = current_state

        state_str = "ON" if new_state else "OFF"
        print(f"Touchpad {source} -> {state_str}", flush=True)
        _apply_full_state(new_state)
        show_touchpad_osd(new_state)

        with state_lock:
            last_toggle_time = time.time()

    def _set_state(enabled: bool, source: str):
        """Set touchpad to specific state (not toggle). Thread-safe."""
        nonlocal current_state, last_toggle_time
        now = time.time()
        with state_lock:
            elapsed = now - last_toggle_time
            if elapsed < 0.5:
                print(f"  [debounce] Ignored {source} ({elapsed:.2f}s < 0.5s)", flush=True)
                return
            if current_state == enabled:
                print(f"  [no-op] Already {'ON' if enabled else 'OFF'}, ignoring {source}", flush=True)
                return
            current_state = enabled
            last_toggle_time = now

        state_str = "ON" if enabled else "OFF"
        print(f"Touchpad {source} -> {state_str}", flush=True)
        _apply_full_state(enabled)
        show_touchpad_osd(enabled)

        with state_lock:
            last_toggle_time = time.time()

    # === dmesg watcher thread ===
    def _dmesg_reader():
        proc = subprocess.Popen(
            ["dmesg", "--follow"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1
        )
        print("  dmesg watcher started", flush=True)
        grace_end = time.time() + 3
        try:
            for line in proc.stdout:
                if time.time() < grace_end:
                    continue
                if "touchpad toggle pressed" in line:
                    _toggle("Fn+F7 (dmesg)")
        except Exception as e:
            print(f"  dmesg error: {e}", flush=True)
        finally:
            proc.kill()

    dmesg_thread = threading.Thread(target=_dmesg_reader, daemon=True)
    dmesg_thread.start()

    # === HID poller thread ===
    # Detects firmware double-tap: firmware toggles HID between 0x00 and 0x03
    def _hid_poller():
        nonlocal resume_suppress_until
        print("  HID poller started", flush=True)
        last_hid = _read_hid()
        print(f"  HID initial value: 0x{last_hid:02x}" if last_hid is not None else "  HID initial: None", flush=True)
        ignore_until = 0.0
        while True:
            time.sleep(0.1)  # poll 10 times/sec
            hid_val = _read_hid()
            if hid_val is None:
                continue
            now = time.time()
            if hid_val != last_hid:
                print(f"  [HID poller] change: 0x{last_hid if last_hid is not None else 0:02x} -> 0x{hid_val:02x}", flush=True)
                last_hid = hid_val
                if now < ignore_until:
                    print(f"  [HID poller] ignoring (cooldown)", flush=True)
                    continue
                if now < resume_suppress_until:
                    print(f"  [HID poller] ignoring (resume suppress)", flush=True)
                    continue
                # Firmware changed HID — this is a double-tap event
                if hid_val == 0x00:
                    ignore_until = now + 1.0
                    _set_state(False, "double-tap (HID->0x00)")
                elif hid_val == 0x03:
                    ignore_until = now + 1.0
                    _set_state(True, "double-tap (HID->0x03)")
            else:
                last_hid = hid_val

    hid_thread = threading.Thread(target=_hid_poller, daemon=True)
    hid_thread.start()

    # === Main loop (suspend + screen-dim detection) ===
    # Track keyboard brightness to detect screen dim/undim events
    _kbd_brightness_path = None
    for _p in [Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness"),
               Path("/sys/class/leds/nuc_wmi::kbd_backlight/brightness")]:
        if _p.exists():
            _kbd_brightness_path = _p
            break
    _last_kbd_brightness = None
    if _kbd_brightness_path:
        try:
            _last_kbd_brightness = int(_kbd_brightness_path.read_text().strip())
        except Exception:
            pass

    try:
        while True:
            time.sleep(5)
            try:
                suspend_path = Path("/sys/power/suspend_stats/success")
                if suspend_path.exists():
                    count = int(suspend_path.read_text().strip())
                else:
                    count = int(Path("/sys/power/wakeup_count").read_text().strip())
                if last_suspend_count is not None and count != last_suspend_count:
                    last_suspend_count = count
                    print("Resume detected — suppressing HID poller for 10s...", flush=True)
                    resume_suppress_until = time.time() + 10.0

                    # Rebind i2c-hid driver to reset touchpad hardware state
                    print("Resume — rebinding i2c_hid_acpi driver...", flush=True)
                    unbind = Path("/sys/bus/i2c/drivers/i2c_hid_acpi/unbind")
                    bind = Path("/sys/bus/i2c/drivers/i2c_hid_acpi/bind")
                    tp_id = "i2c-UNIW0001:00"
                    try:
                        unbind.write_text(tp_id)
                        time.sleep(2)
                        bind.write_text(tp_id)
                        time.sleep(3)
                        print("Resume — i2c-hid rebound successfully", flush=True)
                    except Exception as e:
                        print(f"Resume — rebind failed: {e}", flush=True)

                    # Force re-apply saved state
                    with state_lock:
                        state = current_state
                    print(f"Resume — re-applying state: {'ON' if state else 'OFF'}", flush=True)
                    _apply_full_state(state)
                    # Verify
                    time.sleep(0.5)
                    hid_val = _read_hid()
                    expected = 0x03 if state else 0x00
                    if hid_val is not None and hid_val != expected:
                        print(f"Resume — HID mismatch (0x{hid_val:02x} != 0x{expected:02x}), retrying...", flush=True)
                        _apply_full_state(state)
                    print("Resume — recovery complete", flush=True)
                last_suspend_count = count

                # Screen dim/undim detection:
                # When GNOME dims the screen, keyboard brightness goes to 0.
                # This can cause i2c bus power state changes that reset the
                # touchpad HID feature report. Re-apply state on undim.
                if _kbd_brightness_path:
                    try:
                        kbd_br = int(_kbd_brightness_path.read_text().strip())
                        if _last_kbd_brightness is not None:
                            if _last_kbd_brightness == 0 and kbd_br > 0:
                                # Screen un-dimmed — re-apply touchpad state
                                with state_lock:
                                    state = current_state
                                print(f"Screen undim detected — re-applying touchpad: {'ON' if state else 'OFF'}", flush=True)
                                _apply_full_state(state)
                        _last_kbd_brightness = kbd_br
                    except Exception:
                        pass

            except Exception:
                pass
    except KeyboardInterrupt:
        print("Daemon stopped.", flush=True)

if __name__ == "__main__":
    main()
