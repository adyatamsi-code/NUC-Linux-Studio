# Intel NUC X15 Laptop Kit - Hardware Specification

## System Overview

The Intel NUC X15 Laptop Kit (Uniwill/TongFang chassis, board `LAPKC71F`) is the target platform.
This document is the authoritative reference for hardware capabilities, EC registers, and project rules.

## DMI Identification

- **Board name**: `LAPKC71F`
- **Board vendor**: Intel Corporation
- **Product name**: `LAPKC71F`
- **System vendor**: Intel(R) Client Systems

## Hardware Features

### 1. Keyboard (ITE8291R3)
- **Type**: Ultra-low-profile mechanical keyboard with per-key RGB LED backlight
- **Controller**: ITE8291R3 USB HID (VID 0x048D, PID 0x6006, FW 16.04.00.00)
- **Grid**: 6×21 LED matrix (hardware rows inverted: hw row 5 = physical top/ESC row)
- **Interface**: USB control transfers (HID SET_REPORT, 8-byte payload) + interrupt EP for row data
- **Control**: Kernel driver `ite8291r3.ko` (sysfs) or `ite8291r3_ctl` Python library (USB direct)
- **Capabilities**:
  - Per-key RGB (Direct Mode, effect 0x33)
  - **Per-key brightness**: Confirmed working. No separate brightness-per-key register exists; brightness is controlled by scaling RGB intensity per key. Writing different RGB magnitudes to individual keys via `key_colors` sysfs produces visible per-key brightness differences. Tested gradient (10%→100%), checkerboard (100%/20%), per-row levels, and single-key stepping — all produce clearly distinct brightness levels. This enables monocolor-with-brightness-variation and per-key brightness overlays.
  - 10 hardware effects: breathing (0x02), wave (0x03), random (0x04), rainbow (0x05), ripple (0x06), marquee (0x09), raindrop (0x0A), aurora (0x0E), fireworks (0x11)
  - Reactive mode (byte 6 = 1): ripple, aurora, fireworks, random
  - Wave direction (byte 6): right=1, left=2, up=3, down=4
  - Speed control (0x00 fastest to 0x0A slowest)
  - 7-slot color palette (firmware-locked on FW 16.04, ROM-burned, not reprogrammable)
  - **Palette wiring mismatch**: Tongfang variant has swapped RGB LED wiring, so palette indices produce different colors than their ITE reference names. Software must remap:

    | Index | ITE Name | Actual Color (NUC X15) | Cause |
    |-------|----------|------------------------|-------|
    | 1 | red | **white** | R+G+B wired together |
    | 2 | orange | orange | correct |
    | 3 | yellow | yellow | correct |
    | 4 | green | green | correct |
    | 5 | blue | blue | correct |
    | 6 | teal | **purple** | wiring swap |
    | 7 | purple | **pink** | wiring swap |
    | 8 | random | random (multi) | correct |

    No HID commands exist to read back or modify the palette LUT. For true custom colors on hardware effects, software-driven per-key mode is the only option.
  - CMD 0x02 audio/animation modifier (mode 0-4)
  - Hardware audio sync via internal ADC (analog audio path only)
- **Layout**: 15-column, 6-row TKL with right-side navigation cluster
- **Bottom row**: Ctrl, Fn, Win, Alt, Space, Alt, Menu, Ctrl, ←, ↓, →, End

#### Fn Key Map
| Fn + Key | Function | WMI Event | Notes |
|----------|----------|-----------|-------|
| Fn+Esc | Fn Lock Toggle | 184 | |
| Fn+F2 | Super Key Lock | — | Direct EC toggle |
| Fn+F3 | Volume Down | 54 | Handled by GNOME |
| Fn+F4 | Volume Up | 55 | Handled by GNOME |
| Fn+F5 | Mic Mute | 183 (0xB7) | Driver maps to KEY_MICMUTE |
| Fn+F7 | Touchpad Toggle | 4/5 | Daemon handles HID LED |
| Fn+F8 | KB Backlight Cycle | 185/187 | GNOME gsd-power handles brightness; daemon observes |
| Fn+F9 | Screen Brightness Down | 21 | |
| Fn+F10 | Screen Brightness Up | 20 | |
| Fn+F11 | Display Switch | ACPI video | |
| Fn+F12 | Airplane Mode | 164 | |
| Fn+Ins | PrtSc | — | |
| Fn+ScrLk | NumLk | — | |

#### ITE8291R3 Command Protocol
| Cmd Byte | Name | Payload Format |
|----------|------|----------------|
| 0x02 | GLOBAL_CTRL | `{0x02, mode, sensitivity, 0, 0, 0, 0, 0}` |
| 0x07 | SET_PALETTE | `{0x07, index, R, G, B, 0, 0, 0}` |
| 0x08 | SET_EFFECT | `{0x08, ctrl, effect, speed, brightness, color_idx, dir/reactive, save}` |
| 0x09 | SET_BRIGHTNESS | `{0x09, 0x02, brightness, 0, 0, 0, 0, 0}` |
| 0x16 | SET_ROW_INDEX | `{0x16, 0x00, row, 0, 0, 0, 0, 0}` |
| 0x80 | GET_FW_VERSION | Query firmware version |
| 0x88 | GET_EFFECT | Query current effect state |

#### CMD 0x02 Global Control Modes
| Mode | Name | Description |
|------|------|-------------|
| 0x00 | Normal/Soft | Returns control to 0x08 Effect Engine |
| 0x01 | Hardware Audio Sync | ADC-based (Realtek ALC269 → ITE PA0/PA1, analog only) |
| 0x02 | Real-Time Data | Prepares for host-driven per-key RGB streaming |
| 0x03 | Diagnostic Scan | Factory LED/key matrix validator |
| 0x04 | BPM/Global Pulse | Internal timer pulse (sensitivity = BPM divider) |

#### Firmware Limitations (FW 16.04.00.00)
- Palette is read-only (hardcoded in write-protected flash)
- Only 11 effect IDs work: 0x02-0x06, 0x09-0x0B, 0x0E, 0x11, 0x33
- ADC audio only sees analog path (speakers/3.5mm); Bluetooth/HDMI/USB bypass ADC
- Reactive fade (0x0B) has stepped/jagged PWM

### 2. Lightbar
- **Type**: Front-facing RGB lightbar (single zone, multiple LEDs)
- **EC registers** (page 0x07):
  - `0x0747` — Brightness (0x00=off, 0x64=max)
  - `0x0748` — Control register (LIGHTBAR_CTRL_ADDR):
    - BIT(0): Static mode (0x01) — display RGB values from 0x0749-0x074B
    - BIT(1): Power Save
    - BIT(2): S0 Off — turns lightbar off when system is awake
    - BIT(3): S3 Off — turns lightbar off when system is asleep
    - BIT(5): Breathing mode (0x20) — hardware EC breathing, pulses RGB color; fixed speed
    - BIT(7): Rainbow mode (0x80) — static rainbow gradient, full brightness
    - Mode bits (0/5/7) are mutually exclusive — clear all before setting new mode
  - `0x0749` — RED channel (0–36)
  - `0x074A` — GREEN channel (0–36)
  - `0x074B` — BLUE channel (0–36)
  - `0x074E` — BIOS Control 1 (Fn-lock, LID/AC flags — DO NOT WRITE)
- **Note**: EC `SUPPORT_1` (0x0765) bit 6 may not report lightbar support — driver force-enables for NUC X15
- **Known issue**: Blue LED physically dim on right side (hardware defect, not software-fixable)
- **Static mode brightness**: EC firmware caps static PWM at ~25-35% duty; only BIT(7) rainbow gives full brightness

### 3. Fans
- **CPU fan**: Present, controllable via hwmon PWM (`pwm1`)
- **dGPU fan**: Present, controllable via hwmon PWM (`pwm2`)
- **Sensors**: CPU temp (`temp1_input`), dGPU temp (`temp2_input`) via hwmon
- **EC temperature race**: Occasional spurious readings (e.g. 165°C) during EC register update — filtered in software

### 4. Battery
- **Charge limit**: EC supports `charge_control_end_threshold` (1-100%)
- **Note**: `batt_charge_limit` flag force-enabled for NUC X15 DMI match

### 5. Power Profiles
- **Physical button**: Left of power button, same size, with 2 indicator LEDs
  - Both LEDs = Performance, One LED = Balanced, No LEDs = Silent
  - Cycles: Silent → Balanced → Performance → Silent
- **EC registers**:
  - `0x0751` (PERF_PROFILE_ADDR): Profile bits in `PERF_PROFILE_MASK` (0xb0) — **unreliable for reads** (stale up to 1s after manual mode changes)
    - Silent: `0xa0`, Balanced: `0x00`, Performance: `0x10`
  - `0x07A5` (CTRL_3_ADDR): Bits 0-1 mirror button LED state — **always readable**, even in manual mode
    - `0x00` = Balanced (1 LED), `0x01` = Performance (2 LEDs), `0x02` = Silent (0 LEDs)
    - Read-only (EC ignores writes)
  - `0x0741` (CTRL_1_ADDR): Bit 0 = manual fan mode; must be cleared for EC to update LEDs on profile change
- **EC constraint**: Writes to 0x0751 ignored when CTRL_1_MANUAL_MODE is active

### 6. Touchpad
- **LED**: Wired to I2C-HID Touchpad Controller (UNIW0001), NOT to EC
- **Control**: HID `HIDIOCSFEATURE` ioctl on `/dev/hidraw*`
- **Toggle**: Fn+F7 or double-tap zone (EC `CTRL_4_TOUCHPAD_TOGGLE_OFF`)

---

## Project Rules

### Rule 1: Our driver is `nuc_wmi` (in `driver/`)
All kernel driver development happens in `driver/`. The `nuc_wmi.ko` module handles EC/WMI communication and `ite8291r3.ko` handles USB keyboard LED control.

### Rule 2: Reference drivers are read-only
Any reference driver code is for study only and must not be modified.

### Rule 3: Single pkexec prompt
All sysfs writes in a single user action must be batched into ONE elevated command using `write_multiple()` or `batch_writes()`.

### Rule 4: Hardware assumptions
If something doesn't work, it's a driver/software bug, not missing hardware. The NUC X15 has: lightbar, per-key RGB keyboard, CPU+dGPU fans, battery charge limit, power profiles, touchpad LED.

### Rule 5: Documentation
Update `docs/NUC_STUDIO_PROGRESS.md` and `CHANGELOG.md` on every feature completion or bug fix.
