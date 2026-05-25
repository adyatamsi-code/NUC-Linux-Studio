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
REQUEST_FILE = Path("/tmp/nuc_touchpad_request")
# Written by the sleep hook BEFORE it forces HID ON for suspend.
# While this file exists the HID poller must ignore all HID changes so it
# does not misinterpret the sleep-hook write as a user double-tap toggle.
SUSPEND_SUPPRESS_FILE = Path("/tmp/nuc_touchpad_suspend_suppress")


def _get_login_user():
    """Get the first logged-in non-root user and their UID."""
    try:
        result = subprocess.run(["who"], capture_output=True, text=True, timeout=3)
        for line in result.stdout.splitlines():
            user = line.split()[0]
            if user == "root":
                continue
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


# Global: timestamp of last daemon-initiated HID write (used by poller to ignore own writes)
_last_hid_write_time = 0.0


def _write_hid(enabled: bool):
    """Write HID feature report.
    0x03 = touchpad ON, LED OFF
    0x00 = touchpad OFF, LED ON
    """
    global _last_hid_write_time
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
            _last_hid_write_time = time.time()
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
    """Show touchpad toggle OSD via NUC OSD service."""
    import socket as _socket
    import json as _json
    label = "Touchpad Enabled" if enabled else "Touchpad Disabled"
    osd_sent = False
    try:
        msg = _json.dumps({"type": "touchpad", "value": enabled, "label": label})
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_DGRAM)
        sock.sendto(msg.encode("utf-8"), "/tmp/nuc-osd.sock")
        sock.close()
        osd_sent = True
    except Exception:
        pass
    if osd_sent:
        return
    # Fallback: notify-send (only if OSD socket unavailable)
    icon = "input-touchpad-symbolic" if enabled else "touchpad-disabled-symbolic"
    text = "Touchpad Enabled" if enabled else "Touchpad Disabled"
    user, uid = _get_login_user()
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    env["DISPLAY"] = ":0"
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    cmd = [
        "notify-send", "-i", icon,
        "-h", "string:x-canonical-private-synchronous:touchpad",
        "-h", "int:transient:1",
        "-u", "low", "-t", "2000",
        "Touchpad", text
    ]
    try:
        subprocess.Popen(
            ["runuser", "-u", user, "--"] + cmd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
    except Exception:
        pass


def _set_input_inhibit(inhibit: bool):
    """Set input inhibit flags for the UNIW0001 touchpad device."""
    import subprocess as _sp
    result = _sp.run(
        ["find", "/sys/devices", "-path", "*UNIW0001*", "-name", "inhibited"],
        capture_output=True, text=True
    )
    val = "1" if inhibit else "0"
    for p in result.stdout.strip().splitlines():
        p = p.strip()
        if p:
            try:
                Path(p).write_text(val)
                print(f"  -> inhibited={val} on {p.split('/')[-2]}", flush=True)
            except Exception as e:
                print(f"  -> inhibit failed {p}: {e}", flush=True)


EC_TOUCHPAD_SYSFS = Path("/sys/devices/platform/nuc_wmi/touchpad_enabled")


def _write_ec_touchpad(enabled: bool):
    """Write EC touchpad toggle via nuc_wmi sysfs."""
    try:
        EC_TOUCHPAD_SYSFS.write_text("1" if enabled else "0")
        print(f"  -> EC touchpad_enabled = {'1' if enabled else '0'}", flush=True)
    except Exception as e:
        print(f"  -> EC touchpad write failed: {e}", flush=True)


def _set_gnome_touchpad(enabled: bool):
    """Set GNOME touchpad send-events to match our state."""
    user, uid = _get_login_user()
    val = "enabled" if enabled else "disabled"
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    env["DISPLAY"] = ":0"
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    try:
        subprocess.run(
            ["runuser", "-u", user, "--", "gsettings", "set",
             "org.gnome.desktop.peripherals.touchpad", "send-events", val],
            env=env, capture_output=True, timeout=5
        )
        print(f"  -> GNOME send-events = {val}", flush=True)
    except Exception as e:
        print(f"  -> GNOME gsettings failed: {e}", flush=True)


def _apply_full_state(enabled: bool, write_hid: bool = True):
    """Apply touchpad state."""
    if write_hid:
        _write_hid(enabled)
    _set_gnome_touchpad(enabled)
    _write_state_files(enabled)


# Public API
def read_touchpad_led_state():
    try:
        if PERSISTENT_STATE_FILE.exists():
            return PERSISTENT_STATE_FILE.read_text().strip() == "1"
    except Exception:
        pass
    return True

def set_touchpad_led(enabled: bool):
    try:
        REQUEST_FILE.write_text("1" if enabled else "0")
    except Exception:
        _apply_full_state(enabled)
        show_touchpad_osd(enabled)
    return True


def main():
    """Touchpad daemon."""
    import sys
    LOCK_FILE = Path("/run/nuc-touchpad-daemon.lock")
    try:
        lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(lock_fd, str(os.getpid()).encode())
        os.ftruncate(lock_fd, len(str(os.getpid())))
    except (OSError, IOError):
        print("ERROR: Another instance already running.", flush=True)
        sys.exit(1)

    print("Starting Touchpad Daemon...", flush=True)

    # Discard any REQUEST_FILE written before this daemon instance started.
    # Without this, a stale request (e.g. written by the UI while the daemon
    # was stopped) would be processed immediately after startup and override
    # the saved persistent state — causing the daemon to apply the *wrong*
    # initial state (e.g. ON when saved state is OFF).
    try:
        if REQUEST_FILE.exists():
            REQUEST_FILE.unlink()
            print("  Discarded stale request file on startup.", flush=True)
    except Exception:
        pass

    # Clear inhibit and ensure EC digitizer is always ON (for double-tap)
    _set_input_inhibit(False)
    _write_ec_touchpad(True)

    devs = _find_touchpad_hidraws()
    if devs:
        print(f"Found touchpad HID devices: {', '.join(devs)}", flush=True)
    else:
        print("WARNING: No touchpad HID devices found!", flush=True)

    import threading

    # Load saved state
    current_state = True
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
    resume_suppress_until = 0.0

    def _do_toggle(source, write_hid=True):
        """Unified toggle — called from all paths. No debounce here."""
        nonlocal current_state
        with state_lock:
            current_state = not current_state
            new_state = current_state

        state_str = "ON" if new_state else "OFF"
        print(f"Touchpad {source} -> {state_str}", flush=True)
        _apply_full_state(new_state, write_hid=write_hid)
        show_touchpad_osd(new_state)

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
                    _do_toggle("Fn+F7 (dmesg)", write_hid=True)
        except Exception as e:
            print(f"  dmesg error: {e}", flush=True)
        finally:
            proc.kill()

    dmesg_thread = threading.Thread(target=_dmesg_reader, daemon=True)
    dmesg_thread.start()

    # === HID poller thread ===
    def _hid_poller():
        nonlocal resume_suppress_until
        print("  HID poller started", flush=True)
        last_hid = _read_hid()
        print(f"  HID initial value: 0x{last_hid:02x}" if last_hid is not None else "  HID initial: None", flush=True)
        while True:
            time.sleep(0.15)
            try:
                hid_val = _read_hid()
                if hid_val is None:
                    continue
                if hid_val != last_hid:
                    print(f"  [HID poller] change: 0x{last_hid if last_hid is not None else 0:02x} -> 0x{hid_val:02x}", flush=True)
                    last_hid = hid_val

                    # Ignore changes caused by the sleep hook forcing HID ON
                    # before suspend (suppress file present = we're in suspend prep)
                    if SUSPEND_SUPPRESS_FILE.exists():
                        print(f"  [HID poller] ignoring (suspend suppress)", flush=True)
                        continue

                    # Ignore changes caused by our own HID writes (within 2s)
                    if time.time() - _last_hid_write_time < 2.0:
                        print(f"  [HID poller] ignoring (own write)", flush=True)
                        continue

                    if time.time() < resume_suppress_until:
                        print(f"  [HID poller] ignoring (resume suppress)", flush=True)
                        continue

                    # Only react if HID disagrees with current state
                    # (firmware double-tap changed HID independently)
                    with state_lock:
                        cur = current_state
                    hid_means_on = (hid_val == 0x03)
                    if hid_means_on == cur:
                        print(f"  [HID poller] ignoring (already matches state)", flush=True)
                        continue

                    # This is a firmware-initiated change (double-tap)
                    _do_toggle("double-tap (HID)", write_hid=False)
                else:
                    last_hid = hid_val
            except Exception:
                pass

    hid_thread = threading.Thread(target=_hid_poller, daemon=True)
    hid_thread.start()

    # === Main loop ===
    try:
        while True:
            time.sleep(0.5)
            try:
                if REQUEST_FILE.exists():
                    try:
                        req = REQUEST_FILE.read_text().strip()
                        REQUEST_FILE.unlink()
                        requested = (req == "1")
                        print(f"UI request: touchpad {'ON' if requested else 'OFF'}", flush=True)
                        with state_lock:
                            if current_state == requested:
                                print(f"  [no-op] Already {'ON' if requested else 'OFF'}", flush=True)
                            else:
                                current_state = requested
                                print(f"Touchpad UI request -> {'ON' if requested else 'OFF'}", flush=True)
                                _apply_full_state(requested, write_hid=True)
                                show_touchpad_osd(requested)
                    except Exception as e:
                        print(f"  request file error: {e}", flush=True)
            except Exception:
                pass
            try:
                suspend_path = Path("/sys/power/suspend_stats/success")
                if suspend_path.exists():
                    count = int(suspend_path.read_text().strip())
                else:
                    count = int(Path("/sys/power/wakeup_count").read_text().strip())
                if last_suspend_count is not None and count != last_suspend_count:
                    last_suspend_count = count
                    print("Resume detected!", flush=True)
                    resume_suppress_until = time.time() + 10.0   # suppress HID noise during full recovery
                    time.sleep(3)
                    _write_ec_touchpad(True)
                    new_devs = _find_touchpad_hidraws()
                    print(f"  Post-resume hidraw devices: {new_devs}", flush=True)
                    hid_val = _read_hid()
                    print(f"  Post-resume HID value: 0x{hid_val:02x}" if hid_val is not None else "  Post-resume HID: None", flush=True)
                    with state_lock:
                        desired = current_state
                    if not desired:
                        print(f"  Restoring OFF state", flush=True)
                        time.sleep(1)
                        _apply_full_state(False)
                        # Re-arm suppress window so HID poller doesn't interpret
                        # our own OFF write as a firmware double-tap
                        resume_suppress_until = time.time() + 3.0
                    else:
                        if hid_val is not None and hid_val != 0x03:
                            _apply_full_state(True)
                        else:
                            print(f"  Touchpad ON confirmed", flush=True)
                            _set_gnome_touchpad(True)
                            _write_state_files(True)

                    print("Resume — recovery complete", flush=True)
                last_suspend_count = count
            except Exception:
                pass
    except KeyboardInterrupt:
        print("Daemon stopped.", flush=True)

if __name__ == "__main__":
    main()
