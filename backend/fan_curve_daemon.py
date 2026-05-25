#!/usr/bin/env python3
import json
import time
import subprocess
from pathlib import Path

STATE_PATHS = [
    Path("/var/lib/nuc-linux-studio/fan_curve_state.json"),
    Path("/tmp/nuc_fan_curve_state.json"),
]
TEMPS_C = [35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]
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


def _reapply_battery_limit() -> None:
    """Re-write the saved charge limit back to sysfs.

    Called after restarting upower (which clears charge_control_end_threshold to 100)
    and after resume from suspend.

    IMPORTANT: Only overwrites sysfs if the current value is the kernel default (100).
    This prevents a stale config value from overwriting a valid in-session limit
    that was set after the config was last saved (timing race between daemon and app).
    """
    import json as _json

    # Read current sysfs value first — if it's NOT the kernel default (100),
    # assume the app or a previous daemon write already set it correctly.
    base = Path("/sys/class/power_supply")
    current_sysfs = None
    if base.exists():
        for entry in base.iterdir():
            t_path = entry / "charge_control_end_threshold"
            if t_path.exists():
                try:
                    current_sysfs = int(t_path.read_text().strip())
                    break
                except Exception:
                    pass

    if current_sysfs is not None and current_sysfs != 100:
        print(f"  Battery limit sysfs={current_sysfs}% (not default) — skipping re-apply", flush=True)
        return

    # sysfs is at kernel default (100) — read saved config and apply it
    config_paths = [Path("/root/.config/nuc_linux_studio/settings.json")]
    for user_dir in Path("/home").iterdir():
        config_paths.append(user_dir / ".config" / "nuc_linux_studio" / "settings.json")

    # Check user home dirs first (app saves there); root config last (may be stale)
    ordered = [p for p in config_paths if not str(p).startswith("/root")] + \
              [p for p in config_paths if str(p).startswith("/root")]

    limit = None
    limit_source = None
    for cfg in ordered:
        if cfg.exists():
            try:
                data = _json.loads(cfg.read_text())
                if "charge_limit" in data:
                    limit = int(data["charge_limit"])
                    limit_source = str(cfg)
                    break
            except Exception:
                pass

    if limit is None:
        return  # No saved limit — don't overwrite whatever the kernel has

    print(f"  Battery limit from config ({limit_source}): {limit}%", flush=True)

    # Write to sysfs
    if base.exists():
        for entry in base.iterdir():
            t_path = entry / "charge_control_end_threshold"
            if t_path.exists():
                try:
                    t_path.write_text(str(limit))
                    print(f"  Battery limit re-applied: {t_path} = {limit}%", flush=True)
                except Exception as e:
                    print(f"  Battery limit write failed {t_path}: {e}", flush=True)
    for driver in ["nuc_wmi", "qc71_laptop"]:
        cp = Path(f"/sys/devices/platform/{driver}/charging_profile")
        if cp.exists():
            try:
                if limit <= 60:   val = "stationary"
                elif limit <= 80: val = "balanced"
                else:             val = "high_capacity"
                cp.write_text(val)
                print(f"  Battery profile re-applied: {cp} = {val}", flush=True)
            except Exception as e:
                print(f"  Battery profile write failed {cp}: {e}", flush=True)


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
    manual_grace_until = 0.0
    _boost_active = False          # True while any temp >= 90C
    _boost_release_step = 0        # 0=not releasing, 1=mid-ramp, 2=done
    _boost_release_cpu_start = 255
    _boost_release_dgpu_start = 255
    _FAN_BOOST_FLAG = Path("/tmp/nuc_fan_boost_active")
    # On boot, give the EC 8 seconds to finish its own initialization before
    # we take manual control. The EC clears manual mode during boot/profile init
    # which was causing the "manual mode cleared externally" loop at startup.
    _startup_delay_until = time.time() + 8.0
    print("  Waiting 8s for EC to initialize before taking manual control...", flush=True)
    _upower_check_counter = 0

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
            # During startup delay, just reload state but don't touch hardware
            if time.time() < _startup_delay_until:
                for candidate in STATE_PATHS:
                    if candidate.exists():
                        state = _read_state()
                        break
                time.sleep(POLL_SECS)
                continue

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
                    # Restart upower on resume — clears stale sysfs fds that cause CPU hog.
                    # Re-apply battery limit immediately after in case upower wrote over it.
                    try:
                        subprocess.run(["systemctl", "restart", "upower.service"],
                                       timeout=10, capture_output=True)
                        print("  upower restarted after resume", flush=True)
                    except Exception as e:
                        print(f"  upower restart failed: {e}", flush=True)
                    _reapply_battery_limit()
                    # Force fan curve re-apply on next tick
                    last_cpu_pwm = None
                    last_dgpu_pwm = None
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
            cpu_curve = curve.get("cpu", [0, 0, 5, 10, 20, 35, 50, 65, 78, 88, 95, 100])
            dgpu_curve = curve.get("dgpu", [0, 0, 5, 10, 20, 35, 50, 65, 78, 88, 95, 100])

            cpu_temp_c = _read_int(sensor / "temp1_input", 50000) / 1000.0
            dgpu_temp_c = _read_int(sensor / "temp2_input", 50000) / 1000.0

            # Hard override: at or above 90°C go full blast regardless of curve
            if cpu_temp_c >= 90.0:
                cpu_pct = 100
            else:
                cpu_pct = _interp_pct(cpu_curve, cpu_temp_c)
            if dgpu_temp_c >= 90.0:
                dgpu_pct = 100
            else:
                dgpu_pct = _interp_pct(dgpu_curve, dgpu_temp_c)

            # Clamp PWM: floor ~600rpm (26/255), ceiling 5900rpm (255/255)
            cpu_pwm = max(26, min(255, _pct_to_pwm(cpu_pct)))
            dgpu_pwm = max(26, min(255, _pct_to_pwm(dgpu_pct)))

            # Fan boost flag + ramp-down logic
            _both_above_90 = cpu_temp_c >= 90.0 or dgpu_temp_c >= 90.0
            _both_below_85 = cpu_temp_c < 85.0 and dgpu_temp_c < 85.0

            if _both_above_90 and not _boost_active:
                # Entering boost: write flag file for OSD
                _boost_active = True
                _boost_release_step = 0
                try:
                    _FAN_BOOST_FLAG.write_text("1")
                except Exception:
                    pass
                print(f"  [boost] ACTIVE cpu={cpu_temp_c:.1f}C gpu={dgpu_temp_c:.1f}C", flush=True)

            elif _boost_active and _both_below_85:
                # Leaving boost: ramp down over 2 poll cycles (~6s)
                if _boost_release_step == 0:
                    # First poll after temps drop — record starting PWM for ramp
                    _boost_release_cpu_start = last_cpu_pwm if last_cpu_pwm is not None else 255
                    _boost_release_dgpu_start = last_dgpu_pwm if last_dgpu_pwm is not None else 255
                    _boost_release_step = 1
                    # Mid-ramp: halfway between full blast and curve target
                    cpu_pwm = max(26, min(255, (_boost_release_cpu_start + cpu_pwm) // 2))
                    dgpu_pwm = max(26, min(255, (_boost_release_dgpu_start + dgpu_pwm) // 2))
                    print(f"  [boost] ramp step 1: cpu_pwm={cpu_pwm} dgpu_pwm={dgpu_pwm}", flush=True)
                elif _boost_release_step == 1:
                    # Final step: use curve target — boost fully released
                    _boost_release_step = 2
                    _boost_active = False
                    try:
                        _FAN_BOOST_FLAG.unlink(missing_ok=True)
                    except Exception:
                        pass
                    print(f"  [boost] ramp step 2 (done): cpu_pwm={cpu_pwm} dgpu_pwm={dgpu_pwm}", flush=True)

            # Check if manual mode was cleared externally (e.g. by driver
            # during profile switch). If so, wait 5s before re-enabling
            # so the EC can process the profile change and update LEDs.
            in_grace = False
            if manual.exists():
                cur_manual = _read_int(manual, 0)
                if cur_manual != 1:
                    if manual_grace_until == 0.0:
                        manual_grace_until = time.time() + 5.0
                        print("  manual mode cleared externally, grace period 5s", flush=True)
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
                        # Re-apply battery limit — upower restart doesn't touch sysfs but
                        # be safe: ensure the saved limit is still in effect.
                        _reapply_battery_limit()
                        break
            except Exception:
                pass

        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()



