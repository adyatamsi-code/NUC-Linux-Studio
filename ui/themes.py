"""
Theme definitions for NUC Linux Studio.

Three desert-inspired themes — a day/night/dusk cycle over the Sahara:

  NIGHT — Ancient Egypt, starry desert night.  Deep lapis-lazuli sky, Milky Way silver,
           pharaoh gold glowing on dark stone.
  DUSK  — Desert sunset / sunrise. Burnt-orange sky, deep violet shadows, amber warmth.
  DAY   — Desert noon / Oasis. Warm sandstone, sky blue, oasis greens.

Cycle: night → dusk → day → night    icons: 🌙 → 🌅 → ☀ → 🌙
Default theme: dusk
"""

# ══════════════════════════════════════════════════════════════════════════════
#  NIGHT — Ancient Egypt / starry desert night
# ══════════════════════════════════════════════════════════════════════════════
NIGHT = {
    "name": "night", "label": "Night",
    "bg": "#100E1C", "bg_secondary": "#1A1730", "bg_tertiary": "#272345", "bg_input": "#1A1730",
    "fg": "#EEE8D8", "fg_secondary": "#A098B0", "fg_muted": "#504868",
    "accent": "#E8B931", "accent_hover": "#C89820", "accent_fg": "#100E1C",
    "tab_bg": "#1A1730", "tab_fg": "#EEE8D8",
    "tab_selected_bg": "#E8B931", "tab_selected_fg": "#100E1C",
    "tab_hover_bg": "#302C50", "tab_hover_fg": "#EEE8D8",
    "border": "#302C50",
    "trough": "#100E1C", "scrollbar": "#1A1730", "progress": "#E8B931",
    "footer_bg": "#1A1730", "status_bg": "#1A1730", "status_fg": "#EEE8D8",
    "btn_bg": "#1A1730", "btn_fg": "#EEE8D8", "btn_hover": "#C89820",
    "btn_danger": "#C04040", "btn_danger_fg": "#EEE8D8",
    "radio_fg": "#E8B931", "radio_bg": "#100E1C",
    "radio_indicator": "#E8B931", "radio_indicator_off": "#100E1C",
    "canvas_bg": "#0C0A18",
    "combo_list_bg": "#1A1730", "combo_list_fg": "#EEE8D8", "combo_list_select": "#C89820",
    "scale_bg": "#1A1730", "scale_trough": "#100E1C",
    "scale_trough_cpu": "#0A1020", "scale_trough_gpu": "#0A1808",
    "scale_fg": "#EEE8D8", "scale_active": "#C89820",
    "keycap_bg": "#181420", "keycap_fg": "#EEE8D8", "keycap_border": "#302C50",
    "keycap_selected": "#E8B931", "keyboard_canvas_bg": "#0C0A18",
    "camera_bg": "#0A0818",
    "battery_gauge_bg": "#100E1C", "battery_body_bg": "#141220",
    "battery_empty_bar": "#201C34", "battery_pct_fg": "#E8B931",
    "battery_charge_line": "#00E676", "battery_fill_high": "#00E676",
    "battery_fill_mid": "#FFD740", "battery_fill_low": "#FF5252",
    "battery_health_track": "#201C34",
    "battery_terminal": "#404060", "battery_terminal_outline": "#302C50",
    "lightbar_chassis": "#181430", "lightbar_slat": "#181430",
    "lightbar_slat_catch": "#272345", "lightbar_bg_rgb": (16, 14, 28),
    "lightbar_mesh": "#302C50", "lightbar_pillar": "#0E0C20",
    "lightbar_pillar_hi": "#252040", "lightbar_pillar_lo": "#08060E",
    "lightbar_opening": "#080610", "lightbar_edge_top": "#201C38",
    "lightbar_edge_bot": "#080610", "lightbar_frame_top": "#181430",
    "lightbar_frame_bot": "#080610",
    "status_green": "#00E676", "status_red": "#FF5252",
    "svc_btn_load": "#2E7D32", "svc_btn_unload": "#C04040",
    "svc_btn_rebuild": "#706880", "svc_btn_restart": "#585070",
    "svc_btn_stop": "#C04040", "svc_btn_reset": "#C04040", "svc_btn_secondary": "#504860",
    "intel-blue": "#0071C5", "nvidia-green": "#76B900",
    "curve_dot_outline": "#100E1C", "curve_grid": "#272345", "curve_text": "#908898",
    "curve_cpu_fill": "#08102A", "curve_dgpu_fill": "#081A08",
    "curve_band_base": (16, 14, 28), "curve_band_step": (2, 1, 3),
    "pink": "#E8508A", "pink_muted": "#903050",
    "coffee": "#6B4A30", "coffee_light": "#8B6A4A",
    "sky_blue": "#7EB8D8", "sky_blue_muted": "#4A7088",
}

# ══════════════════════════════════════════════════════════════════════════════
#  DUSK — Desert sunset / sunrise  ← DEFAULT
# ══════════════════════════════════════════════════════════════════════════════
DUSK = {
    "name": "dusk", "label": "Dusk",
    "bg": "#1C1228", "bg_secondary": "#2A1C3C", "bg_tertiary": "#3A2850", "bg_input": "#2A1C3C",
    "fg": "#F0DEC0", "fg_secondary": "#C09060", "fg_muted": "#785040",
    "accent": "#F07030", "accent_hover": "#D05010", "accent_fg": "#1C1228",
    "tab_bg": "#2A1C3C", "tab_fg": "#F0DEC0",
    "tab_selected_bg": "#F07030", "tab_selected_fg": "#1C1228",
    "tab_hover_bg": "#3E2A54", "tab_hover_fg": "#F0DEC0",
    "border": "#3E2A54",
    "trough": "#1C1228", "scrollbar": "#2A1C3C", "progress": "#F07030",
    "footer_bg": "#2A1C3C", "status_bg": "#2A1C3C", "status_fg": "#F0DEC0",
    "btn_bg": "#2A1C3C", "btn_fg": "#F0DEC0", "btn_hover": "#D05010",
    "btn_danger": "#C03030", "btn_danger_fg": "#F0DEC0",
    "radio_fg": "#F07030", "radio_bg": "#1C1228",
    "radio_indicator": "#F07030", "radio_indicator_off": "#1C1228",
    "canvas_bg": "#160E20",
    "combo_list_bg": "#2A1C3C", "combo_list_fg": "#F0DEC0", "combo_list_select": "#D05010",
    "scale_bg": "#2A1C3C", "scale_trough": "#1C1228",
    "scale_trough_cpu": "#180E28", "scale_trough_gpu": "#181018",
    "scale_fg": "#F0DEC0", "scale_active": "#D05010",
    "keycap_bg": "#201428", "keycap_fg": "#F0DEC0", "keycap_border": "#3E2A54",
    "keycap_selected": "#F07030", "keyboard_canvas_bg": "#150E1E",
    "camera_bg": "#100C1A",
    "battery_gauge_bg": "#1C1228", "battery_body_bg": "#201428",
    "battery_empty_bar": "#2E1E40", "battery_pct_fg": "#F07030",
    "battery_charge_line": "#00E676", "battery_fill_high": "#00E676",
    "battery_fill_mid": "#FFD740", "battery_fill_low": "#FF5252",
    "battery_health_track": "#2E1E40",
    "battery_terminal": "#604050", "battery_terminal_outline": "#502840",
    "lightbar_chassis": "#201428", "lightbar_slat": "#201428",
    "lightbar_slat_catch": "#3A2850", "lightbar_bg_rgb": (28, 18, 40),
    "lightbar_mesh": "#3E2A54", "lightbar_pillar": "#160E22",
    "lightbar_pillar_hi": "#2E1E40", "lightbar_pillar_lo": "#0C0814",
    "lightbar_opening": "#0A0610", "lightbar_edge_top": "#281A3C",
    "lightbar_edge_bot": "#0C0812", "lightbar_frame_top": "#201430",
    "lightbar_frame_bot": "#0C0812",
    "status_green": "#40C080", "status_red": "#F05050",
    "svc_btn_load": "#2E7D40", "svc_btn_unload": "#C04040",
    "svc_btn_rebuild": "#906050", "svc_btn_restart": "#804840",
    "svc_btn_stop": "#C04040", "svc_btn_reset": "#C04040", "svc_btn_secondary": "#704040",
    "intel-blue": "#0071C5", "nvidia-green": "#76B900",
    "curve_dot_outline": "#1C1228", "curve_grid": "#3A2850", "curve_text": "#C09060",
    "curve_cpu_fill": "#180E28", "curve_dgpu_fill": "#180E18",
    "curve_band_base": (28, 18, 40), "curve_band_step": (3, 1, 2),
    "pink": "#F05080", "pink_muted": "#A03060",
    "coffee": "#7A5030", "coffee_light": "#9A7048",
    "sky_blue": "#8070D0", "sky_blue_muted": "#604090",
}

# ══════════════════════════════════════════════════════════════════════════════
#  DAY — Desert noon / Oasis
# ══════════════════════════════════════════════════════════════════════════════
DAY = {
    "name": "day", "label": "Day",
    "bg": "#F5EDD8", "bg_secondary": "#EDE0C4", "bg_tertiary": "#E0D0B0", "bg_input": "#F0E8D0",
    "fg": "#2A2010", "fg_secondary": "#5A4830", "fg_muted": "#988060",
    "accent": "#2A90D0", "accent_hover": "#1870A8", "accent_fg": "#FFFFFF",
    "tab_bg": "#E0D0B0", "tab_fg": "#2A2010",
    "tab_selected_bg": "#2A90D0", "tab_selected_fg": "#FFFFFF",
    "tab_hover_bg": "#D0C098", "tab_hover_fg": "#2A2010",
    "border": "#C8B890",
    "trough": "#E0D0B0", "scrollbar": "#C8B890", "progress": "#2A90D0",
    "footer_bg": "#E0D0B0", "status_bg": "#E0D0B0", "status_fg": "#2A2010",
    "btn_bg": "#EDE0C4", "btn_fg": "#2A2010", "btn_hover": "#1870A8",
    "btn_danger": "#B03028", "btn_danger_fg": "#FFFFFF",
    "radio_fg": "#2A90D0", "radio_bg": "#F5EDD8",
    "radio_indicator": "#2A90D0", "radio_indicator_off": "#F5EDD8",
    "canvas_bg": "#F8F0E0",
    "combo_list_bg": "#F0E8D0", "combo_list_fg": "#2A2010", "combo_list_select": "#1870A8",
    "scale_bg": "#EDE0C4", "scale_trough": "#C8B890",
    "scale_trough_cpu": "#B8D0E8", "scale_trough_gpu": "#B8D8B0",
    "scale_fg": "#2A2010", "scale_active": "#1870A8",
    "keycap_bg": "#363028", "keycap_fg": "#A09078", "keycap_border": "#585040",
    "keycap_selected": "#2A90D0", "keyboard_canvas_bg": "#D8C8A8",
    "camera_bg": "#C8B890",
    "battery_gauge_bg": "#F5EDD8", "battery_body_bg": "#E0D0B0",
    "battery_empty_bar": "#C8B890", "battery_pct_fg": "#2A90D0",
    "battery_charge_line": "#2E8B57", "battery_fill_high": "#388E3C",
    "battery_fill_mid": "#F9A825", "battery_fill_low": "#C62828",
    "battery_health_track": "#D8C8A8",
    "battery_terminal": "#808060", "battery_terminal_outline": "#A09070",
    "lightbar_chassis": "#C8B890", "lightbar_slat": "#B8A880",
    "lightbar_slat_catch": "#C8B890", "lightbar_bg_rgb": (245, 237, 216),
    "lightbar_mesh": "#A89870", "lightbar_pillar": "#A09060",
    "lightbar_pillar_hi": "#B8A878", "lightbar_pillar_lo": "#907850",
    "lightbar_opening": "#887050", "lightbar_edge_top": "#B8A878",
    "lightbar_edge_bot": "#A09060", "lightbar_frame_top": "#B0A070",
    "lightbar_frame_bot": "#988860",
    "status_green": "#2E8B57", "status_red": "#C62828",
    "svc_btn_load": "#2E7D2A", "svc_btn_unload": "#B02828",
    "svc_btn_rebuild": "#A09050", "svc_btn_restart": "#B8A050",
    "svc_btn_stop": "#B02828", "svc_btn_reset": "#B02828", "svc_btn_secondary": "#C8A840",
    "intel-blue": "#0071C5", "nvidia-green": "#76B900",
    "curve_dot_outline": "#F5EDD8", "curve_grid": "#C8B890", "curve_text": "#504030",
    "curve_cpu_fill": "#C0D8EC", "curve_dgpu_fill": "#C8E8B8",
    "curve_band_base": (224, 208, 176), "curve_band_step": (-4, -3, -2),
    "pink": "#C84070", "pink_muted": "#A04060",
    "coffee": "#6B5030", "coffee_light": "#8B7050",
    "sky_blue": "#2A90D0", "sky_blue_muted": "#4AA8D0",
}


# ── Theme registry ─────────────────────────────────────────────────────────────
DARK  = NIGHT   # backward-compat alias
LIGHT = DAY     # backward-compat alias

THEMES = {
    "night": NIGHT,
    "dusk":  DUSK,
    "day":   DAY,
    "dark":  NIGHT,   # legacy saved config value
    "light": DAY,     # legacy saved config value
}

# Cycle: night → dusk → day → night
THEME_CYCLE = ["night", "dusk", "day"]
THEME_ICONS  = {"night": "🌙", "dusk": "🌅", "day": "☀"}

# Current active theme — default is DUSK
_current = DUSK


def get():
    """Return the currently active theme dict."""
    return _current


def set_theme(name):
    """Set the active theme by name. Resolves legacy dark/light names."""
    global _current
    canonical = {"dark": "night", "light": "day"}.get(name, name)
    _current = THEMES.get(canonical, DUSK)
    return _current


def next_theme_name(current_name):
    """Return the next theme name in the cycle."""
    canonical = {"dark": "night", "light": "day"}.get(current_name, current_name)
    try:
        idx = THEME_CYCLE.index(canonical)
    except ValueError:
        idx = 0
    return THEME_CYCLE[(idx + 1) % len(THEME_CYCLE)]


_theme_initialized = False


def apply_ttk_styles(style, theme=None):
    """Apply a theme dict to ttk.Style. Call after every theme change."""
    global _theme_initialized
    t = theme or _current
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
    style.configure('.', focuscolor=t["bg"], selectbackground=t["accent"],
                    selectforeground=t["accent_fg"])
    style.configure('TButton', focuscolor=t["btn_bg"])
    style.map('TButton',
              background=[('active', t["accent"]), ('pressed', t["accent_hover"]),
                          ('!disabled', t["btn_bg"])],
              foreground=[('active', t["accent_fg"]), ('!disabled', t["btn_fg"])])


