# NUC Linux Studio v2.7

A full-featured Linux replacement for Intel NUC Software Studio, targeting the NUC X15 Laptop Kit (TongFang/Uniwill chassis, board `LAPKC71F`).

## Features

### Keyboard Lighting
- **Audio-reactive mode** — software FFT spectrum visualizer across keyboard columns. Works with any audio output (Bluetooth, HDMI, USB DAC) via PipeWire/PulseAudio capture. Keeps running after app close through a dedicated daemon.
- **Per-key RGB** — full 6×21 ITE8291R3 grid with color editor, Gaming/Coding presets, and 10 hardware effects: breathing, wave, rainbow, ripple, aurora, fireworks, raindrop, marquee, random, audio visualizer.
- **Effect controls** — per-effect speed, color palette, direction (wave), and reactive mode (ripple/aurora/fireworks), all saved per effect. Brightness slider appears only for Glow.
- **Brightness sync** — Fn+F8 toggle handled by GNOME `gsd-power`. Daemon restores effect and colors on boot/resume and survives idle dim.

### Chassis Lighting
- **Lightbar** — static RGB (16M colors mapped to EC PWM) plus a rainbow animation driven through EC registers. Calibrated swatches show actual physical LED output (R+G only, blue dead).

### Performance & Thermals
- **Fan curves** — per-profile CPU and dGPU curves with live temperature and RPM monitoring. A dedicated daemon keeps curves active after app close, releases fan control cleanly on suspend, and re-applies after resume.
- **Power profiles** — Silent / Balanced / Performance / Benchmark, synced to the hardware button via the CTRL_3 register (reliable, no double-cycling).
- **Battery health** — charge limit at 60% / 80% / 100% via sysfs, plus a battery and NVMe drive health canvas.

### Hardware Controls
- **Face unlock** — Howdy integration with face model management, PAM configuration, and camera preview.
- **Toggles** — Fn Lock, Super Key Lock, Touchpad (with LED sync via HID feature reports), and Mic Mute status.

### System Integration
- **On-screen display** — GTK3 popup overlay shown on all monitors at once for Fn key events: caps lock, touchpad, mic, airplane mode, keyboard brightness, performance mode, screen brightness. Runs as an autostart daemon via `/etc/xdg/autostart/`.
- **Dark / Light theme** — full toggle with dark (indigo/gold) and light (ivory/sky-blue) palettes. Theme-aware status indicators, per-tab restyling, branded Intel/NVIDIA badges.

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
| `fan-curve.service` | Applies custom fan curves from JSON state file, interpolates temp→PWM, survives app close, handles suspend/resume with 12 s EC grace period |
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

This builds and installs DKMS drivers (`nuc_wmi` + `ite8291r3`), copies the app to `/opt/nuc-linux-studio/`, creates systemd services, installs udev rules, installs the suspend/resume sleep hook, adds a `nuc-studio` launcher command, and sets up polkit policy for GUI elevation.

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
| `docs/ARCHITECTURE.md` | Full system architecture, data flows, IPC, EC register experiments, ITE8291R3 USB protocol, fan suspend/resume, OSD design |
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
