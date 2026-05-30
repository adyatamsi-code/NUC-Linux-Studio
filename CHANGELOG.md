## [2.6.2] 2026-05-30 — Fan Resume Fix: EC PWM Release on Suspend/Resume

### Fan Curve Daemon — Fans No Longer Stuck at Full Blast After Resume

- **Bug**: After suspend/resume, CPU and GPU fans ran at full blast until the 12-second grace period expired (~12s of loud fans after every wake).
- **Root cause**: The fan-curve daemon held `manual_control=1` (PWM writes active) across suspend. When the EC resumed, it found stale PWM values (often 255) already set and couldn't override them during its internal init phase — the daemon and the EC were fighting over PWM registers.
- **Fix 1 — systemd-sleep hook** (`packaging/nuc-fan-curve-sleep` → `/usr/lib/systemd/system-sleep/nuc-fan-curve`): New bash hook called by `systemd-sleep` before every suspend. Releases `manual_control=0` and `pwm1_enable=0` / `pwm2_enable=0` for both `nuc_wmi` and `qc71_laptop` platform paths. EC gets clean ownership before the system powers down.
- **Fix 2 — daemon resume path** (`backend/fan_curve_daemon.py`): On resume detection (wakeup_count change), daemon now immediately releases fan control (`manual_control=0`, `pwm1_enable=0`) before waiting for sysfs to stabilize. Sets a 12s `manual_grace_until` window so PWM writes are blocked while the EC finishes its own thermal initialization. Clears `last_cpu_pwm` / `last_dgpu_pwm` to force a fresh curve re-apply after the grace period.
- **install.sh**: Added step that installs the sleep hook with `chmod +x` and verifies the file is in place.
- **Log output**: `Resume detected — releasing fan control and waiting for EC to settle...` then `Fan control released to EC for resume init`.
- **Files**: `backend/fan_curve_daemon.py`, `install.sh`, `packaging/nuc-fan-curve-sleep`

---

## [2.6.1] 2026-05-17 — Suspend/Resume Bug Fixes: Gaming Theme, Battery Limit Race

### Keyboard — Gaming/Coding/Writing/Glow Themes Restored Correctly After Resume

- **Bug**: After suspend/resume, any app-managed per-key theme (`gaming`, `coding`, `writing`, `glow`) was restored as **flat orange monocolor** instead of the correct multi-color theme.
- **Root cause**: `_ensure_effect_on()` in `kbd_brightness_daemon.py` had no case for these effects. They fell through to the `elif current == "off":` branch (which fires on resume since the driver is freshly bound). That branch picked the first color from `keyboard_colors` — for gaming that's `#ff6400` (orange tier-1) — and wrote `monocolor` to the effect sysfs.
- **Fix**: Added `elif saved_effect in ("gaming", "coding", "writing", "glow"):` branch that calls `_restore_per_key_from_config()` — same path as `per-key`. This correctly restores the full 101-key RGB map from saved colors.
- **Log output**: `Restored app-managed theme 'gaming' as per-key colors` ✅
- **File**: `backend/kbd_brightness_daemon.py`

### Battery — Stale Config Value No Longer Overwrites Valid Sysfs Limit on Resume

- **Bug**: Fan-curve daemon's `_reapply_battery_limit()` was reading a stale config value (e.g. `58%` from a previous session's last save) and overwriting the current sysfs limit. This caused the battery to stop charging after resume when the threshold was erroneously lowered.
- **Root cause**: Config is saved by the app only when settings change. Between sessions, the config may reflect an older limit than what the app last applied and displayed. On resume, the daemon fires before the app opens, reading the stale config and applying it to sysfs.
- **Fix**: `_reapply_battery_limit()` now reads the current `charge_control_end_threshold` sysfs value first. If it's **not** the kernel default (100) — meaning something already set a valid limit — the function returns without touching sysfs. Only if sysfs == 100 (kernel reset by upower) does it fall through to apply the config value. This prevents the stale-config overwrite entirely.
- **Also fixed**: User home config dirs are now checked before `/root` config (root config is often stale from old pkexec sessions). Logs now print which config file the limit was read from.
- **File**: `backend/fan_curve_daemon.py`

### Touchpad — Resume Behavior Confirmed Correct (Not a Bug)

- **Investigated**: User reported touchpad was ON after resume when they expected it OFF. Log trace showed touchpad was double-tapped ON at 09:15 by the user, then the system suspended at 09:47. Resume correctly restored ON state. The user's OFF expectation was based on a prior session's state, not the state at suspend time. No fix needed.

---

## [2.6.0] 2026-05-17 — On-Demand Audio Daemon, Install/Uninstall Fixes, requirements.txt Cleanup

### kbd-audio.service — On-Demand (Not Auto-Enabled)

- **Changed**: `kbd-audio.service` is now installed but **never auto-enabled or auto-started** by `install.sh` or the RPM spec. The service unit file is present so `systemctl start` works, but it is entirely idle (not running, no parec, no USB, 0% CPU) until the audio effect is selected.
- **App-side start**: `KeyboardController._start_audio_reactive()` spawns a 0.5s-delayed background thread that calls `systemctl start kbd-audio.service` when audio mode is first activated. The 0.5s delay covers the USB release race on rapid effect switching.
- **App-side stop**: `KeyboardController._stop_audio_reactive()` calls `systemctl stop kbd-audio.service` immediately after writing `active: false` to the state file. parec is killed, USB is released, kernel driver is rebound — all by the daemon's own cleanup path.
- **Result**: Zero CPU and memory overhead from audio daemon when any non-audio effect is active. Previously ~3-5% CPU was consumed polling `/var/lib/nuc-linux-studio/audio_mode` every 1s regardless of effect.
- **Files**: `backend/keyboard.py`, `install.sh`, `packaging/nuc-linux-studio.spec`

### kbd-audio.service — Crash/Kill Watchdog + Heartbeat

- **Watchdog**: Audio daemon outer poll loop checks `STATE_FILE.stat().st_mtime` on every iteration. If the state file's mtime is >30s old (app crashed/killed without writing `active: false`), daemon writes `{"active": false}` and exits cleanly. This prevents a zombie audio daemon holding the USB device after a killed app.
- **Heartbeat**: Inside the active audio rendering loop, the state file is `touch()`'d every 10s. This updates the mtime, preventing the watchdog from triggering during normal long-running audio sessions where params haven't changed.
- **Idle exit**: If daemon is idle (active=false) and the state file mtime is >60s old, daemon exits cleanly — no need to stay running once it has nothing to do.
- **File**: `backend/audio_daemon.py`

### install.sh — `--no-driver` Flag

- **New flag**: `sudo ./install.sh --no-driver` skips the entire DKMS block (remove → build → install → modprobe → udev rules). Copies app files, restarts services, done in ~10s. Use after any UI/backend Python change.
- **Usage note**: Added 3-line comment block at top of `install.sh` documenting both modes.
- **Not-installed note**: Added comment listing `tools/`, `docs/`, `backup/`, `tests/` as dev-only directories never installed to `/opt/`.
- **Missing**: The udevadm/UPower restart block is also skipped with `--no-driver` (no driver = no udev bind needed).
- **File**: `install.sh`

### uninstall.sh — Three Bug Fixes

- **Duplicate `log()`**: Removed second identical `log()` function definition (was on lines 11-12).
- **Hardcoded version**: Replaced `rm -rf /usr/src/nuc_wmi-1.0` with `rm -rf /usr/src/nuc_wmi-${VERSION}` (new `VERSION="2.0"` variable at top).
- **Missing battery service**: Added `systemctl disable --now nuc-battery-limit.service` and `rm -f /usr/lib/systemd/system/nuc-battery-limit.service`.
- **Bonus**: Added `rm -f /usr/share/applications/nuc-studio.desktop` (alternate desktop filename), `rm -f /etc/udev/rules.d/99-ite8291r3.rules`, and `systemctl stop/disable kbd-audio.service`.
- **File**: `uninstall.sh`

### requirements.txt — Stale Dependency Removed

- **Removed**: `ite8291r3-ctl>=0.0.1` — the CLI tool was removed as a dependency in v2.0 (direct Python library import used instead). The stale entry caused confusing `pip install` errors on fresh systems because the package name is `ite8291r3-ctl` (hyphen) but it installs a CLI binary; the Python *package* `ite8291r3_ctl` (underscore imported) is separate.
- **Added**: Detailed comment block explaining: `ite8291r3_ctl` Python package is required for audio mode (optional feature); install with `pip install ite8291r3-ctl`; CuPy is optional GPU accelerator; both are commented out in the file.
- **File**: `requirements.txt`

---

## [2.5.4] 2026-05-17 — Battery upower Reset Documentation & Protection Verification

### Battery — upower Restart Clears charge_control_end_threshold (Confirmed)

- **Finding**: Restarting `upower.service` resets `charge_control_end_threshold` back to the kernel default of `100`, silently allowing the battery to charge past the configured limit until something re-writes sysfs.
- **Root cause**: upower re-reads and re-initializes sysfs battery devices on restart. Writable threshold values are reset to kernel defaults. This is an upstream upower behavior.
- **Impact**: `nuc-battery-limit.service` (Type=oneshot) only runs at boot — it does NOT protect against a upower restart that happens mid-session (e.g. after a package update, crash, or manual restart).
- **Protection confirmed working**: `_reapply_battery_limit()` in `backend/fan_curve_daemon.py` re-applies the saved charge limit from `settings.json` on every upower restart detection AND after every resume from suspend. This was already in place.
- **Important subtlety**: After a upower restart, if the user moves the charge limit slider before the daemon acts, sysfs shows the correct value because the **UI write** both restored it AND saved it — not because upower preserved it. The daemon is the silent safety net for unattended operation.
- **Rule added to AGENT_RULES.md**: Never rely on `charge_control_end_threshold` persisting across upower restarts without the fan-curve daemon running.

### Documentation

- `docs/AGENT_RULES.md`: Added `⚠️ KNOWN: upower restart clears charge_control_end_threshold` entry in Common Bugs & Fixes section.
- `docs/ARCHITECTURE.md`: Added Section 14 — "Battery Charge Limit — Persistence & upower Interaction" with full flow diagram and rules.
- `docs/NUC_STUDIO_PROGRESS.md`: Expanded Section 3 with two new checked items; added Session 21 log entry.
- `CHANGELOG.md`: This entry.

---

## [2.5.3] 2026-05-16 — OSD CSS Fix, Gaming Theme Brightness, Per-Key/Glow Separation, Fan Curve UI

### OSD — Critical CSS Crash Fixed
- **Bug**: OSD service was crashing instantly on every start with `GLib.GError: 'e' is not a valid property name`.
- **Root cause**: A stray `e c` prefix was present on the `background-color` line inside `#nuc-osd-box` CSS block (line 146), introduced by a previous edit. GTK CSS parser rejected the entire stylesheet, so `NucOSD.__init__()` threw on every launch. Service was in restart-loop (counter > 100).
- **Fix**: Removed the stray characters. `#nuc-osd-box { background-color: rgba(12, 12, 12, 0.72); }` is now valid.
- **Result**: OSD starts cleanly ("NUC OSD listening on /tmp/nuc-osd.sock"), caps-lock/touchpad/kbd-brightness OSDs all work again.
- **File**: `backend/osd.py`

### Keyboard — Per-Key vs Glow Properly Separated
- **Changed**: Brightness slider is now **only** shown for the `glow` effect. It is hidden for `per-key`.
- **Rationale**: Per-key mode lets you set any RGB value per-key — the color itself encodes brightness. A global brightness slider that dims those chosen colors uniformly is confusing and unexpected. Glow mode uses a single base color for all keys + per-key multipliers, so a global brightness control makes sense.
- **Changed**: `_apply_per_key()` now always calls `set_per_key_colors(composite, 100)` — brightness argument is always 100. Per-key colors represent intended luminance; passing the keyboard brightness slider value would double-dim colors (once in RGB, once in hardware).
- **File**: `ui/tabs/keyboard.py`

### Keyboard — Gaming Theme Brightness Floor Raised
- **Bug**: At 50% keyboard brightness, tier 3 (support keys: F1-F10, 8-0, arrows) and tier 4 (rest keys) were nearly invisible because their base RGB values (128, 0, 0) and (64, 0, 0) scaled to (64, 0, 0) and (32, 0, 0) — barely above off.
- **Root cause**: The gaming theme's dynamic range was too large (4:1 ratio between movement and rest tiers), so the bottom tiers disappeared at 50% brightness.
- **Fix**: Raised tier floors — `(255,0,0)` movement, `(255,100,0)` hot (orange, slightly less warm), `(180,0,0)` support (70% red), `(100,0,0)` rest (40% red, was 25%). At 50% brightness: rest keys show at `(50,0,0)` ~20% — dim but visually distinct. All tiers remain identifiable at any brightness level.
- **File**: `ui/tabs/keyboard.py`

### Fan Curve — Shorter Sliders, GPU Temp Labels, Alternating Row Colors
- **Sliders**: CPU and GPU fan curve sliders shortened from `length=220` → `length=160` to fit new GPU temp column.
- **GPU Temp column** (column 5): Added `{temp}°C` labels for GPU fan rows, mirroring the CPU temp column on the right edge of the grid. Now both CPU and GPU fan curves have temp context visible on both sides.
- **Distinct trough colors**: CPU sliders use `scale_trough_cpu` (blue family), GPU sliders use `scale_trough_gpu` (green family). Both themes have dedicated values:
  - Dark: `cpu="#0E1828"`, `gpu="#0E1E0E"`
  - Light: `cpu="#C0D0E8"`, `gpu="#C8E8C0"`
- **Alternating row shading**: Even rows (35°C, 45°C, 55°C…) use the base trough color. Odd rows (40°C, 50°C, 60°C…) are `+18` RGB per channel — visually lighter. Both sides alternate independently (CPU and GPU).
- **Theme-aware**: `apply_theme()` recomputes all alternating trough colors on theme switch.
- **Files**: `ui/tabs/power.py`, `ui/themes.py`

### OSD Cairo `_on_draw` — Previously Broken, Confirmed Fixed
- **Previous bug** (from v2.5.0): `cr.ellipse = None` (invalid attribute assignment) and `cr.fill()` called **after** `cr.restore()` — Cairo's restore() discards the current path before fill can execute, resulting in no shadow ellipse drawn (silent no-op, no crash on fill, but DOES crash on `cr.ellipse = None` attribute write depending on pycairo version).
- **Fix confirmed**: `cr.set_source(pat)` and `cr.fill()` are now inside `save()/restore()` block, before `restore()` is called. The `cr.ellipse = None` line removed entirely.
- **File**: `backend/osd.py`

---

## [2.5.2] 2026-05-16 — OSD CSS Fix (partial), Fan Curve Improvements, Per-Key/Glow Split

*(This entry covers the work done just before v2.5.3 — OSD fix was blocked by the CSS corruption described above)*

### Fan Curve Sliders (Power Tab)
- Sliders shortened 220→160, GPU temp labels added, trough colors split CPU/GPU, alternating rows.
- See v2.5.3 for complete description (same code, same deploy).

---

## [2.5.1] 2026-05-16 — Per-Key Brightness UI

### Keyboard Tab — Per-Key Brightness Slider Now Visible in Per-Key Mode
- **Files Modified:** `ui/tabs/keyboard.py`
- **Feature:** The brightness slider (previously only shown in `glow` mode) is now also displayed when `per-key` effect is active.
- **Behaviour:**
  - In `glow` mode: slider label reads "Brightness:" — adjusts whole-keyboard base brightness
  - In `per-key` mode: slider label reads "Key Brightness:" — adjusts brightness of currently **selected** keys independently
  - Clicking a key in per-key mode syncs the brightness slider to that key's saved brightness value
  - Status bar message updated: "use picker to set color, brightness slider to dim"
- **Why:** The backend (`_apply_brightness`, `_perkey_brightness`) already fully supported per-key brightness in per-key mode; only the UI widget visibility was incorrectly gated to `glow`-only.

## [2.5.0] 2026-05-16 — Lightbar OSD Fix, Fan Boost Ramp-Down, GNOME OSD Style, Writing Theme

### Lightbar — False "Lightbar Off" OSD Suppressed
- **Fixed**: Switching lightbar effects (e.g. rainbow → monocolor) was triggering a "Lightbar Off" OSD.
- **Root Cause**: `LightbarController.set_color()` / `set_effect()` write zeros first (to disable rainbow) before writing the new color. The EC echoes a `lightbar state changed` WMI event mid-write, and the daemon read `multi_intensity = 0 0 0` at that moment.
- **Fix**: Both `LightbarController.set_color()` and `set_effect()` now stamp `/tmp/nuc_lightbar_write_ts`. The daemon skips the OSD if that timestamp is within the last 2 seconds.
- **Files**: `backend/keyboard.py`, `backend/kbd_brightness_daemon.py`

### Fan Curve Daemon — Thermal Boost Ramp-Down
- **New**: When CPU or GPU temp drops from ≥90°C back below 85°C, fans no longer jump immediately to curve target. Instead a 2-step linear ramp over ~6s: 255 → midpoint → curve target.
- **New**: `/tmp/nuc_fan_boost_active` flag file — written when temp ≥ 90°C, deleted when ramp-down completes.
- **File**: `backend/fan_curve_daemon.py`

### Fan Boost OSD — Temp-Gated + Better Labels
- **Changed**: Fan boost OSD no longer triggered by EC `fan_always_on` sysfs (unreliable). Now driven by `/tmp/nuc_fan_boost_active` flag file polled every 5s in kbd_brightness_daemon main loop.
- **Labels**: `"🌡 Thermal: Fans Full Blast"` ON / `"✅ Thermal: Cooling Down"` OFF.
- **File**: `backend/kbd_brightness_daemon.py`

### OSD — GNOME-style Visual Redesign
- **Restyled** to match GNOME Shell's native OSD aesthetic:
  - `border-radius: 24px` pill shape (was 12px card)
  - No border (was `1px solid rgba(255,255,255,0.08)`)
  - `rgba(12,12,12,0.72)` darker/more transparent bg (was 0.88 opaque)
  - Icon `font-size: 32px`, `font-weight: 400` label at `rgba(255,255,255,0.75)` (softer, less KDE-like)
  - Accent bar 3px tall, pill-shaped rounded ends (was 6px rectangular)
  - Cairo radial gradient shadow vignette behind the box for frosted-glass depth
  - `WIN_W=180`, `WIN_H=110` (slightly wider/taller for better breathing room)
  - Display time 1800ms, 10-step fade at 25ms (smoother fade-out)
- **File**: `backend/osd.py`

### Keyboard — "Writing" Theme (replaces "Rainbow")
- **New effect**: `writing` — 5-tier indigo & yellow per-key theme for writing/browsing sessions.
  - A–Z letters: `(255,220,0)` full yellow — warm gold at slider=100
  - SPACE, ENTER, BACKSPACE, TAB: `(75,0,220)` full indigo — "commit" keys
  - Arrows, HOME, END, PGUP, PGDN, DEL, INS: `(110,60,200)` soft indigo — navigation family
  - SHIFT×2, CTRL×2, ALT×2, CAPS, FN, WIN, MENU: `(128,110,0)` dim yellow — half amplitude
  - Everything else: `(30,0,80)` near-dark indigo — barely visible
- **Position**: replaces `rainbow` slot — sits between `monocolor` and `coding` in the Simple group.
- **Migration**: saved configs with `keyboard_effect: "rainbow"` auto-migrate to `"writing"` on load.
- **File**: `ui/tabs/keyboard.py`

---

## [2.4.0] 2026-05-16 — Touchpad OSD Suppresses GNOME Notifications, Gaming/Coding Themes Overhauled

### Touchpad — GNOME Notification Suppression
- **Fixed**: After adding the custom OSD overlay, GNOME was still showing its own "Touchpad Enabled/Disabled" system notifications in addition to our OSD popup.
- **Root Cause**: `show_touchpad_osd()` in `backend/touchpad_daemon.py` sent to the OSD socket AND always called `notify-send` unconditionally (the comment said "fallback" but there was no condition).
- **Fix**: Added `osd_sent` boolean flag. The `notify-send` call is now only made if the Unix socket send to `/tmp/nuc-osd.sock` fails (i.e. OSD service is unavailable). This makes it a true fallback — no duplicate notifications when OSD is running.
- **File**: `backend/touchpad_daemon.py`

---

## [2.3.0] 2026-05-16 — Per-Key Startup Fix, Dynamic Rainbow Lightbar

### Keyboard Tab — Per-Key Auto-Apply on Startup (Bug Fix — Issue 3)
- **Fixed**: Per-key RGB colors were NOT sent to hardware on app startup / config restore.
  Previously, `_apply_settings_impl` skipped the hardware write for per-key mode during `is_loading`,
  returning early and leaving LEDs dark until the user manually clicked "Apply".
- **Fix**: Per-key mode now ALWAYS calls `_apply_per_key()` — both on initial load and on manual effect
  switch. This brings the hardware in sync immediately on startup and after suspend/resume.

### Lightbar Tab — Dynamic (Scrolling) Rainbow Effect
- **New effect**: "Dynamic Rainbow" added to lightbar effect selector.
- **Description**: Software-driven scrolling rainbow that continuously cycles through the full HSV hue
  spectrum at ~30fps, writing to the `multi_intensity` sysfs each cycle.
- **Implementation**: `LightbarController._start_dynamic_rainbow()` / `_stop_dynamic_rainbow()` —
  managed by a daemon thread (same pattern as existing software breathing).
- **Preview canvas**: Dynamic rainbow uses the same animated canvas preview as hardware rainbow.
- **Backend**: `LightbarController.set_effect("dynamic_rainbow", brightness)` starts the SW loop.
  All other `set_color()` / `set_effect()` calls stop the dynamic rainbow thread before proceeding.
- **State persistence**: Saved and restored via `lightbar_effect` in settings.json.
- **Resource impact**: ~5-10% CPU for the write loop on 30fps sysfs writes (documented in FEATURE_COMPARISON).

## [2.2.0] 2026-05-16 — Keyboard UI Overhaul, Battery Boot Service, Audio Preview, Color Memory

### Keyboard Tab — Per-Effect Color Memory
- `_save_effect_settings` now persists `cp_hue`, `cp_sat`, `cp_val`, `mono_color`, `glow_brightness` per effect.
- `_restore_effect_settings` restores color picker HSV + brightness when switching back to any effect.
- `_update_controls_state` loads per-effect saved color instead of always defaulting to `_mono_color`.
- `load_state` restores picker from active effect's settings on startup.
- Glow canvas is now recomputed from `mono_color + perkey_brightness` on restore — prevents double-dimmed colors from raw snapshot.

### Keyboard Tab — Audio Mode Preview
- Rainbow mode: keyboard canvas now shows a left→right hue gradient (red→violet) matching the hardware visual. Previously all keys showed neutral theme color.
- Single color mode: all keys show the picker color as before.
- Toggling "🌈 Use rainbow" immediately repaints the canvas.
- `_refresh_audio_canvas` is called from `load_state` and `_apply_settings_impl` for correct first-draw.

### Keyboard Tab — Selection UX Overhaul
- **Left-click**: always selects a key (no longer toggles off on second click).
- **Right-click**: deselects the key under cursor, preserving its color.
- New **✔ Deselect** button: drops selection highlight on all selected keys, preserves all colors.
- **✖ Clear Sel** / **✖ Clear All**: labels clarified (were ClrSel/ClrAll).
- All buttons wider with emoji prefixes for clarity.

### Keyboard Tab — Selection Outline Contrast
- Selection outline now uses `t["keycap_selected"]` (theme-aware) instead of hardcoded `#E8B931`.
- Dark theme: `#E8B931` gold — high contrast on dark charcoal keys.
- Light theme: `#E05000` deep orange — maximum contrast on ivory/light key surface.
- Outline width bumped from 2px → 4px for both themes.
- Bug fixed: `_redraw_keyboard` was ignoring theme and always using gold — now consistent with `_update_selection_display`.

### Battery — Boot-Time Charge Limit
- New `backend/battery_limit_apply.py`: reads `charge_limit` from saved config and writes to sysfs at boot.
- New `nuc-battery-limit.service` (Type=oneshot): runs at boot, enabled by install script.
- Reads from all user home dirs + `/root` config paths.
- Confirmed working: applies `charge_control_end_threshold` + `charging_profile` on boot.

### Battery — Light Theme Label Visibility
- Battery stat columns (Design Capacity, Current Max, Wear Level, Cycle Count, Voltage Now) now re-themed on `apply_theme` — previously skipped by `_retheme_all`, leaving stale dark-theme colors on light theme.
- Charge Limit title + description stored as `self._charge_limit_title_lbl` / `self._charge_limit_desc_lbl` and updated in `apply_theme`.
- Light theme `fg_secondary` darkened: `#505060` → `#3A3A4A` for better contrast on ivory background.

### OSD — Fan Boost Icons & Labels
- Fan Boost ON: `🌀` orange-red (`#ff7043`) — "Thermal Boost: Fans Max"
- Fan Boost OFF: `💤` gray (`#90a4ae`) — "Thermal Boost: Off"
- Previously both states showed identical `🌀` icon, only color differed.
- Label corrected: Fan Boost is an EC thermal protection event (>~90°C), not a hotkey toggle.

### Bug Fix — App Launch Failure (UnboundLocalError)
- `root = tk.Tk(...)` was indented inside `if '--env-file' in _sys.argv:` block — only assigned when launched via pkexec with env file, never on normal launch.
- Fixed indentation: `root` now always assigned at function scope.

---

## [2.1.0] 2026-05-16 — OSD Multi-Monitor Fix, UI Polish, Docs Overhaul

### OSD — Multi-Monitor Positioning Fixed
- **Root cause**: `Gtk.WindowType.TOPLEVEL` is ignored by Mutter/GNOME Shell on XWayland — WM always moves it to the primary monitor, so both OSD windows appeared on screen 0.
- **Fix**: Changed to `Gtk.WindowType.POPUP` which bypasses WM placement policy entirely; `window.move(x, y)` is now honored unconditionally.
- Added extra `position()` calls at +50ms and +150ms after `show_all()` to handle async XWayland remap events.
- `StartupWMClass` in `.desktop` file and `tk.Tk(className=...)` now match (`nuc-studio`), fixing the taskbar icon.

### Keyboard Tab — Brightness Slider Scope Fixed
- Brightness slider is now hidden when the `per-key` effect is active; shown only for `glow` effect.
- `brt_row` stored as `self._brt_row` and toggled in `_update_effect_ui` alongside speed/direction/reactive rows.

### Feature Comparison Updated
- OSD row: changed from ❌ No to ✅ Yes (GTK3 per-monitor overlay, caps-lock ON=green/OFF=red, 10 event types)

### Documentation
- `docs/ARCHITECTURE.md`: Added Section 11 (OSD Architecture), updated Section 10 (deploy/sync)
- `docs/FEATURE_COMPARISON.md`: OSD row updated
- `CHANGELOG.md`: This entry
- `install.sh`: Fixed `.desktop` filename (`nuc-studio.desktop`), `StartupWMClass=nuc-studio`, added rsync sync procedure note

---

## [2.0.0] 2026-05-13 — Version 2.0 Release

### Version Bump
- `setup.py`: 1.0.0 → 2.0.0
- `install.sh`: VERSION 1.0 → 2.0
- `driver/dkms.conf`: PACKAGE_VERSION 1.0 → 2.0
- `packaging/nuc-linux-studio.spec`: Version 1.0 → 2.0

### Theme: Status Indicator Colors Fixed
- **Face Unlock tab** (`ui/tabs/face_unlock.py`): `apply_theme()` now calls `_refresh_status()` to update
  status label foreground colors (green/red) on theme switch. Previously only backgrounds were updated,
  leaving status text stuck at the initial theme's green regardless of theme toggle.
- **Toggles tab** (`ui/tabs/toggles.py`): Added `_refresh_mic_status()` to `apply_theme()` for instant
  mic mute status color update on theme switch (was delayed by 1.5s timer).
- Dark theme `status_green`: `#00E676` (neon green) — bright, high-contrast on dark backgrounds
- Light theme `status_green`: `#2E8B57` (grass green) — readable on light backgrounds

### Lightbar: Color Swatch Calibration
- **Physical color mapping**: Swatches now display the approximate physical LED output, not the raw EC
  value. The NUC X15 lightbar has R+G LEDs only (blue dead), so R+G mixing produces:
  - R=255, G=0→255: red → orange → amber → yellow (R overpowers G visually)
  - R=255→0, G=255: yellow → lime → spring → green (green only visible when R < ~128)
- **13 calibrated swatches**: 6 red-to-yellow + 7 yellow-to-green with equal visual spacing
- **Active color preview**: 48×48 (4× the 24×24 picker swatches), with accent-colored border
- **"Active:" label**: Bold, positioned to the left of the preview (was small text above)
- **20px separation** between active preview and picker swatches
- **Theme-aware borders**: All swatches use `t["border"]`, active preview uses `t["accent"]`

### Documentation
- `README.md`: Updated to v2.0, added lightbar calibration note, mic mute status, dark/light theme description
- `docs/FEATURE_COMPARISON.md`: Graphical Lightbar UI → ✅, UI Theme → Dark/Light
- `docs/NUC_STUDIO_PROGRESS.md`: Checked off lightbar UI + reset, added light theme + theme toggle entries, added session 16-17 log
- `CHANGELOG.md`: Added v2.0 release entry
- `packaging/nuc-linux-studio.spec`: Added v2.0 changelog entry

---

## [2026-05-13a] Theme Overhaul, Fan Curve Labels, Battery Colors, Touchpad Fix, /opt Deploy

### ⚠️ RECURRING BUG: Edits not deployed to /opt/nuc-linux-studio/
- The app runs from `/opt/nuc-linux-studio/`, NOT from the dev directory `~/Downloads/Project-nuc/`.
- Multiple editing sessions produced correct code in dev, but the user saw NO changes because
  the installed copy at `/opt/` was stale. This has now happened **at least 3 times**.
- **Every agent session MUST copy edited files to /opt/ after editing.** See AGENT_RULES.md.

### Light Theme Overhaul (`ui/themes.py`)
- Replaced all chocolate-brown accents (`#5C3A1E`) with sky blue (`#2E8BC0`)
- Tab selected bg, radio buttons, sliders, progress bars, buttons — all sky blue now
- Text changed from brown (`#2A1E14`) to neutral charcoal (`#1E1E24`)
- Backgrounds shifted from warm tan to cleaner ivory/cream

### Dark Theme Status Indicators (`ui/themes.py`)
- `status_green`: `#4CAF50` (dull) → `#00E676` (neon green) — affects all status labels
- `status_red`: `#E05050` → `#FF5252` (brighter)
- Light theme `status_green`: `#388E3C` (grass green, appropriate for daylight)

### Fan Curve Graph (`ui/tabs/power.py`)
- Line labels: "CPU" → "i7-11800H", "dGPU" → "RTX 3070m"
- Axis tick labels and axis titles now use neutral `text_color` instead of branded blue/green
- Live RPM labels: removed hardcoded `#0071C5`/`#76B900`, use theme's branded colors set at init

### Battery (`ui/tabs/battery.py`)
- Charge line/text: hardcoded `#FFB6C1` → theme-aware `battery_charge_line` color

### Face Unlock (`ui/tabs/face_unlock.py`)
- Stop preview buttons now use theme colors instead of hardcoded values

### Touchpad Double-Tap Fix (`backend/touchpad_daemon.py`)
- When firmware double-tap detected via HID poller, daemon now skips re-writing HID (`skip_hid=True`)
- Prevents race condition where redundant HID write could confuse firmware digitizer state
- `_apply_full_state()` and `_set_state()` accept `skip_hid` parameter

---

## [2026-05-11h] Update FEATURE_COMPARISON.md with Resource Impact

### Feature Comparison Update
- **`docs/FEATURE_COMPARISON.md`**: Added a `Est. Impact` column providing an estimated breakdown of the CPU and Memory footprint relative to the entire application ecosystem.

## [2026-05-11g] Update FEATURE_COMPARISON.md

### Feature Comparison Update
- **`docs/FEATURE_COMPARISON.md`**: Updated the comparison table based on the official Intel NUC Software Studio User Guide (Section 6.1).
  - Added `Separate AC/Battery Profiles` row under both Keyboard Backlight and Front Lightbar, noting that the Linux app only supports one global lighting profile while the original supports different settings for plugged in vs battery.
  - Added `Graphical Lightbar UI` row under Front Lightbar to indicate the missing on-screen visual representation.
  - Added `Hardware Reset Button` row under Front Lightbar controls, highlighting the absence of the EC clear/flush button in the Linux app.
  - Added `App UI Touchpad State Tracking` row under Hardware Toggles, noting the missing UI toggle switch/state tracking for the touchpad.
  - Added `On-Screen Display (OSD) Overlay` row under Other Features, noting the missing unified OSD for Fn key combinations in the Linux app.

## [2026-05-11f] Documentation Overhaul

### All Markdown Files Updated
- **`README.md`**: Complete rewrite — added kernel modules table, sysfs interfaces table, hardware compatibility matrix, all current features including audio visualizer and direct USB integration
- **`driver/README.md`**: Replaced old qc71_laptop README with comprehensive nuc_wmi + ite8291r3 driver documentation — full sysfs interface tables, installation instructions, compatibility info
- **`docs/HARDWARE_SPEC.md`**: Added ITE8291R3 command protocol tables, CMD 0x02 global control modes, firmware limitations, Fn key map with correct WMI event codes (183 for mic mute, 185/187 for backlight), CTRL_3 register documentation, touchpad HID details
- **`docs/NUC_STUDIO_PROGRESS.md`**: Reorganized into 10 sections (added System Services, Installation & Packaging), added all completed features from sessions 13-14 (speed/color sysfs, audio mode, direct USB, software audio visualizer), added Known Hardware Limitations section, consolidated session log
- **`docs/GEMINI.md`**: Added Rules 8-9 (driver sysfs conventions, daemon conventions), updated project structure to reflect current layout
- **`docs/KEYBOARD_LAYOUT.md`**: No changes needed (already up to date)
- **`docs/ARCHITECTURE.md`**: No changes needed (already comprehensive with sections 1-12)

---

## [2026-05-11e] Remove ite8291r3-ctl CLI Dependency, Software Audio-Reactive Mode

### Backend: Direct USB Library Integration
- **Files Modified:** `backend/keyboard.py`, `install.sh`
- **Removed all subprocess calls to `ite8291r3-ctl` CLI tool** — the backend now uses the `ite8291r3_ctl` Python library directly via USB for:
  - `set_effect()` — builds effect data and calls `dev.set_effect()`
  - `set_backlight_color()` — calls `dev.set_color()`
  - `set_backlight_brightness()` — calls `dev.set_brightness()`
  - `get_backlight()` — calls `dev.get_brightness()` / `dev.is_off()`
- **Fixes "[Errno 2] No such file or directory: 'ite8291r3-ctl'"** error in the UI
- Install script now clears `__pycache__` to prevent stale bytecode issues
- **Root cause of install bug**: `/opt/nuc-linux-studio/` is the runtime location (used by launcher), but `pip install -e .` only updates the dev tree. Install script must copy to `/opt/`.

### Software Audio-Reactive Keyboard Mode
- **New file:** `tools/test_music_sensitivity.py`
- **Hardware mode** (`--hw`): Sweeps CMD 0x02 mode=0x01 sensitivity values (ADC-based, analog audio only)
- **Software mode** (`--sw`): Captures system audio via PipeWire/PulseAudio monitor source
  - Works with **Bluetooth, HDMI, USB DAC, any output** — not limited to analog path
  - FFT spectrum analysis → 21-band equalizer visualization across keyboard columns
  - Uses `ite8291r3_ctl` library for proper per-key RGB protocol
  - Auto-detects EasyEffects sink for complete audio capture
  - ~30fps rainbow spectrum visualizer with auto-gain normalization

### New Hardware Documentation (from Gemini + Tongfang schematic analysis)
- **CMD 0x02 Mode 0x04**: Internal Clock Pulse (BPM divider), does NOT use ADC
- **Interrupt EP 0x81**: Reports ADC peak level in Byte 5 during Mode 0x01 — can confirm if analog path is active
- **Palette unlock sequence**: `{0xFE, 0x55, 0xAA, ...}` before CMD 0x14 (risky, writes to flash)
- **EC Audio-to-KBD gate**: WMI GUID `ABBC0F6F-8EA1-11d1-00A0-C90629100000`, EC offset 0xCF/0xD0 — toggles ALC269 analog out to ITE ADC
- **CMD 0x08 Byte 7**: "Density/Spread" parameter — controls how many keys lit in wave/fireworks
- **Per-key brightness**: Some keys consistently brighter in tests — hardware may support per-key brightness granularity

## [2026-05-11d] CMD 0x02 Protocol Fully Documented, Audio Sensitivity Control

### CMD 0x02 Global Control — Full Protocol Breakdown (Confirmed by Tongfang Spec)
- **Files Modified:** `driver/ite8291r3.c`, `docs/ARCHITECTURE.md`, `tools/test_music_mode.py`
- **Mode 0x00**: Normal/Soft Mode — returns control to 0x08 Effect Engine
- **Mode 0x01**: **Hardware Audio Sync** — ITE8291R3 listens to internal ADC pins (PA0/PA1), wired from Realtek ALC269 analog output on King County/QC71 schematic
- **Mode 0x02**: Real-Time Data Mode — prepares for per-key RGB host streaming (Direct Mode)
- **Mode 0x03**: **Diagnostic Scanner** — factory-level LED/key matrix validation tool, not a consumer animation
- **Mode 0x04**: BPM/Global Pulse — pulses based on average audio amplitude (FW dependent)
- **Added `audio_sensitivity` sysfs** (RW, 0-255): Controls ADC gain/threshold for mode 0x01
  - 0x00–0x20: Very low (requires max volume)
  - 0x80 (128): Standard (recommended default)
  - 0xFF (255): Max (picks up electronic noise — explains previous "chaotic" behavior)
- **Hybrid mode confirmed**: Aurora (0x0E) + reactive=1 via 0x08, then CMD 0x02 mode=0x01 = audio-triggered spikes over Aurora background
- **Default sensitivity changed from 0xFF → 0x80** to avoid noise-floor triggering

## [2026-05-11c] Audio Mode Discovery, Effect ID Probing, Palette Conclusion

### Discovery: CMD 0x02 Audio/Animation Modes
- **Files Modified:** `driver/ite8291r3.c`, `tools/test_music_interactive.py`
- **Description**: Discovered that USB command byte `0x02` (distinct from effect ID 0x02 "breathing") controls an undocumented audio/animation mode on the ITE8291R3. Sent AFTER a SET_EFFECT command, it modifies the active effect's behavior.
- **Command format**: `{0x02, mode, sensitivity, 0, 0, 0, 0, 0}` via standard send_ctrl (wValue 0x0300)
- **Mode 0x00**: Disable (normal effect)
- **Mode 0x01**: Audio/reactive enhancement — combined with aurora reactive=1, creates reactive patterns
- **Mode 0x03**: Row scanner — lights keys one by one per row, overrides certain colors, leaves partial rows lit
- **Interesting combinations found**:
  - Aurora + audio_mode=3: Row scanner effect (unique, not achievable any other way)
  - Aurora + reactive=1 + speed=0 + audio_mode=1: Fast reactive row pattern
  - Aurora + reactive=1 + speed=0x0A + audio_mode=1: Shifting color reactive pattern
- **Added `audio_mode` sysfs** (RW, 0-3): Sends CMD 0x02 immediately when written, and auto-sends after every effect change if non-zero.

### Research: Palette Reprogramming — IMPOSSIBLE on FW 16.04
- **Conclusion**: After testing CMD 0x07 (wValue 0x0300), CMD 0x07 (wValue 0x03CC with 0xCC prefix + commit 0x08), and CMD 0x14 (wValue 0x0300), all silently ignored. The palette is **hardcoded in firmware** on this NUC X15 (FW 16.04.00.00, PID 6006). Cannot be changed.
- **Final palette mapping** (firmware-locked):
  - 1=white, 2=orange, 3=yellow, 4=green, 5=blue, 6=purple, 7=pink, 8=random
- Palette code and sysfs kept in driver for potential future firmware updates.

### Research: Undocumented Effect IDs — ALL INVALID
- **Tested**: 0x07, 0x08, 0x0C, 0x0D, 0x0F, 0x10, 0x12, 0x13
- **Result**: All silently ignored by hardware (chip continues previous effect)
- **Confirmed valid IDs on FW 16.04**: 0x02, 0x03, 0x04, 0x05, 0x06, 0x09, 0x0A, 0x0B, 0x0E, 0x11, 0x33
- Gemini's suggestions about "Neon", "Sway", "Radial Wave", "Snake" etc. were incorrect for this firmware.

### Research: Music/Audio Sync Mode
- **CMD 0x02 with mode=0x01**: Does NOT create obvious audio-reactive behavior on its own. The NUC X15 motherboard likely does NOT have the audio codec wired to the ITE8291R3's ADC pins.
- **CMD 0x02 with mode=0x03**: Creates a unique row-scanning animation that may have been mistaken for "music sync" during early development (it has a rhythmic quality).
- **True music sync** would require host-driven per-key RGB streaming (Direct Mode 0x33 + FFT daemon).

### Cleanup: Removed Non-Working Features
- Removed non-existent effect IDs (neon, sway, radial, snake) from driver and UI
- Disabled palette init on probe (no-op on this firmware)
- Color presets renamed to match actual hardware palette (white/orange/yellow/green/blue/purple/pink)

---

## [2026-05-11b] Keyboard Effect Color Palette, Reactive Mode, Wave Direction, UI Overhaul

### Feature: Color Palette Programming (`driver/ite8291r3.c`)
- **Files Modified:** `driver/ite8291r3.c`
- **Description**: The ITE8291R3 has a 7-slot internal color palette that animated effects reference by index. The default palette on this NUC X15 hardware had incorrect colors (index 1 = white instead of red). The driver now **reprograms the palette on every module load** using `CMD_SET_PALETTE (0x07)` USB HID command. Added `palette` write-only sysfs for custom palette entries (`echo "index r g b" > palette`).
- **Default palette**: 1=red(255,0,0), 2=orange(255,128,0), 3=yellow(255,255,0), 4=green(0,255,0), 5=blue(0,0,255), 6=teal(0,255,255), 7=purple(128,0,255)

### Feature: Reactive Mode (`driver/ite8291r3.c`, `backend/keyboard.py`)
- **Files Modified:** `driver/ite8291r3.c`, `backend/keyboard.py`, `backend/facade.py`, `ui/tabs/keyboard.py`
- **Description**: Added `reactive` sysfs attribute (0/1) to driver. Byte 6 of the SET_EFFECT command is the reactive flag for supported effects. Ripple, aurora, and fireworks now automatically enable reactive=1, making them respond to keypresses (hardware-driven, low latency).
- **Supported effects**: ripple ✅, aurora ✅, fireworks ✅ (per ITE8291R3 protocol)

### Feature: Wave Direction Control (`driver/ite8291r3.c`, `backend/keyboard.py`, UI)
- **Files Modified:** `driver/ite8291r3.c`, `backend/keyboard.py`, `backend/facade.py`, `ui/tabs/keyboard.py`
- **Description**: Added `direction` sysfs attribute (0-4: none/right/left/up/down) to driver. For wave effect (0x03), byte 6 = direction instead of reactive. UI has a direction dropdown (enabled only for wave). Direction saved per-effect in settings.
- **Directions**: 0=none, 1=right, 2=left, 3=up, 4=down

### Improvement: UI Controls — Disable Instead of Hide
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description**: Per-key buttons (Set Color, Clear Selected, Clear All, Apply), color preset combo, speed slider, and direction dropdown are always visible but **disabled/enabled** based on the current effect. No more dynamic layout shifts that confuse users.

### Improvement: Per-Effect Settings Memory
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description**: Each effect now saves and restores its own color preset, speed, and direction. Switching effects restores last-used settings. Saved to config as `keyboard_effect_settings`.

### Improvement: Separate Per-Key and Mono Color Storage
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description**: Per-key color layout and monocolor are stored separately (`_perkey_colors`, `_mono_color`). Switching between per-key and monocolor no longer destroys the other's colors. Both saved to config as `keyboard_perkey_colors` and `keyboard_mono_color`.

### Improvement: Per-Key Auto-Apply on Switch
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description**: Switching to per-key mode now immediately sends saved per-key colors to hardware — no need to click Apply.

### Fix: Effect Property Support Matrix Enforced in UI
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description**: Color preset dropdown only enabled for effects that actually support color (breathing, raindrop, ripple, aurora, fireworks). Wave and marquee always use random colors per hardware spec. Removed redundant "(multi)" variants for wave and marquee since they don't support single-color mode.

### Research: Music Sync / Audio Visualizer
- **Finding**: The ITE8291R3 (Rev 0.03) does NOT have a native audio processing mode. "Music sync" is host-driven — requires a userspace daemon to perform FFT audio analysis and stream per-key RGB frames via the existing Direct Mode infrastructure. Not implemented yet.

### Research: Color Palette Reprogramming
- **Finding**: The ITE8291R3 uses `CMD 0x07` to reprogram palette slots. Packet: `{0x07, index, R, G, B, 0, 0, 0}`. This is now implemented in the driver and auto-applied on init.

### Effect Property Support Matrix (Hardware)
| Effect | Color | Speed | Direction | Reactive |
|--------|:---:|:---:|:---:|:---:|
| breathing | ✅ | ✅ | - | - |
| raindrop | ✅ | ✅ | - | - |
| ripple | ✅ | ✅ | - | ✅ |
| aurora | ✅ | ✅ | - | ✅ |
| fireworks | ✅ | ✅ | - | ✅ |
| wave | ❌ | ✅ | ✅ | - |
| marquee | ❌ | ✅ | - | - |
| rainbow | ❌ | - | - | - |

---

## [2026-05-11] Keyboard Effect Speed & Color Control, Resume Restoration

### Feature: Driver Speed & Color Index Sysfs (`driver/ite8291r3.c`)
- **Files Modified:** `driver/ite8291r3.c`
- **Description**: Added `speed` (RW, 0-9) and `color_index` (RW, 0-8) sysfs attributes to the ITE8291R3 driver. Effect commands now use stored speed/color_index instead of hardcoded `speed=5, color=8`. Writing to speed or color_index while an animated effect is active immediately re-applies the effect with the new parameters. Removed unused `ite8291r3_groups[]` array.
- **Color index mapping**: 0=red, 1=orange, 2=yellow, 3=green, 4=blue, 5=teal, 6=purple, 7=white, 8=random/multi

### Feature: Backend Speed & Color Passthrough (`backend/keyboard.py`)
- **Files Modified:** `backend/keyboard.py`
- **Description**: `set_effect()` kernel driver path now writes `speed` and `color_index` sysfs before writing the effect name. Added `_COLOR_NAME_TO_INDEX` mapping dict. UI speed slider and "(multi)" color variant now actually work.

### Fix: Daemon Restores Animated Effects on Resume (`backend/kbd_brightness_daemon.py`)
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Description**: `_ensure_effect_on()` now restores any saved effect from config — not just monocolor/per-key. Reads `keyboard_effect` and `keyboard_speed` from settings.json, writes speed/color_index sysfs, then writes the effect name. `_ensure_effect_not_off()` also delegates to `_ensure_effect_on()` for full restore. Added `_color_index_from_config()` helper that finds the closest ITE8291R3 color index from saved keyboard colors.

### Fix: Fan Curve Daemon Resume Handling (`backend/fan_curve_daemon.py`)
- **Files Modified:** `backend/fan_curve_daemon.py`
- **Description**: Added suspend/resume detection (polls `/sys/power/suspend_stats/success`). On resume, waits 2s then re-discovers hwmon paths since they can renumber. Added boot retry loop (30s) and stale-path recovery in exception handler. Logs hwmon paths on startup.

### Verified: All Daemons Survive Suspend/Resume
- **Test**: `rtcwake -m mem -s 5` (5-second suspend cycle)
- **kbd-brightness**: Re-bound ITE8291R3 USB, restored `breathing` effect with speed=3 from config ✅
- **fan-curve**: Re-discovered hwmon paths, continued applying curves ✅
- **touchpad-led**: Re-applied disabled state + HID LED ✅ (already had resume handling)

### Fix: Fn+F8 Toggle Broken After Effect Restore Changes
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: `_ensure_effect_not_off()` was changed to delegate to `_ensure_effect_on()`, which does a full config-based restore including per-key USB writes (101 entries). This is too slow for the Fn+F8 toggle path — each brightness cycle triggered a full USB restore, causing cascading state confusion and rapid cycling.
- **Fix**: Restored `_ensure_effect_not_off()` to be lightweight: just set `monocolor` if effect is `off`, or re-apply per-key colors if effect is `per-key`. The heavy `_ensure_effect_on()` is only called on boot/resume (`restore_effect=True`).

### Fix: Driver Speed/Color Writes Causing Effect Glitches
- **Files Modified:** `driver/ite8291r3.c`
- **Root Cause**: `speed_store()` and `color_index_store()` re-applied the current animated effect every time they were written. When the backend wrote speed → color_index → effect in sequence, the first two writes re-applied the OLD effect, causing visual glitches.
- **Fix**: `speed_store()` and `color_index_store()` now only store the value without re-applying. The effect is applied once when `effect_store()` is written, using the already-stored speed and color_index values.

### Fix: Backend Skips Speed/Color for Off Effect
- **Files Modified:** `backend/keyboard.py`
- **Description**: `set_effect()` no longer writes speed/color_index sysfs for the "off" effect (unnecessary and could cause spurious state).

---

## [2026-05-10c] Icon Gradient & Text Alignment Refinement

### App Icon Update
- **Files:** `ui/assets/inuc_icon.png` (256px), `inuc_icon_128.png`, `inuc_icon_64.png`, `inuc_icon_48.png`
- **Changes**: Pushed indigo further up in gradient (power curve 0.4 instead of linear), pale blue now concentrated at the top. "i" bottom-aligned to "NUC" baseline. Text centered horizontally, positioned in lower portion of icon.

---

## [2026-05-10b] App Icon, Backend Fixes, Fan Curve Fix, Face Unlock Overhaul

### Feature: App Icon (iNUC)
- **Files:** `ui/assets/inuc_icon.png` (256px), `inuc_icon_128.png`, `inuc_icon_64.png`, `inuc_icon_48.png`
- **Description**: Created dark purple (#2d2640) app icon with yellow (#E8B931) "iNUC" text. Installed to `/usr/share/icons/hicolor/` at all standard sizes. Desktop entry now uses `Icon=nuc-linux-studio` instead of generic `preferences-system`.

### Fix: Fan Curve Sliders Drifting
- **Files Modified:** `ui/tabs/power.py`
- **Root Cause**: `_load_curve_to_sliders()` programmatically sets slider values which triggers `_on_curve_change()` callbacks, causing cascading monotonicity enforcement that shifts other sliders.
- **Fix**: Added `_loading_sliders` guard flag. When True, `_on_curve_change` returns immediately.

### Fix: PWM Display Corrected
- **Files Modified:** `ui/tabs/power.py`
- **Root Cause**: Live status showed raw sysfs PWM value (0-255) with a "%" suffix, e.g. "PWM: 85%" when actual duty was 33%.
- **Fix**: Now displays `round(value * 100 / 255)` as actual percentage.

### Fix: Keyboard Brightness — Fight Back Against External Dim
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: gsd-power idle dim sets kbd brightness to 0; stale WMI events during dim could cycle to Off.
- **Fix**: Daemon immediately restores brightness when external dim detected. WMI events during idle-dim state restore brightness instead of cycling.

### Feature: Face Unlock Tab Overhaul
- **Files Modified:** `ui/tabs/face_unlock.py`
- Independent folder naming (display name stored separately from howdy snapshot labels)
- Drag-and-drop snapshots between folders
- Column width persistence (saved to `~/.config/nuc_linux_studio/face_groups.json`)
- Rename now works: folders rename display only, snapshots edit howdy's models.dat
- RGB camera preview button (alongside IR camera)
- Bigger Treeview heading font

### Fix: Backend Code Quality
- **`facade.py`**: Fixed expression-as-statement in `set_fan_curve` (was `x if cond else None`)
- **`touchpad_daemon.py`**: Replaced hardcoded `"adriansandru", "1000"` fallback with dynamic user detection via `/home` enumeration

### Cleanup: Unused Assets Removed
- Deleted: `download_logos.py`, `download_logos.sh`, `fix_logos.sh`, `intel.svg`, `nvidia.svg`, `intel_logo.svg`, `nvidia_logo.svg`
- Kept: `intel_logo.png`, `nvidia_logo.png` (used by power tab), all `inuc_icon*.png`

### UI: Toggles Tab Buttons
- Smaller font (8pt), right-aligned via weight=1 spacer column

---

## [2026-05-10] Power Profile CTRL_3 Solution, Temperature Fix, Idle Dim Fix & UI Improvements

### Feature: CTRL_3 Power Profile Reading (Driver)
- **Files Modified:** `driver/pdev.c`, `driver/ec.h`
- **Description**: Replaced unreliable 0x0751 register reads with CTRL_3 (0x07A5) power LED register for profile identification. CTRL_3 bits 0-1 mirror the physical power button LED state and are always readable, even with manual fan mode ON. Button press handler no longer writes to EC — only schedules a deferred manual-mode clear at 300ms so LEDs update correctly.
- **Impact**: Eliminates double-cycling, stale reads, and software tracking desync that plagued all previous approaches (6 attempts documented in ARCHITECTURE.md §9).

### Fix: EC Temperature Reading Race Condition
- **Files Modified:** `backend/fans.py`, `ui/tabs/power.py`
- **Root Cause**: EC updates temperature registers asynchronously; kernel reads during partial update return spurious values (e.g. 165°C on dGPU).
- **Fix**: Backend rejects readings >150°C or <0°C (substitutes 0). UI clamps display to 0–120°C as secondary safety net.

### Fix: Keyboard Brightness Preserved During Screen Idle Dim
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: GNOME `gsd-power` writes brightness=0 on idle dim. Daemon's sysfs poll picked this up and updated `current_index` to Off, losing the user's chosen level.
- **Fix**: Daemon now distinguishes user-initiated (Fn+F8 dmesg) vs external (sysfs poll) brightness changes. When brightness drops to 0 without a dmesg event, daemon sets `_idle_dimmed=True` and preserves saved level. On brightness restore, re-applies saved brightness and effect.

### Feature: Face Unlock Tab (Howdy Integration)
- **Files Modified:** `ui/tabs/face_unlock.py`
- **Description**: Full Howdy face authentication management tab — install/uninstall Howdy, add/remove face models, test recognition, configure PAM integration. Includes real user detection for running commands as the non-root user.

### UI: Battery Tab Visual Improvements
- **Files Modified:** `ui/tabs/battery.py`
- **Description**: Giant battery icon gauge on wider canvas (740×700), deferred initial status read for instant tab loading.

### UI: Toggles Tab & Daemon Management
- **Files Modified:** `ui/tabs/toggles.py`
- **Description**: Centralized daemon service controls (start/stop/restart touchpad-led, kbd-brightness, fan-curve services) with live status polling.

### Docs: Architecture Deep Dive
- **Files Modified:** `docs/ARCHITECTURE.md`
- **Description**: Added sections 9 (Power Profile & Manual/Automatic Mode — full experimental results from EC register probing), 10 (EC Temperature Race Condition), and 11 (Keyboard Brightness & Screen Idle Dim). Documents all 7 attempted approaches for profile sync with detailed timing data.

## [2026-05-09] Keyboard Layout Visual Fix

### Fix: Keyboard UI Keycap Proportions & Spacing
- **Files Modified:** `ui/tabs/keyboard.py`
- **Root Cause**: Gemini implemented inter-key spacing by computing `pad_x` from `col_w * 0.1` and `pad_y` from `row_h * 0.1` independently. Since `row_h` is ~10× larger than `col_w`, vertical gaps were massively larger than horizontal gaps, crushing key height and making text overflow. The overall keyboard size was not expanded to accommodate gaps — keycaps were shrunk instead.
- **Fix** (3 changes):
  1. **Aspect ratio 3.5 → 2.7**: Keyboard is taller/larger, making 1U keys nearly square (matching physical hardware)
  2. **Uniform gap**: Single gap value derived from 1U key width (`unit_key_w * 0.05`), used for both X and Y padding — ensures equal spacing in all directions
  3. **Font size reduction**: Multipliers reduced to `0.14` (arrows) and `0.10` (regular keys) of actual rendered key height to prevent text overshooting keycap boundaries
- **Docs Updated:** `docs/KEYBOARD_LAYOUT.md` — added inter-key gap rules and font sizing guidelines

## [2026-05-09] Thermal Optimization, Fan Curve Daemon, Keyboard Brightness Fixes & Driver Grace Period

### Fix: CPU Fan Overheating When App Open
- **Files Modified:** `backend/touchpad_daemon.py`, `ui/tabs/power.py`, `ui/main.py`
- **Root Cause**: Three independent hot loops were driving CPU usage and PWM writes:
  1. Touchpad daemon had a 5-second re-enforcement loop continuously running `runuser + gsettings`
  2. Power tab's `update_status()` called `_apply_curve_for_current_temp()` every 3 seconds, continuously writing PWM values even when unchanged
  3. App exit left fans stuck in manual mode (`pwm1_enable: 2`, PWM locked at last written value)
- **Fix**:
  - Touchpad daemon made state-change-only (removed 5s re-enforce loop)
  - Power tab no longer writes PWM directly; persists curve state to JSON for the fan curve daemon
  - UI refresh interval increased from 3s to 5s
  - App exit no longer releases fan control if `fan-curve.service` is active

### Feature: Fan Curve Daemon (`fan-curve.service`)
- **Files Created:** `backend/fan_curve_daemon.py`
- **Files Modified:** `install.sh`, `uninstall.sh`, `packaging/nuc-linux-studio.spec`, `ui/tabs/toggles.py`
- **Description**: New dedicated systemd daemon that reads fan curve state from `/var/lib/nuc-linux-studio/fan_curve_state.json`, interpolates temperature→PWM values, and writes to hwmon — only when values actually change. Polls every 3 seconds. Survives app close, maintaining custom fan curves persistently.
- **Architecture**: UI writes curve config to JSON → daemon reads and applies → if state file missing or disabled, daemon releases fans back to EC automatic control.

### Fix: Keyboard Brightness Not Restoring After Reboot
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: Daemon only used `/tmp/nuc_kbd_brightness` (volatile, lost on reboot). After reboot, brightness fell back to config default (50%) instead of last-used value (100%).
- **Fix**: Added persistent state file `/var/lib/nuc-linux-studio/kbd_brightness`. Daemon loads from persistent state first, then config fallback. Both files updated on every state change.

### Fix: Keyboard Turning Off Spontaneously
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: Dual brightness consumer conflict — GNOME's `gsd-power` catches `KEY_KBDILLUMTOGGLE` and writes brightness to sysfs, while our daemon also caught the same event via dmesg and blind-cycled `(current_index + 1) % 3`. When at 100%, next step was Off.
- **Fix**: Daemon changed to **observe-only** on brightness events — reads sysfs after 150ms delay (letting gsd-power finish), syncs state files, does NOT write brightness. Added periodic 5-second sysfs poll for state synchronization.

### Fix: Spurious WMI Event 187 on Driver Load
- **Files Modified:** `driver/events.c`
- **Root Cause**: EC delivers stale/queued WMI events when `wmi_install_notify_handler()` registers the callback. Event `int=187` ("keyboard backlight changed") fires 1-17 seconds after every driver load/reload, causing unwanted brightness changes.
- **Fix**: Added 3-second grace period (`WMI_GRACE_JIFFIES = 3 * HZ`) in `process_event_72()`. Keyboard backlight events (codes 185, 187, 240) are logged as "suppressed — grace period" and not reported to the input subsystem or LED hw_changed during the grace window after handler installation.

## [2026-05-08] Keyboard Toggle Fix & Mic Mute Event

### Fix: Fn+F8 Toggle Not Lighting Keyboard
- **Files Modified:** `backend/kbd_brightness_daemon.py`
- **Root Cause**: The daemon only wrote brightness (0/128/255) to sysfs but never checked/set the keyboard `effect`. After reboot or app close, the ITE8291R3 effect is `off`, so brightness writes have no visible result.
- **Fix**: Added `_ensure_effect_on()` that checks `/sys/class/leds/ite8291r3::kbd_backlight/effect` and sets it to `monocolor` if it's `off`. Called automatically when setting brightness > 0.

### Fix: Mic Mute WMI Event Code 183
- **Files Modified:** `driver/events.c`
- **Description**: The NUC X15 sends WMI event code **183** (0xB7) for the mic mute button, not code 7 as the original driver expected. Added `case 183:` to `process_event_72()` and `{ KE_KEY, 0xb7, { KEY_MICMUTE }}` to the keymap so GNOME receives the mic mute input event.

### Fix: Install Script Service Restart
- **Files Modified:** `install.sh`
- **Description**: Changed `systemctl enable --now` to `systemctl enable` + `systemctl restart` so services pick up new code on reinstall instead of continuing with the old daemon process.

## [2026-05-08] Build Fix & Driver Rebuild

### Build Environment Issue
- **Problem**: DKMS build failed with `fatal error: asm/cpufeaturemasks.h: No such file or directory` on Fedora 44 kernel 6.19.14-300.fc44.
- **Root Cause**: The `kernel-devel-6.19.14-300.fc44` package was missing generated arch headers (`cpufeaturemasks.h`, `orc_hash.h`) in `arch/x86/include/generated/asm/`. This is a Fedora 44 packaging bug.
- **Fix**: `sudo dnf reinstall kernel-devel-$(uname -r)` — reinstalling the package restores the missing generated headers.
- **Note**: Copying generated headers from an older kernel (e.g. fc43) causes `struct module` size mismatch at load time (`module nuc_wmi: .gnu.linkonce.this_module section size must match`), so always use the correct kernel-devel package.

### Driver Changes
- **`events.c`**: Fixed stray `y` character before `/* microphone mute button */` comment that was introduced in a previous edit.

### System Configuration
- **Secure Boot**: DISABLED (confirmed via `mokutil --sb-state`). Module signing warnings are cosmetic only.
- **Modules loaded**: `nuc_wmi`, `ite8291r3` both loaded successfully after rebuild.
- **Services**: `touchpad-led.service` and `kbd-brightness.service` enabled and running.

## [2026-05-06] Keyboard Preset Modes & Close Bug Fix

### Feature: Gaming & Coding Keyboard Modes
- **Files Modified:** `ui/tabs/keyboard.py`
- **Description:** Re-added "Gaming" and "Coding" preset modes to the keyboard effect dropdown. Gaming uses 670nm wavelength (red, `#FF0000`) and Coding uses 520nm wavelength (green, `#00FF00`). Both are monocolor modes with a fixed color — selecting them immediately applies the color to the entire keyboard and lightbar at the current brightness level.

### Fix: Window Close Crash (AttributeError)
- **Files Modified:** `ui/main.py`
- **Description:** Added `self._touchpad_daemon = None` initialization in `NUCApp.__init__`. Previously, closing the window via the X button triggered `_stop_touchpad_daemon()` which accessed `self._touchpad_daemon` — an attribute that was never set because the daemon was moved to a systemd service in a prior session.
- **Reasoning:** The daemon spawn code (`_start_touchpad_daemon`) is still present but never called (commented out in favor of systemd). The `_stop_touchpad_daemon` method checks the attribute, so it must exist. Initializing to `None` makes the guard `if self._touchpad_daemon` safely return False.

## [2026-05-05] Profile & Fan Curve Improvements

### Fix: Hardware Profile Button
- **Description:** Fixed the physical performance mode button so it correctly cycles through power profiles and syncs with the application.

### Feature: Fan Curves in App
- **Description:** Added fan curve support to the application UI, allowing users to define and apply custom fan curves directly from the interface.

### Feature: Profile Selection from App
- **Description:** Users can now set power profiles (Balanced, Silent, Performance, Benchmark) directly from the application UI, with proper EC register writes and UI feedback.

## [2026-05-05] Profile Button Sync Fix + Blue LED Logging

### Fix: Physical Profile Button Not Syncing with UI
- **Files Modified:** `driver/events.c`, `driver/pdev.c`, `ui/tabs/power.py`
- **Description:** 
  - Event 176 (perf mode button) now cycles the EC FAN_CTRL register (0x0751) bits 0-2 through profiles 0→1→2→0 and emits `sysfs_notify` so the UI can react.
  - `pm_profile_show` now uses 3-bit mask (0x07) instead of 2-bit (0x03) per `FAN_CTRL_LEVEL_MASK`.
  - UI `apply_profile` no longer fails with "hardware did not change" — removed strict pre/post comparison.
  - UI `update_status` refreshes displayed profile every 3 seconds to sync with physical button.
- **Reasoning:** The physical button generates WMI event 176 but the EC does NOT automatically update the fan control register. The driver must handle the event by cycling the profile value. Previously the event was ignored ("handled by polling") but the register never changed.

### Known Issue: Blue LED (Logged, Not Resolved)
- **Status:** Blue channel of lightbar shows very dim, only on right side of bar.
- **What works:** Red, green, rainbow animation (all LEDs, full brightness).
- **What doesn't:** Static blue via register 0x074B — appears faint and only right portion lights.
- **Tested approaches that didn't help:**
  1. Full 0-255 direct write (lightbar stopped responding entirely)
  2. Step-based 0-36 scaling (same dim blue)
  3. Writing CTRL register before colors (same)
  4. Writing CTRL after colors (same)
  5. Not touching CTRL at all, just write RGB + disable rainbow (same)
  6. Enabling Uniwill mode 0x0741=0x01 (no change)
- **Next steps to investigate:**
  - Compare with the exact binary Gemini compiled previously (if available)
  - Try alternate blue register address (0x074C?)
  - Try WMI method for lightbar color instead of direct EC register writes
  - Check if Windows driver uses ACPI method call instead of direct EC

## [2026-05-05] Major Project Restructure and Bug Fixes

### Project Restructure
- **Files Modified:** Entire project layout
- **Description:** Reorganized project from `interface/linux_nuc_studio/` nested layout to flat top-level structure:
  - `driver/` — nuc_wmi kernel module (moved from `linux_drivers/nuc_wmi/`)
  - `backend/` — Python sysfs backend (moved from `interface/linux_nuc_studio/backend/`)
  - `ui/` — Tkinter GUI (moved from `interface/linux_nuc_studio/ui/`)
  - `reference/` — read-only reference drivers (qc71_laptop, tuxedo-keyboard, windows_drivers)
  - `packaging/` — .desktop and .spec files
  - `tests/` — test scripts
- Removed dead files: `interface/linux_nuc_studio/backend.py`, `tools/` duplicates, `obsolete/`
- Updated all imports from `linux_nuc_studio.backend` → `backend`, `linux_nuc_studio.ui` → `ui`
- **Reasoning:** Clean separation of driver/backend/UI per project rules. Eliminates confusion between reference and development code.

### Fix: Multiple pkexec Password Prompts
- **Files Modified:** `backend/core.py`, `backend/keyboard.py`
- **Description:** Added `batch_writes()` context manager that accumulates `write_text()` calls and flushes them in a single `pkexec` invocation. Updated `LightbarController.set_color()` to use `write_multiple()` for multi_intensity + brightness in one call. Updated `set_effect("off")` to batch all disable writes.
- **Reasoning:** Previously each `write_text()` called `pkexec` separately — setting lightbar color triggered 2 prompts, effects triggered 3-4. Now all writes per action are batched into one elevated shell command.

### Fix: Lightbar Blue Intensity (Driver)
- **Files Modified:** `driver/led_lightbar.c`
- **Description:** Three changes to `multi_intensity_store()`:
  1. Added rounding to scaling formula: `(value * 36 + 127) / 255` instead of `(value * 36) / 255`
  2. Changed write order: set CTRL register (disable animations, enable lightbar) BEFORE writing RGB values
  3. Replaced multiple separate `set_rainbow_mode(0)` + `set_breathing_mode(0)` + `switch()` calls with single atomic CTRL register read-modify-write
- **Reasoning:** Blue appeared at very low intensity only on right side. The old code wrote colors while animations might still be active (EC processes writes sequentially and could be interrupted by the late ctrl change). The rounding fix prevents low RGB values from truncating to 0.

### Documentation
- **Files Modified:** `docs/GEMINI.md`, `docs/HARDWARE_SPEC.md`
- **Description:** Updated project rules to reflect new structure and established rules (reference-only drivers, single pkexec prompt, hardware assumptions).

## [2026-04-26] Documentation Update
- **Files Modified:** `NUC_STUDIO_PROGRESS.md`
- **Description:** Added a progress tracker document to map the features described in the official Intel NUC Software Studio User Guide PDF to our Linux driver and frontend ecosystem.
- **Reasoning:** To meet the user's request of extracting the functionality described in the official Intel NUC manual and keeping track of what works, what falls back to different modes, and what's yet to be implemented.

## [2026-04-26] Driver Recompilation Script
- **Files Modified:** `reload_driver.sh`
- **Description:** Created a bash script to cleanly compile and reload the updated `qc71_laptop` module.
- **Reasoning:** Provided a rapid testing mechanism to reload the `qc71_laptop` driver in-place, preventing the user from needing to manually unload and reload the module during the testing phase of the lightbar and profile fixes.

## [2026-04-26] Project Reorganization
- **Files Modified:** `organize_project.sh`
- **Description:** Created a shell script to reorganize the loose files in the project root into structured directories: `linux_drivers`, `windows_drivers`, `interface`, `tools`, `docs`, and `obsolete`.
- **Reasoning:** To fulfill the user's request to clean up the project structure, separate the different drivers, isolate the UI interface, and group utility scripts, making the project easier to navigate and maintain as development continues on merging the two Linux drivers.

## [2026-04-26] Touchpad LED Logic Fix
- **Files Modified:** `qc71_laptop/events.c`
- **Description:** Inverted the bit manipulation for `CTRL_4_TOUCHPAD_TOGGLE_OFF` when handling touchpad WMI events.
- **Reasoning:** The user reported that the touchpad white LED was not turning on when the touchpad was disabled. The original logic was incorrectly setting the `CTRL_4_TOUCHPAD_TOGGLE_OFF` bit to `1` when the touchpad was turned off (which turned the LED off), and clearing it to `0` when the touchpad was turned on (which turned the LED on). This change swaps the logic so the LED lights up when the touchpad is inactive, which is the expected behavior for the device.

## [2026-04-26] Touchpad LED Revert and HID Daemon Implementation
- **Files Modified:** `qc71_laptop/events.c`, `linux_nuc_studio/backend/touchpad.py`, `linux_nuc_studio/backend/touchpad_daemon.py`
- **Description:** Reverted the previous `CTRL_4_TOUCHPAD_TOGGLE_OFF` bit inversion. Added a new Python daemon to control the Touchpad LED via HID feature reports.
- **Reasoning:** Further investigation revealed that the `CTRL_4_TOUCHPAD_TOGGLE_OFF` EC register bit does NOT control the Touchpad LED; it actually disables the hardware double-tap toggle switch. The previous bit inversion was reverted to restore the double-tap functionality. The Touchpad LED on TongFang/Uniwill models is physically wired to the I2C-HID Touchpad Controller and must be toggled by sending a specific HID feature report to the touchpad itself. Since ACPI modules (`qc71_laptop`) cannot safely send HID reports, the fix was implemented in userspace as part of `linux_nuc_studio`. A new daemon `touchpad_daemon.py` monitors the log (`/dev/kmsg`) for WMI events emitted by `qc71_laptop` and dispatches the correct `HIDIOCSFEATURE` ioctl commands to `/dev/hidraw*` to toggle the LED synchronously with the touchpad state.

## [2026-04-26] Lightbar Multi-color LED Integration and Fixes
- **Files Modified:** `qc71_laptop/led_lightbar.c`, `qc71_laptop/pdev.c`, `linux_nuc_studio/backend/keyboard.py`
- **Description:** Abandoned the touchpad LED issue as requested. Integrated multi-color LED control into `qc71_laptop` by simulating the multi-color interface (`multi_intensity`) natively under the `led_classdev` API instead of relying on `led-class-multicolor`, which prevented the driver from loading on some kernels. Modified `qc71_led_lightbar_setup` to bypass the `qc71_features.lightbar` ACPI feature check. Reverted EC mapping to strictly scale 0-255 RGB values to the exact EC PWM levels `0-9` (multiplied by 4) to fix broken registers causing only RED to display. Explicitly disabled rainbow mode internally when setting `multi_intensity` to avoid color desynchronization. Updated `pdev.c` pm_profile sysfs endpoint to return `-EOPNOTSUPP` on write, forcing the UI to fallback correctly to `WMBC` ACPI WMI commands. Removed undeclared dependency in `keyboard.py` to fix controller failure.
- **Reasoning:** The user reported two regressions: 1) "Profile setting failed - hardware did not change from 2". This was caused by my previous commit re-adding `pm_profile_store` but not writing to the correct ACPI endpoint. Since `STA0_ADDR` (`0x68`) acts purely as a status-read register on the NUC X15 architecture rather than a writable hardware hook, returning `0` inside the driver tricked the Python frontend into thinking the profile was updated. By returning `-EOPNOTSUPP`, the Python application correctly triggers its WMAX/WMBC ACPI fallback logic which directly changes the EC thermal profile dynamically. 2) "I can't change the keyboard lighting anymore". My previous Python patch added a `time.sleep(0.02)` call but the module was only imported within the `LightbarController` scope, which caused the `KeyboardController` implementation to throw NameErrors when evaluated. The import statement was
## [2026-05-14] Touchpad Toggle — Full Fix (Kernel Debounce + Daemon Architecture)
### Root Cause Found
The touchpad toggle (Fn+F7 and double-tap) was broken due to three compounding issues:
1. **EC register corruption**: Writing to EC CTRL_4 (page 0x07, offset 0xA6) desynchronized firmware's internal LED/touchpad state machine. Reboot required to recover. **Rule: never write EC CTRL_4 from software.**
2. **Firmware double-fires i8042 sequence**: Each physical Fn+F7 press causes the EC firmware to send the touchpad scancode sequence TWICE — with a variable 0.6s–3s gap between firings. No userspace debounce is reliable.
3. **Daemon was reading HID instead of writing it**: Firmware fires the toggle event but does NOT update the HID feature report. The daemon must WRITE the new state; firmware never writes HID.
### Fixes Applied
#### `driver/events.c`
- Added kernel-level 3-second debounce in `key_event_work()` using `ktime_get()` — drops second firing before it reaches dmesg
- Removed EC CTRL_4 register writes from WMI event handlers (cases 4/5) and `key_event_work`
- **Files:** `driver/events.c`
#### `backend/touchpad_daemon.py`  
- On "touchpad toggle pressed" dmesg event: call `_toggle()` (flip state + write HID) instead of reading HID back
- Increased userspace debounce to 2.0s as secondary safety net
- **Files:** `backend/touchpad_daemon.py`
### Suspend/Resume Status
- ✅ Resume with touchpad ON: works (sleep hook forces ON before suspend, daemon confirms ON after)
- ⚠️ Resume with touchpad OFF: needs further testing (sleep hook forces ON before suspend, daemon should re-apply OFF after resume)
- Sleep hook: `/usr/lib/systemd/system-sleep/nuc-touchpad-sleep.sh`
