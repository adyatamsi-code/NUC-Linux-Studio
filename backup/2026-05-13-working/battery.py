import tkinter as tk
from tkinter import ttk
from backend import BackendError
from ..utils import show_message

class BatteryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.charge_limit_var = tk.IntVar(value=80)
        self._slide_job = None
        self._cached_capacity = 0
        self.create_widgets()
        # Defer initial status read so tab appears instantly
        self.after(100, self.update_status)

    def _get_theme(self):
        from ui import themes
        return themes.get()

    def create_widgets(self):
        t = self._get_theme()
        ttk.Label(self, text="Battery Health Management", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 20))

        # Main horizontal layout
        main_row = ttk.Frame(self)
        main_row.pack(fill=tk.BOTH, expand=True)

        # Left side: Giant Battery Icon
        gauge_frame = ttk.Frame(main_row)
        gauge_frame.pack(side=tk.LEFT, anchor="n", padx=(0, 20))

        # Widen the canvas significantly so text doesn't get cut off on the right, matches frame bg
        self.gauge_canvas = tk.Canvas(gauge_frame, width=740, height=700, bg=t["battery_gauge_bg"], highlightthickness=0)
        self.gauge_canvas.pack()

        # Right side: Information and Controls
        info_frame = ttk.Frame(main_row)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Current status
        status_top = ttk.Frame(info_frame)
        status_top.pack(fill=tk.X, pady=(0, 24))
        self.capacity_label = ttk.Label(status_top, text="--%", font=("Arial", 36, "bold"), foreground=t["battery_pct_fg"])
        self.capacity_label.pack(side=tk.LEFT)
        
        status_text_frame = ttk.Frame(status_top)
        status_text_frame.pack(side=tk.LEFT, padx=16, fill=tk.Y)
        self.status_label = ttk.Label(status_text_frame, text="Status Unknown", font=("Arial", 14))
        self.status_label.pack(anchor="w", pady=(4, 0))
        self.battery_info = ttk.Label(status_text_frame, text="Path: unknown", font=("Arial", 10), foreground="gray")
        self.battery_info.pack(anchor="w", pady=(4, 0))

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 24))

        # Charge Limit Slider (Themed like NUC Studio)
        ttk.Label(info_frame, text="Charge Limit", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(info_frame, text="Set maximum charge percentage to extend battery lifespan.", font=("Arial", 11), foreground="gray").pack(anchor="w", pady=(0, 16))

        slider_frame = ttk.Frame(info_frame)
        slider_frame.pack(fill=tk.X, pady=(0, 12))

        # Slider spanning safe 20-100%
        self.charge_slider = tk.Scale(slider_frame, from_=20, to=100, orient=tk.HORIZONTAL,
                                       variable=self.charge_limit_var, command=self.on_slide,
                                       length=400, sliderlength=30, width=20, showvalue=False,
                                       bg=t["scale_bg"], fg=t["scale_fg"], troughcolor=t["scale_trough"],
                                       highlightthickness=0, activebackground=t["scale_active"],
                                       repeatdelay=150, repeatinterval=50)
        self.charge_slider.pack(side=tk.LEFT)
        
        self.charge_value_label = ttk.Label(slider_frame, text="80%", font=("Arial", 14, "bold"), foreground=t["battery_pct_fg"])
        self.charge_value_label.pack(side=tk.LEFT, padx=(16, 0))

        # Tick marks for context
        ticks_frame = ttk.Frame(info_frame)
        ticks_frame.pack(fill=tk.X, pady=(0, 24))
        # Adjust tick marks to roughly match the 20-100 scale on a 400px wide slider
        ttk.Label(ticks_frame, text="20%", font=("Arial", 9), foreground="gray").place(x=10, y=0)
        ttk.Label(ticks_frame, text="60%", font=("Arial", 9), foreground="gray").place(x=195, y=0, anchor="n")
        ttk.Label(ticks_frame, text="100%", font=("Arial", 9), foreground="gray").place(x=380, y=0)
        # Placeholder to give the frame height
        ttk.Label(ticks_frame, text=" ").pack()


    def _draw_gauge(self, capacity, limit):
        """Draws a massive, clean battery icon with 20 bars of 5% increments, 2x scale."""
        from ui import themes
        t = themes.get()
        c = self.gauge_canvas
        c.delete("all")
        
        # 2x scaled dimensions — centered with generous left margin for text
        cx, cy = 340, 340
        bw, bh = 300, 520
        x1 = cx - bw/2
        y1 = cy - bh/2
        x2 = cx + bw/2
        y2 = cy + bh/2
        
        # Battery terminal
        term_w = 140
        term_h = 50
        c.create_rectangle(cx - term_w/2, y1 - term_h, cx + term_w/2, y1, fill="#555", outline="#444")
        
        # Battery outline
        c.create_rectangle(x1, y1, x2, y2, outline="#555", width=10, fill=t["battery_body_bg"])

        # Draw 20 bars of 5% increments inside the battery
        bar_pad = 12  # padding from battery wall
        bar_gap = 4   # gap between bars
        bar_area_top = y1 + bar_pad
        bar_area_bot = y2 - bar_pad
        total_bar_height = bar_area_bot - bar_area_top
        num_bars = 20
        bar_h = (total_bar_height - (num_bars - 1) * bar_gap) / num_bars
        empty_color = t["battery_empty_bar"]

        for i in range(num_bars):
            # Bar 0 = top (95-100%), bar 19 = bottom (0-5%)
            bar_pct_low = (num_bars - 1 - i) * 5   # e.g. bar 19 -> 0%, bar 0 -> 95%
            bar_y_top = bar_area_top + i * (bar_h + bar_gap)
            bar_y_bot = bar_y_top + bar_h

            if capacity >= bar_pct_low + 5:
                # Fully filled
                if capacity <= 20:
                    color = "#F44336"
                elif capacity <= 50:
                    color = "#FFC107"
                else:
                    color = "#4CAF50"
                c.create_rectangle(x1 + bar_pad, bar_y_top, x2 - bar_pad, bar_y_bot,
                                   fill=color, outline="")
            elif capacity > bar_pct_low:
                # Partially filled
                if capacity <= 20:
                    color = "#F44336"
                elif capacity <= 50:
                    color = "#FFC107"
                else:
                    color = "#4CAF50"
                # Dim version for unfilled portion
                c.create_rectangle(x1 + bar_pad, bar_y_top, x2 - bar_pad, bar_y_bot,
                                   fill=empty_color, outline="")
                fill_frac = (capacity - bar_pct_low) / 5.0
                fill_h = bar_h * fill_frac
                c.create_rectangle(x1 + bar_pad, bar_y_bot - fill_h, x2 - bar_pad, bar_y_bot,
                                   fill=color, outline="")
            else:
                # Empty
                c.create_rectangle(x1 + bar_pad, bar_y_top, x2 - bar_pad, bar_y_bot,
                                   fill=empty_color, outline="")

        # Draw limit marker line
        limit_y = y2 - (limit / 100.0) * bh
        c.create_line(x1 - 25, limit_y, x2 + 25, limit_y, fill=t["battery_pct_fg"], width=6, dash=(8, 4))

        # Limit label on the right side (with spacing between label and %)
        c.create_text(x2 + 40, limit_y - 24, text="Limit", font=("Arial", 14, "bold"), fill=t["battery_pct_fg"], anchor="w")
        c.create_text(x2 + 40, limit_y + 24, text=f"{limit}%", font=("Arial", 16, "bold"), fill=t["battery_pct_fg"], anchor="w")

        # Draw charge marker line (same dotted style, pink)
        charge_y = y2 - (capacity / 100.0) * bh
        charge_y = max(y1 + 10, min(y2 - 10, charge_y))
        c.create_line(x1 - 25, charge_y, x2 + 25, charge_y, fill="#FFB6C1", width=6, dash=(8, 4))

        # Actual charge text on the left side, light pink (with spacing between label and %)
        c.create_text(x1 - 40, charge_y - 24, text="Charge", font=("Arial", 14, "bold"), fill="#FFB6C1", anchor="e")
        c.create_text(x1 - 40, charge_y + 24, text=f"{capacity}%", font=("Arial", 16, "bold"), fill="#FFB6C1", anchor="e")

    def on_slide(self, value):
        val = int(float(value))
        self.charge_value_label.config(text=f"{val}%")
        # Redraw gauge instantly using cached capacity (no sysfs read)
        self._draw_gauge(self._cached_capacity, val)
        # Debounce the actual sysfs write
        if self._slide_job:
            self.after_cancel(self._slide_job)
        self._slide_job = self.after(200, self.apply_limit)

    def get_state(self):
        return {"charge_limit": self.charge_limit_var.get()}

    def load_state(self, data):
        if "charge_limit" in data:
            self.charge_limit_var.set(data["charge_limit"])
            self.charge_value_label.config(text=f"{self.charge_limit_var.get()}%")
            self.apply_limit()

    def apply_limit(self):
        if not self.app.backend:
            if not getattr(self.app, 'is_loading', False):
                show_message(self.app.root, "Unavailable", "Backend not available, battery limit not supported.")
            return
        try:
            self.app.backend.set_battery_charge_limit(self.charge_limit_var.get())
            self.app.status_var.set(f"Battery charge limit set to {self.charge_limit_var.get()}%")
            self.app.save_config()
            self.update_status()
        except BackendError as exc:
            if not getattr(self.app, 'is_loading', False):
                show_message(self.app.root, "Error", f"Battery limit failed:\n\n{exc}")

    def apply_theme(self):
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()
        self.gauge_canvas.configure(bg=t["battery_gauge_bg"])
        self.capacity_label.configure(foreground=t["battery_pct_fg"])
        self.charge_value_label.configure(foreground=t["battery_pct_fg"])
        self.charge_slider.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                     troughcolor=t["scale_trough"],
                                     activebackground=t["scale_active"])
        cap = self._cached_capacity
        self._draw_gauge(cap, self.charge_limit_var.get())

    def update_status(self):
        info = self.app.backend.get_battery_info() if self.app.backend else {}
        cap = info.get("capacity")
        if cap is not None:
            cap = int(cap)
            self._cached_capacity = cap
            self.capacity_label.config(text=f"{cap}%")
            status = info.get("status", "Unknown")
            self.status_label.config(text=status)
        else:
            cap = 0
            self._cached_capacity = 0
            self.capacity_label.config(text="--%")
            self.status_label.config(text="Unavailable")
            
        self._draw_gauge(cap, self.charge_limit_var.get())
        
        paths = info.get('paths', [])
        if paths:
            # Just show the base name of the first path (e.g. BAT0) instead of the full messy path
            name = paths[0].split('/')[-1]
            self.battery_info.config(text=f"Device: {name}")
        else:
            self.battery_info.config(text="Device: unknown")