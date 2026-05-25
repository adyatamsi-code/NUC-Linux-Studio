"""
Theme definitions for NUC Linux Studio.

Each theme is a dict of semantic color keys used throughout the UI.
"""

DARK = {
    "name": "dark",
    "label": "Dark",

    # Core backgrounds
    "bg": "#1a1625",
    "bg_secondary": "#2d2640",
    "bg_tertiary": "#3d3560",
    "bg_input": "#2d2640",

    # Text
    "fg": "#F0EDE5",
    "fg_secondary": "gray",
    "fg_muted": "#666",

    # Accent (gold)
    "accent": "#E8B931",
    "accent_hover": "#D4A017",
    "accent_fg": "#1a1625",  # text on accent background

    # Tab bar
    "tab_bg": "#2d2640",
    "tab_fg": "#F0EDE5",
    "tab_selected_bg": "#E8B931",
    "tab_selected_fg": "#1a1625",
    "tab_hover_bg": "#4a4070",
    "tab_hover_fg": "#F0EDE5",

    # Borders / separators
    "border": "#3d3560",

    # Scrollbar / progress
    "trough": "#1a1625",
    "scrollbar": "#2d2640",
    "progress": "#E8B931",

    # Footer
    "footer_bg": "#2d2640",

    # Status bar
    "status_bg": "#2d2640",
    "status_fg": "#F0EDE5",

    # Buttons
    "btn_bg": "#2d2640",
    "btn_fg": "#F0EDE5",
    "btn_hover": "#D4A017",
    "btn_danger": "#F44336",
    "btn_danger_fg": "white",

    # Radio / Check buttons
    "radio_fg": "#E8B931",
    "radio_bg": "#1a1625",
    "radio_indicator": "#E8B931",
    "radio_indicator_off": "#1a1625",

    # Canvas (lightbar etc.)
    "canvas_bg": "#1a1625",

    # Combobox dropdown
    "combo_list_bg": "#2d2640",
    "combo_list_fg": "#F0EDE5",
    "combo_list_select": "#D4A017",

    # Slider / Scale
    "scale_bg": "#2d2640",
    "scale_trough": "#1a1625",
    "scale_fg": "white",
    "scale_active": "#D4A017",

    # ── Per-tab semantic colors ──────────────────────────────

    # Keyboard
    "keycap_bg": "#151020",
    "keycap_fg": "#F0EDE5",
    "keycap_border": "#3d3560",
    "keyboard_canvas_bg": "#1e1833",

    # Camera preview
    "camera_bg": "#0d1117",

    # Battery gauge
    "battery_gauge_bg": "#1a1625",
    "battery_body_bg": "#1a1a1a",
    "battery_empty_bar": "#222222",
    "battery_pct_fg": "#E8B931",

    # Lightbar chassis
    "lightbar_chassis": "#2a2440",
    "lightbar_slat": "#2a2440",
    "lightbar_slat_catch": "#3d3658",
    "lightbar_bg_rgb": (26, 22, 37),
    "lightbar_mesh": "#403858",
    "lightbar_pillar": "#201c36",
    "lightbar_pillar_hi": "#352f50",
    "lightbar_pillar_lo": "#060410",
    "lightbar_opening": "#0a0812",
    "lightbar_edge_top": "#2e2845",
    "lightbar_edge_bot": "#0a0810",
    "lightbar_frame_top": "#252040",
    "lightbar_frame_bot": "#0a0810",

    # Service status indicators
    "status_green": "#4CAF50",
    "status_red": "#F44336",

    # Service action buttons
    "svc_btn_load": "#4CAF50",
    "svc_btn_unload": "#F44336",
    "svc_btn_rebuild": "#FF9800",
    "svc_btn_restart": "#2196F3",
    "svc_btn_stop": "#F44336",
    "svc_btn_reset": "#F44336",

    # Branded colors (always the same on both themes)
    "intel-blue": "#0071C5",
    "nvidia-green": "#76B900",

    # Fan curve
    "curve_dot_outline": "#1a1625",
    "curve_grid": "#3d3560",
    "curve_text": "#C0C0C0",
    "curve_cpu_fill": "#001c3a",
    "curve_dgpu_fill": "#1a2e00",
    "curve_band_base": (26, 22, 37),
    "curve_band_step": (2, 1, 3),
}


LIGHT = {
    "name": "light",
    "label": "Light",

    # Core backgrounds — warm parchment (slightly darker than pure cream)
    "bg": "#F0EBE4",
    "bg_secondary": "#F5EFE8",
    "bg_tertiary": "#E6DED4",
    "bg_input": "#F5EFE8",

    # Text — warm dark brown (not pure black)
    "fg": "#2D2420",
    "fg_secondary": "#7A6E62",
    "fg_muted": "#A89888",

    # Accent — muted indigo/plum (inverse of dark theme's gold)
    "accent": "#6B4C8A",
    "accent_hover": "#553A72",
    "accent_fg": "#FFFFFF",  # text on accent background

    # Tab bar
    "tab_bg": "#E6DED4",
    "tab_fg": "#2D2420",
    "tab_selected_bg": "#6B4C8A",
    "tab_selected_fg": "#FFFFFF",
    "tab_hover_bg": "#DDD5C8",
    "tab_hover_fg": "#2D2420",

    # Borders / separators
    "border": "#D4C8BA",

    # Scrollbar / progress
    "trough": "#E6DED4",
    "scrollbar": "#D4C8BA",
    "progress": "#6B4C8A",

    # Footer
    "footer_bg": "#E6DED4",

    # Status bar
    "status_bg": "#E6DED4",
    "status_fg": "#2D2420",

    # Buttons
    "btn_bg": "#E6DED4",
    "btn_fg": "#2D2420",
    "btn_hover": "#6B4C8A",
    "btn_danger": "#C44040",
    "btn_danger_fg": "white",

    # Radio / Check buttons — soft rose/plum
    "radio_fg": "#6B4C8A",
    "radio_bg": "#F0EBE4",
    "radio_indicator": "#6B4C8A",
    "radio_indicator_off": "#F0EBE4",

    # Canvas (lightbar etc.)
    "canvas_bg": "#F0EBE4",

    # Combobox dropdown
    "combo_list_bg": "#F5EFE8",
    "combo_list_fg": "#2D2420",
    "combo_list_select": "#6B4C8A",

    # Slider / Scale
    "scale_bg": "#E6DED4",
    "scale_trough": "#D4C8BA",
    "scale_fg": "#2D2420",
    "scale_active": "#6B4C8A",

    # ── Per-tab semantic colors ──────────────────────────────

    # Keyboard
    "keycap_bg": "#3A3A3A",
    "keycap_fg": "#E8E0D6",
    "keycap_border": "#A89888",
    "keyboard_canvas_bg": "#DDD5C8",

    # Camera preview
    "camera_bg": "#D5CCBF",

    # Battery gauge
    "battery_gauge_bg": "#F0EBE4",
    "battery_body_bg": "#DDD5C8",
    "battery_empty_bar": "#CCC4B8",
    "battery_pct_fg": "#6B4C8A",

    # Lightbar chassis
    "lightbar_chassis": "#CCC4B8",
    "lightbar_slat": "#BCB4A8",
    "lightbar_slat_catch": "#D5CCBF",
    "lightbar_bg_rgb": (240, 235, 228),
    "lightbar_mesh": "#B4ACA0",
    "lightbar_pillar": "#ACA498",
    "lightbar_pillar_hi": "#C4BCB0",
    "lightbar_pillar_lo": "#9C9488",
    "lightbar_opening": "#948C80",
    "lightbar_edge_top": "#C4BCB0",
    "lightbar_edge_bot": "#ACA498",
    "lightbar_frame_top": "#BCB4A8",
    "lightbar_frame_bot": "#A49C90",

    # Service status indicators — darker green for legibility on light bg
    "status_green": "#2E7D32",
    "status_red": "#C62828",

    # Service action buttons
    "svc_btn_load": "#2E7D32",
    "svc_btn_unload": "#C62828",
    "svc_btn_rebuild": "#E65100",
    "svc_btn_restart": "#1565C0",
    "svc_btn_stop": "#C62828",
    "svc_btn_reset": "#C62828",

    # Branded colors (always the same on both themes)
    "intel-blue": "#0071C5",
    "nvidia-green": "#76B900",

    # Fan curve
    "curve_dot_outline": "#F0EBE4",
    "curve_grid": "#BCB4A8",
    "curve_text": "#666",
    "curve_cpu_fill": "#c4dcf0",
    "curve_dgpu_fill": "#dcefc4",
    "curve_band_base": (210, 205, 198),
    "curve_band_step": (-4, -3, -5),
}


THEMES = {"dark": DARK, "light": LIGHT}

# Current active theme (module-level, set by the app)
_current = DARK


def get():
    """Return the currently active theme dict."""
    return _current


def set_theme(name):
    """Set the active theme by name."""
    global _current
    _current = THEMES.get(name, DARK)
    return _current


_theme_initialized = False


def apply_ttk_styles(style, theme=None):
    """Apply a theme dict to ttk.Style. Call after theme change."""
    global _theme_initialized
    t = theme or _current
    # Only switch to 'default' base theme once; subsequent calls just reconfigure.
    if not _theme_initialized:
        style.theme_use('default')
        _theme_initialized = True
    style.configure('TNotebook', background=t["bg"], borderwidth=0)
    style.configure('TNotebook.Tab',
                    background=t["tab_bg"], foreground=t["tab_fg"],
                    padding=[20, 8], borderwidth=0,
                    font=('Segoe UI', 10, 'bold'))
    style.map('TNotebook.Tab',
              background=[('selected', t["tab_selected_bg"]), ('active', t["tab_hover_bg"])],
              foreground=[('selected', t["tab_selected_fg"]), ('active', t["tab_hover_fg"])])

    style.configure('TFrame', background=t["bg"])
    style.configure('TLabelframe', background=t["bg"], bordercolor=t["border"])
    style.configure('TLabelframe.Label', background=t["bg"], foreground=t["accent"])
    style.configure('TLabel', background=t["bg"], foreground=t["fg"])
    # Branded label styles — foreground is always Intel blue / Nvidia green regardless of theme
    style.configure('Intel.TLabel', background=t["bg"], foreground=t["intel-blue"])
    style.configure('Nvidia.TLabel', background=t["bg"], foreground=t["nvidia-green"])
    style.configure('TButton', background=t["btn_bg"], foreground=t["btn_fg"], borderwidth=1)
    style.map('TButton', background=[('active', t["btn_hover"])])
    style.configure('TCheckbutton', background=t["bg"], foreground=t["radio_fg"],
                    font=('Arial', 10, 'bold'))
    style.map('TCheckbutton',
              background=[('active', t["bg"])],
              foreground=[('active', t["radio_fg"]), ('disabled', t["fg_muted"])],
              indicatorcolor=[('selected', t["radio_indicator"]), ('!selected', t["radio_indicator_off"])],
              indicatorrelief=[('pressed', 'flat')],
              indicatorbackground=[('selected', t["radio_indicator"]), ('!selected', t["radio_indicator_off"])])
    style.configure('TRadiobutton', background=t["bg"], foreground=t["radio_fg"],
                    font=('Arial', 10, 'bold'), indicatormargin=4)
    style.map('TRadiobutton',
              background=[('active', t["bg"])],
              foreground=[('active', t["radio_fg"]), ('disabled', t["fg_muted"])],
              indicatorcolor=[('selected', t["radio_indicator"]), ('!selected', t["radio_indicator_off"])],
              indicatorrelief=[('pressed', 'flat')])
    style.configure('TCombobox',
                    fieldbackground=t["bg_input"], background=t["bg_secondary"],
                    foreground=t["fg"], selectbackground=t["accent_hover"])
    style.map('TCombobox',
              fieldbackground=[('readonly', t["bg_input"])],
              foreground=[('readonly', t["fg"])])
    style.configure('Vertical.TScrollbar', background=t["scrollbar"], troughcolor=t["trough"])
    style.configure('TEntry', fieldbackground=t["bg_input"], foreground=t["fg"])
    style.configure('TProgressbar', troughcolor=t["trough"], background=t["progress"])

    # Kill default blue focus rectangles and selection colors
    style.configure('.', focuscolor=t["bg"], selectbackground=t["accent"],
                    selectforeground=t["accent_fg"])
    style.configure('TButton', focuscolor=t["btn_bg"])
    style.map('TButton',
              background=[('active', t["accent"]), ('pressed', t["accent_hover"]),
                          ('!disabled', t["btn_bg"])],
              foreground=[('active', t["accent_fg"]), ('!disabled', t["btn_fg"])])



