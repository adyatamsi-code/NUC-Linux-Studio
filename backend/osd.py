#!/usr/bin/env python3
"""
NUC Linux Studio — Custom OSD (On-Screen Display) v2

Shows a compact, styled popup on ALL monitors for NUC-specific hotkeys.
Uses one GTK3 window per monitor with proper Wayland-compatible positioning.

Supported events:
  kbd-brightness, touchpad, mic-mute, airplane, perf-mode, caps-lock

Socket: /tmp/nuc-osd.sock (Unix DGRAM)
Message format: {"type": "...", "value": ..., "label": "..."}
"""
import json
import os
import socket
import threading

# Force X11 backend so window positioning with move() works reliably on
# XWayland setups where the Wayland layer-shell protocol is not available.
# This must be set before any GLib/GTK import.
if "GDK_BACKEND" not in os.environ:
    os.environ["GDK_BACKEND"] = "x11"

SOCKET_PATH = "/tmp/nuc-osd.sock"

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import cairo

# Try to use gtk-layer-shell for proper per-monitor Wayland positioning.
# Falls back gracefully on compositors that don't support layer-shell (e.g. GNOME).
_LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    # Quick probe: only enable if the compositor actually advertises the protocol.
    # gtk-layer-shell itself will print warnings if unsupported; we suppress by
    # checking the global availability before calling init_for_window().
    _LAYER_SHELL = GtkLayerShell.is_supported()
except Exception:
    pass

# Visual config per event type
EVENT_VISUALS = {
    "kbd-brightness": {
        "icon": "🔆",
        "icon_off": "🔅",
        "color": "#4fc3f7",
        "color_off": "#666666",
        "has_bar": True,
    },
    "touchpad": {
        "icon": "🖱️",
        "icon_off": "🖱️✗",
        "color": "#66bb6a",
        "color_off": "#ef5350",
        "has_bar": False,
    },
    "mic-mute": {
        "icon": "🎤",
        "icon_off": "🎤🚫",
        "color": "#66bb6a",
        "color_off": "#ef5350",
        "has_bar": False,
    },
    "airplane": {
        "icon": "📡",
        "icon_off": "✈️",
        "color": "#66bb6a",
        "color_off": "#ffa726",
        "has_bar": False,
    },
    "perf-mode": {
        "icon": "⚡",
        "icon_off": "⚡",
        "color": "#ab47bc",
        "color_off": "#ab47bc",
        "has_bar": False,
    },
    "caps-lock": {
        "icon": "🔠",
        "icon_off": "🔡",
        "color": "#66bb6a",
        "color_off": "#ef5350",
        "has_bar": False,
    },
    "ac-power": {
        "icon": "🔌",
        "icon_off": "🔋",
        "color": "#66bb6a",
        "color_off": "#ffa726",
        "has_bar": False,
    },
    "fan-boost": {
        "icon": "🌀",       # Fan Boost ON  — spinning fast
        "icon_off": "💤",   # Fan Boost OFF — fans quiet/idle
        "color": "#ff7043",
        "color_off": "#90a4ae",
        "has_bar": False,
    },
    "volume": {
        "icon": "🔊",
        "icon_off": "🔇",
        "color": "#4fc3f7",
        "color_off": "#666666",
        "has_bar": True,
    },
    "screen-brightness": {
        "icon": "☀️",
        "icon_off": "🌑",
        "color": "#fff176",
        "color_off": "#666666",
        "has_bar": True,
    },
    "fn-lock": {
        "icon": "🔒",
        "icon_off": "🔓",
        "color": "#66bb6a",
        "color_off": "#aaaaaa",
        "has_bar": False,
    },
    "super-key-lock": {
        "icon": "⊞🔒",
        "icon_off": "⊞",
        "color": "#ef5350",
        "color_off": "#66bb6a",
        "has_bar": False,
    },
    "lightbar": {
        "icon": "💡",
        "icon_off": "💡",
        "color": "#ab47bc",
        "color_off": "#666666",
        "has_bar": False,
    },
}

OSD_CSS = """
#nuc-osd-win {
    background-color: transparent;
}
#nuc-osd-box {
    background-color: rgba(12, 12, 12, 0.72);
    border-radius: 24px;
    padding: 14px 24px;
}
#nuc-osd-icon {
    font-size: 32px;
    margin-bottom: 2px;
}
#nuc-osd-label {
    font-size: 10px;
    font-weight: 400;
    color: rgba(255, 255, 255, 0.75);
    letter-spacing: 0.3px;
}
"""

WIN_W, WIN_H = 180, 110
DISPLAY_MS = 1800
FADE_STEPS = 10
FADE_MS = 25


class OSDWindow:
    """A single OSD popup window for one monitor."""

    def __init__(self, monitor):
        self.monitor = monitor
        # Use POPUP so the window manager doesn't interfere with positioning.
        # TOPLEVEL with any type-hint gets re-placed by Mutter on XWayland.
        # Gtk.WindowType.POPUP bypasses the WM's placement policy entirely,
        # so window.move(x, y) is respected unconditionally on XWayland.
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        win.set_name("nuc-osd-win")
        win.set_decorated(False)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_keep_above(True)
        win.set_accept_focus(False)
        win.set_app_paintable(True)
        win.set_default_size(WIN_W, WIN_H)
        win.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)

        screen = win.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            win.set_visual(visual)

        if _LAYER_SHELL:
            GtkLayerShell.init_for_window(win)
            GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, False)
            GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.RIGHT, False)
            GtkLayerShell.set_margin(win, GtkLayerShell.Edge.BOTTOM, 60)
            GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
            if monitor:
                GtkLayerShell.set_monitor(win, monitor)

        win.connect("draw", self._on_draw)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_name("nuc-osd-box")
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        self.icon_label = Gtk.Label()
        self.icon_label.set_name("nuc-osd-icon")
        box.pack_start(self.icon_label, False, False, 0)

        self.text_label = Gtk.Label()
        self.text_label.set_name("nuc-osd-label")
        box.pack_start(self.text_label, False, False, 0)

        # Progress bar (custom drawn)
        self.bar_area = Gtk.DrawingArea()
        self.bar_area.set_size_request(130, 3)
        self.bar_area.connect("draw", self._draw_bar)
        box.pack_start(self.bar_area, False, False, 4)

        win.add(box)
        self.window = win
        self._bar_fraction = 0.0
        self._bar_color = "#4fc3f7"
        self._bar_visible = False
        # Accent color drawn as a subtle top-edge tint on the box background
        self._accent_color = "#4fc3f7"

    def _on_draw(self, widget, cr):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        alloc = widget.get_allocation()
        child = widget.get_child()
        if child:
            ca = child.get_allocation()
            cx = ca.x + ca.width / 2
            cy = ca.y + ca.height / 2

            # Radial shadow gradient — frosted-glass depth behind the box
            pat = cairo.RadialGradient(cx, cy + 8, 2, cx, cy + 8, max(ca.width, ca.height) * 0.55)
            pat.add_color_stop_rgba(0,   0, 0, 0, 0.40)
            pat.add_color_stop_rgba(0.6, 0, 0, 0, 0.15)
            pat.add_color_stop_rgba(1,   0, 0, 0, 0)
            cr.save()
            cr.translate(cx, cy + 8)
            cr.scale(ca.width * 0.58, ca.height * 0.42)
            cr.arc(0, 0, 1, 0, 6.2832)
            cr.set_source(pat)
            cr.fill()
            cr.restore()

            # Thin colored accent line at top edge of box
            r, g, b = self._parse_color(self._accent_color)
            x0 = ca.x + 20
            x1 = ca.x + ca.width - 20
            y0 = ca.y + 0.5
            cr.set_source_rgba(r, g, b, 0.65)
            cr.set_line_width(2.5)
            # Rounded ends for the accent line
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(x0, y0)
            cr.line_to(x1, y0)
            cr.stroke()
        return False

    def _draw_bar(self, widget, cr):
        if not self._bar_visible:
            return
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        r = h / 2  # full pill radius
        # Background track
        cr.set_source_rgba(1, 1, 1, 0.12)
        self._rounded_rect(cr, 0, 0, w, h, r)
        cr.fill()
        # Filled portion — pill shape
        rv, gv, bv = self._parse_color(self._bar_color)
        cr.set_source_rgba(rv, gv, bv, 0.85)
        fw = max(0, int(w * self._bar_fraction))
        if fw > 0:
            self._rounded_rect(cr, 0, 0, fw, h, r)
            cr.fill()

    @staticmethod
    def _rounded_rect(cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
        cr.arc(x + r, y + r, r, 3.14159, 4.71239)
        cr.close_path()

    @staticmethod
    def _parse_color(hex_color):
        h = hex_color.lstrip("#")
        return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255

    def update(self, icon, label, bar_fraction, bar_color, bar_visible, accent_color):
        self.icon_label.set_text(icon)
        self.text_label.set_text(label)
        self._bar_fraction = bar_fraction
        self._bar_color = bar_color
        self._bar_visible = bar_visible
        self._accent_color = accent_color
        self.bar_area.set_visible(bar_visible)
        self.bar_area.queue_draw()
        self.window.queue_draw()

    def position(self):
        if _LAYER_SHELL:
            return  # layer-shell handles placement per-monitor
        if self.monitor:
            geom = self.monitor.get_geometry()
        else:
            screen = self.window.get_screen()
            idx = screen.get_primary_monitor()
            geom = screen.get_monitor_geometry(idx if idx >= 0 else 0)
        x = geom.x + (geom.width - WIN_W) // 2
        y = geom.y + geom.height - WIN_H - 60
        self.window.move(x, y)

    def show(self):
        self.position()
        self.window.show_all()
        if not self._bar_visible:
            self.bar_area.hide()
        self.window.set_opacity(1.0)
        # XWayland/Mutter may re-place the window after the X11 map event.
        # Schedule multiple position() calls: immediately, after 50ms, 150ms.
        GLib.idle_add(self._reposition_idle)
        GLib.timeout_add(50, self._reposition_idle)
        GLib.timeout_add(150, self._reposition_idle)

    def _reposition_idle(self):
        self.position()
        return False  # don't repeat

    def hide(self):
        self.window.hide()

    def set_opacity(self, opacity):
        self.window.set_opacity(opacity)

    def destroy(self):
        self.window.destroy()


class NucOSD:
    def __init__(self):
        self._windows = []
        self._hide_timer = None
        self._fade_timer = None
        self._fade_step = 0
        self._setup_css()
        self._create_windows()
        self._connect_monitor_signals()

    def _setup_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(OSD_CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _create_windows(self):
        # Destroy any existing windows first (called on reconnect too)
        for w in self._windows:
            try:
                w.destroy()
            except Exception:
                pass
        self._windows = []
        display = Gdk.Display.get_default()
        n = display.get_n_monitors()
        for i in range(max(1, n)):
            mon = display.get_monitor(i) if i < n else None
            self._windows.append(OSDWindow(mon))

    def _connect_monitor_signals(self):
        """Rebuild windows when monitors are added or removed."""
        display = Gdk.Display.get_default()
        display.connect("monitor-added", self._on_monitor_changed)
        display.connect("monitor-removed", self._on_monitor_changed)

    def _on_monitor_changed(self, display, monitor):
        """A monitor was hot-plugged or unplugged — rebuild OSD windows."""
        print(f"Monitor topology changed — rebuilding OSD windows", flush=True)
        GLib.idle_add(self._rebuild_windows)

    def _rebuild_windows(self):
        # Hide all current windows before destroying them
        for w in self._windows:
            try:
                w.hide()
            except Exception:
                pass
        self._create_windows()
        return False

    def show(self, msg):
        event_type = msg.get("type", "")
        value = msg.get("value", 0)
        label = msg.get("label", "")

        vis = EVENT_VISUALS.get(event_type, EVENT_VISUALS["perf-mode"])
        is_on = bool(value) if not isinstance(value, (int, float)) else value > 0
        icon = vis["icon"] if is_on else vis["icon_off"]
        color = vis["color"] if is_on else vis["color_off"]
        has_bar = vis.get("has_bar", False)
        bar_frac = max(0.0, min(1.0, value / 100.0)) if has_bar and isinstance(value, (int, float)) else 0.0
        # Hide bar when at 0% (nothing to show, would just render empty track)
        if has_bar and bar_frac == 0.0:
            has_bar = False

        for w in self._windows:
            w.update(icon, label, bar_frac, color, has_bar, color)
            w.show()

        if self._hide_timer:
            GLib.source_remove(self._hide_timer)
        if self._fade_timer:
            GLib.source_remove(self._fade_timer)
            self._fade_timer = None
        self._hide_timer = GLib.timeout_add(DISPLAY_MS, self._start_fade)

    def _start_fade(self):
        self._hide_timer = None
        self._fade_step = 0
        self._fade_timer = GLib.timeout_add(FADE_MS, self._fade_tick)
        return False

    def _fade_tick(self):
        self._fade_step += 1
        opacity = 1.0 - (self._fade_step / FADE_STEPS)
        if opacity <= 0:
            for w in self._windows:
                w.hide()
            self._fade_timer = None
            return False
        for w in self._windows:
            w.set_opacity(opacity)
        return True


def _socket_listener(osd):
    # Retry binding the socket up to 10 times (5s) in case another instance is dying
    for attempt in range(10):
        try:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.bind(SOCKET_PATH)
            os.chmod(SOCKET_PATH, 0o666)
            print(f"NUC OSD listening on {SOCKET_PATH}", flush=True)
            break
        except Exception as e:
            print(f"OSD socket bind attempt {attempt+1} failed: {e}", flush=True)
            import time as _time
            _time.sleep(0.5)
    else:
        print("OSD: could not bind socket after 10 attempts, exiting", flush=True)
        return
    while True:
        try:
            data, _ = sock.recvfrom(4096)
            msg = json.loads(data.decode("utf-8"))
            GLib.idle_add(osd.show, msg)
        except Exception as e:
            print(f"OSD socket error: {e}", flush=True)


def send_osd(event_type: str, value, label: str):
    """Helper: send an OSD message (call from any process)."""
    msg = json.dumps({"type": event_type, "value": value, "label": label})
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.sendto(msg.encode("utf-8"), SOCKET_PATH)
        sock.close()
    except Exception:
        pass


def main():
    osd = NucOSD()
    t = threading.Thread(target=_socket_listener, args=(osd,), daemon=True)
    t.start()
    Gtk.main()


if __name__ == "__main__":
    main()
