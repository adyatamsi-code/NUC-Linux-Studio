"""Custom dark-themed color picker for NUC Linux Studio."""
import tkinter as tk
from tkinter import ttk
import colorsys


class ColorPickerDialog(tk.Toplevel):
    """A dark-themed color picker dialog with hue bar, saturation/value square, and hex input."""

    def __init__(self, parent, initial_color="#ffffff", title="Choose Color"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg="#1a1625")
        self.geometry("620x440")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._hue = 0.0
        self._sat = 1.0
        self._val = 1.0

        # Parse initial color
        try:
            r = int(initial_color[1:3], 16)
            g = int(initial_color[3:5], 16)
            b = int(initial_color[5:7], 16)
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            self._hue = h
            self._sat = s
            self._val = v
        except Exception:
            pass

        self._build_ui()
        # Force window to render and map before drawing canvases
        self.update()
        self._draw_hue_bar()
        self._draw_sv_square()
        self._update_preview()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _build_ui(self):
        # Main layout: SV square (left) + Hue bar (right)
        top = tk.Frame(self, bg="#1a1625")
        top.pack(fill=tk.BOTH, expand=True, padx=16, pady=(16, 8))

        # SV square (256x256)
        self._sv_canvas = tk.Canvas(top, width=256, height=256, bg="#000",
                                     highlightthickness=1, highlightbackground="#3d3560",
                                     cursor="crosshair")
        self._sv_canvas.pack(side=tk.LEFT, padx=(0, 12))
        self._sv_canvas.bind("<Button-1>", self._on_sv_click)
        self._sv_canvas.bind("<B1-Motion>", self._on_sv_click)

        # Right column: hue bar + preview + controls
        right = tk.Frame(top, bg="#1a1625")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Hue bar (30x256)
        self._hue_canvas = tk.Canvas(right, width=30, height=256, bg="#000",
                                      highlightthickness=1, highlightbackground="#3d3560",
                                      cursor="hand2")
        self._hue_canvas.pack(side=tk.LEFT, padx=(0, 12))
        self._hue_canvas.bind("<Button-1>", self._on_hue_click)
        self._hue_canvas.bind("<B1-Motion>", self._on_hue_click)

        # Preview + controls
        ctrl = tk.Frame(right, bg="#1a1625")
        ctrl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Color preview
        self._preview = tk.Canvas(ctrl, width=120, height=80, highlightthickness=1,
                                   highlightbackground="#3d3560")
        self._preview.pack(pady=(0, 12))

        # Hex input
        hex_frame = tk.Frame(ctrl, bg="#1a1625")
        hex_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(hex_frame, text="#", bg="#1a1625", fg="#E8B931",
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        self._hex_var = tk.StringVar()
        self._hex_entry = tk.Entry(hex_frame, textvariable=self._hex_var, width=8,
                                    font=("Arial", 12), bg="#2d2640", fg="#F0EDE5",
                                    insertbackground="#E8B931", relief="flat", bd=2)
        self._hex_entry.pack(side=tk.LEFT, padx=(2, 0))
        self._hex_entry.bind("<Return>", self._on_hex_enter)
        self._hex_entry.bind("<FocusOut>", self._on_hex_enter)

        # RGB labels
        rgb_frame = tk.Frame(ctrl, bg="#1a1625")
        rgb_frame.pack(fill=tk.X, pady=(0, 8))
        self._r_label = tk.Label(rgb_frame, text="R: 255", bg="#1a1625", fg="#ff6666", font=("Arial", 10))
        self._r_label.pack(side=tk.LEFT, padx=(4, 6))
        self._g_label = tk.Label(rgb_frame, text="G: 255", bg="#1a1625", fg="#66ff66", font=("Arial", 10))
        self._g_label.pack(side=tk.LEFT, padx=(0, 6))
        self._b_label = tk.Label(rgb_frame, text="B: 255", bg="#1a1625", fg="#6688ff", font=("Arial", 10))
        self._b_label.pack(side=tk.LEFT)

        # Quick color presets
        presets_frame = tk.Frame(ctrl, bg="#1a1625")
        presets_frame.pack(fill=tk.X, pady=(0, 8))
        presets = [
            "#FF0000", "#FF8000", "#FFFF00", "#00FF00",
            "#00FFFF", "#0000FF", "#8000FF", "#FF00FF",
            "#FFFFFF", "#FFB0E0", "#FF4444", "#000000",
        ]
        for i, color in enumerate(presets):
            btn = tk.Canvas(presets_frame, width=22, height=22, bg=color,
                            highlightthickness=1, highlightbackground="#3d3560",
                            cursor="hand2")
            btn.grid(row=i // 4, column=i % 4, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=color: self._set_from_hex(c))

    # Bottom buttons
        btn_frame = tk.Frame(self, bg="#1a1625")
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 16))
        tk.Button(btn_frame, text="OK", font=("Arial", 11, "bold"),
                  fg="white", bg="#4CAF50", relief="flat", padx=20, pady=6,
                  command=self._on_ok).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", font=("Arial", 11),
                  fg="white", bg="#555", relief="flat", padx=20, pady=6,
                  command=self._on_cancel).pack(side=tk.LEFT)

    def _draw_hue_bar(self):
        """Draw vertical rainbow hue bar."""
        c = self._hue_canvas
        c.delete("bar")
        h_px = 256
        for y in range(h_px):
            hue = y / h_px
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            c.create_line(0, y, 30, y, fill=color, tags="bar")
        # Draw hue indicator
        hy = int(self._hue * h_px)
        c.create_line(0, hy, 30, hy, fill="white", width=2, tags="hue_indicator")

    def _draw_sv_square(self):
        """Draw saturation (x) / value (y) square for current hue."""
        c = self._sv_canvas
        c.delete("sq")
        size = 256
        # Use PhotoImage for speed
        img = tk.PhotoImage(width=size, height=size)
        row_data = []
        for y in range(size):
            val = 1.0 - y / (size - 1)
            row = []
            for x in range(size):
                sat = x / (size - 1)
                r, g, b = colorsys.hsv_to_rgb(self._hue, sat, val)
                row.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
            row_data.append("{" + " ".join(row) + "}")
        img.put(" ".join(row_data))
        self._sv_img = img  # prevent GC
        c.create_image(0, 0, anchor="nw", image=img, tags="sq")
        # Draw crosshair
        cx = int(self._sat * (size - 1))
        cy = int((1.0 - self._val) * (size - 1))
        c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline="white", width=2, tags="sq")
        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline="black", width=1, tags="sq")

    def _update_preview(self):
        r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
        ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)
        hex_color = f"#{ri:02x}{gi:02x}{bi:02x}"
        self._preview.configure(bg=hex_color)
        self._hex_var.set(hex_color[1:].upper())
        self._r_label.config(text=f"R: {ri}")
        self._g_label.config(text=f"G: {gi}")
        self._b_label.config(text=f"B: {bi}")

    def _on_sv_click(self, event):
        x = max(0, min(event.x, 255))
        y = max(0, min(event.y, 255))
        self._sat = x / 255
        self._val = 1.0 - y / 255
        self._draw_sv_square()
        self._update_preview()

    def _on_hue_click(self, event):
        y = max(0, min(event.y, 255))
        self._hue = y / 255
        self._hue_canvas.delete("hue_indicator")
        self._hue_canvas.create_line(0, y, 30, y, fill="white", width=2, tags="hue_indicator")
        self._draw_sv_square()
        self._update_preview()

    def _on_hex_enter(self, event=None):
        hex_str = self._hex_var.get().strip().lstrip("#")
        if len(hex_str) == 6:
            self._set_from_hex(f"#{hex_str}")

    def _set_from_hex(self, hex_color):
        try:
            r = int(hex_color[1:3], 16) / 255
            g = int(hex_color[3:5], 16) / 255
            b = int(hex_color[5:7], 16) / 255
            self._hue, self._sat, self._val = colorsys.rgb_to_hsv(r, g, b)
            self._draw_hue_bar()
            self._draw_sv_square()
            self._update_preview()
        except Exception:
            pass

    def _on_ok(self):
        r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
        ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)
        self.result = ((ri, gi, bi), f"#{ri:02x}{gi:02x}{bi:02x}")
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def ask_color(parent, initial_color="#ffffff", title="Choose Color"):
    """Show the custom color picker and return (rgb_tuple, hex_string) or (None, None)."""
    dlg = ColorPickerDialog(parent, initial_color, title)
    dlg.wait_window()
    if dlg.result:
        return dlg.result
    return None, None

