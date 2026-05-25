# Agent Rules & Knowledge Base

## MANDATORY PROCEDURES

### Before Modifying ANY File:
1. **Read current state first** — always read the full file before editing
2. **Use `install.sh --no-driver`** to deploy without rebuilding DKMS (fast, safe for UI/backend changes)
3. **Document changes**: Update CHANGELOG.md after every session

### Deploy Rule — ALWAYS Use install.sh
- **Never manually `cp` files to `/opt/`** — the install script handles caches, services, OSD restart
- **`sudo bash install.sh --no-driver`** — skips DKMS rebuild, deploys app + backend + services in ~10s
- **`sudo bash install.sh`** — full install including DKMS (use only when driver changed)
- The install script clears `__pycache__`, restarts all services, restarts OSD for the active user
- Source: `/home/adriansandru/Downloads/Project-nuc/` → Deployed: `/opt/nuc-linux-studio/`
- `--no-driver` also skips udevadm/UPower restart (safe for Python-only changes)

### When Stuck or Need Online Research:
1. **Ask the user to relay a question to Gemini** — format a clear, specific question with all hardware context
2. **Wait for the response** before implementing
3. **Never guess** at hardware behavior — test or ask

### Filter Out What Doesn't Work:
- **Log failed approaches** in this file so they are never retried
- **Log successful approaches** so they can be replicated
- **Don't loop** on the same failed approach more than once

### Reference Documents (READ BEFORE ANY TASK):
- `docs/HARDWARE_SPEC.md` — Authoritative hardware reference (EC registers, HID, device IDs)
- `docs/ARCHITECTURE.md` — Full system architecture, data flows, component inventory
- `docs/TOUCHPAD_DAEMON_LOG.md` — Touchpad debugging history (bugs found, fixes, hardware facts)
- `docs/NUC_STUDIO_PROGRESS.md` — Feature completion tracker
- `docs/FEATURE_COMPARISON.md` — Windows vs Linux feature parity
- `docs/GEMINI.md` — Project rules (driver structure, conventions, daemon rules)
- `docs/KEYBOARD_LAYOUT.md` — Keyboard grid mapping reference
- `docs/GEMINI_LIGHTBAR_QUESTION.md` — Lightbar brightness investigation

---

## UI ARCHITECTURE RULES

### Theme System
- **Two themes**: `dark` (indigo/gold) and `light` (ivory/sky-blue)
- **Theme dict keys used everywhere** — never hardcode colors in widget creation
- **`apply_theme()`** must update ALL widget fg/bg explicitly — `_retheme_all()` deliberately skips `fg` on Labels to avoid overwriting data-driven colors
- **Pattern for static labels**: store as `self._label_name`, add explicit `.configure(fg=t["..."])` in `apply_theme()`
- **`keycap_selected`**: dark=`#E8B931` gold, light=`#E05000` deep orange — use `t["keycap_selected"]` never hardcode
- **`fg_secondary`**: dark=`#908898`, light=`#3A3A4A` — darkened for light theme contrast

### Keyboard Tab — Color & Effect Memory
- `_effect_settings[effect]` stores: `color_preset`, `speed`, `direction`, `reactive`, `cp_hue`, `cp_sat`, `cp_val`, `mono_color`, `glow_brightness`
- `_save_effect_settings()` must be called: on any color change, on effect switch (before leaving old effect), on slider/checkbox change
- `_restore_effect_settings(effect)` restores picker HSV + mono_color + brightness; call `after(50, draw_*)` to defer widget updates
- **Glow canvas** stores pre-multiplied brightness colors — NEVER restore from raw `_effect_canvas_colors["glow"]`. Always recompute: `mono_color × perkey_brightness[k]`
- **`keyboard_colors`** = canvas display state (may be brightness-dimmed). **`_perkey_colors`** = true per-key colors. **`_mono_color`** = base color for glow/monocolor.
- `get_state()` saves both `keyboard_colors` AND `keyboard_perkey_colors` — both needed for correct restore

### Keyboard Tab — Selection Model
- **Left-click**: always ADD to selection (never toggle off)
- **Right-click**: REMOVE from selection (color preserved)
- **✔ Deselect button**: clears all selection highlights, colors preserved
- **✖ Clear Sel**: resets color of selected keys to DEFAULT_COLOR
- **✖ Clear All**: resets all keys to DEFAULT_COLOR
- Selection outline: `t["keycap_selected"]`, width=4 (both `_redraw_keyboard` and `_update_selection_display`)

### Keyboard Tab — Audio Preview
- **Rainbow mode**: paint each column a distinct hue via `hue = col_index / 16` — static preview matching hardware visual
- **Single color mode**: fill all keys with picker color
- `_refresh_audio_canvas()` must be called from: `_on_effect_change`, `_on_audio_rainbow_change`, `_apply_settings_impl`, `load_state`
- Do NOT use `DEFAULT_COLOR` for audio rainbow canvas — that shows neutral gray, not a rainbow

### Battery Tab
- `_stat_col_frames` list: each entry is `(col_frame, caption_lbl, value_lbl)` — iterate in `apply_theme` to re-color
- Charge Limit labels: `self._charge_limit_title_lbl`, `self._charge_limit_desc_lbl` — update in `apply_theme`
- Anonymous `tk.Label(...)` without storing reference = invisible to `apply_theme`; always store as `self._*`

### OSD
- **ALWAYS use `Gtk.WindowType.POPUP`** — TOPLEVEL gets repositioned by Mutter/GNOME on XWayland regardless of `window.move()`
- Call `position()` at show_all + idle + +50ms + +150ms to fight XWayland async remap
- Force `GDK_BACKEND=x11` via env (set in autostart desktop file)
- Socket: `/tmp/nuc-osd.sock` Unix DGRAM, JSON `{"type":..., "value":..., "label":...}`

### OSD CSS Rules (CRITICAL)
- **Never introduce stray characters** in the `OSD_CSS` string — GTK parser rejects the entire stylesheet on any invalid token and the OSD crashes at launch, entering a restart-loop.
- Any invalid property name (even a stray letter like `e c`) causes `GLib.GError: 'e' is not a valid property name` at `provider.load_from_data()`.
- Diagnose via: `journalctl --user -u nuc-osd -n 20 --no-pager` — error message shows exactly which character/line failed.

### Cairo Drawing — `_on_draw` Rules (CRITICAL)
- **`cr.fill()` MUST be called BEFORE `cr.restore()`** — `restore()` discards the current path. Calling `fill()` after `restore()` draws nothing (silent no-op).
- **Cairo has no `cr.ellipse()` method** — use `cr.save() / cr.translate(cx, cy) / cr.scale(w, h) / cr.arc(0, 0, 1, 0, 6.2832) / cr.set_source(pat) / cr.fill() / cr.restore()` for ellipse gradient.
- Pattern for radial shadow ellipse:
  ```python
  cr.save()
  cr.translate(cx, cy)
  cr.scale(width * 0.58, height * 0.42)
  cr.arc(0, 0, 1, 0, 6.2832)
  cr.set_source(pat)   # BEFORE restore
  cr.fill()            # BEFORE restore
  cr.restore()
  ```

---

## COMMON BUGS & FIXES (CONFIRMED)

### ❌ FAILED: `cp -r` to deploy
- Copies `__pycache__` from dev — stale bytecode runs instead of new source
- **Fix**: Always use `install.sh` or `rsync --exclude='__pycache__'`

### ❌ FAILED: Hardcoded `#E8B931` for keycap_selected
- Gold is invisible on dark-theme charcoal keys; pale blue was low contrast on light theme
- **Fix**: Use `t["keycap_selected"]` — theme provides correct color for each theme

### ❌ FAILED: Restoring glow canvas from `_effect_canvas_colors["glow"]`
- Snapshot contains pre-multiplied brightness values — restoring gives double-dimmed wrong colors
- **Fix**: Recompute `mono_color × perkey_brightness[k]` on every restore-to-glow

### ❌ FAILED: `DEFAULT_COLOR` for audio rainbow canvas
- Renders as neutral gray (theme text color), not a rainbow
- **Fix**: Compute `hue = col_index / total_cols`, convert HSV→hex per key

### ❌ FAILED: `Gtk.WindowType.TOPLEVEL` for OSD windows
- Mutter places all TOPLEVEL windows on primary monitor, ignoring `window.move()`
- **Fix**: Use `Gtk.WindowType.POPUP` + multiple `position()` calls

### ❌ FAILED: `root = tk.Tk(...)` indented inside `if '--env-file' in _sys.argv:`
- `root` only assigned when launched via pkexec with `--env-file`, causing `UnboundLocalError` on normal launch
- **Fix**: `root = tk.Tk(...)` must be at function scope, outside all conditionals

### ❌ FAILED: Anonymous `tk.Label()` without storing reference
- Invisible to `apply_theme()` — fg color stuck at creation-time theme after theme switch
- **Fix**: Always `self._label = tk.Label(...)` for any label that has theme-sensitive fg

### ❌ FAILED: `_retheme_all()` handling fg for all labels
- `_retheme_all` deliberately skips fg on Labels — written this way to avoid overwriting data-driven colors (health %, battery %, etc.)
- **Fix**: Explicitly update each static label in `apply_theme()` with the correct theme key

### ✅ WORKING: OSD Notification — True Fallback to notify-send
- `show_touchpad_osd()` sends to `/tmp/nuc-osd.sock` first; `notify-send` is only called if socket send FAILS.
- Pattern: set `osd_sent = True` inside the try block, then `if osd_sent: return` before the fallback.
- **Do NOT call notify-send unconditionally** — GNOME will show duplicate notifications alongside the OSD popup.

### ✅ WORKING: Battery boot-time charge limit
- `backend/battery_limit_apply.py` + `nuc-battery-limit.service` (Type=oneshot)
- Reads from all user home config paths + `/root`
- Writes `charge_control_end_threshold` AND `charging_profile` (for nuc_wmi driver)

### ⚠️ KNOWN: upower restart clears `charge_control_end_threshold`
- Restarting (or crash-cycling) `upower.service` resets `charge_control_end_threshold` back to the kernel default of `100`.
- The `nuc-battery-limit.service` (Type=oneshot) only runs at boot — it does NOT re-apply after a upower restart mid-session.
- **Protection in place**: `fan_curve_daemon.py::_reapply_battery_limit()` re-writes the saved limit on every upower restart detection AND after every resume from suspend.
- **Detection**: fan-curve daemon polls for upower service restarts; trigger is the service becoming active again after a restart.
- **Rule**: Do NOT rely on `charge_control_end_threshold` persisting across upower restarts without the fan-curve daemon running.
- **Confirmed behavior**: sysfs may momentarily show the correct value if the UI slider was moved after the restart — that move both restored the value AND saved it. The daemon write is the silent safety net.

### ❌ FAILED: Per-key brightness slider shown in per-key mode
- Per-key colors encode their own luminance. Showing a global brightness slider that dims all colors uniformly confused users and broke intended color fidelity.
- **Fix**: Brightness slider only shown for `glow` mode. `_apply_per_key()` always passes `brightness=100` to hardware.

### ❌ FAILED: Gaming/themed-effect brightness with large dynamic range
- If tier 4 (rest keys) base RGB is (64,0,0) and brightness=50%, hardware writes (32,0,0) ≈ ~12% luminance — invisible.
- **Fix**: Raise the floor — minimum base for any visible tier should be ≥ 100 per channel. At 50% brightness: 100×0.5=50 (~20% luminance) is dim but visually present.
- **Rule**: For per-key themed effects with tiers, the ratio between highest/lowest tier should be ≤ 3:1. Gaming theme: 255:100 (≈ 2.5:1).

### ❌ FAILED: `set_per_key_colors(composite, brightness)` with slider value in themed modes
- Themed modes (gaming, coding, writing) already bake relative luminance into RGB. Passing the keyboard brightness slider as the brightness arg does NOT scale colors proportionally — it passes the same slider value to the driver's `hw_brightness` parameter which scales uniformly at the hardware level.
- **Fix**: Pass brightness from the keyboard brightness slider directly as the `brightness` arg. But ensure tier base RGBs are high enough that even at lowest slider value (0%), keys still look intentional not broken.

### ✅ WORKING: Per-key app-managed effects — `_APP_MANAGED` guard
- `sync_from_hardware()` must skip sysfs effect read if current effect is in `_APP_MANAGED = {"gaming", "coding", "writing", "per-key", "glow"}`.
- These effects use `set_per_key_colors()` → hardware always reports `"monocolor"` or `"per-key"` in sysfs, never the app-level theme name.
- Without this guard, every sync_from_hardware call would overwrite `effect_var` with `"monocolor"` or `"per-key"`, losing the saved theme on every app open.

---

## TOUCHPAD HARDWARE FACTS (CONFIRMED VIA TESTING)

### Device
- **Touchpad**: UNIW0001, I2C-HID, `/dev/hidraw3` or `/dev/hidraw4` (varies after reboot)
- **HID Feature Report**: Report ID 7, 2 bytes
- **EC sysfs**: `/sys/devices/platform/nuc_wmi/touchpad_enabled` (CTRL_4 bit 6)
- **EC debug**: `/sys/devices/platform/nuc_wmi/debug_ec` (WARNING: read takes ~8 seconds, dumps all registers)

### HID Feature Report Values (Bitmask)
| Value | Bit 1 | Bit 0 | LED | Touchpad Hardware | Notes |
|-------|-------|-------|-----|-------------------|-------|
| 0x00 | 0 | 0 | ON | OFF | Firmware still detects double-tap at hardware level |
| 0x01 | 0 | 1 | OFF | OFF | |
| 0x02 | 1 | 0 | ON | OFF | |
| 0x03 | 1 | 1 | OFF | ON (active) | Normal operating state |

### ✅ WORKING SOLUTION (2026-05-12):
**HID-only architecture — no EC, no gsettings needed.**

1. **Disable touchpad**: Write HID 0x00 → LED ON, touchpad OFF
2. **Enable touchpad**: Write HID 0x03 → LED OFF, touchpad ON
3. **Fn+F7 detection**: dmesg watcher catches "touchpad toggle pressed" → daemon toggles HID
4. **Double-tap detection**: Firmware detects double-tap AT HARDWARE LEVEL even when HID=0x00.
   Firmware changes HID value (0x00→0x03 or 0x03→0x00). HID poller (100ms interval) detects
   the change and syncs daemon state + OSD.
5. **Key insight**: The firmware double-tap mechanism works independently of the digitizer
   power state. It operates at the I2C controller level, not the OS input stack.

### Critical Hardware Behaviors:
1. **HID 0x00**: LED ON, cursor stops. Firmware CAN still detect double-tap and toggle HID back to 0x03.
2. **HID 0x03**: LED OFF, cursor works. Firmware CAN detect double-tap and toggle HID to 0x00.
3. **The LED is directly tied to HID state** — no separate control. LED ON only when HID=0x00 or 0x02.
4. **LED does NOT latch** — pulsing HID 0x00 then 0x03 does NOT keep LED on.
5. **Reading HID (HIDIOCGFEATURE) is safe** — does not change state.
6. **Fn+F7** generates kernel dmesg event "touchpad toggle pressed" AND fires WMI event 0x04 (always "off").
7. **Double-tap** changes HID feature report value (firmware toggles between 0x00 and 0x03).
8. **EC CTRL_4 bit 7 does NOT control LED** — tested with bit 6 cleared, LED stayed off.
9. **EC touchpad_enabled sysfs** does NOT control the LED.
10. **debug_ec read takes ~8 seconds** (dumps 112 registers via WMI). Never use for real-time operations.
11. **Writing same HID value twice** is idempotent (does NOT toggle).

### Approaches Tried & FAILED (DO NOT RETRY):
1. **EC CTRL_4 bit 7 for LED**: Does NOT control LED. Tested clean (bit6=0). No effect.
2. **gsettings-only disable + HID always 0x03**: No LED (LED requires HID 0x00).
3. **HID pulse (0x00 briefly then 0x03)**: LED doesn't latch — turns off when HID goes to 0x03.
4. **EC sysfs (touchpad_enabled) for LED**: EC bit 6 has no effect on LED.
5. **debug_ec read for real-time state**: Takes 8 seconds. Unusable for daemon.
6. **HID-only follower mode (never write HID, only read)**: HID never changes from Fn+F7.
7. **Driver modification for EC bit 7**: Broke keyboard and touchpad completely. Required restore from backup + DKMS reinstall.
8. **HID bitmask 0x01/0x02**: Neither keeps hardware alive with LED on.
9. **Kernel-level hid_hw_raw_request() for touchpad toggle**: returns success but touchpad doesn't resume. **Touchpad HID writes MUST stay in userspace via HIDIOCSFEATURE ioctl.**

---

## GENERAL PROJECT KNOWLEDGE

### Daemon Architecture
- All daemons run as root systemd services
- Communication with app via filesystem (no sockets/dbus)
- State files: `/tmp/` (volatile), `/var/lib/nuc-linux-studio/` (persistent)
- All daemons handle suspend/resume

### Key Service Files
| Service | Source | Binary | Auto-enabled? |
|---------|--------|--------|--------------|
| touchpad-led.service | backend/touchpad_daemon.py | /opt/nuc-linux-studio/backend/touchpad_daemon.py | ✅ Yes |
| kbd-brightness.service | backend/kbd_brightness_daemon.py | /opt/nuc-linux-studio/backend/kbd_brightness_daemon.py | ✅ Yes |
| fan-curve.service | backend/fan_curve_daemon.py | /opt/nuc-linux-studio/backend/fan_curve_daemon.py | ✅ Yes |
| nuc-battery-limit.service | backend/battery_limit_apply.py | /opt/nuc-linux-studio/backend/battery_limit_apply.py | ✅ Yes (oneshot) |
| kbd-audio.service | backend/audio_daemon.py | /opt/nuc-linux-studio/backend/audio_daemon.py | ❌ **On-demand only** |
| nuc-osd (user unit) | backend/osd.py | /opt/nuc-linux-studio/backend/osd.py | ✅ Yes (user unit) |

### kbd-audio.service — On-Demand Lifecycle
- **NEVER auto-started** by install.sh or RPM spec. Unit file is installed but not enabled.
- **Started** by `KeyboardController._start_audio_reactive()` via `systemctl start` (0.5s delayed thread, after checking `is-active`).
- **Stopped** by `KeyboardController._stop_audio_reactive()` via `systemctl stop` (immediately, before USB rebind wait).
- **Self-stops** if `STATE_FILE` mtime is >30s old (app crash watchdog in `audio_daemon.py`).
- **Rule**: Never manually `systemctl enable kbd-audio.service` — it will run forever consuming CPU even when audio mode is off.

### Audio Daemon — GPU Acceleration
- Tries CuPy (CUDA) at startup; falls back to NumPy silently
- GPU path: FFT + band compression + RGB frame built on GPU, single `cp.asnumpy()` transfer per frame
- CPU path: pure NumPy, ~same logic
- `time.sleep(0.016)` = ~60fps target
- Do NOT add UI canvas sync to this daemon — too costly (Tkinter is single-threaded, canvas updates from daemon thread are unsafe)
- **Rejected approach**: shared memory / shm for UI canvas sync — evaluated as ~5-8% CPU for 30fps canvas at 126 keys, not worth it for a lightweight app

### Config File
- Path: `~/.config/nuc_linux_studio/settings.json` (real user home, not root)
- Root config also checked: `/root/.config/nuc_linux_studio/settings.json`
- All tab state serialized via `get_state()` / `load_state()` pattern
- `save_config()` skips during `is_loading=True` to prevent save-during-restore loops

