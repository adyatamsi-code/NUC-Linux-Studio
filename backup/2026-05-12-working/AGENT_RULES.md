# Agent Rules & Knowledge Base

## MANDATORY PROCEDURES

### Before Modifying ANY File:
1. **Backup first**: `cp <file> backup/YYYY-MM-DD/<file>.bak`
2. **Read current state**: Read the file fully before editing
3. **Document changes**: Update CHANGELOG.md after every modification

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

### Service Deployment:
- Source code: `/home/adriansandru/Downloads/Project-nuc/backend/`
- Installed copy: `/opt/nuc-linux-studio/backend/`
- After editing, MUST: `sudo cp <file> /opt/nuc-linux-studio/backend/<file> && sudo systemctl restart <service>`

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

### Approaches That WORK (CONFIRMED):
1. ✅ **HID 0x00 to disable** — LED ON, touchpad OFF, double-tap still detected by firmware
2. ✅ **HID 0x03 to enable** — LED OFF, touchpad ON, double-tap detected by firmware  
3. ✅ **HID poller at 100ms** — catches firmware double-tap HID changes in both directions
4. ✅ **dmesg watcher** — catches Fn+F7 via "touchpad toggle pressed" string
5. ✅ **`_set_state()` (not toggle) for HID poller** — prevents double-toggle race
6. ✅ **1-second cooldown after HID poller event** — prevents bounce
7. ✅ **debug_ec write ("a6 XX")** — fast, single register write via sysfs (but NOT needed for working solution)

---

## GENERAL PROJECT KNOWLEDGE

### Daemon Architecture
- All daemons run as root systemd services
- Communication with app via filesystem (no sockets/dbus)
- State files: `/tmp/` (volatile), `/var/lib/nuc-linux-studio/` (persistent)
- All daemons handle suspend/resume

### Key Service Files
| Service | Source | Binary |
|---------|--------|--------|
| touchpad-led.service | backend/touchpad_daemon.py | /opt/nuc-linux-studio/backend/touchpad_daemon.py |
| kbd-brightness.service | backend/kbd_brightness_daemon.py | /opt/nuc-linux-studio/backend/kbd_brightness_daemon.py |
| fan-curve.service | backend/fan_curve_daemon.py | /opt/nuc-linux-studio/backend/fan_curve_daemon.py |
| kbd-audio.service | backend/audio_daemon.py | /opt/nuc-linux-studio/backend/audio_daemon.py |

