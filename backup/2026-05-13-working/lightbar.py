import tkinter as tk
from tkinter import ttk
import colorsys
import math
from backend import BackendError
from ..utils import sanitize_color, show_message
from ..color_picker import ask_color


class LightbarTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.color = "#ffffff"
        self.effect_var = tk.StringVar(value="rainbow")
        self.brightness_var = tk.IntVar(value=100)
        self._rainbow_anim_id = None
        self._rainbow_hue = 0.0
        self._pulse_phase = 0.0
        self._update_theme_colors()
        self.create_widgets()

    def _update_theme_colors(self):
        from ui import themes
        t = themes.get()
        self._bg_rgb = t["lightbar_bg_rgb"]
        self._chassis_col = t["lightbar_chassis"]
        self._slat_col = t["lightbar_slat"]
        self._slat_catch = t["lightbar_slat_catch"]

    def create_widgets(self):
        from ui import themes
        t = themes.get()
        ttk.Label(self, text="Lightbar Controls", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))

        self._lightbar_available = (
            self.app.backend is not None
            and hasattr(self.app.backend, '_lightbar')
            and getattr(self.app.backend._lightbar, 'available', False)
        )

        if not self._lightbar_available and self.app.backend is not None:
            ttk.Label(
                self,
                text="⚠ Lightbar not detected. If your system has a lightbar, "
                     "rebuild and reload the driver (nuc_wmi or qc71_laptop) to enable it.",
                wraplength=580, foreground="gray"
            ).pack(fill=tk.X, pady=(8, 8))

        from ui import themes
        t = themes.get()
        # === Graphical Lightbar Preview ===
        self.lightbar_canvas = tk.Canvas(
            self, height=60, bg=t["canvas_bg"],
            highlightthickness=0, relief="flat"
        )
        self.lightbar_canvas.pack(fill=tk.X, pady=(0, 12))
        self.lightbar_canvas.bind("<Configure>", self._on_configure)

        # Effect selection
        effect_frame = ttk.LabelFrame(self, text="Effect", padding=8)
        effect_frame.pack(fill=tk.X, pady=(0, 12))

        effects = [
            ("Monocolor", "monocolor", "Static color"),
            ("Rainbow", "rainbow", "Built-in rainbow animation"),
            ("Off", "off", "Turn lightbar off"),
        ]

        for label, value, desc in effects:
            row = ttk.Frame(effect_frame)
            row.pack(fill=tk.X, pady=2)
            rb = tk.Radiobutton(row, text=label, variable=self.effect_var, value=value,
                                 command=self.apply_settings,
                                 fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                                 activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                                 indicatoron=1, font=("Arial", 10, "bold"),
                                 bd=0, highlightthickness=0, relief="flat")
            rb.pack(side=tk.LEFT)
            ttk.Label(row, text=f"— {desc}", foreground="gray", font=("Arial", 9)).pack(side=tk.LEFT, padx=(8, 0))

        # Color picker
        color_frame = ttk.Frame(self)
        color_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(color_frame, text="Color:").pack(side=tk.LEFT, padx=(0, 8))
        self.color_preview = tk.Label(color_frame, bg=self.color, width=4, relief=tk.SUNKEN)
        self.color_preview.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(color_frame, text="Choose color", command=self.choose_color).pack(side=tk.LEFT)

        # Brightness slider
        brightness_frame = ttk.Frame(self)
        brightness_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(brightness_frame, text="Brightness:").pack(side=tk.LEFT, padx=(0, 8))
        self.brightness_slider = tk.Scale(brightness_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                             variable=self.brightness_var, command=self.update_brightness_label,
                                             length=300, sliderlength=30, width=18, showvalue=False,
                                             bg=t["scale_bg"], fg=t["scale_fg"], troughcolor=t["scale_trough"],
                                             highlightthickness=0, activebackground=t["scale_active"],
                                             repeatdelay=150, repeatinterval=50)
        self.brightness_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.brightness_label = ttk.Label(brightness_frame, text="100%")
        self.brightness_label.pack(side=tk.RIGHT)

        # Reset button
        reset_frame = ttk.Frame(self)
        reset_frame.pack(fill=tk.X, pady=(8, 0))
        self.reset_btn = tk.Button(reset_frame, text="⟲ Reset Lightbar", font=("Arial", 10),
                                   fg="white", bg=t["svc_btn_reset"], relief="flat", padx=12, pady=4,
                                   command=self.reset_lightbar)
        self.reset_btn.pack(side=tk.LEFT)
        ttk.Label(reset_frame, text="— Flush all EC lightbar settings and turn off",
                  foreground="gray", font=("Arial", 9)).pack(side=tk.LEFT, padx=(8, 0))

        self.status_label = ttk.Label(self, text="Lightbar status unavailable", wraplength=580)
        self.status_label.pack(fill=tk.X, pady=(8, 0))

        self.update_status_label()

    # === Rendering ===

    def _interp(self, target_rgb, factor):
        bg = self._bg_rgb
        r = int(bg[0] + (target_rgb[0] - bg[0]) * max(0, min(factor, 1)))
        g = int(bg[1] + (target_rgb[1] - bg[1]) * max(0, min(factor, 1)))
        b = int(bg[2] + (target_rgb[2] - bg[2]) * max(0, min(factor, 1)))
        return f"#{max(0,min(r,255)):02x}{max(0,min(g,255)):02x}{max(0,min(b,255)):02x}"

    def _on_configure(self, event=None):
        self._draw_lightbar()

    def _draw_lightbar(self, event=None):
        self._update_theme_colors()
        from ui import themes
        t = themes.get()
        c = self.lightbar_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 30:
            return

        c.delete("all")

        effect = self.effect_var.get()
        brightness = self.brightness_var.get() / 100.0

        cx = w / 2
        cy = h / 2
        bar_w = w * 0.55

        front_w = w * 0.94
        lip_y1 = cy - 14
        lip_y2 = cy + 14
        half_front = front_w / 2
        half_bar = bar_w / 2

        pillar_w = 3
        left_pillar = cx - half_bar - pillar_w
        right_pillar = cx + half_bar
        open_x1 = left_pillar + pillar_w
        open_x2 = right_pillar
        self._open_x1 = open_x1
        self._open_x2 = open_x2

        # Opening area for LED grill
        open_y1 = cy - 8
        open_y2 = cy + 8

        # LAYER 1: Ambient glow (use smooth=True oval for antialiasing)
        if effect != "off" and brightness > 0:
            amb_rgb = self._get_ambient_rgb(effect, brightness)
            if amb_rgb:
                amb_col = self._interp(amb_rgb, 0.10 * brightness)
                c.create_oval(cx - bar_w * 0.7, cy - 18,
                             cx + bar_w * 0.7, cy + 20,
                             fill=amb_col, outline=amb_col, width=1)

        # LAYER 2: Full chassis front lip — use rounded rectangle for smoother edges
        r = 4  # corner radius
        fx1, fy1, fx2, fy2 = cx - half_front, lip_y1, cx + half_front, lip_y2
        c.create_polygon(
            fx1+r, fy1, fx2-r, fy1, fx2, fy1, fx2, fy1+r,
            fx2, fy2-r, fx2, fy2, fx2-r, fy2, fx1+r, fy2,
            fx1, fy2, fx1, fy2-r, fx1, fy1+r, fx1, fy1,
            fill=self._chassis_col, outline=self._chassis_col, smooth=True
        )
        c.create_line(fx1+r, lip_y1, fx2-r, lip_y1,
                     fill=t["lightbar_edge_top"], width=1)
        c.create_line(fx1+r, lip_y2, fx2-r, lip_y2,
                     fill=t["lightbar_edge_bot"], width=1)

        # LAYER 3: Side micro-mesh (staggered dots, visible contrast)
        mesh_col = t["lightbar_mesh"]
        for ax1, ax2 in [(int(cx - half_front) + 2, int(left_pillar)),
                          (int(right_pillar + pillar_w), int(cx + half_front) - 2)]:
            row = 0
            for y in range(int(lip_y1) + 3, int(lip_y2) - 2, 3):
                offset = 1 if row % 2 else 0
                for x in range(ax1, ax2, 3):
                    dx = x + offset
                    if ax1 <= dx < ax2:
                        c.create_oval(dx, y, dx + 2, y + 2,
                                     fill=mesh_col, outline="")
                row += 1

        # LAYER 4: Vertical pillars (visible structural dividers)
        pillar_col = t["lightbar_pillar"]
        for px in [left_pillar, right_pillar]:
            c.create_rectangle(px - 1, lip_y1, px + pillar_w + 1, lip_y2,
                              fill=pillar_col, outline="")
            # Left highlight edge
            c.create_line(px - 1, lip_y1, px - 1, lip_y2, fill=t["lightbar_pillar_hi"], width=1)
            # Right shadow edge
            c.create_line(px + pillar_w + 1, lip_y1, px + pillar_w + 1, lip_y2,
                         fill=t["lightbar_pillar_lo"], width=1)

        # LAYER 5: Opening dark background
        c.create_rectangle(open_x1, open_y1, open_x2, open_y2,
                          fill=t["lightbar_opening"], outline="")

        # LAYER 6: LED bloom fills entire opening (drawn BEFORE mesh)
        if effect != "off" and brightness > 0:
            self._draw_bloom_in_region(c, cx, cy, bar_w, open_y1, open_y2, effect, brightness)

        # LAYER 7: Mesh/grill overlay — drawn ON TOP of LED bloom
        # This creates the illusion of LEDs behind a grille
        mesh_col = self._slat_col
        row = 0
        for y in range(int(open_y1) + 1, int(open_y2) - 1, 3):
            offset = 1 if row % 2 else 0
            for x in range(int(open_x1) + 1, int(open_x2) - 1, 3):
                dx = x + offset
                if open_x1 <= dx < open_x2:
                    c.create_rectangle(dx, y, dx + 2, y + 2,
                                      fill=mesh_col, outline="")
            row += 1

        # Close the frame top/bottom
        c.create_rectangle(open_x1, lip_y1, open_x2, open_y1,
                          fill=self._chassis_col, outline="")
        c.create_rectangle(open_x1, open_y2, open_x2, lip_y2,
                          fill=self._chassis_col, outline="")
        c.create_line(open_x1, open_y1, open_x2, open_y1, fill=t["lightbar_frame_top"], width=1)
        c.create_line(open_x1, open_y2, open_x2, open_y2, fill=t["lightbar_frame_bot"], width=1)

        if effect == "rainbow" and brightness > 0:
            self._start_rainbow_animation()
        else:
            self._stop_rainbow_animation()

    def _draw_bloom_in_region(self, c, cx, cy, bar_w, y1, y2, effect, brightness):
        # Clip bloom to the opening area between pillars
        open_x1 = getattr(self, '_open_x1', cx - bar_w / 2)
        open_x2 = getattr(self, '_open_x2', cx + bar_w / 2)
        half_w = (open_x2 - open_x1) / 2
        open_cx = (open_x1 + open_x2) / 2
        gap_cy = (y1 + y2) / 2

        if effect == "monocolor":
            r, g, b = (int(self.color[i:i+2], 16) for i in (1, 3, 5))
            rgb = (r, g, b)
            for layer in range(6, 0, -1):
                factor = ((1.0 - (layer / 6)) ** 2) * brightness * 0.8
                color = self._interp(rgb, factor)
                taper = (layer / 6) * 8
                c.create_rectangle(open_cx - half_w + taper, y1,
                                  open_cx + half_w - taper, y2,
                                  fill=color, outline="")
            core_r = int(rgb[0] + (255 - rgb[0]) * 0.6 * brightness)
            core_g = int(rgb[1] + (255 - rgb[1]) * 0.6 * brightness)
            core_b = int(rgb[2] + (255 - rgb[2]) * 0.6 * brightness)
            core_col = f"#{min(core_r,255):02x}{min(core_g,255):02x}{min(core_b,255):02x}"
            c.create_rectangle(open_cx - half_w, gap_cy - 1, open_cx + half_w, gap_cy + 1,
                              fill=core_col, outline="")

        elif effect == "rainbow":
            segments = 40
            total_w = open_x2 - open_x1
            seg_w = total_w / segments
            x_start = open_x1
            for seg in range(segments):
                hue = (seg / segments + self._rainbow_hue) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                rgb = (int(r * 255), int(g * 255), int(b * 255))
                sx = x_start + seg * seg_w
                for layer in range(4, 0, -1):
                    factor = ((1.0 - (layer / 4)) ** 2) * brightness * 0.7
                    color = self._interp(rgb, factor)
                    c.create_rectangle(sx, y1, sx + seg_w + 1, y2,
                                      fill=color, outline="")
                cr = int(rgb[0] + (255 - rgb[0]) * 0.5 * brightness)
                cg = int(rgb[1] + (255 - rgb[1]) * 0.5 * brightness)
                cb = int(rgb[2] + (255 - rgb[2]) * 0.5 * brightness)
                core_col = f"#{min(cr,255):02x}{min(cg,255):02x}{min(cb,255):02x}"
                c.create_rectangle(sx, gap_cy - 1, sx + seg_w + 1, gap_cy + 1,
                                  fill=core_col, outline="")

    def _get_ambient_rgb(self, effect, brightness):
        if effect == "monocolor":
            r, g, b = (int(self.color[i:i+2], 16) for i in (1, 3, 5))
            return (r, g, b)
        elif effect == "rainbow":
            return (180, 180, 200)
        return None

    def _start_rainbow_animation(self):
        if self._rainbow_anim_id is not None:
            return
        def animate():
            if self.effect_var.get() != "rainbow":
                self._rainbow_anim_id = None
                return
            self._rainbow_hue = (self._rainbow_hue + 0.006) % 1.0
            self._draw_lightbar()
            self._rainbow_anim_id = self.after(50, animate)
        self._rainbow_anim_id = self.after(50, animate)

    def _stop_rainbow_animation(self):
        if self._rainbow_anim_id is not None:
            self.after_cancel(self._rainbow_anim_id)
            self._rainbow_anim_id = None

    # === Controls ===

    def choose_color(self):
        rgb, hex_color = ask_color(self.winfo_toplevel(), self.color, "Choose lightbar color")
        if hex_color:
            self.color = sanitize_color(hex_color)
            self.color_preview.config(bg=self.color)
            self._draw_lightbar()
            if self.effect_var.get() == "monocolor":
                self.apply_settings()

    def update_brightness_label(self, value):
        self.brightness_label.config(text=f"{int(float(value))}%")
        self._draw_lightbar()
        effect = self.effect_var.get()
        if effect == "monocolor":
            try:
                self.after_cancel(self._brightness_job)
            except Exception:
                pass
            self._brightness_job = self.after(300, self.apply_settings)

    def get_state(self):
        return {
            "lightbar_color": self.color,
            "lightbar_brightness": self.brightness_var.get(),
            "lightbar_effect": self.effect_var.get()
        }

    def load_state(self, data):
        if "lightbar_color" in data:
            self.color = sanitize_color(data["lightbar_color"])
            self.color_preview.config(bg=self.color)
        if "lightbar_brightness" in data:
            self.brightness_var.set(data["lightbar_brightness"])
            self.brightness_label.config(text=f"{data['lightbar_brightness']}%")
        if "lightbar_effect" in data:
            eff = data["lightbar_effect"]
            if "breathing" in eff:
                eff = "monocolor"
            self.effect_var.set(eff)

        if self.effect_var.get() == "monocolor" and self.brightness_var.get() == 0:
            self.brightness_var.set(100)
            self.brightness_label.config(text="100%")

        self.update_status_label()
        self.apply_settings()
        self.after(100, self._draw_lightbar)

    def reset_lightbar(self):
        if not self.app.backend or not self._lightbar_available:
            return
        try:
            self.app.backend.reset_lightbar()
            self.effect_var.set("off")
            self.brightness_var.set(100)
            self.brightness_label.config(text="100%")
            self._draw_lightbar()
            self.status_label.config(text="Lightbar reset to off")
            self.app.status_var.set("Lightbar reset")
        except BackendError as exc:
            show_message(self.app.root, "Lightbar error", f"Failed to reset lightbar:\n\n{exc}")

    def apply_settings(self):
        if not self.app.backend or not self._lightbar_available:
            self._draw_lightbar()
            return

        rgb = tuple(int(self.color[i:i+2], 16) for i in (1, 3, 5))
        brightness = self.brightness_var.get()
        effect = self.effect_var.get()

        try:
            if effect == "monocolor":
                self.app.backend.set_lightbar_color(rgb, brightness)
            else:
                self.app.backend.set_lightbar_effect(effect, rgb, brightness)

            self.status_label.config(text=f"Lightbar set to {effect} ({self.color}, {brightness}%)")
            self.app.status_var.set(f"Lightbar effect '{effect}' applied")
            if not getattr(self.app, "is_loading", False):
                self.app.save_config()
        except BackendError as exc:
            if not getattr(self.app, "is_loading", False):
                show_message(self.app.root, "Lightbar error", f"Failed to apply lightbar settings:\n\n{exc}")

        self._draw_lightbar()

    def update_status_label(self):
        available = self.app.backend and self.app.backend.supports_lightbar_rainbow() if self.app.backend else False
        status = "available" if self.app.backend else "backend unavailable"
        self.status_label.config(text=f"Lightbar is {status}. Rainbow support: {'yes' if available else 'no'}.")

    def apply_theme(self):
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()
        self._update_theme_colors()
        self.lightbar_canvas.configure(bg=t["canvas_bg"])
        self.brightness_slider.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                         troughcolor=t["scale_trough"],
                                         activebackground=t["scale_active"])
        self.reset_btn.configure(bg=t["svc_btn_reset"])
        # Restyle radiobuttons
        for child in self.winfo_children():
            for sub in child.winfo_children() if hasattr(child, 'winfo_children') else []:
                if hasattr(sub, 'winfo_children'):
                    for w in sub.winfo_children():
                        if w.winfo_class() == "Radiobutton":
                            w.configure(fg=t["radio_fg"], bg=t["radio_bg"],
                                        selectcolor=t["radio_bg"],
                                        activebackground=t["radio_bg"],
                                        activeforeground=t["radio_fg"])
        self._draw_lightbar()

    def destroy(self):
        self._stop_rainbow_animation()
        super().destroy()
