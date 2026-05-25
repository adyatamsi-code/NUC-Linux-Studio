# Touchpad Daemon Debug Log — May 12, 2026

## Hardware Facts (confirmed via testing)

1. **LED ON (lit) = touchpad DISABLED** — the LED is a "touchpad locked" indicator
2. **HID feature report is the MASTER SWITCH**: `0x03` = touchpad ENABLED (events flow), `0x00` = touchpad DISABLED (events stop). The LED state follows the val but inverted: 0x03 = LED ON, 0x00 = LED OFF.
3. **EC CTRL_4 bit 6**: secondary control, does NOT actually stop/start touchpad events by itself
4. **Fn+F7 produces TWO dmesg events**: the i8042 scancode filter fires "touchpad toggle pressed" twice ~1s apart. The firmware also changes the HID feature report value.
5. **WMI events (case 4/5 "touchpad on"/"touchpad off")**: never fire on this hardware — only the i8042 path is used
6. **Writing the HID feature report (HIDIOCSFEATURE)**: REQUIRED to actually enable/disable the touchpad. Without it the hardware stays in its last state.
7. **Reading the HID feature report (HIDIOCGFEATURE) is safe** — does not affect touchpad state
8. **EC sysfs write does NOT change the HID feature report value** — they are independent
9. **Double-tap on the LED area**: handled entirely by the touchpad firmware, changes the HID feature report value, no dmesg/kernel event
10. **gsettings send-events**: controls GNOME's processing of touchpad events; secondary to HID

## Bugs Found & Fixed

### Bug 1: Inverted OSD
- **Symptom**: OSD showed opposite state from LED
- **Cause**: LED ON = touchpad OFF, but OSD was using LED state directly
- **Fix**: OSD follows the `enabled` parameter (touchpad state), not LED state

### Bug 2: Double toggle on single Fn+F7 press
- **Symptom**: Pressing Fn+F7 toggled ON then immediately OFF
- **Cause**: Fn+F7 generates two "touchpad toggle pressed" dmesg events ~1s apart. Debounce was too short (0.3s).
- **Fix**: Debounce set to 1.5s, and debounce timer updated AFTER set_touchpad_led() completes (not before)

### Bug 3: HID feature report write breaks touchpad
- **Symptom**: gsettings=enabled, EC=1, but touchpad hardware non-responsive
- **Cause**: Writing HIDIOCSFEATURE resets the EC touchpad state, overriding our EC sysfs write
- **Fix**: Removed all HID feature report WRITES. Only EC sysfs + gsettings used to toggle.

### Bug 4: HID poller undoes Fn+F7 toggle
- **Symptom**: Every Fn+F7 OFF gets reversed to ON after ~1.5s
- **Cause**: Fn+F7 also changes the HID feature report value (firmware processes same scancodes). The HID poller reads this change and treats it as a user double-tap, re-enabling the touchpad.
- **Fix**: HID poller suppressed for 5s after any Fn+F7/dmesg event (`last_fnf7_time` variable)

### Bug 5: write_ec=False on Fn+F7 left EC out of sync  
- **Symptom**: gsettings set to enabled but touchpad hardware didn't respond
- **Cause**: EC touchpad_enabled was not written on Fn+F7 events (was skipped because of incorrect assumption that WMI handler writes it)
- **Fix**: Always write EC sysfs on every toggle, regardless of source

### Bug 6: Removing HID write broke touchpad entirely
- **Symptom**: OSD and LED toggle, but touchpad never responds
- **Cause**: The HID feature report (HIDIOCSFEATURE) is the MASTER SWITCH for the touchpad hardware. Without writing it, the firmware never enables/disables actual event delivery. EC sysfs and gsettings are secondary — they don't control the hardware.
- **Confirmed**: `libinput debug-events` showed ZERO events with HID val=0x00, and immediate events after writing val=0x03
- **HID values (confirmed)**: val 0x03 = touchpad ENABLED (sends events), val 0x00 = touchpad DISABLED (silent)
- **Fix**: Restored HID feature report writes. Combined with Bug 4 fix (5s HID poll suppression after Fn+F7) to prevent the poller from undoing toggles.

### Bug 7: HID poller causes infinite ON/OFF toggle loop
- **Symptom**: Touchpad rapidly toggles ON→OFF→ON→OFF every ~2.5s endlessly
- **Cause**: Writing the HID feature report (0x03 to enable) triggers the firmware's internal toggle mechanism, which immediately resets the value back to 0x00. The poller reads 0x00, thinks it's a double-tap, writes 0x03 again → infinite loop.
- **Fix**: Removed HID poller entirely. Double-tap on the LED cannot be detected via HID polling because it's incompatible with HID writes. Only Fn+F7 (via dmesg) is used for toggling.

### Bug 9: EC Register Corruption (2026-05-14)
- **Symptom**: After writing `0x67` to EC register page 0x07 offset 0xA6 (CTRL_4), double-tap stopped working, Fn+F7 LED/OSD reversed, touchpad permanently unresponsive
- **Root cause**: EC CTRL_4 bit 6 is a BOOKKEEPING FLAG only. Writing it directly desynchronizes firmware's internal state machine. The LED/digitizer power is NOT controlled by this register from software.
- **Fix**: Reboot to reset EC firmware state. **NEVER write EC CTRL_4 register from software again.**

### Bug 10: Firmware double-fires "touchpad toggle pressed" (2026-05-14)
- **Symptom**: Every Fn+F7 press or double-tap generated two `key_event_work` firings in dmesg — 0.6s to 3s apart (variable). Daemon would toggle ON then OFF (net no change). No userspace debounce value was reliable.
- **Root cause**: The EC firmware sends the i8042 scancode sequence twice per physical key event. The gap is inconsistent (firmware behavior).
- **Fix**: Added kernel-level debounce in `driver/events.c` `key_event_work()` using `ktime_get()`. If re-fired within 3 seconds, the second firing is silently dropped. This is in the kernel, before dmesg, so it's immune to timing issues.
- **Code change**: `driver/events.c` — added `last_touchpad_toggle_time` ktime tracking in `key_event_work`.

### Bug 11: Daemon reads HID after toggle (wrong architecture) (2026-05-14)
- **Symptom**: After toggle, daemon read HID=0x00 every time and reported "OFF". Touchpad never enabled.
- **Root cause**: Firmware fires the event but does NOT update the HID feature report itself. HID stays at whatever it was last written. Daemon was reading it expecting firmware to have updated it.
- **Fix**: Daemon calls `_toggle()` on "touchpad toggle pressed" — flips own state and WRITES HID. Firmware never writes HID; that is always the daemon's responsibility.

### Bug 8: LED vs Double-tap — Hardware Incompatibility
- **Symptom**: Cannot have both LED indicator AND double-tap re-enable working simultaneously
- **Root cause**: HID feature report byte is a bitmask:
  - `0x03` = touchpad hardware ON, LED OFF
  - `0x02` = touchpad hardware OFF, LED ON
  - `0x01` = touchpad hardware OFF, LED OFF
  - `0x00` = touchpad hardware OFF, LED ON
  Writing `0x00` or `0x02` to show the LED puts the I2C touchpad controller into a low-power state where the digitizer is off. The firmware cannot detect the capacitive double-tap gesture because the hardware is physically powered down.
- **Confirmed via Gemini research**: Windows PTP driver uses "soft disable" (OS ignores events) rather than hardware disable. The LED is controlled by the same HID report that controls power — there is no independent LED control path (no separate ACPI/WMI method or EC register for the LED on this specific chassis).
- **Resolution**: LED control requires HID write → kills double-tap. This is a fundamental hardware constraint. The daemon uses HID `0x00`/`0x03` for Fn+F7 toggle (with LED). Double-tap re-enable is not supported; use Fn+F7 or the GUI app. OSD popup provides visual feedback for all toggles.

