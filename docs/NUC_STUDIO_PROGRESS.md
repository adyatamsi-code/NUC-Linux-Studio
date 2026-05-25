# Intel NUC Software Studio Replica - Progress Tracker

This document tracks progress in replicating the official Intel NUC Software Studio (for the NUC X15 Laptop Kit) under Linux using the `nuc_wmi` driver + `nuc-linux-studio` application.

> **RULE:** This file MUST be updated whenever a feature is completed, a bug is fixed, or a UI improvement is made.

## 1. Performance Tuning (Power Profiles)
- [x] **Balanced Mode** (via ACPI WMBC/WMAX fallback)
- [x] **Silent/Power Saver Mode**
- [x] **Performance Mode**
- [x] **Benchmark Mode** (100% fans, app-enforced)
- [x] **Live System Monitor** (CPU/GPU temps, RPMs, PWM percentages — color-coded, brand logos)
- [x] **Profile Selection from App** (UI combobox → EC via WMBC)
- [x] **Hardware Profile Button Sync** (CTRL_3 register read — reliable, no double-cycling)

## 2. Fan Control
- [x] **Automatic Fan Control** (EC-managed)
- [x] **Manual Fan Sliders** (CPU & dGPU PWM via hwmon)
- [x] **Custom Fan Curves** (per-profile, per-temperature threshold)
- [x] **Fan Curve Editor** (UI sliders with monotonic enforcement, live visualization canvas, safety guardrails)
- [x] **Fan Curve Daemon** (`fan-curve.service` — persists after app close, handles suspend/resume, writes only on value change)

## 3. Battery Health Management
- [x] **Charge Limits** (60% / 80% / 100% via `charge_control_end_threshold`)
- [x] **Battery Info Display** (segmented gauge with charge/limit indicators)
- [x] **Boot-time limit reapply** (`nuc-battery-limit.service` oneshot — writes threshold on every boot)
- [x] **upower-restart protection** (`_reapply_battery_limit()` in fan-curve daemon — re-writes threshold after upower restart AND after suspend/resume)

## 4. Keyboard Backlight (ITE8291R3)
- [x] **Static / Monocolor** (via kernel driver sysfs + USB library fallback)
- [x] **Brightness Control** (Fn+F8 via GNOME gsd-power, daemon observes + syncs)
- [x] **Per-Key RGB** (full 101-key, 6×21 grid, direct USB row data)
- [x] **Per-Key Brightness** (confirmed: scaling RGB intensity per key produces visible brightness differences; no separate HW channel needed)
- [x] **Per-Key Brightness UI** (brightness slider visible in per-key mode; adjusts brightness of selected keys; slider label changes to "Key Brightness:" in per-key mode vs "Brightness:" in glow mode)
- [x] **Breathing Effect** (color + speed, saved per-effect)
- [x] **Wave Effect** (direction: right/left/up/down, speed)
- [x] **Rainbow Effect** (static rainbow, no parameters)
- [x] **Ripple Effect** (color, speed, reactive to keypresses ✅)
- [x] **Aurora Effect** (color, speed, reactive ✅)
- [x] **Fireworks Effect** (color, speed, reactive ✅)
- [x] **Raindrop Effect** (color, speed)
- [x] **Marquee Effect** (multi-color, speed)
- [x] **Random Effect** (color, speed, reactive)
- [x] **Audio Visualizer** (software FFT mode — works with all audio outputs via PipeWire/PulseAudio capture; persists via `kbd-audio.service` daemon after app close)
- [x] **Color Palette** (7-slot firmware palette: white/orange/yellow/green/blue/purple/pink + random)
- [x] **Reactive Mode** (hardware-driven keypress reactivity for ripple/aurora/fireworks/random)
- [x] **Audio Mode / CMD 0x02** (row scanner mode=3, reactive enhancement mode=1, BPM pulse mode=4)
- [x] **Per-Effect Settings Memory** (color, speed, direction saved individually per effect)
- [x] **Separate Per-Key / Mono Color Storage** (switching modes preserves colors)
- [x] **Speed Control** (0-9 slider per effect, sysfs passthrough)
- [x] **Direction Control** (wave: right/left/up/down; audio: up/down via sysfs)
- [x] **Daemon Resume Restore** (restores effect + per-key colors + brightness after suspend/resume/reboot)
- [x] **Gaming Preset** (red monocolor)
- [x] **Coding Preset** (green monocolor)
- [x] **Direct USB Integration** (removed ite8291r3-ctl CLI dependency, uses Python library directly)
- [x] **Custom Color Picker** (dark-themed HSV picker with hue bar, SV square, hex input, presets — replaces system colorchooser)
- [x] **Audio Sync / Visualizer** (Software FFT via PipeWire — captures all audio outputs; GPU-accelerated color flashing per frequency band; persists via `kbd-audio.service` after app close. Chip ADC not wired on NUC X15 so host-driven FFT is the correct and complete implementation.)
- [x] **Palette Reprogramming** — ~~IMPOSSIBLE~~: FW 16.04 ignores ALL palette write commands (CMD 0x07 wValue 0x0300, CMD 0x07 wValue 0x03CC, CMD 0x14 wValue 0x0300 — all ROM-burned). Palette fixed: 1=white 2=orange 3=yellow 4=green 5=blue 6=purple 7=pink 8=random. Per-key Direct Mode (effect 0x33) bypasses palette entirely.
- [ ] **Separate AC/Battery Profiles** (Linux app currently only supports one global lighting profile)

## 5. Front Lightbar (Status LED)
- [x] **Static / Monocolor** (full 16M color, mapped to EC 0-36 PWM steps with rounding)
- [x] **Rainbow Mode** (hardware toggle BIT(7) of 0x0748)
- [x] **Dynamic Rainbow** (software-driven scrolling hue cycle via `LightbarController._start_dynamic_rainbow()`, ~30fps EC sysfs writes)
- [x] **Breathing Mode** — Confirmed non-functional on NUC X15 hardware (BIT(5) of 0x0748 has no visible effect; removed from UI)
- [x] **Trigger Flush** (EC shadow registers flushed via `TRIGGER_1_LIGHTBAR`)
- [x] **Custom Color Picker** (dark-themed HSV picker replaces system colorchooser for both lightbar and keyboard)
- [x] **Graphical Lightbar UI** (Canvas preview with animated rainbow, monocolor glow, calibrated R+G color swatches)
- [x] **Hardware Reset Button** (EC clear/flush via reset button in UI)
- [ ] **Separate AC/Battery Profiles** (Linux app currently only supports one global lighting profile)

## 6. Hardware Toggles
- [x] **Touchpad Toggle** (Fn+F7 → daemon → gsettings + HID LED via hidraw)
- [x] **Touchpad LED Sync** (LED on when touchpad disabled, HID feature report)
- [x] **App UI Touchpad State Tracking** (Toggle switch in Toggles tab + polling; OSD-only notification, no GNOME system notification duplicates)
- [x] **Super Key Lock** (Fn+F2, EC TRIGGER_1_ADDR)
- [x] **Fn Lock** (Fn+Esc toggle)
- [x] **Mic Mute** (WMI event 183 → KEY_MICMUTE)

## 7. Face Unlock
- [x] **Howdy Integration** (install/uninstall, add/remove face models, test recognition)
- [x] **PAM Configuration** (automated PAM integration toggle)
- [x] **Camera Preview** (RGB + IR camera views)
- [x] **Face Model Management** (folders, drag-and-drop, rename, column persistence)

## 8. UI/UX
- [x] **Single password prompt** (pkexec with env forwarding)
- [x] **Dark theme** (indigo/gold palette: #1A1628 bg, #E8B931 accent)
- [x] **Light theme** (ivory/sky-blue palette: #F2EDE6 bg, #4AAFE0 accent)
- [x] **Theme toggle** (full dark↔light switch with per-tab widget restyling, status color adaptation)
- [x] **Brand badges** (Intel blue #0071C5, NVIDIA green #76B900 logos)
- [x] **Consistent sliders** (tk.Scale, uniform sizing)
- [x] **Scrollable Power tab** (Canvas+scrollbar)
- [x] **Window geometry persistence** (save/restore position and size)
- [x] **Per-key keyboard canvas** (proportional layout, 2.7 aspect ratio, uniform gaps)
- [x] **Effect controls** (always visible, disabled/enabled per effect — no layout shifts)
- [x] **App icon** (iNUC with indigo→pale-blue gradient)
- [x] **Daemon service controls** (start/stop/restart from Toggles tab)
- [x] **Consistent widget theming** (all radio buttons and checkbuttons use tk native widgets with gold/indigo theme)
- [x] **Custom color picker** (dark-themed HSV square + hue bar, hex input, RGB values, preset swatches)
- [x] **Auto-save on close**
- [ ] **On-Screen Display (OSD) Overlay** (Missing unified OSD for Fn key combinations)

## 9. System Services
- [x] **kbd-brightness.service** (observe brightness, restore on boot/resume, idle dim handling)
- [x] **touchpad-led.service** (Fn+F7 toggle + HID LED, state-change-only)
- [x] **fan-curve.service** (JSON-driven fan curves, suspend/resume recovery, boot retry)
- [x] **kbd-audio.service** (audio-reactive keyboard daemon — persists audio visualizer after app close, activated via state file IPC)
- [x] **All daemons survive suspend/resume** (verified with rtcwake)
- [x] **3-second WMI grace period** (suppresses stale EC events after driver load)

## 10. Installation & Packaging
- [x] **install.sh** (DKMS build, app copy, systemd services, udev rules, launcher, polkit)
- [x] **uninstall.sh** (clean removal)
- [x] **RPM spec** (nuc-linux-studio.spec with DKMS, services, desktop entry)
- [x] **Desktop entry** (with iNUC icon at all hicolor sizes)

---

### Known Hardware Limitations
- **Lightbar blue LED dim on right side**: Hardware defect — single-zone lightbar, blue LED physically weak on right. Not software-fixable.
- **Lightbar R+G only color space**: With blue dead, the achievable colors are red → orange → amber → yellow → lime → green. Green only appears when R channel drops below ~50% (R<128). UI swatches calibrated to match physical output.
- **Lightbar static mode dim**: EC firmware caps static PWM at ~25-35% duty. Only rainbow (BIT7) gives full brightness.
- **ITE8291R3 palette ROM-burned**: FW 16.04 ignores all CMD 0x07/0x14 palette writes (tested: wValue 0x0300, 0x03CC, with and without 0xCC prefix + commit 0x08). Palette is hardcoded in firmware — not writable at runtime. Per-key Direct Mode (effect 0x33) is the workaround for custom colors.
- **Hardware audio sync (chip ADC)**: ITE8291R3 ADC pins not connected on NUC X15. CMD 0x02 mode=1 silently ignored. This is irrelevant — the software FFT visualizer via PipeWire (`kbd-audio.service`) is fully implemented and superior (works with all audio sources, not just analog).

---

## Session Log

### 2026-05-05 (Sessions 1-3)
- Initial project structure, driver development
- Profile button sync, fan curves, battery charge limit
- Per-key RGB, touchpad LED, keyboard brightness daemon
- Full session details in CHANGELOG.md

### 2026-05-06 (Sessions 4-5)
- Gaming/Coding presets, window close fix
- Per-key RGB grid mapping reworked empirically
- Mic mute WMI event, battery charge limit force-enable
- Keyboard brightness daemon rewritten for observe-only
- Install/uninstall scripts, RPM spec

### 2026-05-08 (Session 6)
- Fn+F8 keyboard toggle fix (effect restore)
- Mic mute event 183, install script service restart

### 2026-05-09 (Sessions 7-9)
- CPU fan overheating fix (3 hot loops eliminated)
- Fan curve daemon created
- Keyboard brightness persistence + idle dim handling
- WMI event grace period
- Keyboard layout proportions fixed
- Theme overhaul (indigo/gold)
- Face unlock tab, lightbar fixes

### 2026-05-10 (Sessions 10-12)
- CTRL_3 power profile solution (7 approaches documented)
- EC temperature race condition fix
- UI layout/sizing overhaul
- Battery gauge redesign
- Fan curve daemon resume handling
- Full effect flow audit (driver → daemon → UI)

### 2026-05-11 (Sessions 13-14)
- Driver: `speed` and `color_index` sysfs attributes
- Backend: speed/color passthrough to sysfs
- Daemon: animated effect restore on resume (not just monocolor/per-key)
- Fan curve daemon: suspend/resume recovery with hwmon re-discovery
- All 3 daemons verified surviving suspend/resume
- CMD 0x02 audio mode discovery + sysfs (audio_mode, audio_sensitivity)
- Palette reprogramming confirmed impossible on FW 16.04
- Undocumented effect IDs probed and confirmed invalid
- Direct USB library integration (removed ite8291r3-ctl CLI dependency)
- Software audio-reactive keyboard mode (FFT spectrum visualizer via PipeWire)

### 2026-05-12 (Session 15)
- Radio button/checkbutton visibility fix — switched ttk→tk native widgets with gold/indigo theme across all tabs
- Options section height increased for per-key button accommodation
- Speed slider enlarged (2.5x longer, 2x taller)
- Palette wiring mismatch confirmed and documented (ROM-burned on FW 16.04)
- Lightbar breathing confirmed non-functional — removed from UI
- Custom dark-themed HSV color picker created (replaces system colorchooser)
- Audio-reactive daemon (`kbd-audio.service`) — audio visualizer persists after app close via state file IPC
- Audio→per-key transition bug fixed (wait for daemon USB release before rebinding kernel driver)
- Full documentation update and project file cleanup

### 2026-05-16 (Session 18) — Version 2.3
- Per-key RGB auto-apply on startup fixed (hardware now in sync immediately on app launch)
- Dynamic Rainbow lightbar effect added (software scrolling hue cycle, ~30fps)
- **Per-Key Brightness UI implemented**: brightness slider now visible in `per-key` mode — allows dimming individual selected keys independently. Slider label dynamically changes to "Key Brightness:" in per-key mode vs "Brightness:" in glow mode. Status bar hints guide user ("use picker to set color, brightness slider to dim"). Clicking a key in per-key mode syncs the brightness slider to that key's saved brightness value.
- CHANGELOG and progress docs updated

### 2026-05-16 (Session 19) — Versions 2.4–2.5
- Touchpad OSD duplicate GNOME notifications fixed (true fallback to notify-send)
- All documentation updated
- Gaming/coding keyboard theme visual overhaul
- OSD GNOME style redesign (GNOME-style pill, frosted-glass shadow, accent bar)
- Writing/browsing theme added (replaces rainbow slot — indigo+yellow 5-tier)
- Fan boost OSD: temp-gated (≥90°C only), 6s ramp-down, `/tmp/nuc_fan_boost_active` flag
- Lightbar false "Off" OSD suppressed with 2s cooldown timestamp
- `_APP_MANAGED` guard in `sync_from_hardware()` — gaming/coding/writing/glow/per-key effects no longer overwritten by sysfs on app open
- Per-key color button removed (picker applies instantly on click)
- Palette swatch spacing increased

### 2026-05-17 (Session 23) — Suspend/Resume Bug Fixes
- **Keyboard resume bug fixed**: `gaming`/`coding`/`writing`/`glow` effects were being restored as flat `monocolor` after suspend/resume. Root cause: `_ensure_effect_on()` in kbd-brightness daemon had no branch for these app-managed per-key themes — they fell through to the `current==off` monocolor fallback. Fix: route all four to `_restore_per_key_from_config()` same as `per-key`. Log now confirms: `Restored app-managed theme 'gaming' as per-key colors`.
- **Battery limit race fixed**: `_reapply_battery_limit()` was applying a stale config value (from a previous session) over a valid in-session sysfs limit. Fix: read current sysfs value first — only apply config if sysfs == kernel default (100). User home configs now checked before root config.
- **Touchpad resume confirmed correct**: touchpad was ON at suspend time (double-tap at 09:15) so ON after resume is correct. Not a bug.

### 2026-05-17 (Session 22) — On-Demand Audio Daemon, Install/Uninstall Hardening
- **kbd-audio.service made on-demand**: No longer auto-enabled at install. App starts/stops via `systemctl start/stop` in `_start_audio_reactive()` / `_stop_audio_reactive()`. 0.5s delayed start prevents USB race on rapid effect switching. Zero CPU when audio effect not active.
- **Audio daemon mtime watchdog**: Self-stops if state file mtime >30s (app crash/kill protection). 10s heartbeat touch inside active loop prevents false-fires during long sessions.
- **install.sh `--no-driver` flag**: Documented and properly implemented — wraps entire DKMS block. Fast redeploy for Python changes now officially supported.
- **uninstall.sh fixed**: Removed duplicate `log()`, version variable added (`VERSION="2.0"`), `nuc_wmi-1.0` → `nuc_wmi-${VERSION}`, `nuc-battery-limit.service` stop/remove added.
- **requirements.txt cleaned**: Removed stale `ite8291r3-ctl` CLI entry; added detailed comments for audio/GPU optional deps.
- **RPM spec updated**: kbd-audio in %files and %preun, not-installed dirs documented, battery-limit in %post/%preun.

### 2026-05-17 (Session 21) — Battery upower Finding & Documentation
- **Root cause confirmed**: `upower.service` restart resets `charge_control_end_threshold` back to kernel default (100). The `nuc-battery-limit.service` oneshot only runs at boot and does NOT protect against mid-session upower restarts.
- **Protection verified**: `_reapply_battery_limit()` in `fan_curve_daemon.py` re-applies the saved charge limit whenever a upower restart is detected AND after every resume from suspend. This was already in the codebase and working correctly.
- **Key distinction**: After a upower restart, if the user manually adjusts the charge slider, sysfs shows the correct value because the UI write both restored and saved it — not because sysfs already had it. The daemon is the silent safety net for cases where the UI is not touched.
- All documentation updated: AGENT_RULES.md, ARCHITECTURE.md (Section 14 added), NUC_STUDIO_PROGRESS.md, CHANGELOG.md.

### 2026-05-16 (Session 20) — Version 2.5.3
- **OSD CSS corruption fixed**: stray `e c` characters on `background-color` line in `OSD_CSS` caused GTK parserej and OSD crash-loop (restart counter > 100). Fixed, OSD confirmed working.
- **Per-key vs Glow fully separated**: Brightness slider hidden in per-key mode; `_apply_per_key()` always uses brightness=100. Glow retains brightness slider.
- **Gaming theme brightness floor raised**: Tier 4 (rest keys) raised from 64→100 R, tier 3 from 128→180, orange adjusted. All tiers visually distinct and present at 50% brightness.
- **Fan curve UI**: sliders 220→160px, GPU temp labels (column 5), distinct CPU/GPU trough colors, alternating even/odd row shading (+18 RGB). Theme-aware on apply_theme().
- **Cairo `_on_draw` fix confirmed**: `cr.fill()` inside `save()/restore()` block, `cr.ellipse=None` removed. No more silent no-op shadow ellipse.
- Toggles tab: mic status refresh added to apply_theme for instant theme-switch color update
- Lightbar tab: color swatches remapped to show actual physical LED output (R+G only, blue dead)
- Lightbar: expanded green swatch range (7 green shades from Yellow-Lime to Deep Green)
- Lightbar: active color preview enlarged to 4× swatch size, "Active:" bold label to left
- Lightbar: all swatches have theme-aware borders (accent for active, border color for pickers)
- Version bumped to 2.0 across setup.py, install.sh, dkms.conf, RPM spec
- All documentation updated with v2.0 findings

