#!/usr/bin/env python3
import json
import time
import subprocess
from pathlib import Path

STATE_PATHS = [
    Path("/var/lib/nuc-linux-studio/fan_curve_state.json"),
    Path("/tmp/nuc_fan_curve_state.json"),
]
TEMPS_C = [40, 50, 60, 70, 80, 90]
POLL_SECS = 3.0


def _find_ctrl_hwmon() -> Path | None:
    base = Path("/sys/devices/platform/nuc_wmi/hwmon")
    if not base.exists():
        base = Path("/sys/devices/platform/qc71_laptop/hwmon")
    if not base.exists():
        return None
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.name.startswith("hwmon") and (entry / "pwm1").exists():
            return entry
    return None


def _find_sensor_hwmon() -> Path | None:
    base = Path("/sys/devices/platform/nuc_wmi/hwmon")
    if not base.exists():
        base = Path("/sys/devices/platform/qc71_laptop/hwmon")
    if not base.exists():
        return None
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.name.startswith("hwmon") and (entry / "temp1_input").exists():
            return entry
    return None


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return default


def _read_state() -> dict | None:
    for path in STATE_PATHS:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _read_profile() -> int:
    for path in [
        Path("/sys/devices/platform/nuc_wmi/pm_profile"),
        Path("/sys/devices/platform/qc71_laptop/pm_profile"),
    ]:
        if path.exists():
            return _read_int(path, 1)
    return 1


def _pct_to_pwm(pct: int) -> int:
    pct = max(0, min(100, int(pct)))
    return int(round(pct * 255 / 100))


def _interp_pct(curve: list[int], temp_c: float) -> int:
    if len(curve) != len(TEMPS_C):
        return 30
    if temp_c <= TEMPS_C[0]:
        return int(curve[0])
    if temp_c >= TEMPS_C[-1]:
        return int(curve[-1])
    for i in range(len(TEMPS_C) - 1):
        t0, t1 = TEMPS_C[i], TEMPS_C[i + 1]
        if t0 <= temp_c <= t1:
            v0 = int(curve[i])
            v1 = int(curve[i + 1])
            ratio = (temp_c - t0) / (t1 - t0)
            return int(round(v0 + ratio * (v1 - v0)))
    return int(curve[-1])


def _write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def main() -> None:
    # === Singleton lock ===
    import fcntl as _fcntl, os as _os, sys as _sys
    _lock_path = "/run/nuc-fan-curve-daemon.lock"
    try:
        _lock_fd = open(_lock_path, 'w')
        _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        _lock_fd.write(str(_os.getpid()))
        _lock_fd.flush()
    except (OSError, IOError):
        print("ERROR: Another instance of fan_curve_daemon is already running. Exiting.", flush=True)
        _sys.exit(1)

    print("fan-curve daemon started", flush=True)

    ctrl = _find_ctrl_hwmon()
    sensor = _find_sensor_hwmon()
    if not ctrl or not sensor:
        print("  fan hwmon paths not found, waiting...", flush=True)
        for _ in range(30):  # retry for 30s on boot
            time.sleep(1)
            ctrl = _find_ctrl_hwmon()
            sensor = _find_sensor_hwmon()
            if ctrl and sensor:
                break
        if not ctrl or not sensor:
            print("  fan hwmon paths still not found; sleeping forever", flush=True)
            while True:
                time.sleep(10)

    print(f"  ctrl hwmon: {ctrl}", flush=True)
    print(f"  sensor hwmon: {sensor}", flush=True)

    manual = Path("/sys/devices/platform/nuc_wmi/manual_control")
    if not manual.exists():
        manual = Path("/sys/devices/platform/qc71_laptop/manual_control")

    last_mtime = 0.0
    last_state_path = None
    state = None
    last_cpu_pwm = None
    last_dgpu_pwm = None
    last_profile = None
    manual_grace_until = 0.0  # Don't re-enable manual mode until this time
    _upower_check_counter = 0  # check upowerd every ~60s (20 ticks at 3s)

    # Track suspend/resume
    last_suspend_count = None
    try:
        last_suspend_count = int(Path("/sys/power/suspend_stats/success").read_text().strip())
    except Exception:
        try:
            last_suspend_count = int(Path("/sys/power/wakeup_count").read_text().strip())
        except Exception:
            pass

    while True:
        try:
            # Check for resume from suspend — re-discover hwmon paths
            try:
                suspend_path = Path("/sys/power/suspend_stats/success")
                if suspend_path.exists():
                    count = int(suspend_path.read_text().strip())
                else:
                    count = int(Path("/sys/power/wakeup_count").read_text().strip())
                if last_suspend_count is not None and count != last_suspend_count:
                    last_suspend_count = count
                    print("  Resume detected — re-discovering hwmon paths...", flush=True)
                    time.sleep(2)  # wait for sysfs to stabilize
                    new_ctrl = _find_ctrl_hwmon()
                    new_sensor = _find_sensor_hwmon()
                    if new_ctrl and new_sensor:
                        ctrl = new_ctrl
                        sensor = new_sensor
                        print(f"  Resumed: ctrl={ctrl} sensor={sensor}", flush=True)
                    else:
                        # Retry a few times
                        for _ in range(5):
                            time.sleep(1)
                            new_ctrl = _find_ctrl_hwmon()
                            new_sensor = _find_sensor_hwmon()
                            if new_ctrl and new_sensor:
                                ctrl = new_ctrl
                                sensor = new_sensor
                                print(f"  Resumed (retry): ctrl={ctrl} sensor={sensor}", flush=True)
                                break
                    # Force re-apply on next tick
                    last_cpu_pwm = None
                    last_dgpu_pwm = None
                last_suspend_count = count
            except Exception:
                pass

            pwm1 = ctrl / "pwm1"
            pwm2 = ctrl / "pwm2"
            pwm1_enable = ctrl / "pwm1_enable"
            pwm2_enable = ctrl / "pwm2_enable"

            # Reload state file only when it changes.
            for candidate in STATE_PATHS:
                if candidate.exists():
                    mtime = candidate.stat().st_mtime
                    if mtime != last_mtime or last_state_path != candidate:
                        state = _read_state()
                        last_mtime = mtime
                        last_state_path = candidate
                        print("  fan state reloaded", flush=True)
                    break

            if not state or not state.get("enabled", True):
                # Release fan control to EC
                if manual.exists() and _read_int(manual, 0) != 0:
                    _write(manual, "0")
                    print("  fan override disabled; EC control restored", flush=True)
                # Also reset PWM channels to auto mode
                if pwm1_enable.exists() and _read_int(pwm1_enable, 1) != 0:
                    _write(pwm1_enable, "0")
                if pwm2_enable.exists() and _read_int(pwm2_enable, 1) != 0:
                    _write(pwm2_enable, "0")
                last_cpu_pwm = None
                last_dgpu_pwm = None
                time.sleep(POLL_SECS)
                continue

            profile = _read_profile()
            if state.get("benchmark", False):
                profile = 3
            profile_curves = state.get("profile_curves", {})
            profile_key = str(profile)
            if profile_key not in profile_curves:
                profile_key = "1"

            curve = profile_curves.get(profile_key, {})
            cpu_curve = curve.get("cpu", [26, 30, 42, 58, 80, 100])
            dgpu_curve = curve.get("dgpu", [26, 30, 42, 58, 88, 100])

            cpu_temp_c = _read_int(sensor / "temp1_input", 50000) / 1000.0
            dgpu_temp_c = _read_int(sensor / "temp2_input", 50000) / 1000.0
            cpu_pct = _interp_pct(cpu_curve, cpu_temp_c)
            dgpu_pct = _interp_pct(dgpu_curve, dgpu_temp_c)

            cpu_pwm = _pct_to_pwm(cpu_pct)
            dgpu_pwm = _pct_to_pwm(dgpu_pct)

            # Check if manual mode was cleared externally (e.g. by driver
            # during profile switch). If so, wait 2s before re-enabling
            # so the EC can process the profile change and update LEDs.
            in_grace = False
            if manual.exists():
                cur_manual = _read_int(manual, 0)
                if cur_manual != 1:
                    if manual_grace_until == 0.0:
                        manual_grace_until = time.time() + 2.0
                        print("  manual mode cleared externally, grace period 2s", flush=True)
                    if time.time() < manual_grace_until:
                        in_grace = True
                    else:
                        manual_grace_until = 0.0
                else:
                    manual_grace_until = 0.0

            if not in_grace:
                # Put PWM channels in manual mode only when override is active.
                if pwm1_enable.exists():
                    _write(pwm1_enable, "1")
                if pwm2_enable.exists():
                    _write(pwm2_enable, "1")
                if manual.exists() and _read_int(manual, 0) != 1:
                    _write(manual, "1")

            if cpu_pwm != last_cpu_pwm and pwm1.exists():
                _write(pwm1, str(cpu_pwm))
                last_cpu_pwm = cpu_pwm
            if dgpu_pwm != last_dgpu_pwm and pwm2.exists():
                _write(pwm2, str(dgpu_pwm))
                last_dgpu_pwm = dgpu_pwm

            if profile != last_profile:
                print(f"  profile {profile} -> CPU {cpu_pct}% dGPU {dgpu_pct}%", flush=True)
                last_profile = profile

        except Exception as exc:
            print(f"  fan daemon warning: {exc}", flush=True)
            # If writes fail, hwmon paths may be stale — try re-discovery
            new_ctrl = _find_ctrl_hwmon()
            new_sensor = _find_sensor_hwmon()
            if new_ctrl and new_sensor and (new_ctrl != ctrl or new_sensor != sensor):
                ctrl = new_ctrl
                sensor = new_sensor
                last_cpu_pwm = None
                last_dgpu_pwm = None
                print(f"  Re-discovered hwmon: ctrl={ctrl} sensor={sensor}", flush=True)

        # upowerd CPU hog watchdog — check every ~60s
        _upower_check_counter += 1
        if _upower_check_counter >= 20:
            _upower_check_counter = 0
            try:
                result = subprocess.run(
                    ["ps", "-C", "upowerd", "-o", "pcpu="],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().splitlines():
                    cpu_pct = float(line.strip())
                    if cpu_pct > 10.0:
                        print(f"  upowerd at {cpu_pct}% CPU — restarting upower.service", flush=True)
                        subprocess.run(
                            ["systemctl", "restart", "upower.service"],
                            timeout=10, capture_output=True
                        )
                        break
            except Exception:
                pass

        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()



