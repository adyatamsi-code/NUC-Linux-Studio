"""
Theme definitions for NUC Linux Studio.

Each theme is a dict of semantic color keys used throughout the UI.
"""

DARK = {
    "name": "dark",
    "label": "Dark",

    # Core backgrounds — deep indigo / purple night
    "bg": "#1A1628",
    "bg_secondary": "#2D2640",
    "bg_tertiary": "#3D3560",
    "bg_input": "#2D2640",

    # Text — warm light
    "fg": "#EDE8E0",
    "fg_secondary": "#908898",
    "fg_muted": "#5A5268",

    # Accent (gold)
    "accent": "#E8B931",
    "accent_hover": "#D4A017",
    "accent_fg": "#1A1628",

    # Tab bar
    "tab_bg": "#2D2640",
    "tab_fg": "#EDE8E0",
    "tab_selected_bg": "#E8B931",
    "tab_selected_fg": "#1A1628",
    "tab_hover_bg": "#4A4070",
    "tab_hover_fg": "#EDE8E0",

    # Borders / separators
    "border": "#3D3560",

    # Scrollbar / progress
    "trough": "#1A1628",
    "scrollbar": "#2D2640",
    "progress": "#E8B931",

    # Footer
    "footer_bg": "#2D2640",

    # Status bar
    "status_bg": "#2D2640",
    "status_fg": "#EDE8E0",

    # Buttons
    "btn_bg": "#2D2640",
    "btn_fg": "#EDE8E0",
    "btn_hover": "#D4A017",
    "btn_danger": "#C44040",
    "btn_danger_fg": "white",

    # Radio / Check buttons — gold
    "radio_fg": "#E8B931",
    "radio_bg": "#1A1628",
    "radio_indicator": "#E8B931",
    "radio_indicator_off": "#1A1628",

    # Canvas
    "canvas_bg": "#1A1628",

    # Combobox dropdown
    "combo_list_bg": "#2D2640",
    "combo_list_fg": "#EDE8E0",
    "combo_list_select": "#D4A017",

    # Slider / Scale
    "scale_bg": "#2D2640",
    "scale_trough": "#1A1628",
    "scale_fg": "#EDE8E0",
    "scale_active": "#D4A017",

    # ── Per-tab semantic colors ──────────────────────────────

    # Keyboard — dark charcoal (real keycap color)
    "keycap_bg": "#1E1C22",
    "keycap_fg": "#EDE8E0",
    "keycap_border": "#3A3648",
    "keycap_selected": "#C0C8D8",
    "keyboard_canvas_bg": "#161420",

    # Camera preview
    "camera_bg": "#0E0C16",

    # Battery gauge
    "battery_gauge_bg": "#1A1628",
    "battery_body_bg": "#1A1820",
    "battery_empty_bar": "#242030",
    "battery_pct_fg": "#E8B931",
    "battery_charge_line": "#00E676",
    "battery_fill_high": "#00E676",
    "battery_fill_mid": "#FFD740",
    "battery_fill_low": "#FF5252",
    "battery_health_track": "#242030",
    "battery_terminal": "#555555",
    "battery_terminal_outline": "#444444",

    # Lightbar chassis
    "lightbar_chassis": "#2A2440",
    "lightbar_slat": "#2A2440",
    "lightbar_slat_catch": "#3D3560",
    "lightbar_bg_rgb": (26, 22, 40),
    "lightbar_mesh": "#403860",
    "lightbar_pillar": "#201C36",
    "lightbar_pillar_hi": "#352F50",
    "lightbar_pillar_lo": "#0A0814",
    "lightbar_opening": "#0C0A16",
    "lightbar_edge_top": "#2E2848",
    "lightbar_edge_bot": "#0C0A14",
    "lightbar_frame_top": "#252040",
    "lightbar_frame_bot": "#0C0A14",

    # Service status indicators — neon green for dark theme
    "status_green": "#00E676",
    "status_red": "#FF5252",

    # Service action buttons (dark theme) — silvery gray palette
    "svc_btn_load": "#2E7D32",       # green — positive (load, install, add)
    "svc_btn_unload": "#C04040",     # red — destructive (delete, stop)
    "svc_btn_rebuild": "#858FA0",    # silver — special actions (rebuild, test)
    "svc_btn_restart": "#707888",    # dark silver — neutral (restart, refresh, snapshot)
    "svc_btn_stop": "#C04040",       # red
    "svc_btn_reset": "#C04040",      # red
    "svc_btn_secondary": "#606878",  # charcoal silver — secondary (rename, camera)

    # Branded colors
    "intel-blue": "#0071C5",
    "nvidia-green": "#76B900",

    # Fan curve
    "curve_dot_outline": "#1A1628",
    "curve_grid": "#3D3560",
    "curve_text": "#B0A8C0",
    "curve_cpu_fill": "#0C1830",
    "curve_dgpu_fill": "#142800",
    "curve_band_base": (26, 22, 40),
    "curve_band_step": (2, 1, 3),

    # Pink accent (for highlights, special items)
    "pink": "#E8508A",
    "pink_muted": "#A04068",

    # Coffee accent (warm contrast)
    "coffee": "#6B4A30",
    "coffee_light": "#8B6A4A",

    # Pale sky (info/secondary)
    "sky_blue": "#7EB8D8",
    "sky_blue_muted": "#4A7088",
}


LIGHT = {
    "name": "light",
    "label": "Light",

    # Core backgrounds — clean warm ivory / cream
    "bg": "#F2EDE6",
    "bg_secondary": "#F8F4EE",
    "bg_tertiary": "#E8E2DA",
    "bg_input": "#F8F4EE",

    # Text — dark charcoal (not brown)
    "fg": "#1E1E24",
    "fg_secondary": "#505060",
    "fg_muted": "#909098",

    # Accent — sky blue (lighter)
    "accent": "#4AAFE0",
    "accent_hover": "#3090C0",
    "accent_fg": "#FFFFFF",

    # Tab bar
    "tab_bg": "#E8E2DA",
    "tab_fg": "#1E1E24",
    "tab_selected_bg": "#4AAFE0",
    "tab_selected_fg": "#FFFFFF",
    "tab_hover_bg": "#D8D2CA",
    "tab_hover_fg": "#1E1E24",

    # Borders / separators
    "border": "#C8C0B4",

    # Scrollbar / progress
    "trough": "#E8E2DA",
    "scrollbar": "#C8C0B4",
    "progress": "#2E8BC0",

    # Footer
    "footer_bg": "#E8E2DA",

    # Status bar
    "status_bg": "#E8E2DA",
    "status_fg": "#1E1E24",

    # Buttons
    "btn_bg": "#E8E2DA",
    "btn_fg": "#1E1E24",
    "btn_hover": "#2E8BC0",
    "btn_danger": "#B03030",
    "btn_danger_fg": "white",

    # Radio / Check buttons — sky blue
    "radio_fg": "#2E8BC0",
    "radio_bg": "#F2EDE6",
    "radio_indicator": "#2E8BC0",
    "radio_indicator_off": "#F2EDE6",

    # Canvas
    "canvas_bg": "#F2EDE6",

    # Combobox dropdown
    "combo_list_bg": "#F8F4EE",
    "combo_list_fg": "#1E1E24",
    "combo_list_select": "#2E8BC0",

    # Slider / Scale
    "scale_bg": "#E8E2DA",
    "scale_trough": "#C8C0B4",
    "scale_fg": "#1E1E24",
    "scale_active": "#2E8BC0",

    # ── Per-tab semantic colors ──────────────────────────────

    # Keyboard — dark-gray charcoal (slightly lighter than night)
    "keycap_bg": "#383438",
    "keycap_fg": "#9E9690",
    "keycap_border": "#5A5658",
    "keycap_selected": "#4AAFE0",
    "keyboard_canvas_bg": "#DDD8D0",

    # Camera preview
    "camera_bg": "#C8C0B4",

    # Battery gauge
    "battery_gauge_bg": "#F2EDE6",
    "battery_body_bg": "#DDD8D0",
    "battery_empty_bar": "#C8C2BA",
    "battery_pct_fg": "#4AAFE0",
    "battery_charge_line": "#2E8B57",
    "battery_fill_high": "#388E3C",
    "battery_fill_mid": "#F9A825",
    "battery_fill_low": "#C62828",
    "battery_health_track": "#D8D2CA",
    "battery_terminal": "#888888",
    "battery_terminal_outline": "#AAAAAA",

    # Lightbar chassis
    "lightbar_chassis": "#C0B8AC",
    "lightbar_slat": "#B0A898",
    "lightbar_slat_catch": "#C8C0B4",
    "lightbar_bg_rgb": (242, 237, 230),
    "lightbar_mesh": "#A8A090",
    "lightbar_pillar": "#A09888",
    "lightbar_pillar_hi": "#B8B0A0",
    "lightbar_pillar_lo": "#908878",
    "lightbar_opening": "#888070",
    "lightbar_edge_top": "#B8B0A0",
    "lightbar_edge_bot": "#A09888",
    "lightbar_frame_top": "#B0A898",
    "lightbar_frame_bot": "#989080",

    # Service status indicators — visible grass green for light theme
    "status_green": "#2E8B57",
    "status_red": "#C62828",

    # Service action buttons (light theme) — gold palette
    "svc_btn_load": "#2E8B57",       # green — positive
    "svc_btn_unload": "#C62828",     # red — destructive
    "svc_btn_rebuild": "#B8960F",    # dark gold — special actions
    "svc_btn_restart": "#C8A830",    # gold — neutral actions
    "svc_btn_stop": "#C62828",       # red
    "svc_btn_reset": "#C62828",      # red
    "svc_btn_secondary": "#D4B440",  # light gold — secondary

    # Branded colors
    "intel-blue": "#0071C5",
    "nvidia-green": "#76B900",

    # Fan curve
    "curve_dot_outline": "#F2EDE6",
    "curve_grid": "#B0A898",
    "curve_text": "#404048",
    "curve_cpu_fill": "#C0D8EC",
    "curve_dgpu_fill": "#D8ECC0",
    "curve_band_base": (210, 206, 198),
    "curve_band_step": (-3, -3, -3),

    # Pink accent (for highlights)
    "pink": "#D04878",
    "pink_muted": "#A04060",

    # Coffee accent
    "coffee": "#6B5840",
    "coffee_light": "#8B7858",

    # Pale sky blue accent (bright, prominent)
    "sky_blue": "#2E8BC0",
    "sky_blue_muted": "#4DA8D0",
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



