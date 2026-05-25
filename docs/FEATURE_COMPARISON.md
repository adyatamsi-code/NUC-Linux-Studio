# Intel NUC Software Studio Replica - Feature Comparison

This table compares the original Intel NUC Software Studio (for the NUC X15 Laptop Kit LAPKC71F) with the open-source NUC Linux Studio replacement.

## Resource Impact Analysis

The **Est. Impact** column represents an estimated breakdown of the CPU and Memory footprint relative to the entire application ecosystem (daemons, UI, driver) running at peak. The total of all implemented and estimated planned features adds up exactly to 100%.

* **0%**: Handled entirely by the Embedded Controller (EC) or ITE8291R3 USB controller hardware. Zero host CPU overhead.
* **0.5 - 1.5%**: Simple intermittent sysfs writes, minor UI components, or infrequent WMI event triggers.
* **2 - 6%**: Python background daemons doing periodic polling (e.g. `fan-curve.service`, `touchpad-led.service`, `kbd-brightness.service`), or moderate UI canvas rendering.
* **10 - 38%**: Heavy computational tasks. For example, `kbd-audio.service` performs continuous audio capture, Numpy FFT analysis, and 30fps USB data streaming, representing the single largest computational footprint.

| Feature | Original Intel NUC Studio (Windows) | NUC Linux Studio | Est. Impact | Status / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Power & Performance** | | | | |
| Power Profiles (Silent, Balanced, Performance) | ✅ Yes | ✅ Yes | 0.5% | Works natively via EC |
| Benchmark Mode (Max Fans) | ✅ Yes | ✅ Yes | 0.5% | App-enforced |
| Profile Selection via App | ✅ Yes | ✅ Yes | 0.5% | |
| Profile Selection via Hardware Button | ✅ Yes | ✅ Yes | 0.5% | Syncs reliably |
| Live System Monitor (Temps, RPM, PWM) | ✅ Yes | ✅ Yes | 10% | Frequent UI polling (2s) & Canvas rendering |
| **Fan Control** | | | | |
| Automatic Control | ✅ Yes | ✅ Yes | 0% | EC-managed (Zero host CPU) |
| Manual Fan Sliders | ✅ Yes | ✅ Yes | 0.5% | |
| Custom Fan Curves | ✅ Yes | ✅ Yes | 6% | `fan-curve.service` daemon; sliders 35–85°C CPU+GPU; alternating row shading, distinct CPU(blue)/GPU(green) trough colors, GPU temp labels |
| **Battery Health** | | | | |
| Charge Limits | ✅ Yes (60%, 80%, 100%) | ✅ Yes (60%, 80%, 100%) | 0.5% | Supported via sysfs |
| Charge Limit Enforced at Boot | ✅ Yes | ✅ Yes | 0% | `nuc-battery-limit.service` (Type=oneshot) applies saved limit on every boot |
| Battery Health Display | ✅ Yes | ✅ Yes | 1% | UI gauge rendering |
| **Keyboard Backlight (ITE8291R3)** | | | | |
| Static / Monocolor Mode | ✅ Yes | ✅ Yes | 0.5% | |
| Brightness Control (Fn+F8) | ✅ Yes | ✅ Yes | 4% | Handled by GNOME + `kbd-brightness.service` daemon |
| Per-Key RGB Customization | ✅ Yes | ✅ Yes | 1.5% | Direct USB row data, mostly idle memory |
| Built-in Animations (Breathing, Wave, Ripple, Aurora, Fireworks, Raindrop, Marquee, Random) | ✅ Yes | ✅ Yes | 0% | Hardware effects (Zero host CPU) |
| Effect Customization (Speed, Color, Direction) | ✅ Yes | ✅ Yes | 0.5% | Supported via hardware |
| Reactive Keypress Effects | ✅ Yes | ✅ Yes | 0% | Hardware-driven |
| Hardware Audio Sync | ✅ Yes | ❌ Partial | 38% | Linux uses software FFT daemon (`kbd-audio.service`) |
| Custom Effect Storage | ✅ Yes | ✅ Yes | 0.5% | Per-effect: color, brightness, speed, direction saved and restored independently |
| Per-Key Color Palette (Multi-Zone) | ✅ Yes | ✅ Yes | 0.5% | Left-click select, right-click deselect, Deselect button preserves colors |
| Audio Effect Canvas Preview | ✅ Yes | ✅ Yes | 0% | Rainbow: column-based hue gradient; Single color: solid fill; static preview, zero CPU |
| Software Keyboard Themes | ❌ No | ✅ Yes | 0.5% | Gaming (4-tier red), Coding (orange/teal/green), Writing (indigo/yellow), Glow (single color+brightness) |
| True Palette Colors | ✅ Yes | ❌ No | 0% | ITE8291R3 firmware bug; palette is ROM-locked |
| Separate AC/Battery Profiles | ✅ Yes | ❌ No | 2% (est.) | Would require AC polling daemon |
| **Front Lightbar** | | | | |
| Static Monocolor Mode | ✅ Yes | ✅ Yes | 0.5% | PWM limited by EC to 25-35% |
| Rainbow Animation | ✅ Yes | ✅ Yes | 0% | Static gradient in hardware |
| Scrolling/Dynamic Rainbow | ✅ Yes | ✅ Yes | 10% | Software-driven hue cycle ~30fps via `LightbarController._start_dynamic_rainbow()` |
| Breathing Mode | ✅ Yes | ❌ No | 0% | Doesn't function correctly on this EC firmware |
| Separate AC/Battery Profiles | ✅ Yes | ❌ No | 2% (est.) | Would require AC polling daemon |
| Graphical Lightbar UI | ✅ Yes | ✅ Yes | 1.5% | Canvas preview with calibrated R+G swatches |
| Hardware Reset Button | ✅ Yes | ✅ Yes | 0.5% | Sends EC clear/flush commands to reset lightbar |
| **Hardware Toggles** | | | | |
| Touchpad Toggle (Fn+F7) | ✅ Yes | ✅ Yes | 4% | Emits event, tracked by `touchpad-led.service` |
| App UI Touchpad State Tracking | ✅ Yes | ✅ Yes | 1% | Interactive toggle switch + polling |
| Super/Windows Key Lock (Fn+F2) | ✅ Yes | ✅ Yes | 0.5% | Supported |
| Fn Lock (Fn+Esc) | ✅ Yes | ✅ Yes | 0.5% | Supported |
| Mic Mute Toggle | ✅ Yes | ✅ Yes | 0.5% | Emits standard keyboard event |
| **Other Features** | | | | |
| Face Unlock Setup | ✅ Yes (Windows Hello) | ✅ Yes (Howdy) | 6% | Spawns Howdy and OpenCV camera preview |
| UI Theme | Light/Dark | Dark/Light | 4% | Indigo/Gold (dark) + Ivory/Sky-Blue (light), full toggle |
| On-Screen Display (OSD) Overlay | ✅ Yes | ✅ Yes | 2.5% | GTK3 GNOME-style pill popup per monitor; caps-lock, touchpad, mic, airplane, kbd-brightness, perf-mode, screen-brightness, thermal-boost, lightbar, fan-boost; GNOME-style `rgba(12,12,12,0.72)` bg, 24px radius, 3px accent bar, Cairo radial shadow vignette |
