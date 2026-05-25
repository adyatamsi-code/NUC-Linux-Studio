# NUC Linux Studio — Architecture & Data Flow

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER SPACE                                    │
│                                                                      │
│  ┌──────────────────────┐    ┌─────────────────────────────────────┐ │
│  │  NUC Linux Studio    │    │  Systemd Daemons (root)             │ │
│  │  (Tkinter GUI)       │    │                                     │ │
│  │  runs as ROOT        │    │  kbd-brightness.service              │ │
│  │  via pkexec           │    │    └─ kbd_brightness_daemon.py      │ │
│  │                      │    │                                     │ │
│  │  ui/main.py          │    │  touchpad-led.service               │ │
│  │  ui/tabs/*.py        │    │    └─ touchpad_daemon.py            │ │
│  │  backend/facade.py   │    │                                     │ │
│  │  backend/*.py        │    │  fan-curve.service                  │ │
│  │                      │    │    └─ fan_curve_daemon.py            │ │
│  │                      │    │                                     │ │
│  │                      │    │  kbd-audio.service                   │ │
│  │                      │    │    └─ audio_daemon.py                │ │
│  │                      │    │                                     │ │
│  │                      │    └─────────────────────────────────────┘ │
│  └──────┬───────────────┘                    │                       │
│         │ write_text()                       │ write sysfs / dmesg   │
│         │ read_text()                        │ --follow              │
│─────────┼────────────────────────────────────┼───────────────────────│
│         ▼            KERNEL SPACE            ▼                       │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐   │
│  │  ite8291r3.ko        │    │  nuc_wmi.ko                      │   │
│  │  USB LED driver      │    │  WMI/ACPI platform driver         │   │
│  │                      │    │                                    │   │
│  │  sysfs:              │    │  sysfs:                            │   │
│  │  /sys/class/leds/    │    │  /sys/devices/platform/nuc_wmi/   │   │
│  │  ite8291r3::         │    │    fn_lock                         │   │
│  │  kbd_backlight/      │    │    super_key_lock                  │   │
│  │    brightness        │    │    touchpad_enabled                │   │
│  │    color             │    │    pm_profile                      │   │
│  │    effect            │    │    hwmon/hwmonN/                    │   │
│  │    key_colors        │    │                                    │   │
│  └──────┬───────────────┘    │  events → dmesg:                   │   │
│         │ USB control msgs   │    "keyboard backlight changed"    │   │
│         │ USB interrupt EP   │    "touchpad toggle pressed"       │   │
│─────────┼────────────────────┼────────────────────────────────────│   │
│         ▼      HARDWARE      ▼                                       │
│  ┌──────────────┐    ┌────────────────────────────────┐             │
│  │ ITE8291R3    │    │ Embedded Controller (EC)        │             │
│  │ USB 048D:    │    │ via WMI GUID 0x70/71/72         │             │
│  │ 6004/6006/   │    │                                  │             │
│  │ CE00         │    │ Fans, battery, power profile,    │             │
│  │              │    │ lightbar, Fn keys, touchpad      │             │
│  │ 6×21 LED     │    │                                  │             │
│  │ grid         │    └────────────────────────────────┘             │
│  └──────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory

### Driver Layer (`driver/`)

| File | Purpose | Loaded By |
|------|---------|-----------|
| `main.c` | nuc_wmi entry point — registers WMI driver, initializes submodules | DKMS/modprobe |
| `events.c` | WMI event handler — emits `pr_info("keyboard backlight changed")` and `pr_info("touchpad toggle pressed")` on Fn key events | WMI notify callback |
| `ite8291r3.c` | USB LED class driver for ITE8291R3 keyboard backlight controller | USB probe on VID 048D |
| `ec.c/h` | EC register read/write via `outb/inb` ports 0x66/0x62 | Platform driver |
| `fan.c/h` | EC-based fan speed read/write | nuc_wmi sysfs |
| `battery.c/h` | EC battery charge limit (start/end threshold) | nuc_wmi sysfs |
| `hwmon.c/h`, `hwmon_fan.c/h`, `hwmon_pwm.c/h` | hwmon interface for fan RPM and PWM | hwmon subsystem |
| `led_lightbar.c/h` | Multicolor LED for chassis lightbar | LED subsystem |
| `pdev.c/h` | Platform device registration | Module init |
| `misc.c/h` | Fn lock, super key lock, touchpad toggle sysfs | Platform sysfs |
| `features.c/h` | Feature detection (which features this chassis supports) | Module init |
| `debugfs.c/h` | EC register debug interface | debugfs |
| `dkms.conf` | DKMS config — builds nuc_wmi.ko + ite8291r3.ko | DKMS |
| `99-ite8291r3.rules` | udev rules — auto-bind ite8291r3 to USB interface 1.1, chmod 0666 on sysfs | udevd |

### Backend Layer (`backend/`)

| File | Purpose | Invoked By |
|------|---------|-----------|
| `facade.py` | `UniwillBackend` — unified API aggregating all controllers | UI `NUCApp.__init__()` |
| `keyboard.py` | `KeyboardController` — sysfs LED control + per-key RGB via `KEY_GRID_MAP`; `LightbarController`; `StatusLedController` | Facade |
| `fans.py` | `FanController` — hwmon fan speed, PWM control | Facade |
| `battery.py` | `BatteryController` — charge limit, battery info | Facade |
| `power.py` | `PowerController` — CPU energy preference, power profiles | Facade |
| `core.py` | `read_text()`, `write_text()`, `write_multiple()`, `batch_writes()` — sysfs I/O helpers | All controllers |
| `kbd_brightness_daemon.py` | Keyboard brightness observe-only handler + per-key restore on resume; syncs sysfs brightness to state files (does NOT write brightness on Fn+F8 — GNOME `gsd-power` handles that) | systemd `kbd-brightness.service` |
| `touchpad_daemon.py` | Touchpad toggle Fn+F7 handler via HID feature reports; state-change-only (no polling loop) | systemd `touchpad-led.service` |
| `fan_curve_daemon.py` | Reads fan curve state from JSON, interpolates temp→PWM, writes only on value change; releases to EC when disabled | systemd `fan-curve.service` |
| `audio_daemon.py` | Audio visualization daemon for per-key RGB effects synced to system audio | systemd `kbd-audio.service` |

### UI Layer (`ui/`)

| File | Purpose |
|------|---------|
| `main.py` | App entry point — pkexec elevation, config load/save, tab management |
| `utils.py` | `KEY_LAYOUT` (6 rows × 11-16 keys), `FN_KEY_SYMBOLS`, `DEFAULT_COLOR`, color helpers |
| `tabs/keyboard.py` | Per-key RGB canvas, effects, brightness display |
| `tabs/lightbar.py` | Chassis lightbar color/effect control |
| `tabs/battery.py` | Battery info, charge limit slider |
| `tabs/power.py` | Power profile selector (Silent/Balanced/Performance); fan curve editor persists state to JSON for fan-curve daemon |
| `tabs/face_unlock.py` | Howdy face authentication management |
| `tabs/toggles.py` | Fn Lock, Super Key Lock, Touchpad toggle, daemon service controls |

### Config & State Files

| Path | Format | Written By | Read By |
|------|--------|-----------|---------|
| `~/.config/nuc_linux_studio/settings.json` | JSON | App (`save_config`) | App + Daemon (via glob) |
| `/tmp/nuc_kbd_brightness` | Plain text (percent) | Kbd daemon | App (UI polling every 1s) |
| `/var/lib/nuc-linux-studio/kbd_brightness` | Plain text (percent) | Kbd daemon | Kbd daemon (persistent, survives reboot) |
| `/tmp/nuc_touchpad_state` | Plain text (0/1) | Touchpad daemon | App (KeyboardController) |
| `/var/lib/nuc-linux-studio/touchpad_state` | Plain text (0/1) | Touchpad daemon | Touchpad daemon (persistent) |
| `/var/lib/nuc-linux-studio/fan_curve_state.json` | JSON | App (Power tab) | Fan curve daemon (persistent) |
| `/tmp/nuc_fan_curve_state.json` | JSON | App (Power tab) | Fan curve daemon (fallback) |
| `/tmp/.nuc_studio_gnome_kbd_backup` | JSON | App (pre-pkexec) | App (on exit, as root) |
| `/tmp/.nuc_studio_env_<PID>` | KEY=VALUE | App (pre-pkexec) | App (post-pkexec) |

---

## 3. Data Flow: Per-Key RGB Colors

### 3A. App Apply Path (user clicks "Apply")

```
User clicks "Apply" in Keyboard Tab
         │
         ▼
KeyboardTab._apply_per_key()
  │  Iterates self.keyboard_colors: {"ESC": "#ff0000", "F1": "#00ffff", ...}
  │  For each key:
  │    COLOR != DEFAULT_COLOR → composite[key] = (r, g, b)
  │    COLOR == DEFAULT_COLOR → composite[key] = (0, 0, 0)      ← ALL keys sent
  │
  ▼
backend.set_per_key_colors(composite, brightness)
         │
         ▼
KeyboardController.set_per_key_colors(key_colors, brightness)
  │  For each key_name in key_colors:
  │    grid_pos = KEY_GRID_MAP[key_name]    e.g. "ESC" → (5, 0)
  │    color_map[(5, 0)] = (255, 0, 0)
  │    Also adds WIDE_KEY_EXTRA_COLS positions (e.g. TAB → (3,1))
  │
  │  IF kernel_driver (sysfs):
  │    Builds string: "5 0 255 0 0 4 0 0 0 0 ..."
  │    write_text(/sys/class/leds/ite8291r3::kbd_backlight/key_colors, string)
  │
  ▼
ite8291r3.c: key_colors_store()
  │  1. memset ALL 6 row buffers to 0          ← CLEARS EVERYTHING
  │  2. Parses "row col r g b" tuples
  │  3. Sets row_data[row][RED_OFFSET + col] etc.
  │  4. Calls enable_user_mode(brightness, save=1)
  │  5. For each row 0-5: set_row_index(row) + send_row(row) via USB
  │
  ▼
ITE8291R3 USB controller updates physical LEDs
```

**Key observation**: The app sends ALL keys (colored + black) so the entire grid is defined. No LEDs are left in a stale state.

### 3B. Daemon Restore Path (boot / resume / Fn+F8 from off)

```
Daemon starts OR resume detected OR brightness changes from 0→non-zero
         │
         ▼
set_brightness(hw_value)
  │  Writes hw_value to sysfs brightness
  │  IF hw_value > 0: calls _ensure_effect_on()
  │
  ▼
_ensure_effect_on()
  │  Reads saved_effect from config glob "/home/*/.config/nuc_linux_studio/settings.json"
  │
  │  IF saved_effect == "per-key":
  │    calls _restore_per_key_from_config(config_path)
  │  ELIF current sysfs effect == "off":
  │    Reads first non-default color from config → writes to sysfs color
  │    Writes "monocolor" to sysfs effect
  │
  ▼
_restore_per_key_from_config(config_path)
  │  Reads settings.json
  │  _migrate_key_names() — normalizes old mixed-case names
  │  For each key with color NOT in (#1a1a1a, #262D33):
  │    grid_pos = KEY_GRID_MAP[key_name]
  │    Builds "row col r g b" string
  │    Also adds WIDE_KEY_EXTRA_COLS
  │  Writes result to sysfs key_colors
  │
  ▼
ite8291r3.c: key_colors_store()     ← same as app path
  │  1. memset ALL row buffers to 0  ← CLEARS EVERYTHING
  │  2. Only colored keys are written (unset keys stay 0,0,0)
```

### ⚠️ CRITICAL DIFFERENCE: App vs Daemon

| Aspect | App Path | Daemon Path |
|--------|----------|-------------|
| Keys sent | ALL keys (colored + black) | ONLY non-default colored keys |
| Unset keys after write | Explicitly (0,0,0) | Implicitly (0,0,0) via memset |
| Effect result | **IDENTICAL** | **IDENTICAL** |
| Config read | In-process `self.keyboard_colors` | File read from disk via glob |
| KEY_GRID_MAP source | In-process class attribute | Runtime import from same class |

**The results should be identical.** Both paths produce the same grid state because the driver memsets all rows to zero before parsing.

---

## 4. Startup & Lifecycle Sequences

### 4A. System Boot

```
1. systemd loads nuc_wmi.ko (via WMI GUID module alias in modprobe)
2. nuc_wmi initializes: pdev → events → hwmon → battery → lightbar → debugfs
3. Events submodule registers WMI notify handler + i8042 filter
4. systemd/udev loads ite8291r3.ko
5. ite8291r3 USB probe runs on VID 048D interface 1
   └─ Creates /sys/class/leds/ite8291r3::kbd_backlight/
6. udev rule 99-ite8291r3.rules fires:
   └─ Tries "echo $kernel:1.1 > /sys/bus/usb/drivers/ite8291r3/bind"
   └─ chmod 0666 on brightness/color/effect/key_colors
7. kbd-brightness.service starts (After=multi-user.target)
   └─ Reads config from /home/*/.config/nuc_linux_studio/settings.json
   └─ set_brightness(saved_level) → _ensure_effect_on()
       └─ IF per-key mode: _restore_per_key_from_config()      ← ⚠️ HERE
       └─ IF monocolor: writes color + sets effect=monocolor
   └─ Starts dmesg --follow thread
8. touchpad-led.service starts
   └─ Finds UNIW0001 hidraw device
   └─ Watches dmesg for "touchpad toggle pressed"
```

### 4B. App Launch (user clicks desktop icon or runs `nuc-studio`)

```
1. /usr/local/bin/nuc-studio bash script:
   └─ Detects DISPLAY/WAYLAND/XAUTHORITY env
   └─ exec python3 /opt/nuc-linux-studio/ui/main.py

2. ui/main.py: main()
   └─ IF not root (euid != 0):
       a. _disable_gnome_kbd_keys()    ← runs as USER (has dbus access)
       b. Saves display env to /tmp/.nuc_studio_env_<PID>
       c. os.execvp("pkexec", [..., "--env-file", env_path])
                                        ← ⚠️ PROCESS REPLACES ITSELF
                                        ← polkit dialog appears
                                        ← during dialog: no app process running
                                        ← LED state controlled only by daemon

   └─ IF root (after pkexec):
       a. Reads --env-file, sets DISPLAY/WAYLAND env
       b. Creates Tk root window
       c. NUCApp.__init__():
          - UniwillBackend() → all controllers init
          - Creates tabs (Keyboard + Power eagerly, others lazy)
          - load_config() → settings.json
            └─ KeyboardTab.load_state(data)
               └─ Sets self.keyboard_colors from config
               └─ Calls apply_settings()
                  └─ IF per-key mode: just saves config, returns
                     ⚠️ DOES NOT auto-apply per-key colors to hardware!
                  └─ IF monocolor/effect: applies to hardware
```

### 4C. pkexec Password Prompt — LED Blackout Issue

```
TIMELINE:

t=0:  User runs nuc-studio
t=0:  main() runs as user, disables GNOME kbd keys
t=0:  os.execvp("pkexec", ...) — original process DIES
t=0:  pkexec spawns, shows polkit authentication dialog

      ┌─────────────────────────────────────────────────────┐
      │  DURING THIS WINDOW (t=0 to t=password_entered):   │
      │                                                     │
      │  • No NUC Studio app process exists                 │
      │  • Daemon is running and owns the LED state         │
      │  • pkexec may trigger USB device permission reset?  │  ← INVESTIGATE
      │  • logind session change may affect USB devices?    │  ← INVESTIGATE
      │  • The ITE8291R3 may lose its programmed state if:  │
      │    - USB device gets unbound/rebound                │   │
      │    - Driver gets reloaded                           │   │
      │    - polkit spawns a process that touches the LED   │
      │                                                     │
      │  OBSERVED: LEDs turn off at the exact moment        │
      │            the password prompt appears               │
      └─────────────────────────────────────────────────────┘

t=N:  User enters password
t=N:  pkexec launches nuc-studio as root
t=N:  App loads config but does NOT auto-apply per-key colors
      (because apply_settings() for per-key just saves config)
t=N:  User must click "Apply" manually to restore colors

      RESULT: LEDs stay off/wrong until user clicks Apply
```

### 4D. Suspend / Resume

```
SUSPEND:
  1. System suspends → USB devices power down → ITE8291R3 loses all state
  
RESUME:
  1. USB re-enumerates → ite8291r3 driver re-probes
  2. udev rule fires → chmod 0666
  3. Daemon (still running) detects resume via suspend_stats counter change
  4. Waits 2 seconds
  5. _restore_keyboard_on_resume()
     └─ Waits up to 10s for sysfs LED to appear
     └─ set_brightness(current_level)
        └─ _ensure_effect_on()  → restores per-key or monocolor from config
  
  6. App (if running) detects resume via timer drift (30s check)
     └─ load_config(restore_power_profile=False)
        └─ KeyboardTab.load_state() → apply_settings()
           └─ per-key mode: does NOT auto-apply colors ← ⚠️ SAME ISSUE
```

---

## 5. Known Issues — Root Cause Analysis

### Issue 1: Wrong colors after daemon restore (boot/driver reload)

**Symptom**: After install script rebuilds the driver, hardware shows wrong/no colors. Opening the app and clicking "Apply" fixes it.

**Root Cause Chain**:
1. `install.sh` runs `dkms remove` → unloads old `ite8291r3.ko` → LEDs go dark
2. `install.sh` runs `dkms install` → loads new `ite8291r3.ko` → LED sysfs appears
3. `install.sh` restarts `kbd-brightness.service`
4. Daemon starts, reads config, calls `set_brightness()` → `_ensure_effect_on()`
5. `_ensure_effect_on()` reads `sysfs effect` → it's `"off"` (fresh driver load)
6. **IF saved_effect == "per-key"**: calls `_restore_per_key_from_config()` ✓
7. **IF saved_effect != "per-key"** (or config doesn't have it): falls into the `elif current == "off"` branch → writes monocolor, not per-key ✗

**Also**: The daemon previously didn't skip `#262D33` (DEFAULT_COLOR) properly — **FIXED** in latest commit.

**Remaining concern**: If the user's saved effect is NOT "per-key" but they had per-key colors set before the rebuild, the daemon restores monocolor instead.

### Issue 2: LEDs turn off when pkexec password prompt appears

**Symptom**: At the exact moment the polkit dialog pops up, keyboard LEDs go dark.

**Possible Causes** (ranked by likelihood):

1. **`_disable_gnome_kbd_keys()` side effect** — Before pkexec, the app calls `gsettings set ... []` to disable GNOME keyboard brightness keys. GNOME's settings daemon may react to this by sending a "turn off keyboard backlight" command to the hardware. Since GNOME may also be writing to `/sys/class/leds/ite8291r3::kbd_backlight/brightness`, setting brightness keys to empty could trigger GNOME to set brightness=0.

2. **logind session switch** — pkexec may create a transition from the user's graphical session context. logind might revoke or reset device permissions during the polkit authentication flow.

3. **USB device rebind** — If pkexec or polkit triggers any kind of USB permission reset, the ite8291r3 device could get unbound and rebound, which would reset its state.

4. **GNOME settings daemon interference** — GNOME's `gsd-power` or `gsd-media-keys` daemon may actively manage keyboard backlights and set brightness=0 when it loses track of the key bindings.

**Investigation steps**:
```bash
# During the pkexec prompt, check if brightness was changed:
cat /sys/class/leds/ite8291r3::kbd_backlight/brightness

# Check dmesg for USB rebind events:
dmesg | tail -20

# Check if GNOME's settings daemon is writing to sysfs:
inotifywait -m /sys/class/leds/ite8291r3::kbd_backlight/brightness
```

### Issue 3: App does NOT auto-apply per-key colors on startup

**Symptom**: After launching the app, per-key colors show correctly in the UI canvas but are NOT sent to hardware until user clicks "Apply".

**Root Cause**: In `KeyboardTab.load_state()` → `apply_settings()`:
```python
if effect == "per-key":
    if not getattr(self.app, 'is_loading', False):
        self.app.save_config()
    return  # ← RETURNS WITHOUT SENDING TO HARDWARE
```

The per-key mode deliberately doesn't auto-apply because the user might want to modify colors before sending. But this means:
- After resume, per-key colors are only restored by the DAEMON
- If the daemon fails or hasn't run yet, LEDs stay dark

**Suggested fix**: Auto-apply per-key colors during `load_state()` if `is_loading` is True (i.e., initial startup), or have the daemon more reliably handle it.

### Issue 4: Config access as root daemon

**Symptom**: Daemon may fail to find config file in edge cases.

**Root Cause**: Daemon uses `glob("/home/*/.config/nuc_linux_studio/settings.json")` which:
- Fails if home directory is encrypted (ecryptfs)
- Fails if config doesn't exist yet (first boot before app ever ran)
- Could pick wrong user's config on multi-user systems

---

## 6. IPC Between App and Daemons

```
┌──────────┐   /tmp/nuc_kbd_brightness   ┌──────────────────┐
│   App    │◄────── polls every 1s ──────│ kbd-brightness    │
│  (UI)    │                              │    daemon         │
│          │   ~/.config/.../settings.json│  (observe-only)   │
│          │──── writes on save ─────────►│ reads via glob    │
│          │                              │ on startup/resume │
│          │                              │                   │
│          │  /var/lib/.../kbd_brightness │ persistent state  │
│          │                              │ survives reboot   │
└──────────┘                              └──────────────────┘

┌──────────┐   /tmp/nuc_touchpad_state   ┌──────────────────┐
│   App    │◄────── reads on demand ─────│ touchpad-led      │
│  (UI)    │                              │    daemon         │
└──────────┘                              └──────────────────┘

┌──────────┐  fan_curve_state.json       ┌──────────────────┐
│   App    │──── writes on curve ────────►│ fan-curve         │
│ (Power)  │     change / profile        │    daemon         │
│          │     switch                   │ reads JSON, sets  │
│          │                              │ PWM via hwmon     │
└──────────┘                              └──────────────────┘

┌──────────┐  /tmp/nuc_audio_state       ┌──────────────────┐
│   App    │◄────── reads on demand ─────│ kbd-audio         │
│  (UI)    │                              │    daemon         │
└──────────┘                              └──────────────────┘

No direct IPC (no sockets, no dbus, no signals).
All communication is via filesystem polling.

Keyboard brightness: GNOME gsd-power handles Fn+F8 toggle
(writes to sysfs). Daemon observes sysfs changes and syncs
state files. Daemon does NOT write brightness on toggle events.
```

---

## 7. ITE8291R3 Grid Layout (KEY_GRID_MAP)

The ITE8291R3 USB controller uses a 6×21 LED grid. Hardware rows are inverted relative to physical layout:

```
HW Row 5 = Physical top:    ESC  F1  F2  F3  F4  F5  F6  F7  F8  F9 F10 F11 F12  INS SCRLK DEL
HW Row 4 = Number row:       `   1   2   3   4   5   6   7   8   9   0   -   =  BKSP  HOME
HW Row 3 = QWERTY:          TAB  .  Q   W   E   R   T   Y   U   I   O   P   [   ]   \   PGUP
HW Row 2 = ASDF:           CAPS  .  A   S   D   F   G   H   J   K   L   ;   '   .  ENT  PGDN
HW Row 1 = ZXCV:            . SHFT .  Z   X   C   V   B   N   M   ,   .   / SHFT  ↑   END
HW Row 0 = Bottom:         CTRL .  FN WIN ALT  .  .  SPC .  .  ALT MNU CTRL  ←   ↓    →

(dots represent wide key extra columns)
```

Wide keys occupy multiple LED columns — the `WIDE_KEY_EXTRA_COLS` dict maps these.

---

## 8. File Dependency Graph

```
install.sh
  ├─ driver/*.c, *.h, Makefile, dkms.conf → /usr/src/nuc_wmi-1.0/ → DKMS
  ├─ driver/99-ite8291r3.rules → /etc/udev/rules.d/
  ├─ ui/, backend/ → /opt/nuc-linux-studio/
  ├─ Creates kbd-brightness.service → /usr/lib/systemd/system/
  ├─ Creates touchpad-led.service → /usr/lib/systemd/system/
  ├─ Creates fan-curve.service → /usr/lib/systemd/system/
  ├─ Creates kbd-audio.service → /usr/lib/systemd/system/
  ├─ Creates /usr/local/bin/nuc-studio launcher
  └─ Creates polkit policy → /usr/share/polkit-1/actions/

/usr/local/bin/nuc-studio (bash)
  └─ exec python3 /opt/nuc-linux-studio/ui/main.py

ui/main.py
  ├─ imports ui/tabs/*.py (via ui/__init__.py)
  ├─ imports backend/facade.py (via backend/__init__.py)
  └─ reads/writes ~/.config/nuc_linux_studio/settings.json

backend/facade.py
  ├─ imports backend/keyboard.py (KeyboardController, LightbarController)
  ├─ imports backend/fans.py
  ├─ imports backend/battery.py
  └─ imports backend/power.py

backend/kbd_brightness_daemon.py (standalone, run by systemd)
  ├─ imports backend/keyboard.py at runtime (for KEY_GRID_MAP)
  └─ reads ~/.config/nuc_linux_studio/settings.json (via glob)

backend/audio_daemon.py (standalone, run by systemd)
  ├─ imports backend/keyboard.py at runtime (for KEY_GRID_MAP)
  └─ reads ~/.config/nuc_linux_studio/settings.json (via glob)
```

---

## 9. Power Profile & Manual/Automatic Mode

### EC Manual Mode vs Automatic Mode

The EC has two operating modes controlled by `CTRL_1_ADDR` bit 0 (`manual_control` sysfs):

- **Automatic mode** (`manual_control=0`): The EC controls fan speeds based on its built-in thermal curves for the current profile. The physical profile button works normally — pressing it cycles the profile AND updates the button LEDs. The EC owns register `0x0751`.

- **Manual mode** (`manual_control=1`): The fan-curve daemon takes over fan control via hwmon PWM writes. The EC cedes control. Register `0x0751` has profile bits preserved by `PERF_PROFILE_MASK` in fan.c, but the register is shared state.

### EC Register 0x0751 (PERF_PROFILE_ADDR / FAN_CTRL_ADDR)

This is a **shared register** used for BOTH profile identification AND fan control:
- Bits 7,5 (`0xb0` mask = `PERF_PROFILE_MASK`): Profile identity
  - `0xa0` = Silent (bits 7+5)
  - `0x00` = Balanced (cleared)  
  - `0x10` = Performance (bit 4)
- Lower bits: fan mode control (manual, boost, etc.)
- `fan.c` reads this register and preserves profile bits when writing fan mode changes

### Observed EC Behavior — Experimental Results (May 2026)

#### What works:
- **Button LEDs always update** when manual mode is cleared, regardless of whether we write profile bits
- **EC cycles the profile internally** on button press, independent of manual mode
- **Initial profile read** works: temporarily clear manual mode → read 0x0751 → restore manual mode (done at driver load in `nuc_wmi_pdev_setup`)

#### What does NOT work (causes double-cycling):
- ❌ Clearing manual mode in the WMI event handler (immediate context) + the deferred work clearing it again
- ❌ Writing profile bits to 0x0751 at the same time as handling a button press — the EC sees BOTH our write and its own queued button press
- ❌ Clearing manual mode in the event handler causes the EC to re-process the button press → skips a profile

#### What does NOT work (stale reads):
- ❌ Reading 0x0751 within 350ms of clearing manual mode — returns **stale/previous** profile
- ❌ Reading 0x0751 while manual mode is ON — returns corrupted data (fan mode bits mixed in)

#### Timing observations:
```
Button Press Timeline:
  t=0      EC fires WMI event 176
  t=0      Driver event handler runs
  t=+300ms Deferred work clears manual mode
  t=+350ms Read 0x0751 → STALE (shows previous profile)
  t=+500ms Read 0x0751 → SOMETIMES correct (500ms deferred readback)
  t=+2000ms Fan daemon re-enables manual mode
```

The EC register 0x0751 takes **a variable amount of time** to reflect the new profile after manual mode is cleared. Reads at 350ms are consistently stale. Reads at 500ms are sometimes correct. The reliable window is unknown.

#### Actual EC readback data (from dmesg):
```
# 500ms deferred readback (second approach):
Press 1: EC 0x0751 = 0x50 → Performance(2) — correct, LEDs matched
Press 2: EC 0x0751 = 0xe0 → Silent(0) — correct, LEDs matched
Press 3: EC 0x0751 = 0x40 → Balanced(1) — correct, LEDs matched
Press 4: EC 0x0751 = 0xe0 → Silent(0) — wrong? (should be Performance)

# 350ms deferred readback (current approach):
Press 1: EC 0x0751 = 0xe0 → Silent(0) — STALE (LEDs showed new profile)
Press 2: EC 0x0751 = 0xe0 → Silent(0) — STALE
Press 3: EC 0x0751 = 0xe0 → Silent(0) — STALE  
Press 4: EC 0x0751 = 0x40 → Balanced(1) — finally caught up (1 behind)
Press 5: EC 0x0751 = 0x50 → Performance(2) — caught up
```

Conclusion: The EC register lags behind the actual LED state by 1-3 presses at 350ms read timing. At 500ms it's better but still occasionally stale.

#### Software tracking issues:
- Computing `next` profile in software gets out of sync with EC because:
  1. The **initial profile read on driver load may be wrong** (the brief manual-mode-clear-and-restore window gives an unreliable read)
  2. Accumulated timing/race drift over multiple presses
  3. The EC's internal starting point after manual mode operations is unpredictable

### Current State of the Problem (UNSOLVED)

**Core conflict:**
1. LEDs only update when manual mode is OFF
2. Manual mode must be ON for custom fan curves (fan daemon)
3. Clearing manual mode during/near a button press causes double-cycling
4. The EC register 0x0751 is unreliable for reading the profile (stale reads)
5. Software tracking gets out of sync with the EC

**What needs to happen:**
- Button press → LEDs cycle correctly (one step per press)
- App reads the correct profile matching the LEDs
- Fan daemon applies the correct curve for the active profile
- No double-cycling, no stale reads, no desync

### Approaches Tried (all partially failed)

| # | Approach | Result |
|---|----------|--------|
| 1 | Clear manual + write profile bits in event handler | ❌ Double-cycling (EC sees write + its own press) |
| 2 | Clear manual only in event handler (no profile write) + software tracking | ❌ Double-cycling still (clearing manual during event = EC reprocesses) |
| 3 | Software tracking only (no EC writes at all) | ❌ LEDs stuck (EC can't update LEDs while manual mode is on) |
| 4 | No EC writes in handler + deferred (300ms) clear manual + deferred write profile bits | ❌ Double-cycling (writing profile bits even deferred causes desync) |
| 5 | No EC writes in handler + deferred (300ms) clear manual only (no profile write) + software tracking | ❌ Software tracking out of sync (initial value wrong, accumulated drift) |
| 6 | No EC writes in handler + deferred (300ms) clear manual + read back 0x0751 | ❌ Stale reads at 350ms — register lags 1-3 presses behind LEDs |
| 7 | **CTRL_3 (0x07A5) read + deferred manual clear** | ✅ **IMPLEMENTED** — see below |

### Solution #7: CTRL_3 Power LED Register (IMPLEMENTED)

#### Discovery
Register `CTRL_3_ADDR` (0x07A5) bits 0-1 mirror the **physical power button LED state** and
are **always readable**, even with manual mode ON. Unlike register 0x0751 which gives stale
or corrupted reads, CTRL_3 reflects the actual profile instantly after a button press.

#### CTRL_3 Properties (experimentally verified)
- **Readable in manual mode**: ✅ Yes — returns correct LED state regardless of `CTRL_1_MANUAL_MODE`
- **Writable**: ❌ No — EC immediately overwrites back to the actual state. Read-only in practice.
- **Updates on button press**: ✅ Yes — EC updates CTRL_3 atomically with the LED hardware
- **No interference with keyboard/fan**: ✅ We only READ this register, never write it

#### CTRL_3 Bit Mapping
```
CTRL_3_ADDR = 0x07A5
Bits 0-1 (CTRL_3_PWR_LED_MASK):
  0x00 (CTRL_3_PWR_LED_LEFT) = 1 LED lit  = Balanced (profile 1)
  0x01 (CTRL_3_PWR_LED_BOTH) = 2 LEDs lit = Performance (profile 2)
  0x02 (CTRL_3_PWR_LED_NONE) = 0 LEDs lit = Silent (profile 0)

Other bits (NOT touched by our code):
  Bit 2: CTRL_3_FAN_QUIET
  Bit 4: CTRL_3_OVERBOOST
  Bit 7: CTRL_3_HIGH_PWR
```

#### Implementation

```
Button Press Flow:
  t=0      EC internally cycles profile + updates LEDs + updates CTRL_3
  t=0      EC fires WMI event 176
  t=0      nuc_wmi_cycle_perf_profile():
             - No EC writes (avoids double-cycling)
             - Schedules deferred work at 300ms
  t=300ms  Deferred work:
             - Clears CTRL_1_MANUAL_MODE (so EC refreshes LED hardware)
             - sysfs_notify("pm_profile") — wakes up pollers
  t=anytime  App reads pm_profile:
             - nuc_wmi_read_perf_profile_from_ec()
             - Reads CTRL_3 bits 0-1
             - Returns matching profile index (always accurate)
  t=~2.3s  Fan daemon re-enables manual mode
```

**Files modified:**
- `driver/pdev.c`:
  - `nuc_wmi_read_perf_profile_from_ec()` → reads CTRL_3 instead of software variable
  - `nuc_wmi_cycle_perf_profile()` → no EC writes, deferred manual-mode clear only
  - `nuc_wmi_pdev_setup()` → initial profile from CTRL_3 instead of temp clear+read 0x0751
- `ui/tabs/power.py`: poll interval 5s → 2s for snappier response

**Registers touched and safety:**
| Register | Action | When | Safe? |
|----------|--------|------|-------|
| CTRL_3 (0x07A5) | READ only | Every pm_profile poll | ✅ Read-only, no side effects |
| CTRL_1 (0x0741) | CLEAR bit 0 | 300ms after button press | ✅ Same as before, fan daemon restores |
| PERF_PROFILE (0x0751) | WRITE | Only on app sysfs write (benchmark) | ✅ Not on button press |
| CTRL_3 other bits | NOT TOUCHED | Never | ✅ Fan quiet, overboost, high power preserved |

**Why this doesn't interfere with keyboard illumination:**
- Keyboard is controlled by ITE8291R3 USB chip (completely separate from EC)
- The previous illumination bug was caused by destructively overwriting 0x0751 (clobbering fan bits)
- We do NOT write to 0x0751 on button press anymore
- We do NOT write to CTRL_3 at all (only read)
- The only EC write on button press is clearing CTRL_1 bit 0 (deferred), which has no effect on keyboard

## 10. Touchpad Toggle — LED Semantics & State Management

### Hardware LED Semantics (CRITICAL)

The touchpad LED indicator has **inverted semantics** relative to touchpad state:

| Touchpad State | LED State | HID Report Value |
|---|---|---|
| **Enabled** (touchpad works) | **LED OFF** (dark) | `0x03` |
| **Disabled** (touchpad blocked) | **LED ON** (white light) | `0x00` |

**Rule: LED ON = touchpad DISABLED. LED OFF = touchpad ENABLED.**

This is the hardware convention set by the UNIW0001 HID device and cannot be changed.

### State Management

The touchpad state is managed by a **single local boolean** (`current_state`) in the daemon:

- `current_state = True` → touchpad enabled, LED off, gsettings `send-events=enabled`
- `current_state = False` → touchpad disabled, LED on, gsettings `send-events=disabled`

### State Sources (priority order)

1. **Persistent state file** (`/var/lib/nuc-linux-studio/touchpad_state`): Read on daemon startup. Survives reboot.
2. **Tmp state file** (`/tmp/nuc_touchpad_state`): Written on every toggle. Read by the app UI for status display.
3. **In-memory `current_state`**: The authoritative runtime state. Toggled on Fn+F7.

### ⚠️ DO NOT read EC sysfs (`touchpad_enabled`) for state

The EC register `touchpad_enabled` is **unreliable** because:
- The HID feature report (`0x03`/`0x00`) sent to control the LED also **resets the EC register**
- This creates a feedback loop: daemon reads EC → acts on value → HID report resets EC → next read returns wrong value
- The EC toggles its own register on Fn+F7 press independently of the daemon

### Toggle Flow (Fn+F7)

```
Fn+F7 pressed
  │
  ▼
EC fires WMI event → dmesg: "touchpad toggle pressed"
  │
  ▼
Daemon _dmesg_reader detects event (debounced 0.5s)
  │
  ▼
current_state = NOT current_state    ← simple flip, no EC/file reads
  │
  ▼
set_touchpad_led(current_state)
  ├─ Write state files (/tmp + /var/lib)
  ├─ gsettings set ... send-events enabled/disabled
  └─ HID Feature Report: 0x03 (LED off) or 0x00 (LED on)
  │
  ▼
show_touchpad_osd(current_state)
  └─ GNOME Shell OSD icon: input-touchpad-symbolic / touchpad-disabled-symbolic
```

### App UI Toggle Flow

```
User clicks checkbox in Toggles tab
  │
  ▼
apply_touchpad_toggle()
  │
  ▼
backend.set_touchpad_toggle_state(enabled)
  │
  ▼
keyboard.py calls set_touchpad_led(enabled) from touchpad_daemon module
  ├─ Write state files
  ├─ gsettings set ... send-events
  └─ HID Feature Report
```

**Note**: When the app toggles the touchpad, the daemon's in-memory `current_state` is NOT updated (different process). On the next Fn+F7 press, the daemon flips its stale `current_state`. This can cause a one-press desync. The workaround is that the daemon always writes to state files, so consecutive toggles self-correct.

## 11. EC Temperature Reading Race Condition

### Problem
Occasional spurious temperature readings of 165°C on dGPU (temp2_input). This exceeds the thermal shutdown threshold and is physically impossible during normal operation.

### Root Cause
The EC updates temperature registers asynchronously. When the kernel reads `temp2_input` via the hwmon sysfs interface, it issues an EC read command. If the EC is in the middle of updating its internal temperature register, a partial/stale byte can be returned. This produces values like 165000 mC (0x28 0x5A8 in some byte-swap scenarios).

### Fix
- **Backend (`fans.py`)**: Rejects any temperature reading >150000 mC or <0 mC, substituting 0.
- **UI (`power.py`)**: Clamps display to 0-120°C range as a secondary safety net.

### Impact
No thermal control impact — the fan curve daemon reads temperatures independently and has its own safety logic. The spurious readings were display-only artifacts.

## 11. Keyboard Brightness & Screen Idle Dim

### Problem
When the screen dims due to idle timeout (GNOME `gsd-power`), the keyboard backlight turns off and doesn't come back when the screen un-dims.

### Root Cause
`gsd-power` writes `0` to `/sys/class/leds/ite8291r3::kbd_backlight/brightness` during idle dim. The kbd-brightness daemon's periodic sysfs poll (`_sync_brightness_from_sysfs()`) observed this change and updated its internal `current_index` to 0 (Off). When the screen un-dimmed, `gsd-power` restored some brightness value, but the daemon had already lost the user's chosen level.

### Fix
The daemon now distinguishes between user-initiated brightness changes (via Fn+F8 dmesg events) and external changes (via sysfs poll). When brightness drops to 0 without a corresponding dmesg event, the daemon:
1. Does NOT update `current_index`
2. Sets `_idle_dimmed = True`
3. When sysfs brightness returns >0, re-applies the saved brightness level and effect

This is purely event-based — the existing 5-second sysfs poll handles both detection and restoration with no additional timers or CPU overhead.

## 12. ITE8291R3 Keyboard Controller Protocol

### USB Interface
- **Vendor ID**: 0x048D (ITE Tech)
- **PIDs**: 0x6004, 0x6006, 0xCE00
- **Interface**: 1 (HID)
- **Control transfer**: `HID_REQ_SET_REPORT (0x09)`, type CLASS, report type Feature, 8-byte payload

### Command Bytes (byte 0 of 8-byte payload)
| Cmd | Name | Payload |
|-----|------|---------|
| 0x07 | SET_PALETTE | `{0x07, index, R, G, B, 0, 0, 0}` — programs palette slot 1-7 |
| 0x08 | SET_EFFECT | `{0x08, control, effect, speed, brightness, color_index, dir_or_reactive, save}` |
| 0x09 | SET_BRIGHTNESS | `{0x09, 0x02, brightness, 0, 0, 0, 0, 0}` |
| 0x16 | SET_ROW_INDEX | `{0x16, 0x00, row, 0, 0, 0, 0, 0}` |
| 0x80 | GET_FW_VERSION | Query firmware version |
| 0x88 | GET_EFFECT | Query current effect state |

### Effect IDs (byte 2 of SET_EFFECT)
| ID | Effect | Supports Color | Supports Direction | Supports Reactive |
|----|--------|:-:|:-:|:-:|
| 0x02 | breathing | ✅ | - | - |
| 0x03 | wave | - | ✅ (right=1,left=2,up=3,down=4) | - |
| 0x04 | random | ✅ | - | ✅ |
| 0x05 | rainbow | - | - | - |
| 0x06 | ripple | ✅ | - | ✅ |
| 0x09 | marquee | - | - | - |
| 0x0A | raindrop | ✅ | - | - |
| 0x0E | aurora | ✅ | - | ✅ |
| 0x11 | fireworks | ✅ | - | ✅ |
| 0x33 (51) | monocolor/user | - (uses row data) | - | - |

### Color Palette
The chip has a 7-slot color palette (indices 1-7) plus index 0 (none) and 8 (random/multi). Animated effects reference colors by palette index, NOT by RGB. The driver reprograms the palette on init to ensure correct colors:

| Index | Color | RGB |
|-------|-------|-----|
| 0 | none | - |
| 1 | red | (255, 0, 0) |
| 2 | orange | (255, 128, 0) |
| 3 | yellow | (255, 255, 0) |
| 4 | green | (0, 255, 0) |
| 5 | blue | (0, 0, 255) |
| 6 | teal | (0, 255, 255) |
| 7 | purple | (128, 0, 255) |
| 8 | random | cycles all |

### Per-Key Mode (Direct Mode)
In user/monocolor mode (effect 51), the host sends full row data via interrupt transfer:
1. Send SET_ROW_INDEX for each row (0-5)
2. Send 65-byte row buffer via interrupt endpoint: `{row_header, B[0..20], G[0..20], R[0..20]}`
3. Hardware rows are inverted: hw row 5 = physical top row (ESC/F-keys)

### Reactive Mode
Byte 6 = 1 enables hardware-driven keypress reactivity. The ITE8291R3 internally detects keypresses and triggers the animation from the pressed key's position. Only supported by: ripple (0x06), aurora (0x0E), fireworks (0x11), random (0x04).

### Music Sync
The ITE8291R3 Rev 0.03 does NOT have native audio processing. Music visualization requires host-driven per-key RGB streaming — a userspace daemon must perform FFT on system audio and send Direct Mode frames at high frequency.

### Sysfs Interface (`/sys/class/leds/ite8291r3::kbd_backlight/`)
| File | Mode | Description |
|------|------|-------------|
| brightness | RW | 0-255 standard LED brightness |
| color | RW | `R G B` — monocolor RGB (triggers user mode) |
| effect | RW | Effect name: off/breathing/wave/ripple/etc |
| speed | RW | 0-9 effect speed |
| color_index | RW | 0-8 palette color index |
| reactive | RW | 0/1 reactive mode flag |
| direction | RW | 0-4 wave direction |
| audio_mode | RW | 0-4 audio/animation modifier (CMD 0x02) |
| audio_sensitivity | RW | 0-255 ADC gain/threshold for audio mode (default 128) |
| palette | WO | `index R G B` — program palette slot (non-functional on FW 16.04) |
| key_colors | WO | `row col R G B [row col R G B ...]` — per-key |

### CMD 0x02 Global Control / Audio Mode
Command byte 0x02 (distinct from effect ID 0x02 "breathing") is a **Global Control** layer in the Tongfang protocol.
- **Format**: `{0x02, mode, sensitivity, 0, 0, 0, 0, 0}`

| Mode | Official Name | Description |
|------|---------------|-------------|
| 0x00 | Normal / Soft Mode | Disables hardware overrides; returns control to the 0x08 Effect Engine |
| 0x01 | Hardware Audio Sync | Connects LED engine to internal ADC pins (Sound-to-Light via Realtek ALC269 → ITE PA0/PA1) |
| 0x02 | Real-Time Data Mode | Prepares controller to receive per-key RGB frames from host (Direct Mode) |
| 0x03 | Diagnostic Scan | Factory-level row/column matrix scanner for LED/key validation |
| 0x04 | BPM / Global Pulse | (FW dependent) Pulses based on average audio amplitude |

**Sensitivity byte** (byte 2, mode 0x01 only — ADC gain/threshold):
- 0x00–0x20: Very low — requires max system volume to trigger
- 0x80: Standard sensitivity (recommended)
- 0xFF: Max sensitivity — picks up electronic noise, causes fast reactive flicker

**Hybrid mode**: Set Aurora (0x0E) with reactive=1 via CMD 0x08, then send CMD 0x02 mode=0x01. The controller uses Aurora colors as background with audio-triggered spikes/flashes.

**Discovered combinations**:
| Base Effect | Params | audio_mode | Result |
|-------------|--------|:---:|--------|
| Aurora (0x0E) | speed=5, reactive=0 | 3 | Row scanner: keys light one by one per row |
| Aurora (0x0E) | speed=0, reactive=1 | 1 | Fast reactive row pattern |
| Aurora (0x0E) | speed=10, reactive=1 | 1 | Shifting color reactive pattern |

### Firmware Limitations (FW 16.04.00.00, PID 6006)
- **Palette is read-only**: Stored in write-protected flash. Unlock sequence `{0xFE, 0x55, 0xAA, 0x00, 0x00, 0x00, 0x00, 0x00}` before CMD 0x14 may work but risks EEPROM wear. Colors are likely hardcoded in FW binary.
- **Only 11 effect IDs work**: 0x02-0x06, 0x09-0x0B, 0x0E, 0x11, 0x33
- **ADC audio wiring confirmed**: Realtek ALC269 MONO_OUT (Pin 37) → ITE8291R3 ADC pins PA0/PA1 (analog only). Bluetooth/HDMI/USB audio stays digital and never reaches the ADC.
- **Reactive fade (0x0B)**: Works but has stepped/jagged PWM (hardware limitation)
- **Per-key brightness variation**: Some keys appear consistently brighter — may indicate per-key brightness granularity in the LED matrix hardware.

### CMD 0x02 Mode 0x04: Internal Clock Pulse (BPM)
- Does NOT use ADC — uses an internal timer to pulse LEDs
- Byte 3 (Sensitivity) acts as **BPM divider**: 0xFF = slow heartbeat, 0x01 = fast strobe

### Interrupt Endpoint 0x81 (Status Readback)
The ITE8291R3 reports status via Interrupt IN endpoint at 8-16ms polling rate:

| Byte | Content |
|------|---------|
| 0 | Report ID |
| 1 | Mode |
| 2 | Speed |
| 3 | Brightness |
| 4 | Color |
| 5 | **ADC Peak** (live audio amplitude in Mode 0x01) |
| 6 | Status |
| 7 | Checksum |

**Byte 5 in Mode 0x01** gives real-time ADC level — use this to confirm if the analog audio path is active.

### EC Register for Audio-to-Keyboard Gate
- **WMI Method**: `AcpiTest_MULong` (GUID: `ABBC0F6F-8EA1-11d1-00A0-C90629100000`)
- **EC offset**: `0xCF` or `0xD0` — toggles "Audio-to-KBD" gate
- Setting to `0x01` keeps ALC269 analog out active even with headphones plugged in
- Could potentially be used to route mixed audio to ADC for hardware sync

### CMD 0x08 Full Parameter Space
| Byte | Parameter | Range / Notes |
|------|-----------|---------------|
| 2 | Effect ID | 0x02-0x11, 0x33 |
| 3 | Speed | 0x00 (fastest) to 0x0A (slowest) |
| 4 | Brightness | 0x00 to 0x32 (50 dec) |
| 5 | Color Index | 0x01-0x07 (palette), 0x08 (random/global) |
| 6 | Direction/Reactive | Bit 0: direction (0=left, 1=right); Bit 7: reactive toggle |
| 7 | Density/Spread | Controls how many keys lit in wave/fireworks |
- **ADC only sees analog path**: Hardware Audio Sync (mode 0x01) only reacts to audio routed through the Realtek ALC269 analog output (internal speakers, 3.5mm jack). Bluetooth, HDMI, and USB audio bypass the ADC entirely.

### Software Audio-Reactive Mode (tools/test_music_sensitivity.py --sw)
For audio output that bypasses the hardware ADC (Bluetooth speakers, HDMI, USB DAC), a software-driven mode captures system audio via PipeWire/PulseAudio monitor source and renders a spectrum visualizer to the keyboard using per-key RGB.

**Data flow**:
```
App Audio → PipeWire → EasyEffects Sink → Output (BT/HDMI/Analog)
                ↓ (.monitor tap)
         parec capture → FFT → 21-band spectrum → ITE8291R3 per-key RGB
```

- Captures from `easyeffects_sink.monitor` (sees all audio regardless of output)
- Log-scaled frequency bands mapped to keyboard columns
- Rainbow hue shift with auto-gain normalization
- ~30fps update rate via USB bulk/control transfer

---

## 10. Development vs Installed Deployment

### Two-Copy Architecture
| Location | Purpose |
|----------|---------|
| `/home/adriansandru/Downloads/Project-nuc/` | **Development** — IDE edits go here |
| `/opt/nuc-linux-studio/` | **Installed** — the app runs from here via pkexec |

The app is launched via a `.desktop` file or `pkexec python3 /opt/nuc-linux-studio/cli.py`. Edits to the dev directory have **no effect** until copied to `/opt/`.

### Sync Procedure (after any edit)
```bash
sudo rsync -a --delete --exclude='__pycache__' ~/Downloads/Project-nuc/ui/ /opt/nuc-linux-studio/ui/
sudo rsync -a --delete --exclude='__pycache__' ~/Downloads/Project-nuc/backend/ /opt/nuc-linux-studio/backend/
sudo cp ~/Downloads/Project-nuc/cli.py /opt/nuc-linux-studio/cli.py
sudo find /opt/nuc-linux-studio -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

**WARNING**: Do NOT use `cp -r` — it copies `__pycache__` dirs from dev, causing stale bytecode to run instead of new source files.

For daemon changes, also restart the relevant service:
```bash
sudo systemctl restart <service-name>
```

### Recommended Full Sync Command
```bash
sudo rsync -a --delete --exclude='__pycache__' ~/Downloads/Project-nuc/ui/ /opt/nuc-linux-studio/ui/ && \
sudo rsync -a --delete --exclude='__pycache__' ~/Downloads/Project-nuc/backend/ /opt/nuc-linux-studio/backend/ && \
sudo cp ~/Downloads/Project-nuc/cli.py /opt/nuc-linux-studio/cli.py && \
sudo find /opt/nuc-linux-studio -name "*.pyc" -delete 2>/dev/null
```

---

## 11. On-Screen Display (OSD)

### Overview
A GTK3-based heads-up overlay that shows event feedback on **all connected monitors** simultaneously. Runs as a background process started on GNOME session login via `/etc/xdg/autostart/nuc-osd.desktop`.

### Architecture
```
Hotkey Event                          OSD Process (user session)
    │                                      │
    ▼                                 /tmp/nuc-osd.sock
backend/osd.py (send_osd helper)  ──► Unix DGRAM socket ──► GLib.idle_add(osd.show)
    │                                      │
    └── events.c / pdev.c daemon           ▼
        sends JSON: {"type":...,      NucOSD.show(msg)
                     "value":...,          │
                     "label":...}          ├── OSDWindow[0] → Monitor 0 (eDP-1)
                                           └── OSDWindow[1] → Monitor 1 (HDMI-1)
```

### Key Design Decisions

#### Window Type: POPUP (not TOPLEVEL)
- `Gtk.WindowType.TOPLEVEL` with any type hint (`NOTIFICATION`, `DOCK`, etc.) gets repositioned by Mutter/GNOME Shell on XWayland — the WM places all TOPLEVEL windows on the primary monitor, ignoring `window.move()`.
- `Gtk.WindowType.POPUP` bypasses WM placement policy entirely. `move(x, y)` is respected unconditionally.
- **Lesson learned**: Never use TOPLEVEL for OSD/overlay windows on GNOME/XWayland; always use POPUP.

#### Multi-Monitor Positioning
- One `OSDWindow` per `Gdk.Monitor`. `display.get_n_monitors()` enumerates all connected monitors.
- `monitor.get_geometry()` returns the physical offset (`geom.x`, `geom.y`) used to compute per-monitor center-bottom position.
- `position()` is called at `show_all()`, then again at +idle, +50ms, +150ms to fight XWayland async remap.
- Monitor hot-plug handled via `display.connect("monitor-added/removed")` → `_rebuild_windows()`.

#### Event Types and Visuals
| Event Type | Icon ON | Icon OFF | Color ON | Color OFF | Has Bar |
|---|---|---|---|---|---|
| `kbd-brightness` | 🔆 | 🔅 | `#4fc3f7` | `#666666` | ✅ |
| `touchpad` | 🖱️ | 🖱️✗ | `#66bb6a` | `#ef5350` | ❌ |
| `mic-mute` | 🎤 | 🎤🚫 | `#66bb6a` | `#ef5350` | ❌ |
| `airplane` | 📡 | ✈️ | `#66bb6a` | `#ffa726` | ❌ |
| `perf-mode` | ⚡ | ⚡ | `#ab47bc` | `#ab47bc` | ❌ |
| `caps-lock` | 🔠 | 🔡 | `#66bb6a` | `#ef5350` | ❌ |
| `screen-brightness` | 🌟 | 🌑 | `#ffcc02` | `#888888` | ✅ |

#### Accent Bar
A 4px colored bar at the top of each OSD popup reflects the event accent color — green for ON, red for OFF — providing immediate visual distinction even at a glance.

#### GDK_BACKEND=x11
The OSD forces `GDK_BACKEND=x11` for reliable `window.move()` on XWayland. The Wayland layer-shell path (`GtkLayerShell`) is probed at startup and used if available (e.g. KDE/sway), but falls back to manual X11 positioning on GNOME.

### Socket Protocol
- **Path**: `/tmp/nuc-osd.sock` (Unix DGRAM, 0o666)
- **Format**: `{"type": "<event>", "value": <int|float|bool>, "label": "<string>"}`
- **Helper**: `from backend.osd import send_osd; send_osd("touchpad", 1, "Touchpad On")`

### Autostart
- Installed as systemd **user unit** to `/usr/lib/systemd/user/nuc-osd.service`
- `ExecStartPre=/bin/sleep 3` — waits for the graphical session to settle before binding the socket
- Enabled per-user by install.sh via `sudo -u "$REAL_USER" systemctl --user enable --now nuc-osd.service`
- Runs as the login user (not root), has access to the user's display session
- Environment: `GDK_BACKEND=x11` set in unit file for reliable `window.move()` on XWayland

### WM_CLASS / Taskbar Icon Matching
- GNOME Shell matches running windows to `.desktop` files by `WM_CLASS`.
- Tkinter sets `WM_CLASS` from `tk.Tk(className=...)`.
- The `.desktop` file must have `StartupWMClass=<className>` matching exactly.
- **Current value**: `nuc-studio` (both `className` and `StartupWMClass`).
- **Lesson learned**: Mismatch causes GNOME to show a generic icon instead of the app icon in the dock/taskbar.

---

## 12. Keyboard Theme System (Per-Key Software Themes)

### Overview
The keyboard tab provides 5 "software themes" that use `set_per_key_colors()` to implement visually rich per-key RGB patterns. These are app-managed — the hardware has no concept of them; they run on top of the hardware's per-key mode.

| Theme | Keys | Description |
|---|---|---|
| `glow` | All | Single base color × per-key brightness multipliers. Global brightness slider adjusts all keys. |
| `per-key` | All | Individual color per key set by user. No global brightness slider. |
| `coding` | All | Orange/white/teal/green 4-group system — structure keys orange, symbols teal, letters half-amp green |
| `writing` | All | Indigo/yellow system — letters gold, commit keys indigo, nav soft-indigo, modifiers dim gold |
| `gaming` | All | Red system — WASD full red, 1-7+action orange, F-keys/arrows 70% red, rest 40% red |

### `_APP_MANAGED` Effect Guard (CRITICAL)
When any of these effects is active, `sync_from_hardware()` must NOT read the sysfs `effect` file to set `effect_var`. The hardware always reports `"monocolor"` (for glow/monocolor) or `"per-key"` (for all per-key themes) — never the app-level theme name. Without this guard, `sync_from_hardware()` would overwrite the saved `"gaming"` / `"coding"` / etc. with `"monocolor"` 500ms after every app launch.

```python
_APP_MANAGED = {"gaming", "coding", "writing", "per-key", "glow"}
if effect_path.exists() and self.effect_var.get() not in _APP_MANAGED:
    hw_effect = effect_path.read_text().strip()
    ...
```

### Per-Key vs Glow Brightness Rule
- **Glow**: `_apply_glow()` calls `set_per_key_colors(composite, 100)`. Brightness is baked into RGB via `mono_color × factor`. Global brightness slider visible.
- **Per-key**: `_apply_per_key()` always calls `set_per_key_colors(composite, 100)`. Per-key colors encode their own luminance — no global dimming. Brightness slider HIDDEN.
- **Themed (gaming/coding/writing)**: `set_per_key_colors(composite, brightness)` where `brightness = keyboard_brightness_var.get()`. Tier base RGBs must have ≥ 100 per-channel floor so keys remain visible at 50%.

### Dynamic Range Rule for Tier-Based Themes
If a theme has N tiers with different base luminances, the ratio between highest and lowest tier base should be ≤ 3:1. At 50% brightness, the bottom tier must still be ≥ ~20% luminance to be visually present.
- Gaming: 255/100 = 2.55:1 ✅
- Coding: letters=(0,128,0), top=(255,255,255) — 2:1 on G channel ✅

---

## 13. Fan Curve UI Architecture

### Grid Layout (Power Tab)
The fan curve sliders are arranged in a 6-column grid:

| Col 0 | Col 1 | Col 2 | Col 3 | Col 4 | Col 5 |
|---|---|---|---|---|---|
| Temp (°C) | CPU Slider | CPU RPM | GPU Slider | GPU RPM | Temp (°C) |

Column 5 mirrors column 0 — shows the same `{temp}°C` label. This lets the user read CPU and GPU fan targets at the same temp point without scanning back to column 0.

### Alternating Row Shading
Even rows (index 0, 2, 4… = 35°C, 45°C, 55°C…) use the base trough color. Odd rows (index 1, 3, 5… = 40°C, 50°C…) are `+18` per RGB channel (visually lighter). Computed inline during slider creation and recomputed in `apply_theme()`.

```python
def _alt_trough(base_hex, lighten, is_odd):
    if not is_odd:
        return base_hex
    r = min(255, int(base_hex[1:3], 16) + lighten)
    g = min(255, int(base_hex[3:5], 16) + lighten)
    b = min(255, int(base_hex[5:7], 16) + lighten)
    return f"#{r:02x}{g:02x}{b:02x}"
```

### Trough Color Keys (themes.py)
| Key | Dark | Light | Family |
|---|---|---|---|
| `scale_trough_cpu` | `#0E1828` | `#C0D0E8` | Blue — Intel |
| `scale_trough_gpu` | `#0E1E0E` | `#C8E8C0` | Green — Nvidia |

---

## 14. Battery Charge Limit — Persistence & upower Interaction

### How the Limit Is Applied

1. **Boot-time (primary)**: `nuc-battery-limit.service` (Type=oneshot, runs once at boot)  
   - Source: `backend/battery_limit_apply.py`
   - Reads `charge_limit` from all config paths (`/root`, `/home/*`)
   - Writes `charge_control_end_threshold` + `charging_profile` sysfs

2. **Runtime guard (secondary)**: `fan_curve_daemon.py::_reapply_battery_limit()`  
   - Called whenever `fan-curve.service` detects a upower restart  
   - Also called after every resume from suspend  
   - Mirror of `battery_limit_apply.py` logic — same config search, same sysfs writes

### The upower Reset Problem (Confirmed 2026-05-17)

**Symptom**: After `sudo systemctl restart upower`, `charge_control_end_threshold` resets to `100` (kernel default). The saved limit is gone until something re-writes sysfs.

**Root cause**: upower manages battery sysfs devices at startup. On restart, it re-reads sysfs and may reset writable thresholds back to the kernel default. This is an upstream upower behavior, not a driver bug.

**Impact**: Without the fan-curve daemon running, the charge limit is silently cleared on every upower restart. The laptop will charge to 100% regardless of the configured limit.

**Protection**:
```
upower restarts
    │
    ▼
fan_curve_daemon detects restart
    │
    ▼
_reapply_battery_limit()
    ├─ Reads charge_limit from settings.json
    ├─ Writes charge_control_end_threshold = <limit>
    └─ Writes charging_profile = stationary/balanced/high_capacity
```

**Important subtlety**: After a upower restart, if the user moves the charge limit slider in the UI *before* the daemon re-applies it, sysfs shows the correct value because the UI write also saves it. The daemon write would have been redundant in that case — but it's the safety net for the case where no one touches the UI.

**Rule**: `nuc-battery-limit.service` MUST remain enabled. `fan-curve.service` MUST remain running for mid-session protection. If only the oneshot boot service is active and upower restarts, the limit is unprotected until next reboot.

---

## TODO: Minimum Window Size & OSD Scaling

### Minimum Window Size (`ui/main.py`)
- **TODO**: Call `root.minsize(width, height)` in `ui/main.py` after the main window is created.
- The correct values depend on target screen resolution and DPI scaling factor (HiDPI vs 1080p).
- At 1080p with no scaling, `minsize(960, 820)` is a reasonable starting point to comfortably fit 11 fan curve sliders + live status section without clipping.
- At 4K with 2× scaling, the effective pixel size doubles and a larger minsize may be needed.
- **Revisit when**: target resolution/DPI configuration is finalized or when users report layout clipping.

### OSD Window Scaling (`backend/osd.py`)
- The OSD popup sizes are currently hardcoded in pixels.
- On HiDPI displays (e.g. 4K@2× scaling) the OSD may appear too small.
- **TODO**: Make OSD width/height/font sizes relative to screen size (use `Gdk.Screen.get_default().get_width()` or `monitor.get_geometry()` to compute a percentage-based size).
- **Revisit when**: OSD is tested on a HiDPI display or user reports it is too small/large.



