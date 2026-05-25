import time
import json
import colorsys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from backend import BackendError
from ..utils import KEY_LAYOUT, FN_KEY_SYMBOLS, DEFAULT_COLOR, sanitize_color, get_closest_color, show_message

# Fixed height for the color area so it doesn't resize dynamically
_COLOR_FRAME_HEIGHT = 200

class KeyboardTab(ttk.Frame):
    # ITE8291R3 Hardware Palette Mapping (NUC X15 / Tongfang QC71 variant)
    #
    # The ITE8291R3 controller has 8 hardcoded palette indices burned into firmware.
    # On this Tongfang variant, the physical RGB LED wiring is swapped, so the
    # palette names from the ITE reference design don't match what's actually
    # displayed. For example, palette index 1 ("red") drives R+G+B simultaneously,
    # producing white. This cannot be fixed — the palette LUT is ROM-burned and
    # there are no HID commands to reprogram it or read it back.
    #
    # Map: UI display name (what user sees) → hardware palette name (sent to controller)
    HW_PALETTE = {
        "white":   "red",       # hw index 1 — R+G+B wired together → white
        "orange":  "orange",    # hw index 2 — correct
        "yellow":  "yellow",    # hw index 3 — correct
        "green":   "green",     # hw index 4 — correct
        "blue":    "blue",      # hw index 5 — correct
        "purple":  "teal",      # hw index 6 — teal wiring → displays purple
        "pink":    "purple",    # hw index 7 — purple wiring → displays pink
        "random":  "random",    # hw index 8 — multi-color cycle
    }
    PALETTE_HEX = {
        "white": "#FFFFFF", "orange": "#FF8000", "yellow": "#FFFF00",
        "green": "#00FF00", "blue": "#0000FF", "purple": "#8000FF",
        "pink": "#FFB0E0", "random": "#FFFFFF",
    }
    PALETTE_NAMES = ["white", "orange", "yellow", "green", "blue", "purple", "pink", "random"]

    # Effect definitions: name -> {has_color, has_speed, has_direction, has_reactive, description}
    # Effect symbols for UI
    EFFECT_ICONS = {
        "breathing": "💨", "wave": "🌊", "random": "🎲", "rainbow": "🌈",
        "ripple": "💧", "marquee": "🎬", "raindrop": "🌧", "aurora": "🌌",
        "fireworks": "🎆", "audio": "🎵", "monocolor": "🎨", "per-key": "⌨",
        "glow": "💡", "coding": "💻", "gaming": "🎮", "off": "⭘",
    }

    EFFECTS = {
        "breathing":  {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": False, "desc": "Pulsing glow"},
        "wave":       {"has_color": False, "has_speed": True,  "has_direction": True,  "has_reactive": False, "desc": "Rainbow wave"},
        "random":     {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": True,  "desc": "Random key colors"},
        "rainbow":    {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Static rainbow"},
        "ripple":     {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": True,  "desc": "Ripple from keypress"},
        "marquee":    {"has_color": False, "has_speed": True,  "has_direction": False, "has_reactive": False, "desc": "Scrolling lights"},
        "raindrop":   {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": False, "desc": "Falling drops"},
        "aurora":     {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": True,  "desc": "Northern lights"},
        "fireworks":  {"has_color": True,  "has_speed": True,  "has_direction": False, "has_reactive": True,  "desc": "Burst effect"},
        "audio":      {"has_color": False, "has_speed": False, "has_direction": True,  "has_reactive": False, "desc": "Audio visualizer (all sources)"},
        "monocolor":  {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Single RGB color"},
        "glow":       {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Single color + per-key brightness"},
        "coding":     {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Static green (coding)"},
        "gaming":     {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Static red (gaming)"},
        "per-key":    {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Individual key colors"},
        "off":        {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Keyboard off"},
    }

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.keyboard_colors = {}
        self._perkey_colors = {}
        self._perkey_brightness = {}
        self._mono_color = "#FFFFFF"
        self.key_items = {}
        self._kb_slide_job = None
        self._selected_keys = set()
        self._resize_job = None
        self._effect_settings = {}
        # HSV state for inline color picker
        self._cp_hue = 0.0
        self._cp_sat = 1.0
        self._cp_val = 1.0

        self.SPAN_BY_ROW = [
            [4]*16,
            [4]*13 + [8, 4],
            [6] + [4]*12 + [6, 4],
            [7] + [4]*11 + [9, 4],
            [9] + [4]*10 + [7, 4, 4],
            [5, 4, 4, 4, 20, 4, 4, 7, 4, 4, 4],
        ]

        self.create_widgets()

        for key_name in self.key_items:
            self.keyboard_colors[key_name] = DEFAULT_COLOR

        self.after(1000, self._poll_kbd_brightness)

    def create_widgets(self):
        # TOP: Brightness bar with yellow gauge
        brightness_frame = ttk.Frame(self, height=40)
        brightness_frame.pack(fill=tk.X, pady=(0, 4))
        brightness_frame.pack_propagate(False)

        self.keyboard_brightness_var = tk.IntVar(value=100)
        self._brightness_levels = [0, 50, 100]
        self._brightness_labels = ["\u2501 Off", "\U0001f319 50%", "\U0001f31e 100%"]

        from ui import themes
        t = themes.get()

        self.brightness_gauge = tk.Canvas(brightness_frame, bg=t["canvas_bg"], highlightthickness=0)
        self.brightness_gauge.pack(fill=tk.BOTH, expand=True)
        self.brightness_gauge.bind("<Configure>", self._draw_brightness_gauge)

        # MIDDLE: Keyboard canvas
        self.canvas = tk.Canvas(self, bg=t["keyboard_canvas_bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=4)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.pixel_virtual = tk.PhotoImage(width=1, height=1)

        # BOTTOM: Controls — compact horizontal layout
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, pady=(4, 0))

        # Row 1: Effects as horizontal radio buttons (wrapping)
        effects_frame = ttk.LabelFrame(controls_frame, text="Effect", padding=4)
        effects_frame.pack(fill=tk.X, pady=(0, 4))

        self.effect_var = tk.StringVar(value="off")
        eff_inner = ttk.Frame(effects_frame)
        eff_inner.pack(fill=tk.X)
        for i, eff_name in enumerate(self.EFFECTS):
            icon = self.EFFECT_ICONS.get(eff_name, "")
            rb = tk.Radiobutton(eff_inner, text=f"{icon} {eff_name}", value=eff_name,
                                variable=self.effect_var, command=self._on_effect_change,
                                fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                                activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                                indicatoron=1, font=("Arial", 10, "bold"),
                                bd=0, highlightthickness=0, relief="flat")
            rb.grid(row=i // 8, column=i % 8, sticky="w", padx=2, pady=1)

        # Row 2: Color area — FIXED HEIGHT container
        self.colors_frame = ttk.LabelFrame(controls_frame, text="Color", padding=6)
        self.colors_frame.pack(fill=tk.X, pady=(0, 4))
        # Fixed-size inner frame
        self._color_container = ttk.Frame(self.colors_frame, height=_COLOR_FRAME_HEIGHT)
        self._color_container.pack(fill=tk.X)
        self._color_container.pack_propagate(False)

        # --- Palette radio buttons (for hardware effects that only support palette colors) ---
        self.color_preset_var = tk.StringVar(value="blue")
        self._color_radios = {}
        self._palette_inner = ttk.Frame(self._color_container)
        for i, color_name in enumerate(self.PALETTE_NAMES):
            rf = ttk.Frame(self._palette_inner)
            rf.grid(row=0, column=i, padx=4, pady=1)
            swatch = tk.Canvas(rf, width=20, height=20, highlightthickness=1,
                               highlightbackground=t["border"],
                               bg=self.PALETTE_HEX.get(color_name, "#FFF"))
            swatch.pack(side=tk.LEFT, padx=(0, 2))
            rb = tk.Radiobutton(rf, text=color_name, value=color_name,
                                  variable=self.color_preset_var, command=self._on_preset_change,
                                  fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                                  activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                                  indicatoron=1, font=("Arial", 10, "bold"),
                                  bd=0, highlightthickness=0, relief="flat",
                                  disabledforeground=t["fg_muted"])
            rb.pack(side=tk.LEFT)
            self._color_radios[color_name] = rb

        # --- Inline color picker (for monocolor / per-key / glow) ---
        self._custom_color_inner = ttk.Frame(self._color_container)
        # Left: SV square
        self._sv_canvas = tk.Canvas(self._custom_color_inner, width=180, height=180, bg="#000",
                                     highlightthickness=1, highlightbackground=t["border"],
                                     cursor="crosshair")
        self._sv_canvas.pack(side=tk.LEFT, padx=(0, 8), anchor="n")
        self._sv_canvas.bind("<Button-1>", self._on_sv_click)
        self._sv_canvas.bind("<B1-Motion>", self._on_sv_click)

        # Hue bar
        self._hue_canvas = tk.Canvas(self._custom_color_inner, width=24, height=180, bg="#000",
                                      highlightthickness=1, highlightbackground=t["border"],
                                      cursor="hand2")
        self._hue_canvas.pack(side=tk.LEFT, padx=(0, 12), anchor="n")
        self._hue_canvas.bind("<Button-1>", self._on_hue_click)
        self._hue_canvas.bind("<B1-Motion>", self._on_hue_click)

        # Right column: preview, hex, brightness, presets
        cp_right = ttk.Frame(self._custom_color_inner)
        cp_right.pack(side=tk.LEFT, fill=tk.Y, anchor="n")

        # Preview swatch + hex
        preview_row = ttk.Frame(cp_right)
        preview_row.pack(fill=tk.X, pady=(0, 4))
        self._custom_swatch = tk.Canvas(preview_row, width=36, height=36,
                                        highlightthickness=2, highlightbackground=t["accent"],
                                        bg=self._mono_color)
        self._custom_swatch.pack(side=tk.LEFT, padx=(0, 6))
        hex_col = ttk.Frame(preview_row)
        hex_col.pack(side=tk.LEFT)
        self._hex_var = tk.StringVar(value="FFFFFF")
        ttk.Label(hex_col, text="#", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        self._hex_entry = tk.Entry(hex_col, textvariable=self._hex_var, width=8,
                                    font=("Arial", 12), bg=t["bg_input"], fg=t["fg"],
                                    insertbackground=t["accent"], relief="flat", bd=2)
        self._hex_entry.pack(side=tk.LEFT, padx=(2, 0))
        self._hex_entry.bind("<Return>", self._on_hex_enter)
        self._hex_entry.bind("<FocusOut>", self._on_hex_enter)

        # RGB labels
        rgb_row = ttk.Frame(cp_right)
        rgb_row.pack(fill=tk.X, pady=(0, 3))
        self._r_label = ttk.Label(rgb_row, text="R: 255", foreground="#ff6666", font=("Arial", 9))
        self._r_label.pack(side=tk.LEFT, padx=(0, 6))
        self._g_label = ttk.Label(rgb_row, text="G: 255", foreground="#66ff66", font=("Arial", 9))
        self._g_label.pack(side=tk.LEFT, padx=(0, 6))
        self._b_label = ttk.Label(rgb_row, text="B: 255", foreground="#6688ff", font=("Arial", 9))
        self._b_label.pack(side=tk.LEFT)

        # Quick presets
        presets_frame = ttk.Frame(cp_right)
        presets_frame.pack(fill=tk.X, pady=(0, 3))
        presets = [
            "#FF0000", "#FF8000", "#FFFF00", "#00FF00",
            "#00FFFF", "#0000FF", "#8000FF", "#FF00FF",
            "#FFFFFF", "#FFB0E0", "#FF4444", "#000000",
        ]
        for i, color in enumerate(presets):
            btn = tk.Canvas(presets_frame, width=20, height=20, bg=color,
                            highlightthickness=1, highlightbackground=t["border"],
                            cursor="hand2")
            btn.grid(row=i // 6, column=i % 6, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=color: self._set_color_from_hex(c))

        # Brightness slider
        brt_row = ttk.Frame(cp_right)
        brt_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(brt_row, text="Brightness:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._perkey_brightness_var = tk.IntVar(value=100)
        self._brightness_slider = tk.Scale(brt_row, from_=5, to=100, orient=tk.HORIZONTAL,
                                           variable=self._perkey_brightness_var, command=self._on_brightness_slide,
                                           length=160, sliderlength=18, width=18, showvalue=False,
                                           bg=t["scale_bg"], fg=t["scale_fg"], troughcolor=t["scale_trough"],
                                           highlightthickness=0, activebackground=t["scale_active"])
        self._brightness_slider.pack(side=tk.LEFT, padx=(0, 4))
        self._brightness_lbl = ttk.Label(brt_row, text="100%", font=("Arial", 10, "bold"), width=5)
        self._brightness_lbl.pack(side=tk.LEFT)

        # --- "No color" label for effects without color ---
        self._no_color_label = ttk.Label(self._color_container, text="No color options for this effect",
                                          foreground="gray", font=("Arial", 10))

        # Row 3: Options (speed, direction, reactive, per-key) — single row, fixed height
        self.options_frame = ttk.LabelFrame(controls_frame, text="Options", padding=4)
        self.options_frame.pack(fill=tk.X, pady=(0, 2))

        opt_inner = ttk.Frame(self.options_frame, height=56)
        opt_inner.pack(fill=tk.X)
        opt_inner.pack_propagate(False)

        # Effect description
        self.effect_desc_label = ttk.Label(opt_inner, text="", foreground="gray", font=("Arial", 9))
        self.effect_desc_label.pack(side=tk.LEFT, padx=(0, 12))

        # Speed
        self.speed_row = ttk.Frame(opt_inner)
        self.speed_row.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(self.speed_row, text="Speed:").pack(side=tk.LEFT, padx=(0, 2))
        self.keyboard_speed_var = tk.IntVar(value=7)
        self.speed_slider = tk.Scale(self.speed_row, from_=1, to=9, orient=tk.HORIZONTAL,
                                     variable=self.keyboard_speed_var, command=self.on_speed_slide,
                                     length=250, sliderlength=16, width=24, showvalue=False,
                                     bg=t["scale_bg"], fg=t["scale_fg"], troughcolor=t["scale_trough"],
                                     highlightthickness=0, activebackground=t["scale_active"],
                                     repeatdelay=150, repeatinterval=50)
        self.speed_slider.pack(side=tk.LEFT)
        self.speed_label = ttk.Label(self.speed_row, text="7", width=2)
        self.speed_label.pack(side=tk.LEFT)

        # Direction
        self.direction_row = ttk.Frame(opt_inner)
        self.direction_row.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(self.direction_row, text="Direction:").pack(side=tk.LEFT, padx=(0, 2))
        self.wave_dir_var = tk.StringVar(value="right")
        self._dir_radios = {}
        for d in ("right", "left", "up", "down"):
            rb = tk.Radiobutton(self.direction_row, text=d, value=d,
                                  variable=self.wave_dir_var, command=self._on_direction_change,
                                  fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                                  activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                                  indicatoron=1, font=("Arial", 10, "bold"),
                                  bd=0, highlightthickness=0, relief="flat")
            rb.pack(side=tk.LEFT, padx=1)
            self._dir_radios[d] = rb

        # Reactive
        self.reactive_row = ttk.Frame(opt_inner)
        self.reactive_row.pack(side=tk.LEFT, padx=(0, 8))
        self.reactive_var = tk.BooleanVar(value=False)
        self.reactive_check = tk.Checkbutton(self.reactive_row, text="Reactive",
                                               variable=self.reactive_var, command=self._on_reactive_change,
                                               fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
                                               activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
                                               font=("Arial", 10, "bold"),
                                               bd=0, highlightthickness=0, relief="flat")
        self.reactive_check.pack(side=tk.LEFT)

        # Per-key buttons
        self.perkey_row = ttk.Frame(opt_inner)
        self.perkey_row.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_set_color = ttk.Button(self.perkey_row, text="Color", command=self._color_selected_keys, width=5)
        self.btn_set_color.pack(side=tk.LEFT, padx=1)
        self.btn_clear_sel = ttk.Button(self.perkey_row, text="ClrSel", command=self._clear_selected_keys, width=5)
        self.btn_clear_sel.pack(side=tk.LEFT, padx=1)
        self.btn_clear_all = ttk.Button(self.perkey_row, text="ClrAll", command=self._clear_all_keys, width=5)
        self.btn_clear_all.pack(side=tk.LEFT, padx=1)
        self.btn_apply_perkey = ttk.Button(self.perkey_row, text="Apply", command=self._apply_per_key, width=5)
        self.btn_apply_perkey.pack(side=tk.LEFT, padx=1)

        # Placeholder
        self.no_options_label = ttk.Label(opt_inner, text="No options", foreground="gray", font=("Arial", 9))

        self._update_controls_state()

    # ═══════════════════════════════════════════════════
    # Inline color picker methods
    # ═══════════════════════════════════════════════════

    def _draw_hue_bar(self):
        c = self._hue_canvas
        c.delete("all")
        h_px = 180
        for y in range(h_px):
            hue = y / h_px
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            c.create_line(0, y, 24, y, fill=color, tags="bar")
        hy = int(self._cp_hue * h_px)
        c.create_line(0, hy, 24, hy, fill="white", width=2, tags="indicator")

    def _draw_sv_square(self):
        c = self._sv_canvas
        c.delete("all")
        size = 180
        img = tk.PhotoImage(width=size, height=size)
        row_data = []
        for y in range(size):
            val = 1.0 - y / (size - 1)
            row = []
            for x in range(size):
                sat = x / (size - 1)
                r, g, b = colorsys.hsv_to_rgb(self._cp_hue, sat, val)
                row.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
            row_data.append("{" + " ".join(row) + "}")
        img.put(" ".join(row_data))
        self._sv_img = img
        c.create_image(0, 0, anchor="nw", image=img, tags="sq")
        cx = int(self._cp_sat * (size - 1))
        cy = int((1.0 - self._cp_val) * (size - 1))
        c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline="white", width=2, tags="crosshair")
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline="black", width=1, tags="crosshair")

    def _update_cp_preview(self):
        r, g, b = colorsys.hsv_to_rgb(self._cp_hue, self._cp_sat, self._cp_val)
        ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)
        hex_color = f"#{ri:02x}{gi:02x}{bi:02x}"
        self._custom_swatch.configure(bg=hex_color)
        self._hex_var.set(hex_color[1:].upper())
        self._r_label.config(text=f"R: {ri}")
        self._g_label.config(text=f"G: {gi}")
        self._b_label.config(text=f"B: {bi}")

    def _on_sv_click(self, event):
        x = max(0, min(event.x, 179))
        y = max(0, min(event.y, 179))
        self._cp_sat = x / 179
        self._cp_val = 1.0 - y / 179
        self._draw_sv_square()
        self._update_cp_preview()
        self._apply_inline_color()

    def _on_hue_click(self, event):
        y = max(0, min(event.y, 179))
        self._cp_hue = y / 179
        self._draw_hue_bar()
        self._draw_sv_square()
        self._update_cp_preview()
        self._apply_inline_color()

    def _on_hex_enter(self, event=None):
        hex_str = self._hex_var.get().strip().lstrip("#")
        if len(hex_str) == 6:
            self._set_color_from_hex(f"#{hex_str}")

    def _set_color_from_hex(self, hex_color):
        try:
            r = int(hex_color[1:3], 16) / 255
            g = int(hex_color[3:5], 16) / 255
            b = int(hex_color[5:7], 16) / 255
            self._cp_hue, self._cp_sat, self._cp_val = colorsys.rgb_to_hsv(r, g, b)
        except Exception:
            pass
        # Defer drawing until widget is mapped
        self.after(50, self._draw_hue_bar)
        self.after(50, self._draw_sv_square)
        self.after(50, self._update_cp_preview)

    def _apply_inline_color(self):
        """Apply color from inline picker to the current effect."""
        r, g, b = colorsys.hsv_to_rgb(self._cp_hue, self._cp_sat, self._cp_val)
        ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)
        hex_color = f"#{ri:02x}{gi:02x}{bi:02x}"
        self._mono_color = hex_color

        effect = self.effect_var.get()
        if effect == "per-key" and self._selected_keys:
            for k in self._selected_keys:
                self._perkey_colors[k] = hex_color
                self.keyboard_colors[k] = hex_color
                self._perkey_brightness[k] = 1.0
            self._perkey_brightness_var.set(100)
            self._brightness_lbl.config(text="100%")
            self._redraw_keyboard()
            self._apply_per_key()
        elif effect == "glow":
            for k in list(self.keyboard_colors.keys()):
                factor = self._perkey_brightness.get(k, 1.0)
                br2 = int(ri * factor)
                bg2 = int(gi * factor)
                bb2 = int(bi * factor)
                self.keyboard_colors[k] = f"#{br2:02x}{bg2:02x}{bb2:02x}"
            self._redraw_keyboard()
            # Debounce hardware write
            if self._kb_slide_job:
                self.after_cancel(self._kb_slide_job)
            self._kb_slide_job = self.after(200, self._apply_glow)
        else:
            for k in list(self.keyboard_colors.keys()):
                self.keyboard_colors[k] = hex_color
            self._redraw_keyboard()
            if self._kb_slide_job:
                self.after_cancel(self._kb_slide_job)
            self._kb_slide_job = self.after(300, self.apply_settings)

    def _init_cp_from_color(self, hex_color):
        """Set the inline color picker to a given hex color."""
        try:
            r = int(hex_color[1:3], 16) / 255
            g = int(hex_color[3:5], 16) / 255
            b = int(hex_color[5:7], 16) / 255
            self._cp_hue, self._cp_sat, self._cp_val = colorsys.rgb_to_hsv(r, g, b)
        except Exception:
            pass
        # Defer drawing until widget is mapped
        self.after(50, self._draw_hue_bar)
        self.after(50, self._draw_sv_square)
        self.after(50, self._update_cp_preview)

    # ═══════════════════════════════════════════════════
    # Brightness gauge
    # ═══════════════════════════════════════════════════

    def _draw_brightness_gauge(self, event=None):
        """Draw the yellow brightness gauge bar."""
        from ui import themes
        t = themes.get()
        g = self.brightness_gauge
        g.delete("all")
        w = g.winfo_width()
        h = g.winfo_height()
        if w < 2 or h < 2:
            return

        pct = self.keyboard_brightness_var.get()
        fill_w = int(w * pct / 100)

        if fill_w > 0:
            g.create_rectangle(0, 0, fill_w, h, fill=t["accent"], outline="")
        if fill_w < w:
            g.create_rectangle(fill_w, 0, w, h, fill=t["canvas_bg"], outline="")

        if pct >= 100:
            txt_color = t["accent_fg"]
        else:
            txt_color = t["accent"]

        if pct == 0:
            label = "\u2501 Off"
        elif pct <= 50:
            label = "\U0001f319 50%"
        else:
            label = "\U0001f31e 100%"

        g.create_text(w - 8, h // 2, text=label, anchor="e",
                      fill=txt_color, font=("Arial", 13, "bold"))
        g.create_text(8, h // 2, text="Fn+F8 to cycle", anchor="w",
                      fill=txt_color, font=("Arial", 9))

    def _update_swatch(self):
        pass

    def _update_controls_state(self):
        effect = self.effect_var.get()
        info = self.EFFECTS.get(effect, {})
        self.effect_desc_label.config(text=info.get("desc", ""))

        # Show correct color panel based on effect type
        self._palette_inner.pack_forget()
        self._custom_color_inner.pack_forget()
        self._no_color_label.pack_forget()

        if effect in ("monocolor", "per-key", "glow"):
            self._custom_color_inner.pack(fill=tk.BOTH, expand=True)
            self._init_cp_from_color(self._mono_color)
        elif info.get("has_color"):
            self._palette_inner.pack(fill=tk.X)
        else:
            self._no_color_label.pack(fill=tk.X)

        # Show/hide option widgets
        if info.get("has_speed"):
            self.speed_row.pack(side=tk.LEFT, padx=(0, 8))
        else:
            self.speed_row.pack_forget()
        if info.get("has_direction"):
            self.direction_row.pack(side=tk.LEFT, padx=(0, 8))
            if effect == "audio":
                for d, rb in self._dir_radios.items():
                    if d in ("up", "down"):
                        rb.pack(side=tk.LEFT, padx=1)
                    else:
                        rb.pack_forget()
                if self.wave_dir_var.get() not in ("up", "down"):
                    self.wave_dir_var.set("up")
            else:
                for d, rb in self._dir_radios.items():
                    rb.pack(side=tk.LEFT, padx=1)
        else:
            self.direction_row.pack_forget()
        if info.get("has_reactive"):
            self.reactive_row.pack(side=tk.LEFT, padx=(0, 8))
        else:
            self.reactive_row.pack_forget()
        if effect in ("per-key", "glow"):
            self.perkey_row.pack(side=tk.LEFT, padx=(0, 4))
        else:
            self.perkey_row.pack_forget()

        has_any = any(info.get(k) for k in ("has_speed", "has_direction", "has_reactive")) or effect in ("per-key", "glow")
        if not has_any:
            self.no_options_label.pack(side=tk.LEFT, padx=4)
        else:
            self.no_options_label.pack_forget()

    def _save_effect_settings(self):
        effect = self.effect_var.get()
        self._effect_settings[effect] = {
            "color_preset": self.color_preset_var.get(),
            "speed": self.keyboard_speed_var.get(),
            "direction": self.wave_dir_var.get(),
            "reactive": self.reactive_var.get(),
        }

    def _restore_effect_settings(self, effect):
        if effect in self._effect_settings:
            s = self._effect_settings[effect]
            self.color_preset_var.set(s.get("color_preset", "blue"))
            self.keyboard_speed_var.set(s.get("speed", 7))
            self.speed_label.config(text=str(s.get("speed", 7)))
            self.wave_dir_var.set(s.get("direction", "right"))
            self.reactive_var.set(s.get("reactive", False))
        self._update_swatch()

    def _on_effect_change(self, event=None):
        old_effect = getattr(self, '_last_effect', None)
        effect = self.effect_var.get()

        if old_effect == "per-key":
            self._perkey_colors = dict(self.keyboard_colors)
        elif old_effect == "monocolor":
            for col in self.keyboard_colors.values():
                if col and col != DEFAULT_COLOR:
                    self._mono_color = col
                    break

        if effect == "per-key" and self._perkey_colors:
            self.keyboard_colors = dict(self._perkey_colors)
        elif effect in ("monocolor", "glow") and self._mono_color and self._mono_color != DEFAULT_COLOR:
            for k in list(self.keyboard_colors.keys()):
                self.keyboard_colors[k] = self._mono_color

        self._last_effect = effect
        self._restore_effect_settings(effect)
        self._update_controls_state()
        if effect in ("per-key", "glow"):
            self._redraw_keyboard()
            if effect == "glow":
                self._apply_glow()
            else:
                self._apply_per_key()
            self.app.status_var.set(f"{'Glow' if effect == 'glow' else 'Per-key'} mode: click keys to select, adjust brightness")
        else:
            self._selected_keys.clear()
            self._redraw_keyboard()
            self.apply_settings()

    def _on_preset_change(self, event=None):
        self._update_swatch()
        self._save_effect_settings()
        self.apply_settings()

    def _on_direction_change(self, event=None):
        self._save_effect_settings()
        self.apply_settings()

    def _on_reactive_change(self):
        self._save_effect_settings()
        self.apply_settings()

    def on_speed_slide(self, value):
        self.speed_label.config(text=str(int(float(value))))
        self._save_effect_settings()
        if self._kb_slide_job:
            self.after_cancel(self._kb_slide_job)
        self._kb_slide_job = self.after(300, self.apply_settings)

    # ═══════════════════════════════════════════════════
    # Canvas / keyboard rendering
    # ═══════════════════════════════════════════════════

    def _on_canvas_resize(self, event):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._redraw_keyboard)

    def _redraw_keyboard(self):
        self._resize_job = None
        self.canvas.delete("all")
        self.key_items.clear()

        from ui import themes
        t = themes.get()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        target_ratio = 2.7
        actual_ratio = w / h
        if actual_ratio > target_ratio:
            kb_w = int(h * target_ratio)
            kb_h = h
        else:
            kb_w = w
            kb_h = int(w / target_ratio)

        x_offset = (w - kb_w) // 2
        y_offset = (h - kb_h) // 2

        unit_key_w = kb_w / 16.0
        gap = max(1, int(unit_key_w * 0.05))
        col_w = kb_w / 64.0
        row_h = kb_h / 6.0
        pad_x = gap
        pad_y = gap

        for r, row in enumerate(KEY_LAYOUT):
            col_idx = 0
            spans = self.SPAN_BY_ROW[r]
            for c, key in enumerate(row):
                span = spans[c] if c < len(spans) else 4
                if key is None:
                    col_idx += span
                    continue

                unique_key = key
                if key in ["SHIFT", "CTRL", "ALT"]:
                    unique_key = key + ("_L" if c < len(row) // 2 else "_R")

                x1 = x_offset + col_idx * col_w + pad_x
                y1 = y_offset + r * row_h + pad_y
                x2 = x_offset + (col_idx + span) * col_w - pad_x
                y2 = y_offset + (r + 1) * row_h - pad_y

                outline = "#E8B931" if unique_key in self._selected_keys else t["keycap_border"]
                outline_w = 2 if unique_key in self._selected_keys else 1
                bg_color = t["keycap_bg"]

                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=bg_color, outline=outline, width=outline_w,
                    tags=("key", f"k_{unique_key}")
                )

                sym_data = FN_KEY_SYMBOLS.get(key)
                if sym_data and isinstance(sym_data, tuple):
                    main_top_text, bottom_numpad_text = sym_data
                else:
                    main_top_text = key
                    bottom_numpad_text = ""

                key_h = y2 - y1
                if key in ("\u2190", "\u2192", "\u2191", "\u2193"):
                    font_size = max(4, int(key_h * 0.14))
                else:
                    font_size = max(3, int(key_h * 0.10))

                color = self.keyboard_colors.get(unique_key, DEFAULT_COLOR)
                if not color or len(color) != 7 or color == DEFAULT_COLOR:
                    fg = t["keycap_fg"]
                else:
                    fg = color

                cx = (x1 + x2) / 2
                text_top_id = None
                text_bottom_id = None

                if key == "SPACE":
                    font_size_space = int(font_size * 1.5)
                    top_y = y1 + (key_h * 0.15)
                    text_top_id = self.canvas.create_text(
                        cx, top_y, text=main_top_text, fill=fg,
                        font=("Arial", font_size_space, "bold"), anchor="n", tags=("key_text", f"t_{unique_key}")
                    )
                elif "\n" in main_top_text:
                    top_y = (y1 + y2) / 2
                    text_top_id = self.canvas.create_text(
                        cx, top_y, text=main_top_text, fill=fg, justify=tk.CENTER,
                        font=("Arial", font_size, "bold"), anchor="center", tags=("key_text", f"t_{unique_key}")
                    )
                else:
                    top_y = y1 + (key_h * 0.15)
                    text_top_id = self.canvas.create_text(
                        cx, top_y, text=main_top_text, fill=fg,
                        font=("Arial", font_size, "bold"), anchor="n", tags=("key_text", f"t_{unique_key}")
                    )
                    if bottom_numpad_text:
                        bottom_y = y2 - (key_h * 0.15)
                        text_bottom_id = self.canvas.create_text(
                            cx, bottom_y, text=bottom_numpad_text, fill=fg,
                            font=("Arial", font_size, "bold"), anchor="s", tags=("key_text", f"t_bot_{unique_key}")
                        )

                self.key_items[unique_key] = (rect_id, text_top_id, text_bottom_id)
                col_idx += span

    def _on_canvas_click(self, event):
        items = self.canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        for item in items:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("k_") or tag.startswith("t_"):
                    if tag.startswith("t_bot_"):
                        key_name = tag[6:]
                    elif tag.startswith("t_"):
                        key_name = tag[2:]
                    else:
                        key_name = tag[2:]
                    self.on_key_click(key_name)
                    return

    def on_key_click(self, key_name):
        effect = self.effect_var.get()
        if effect not in ("per-key", "monocolor", "glow"):
            self.app.status_var.set("Switch to 'per-key', 'monocolor', or 'glow' to edit key colors")
            return
        if effect in ("per-key", "glow"):
            if key_name in self._selected_keys:
                self._selected_keys.discard(key_name)
            else:
                self._selected_keys.add(key_name)
            self._update_selection_display()
        else:
            # monocolor — clicking key does nothing special, use inline picker
            pass

    def _on_brightness_slide(self, value):
        pct = int(float(value))
        self._brightness_lbl.config(text=f"{pct}%")
        if self._kb_slide_job:
            self.after_cancel(self._kb_slide_job)
        self._kb_slide_job = self.after(200, self._apply_brightness)

    def _apply_brightness(self):
        factor = self._perkey_brightness_var.get() / 100.0
        effect = self.effect_var.get()

        if effect == "monocolor":
            base = self._mono_color
            r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
            r, g, b = int(r * factor), int(g * factor), int(b * factor)
            scaled = f"#{r:02x}{g:02x}{b:02x}"
            for k in list(self.keyboard_colors.keys()):
                self.keyboard_colors[k] = scaled
            self._redraw_keyboard()
            self.apply_settings()
        elif effect in ("per-key", "glow"):
            targets = self._selected_keys if self._selected_keys else set(self.keyboard_colors.keys())
            for k in targets:
                self._perkey_brightness[k] = factor
                base = self._mono_color if effect == "glow" else self._perkey_colors.get(k, DEFAULT_COLOR)
                if base and len(base) == 7 and base.startswith("#"):
                    br, bg_, bb = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
                    br, bg_, bb = int(br * factor), int(bg_ * factor), int(bb * factor)
                    self.keyboard_colors[k] = f"#{br:02x}{bg_:02x}{bb:02x}"
            self._redraw_keyboard()
            self._apply_glow() if effect == "glow" else self._apply_per_key()

    def _apply_glow(self):
        if not self.app.backend:
            self.app.status_var.set("No backend available")
            return
        try:
            self.app.backend._keyboard._stop_audio_reactive()
        except Exception:
            pass
        composite = {}
        base = self._mono_color
        br, bg_, bb = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
        for key in self.keyboard_colors:
            factor = self._perkey_brightness.get(key, 1.0)
            composite[key] = (int(br * factor), int(bg_ * factor), int(bb * factor))
        try:
            self.app.backend.set_per_key_colors(composite, 100)
            self.app.status_var.set("Glow mode applied")
            if not getattr(self.app, 'is_loading', False):
                self.app.save_config()
        except Exception as exc:
            show_message(self.app.root, "Glow Error", str(exc))

    def _update_selection_display(self):
        from ui import themes
        t = themes.get()
        for key_name, items in self.key_items.items():
            rect_id = items[0]
            if key_name in self._selected_keys:
                self.canvas.itemconfigure(rect_id, outline=t["keycap_selected"], width=3)
            else:
                self.canvas.itemconfigure(rect_id, outline=t["keycap_border"], width=1)
        count = len(self._selected_keys)
        if count:
            self.app.status_var.set(f"{count} key(s) selected \u2014 use picker to set color")
            first_key = next(iter(self._selected_keys))
            brt = self._perkey_brightness.get(first_key, 1.0)
            self._perkey_brightness_var.set(int(brt * 100))
            self._brightness_lbl.config(text=f"{int(brt * 100)}%")

    def _color_selected_keys(self):
        """Apply current inline picker color to selected keys."""
        if not self._selected_keys:
            self.app.status_var.set("Select keys first by clicking them")
            return
        r, g, b = colorsys.hsv_to_rgb(self._cp_hue, self._cp_sat, self._cp_val)
        hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        for key in self._selected_keys:
            self.keyboard_colors[key] = hex_color
            self._perkey_colors[key] = hex_color
            self._perkey_brightness[key] = 1.0
        self._selected_keys.clear()
        self._redraw_keyboard()
        self.app.status_var.set("Colors set \u2014 click 'Apply' to send to hardware")

    def _clear_selected_keys(self):
        if not self._selected_keys:
            self.app.status_var.set("Select keys first")
            return
        for key in self._selected_keys:
            self.keyboard_colors[key] = DEFAULT_COLOR
        self._selected_keys.clear()
        self._redraw_keyboard()

    def _clear_all_keys(self):
        for key in list(self.keyboard_colors.keys()):
            self.keyboard_colors[key] = DEFAULT_COLOR
        self._selected_keys.clear()
        self._redraw_keyboard()

    def _apply_per_key(self):
        if not self.app.backend:
            self.app.status_var.set("No backend available")
            return
        try:
            self.app.backend._keyboard._stop_audio_reactive()
        except Exception:
            pass
        composite = {}
        colored_count = 0
        for key, color in self.keyboard_colors.items():
            if color and color != DEFAULT_COLOR:
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                composite[key] = (r, g, b)
                colored_count += 1
            else:
                composite[key] = (0, 0, 0)
        if colored_count == 0:
            self.app.status_var.set("No per-key colors set \u2014 select keys and set colors first")
            return
        try:
            brightness = self.keyboard_brightness_var.get()
            self.app.backend.set_per_key_colors(composite, brightness)
            self.app.status_var.set(f"Per-key RGB applied ({colored_count} keys)")
            if not getattr(self.app, 'is_loading', False):
                self.app.save_config()
        except Exception as exc:
            show_message(self.app.root, "Per-Key RGB Error", str(exc))

    def update_button_color(self, key_name):
        if key_name not in self.key_items:
            return
        from ui import themes
        t = themes.get()
        rect_id, text_top_id, text_bottom_id = self.key_items[key_name]
        color = sanitize_color(self.keyboard_colors.get(key_name, DEFAULT_COLOR))
        if not color or len(color) != 7 or color == DEFAULT_COLOR:
            fg = t["keycap_fg"]
        else:
            fg = color
        if text_top_id: self.canvas.itemconfigure(text_top_id, fill=fg)
        if text_bottom_id: self.canvas.itemconfigure(text_bottom_id, fill=fg)
        self.canvas.itemconfigure(rect_id, fill=t["keycap_bg"])

    def set_brightness_from_hw(self, percent):
        closest = min(self._brightness_levels, key=lambda x: abs(x - percent))
        self.keyboard_brightness_var.set(closest)
        self._draw_brightness_gauge()
        if not getattr(self.app, 'is_loading', False):
            eff = self.effect_var.get()
            if eff not in ("per-key", "glow", "off"):
                if self._kb_slide_job:
                    self.after_cancel(self._kb_slide_job)
                self._kb_slide_job = self.after(100, self.apply_settings)

    def _poll_kbd_brightness(self):
        try:
            pct = None
            state_file = Path("/tmp/nuc_kbd_brightness")
            if state_file.exists():
                pct = int(state_file.read_text().strip())
            if pct is None:
                sysfs = Path("/sys/class/leds/ite8291r3::kbd_backlight/brightness")
                if sysfs.exists():
                    hw_val = int(sysfs.read_text().strip())
                    pct = round(hw_val * 100 / 255) if hw_val > 0 else 0
            if pct is not None and pct != self.keyboard_brightness_var.get():
                self.set_brightness_from_hw(pct)
        except Exception:
            pass
        self.after(1000, self._poll_kbd_brightness)

    # ═══════════════════════════════════════════════════
    # Apply settings
    # ═══════════════════════════════════════════════════

    def apply_settings(self):
        import threading
        self._update_controls_state()
        threading.Thread(target=self._apply_settings_impl, daemon=True).start()

    def _apply_settings_impl(self):
        try:
            effect = self.effect_var.get()

            if effect != "audio" and self.app.backend and self.app.backend._keyboard:
                try:
                    self.app.backend._keyboard._stop_audio_reactive()
                except Exception:
                    pass

            if effect == "glow":
                self._apply_glow()
                return

            if effect in ("per-key",):
                if getattr(self.app, 'is_loading', False):
                    self._apply_per_key()
                else:
                    self.app.save_config()
                return

            if not self.app.backend:
                if not getattr(self.app, 'is_loading', False):
                    self.app.save_config()
                self.app.status_var.set("Keyboard config saved (hardware control unavailable).")
                return

            brightness = self.keyboard_brightness_var.get()
            hw_speed = 10 - self.keyboard_speed_var.get()

            color = None
            for key, col in self.keyboard_colors.items():
                if col and col != DEFAULT_COLOR:
                    color = (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16))
                    break
            if color is None:
                color = (255, 255, 255)

            if effect == "monocolor":
                self.app.backend.set_keyboard_backlight_brightness(brightness)
                time.sleep(0.1)
                self.app.backend.set_keyboard_backlight_color(color)
            elif effect == "off":
                self.app.backend.set_keyboard_effect("off")
            elif effect == "coding":
                # Coding mode: static green monocolor
                coding_color = (0, 255, 0)
                self.app.backend.set_keyboard_backlight_brightness(brightness)
                time.sleep(0.1)
                self.app.backend.set_keyboard_backlight_color(coding_color)
                # Update canvas
                for k in list(self.keyboard_colors.keys()):
                    self.keyboard_colors[k] = "#00ff00"
                self.after(0, self._redraw_keyboard)
            elif effect == "gaming":
                # Gaming mode: static red monocolor
                gaming_color = (255, 0, 0)
                self.app.backend.set_keyboard_backlight_brightness(brightness)
                time.sleep(0.1)
                self.app.backend.set_keyboard_backlight_color(gaming_color)
                # Update canvas
                for k in list(self.keyboard_colors.keys()):
                    self.keyboard_colors[k] = "#ff0000"
                self.after(0, self._redraw_keyboard)
            else:
                ui_color = self.color_preset_var.get()
                info = self.EFFECTS.get(effect, {})

                if not info.get("has_color"):
                    effect_color = "random"
                    ui_color = "random"
                else:
                    effect_color = self.HW_PALETTE.get(ui_color, ui_color)

                reactive = self.reactive_var.get() if info.get("has_reactive") else False
                direction = self.wave_dir_var.get() if info.get("has_direction") else None

                self.app.backend.set_keyboard_effect(
                    effect, color=effect_color, speed=hw_speed,
                    brightness=brightness, reactive=reactive, direction=direction
                )

                if ui_color != "random" and ui_color in self.PALETTE_HEX:
                    hex_color = self.PALETTE_HEX[ui_color]
                    for k in list(self.keyboard_colors.keys()):
                        self.keyboard_colors[k] = hex_color
                    self.after(0, self._redraw_keyboard)

            self.after(0, lambda: self.app.status_var.set(f"Keyboard: {effect} applied"))
            if not getattr(self.app, 'is_loading', False):
                self._save_effect_settings()
                self.after(0, self.app.save_config)
        except Exception as exc:
            if not getattr(self.app, 'is_loading', False):
                self.after(0, lambda e=exc: show_message(self.app.root, "Apply failed", f"Failed to apply keyboard settings:\n\n{e}"))

    def apply_theme(self):
        from ui import themes
        t = themes.get()

        self.canvas.configure(bg=t["keyboard_canvas_bg"])
        self.brightness_gauge.configure(bg=t["canvas_bg"])

        self.speed_slider.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                    troughcolor=t["scale_trough"],
                                    activebackground=t["scale_active"])

        self._brightness_slider.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                          troughcolor=t["scale_trough"],
                                          activebackground=t["scale_active"])

        # Inline picker canvases
        self._sv_canvas.configure(highlightbackground=t["border"])
        self._hue_canvas.configure(highlightbackground=t["border"])
        self._custom_swatch.configure(highlightbackground=t["accent"])
        self._hex_entry.configure(bg=t["bg_input"], fg=t["fg"], insertbackground=t["accent"])

        def _restyle_radios(parent):
            for child in parent.winfo_children():
                wclass = child.winfo_class()
                if wclass == "Radiobutton":
                    child.configure(fg=t["radio_fg"], bg=t["radio_bg"],
                                    selectcolor=t["radio_bg"],
                                    activebackground=t["radio_bg"],
                                    activeforeground=t["radio_fg"])
                elif wclass == "Checkbutton":
                    child.configure(fg=t["radio_fg"], bg=t["radio_bg"],
                                    selectcolor=t["radio_bg"],
                                    activebackground=t["radio_bg"],
                                    activeforeground=t["radio_fg"])
                elif wclass == "Frame" and not isinstance(child, ttk.Frame):
                    child.configure(bg=t["bg"])
                _restyle_radios(child)

        _restyle_radios(self)

        self._draw_brightness_gauge()
        self._redraw_keyboard()
        # Redraw inline picker if visible
        if self._custom_color_inner.winfo_ismapped():
            self._draw_hue_bar()
            self._draw_sv_square()
            self._update_cp_preview()
        # Repaint selection outlines with the new theme's keycap_selected color
        self._update_selection_display()

    # ═══════════════════════════════════════════════════
    # State save/load
    # ═══════════════════════════════════════════════════

    def get_state(self):
        effect = self.effect_var.get()
        if effect == "per-key":
            self._perkey_colors = dict(self.keyboard_colors)
        elif effect == "monocolor":
            for col in self.keyboard_colors.values():
                if col and col != DEFAULT_COLOR:
                    self._mono_color = col
                    break
        return {
            "keyboard_colors": self.keyboard_colors,
            "keyboard_perkey_colors": self._perkey_colors,
            "keyboard_mono_color": self._mono_color,
            "keyboard_brightness": self.keyboard_brightness_var.get(),
            "keyboard_speed": self.keyboard_speed_var.get(),
            "keyboard_effect": self.effect_var.get(),
            "keyboard_color_preset": self.color_preset_var.get(),
            "keyboard_effect_settings": self._effect_settings,
        }

    @staticmethod
    def _migrate_key_names(colors):
        ALIAS = {
            "Esc": "ESC", "Backspace": "BACKSPACE", "Tab": "TAB", "Caps": "CAPS",
            "Enter": "ENTER", "Shift": "SHIFT", "Ctrl": "CTRL", "Alt": "ALT",
            "Win": "WIN", "Space": "SPACE", "Fn": "FN", "Menu": "MENU",
            "Ins": "INS", "Del": "DEL", "Home": "HOME", "End": "END",
            "PgUp": "PGUP", "PgDn": "PGDN", "ScrLk": "SCRLK", "PrtSc": "INS",
            "Up": "\u2191", "Down": "\u2193", "Left": "\u2190", "Right": "\u2192",
        }
        migrated = {}
        for key, val in colors.items():
            canonical = ALIAS.get(key, key)
            if canonical in migrated and val in ("#262D33", "#1a1a1a", "#2d2640"):
                continue
            migrated[canonical] = val
        return migrated

    def load_state(self, data):
        if "keyboard_perkey_colors" in data:
            raw = {k: sanitize_color(v) for k, v in data["keyboard_perkey_colors"].items()}
            self._perkey_colors = self._migrate_key_names(raw)
        if "keyboard_mono_color" in data:
            self._mono_color = sanitize_color(data["keyboard_mono_color"])
        if "keyboard_colors" in data:
            raw = {k: sanitize_color(v) for k, v in data["keyboard_colors"].items()}
            self.keyboard_colors = self._migrate_key_names(raw)
        if "keyboard_brightness" in data:
            raw = data["keyboard_brightness"]
            closest = min(self._brightness_levels, key=lambda x: abs(x - raw))
            self.keyboard_brightness_var.set(closest)
            self._draw_brightness_gauge()
        if "keyboard_speed" in data:
            self.keyboard_speed_var.set(data["keyboard_speed"])
            self.speed_label.config(text=str(data["keyboard_speed"]))
        if "keyboard_effect" in data:
            eff = data["keyboard_effect"]
            if "(multi)" in eff:
                clean = eff.replace(" (multi)", "")
                eff = clean
                self.color_preset_var.set("random")
            elif "(hardware)" in eff:
                eff = eff.replace(" (hardware)", "")
            if eff == "reactive":
                eff = "random"
                self.reactive_var.set(True)
            if eff not in self.EFFECTS:
                eff = "off"
            self.effect_var.set(eff)
            self._last_effect = eff
        if "keyboard_color_preset" in data:
            preset = data["keyboard_color_preset"]
            migrate_colors = {"red": "white", "teal": "purple", "none": "random"}
            preset = migrate_colors.get(preset, preset)
            if preset not in self.PALETTE_NAMES:
                preset = "blue"
            self.color_preset_var.set(preset)
        if "keyboard_effect_settings" in data:
            self._effect_settings = data["keyboard_effect_settings"]

        self._update_controls_state()
        self._update_swatch()

        for r, row in enumerate(KEY_LAYOUT):
            for c, key in enumerate(row):
                if key is None:
                    continue
                unique_key = key
                if key in ["SHIFT", "CTRL", "ALT"]:
                    unique_key = key + ("_L" if c < len(row) // 2 else "_R")
                if unique_key not in self.keyboard_colors:
                    self.keyboard_colors[unique_key] = DEFAULT_COLOR

        self._redraw_keyboard()
        self.apply_settings()
