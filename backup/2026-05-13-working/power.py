import tkinter as tk
from tkinter import ttk
import json
import subprocess
from pathlib import Path
from backend import BackendError
from ..utils import show_message

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import cairosvg
    _CAIRO_AVAILABLE = True
except ImportError:
    _CAIRO_AVAILABLE = False

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

FAN_CURVE_STATE_PATHS = [
    Path("/var/lib/nuc-linux-studio/fan_curve_state.json"),
    Path("/tmp/nuc_fan_curve_state.json"),
]

# Profile display config: (name, icon, color)
_PROFILE_INFO = {
    0: ("🔇  Silent", "#f0c040"),
    1: ("⚖️  Balanced", "#3fb950"),
    2: ("🚀  Performance", "#8b5cf6"),
    3: ("⚡  BENCHMARK", "#ff4444"),
}


def _temp_color(temp_c):
    """Return color for temperature: blue 40-60, green 60-85, red 85-100."""
    if temp_c < 60:
        return "#58a6ff"   # blue
    elif temp_c < 85:
        return "#3fb950"   # green
    else:
        return "#ff4444"   # red


def _load_logo_from_svg(svg_path, size):
    """Load a logo from SVG at the requested size using cairosvg, falling back to PNG resize."""
    if _CAIRO_AVAILABLE and _PIL_AVAILABLE and svg_path.exists():
        try:
            import io
            png_data = cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)
            img = Image.open(io.BytesIO(png_data)).resize((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass
    # Fallback: resize PNG
    png_path = svg_path.with_suffix(".png")
    if _PIL_AVAILABLE and png_path.exists():
        try:
            img = Image.open(png_path).resize((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass
    return None


class PowerTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.refresh_job = None
        self._curve_job = None
        self._current_profile = 1
        # Per-profile fan curves: {profile_idx: {"cpu": [6 values], "dgpu": [6 values]}}
        self._profile_curves = {
            0: {"cpu": [26, 30, 35, 42, 50, 65],   "dgpu": [26, 30, 35, 42, 55, 70]},    # Silent
            1: {"cpu": [26, 30, 42, 58, 80, 100],  "dgpu": [26, 30, 42, 58, 88, 100]},   # Balanced
            2: {"cpu": [30, 40, 55, 70, 90, 100],  "dgpu": [30, 40, 55, 70, 95, 100]},   # Performance
            3: {"cpu": [100, 100, 100, 100, 100, 100], "dgpu": [100, 100, 100, 100, 100, 100]},  # Benchmark
        }
        self.create_widgets()
        self.start_refresh()

    def create_widgets(self):
        from ui import themes
        t = themes.get()
        f = self
        ttk.Label(f, text="Power & Fan Management", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 6))

        # Hardware Power Profile
        profile_frame = ttk.LabelFrame(f, text="Power Profile", padding=8)
        profile_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(profile_frame, text="Current profile (set by physical button):",
                  foreground="gray", font=("Arial", 9)).pack(anchor="w", pady=(0, 4))

        self.profile_var = tk.IntVar(value=1)
        self.profile_label = ttk.Label(profile_frame, text="⚖️  Balanced", font=("Arial", 15, "bold"))
        self.profile_label.pack(anchor="w", pady=(0, 4))

        # Benchmark toggle
        self.benchmark_var = tk.BooleanVar(value=False)
        tk.Checkbutton(profile_frame, text="Benchmark Mode (fans 100%, overrides button)",
                        variable=self.benchmark_var, command=self._on_benchmark_toggle,
                        fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                        activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                        font=("Arial", 10, "bold"),
                        bd=0, highlightthickness=0, relief="flat").pack(anchor="w", pady=(4, 0))

        # EC control toggle — release fan control to firmware
        self.ec_control_var = tk.BooleanVar(value=False)
        self._ec_control_cb = tk.Checkbutton(profile_frame,
                        text="Use firmware fan curves (disable custom fan curves)",
                        variable=self.ec_control_var, command=self._on_ec_control_toggle,
                        fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                        activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                        font=("Arial", 10, "bold"),
                        bd=0, highlightthickness=0, relief="flat")
        self._ec_control_cb.pack(anchor="w", pady=(4, 0))
        ttk.Label(profile_frame,
                  text="When enabled, the EC uses its built-in Silent/Balanced/Performance fan curves",
                  foreground="gray", font=("Arial", 9)).pack(anchor="w", padx=(24, 0))

        # Fan Curve Editor
        fan_frame = ttk.LabelFrame(f, text="Fan Curve", padding=6)
        fan_frame.pack(fill=tk.X, pady=(0, 8))

        self.fan_curve_vars = {"cpu": {}, "dgpu": {}}
        self.fan_curve_labels = {"cpu": {}, "dgpu": {}}
        self.fan_curve_sliders = {"cpu": {}, "dgpu": {}}
        self._loading_sliders = False  # Guard against cascading callbacks
        temps = [40, 50, 60, 70, 80, 90]
        min_speeds = {"cpu": {40: 26, 50: 30, 60: 42, 70: 58, 80: 80, 90: 100},
                      "dgpu": {40: 26, 50: 30, 60: 42, 70: 58, 80: 88, 90: 100}}
        self._min_speeds = min_speeds
        self._temps = temps
        self._max_rpm = {"cpu": 5780, "dgpu": 5500}

        defaults = self._profile_curves[1]

        curve_grid = ttk.Frame(fan_frame)
        curve_grid.pack(fill=tk.X, expand=True)
        curve_grid.columnconfigure(1, weight=1)
        curve_grid.columnconfigure(3, weight=1)

        ttk.Label(curve_grid, text="Temp", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=4)
        self._cpu_fan_header = ttk.Label(curve_grid, text="CPU Fan", font=("Arial", 10, "bold"), foreground=t["intel-blue"])
        self._cpu_fan_header.grid(row=0, column=1, padx=4)
        ttk.Label(curve_grid, text="RPM", font=("Arial", 9), foreground="#8b949e").grid(row=0, column=2, padx=2)
        self._dgpu_fan_header = ttk.Label(curve_grid, text="dGPU Fan", font=("Arial", 10, "bold"), foreground=t["nvidia-green"])
        self._dgpu_fan_header.grid(row=0, column=3, padx=4)
        ttk.Label(curve_grid, text="RPM", font=("Arial", 9), foreground="#8b949e").grid(row=0, column=4, padx=2)

        for i, temp in enumerate(temps):
            cpu_min = min_speeds["cpu"][temp]
            dgpu_min = min_speeds["dgpu"][temp]
            ttk.Label(curve_grid, text=f"{temp}°C", font=("Arial", 10)).grid(row=i+1, column=0, padx=4, pady=2)

            cpu_var = tk.IntVar(value=defaults["cpu"][i])
            cpu_slider = tk.Scale(curve_grid, from_=cpu_min, to=100, orient=tk.HORIZONTAL,
                                  variable=cpu_var, length=220, sliderlength=40, width=22, showvalue=False,
                                  bg=t["scale_bg"], fg=t["intel-blue"], troughcolor=t["scale_trough"], highlightthickness=0,
                                  activebackground=t["intel-blue"],
                                  repeatdelay=150, repeatinterval=50,
                                  command=lambda v, _t=temp, var=cpu_var, ch="cpu": self._on_curve_change(_t, ch, var))
            cpu_slider.grid(row=i+1, column=1, padx=4, pady=2, sticky="ew")
            cpu_lbl = ttk.Label(curve_grid, text=f"~{int(defaults['cpu'][i] * self._max_rpm['cpu'] / 100)}", width=6, foreground=t["intel-blue"])
            cpu_lbl.grid(row=i+1, column=2, padx=2)
            self.fan_curve_vars["cpu"][temp] = cpu_var
            self.fan_curve_labels["cpu"][temp] = cpu_lbl
            self.fan_curve_sliders["cpu"][temp] = cpu_slider

            dgpu_var = tk.IntVar(value=defaults["dgpu"][i])
            dgpu_slider = tk.Scale(curve_grid, from_=dgpu_min, to=100, orient=tk.HORIZONTAL,
                                   variable=dgpu_var, length=220, sliderlength=40, width=22, showvalue=False,
                                   bg=t["scale_bg"], fg=t["nvidia-green"], troughcolor=t["scale_trough"], highlightthickness=0,
                                   activebackground=t["nvidia-green"],
                                   repeatdelay=150, repeatinterval=50,
                                   command=lambda v, _t=temp, var=dgpu_var, ch="dgpu": self._on_curve_change(_t, ch, var))
            dgpu_slider.grid(row=i+1, column=3, padx=4, pady=2, sticky="ew")
            dgpu_lbl = ttk.Label(curve_grid, text=f"~{int(defaults['dgpu'][i] * self._max_rpm['dgpu'] / 100)}", width=6, foreground=t["nvidia-green"])
            dgpu_lbl.grid(row=i+1, column=4, padx=2)
            self.fan_curve_vars["dgpu"][temp] = dgpu_var
            self.fan_curve_labels["dgpu"][temp] = dgpu_lbl
            self.fan_curve_sliders["dgpu"][temp] = dgpu_slider

        # Curve canvas
        from ui import themes
        t_init = themes.get()
        self.curve_canvas = tk.Canvas(fan_frame, height=370, bg=t_init["canvas_bg"], highlightthickness=1, highlightbackground=t_init["border"])
        self.curve_canvas.pack(fill=tk.X, pady=(12, 6))
        self.curve_canvas.bind("<Configure>", lambda e: self._draw_curve())
        self._draw_curve()

        # System Status — compact horizontal layout with 2x sized text/icons
        status_frame = ttk.LabelFrame(f, text="Live System Status", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 8))

        self.sensors_frame = ttk.Frame(status_frame)
        self.sensors_frame.pack(fill=tk.X, pady=(0, 4))
        self.sensors_frame.columnconfigure(0, weight=1)
        self.sensors_frame.columnconfigure(1, weight=1)

        # CPU (left side) — 2x sizes
        cpu_row = ttk.Frame(self.sensors_frame)
        cpu_row.grid(row=0, column=0, sticky="w", padx=4, pady=10)

        # Intel logo + label badge — 2x logo (72px)
        self._intel_photo = None
        self._cpu_badge = tk.Frame(cpu_row, bg=t["intel-blue"], padx=6, pady=6)
        cpu_badge = self._cpu_badge
        cpu_badge.pack(side=tk.LEFT, padx=(0, 14))
        intel_svg = _ASSETS_DIR / "intel_logo.svg"
        self._intel_photo = _load_logo_from_svg(intel_svg, 72)
        if self._intel_photo:
            tk.Label(cpu_badge, image=self._intel_photo, bg=t["intel-blue"]).pack(side=tk.LEFT, padx=(2, 6), pady=2)
        tk.Label(cpu_badge, text=" intel ", bg=t["intel-blue"], fg="white",
                 font=("Arial", 20, "bold italic")).pack(side=tk.LEFT, padx=(0, 6), pady=2)

        self.cpu_temp_lbl = ttk.Label(cpu_row, text="-- °C", font=("Arial", 26, "bold"))
        self.cpu_temp_lbl.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(cpu_row, text="🌀", font=("Arial", 24)).pack(side=tk.LEFT, padx=(0, 4))
        self.cpu_rpm_lbl = ttk.Label(cpu_row, text="-- RPM", font=("Arial", 22), foreground=t["intel-blue"])
        self.cpu_rpm_lbl.pack(side=tk.LEFT, padx=(0, 12))
        self.cpu_pwm_lbl = ttk.Label(cpu_row, text="-- %", foreground="gray", font=("Arial", 16))
        self.cpu_pwm_lbl.pack(side=tk.LEFT)

        # dGPU (right side) — 2x sizes
        gpu_row = ttk.Frame(self.sensors_frame)
        gpu_row.grid(row=0, column=1, sticky="e", padx=4, pady=10)

        # NVIDIA logo + label badge — 2x logo (72px)
        self._nvidia_photo = None
        self._gpu_badge = tk.Frame(gpu_row, bg=t["nvidia-green"], padx=6, pady=6)
        gpu_badge = self._gpu_badge
        gpu_badge.pack(side=tk.LEFT, padx=(0, 14))
        nvidia_svg = _ASSETS_DIR / "nvidia_logo.svg"
        self._nvidia_photo = _load_logo_from_svg(nvidia_svg, 72)
        if self._nvidia_photo:
            tk.Label(gpu_badge, image=self._nvidia_photo, bg=t["nvidia-green"]).pack(side=tk.LEFT, padx=(2, 6), pady=2)
        tk.Label(gpu_badge, text=" nVIDIA ", bg=t["nvidia-green"], fg="black",
                 font=("Arial", 20, "bold")).pack(side=tk.LEFT, padx=(0, 6), pady=2)
        self.dgpu_temp_lbl = ttk.Label(gpu_row, text="-- °C", font=("Arial", 26, "bold"))
        self.dgpu_temp_lbl.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(gpu_row, text="🌀", font=("Arial", 24)).pack(side=tk.LEFT, padx=(0, 4))
        self.dgpu_rpm_lbl = ttk.Label(gpu_row, text="-- RPM", font=("Arial", 22), foreground=t["nvidia-green"])
        self.dgpu_rpm_lbl.pack(side=tk.LEFT, padx=(0, 12))
        self.dgpu_pwm_lbl = ttk.Label(gpu_row, text="-- %", foreground="gray", font=("Arial", 16))
        self.dgpu_pwm_lbl.pack(side=tk.LEFT)

        self.status_error_lbl = ttk.Label(status_frame, text="", foreground="red", wraplength=500)

        self.auto_refresh_var = tk.BooleanVar(value=True)

        # Load initial profile from hardware
        if self.app.backend:
            current = self.app.backend.get_power_profile()
            if current is not None and current != 3:
                self._current_profile = current
                self.profile_var.set(current)
                self._load_curve_to_sliders(current)
                info = _PROFILE_INFO.get(current, ("Balanced", "#3fb950"))
                self.profile_label.config(text=info[0], foreground=info[1])

    def _update_profile_label(self, profile_idx):
        info = _PROFILE_INFO.get(profile_idx, ("Balanced", "#3fb950"))
        self.profile_label.config(text=info[0], foreground=info[1])

    def cycle_profile(self):
        if self.benchmark_var.get():
            return
        self.after(500, self._read_and_apply_profile)

    def _read_and_apply_profile(self):
        self._save_sliders_to_profile(self._current_profile)
        new_profile = None
        if self.app.backend:
            new_profile = self.app.backend.get_power_profile()
        if new_profile is None or new_profile == 3:
            return
        if new_profile == self._current_profile:
            return
        self._current_profile = new_profile
        self.profile_var.set(new_profile)
        self._load_curve_to_sliders(new_profile)
        self._persist_fan_curve_state()
        self._update_profile_label(new_profile)
        info = _PROFILE_INFO.get(new_profile, ("Balanced", "#3fb950"))
        self.app.status_var.set(f"Profile: {info[0]}")
        if not getattr(self.app, 'is_loading', False):
            self.app.save_config()

    def _on_benchmark_toggle(self):
        if self.benchmark_var.get():
            self._save_sliders_to_profile(self._current_profile)
            self._current_profile = 3
            self.profile_var.set(3)
            self._load_curve_to_sliders(3)
            self._persist_fan_curve_state()
            if self.app.backend:
                try:
                    self.app.backend.apply_fan_override(100, 100)
                except Exception:
                    pass
            self._update_profile_label(3)
            self.app.status_var.set("Benchmark mode ON — fans at 100%")
        else:
            hw_profile = 1
            if self.app.backend:
                p = self.app.backend.get_power_profile()
                if p is not None and p != 3:
                    hw_profile = p
            self._save_sliders_to_profile(self._current_profile)
            self._current_profile = hw_profile
            self.profile_var.set(hw_profile)
            self._load_curve_to_sliders(hw_profile)
            self._persist_fan_curve_state()
            self._update_profile_label(hw_profile)
            info = _PROFILE_INFO.get(hw_profile, ("Balanced", "#3fb950"))
            self.app.status_var.set(f"Benchmark OFF — back to {info[0]}")
        if not getattr(self.app, 'is_loading', False):
            self.app.save_config()

    def _on_ec_control_toggle(self):
        """Toggle between custom fan curves and EC firmware control."""
        ec_mode = self.ec_control_var.get()
        if ec_mode:
            # Disable custom fan curves — tell daemon to release control
            self.benchmark_var.set(False)
            self._persist_fan_curve_state()  # writes enabled=False when ec_mode
            # Directly clear manual mode + PWM enables so EC takes over immediately
            for path_str in ("/sys/devices/platform/nuc_wmi/manual_control",
                             "/sys/devices/platform/qc71_laptop/manual_control"):
                p = Path(path_str)
                if p.exists():
                    try:
                        p.write_text("0")
                    except Exception:
                        pass
                    break
            # Reset PWM channels to auto
            for hwmon_base in [Path("/sys/devices/platform/nuc_wmi/hwmon"),
                               Path("/sys/devices/platform/qc71_laptop/hwmon")]:
                if not hwmon_base.exists():
                    continue
                for entry in sorted(hwmon_base.iterdir()):
                    if entry.is_dir() and entry.name.startswith("hwmon"):
                        for pwm_en in ["pwm1_enable", "pwm2_enable"]:
                            p = entry / pwm_en
                            if p.exists():
                                try:
                                    p.write_text("0")
                                except Exception:
                                    pass
                        break
            self.app.status_var.set("Fan control released to EC firmware")
        else:
            # Re-enable custom fan curves
            self._persist_fan_curve_state()
            self.app.status_var.set("Custom fan curves re-enabled")
        if not getattr(self.app, 'is_loading', False):
            self.app.save_config()

    def _save_sliders_to_profile(self, profile_idx):
        for i, temp in enumerate(self._temps):
            self._profile_curves[profile_idx]["cpu"][i] = self.fan_curve_vars["cpu"][temp].get()
            self._profile_curves[profile_idx]["dgpu"][i] = self.fan_curve_vars["dgpu"][temp].get()

    def _load_curve_to_sliders(self, profile_idx):
        self._loading_sliders = True
        curve = self._profile_curves[profile_idx]
        for i, temp in enumerate(self._temps):
            for ch in ["cpu", "dgpu"]:
                val = max(curve[ch][i], self._min_speeds[ch][temp])
                self.fan_curve_vars[ch][temp].set(val)
                rpm = int(val * self._max_rpm[ch] / 100)
                self.fan_curve_labels[ch][temp].config(text=f"~{rpm}")
        self._loading_sliders = False
        if hasattr(self, '_curve_job') and self._curve_job:
            self.after_cancel(self._curve_job)
        self._curve_job = self.after(100, self._draw_curve)

    def _on_curve_change(self, temp, channel, var):
        if self._loading_sliders:
            return
        val = var.get()
        floor = self._min_speeds[channel].get(temp, 0)
        if val < floor:
            val = floor
            var.set(val)
        rpm = int(val * self._max_rpm[channel] / 100)
        self.fan_curve_labels[channel][temp].config(text=f"~{rpm}")

        temps = sorted(self.fan_curve_vars[channel].keys())
        idx = temps.index(temp)
        for i in range(idx):
            lower_var = self.fan_curve_vars[channel][temps[i]]
            if lower_var.get() > val:
                lower_var.set(val)
                self.fan_curve_labels[channel][temps[i]].config(text=f"~{int(val * self._max_rpm[channel] / 100)}")
        for i in range(idx + 1, len(temps)):
            higher_var = self.fan_curve_vars[channel][temps[i]]
            if higher_var.get() < val:
                higher_var.set(val)
                self.fan_curve_labels[channel][temps[i]].config(text=f"~{int(val * self._max_rpm[channel] / 100)}")

        if self._curve_job:
            self.after_cancel(self._curve_job)
        self._curve_job = self.after(150, self._curve_deferred_update)

    def _curve_deferred_update(self):
        self._curve_job = None
        self._draw_curve()
        self._save_sliders_to_profile(self._current_profile)
        self._persist_fan_curve_state()
        if not getattr(self.app, 'is_loading', False):
            self.app.save_config()

    def _persist_fan_curve_state(self):
        ec_mode = self.ec_control_var.get()
        payload = {
            "enabled": not ec_mode,
            "benchmark": bool(self.benchmark_var.get()) if not ec_mode else False,
            "current_profile": int(self._current_profile),
            "profile_curves": {str(k): v for k, v in self._profile_curves.items()},
        }
        for path in FAN_CURVE_STATE_PATHS:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload), encoding="utf-8")
                return
            except Exception:
                continue

    def _apply_curve_for_current_temp(self):
        if not self.app.backend or not self.app.backend._fans:
            return
        try:
            fs = self.app.backend.get_fan_status()
            cpu_temp = fs.get("CPU", {}).get("temperature_mC", 50000) / 1000
            dgpu_temp = fs.get("dGPU", {}).get("temperature_mC", 50000) / 1000
            cpu_pct = self._interpolate_curve("cpu", cpu_temp)
            dgpu_pct = self._interpolate_curve("dgpu", dgpu_temp)
            self.app.backend.apply_fan_override(cpu_pct, dgpu_pct)
        except Exception:
            pass

    def _interpolate_curve(self, channel, temp):
        temps = sorted(self.fan_curve_vars[channel].keys())
        if temp <= temps[0]:
            return self.fan_curve_vars[channel][temps[0]].get()
        if temp >= temps[-1]:
            return self.fan_curve_vars[channel][temps[-1]].get()
        for i in range(len(temps) - 1):
            if temps[i] <= temp <= temps[i+1]:
                t0, t1 = temps[i], temps[i+1]
                v0 = self.fan_curve_vars[channel][t0].get()
                v1 = self.fan_curve_vars[channel][t1].get()
                ratio = (temp - t0) / (t1 - t0)
                return max(int(v0 + ratio * (v1 - v0)), self._min_speeds[channel].get(int(temp), 0))
        return 100

    def _draw_curve(self):
        c = self.curve_canvas
        c.delete("all")
        w = max(c.winfo_width(), 400)
        h = max(c.winfo_height(), 300)
        pad_l, pad_b, pad_t, pad_r = 62, 90, 28, 80

        temps = sorted(self.fan_curve_vars["cpu"].keys())
        temp_min, temp_max = temps[0], temps[-1]

        max_rpm = max(self._max_rpm["cpu"], self._max_rpm["dgpu"])
        rpm_ticks = [0, 1000, 2000, 3000, 4000, 5000]

        def tx(t): return pad_l + (t - temp_min) / (temp_max - temp_min) * (w - pad_l - pad_r)
        def ty(pct): return (h - pad_b) - (pct / 100) * (h - pad_b - pad_t)
        def ty_rpm(rpm): return (h - pad_b) - (rpm / max_rpm) * (h - pad_b - pad_t)

        from ui import themes
        th = themes.get()
        is_light = th["name"] == "light"

        for i in range(5):
            y0 = pad_t + i * (h - pad_b - pad_t) / 5
            y1 = pad_t + (i + 1) * (h - pad_b - pad_t) / 5
            base = th["curve_band_base"]
            step = th["curve_band_step"]
            shade = f"#{max(0,min(base[0]+i*step[0],255)):02x}{max(0,min(base[1]+i*step[1],255)):02x}{max(0,min(base[2]+i*step[2],255)):02x}"
            c.create_rectangle(pad_l, y0, w - pad_r, y1, fill=shade, outline="")

        grid_color = th["curve_grid"]
        text_color = th["curve_text"]

        intel = th["intel-blue"]
        nvidia = th["nvidia-green"]

        for t in temps:
            x = tx(t)
            c.create_line(x, pad_t, x, h - pad_b, fill=grid_color, width=1)
            c.create_text(x, h - pad_b + 18, text=f"{t}°C", fill=intel, font=("Segoe UI", 9))
        for rpm in rpm_ticks:
            y = ty_rpm(rpm)
            c.create_line(pad_l, y, w - pad_r, y, fill=grid_color, width=1)
            lbl = f"{rpm//1000}k" if rpm >= 1000 else str(rpm)
            c.create_text(pad_l - 24, y, text=lbl, fill=nvidia, font=("Segoe UI", 9))

        cpu_points = [(tx(t), ty(self.fan_curve_vars["cpu"][t].get())) for t in temps]
        dgpu_points = [(tx(t), ty(self.fan_curve_vars["dgpu"][t].get())) for t in temps]

        cpu_fill = [cpu_points[0]] + cpu_points + [cpu_points[-1], (cpu_points[-1][0], h - pad_b), (cpu_points[0][0], h - pad_b)]
        c.create_polygon(cpu_fill, fill=th["curve_cpu_fill"], outline="")
        dgpu_fill = [dgpu_points[0]] + dgpu_points + [dgpu_points[-1], (dgpu_points[-1][0], h - pad_b), (dgpu_points[0][0], h - pad_b)]
        c.create_polygon(dgpu_fill, fill=th["curve_dgpu_fill"], outline="")

        for i in range(len(cpu_points) - 1):
            c.create_line(cpu_points[i][0], cpu_points[i][1], cpu_points[i+1][0], cpu_points[i+1][1],
                         fill=intel, width=3, smooth=True, splinesteps=36, capstyle=tk.ROUND)
        for pt in cpu_points:
            c.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5, fill=intel, outline=th["curve_dot_outline"], width=2)

        for i in range(len(dgpu_points) - 1):
            c.create_line(dgpu_points[i][0], dgpu_points[i][1], dgpu_points[i+1][0], dgpu_points[i+1][1],
                         fill=nvidia, width=3, smooth=True, splinesteps=36, capstyle=tk.ROUND)
        for pt in dgpu_points:
            c.create_oval(pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5, fill=nvidia, outline=th["curve_dot_outline"], width=2)

        c.create_text(w // 2, h - pad_b + 40, text="Temperature (°C)", fill=intel, font=("Segoe UI", 9))
        c.create_text(14, h // 2, text="RPM", fill=nvidia, font=("Segoe UI", 9), angle=90)
        # CPU label: positioned just above the CPU line at the second point
        cpu_label_x = cpu_points[1][0]
        cpu_label_y = cpu_points[1][1] - 16
        c.create_oval(cpu_label_x - 4, cpu_label_y - 4, cpu_label_x + 4, cpu_label_y + 4, fill=intel, outline="")
        c.create_text(cpu_label_x + 10, cpu_label_y, text="CPU", fill=intel, font=("Segoe UI", 9, "bold"), anchor="w")
        # dGPU label: positioned just above the dGPU line at the 4th point
        dgpu_label_x = dgpu_points[3][0]
        dgpu_label_y = dgpu_points[3][1] - 16
        c.create_oval(dgpu_label_x - 4, dgpu_label_y - 4, dgpu_label_x + 4, dgpu_label_y + 4, fill=nvidia, outline="")
        c.create_text(dgpu_label_x + 10, dgpu_label_y, text="dGPU", fill=nvidia, font=("Segoe UI", 9, "bold"), anchor="w")

    def update_status(self):
        if not self.app.backend:
            self.update_live_display(None, "Backend unavailable")
            return
        try:
            fs = self.app.backend.get_fan_status()
            self.update_live_display(fs)
            if not self.benchmark_var.get():
                current = self.app.backend.get_power_profile()
                if current is not None and current != self._current_profile and current != 3:
                    self._save_sliders_to_profile(self._current_profile)
                    self._current_profile = current
                    self.profile_var.set(current)
                    self._load_curve_to_sliders(current)
                    self._persist_fan_curve_state()
                    self._update_profile_label(current)
        except BackendError as exc:
            self.update_live_display(None, str(exc))

    def update_live_display(self, status, error=None):
        if error:
            self.status_error_lbl.config(text=f"Error:\n{error}")
            self.status_error_lbl.pack(fill=tk.X, pady=4)
        else:
            self.status_error_lbl.pack_forget()

        if status:
            if "CPU" in status:
                cpu = status["CPU"]
                temp_c = cpu['temperature_mC'] / 1000
                # Sanity clamp: EC temps should be 0-120°C; anything higher is corrupt data
                temp_c = max(0, min(temp_c, 120))
                self.cpu_temp_lbl.config(text=f"{temp_c:.1f} °C", foreground=_temp_color(temp_c))
                self.cpu_rpm_lbl.config(text=f"{cpu['fan_rpm']} RPM", foreground="#0071C5")
                self.cpu_pwm_lbl.config(text=f"{round(cpu['pwm_value'] * 100 / 255)}%")
            if "dGPU" in status:
                dgpu = status["dGPU"]
                temp_c = dgpu['temperature_mC'] / 1000
                # Sanity clamp: EC temps should be 0-120°C; anything higher is corrupt data
                temp_c = max(0, min(temp_c, 120))
                self.dgpu_temp_lbl.config(text=f"{temp_c:.1f} °C", foreground=_temp_color(temp_c))
                self.dgpu_rpm_lbl.config(text=f"{dgpu['fan_rpm']} RPM", foreground="#76B900")
                self.dgpu_pwm_lbl.config(text=f"{round(dgpu['pwm_value'] * 100 / 255)}%")
        elif not error:
            self.status_error_lbl.config(text="No fan data available.")
            self.status_error_lbl.pack(fill=tk.X, pady=4)

    def toggle_refresh(self):
        if self.refresh_job: self.after_cancel(self.refresh_job)
        if self.auto_refresh_var.get(): self.start_refresh()

    def start_refresh(self):
        if self.auto_refresh_var.get():
            self.update_status()
            self.refresh_job = self.after(2000, self.start_refresh)

    def apply_theme(self):
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()
        # Curve canvas
        self.curve_canvas.configure(bg=t["canvas_bg"], highlightbackground=t["border"])
        # Intel / Nvidia badge frames and their child labels
        for badge, color in [(self._cpu_badge, t["intel-blue"]), (self._gpu_badge, t["nvidia-green"])]:
            badge.configure(bg=color)
            for child in badge.winfo_children():
                if child.winfo_class() == "Label":
                    child.configure(bg=color)
        # RPM labels — force branded foreground directly (ttk styles are unreliable)
        self.cpu_rpm_lbl.configure(foreground=t["intel-blue"])
        self.dgpu_rpm_lbl.configure(foreground=t["nvidia-green"])
        # Fan curve headers
        self._cpu_fan_header.configure(foreground=t["intel-blue"])
        self._dgpu_fan_header.configure(foreground=t["nvidia-green"])
        # Fan curve sliders
        for ch, sliders in self.fan_curve_sliders.items():
            color = t["intel-blue"] if ch == "cpu" else t["nvidia-green"]
            for slider in sliders.values():
                slider.configure(bg=t["scale_bg"], troughcolor=t["scale_trough"],
                                 fg=color, activebackground=color)
        # Fan curve RPM labels — force branded foreground directly
        for ch, labels in self.fan_curve_labels.items():
            color = t["intel-blue"] if ch == "cpu" else t["nvidia-green"]
            for lbl in labels.values():
                lbl.configure(foreground=color)
        # Benchmark checkbox
        for child in self.winfo_children():
            if hasattr(child, 'winfo_children'):
                for w in child.winfo_children():
                    if w.winfo_class() == "Checkbutton":
                        w.configure(fg=t["radio_fg"], bg=t["radio_bg"],
                                    selectcolor=t["radio_bg"],
                                    activebackground=t["radio_bg"],
                                    activeforeground=t["radio_fg"])
        # Redraw curve
        self._draw_curve()

    def get_state(self):
        self._save_sliders_to_profile(self._current_profile)
        return {
            "profile_curves": {str(k): v for k, v in self._profile_curves.items()},
            "current_profile": self._current_profile,
            "benchmark": self.benchmark_var.get(),
            "ec_fan_control": self.ec_control_var.get(),
        }

    def load_state(self, data, restore_profile=True):
        if "profile_curves" in data:
            for k_str, curves in data["profile_curves"].items():
                k = int(k_str)
                if k in self._profile_curves:
                    for ch in ["cpu", "dgpu"]:
                        if ch in curves:
                            self._profile_curves[k][ch] = curves[ch]

        hw_profile = 1
        if self.app.backend:
            p = self.app.backend.get_power_profile()
            if p is not None and p != 3:
                hw_profile = p

        benchmark = data.get("benchmark", False)
        self.benchmark_var.set(benchmark)

        ec_mode = data.get("ec_fan_control", False)
        self.ec_control_var.set(ec_mode)

        if benchmark:
            self._current_profile = 3
            self.profile_var.set(3)
            self._update_profile_label(3)
        else:
            self._current_profile = hw_profile
            self.profile_var.set(hw_profile)
            self._update_profile_label(hw_profile)

        self._load_curve_to_sliders(self._current_profile)

        if restore_profile:
            self._persist_fan_curve_state()

