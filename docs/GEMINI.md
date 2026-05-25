# Agent Rules and Instructions

## Logging Changes
- **Changelog Mandate:** Whenever you make modifications to the project, you MUST document what was changed and the technical rationale (why it was changed).
- **Log File:** Append your log entries to `CHANGELOG.md` in the root of the project.
- **Context Preservation:** Ensure every log entry includes a timestamp or date, the specific files modified, a brief description of the changes, and the reasoning behind them.

## Project Rules (MUST FOLLOW)

### Rule 1: Our driver is in `driver/`
All kernel driver development happens in `driver/` — two modules:
- `nuc_wmi.ko` — WMI/ACPI platform driver (fans, battery, power profiles, lightbar, toggles, EC)
- `ite8291r3.ko` — USB LED class driver (keyboard RGB, effects, per-key colors)

### Rule 2: Reference drivers are read-only
Any reference driver code (e.g. `reference/qc71_laptop/`, `reference/tuxedo-keyboard/`) is for study only and must NEVER be modified.

### Rule 3: Windows driver as reference
Windows NUC Studio data serves as the authoritative reference for EC register behavior.

### Rule 4: Project structure
```
driver/     → nuc_wmi + ite8291r3 kernel modules (C)
backend/    → Python sysfs interface + systemd daemons
ui/         → Tkinter GUI (dark indigo/gold theme)
cli.py      → Command-line interface
tools/      → Hardware probing & testing utilities
packaging/  → .desktop, .spec files
tests/      → Test scripts
docs/       → Documentation (HARDWARE_SPEC.md is authoritative)
```

### Rule 5: Hardware assumptions
The NUC X15 (LAPKC71F) HAS: lightbar, per-key RGB mechanical keyboard (ITE8291R3), CPU+dGPU fans, battery charge limit, power profiles, touchpad LED. If something doesn't work, it's a software bug.

### Rule 6: Single pkexec prompt
All sysfs writes in a single user action must be batched into ONE elevated command. Use `write_multiple()` or `batch_writes()` context manager — never multiple sequential `write_text()` calls.

### Rule 7: Progress tracking
Whenever a feature is completed, a bug is fixed, or a UI improvement is made, update `docs/NUC_STUDIO_PROGRESS.md` and `CHANGELOG.md`.

### Rule 8: Driver sysfs conventions
- Keyboard effects via sysfs: write `speed`, `color_index`, `reactive`, `direction` BEFORE writing `effect` name
- Speed/color writes do NOT re-apply the effect — only `effect` write triggers hardware update
- The `off` effect should not write speed/color (unnecessary)

### Rule 9: Daemon conventions
- Daemons are state-change-only (no polling loops for re-enforcement)
- All daemons handle suspend/resume via `/sys/power/suspend_stats/success` polling
- Keyboard daemon is observe-only for Fn+F8 (GNOME gsd-power handles the actual brightness write)
- Fan curve daemon writes PWM only when values change
- All persistent state in `/var/lib/nuc-linux-studio/`, volatile in `/tmp/`
