import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager
import threading

class BackendError(RuntimeError):
    pass

# Track whether we've already elevated permissions this session
_elevated = False

def elevate_sysfs_permissions() -> None:
    """
    Run a single pkexec/sudo call at startup to make all relevant sysfs files
    writable for the current user, so no further password prompts are needed.
    """
    global _elevated
    if _elevated:
        return

    import glob as _glob
    paths_to_chmod = []

    # Collect hwmon writable paths (pwm, brightness, etc.)
    for pattern in [
        "/sys/devices/platform/nuc_wmi/hwmon/hwmon*/pwm*",
        "/sys/devices/platform/qc71_laptop/hwmon/hwmon*/pwm*",
        "/sys/devices/platform/nuc_wmi/manual_control",
        "/sys/devices/platform/qc71_laptop/manual_control",
        "/sys/devices/platform/nuc_wmi/hwmon/hwmon*/pwm*_enable",
        "/sys/devices/platform/qc71_laptop/hwmon/hwmon*/pwm*_enable",
        "/sys/class/hwmon/hwmon*/pwm*",
        "/sys/class/leds/ite8291*/*",
        "/sys/class/leds/*::kbd_backlight/*",
        "/sys/class/leds/uniwill:multicolor:status/*",
        "/sys/class/leds/uniwill:multicolor:status_1/*",
        "/sys/class/leds/rgb:lightbar/*",
        "/sys/class/leds/tuxedo:rgb:lightbar/*",
        "/sys/class/leds/rgb:status/*",
        "/sys/class/leds/tuxedo:rgb:status/*",
        "/sys/devices/platform/INOU0000:00/leds/*/*",
        "/sys/devices/platform/INOU0000:00/*",
        "/sys/devices/platform/nuc_wmi/*",
        "/sys/devices/platform/qc71_laptop/*",
    ]:
        paths_to_chmod.extend(_glob.glob(pattern))

    # Battery charge control
    for bat_path in Path("/sys/class/power_supply").glob("BAT*"):
        for ctrl in ["charge_control_end_threshold", "charge_control_start_threshold"]:
            p = bat_path / ctrl
            if p.exists():
                paths_to_chmod.append(str(p))

    # Touchpad hidraw devices (for LED control)
    hidraw_devs = []
    hidraw_base = Path("/sys/class/hidraw")
    if hidraw_base.exists():
        for hidraw_dir in hidraw_base.iterdir():
            uevent_path = hidraw_dir / "device" / "uevent"
            try:
                if uevent_path.exists() and "UNIW0001" in uevent_path.read_text():
                    dev_path = f"/dev/{hidraw_dir.name}"
                    if Path(dev_path).exists():
                        hidraw_devs.append(dev_path)
            except Exception:
                pass

    # Filter to only existing files that are not already writable
    final_paths = []
    for p in paths_to_chmod:
        pp = Path(p)
        if pp.exists() and pp.is_file() and not os.access(pp, os.W_OK):
            final_paths.append(str(pp))

    # Add hidraw devices that aren't writable
    for dev in hidraw_devs:
        if not os.access(dev, os.W_OK):
            final_paths.append(dev)

    # Add input event devices that aren't readable (for touchpad daemon evdev)
    input_base = Path("/dev/input")
    if input_base.exists():
        for ev in input_base.glob("event*"):
            if not os.access(ev, os.R_OK):
                final_paths.append(str(ev))

    if not final_paths:
        _elevated = True
        return

    cmd = "pkexec" if shutil.which("pkexec") else "sudo"
    # chmod 666 all paths in a single elevated call
    script = " ; ".join(f"chmod 666 '{p}'" for p in final_paths)
    try:
        res = subprocess.run([cmd, "sh", "-c", script], capture_output=True, text=True)
        if res.returncode == 0:
            _elevated = True
        else:
            # Non-fatal: fall back to per-write elevation
            print(f"Warning: Initial permission elevation failed: {res.stderr.strip()}")
            _elevated = True  # Don't ask again even if it failed
    except Exception as e:
        print(f"Warning: Could not elevate permissions: {e}")
        _elevated = True


# Thread-local storage for write batching
_batch_local = threading.local()

@contextmanager
def batch_writes():
    """Context manager to batch multiple write_text calls into a single elevated command."""
    _batch_local.pending = {}
    try:
        yield
    finally:
        pending = _batch_local.pending
        _batch_local.pending = None
        if pending:
            _flush_writes(pending)

def _flush_writes(writes: Dict[Path, str]) -> None:
    """Actually perform the writes (direct or elevated)."""
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
            raise BackendError(f"Failed writing to sysfs ({p} = '{v}'): {e}")

    # Use a helper script to write all values in one elevated call
    cmd = "pkexec" if shutil.which("pkexec") else "sudo"
    # Build a safe script using printf and tee (no shell interpolation of values)
    script_lines = []
    for p, v in writes.items():
        if p.exists():
            # Use printf with %s to avoid interpretation of special chars
            safe_val = v.replace("'", "'\\''")
            safe_path = str(p).replace("'", "'\\''")
            script_lines.append(f"printf '%s' '{safe_val}' > '{safe_path}'")
    if not script_lines:
        return

    script = " ; ".join(script_lines)
    try:
        res = subprocess.run([cmd, "sh", "-c", script], capture_output=True, text=True)
        if res.stderr and "Permission denied" in res.stderr:
            raise BackendError(f"Kernel rejected write (Permission Denied). Driver mode locked or unsupported. ({res.stderr.strip()})")
        if res.returncode != 0:
            raise BackendError(f"Elevation ({cmd}) failed (code {res.returncode}): {res.stderr.strip()}")
    except subprocess.CalledProcessError as exc:
        raise BackendError(f"Command failed: {exc}")

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()

def write_multiple(writes: Dict[Path, str]) -> None:
    # If we're inside a batch_writes() context, accumulate instead of flushing
    pending = getattr(_batch_local, 'pending', None)
    if pending is not None:
        pending.update(writes)
        return
    _flush_writes(writes)

def write_text(path: Path, value: str) -> None:
    write_multiple({path: value})

def check_acpi_presence() -> bool:
    acpi_dir = Path("/sys/bus/acpi/devices")
    return any(entry.name.startswith("INOU0000") for entry in acpi_dir.iterdir()) if acpi_dir.exists() else False


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def nuc_wmi_source_dir() -> Optional[Path]:
    source_dir = get_repo_root() / "driver"
    return source_dir if source_dir.exists() and (source_dir / "Makefile").exists() else None


def is_qc71_driver_loaded() -> bool:
    return Path("/sys/devices/platform/nuc_wmi").exists() or Path("/sys/devices/platform/qc71_laptop").exists()

def is_tuxedo_driver_loaded() -> bool:
    return Path("/sys/bus/platform/drivers/tuxedo_keyboard").exists() or Path("/sys/module/tuxedo_keyboard").exists()


def is_qc71_source_available() -> bool:
    return nuc_wmi_source_dir() is not None


def _find_qc71_hwmon() -> Optional[Path]:
    platform_base = Path("/sys/devices/platform")
    if not platform_base.exists():
        return None
    for device in sorted(platform_base.glob("*nuc_wmi*")) + sorted(platform_base.glob("*qc71*")):
        hwmon_dir = device / "hwmon"
        if not hwmon_dir.exists():
            continue
        for entry in sorted(hwmon_dir.iterdir()):
            if entry.is_dir():
                return entry
    return None


def find_uniwill_hwmon() -> Optional[Path]:
    # Always prioritize the custom nuc_wmi driver over the generic uniwill one!
    qc71_hwmon = _find_qc71_hwmon()
    if qc71_hwmon is not None:
        return qc71_hwmon

    base = Path("/sys/class/hwmon")
    if base.exists():
        for entry in base.iterdir():
            if (entry / "name").exists():
                name_text = read_text(entry / "name")
                if name_text and ("uniwill" in name_text.lower() or "tuxedo" in name_text.lower()):
                    return entry

    # Return None to signal that hwmon is not available; callers must handle this.
    return None


def get_elevation_command() -> Optional[List[str]]:
    if shutil.which("pkexec"):
        return ["pkexec"]
    if shutil.which("sudo"):
        return ["sudo"]
    return None


def install_qc71_driver() -> str:
    source_dir = nuc_wmi_source_dir()
    if not source_dir:
        raise BackendError("nuc_wmi source directory is not available in the application repository.")
    if not shutil.which("make"):
        raise BackendError("Cannot install nuc_wmi because 'make' is not installed.")

    elevation = get_elevation_command()
    if not elevation:
        raise BackendError("Cannot install nuc_wmi because no elevated privilege helper (pkexec or sudo) is available.")

    install_target = "dkmsinstall" if shutil.which("dkms") else "install"
    install_cmd = elevation + ["make", install_target]
    res = subprocess.run(install_cmd, cwd=source_dir, capture_output=True, text=True)
    if res.returncode != 0:
        raise BackendError(
            f"nuc_wmi install failed with exit code {res.returncode}: {res.stderr.strip() or res.stdout.strip()}"
        )

    load_cmd = elevation + ["modprobe", "nuc_wmi"]
    res = subprocess.run(load_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise BackendError(
            f"nuc_wmi was installed but failed to load: {res.stderr.strip() or res.stdout.strip()}"
        )

    return f"nuc_wmi driver installed and loaded via {install_target}."
