<<<<<<< HEAD
# NUC-Linux-Studio
=======
# NUC Linux Studio v2.1

A full-featured Linux replacement for Intel NUC Software Studio, targeting the NUC X15 Laptop Kit (TongFang/Uniwill chassis, board `LAPKC71F`).

## Features

- **Per-key RGB keyboard** — full 6×21 ITE8291R3 grid with color editor, presets (Gaming/Coding), and 10 hardware effects (breathing, wave, rainbow, ripple, aurora, fireworks, raindrop, marquee, random, audio visualizer)
- **Effect controls** — per-effect speed, color palette selection, direction (wave), reactive mode (ripple/aurora/fireworks), all saved per-effect; brightness slider shown only for Glow effect
- **Software audio-reactive mode** — FFT spectrum visualizer across keyboard columns, works with all audio outputs (Bluetooth, HDMI, USB DAC) via PipeWire/PulseAudio capture; persists after app close via dedicated daemon
- **Keyboard brightness** — Fn+F8 toggle handled by GNOME `gsd-power`; daemon syncs state, restores effect + colors on boot/resume, survives idle dim
- **Chassis lightbar** — static RGB color (16M colors mapped to EC PWM), rainbow animation via EC registers; calibrated color swatches showing actual physical LED output (R+G LEDs only, blue dead)
- **Power profiles** — Silent / Balanced / Performance / Benchmark with hardware button sync via CTRL_3 register (reliable, no double-cycling)
- **Fan curves** — per-profile CPU & dGPU curves with live temperature/RPM monitoring; dedicated daemon persists curves after app close
- **Battery charge limit** — 60% / 80% / 100% via sysfs; battery + NVMe drive health canvas
- **Hardware toggles** — Fn Lock, Super Key Lock, Touchpad (with LED sync via HID feature reports), Mic Mute status display
- **Face unlock** — Howdy integration tab with face model management, PAM configuration, camera preview
- **On-screen display (OSD)** — GTK3 POPUP overlay shown on **all monitors** simultaneously for Fn key events (caps lock, touchpad, mic, airplane mode, kbd brightness, perf mode, screen brightness); runs as autostart daemon via `/etc/xdg/autostart/`
- **Dark/Light theme** — full theme toggle with dark (indigo/gold) and light (ivory/sky-blue) palettes; theme-aware status indicators, per-tab widget restyling, branded Intel/NVIDIA badges

## Architecture

```
driver/     — nuc_wmi.ko + ite8291r3.ko (DKMS kernel modules)
backend/    — Python sysfs controllers + systemd daemons
ui/         — Tkinter GUI (runs as root via pkexec)
cli.py      — Command-line interface
tools/      — Hardware probing & testing utilities
docs/       — Architecture, hardware specs, progress tracking
```

### Kernel Modules
| Module | Purpose |
|--------|---------|
| `nuc_wmi.ko` | WMI/ACPI platform driver — fans, battery, power profiles, lightbar, Fn keys, touchpad, EC access |
| `ite8291r3.ko` | USB LED class driver — per-key RGB, effects, brightness, audio mode for ITE8291R3 controller |

### Systemd Daemons
| Service | Purpose |
|---------|---------|
| `kbd-brightness.service` | Observes keyboard brightness changes, restores effects + per-key colors on boot/resume, handles idle dim, syncs state files |
| `touchpad-led.service` | Handles Fn+F7 touchpad toggle + HID LED control via hidraw |
| `fan-curve.service` | Applies custom fan curves from JSON state file, interpolates temp→PWM, survives app close, handles suspend/resume |
| `kbd-audio.service` | Audio-reactive keyboard daemon — captures system audio, runs FFT, drives per-key RGB; persists after app close |

### Key sysfs Interfaces
| Path | Description |
|------|-------------|
| `/sys/class/leds/ite8291r3::kbd_backlight/` | Keyboard: brightness, color, effect, speed, color_index, reactive, direction, audio_mode, audio_sensitivity, key_colors, palette |
| `/sys/devices/platform/nuc_wmi/` | Platform: fn_lock, super_key_lock, touchpad_enabled, pm_profile, manual_control, hwmon/ |

## Requirements

- Python 3 (standard library + `ite8291r3_ctl` library for USB fallback)
- Tkinter: `sudo dnf install python3-tkinter` (Fedora)
- Kernel headers for DKMS: `sudo dnf install kernel-devel-$(uname -r)`
- Optional: PipeWire + `parec` for software audio-reactive mode

## Install

```bash
sudo ./install.sh
```

This builds and installs DKMS drivers (`nuc_wmi` + `ite8291r3`), copies the app to `/opt/nuc-linux-studio/`, creates systemd services, installs udev rules, adds a `nuc-studio` launcher command, and sets up polkit policy for GUI elevation.

## Launch

```bash
nuc-studio
```

## Uninstall

```bash
sudo ./uninstall.sh
```

## Documentation

| Document | Description |
|----------|-------------|
| `docs/ARCHITECTURE.md` | Full system architecture, data flows, IPC, EC register experiments, ITE8291R3 USB protocol, CMD 0x02 audio mode, OSD design |
| `docs/HARDWARE_SPEC.md` | EC registers, WMI events, hardware capabilities, Fn key map, power profile registers |
| `docs/KEYBOARD_LAYOUT.md` | ITE8291R3 6×21 grid mapping, keycap sizing rules, UI rendering guide |
| `docs/FEATURE_COMPARISON.md` | Side-by-side with Windows NUC Studio — what works, what's pending, resource estimates |
| `docs/NUC_STUDIO_PROGRESS.md` | Feature tracker vs Windows NUC Studio with session log |
| `docs/GEMINI.md` | Agent rules and project conventions |
| `CHANGELOG.md` | Detailed technical change log per session |

## Hardware Compatibility

| Component | Chip/Controller | Interface |
|-----------|----------------|-----------|
| Keyboard RGB | ITE8291R3 (VID 048D, PID 6006) | USB HID |
| Embedded Controller | Uniwill EC (page 0x07) | WMI/ACPI |
| Audio codec | Realtek ALC269 | Internal analog → ITE ADC |
| Board | LAPKC71F | DMI match |
| Firmware | ITE FW 16.04.00.00 | — |
>>>>>>> fe8b8bd (Initial Release)
