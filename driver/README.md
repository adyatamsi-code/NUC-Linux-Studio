# NUC WMI + ITE8291R3 Kernel Drivers

Linux kernel drivers for the Intel NUC X15 Laptop Kit (TongFang/Uniwill QC71 chassis).

## Modules

### nuc_wmi.ko
WMI/ACPI platform driver providing:
- **Fan control** — hwmon integration (fan RPM, PWM, temperature sensors for CPU & dGPU)
- **Lightbar** — multicolor LED via EC registers (static RGB + rainbow mode)
- **Power profiles** — Silent/Balanced/Performance via EC, with CTRL_3 register for reliable profile readback
- **Battery** — charge limit control via `charge_control_end_threshold`
- **Hardware toggles** — Fn Lock, Super Key Lock, Touchpad Enable via sysfs
- **WMI events** — keyboard backlight, touchpad toggle, mic mute, profile button, with 3-second grace period on driver load
- **EC debug** — debugfs interface for direct EC register read/write

### ite8291r3.ko
USB LED class driver for the ITE8291R3 keyboard backlight controller:
- **Effects** — breathing, wave, random, rainbow, ripple, marquee, raindrop, aurora, fireworks
- **Per-key RGB** — full 6×21 grid via Direct Mode (effect 0x33)
- **Speed & color** — sysfs attributes for real-time effect parameter changes
- **Reactive mode** — hardware-driven keypress reactivity
- **Wave direction** — right/left/up/down
- **Audio mode** — CMD 0x02 global control (audio sync, diagnostic scan, BPM pulse)
- **Audio sensitivity** — ADC gain/threshold control (0-255)
- **Palette** — sysfs write interface (non-functional on FW 16.04, kept for future firmware)

## Sysfs Interfaces

### nuc_wmi (`/sys/devices/platform/nuc_wmi/`)
| File | Mode | Description |
|------|------|-------------|
| `fn_lock` | RW | Fn Lock state (0/1) |
| `super_key_lock` | RW | Super/Windows key lock (0/1) |
| `touchpad_enabled` | RW | Touchpad state (0/1) |
| `pm_profile` | RW | Power profile (0=Silent, 1=Balanced, 2=Performance) |
| `manual_control` | RW | Manual fan mode (0=EC auto, 1=manual PWM) |
| `hwmon/hwmonN/` | — | Fan RPM, PWM, temperatures |

### ite8291r3 (`/sys/class/leds/ite8291r3::kbd_backlight/`)
| File | Mode | Description |
|------|------|-------------|
| `brightness` | RW | LED brightness (0-255) |
| `color` | RW | Monocolor RGB (`R G B`) |
| `effect` | RW | Effect name (off/breathing/wave/ripple/aurora/fireworks/raindrop/marquee/rainbow/monocolor) |
| `speed` | RW | Effect speed (0-9, 0=fastest) |
| `color_index` | RW | Palette color index (0-8, 8=random) |
| `reactive` | RW | Reactive mode (0/1) |
| `direction` | RW | Wave direction (0-4: none/right/left/up/down) |
| `audio_mode` | RW | CMD 0x02 mode (0-4) |
| `audio_sensitivity` | RW | ADC gain (0-255, default 128) |
| `palette` | WO | Program palette slot (`index R G B`) |
| `key_colors` | WO | Per-key data (`row col R G B [row col R G B ...]`) |

## Installation

Managed by the project's `install.sh` script via DKMS:

```bash
# From project root:
sudo ./install.sh
```

This copies driver sources to `/usr/src/nuc_wmi-1.0/`, runs `dkms install`, and sets up udev rules.

### Manual build (for development)
```bash
cd driver/
make
sudo insmod nuc_wmi.ko
sudo insmod ite8291r3.ko
```

## Dependencies

- Kernel headers: `sudo dnf install kernel-devel-$(uname -r)` (Fedora)
- Kernel compiled with `CONFIG_ACPI`, `CONFIG_DMI`, `CONFIG_USB_HID`
- DKMS: `sudo dnf install dkms`

## Compatibility

- **Tested on**: Intel NUC X15 (LAPKC71F), Fedora 44, kernel 6.19.x
- **ITE8291R3 PIDs**: 0x6004, 0x6006, 0xCE00 (VID 0x048D)
- **Based on**: [qc71_laptop](https://github.com/pobrn/qc71_laptop) by pobrn (GPL v2.0)

## License

GNU General Public License v2.0
