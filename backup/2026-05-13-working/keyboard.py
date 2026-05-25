import time
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from backend import BackendError
from ..utils import KEY_LAYOUT, FN_KEY_SYMBOLS, DEFAULT_COLOR, sanitize_color, get_closest_color, show_message
from ..color_picker import ask_color

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
        "coding": "💻", "gaming": "🎮", "off": "⭘",
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
        "coding":     {"has_color": True,  "has_speed": False, "has_direction": False, "has_reactive": True,  "desc": "Coding mode (reactive typing)"},
        "gaming":     {"has_color": True,  "has_speed": False, "has_direction": False, "has_reactive": True,  "desc": "Gaming mode (WASD highlight)"},
        "per-key":    {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Individual key colors"},
        "off":        {"has_color": False, "has_speed": False, "has_direction": False, "has_reactive": False, "desc": "Keyboard off"},
    }

    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.keyboard_colors = {}
        self._perkey_colors = {}
        self._mono_color = "#FFFFFF"
        self.key_items = {}
        self._kb_slide_job = None
        self._selected_keys = set()
        self._resize_job = None
        self._effect_settings = {}

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

        # Yellow gauge canvas fills the entire brightness bar
        self.brightness_gauge = tk.Canvas(brightness_frame, bg=self.app.theme["canvas_bg"], highlightthickness=0)
        self.brightness_gauge.pack(fill=tk.BOTH, expand=True)
        self.brightness_gauge.bind("<Configure>", self._draw_brightness_gauge)

        # MIDDLE: Keyboard canvas
        from ui import themes
        t = themes.get()
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
            rb.grid(row=i // 7, column=i % 7, sticky="w", padx=2, pady=1)

        # Row 2: Colors as horizontal radio buttons with swatches
        colors_frame = ttk.LabelFrame(controls_frame, text="Color", padding=4)
        colors_frame.pack(fill=tk.X, pady=(0, 4))

        self.color_preset_var = tk.StringVar(value="blue")
        self._color_radios = {}
        col_inner = ttk.Frame(colors_frame)
        col_inner.pack(fill=tk.X)
        for i, color_name in enumerate(self.PALETTE_NAMES):
            rf = ttk.Frame(col_inner)
            rf.grid(row=0, column=i, padx=4, pady=1)
            swatch = tk.Canvas(rf, width=20, height=20, highlightthickness=0,
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

        # Row 3: Options (speed, direction, reactive, per-key) — single row, fixed height
        self.options_frame = ttk.LabelFrame(controls_frame, text="Options", padding=4)
        self.options_frame.pack(fill=tk.X, pady=(0, 2))

        opt_inner = ttk.Frame(self.options_frame, height=56)
        opt_inner.pack(fill=tk.X)
        opt_inner.pack_propagate(False)
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

        # Direction (radio buttons)
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

        # Draw yellow fill
        if fill_w > 0:
            g.create_rectangle(0, 0, fill_w, h, fill=t["accent"], outline="")
        # Draw empty portion in theme bg
        if fill_w < w:
            g.create_rectangle(fill_w, 0, w, h, fill=t["canvas_bg"], outline="")

        # Text colors depend on brightness level
        if pct >= 100:
            txt_color = t["accent_fg"]  # dark on accent
        else:
            txt_color = t["accent"]  # accent on dark

        # Draw labels
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
        pass  # Color swatches are now inline with radio buttons

    def _update_controls_state(self):
        effect = self.effect_var.get()
        info = self.EFFECTS.get(effect, {})
        self.effect_desc_label.config(text=info.get("desc", ""))

        # Enable/disable color radio buttons
        color_state = tk.NORMAL if info.get("has_color") else tk.DISABLED
        for rb in self._color_radios.values():
            rb.config(state=color_state)

        # Show/hide option widgets (all packed side=LEFT in opt_inner)
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
        if effect == "per-key":
            self.perkey_row.pack(side=tk.LEFT, padx=(0, 4))
        else:
            self.perkey_row.pack_forget()

        has_any = any(info.get(k) for k in ("has_speed", "has_direction", "has_reactive")) or effect == "per-key"
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
        elif effect == "monocolor" and self._mono_color and self._mono_color != DEFAULT_COLOR:
            for k in list(self.keyboard_colors.keys()):
                self.keyboard_colors[k] = self._mono_color

        self._last_effect = effect
        self._restore_effect_settings(effect)
        self._update_controls_state()
        if effect == "per-key":
            self._redraw_keyboard()
            self._apply_per_key()
            self.app.status_var.set("Per-key mode: click keys to select, then 'Set Color'")
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
        if effect != "per-key" and effect != "monocolor":
            self.app.status_var.set("Switch to 'per-key' or 'monocolor' to edit key colors")
            return
        if effect == "per-key":
            if key_name in self._selected_keys:
                self._selected_keys.discard(key_name)
            else:
                self._selected_keys.add(key_name)
            self._update_selection_display()
        else:
            current = sanitize_color(self.keyboard_colors.get(key_name, DEFAULT_COLOR))
            # Defer color picker to next event loop iteration to avoid canvas click
            # interfering with dialog grab/rendering
            self.after(10, lambda: self._open_mono_color_picker(current))

    def _open_mono_color_picker(self, initial_color):
        rgb, hex_color = ask_color(self.winfo_toplevel(), initial_color, "Set keyboard color")
        if hex_color:
            for k in list(self.keyboard_colors.keys()):
                self.keyboard_colors[k] = hex_color
            self._redraw_keyboard()
            self.apply_settings()

    def _update_selection_display(self):
        from ui import themes
        t = themes.get()
        for key_name, items in self.key_items.items():
            rect_id = items[0]
            if key_name in self._selected_keys:
                self.canvas.itemconfigure(rect_id, outline="#E8B931", width=2)
            else:
                self.canvas.itemconfigure(rect_id, outline=t["keycap_border"], width=1)
        count = len(self._selected_keys)
        if count:
            self.app.status_var.set(f"{count} key(s) selected \u2014 click 'Set Color' to apply")

    def _color_selected_keys(self):
        if not self._selected_keys:
            self.app.status_var.set("Select keys first by clicking them")
            return
        rgb, hex_color = ask_color(self.winfo_toplevel(), "#ffffff", f"Set color for {len(self._selected_keys)} key(s)")
        if hex_color:
            for key in self._selected_keys:
                self.keyboard_colors[key] = hex_color
            self._selected_keys.clear()
            self._redraw_keyboard()
            self.app.status_var.set("Colors set \u2014 click 'Apply Per-Key' to send to hardware")

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
        # Stop audio daemon if it was running (audio→per-key transition)
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
            if eff not in ("per-key", "off"):
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
        """Apply keyboard settings in background thread to keep UI responsive."""
        import threading
        self._update_controls_state()
        threading.Thread(target=self._apply_settings_impl, daemon=True).start()

    def _apply_settings_impl(self):
        try:
            effect = self.effect_var.get()

            # Ensure audio daemon is stopped when switching to any non-audio effect
            if effect != "audio" and self.app.backend and self.app.backend._keyboard:
                try:
                    self.app.backend._keyboard._stop_audio_reactive()
                except Exception:
                    pass

            if effect == "per-key":
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
                # Coding mode: breathing green with reactive keypresses
                ui_color = self.color_preset_var.get()
                effect_color = self.HW_PALETTE.get(ui_color, "green")
                reactive = self.reactive_var.get()
                self.app.backend.set_keyboard_backlight_brightness(brightness)
                time.sleep(0.1)
                self.app.backend.set_keyboard_effect(
                    "breathing", color=effect_color, speed=hw_speed,
                    brightness=brightness, reactive=reactive, direction=None
                )
                # Update canvas with the UI color
                if ui_color in self.PALETTE_HEX:
                    hex_color = self.PALETTE_HEX[ui_color]
                    for k in list(self.keyboard_colors.keys()):
                        self.keyboard_colors[k] = hex_color
                    self.after(0, self._redraw_keyboard)
            elif effect == "gaming":
                # Gaming mode: fireworks with reactive keypresses
                ui_color = self.color_preset_var.get()
                effect_color = self.HW_PALETTE.get(ui_color, "red")
                reactive = self.reactive_var.get()
                self.app.backend.set_keyboard_backlight_brightness(brightness)
                time.sleep(0.1)
                self.app.backend.set_keyboard_effect(
                    "fireworks", color=effect_color, speed=hw_speed,
                    brightness=brightness, reactive=reactive, direction=None
                )
                # Update canvas with the UI color
                if ui_color in self.PALETTE_HEX:
                    hex_color = self.PALETTE_HEX[ui_color]
                    for k in list(self.keyboard_colors.keys()):
                        self.keyboard_colors[k] = hex_color
                    self.after(0, self._redraw_keyboard)
            else:
                ui_color = self.color_preset_var.get()  # UI name (e.g. "white")
                info = self.EFFECTS.get(effect, {})

                if not info.get("has_color"):
                    effect_color = "random"
                    ui_color = "random"
                else:
                    # Map user-friendly name to hardware palette name
                    effect_color = self.HW_PALETTE.get(ui_color, ui_color)

                reactive = self.reactive_var.get() if info.get("has_reactive") else False
                direction = self.wave_dir_var.get() if info.get("has_direction") else None

                self.app.backend.set_keyboard_effect(
                    effect, color=effect_color, speed=hw_speed,
                    brightness=brightness, reactive=reactive, direction=direction
                )

                # Update keyboard canvas with the UI color
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
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()

        # Canvas backgrounds
        self.canvas.configure(bg=t["keyboard_canvas_bg"])
        self.brightness_gauge.configure(bg=t["canvas_bg"])

        # Speed slider
        self.speed_slider.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                    troughcolor=t["scale_trough"],
                                    activebackground=t["scale_active"])

        # All radiobuttons in effects and colors
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

        # Redraw
        self._draw_brightness_gauge()
        self._redraw_keyboard()

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
            # Migrate old effect names
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
            # Migrate old color names to match current UI names
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
