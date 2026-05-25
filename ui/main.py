#!/usr/bin/env python3
import json
import time
import signal
import subprocess
import atexit
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk
import os
import sys

# Add project root to sys.path so packages can be imported
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ui import KeyboardTab, BatteryTab, LightbarTab, PowerTab, TogglesTab, show_message
from ui.tabs.face_unlock import FaceUnlockTab
from ui import themes

try:
    from backend import UniwillBackend, BackendError
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False
    print("Warning: backend not available, using UI-only mode")

# Config: always use the real user's home, not root's (app runs as root via pkexec)
def _get_real_user_home():
    """Get the actual logged-in user's home directory, even when running as root."""
    # Check SUDO_USER / PKEXEC_UID first
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        import pwd
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    pkexec_uid = os.environ.get("PKEXEC_UID")
    if pkexec_uid:
        import pwd
        try:
            return Path(pwd.getpwuid(int(pkexec_uid)).pw_dir)
        except (KeyError, ValueError):
            pass
    # Check /run/user/*/bus to find an active session
    import glob as _glob
    for bus in sorted(_glob.glob("/run/user/*/bus")):
        try:
            uid = int(bus.split("/")[3])
            if uid == 0:
                continue
            import pwd
            return Path(pwd.getpwuid(uid).pw_dir)
        except Exception:
            continue
    return Path.home()

_REAL_HOME = _get_real_user_home()
CONFIG_DIR = _REAL_HOME / ".config" / "nuc_linux_studio"
CONFIG_FILE = CONFIG_DIR / "settings.json"
OLD_CONFIG = _REAL_HOME / ".nuc_linux_colors.json"

class NUCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NUC Linux Studio")
        # Default geometry captured from a well-fitting session on the target display.
        # _restore_window_geometry() will override this if a saved geometry exists.
        self.root.geometry("3014x1822+270+56")
        self.root.minsize(1400, 900)
        self.root.configure(bg='#1a1625')  # default, overridden by theme below
        self.backend = None
        self._touchpad_daemon = None

        # Set window icon for taskbar
        try:
            _icon_path = Path(__file__).resolve().parent / "assets" / "inuc_icon.png"
            if not _icon_path.exists():
                _icon_path = Path("/usr/share/icons/hicolor/256x256/apps/nuc-linux-studio.png")
            if _icon_path.exists():
                _icon_img = tk.PhotoImage(file=str(_icon_path))
                self.root.iconphoto(True, _icon_img)
                self._app_icon = _icon_img  # prevent GC
        except Exception:
            pass

        # Restore saved window geometry
        self._restore_window_geometry()

        # Initialize theme from saved config — default is "dusk"
        self._current_theme_name = "dusk"
        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._current_theme_name = cfg.get("theme", "dusk")
        except Exception:
            pass
        self.theme = themes.set_theme(self._current_theme_name)
        self.root.configure(bg=self.theme["bg"])

        # Apply ttk styles from theme
        style = ttk.Style()
        themes.apply_ttk_styles(style, self.theme)

        self.root.option_add('*TCombobox*Listbox.background', self.theme["combo_list_bg"])
        self.root.option_add('*TCombobox*Listbox.foreground', self.theme["combo_list_fg"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.theme["combo_list_select"])

        if BACKEND_AVAILABLE:
            try:
                self.backend = UniwillBackend()
                print("Backend initialized:", self.backend.hwmon_path)
            except Exception as exc:
                print("Backend init failed:", exc)
                self.backend = None

        # Ensure EC regains fan control if app exits or crashes
        atexit.register(self._release_fans_on_exit)
        atexit.register(self._restore_gnome_kbd_on_exit)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.create_widgets()

        # No need to apply_theme on first load — widgets are created with correct colors.
        # apply_theme is only needed after theme toggle.

        # Profile switch button (KEY_PROG1 -> XF86Launch1) cycles power profiles
        self.root.bind('<XF86Launch1>', self._cycle_tab)
        self.root.bind('<Key-F13>', self._cycle_tab)  # fallback binding
        
        # Stretch tabs across the full notebook width on resize
        self._tab_resize_job = None
        self._last_tab_pad = None
        self.root.bind("<Configure>", self._on_resize)

        # Disable GNOME's keyboard brightness handling so our daemon controls Fn+F8
        # (already done pre-pkexec as the user; this is just for the tkinter fallback)
        self._gnome_kbd_keys_backup = {}

        # Also suppress at the tkinter level as a fallback
        for kbdev in ('XF86KbdBrightnessUp', 'XF86KbdBrightnessDown', 'XF86KbdLightOnOff'):
            self.root.bind(f'<{kbdev}>', self._suppress_kbd_brightness)

        self.is_loading = True
        self.load_config()
        self.is_loading = False
        self._resume_check_interval_ms = 30000
        self._last_resume_check = time.time()
        self.schedule_resume_check()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _suppress_kbd_brightness(self, event=None):
        """Suppress GNOME's keyboard brightness OSD — let our daemon handle Fn+F8."""
        return "break"

    def _on_resize(self, event):
        """Dynamically pad tabs so they stretch across the full notebook width."""
        if event.widget != self.root:
            return
        if self._tab_resize_job:
            self.root.after_cancel(self._tab_resize_job)
        self._tab_resize_job = self.root.after(50, self._adjust_tab_widths)

    def _adjust_tab_widths(self):
        """Calculate and apply tab padding to fill notebook width."""
        self._tab_resize_job = None
        try:
            nb_width = self.notebook.winfo_width()
            if nb_width < 100:
                return
            import tkinter.font as tkfont
            tab_font = tkfont.Font(family='Arial', size=10, weight='bold')
            tab_texts = [name for name, _ in self._tab_classes]
            total_text_width = sum(tab_font.measure(t) for t in tab_texts)
            num_tabs = len(tab_texts)
            # Account for borders, focus rings, inter-tab gaps (2px border each side + 2px gap)
            total_overhead = num_tabs * 6
            remaining = nb_width - total_text_width - total_overhead
            if remaining < 0:
                remaining = 0
            # Distribute remaining space as padding on each side of each tab
            pad_per_side = max(4, int(remaining / (num_tabs * 2)))
            # Only update if padding actually changed (prevents feedback loop)
            if pad_per_side != self._last_tab_pad:
                self._last_tab_pad = pad_per_side
                style = ttk.Style()
                style.configure('TNotebook.Tab', padding=[pad_per_side, 8])
        except Exception:
            pass

    def _restore_gnome_kbd_on_exit(self):
        """Restore GNOME's keyboard brightness media keys on exit."""
        user, uid = self._get_session_user()
        _restore_gnome_kbd_keys_as_user(user, uid)

    def _get_session_user(self):
        """Get the logged-in user and UID for running gsettings."""
        try:
            result = subprocess.run(["who"], capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                user = line.split()[0]
                id_result = subprocess.run(["id", "-u", user], capture_output=True, text=True, timeout=3)
                return user, id_result.stdout.strip()
        except Exception:
            pass
        return "adriansandru", "1000"


    def _cycle_tab(self, event=None):
        """Cycle through power profiles on profile switch button press."""
        if hasattr(self, 'power_tab'):
            self.power_tab.cycle_profile()

    def log(self, msg):
        pass

    def create_widgets(self):
        self._main_frame = main_frame = tk.Frame(self.root, bg=self.theme["bg"], padx=12, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.notebook = notebook = ttk.Notebook(main_frame)
        notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        # Lazy-loading: create placeholder frames, instantiate tabs on first select
        self._tab_classes = [
            ("Keyboard", KeyboardTab),
            ("Lightbar", LightbarTab),
            ("Battery & SSD", BatteryTab),
            ("Power", PowerTab),
            ("Face Unlock", FaceUnlockTab),
            ("Toggles", TogglesTab),
        ]
        self._tab_frames = []
        self._tab_instances = [None] * len(self._tab_classes)
        self._pending_config = None

        for name, _ in self._tab_classes:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=name, sticky="nsew")
            self._tab_frames.append(frame)

        # Eagerly create keyboard tab (index 0) since it's visible first
        self._materialize_tab(0)
        self.keyboard_tab = self._tab_instances[0]

        # Eagerly create lightbar tab (index 1) so saved effect is restored
        self._materialize_tab(1)

        # Eagerly create battery tab (index 2) so charge limit is applied at startup
        self._materialize_tab(2)

        # Eagerly create power tab (index 3) so profile polling starts immediately
        self._materialize_tab(3)

        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.create_footer(main_frame)

    def _materialize_tab(self, idx):
        """Instantiate a tab if not already created."""
        if self._tab_instances[idx] is not None:
            return
        name, cls = self._tab_classes[idx]
        frame = self._tab_frames[idx]
        tab = cls(frame, self)
        tab.pack(fill=tk.BOTH, expand=True)
        self._tab_instances[idx] = tab
        # Apply pending config if available
        if self._pending_config is not None:
            if idx == 3:  # Power tab takes restore_profile kwarg
                tab.load_state(self._pending_config, restore_profile=True)
            else:
                tab.load_state(self._pending_config)

    def _on_tab_changed(self, event=None):
        idx = self.notebook.index(self.notebook.select())
        self._materialize_tab(idx)
        # Re-apply treeview styles when visiting face unlock
        if idx == 4:
            style = ttk.Style()
            style.configure("Treeview",
                           background=self.theme["bg_secondary"], foreground=self.theme["fg"],
                           fieldbackground=self.theme["bg_secondary"])
            style.configure("Treeview.Heading",
                           background=self.theme["bg"], foreground=self.theme["accent"])
            style.map("Treeview",
                      background=[("selected", self.theme["accent_hover"])],
                      foreground=[("selected", self.theme["accent_fg"])])

    @property
    def lightbar_tab(self):
        if self._tab_instances[1] is None:
            self._materialize_tab(1)
        return self._tab_instances[1]

    @lightbar_tab.setter
    def lightbar_tab(self, val):
        self._tab_instances[1] = val

    @property
    def battery_tab(self):
        if self._tab_instances[2] is None:
            self._materialize_tab(2)
        return self._tab_instances[2]

    @battery_tab.setter
    def battery_tab(self, val):
        self._tab_instances[2] = val

    @property
    def power_tab(self):
        if self._tab_instances[3] is None:
            self._materialize_tab(3)
        return self._tab_instances[3]

    @power_tab.setter
    def power_tab(self, val):
        self._tab_instances[3] = val

    @property
    def toggles_tab(self):
        if self._tab_instances[5] is None:
            self._materialize_tab(5)
        return self._tab_instances[5]

    @toggles_tab.setter
    def toggles_tab(self, val):
        self._tab_instances[5] = val

    def create_footer(self, parent):
        self._footer = footer = tk.Frame(parent, bg=self.theme["footer_bg"])
        footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=1)
        footer.columnconfigure(2, weight=1)

        save_button = ttk.Button(footer, text="Export Config", command=self.save_config)
        save_button.grid(row=0, column=0, sticky="ew", padx=4)

        load_button = ttk.Button(footer, text="Import Config", command=self.load_config_file)
        load_button.grid(row=0, column=1, sticky="ew", padx=4)

        theme_icon = themes.THEME_ICONS.get(self._current_theme_name, "🌅")
        self._theme_btn = tk.Button(
            footer, text=f"{theme_icon} Theme",
            font=("Arial", 10), fg=self.theme["btn_fg"],
            bg=self.theme["btn_bg"], relief="flat", padx=12, pady=4,
            command=self._toggle_theme
        )
        self._theme_btn.grid(row=0, column=2, sticky="ew", padx=4)

    def _toggle_theme(self):
        """Cycle through night → dusk → day → night."""
        new_name = themes.next_theme_name(self._current_theme_name)
        self._current_theme_name = new_name
        self.theme = themes.set_theme(new_name)

        # Save preference immediately
        self.save_config()

        # Full UI restart is the only reliable way to apply theme in tkinter
        # Destroy everything and recreate
        self.root.configure(bg=self.theme["bg"])
        self._main_frame.configure(bg=self.theme["bg"])
        self._footer.configure(bg=self.theme["footer_bg"])
        style = ttk.Style()
        themes.apply_ttk_styles(style, self.theme)

        # Override the problematic default ttk "focus" colors
        style.map('TNotebook.Tab',
                  background=[('selected', self.theme["tab_selected_bg"]),
                              ('active', self.theme["tab_hover_bg"]),
                              ('!selected', self.theme["tab_bg"])],
                  foreground=[('selected', self.theme["tab_selected_fg"]),
                              ('active', self.theme["tab_hover_fg"]),
                              ('!selected', self.theme["tab_fg"])])
        # Kill default blue focus/select colors
        style.configure('TButton', focuscolor=self.theme["btn_bg"])
        style.map('TButton',
                  background=[('active', self.theme["accent"]), ('pressed', self.theme["accent_hover"])],
                  foreground=[('active', self.theme["accent_fg"])])

        self.root.option_add('*TCombobox*Listbox.background', self.theme["combo_list_bg"])
        self.root.option_add('*TCombobox*Listbox.foreground', self.theme["combo_list_fg"])
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.theme["combo_list_select"])

        # Treeview
        style.configure("Treeview",
                       background=self.theme["bg_secondary"], foreground=self.theme["fg"],
                       fieldbackground=self.theme["bg_secondary"])
        style.configure("Treeview.Heading",
                       background=self.theme["bg"], foreground=self.theme["accent"])
        style.map("Treeview",
                  background=[("selected", self.theme["accent_hover"])],
                  foreground=[("selected", self.theme["accent_fg"])])

        # Update face_unlock tree tag colors if tab exists
        try:
            face_tab = self._tab_instances[4] if len(self._tab_instances) > 4 else None
            if face_tab and hasattr(face_tab, '_faces_tree'):
                face_tab._faces_tree.tag_configure("face",
                    foreground=self.theme["accent"], font=("Segoe UI", 11, "bold"))
                face_tab._faces_tree.tag_configure("snapshot",
                    foreground="#555555" if self.theme["name"] == "day" else "#C0C0C0",
                    font=("Segoe UI", 11))
        except Exception:
            pass

        # Apply per-tab theme updates
        self._apply_theme_to_tabs()

        # Schedule a second pass to catch anything that was redrawn after us
        self.root.after(150, self._apply_theme_to_tabs)

        # Update theme button icon
        icon = themes.THEME_ICONS.get(new_name, "🌅")
        self._theme_btn.configure(
            text=f"{icon} Theme",
            fg=self.theme["btn_fg"], bg=self.theme["btn_bg"]
        )

        # Re-apply tab stretching
        self._last_tab_pad = None
        self._adjust_tab_widths()

        self.status_var.set(f"Theme switched to {self.theme['label']}")

    def _apply_theme_to_tabs(self):
        """Apply theme colors to all per-tab widgets via each tab's apply_theme() method."""
        for tab in self._tab_instances:
            if tab is not None and hasattr(tab, 'apply_theme'):
                try:
                    tab.apply_theme()
                except Exception as e:
                    import traceback; traceback.print_exc()
                    print(f"apply_theme failed for {tab.__class__.__name__}: {e}")


    def load_config(self, path=None, restore_power_profile=True):
        if path is None:
            if CONFIG_FILE.exists():
                path = CONFIG_FILE
            elif OLD_CONFIG.exists():
                path = OLD_CONFIG
            else:
                path = CONFIG_FILE

        self.is_loading = True
        try:
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f: data = json.load(f)
                    self._pending_config = data
                    # Load state for already-materialized tabs
                    if self._tab_instances[0]:  # Keyboard
                        self._tab_instances[0].load_state(data)
                    if self._tab_instances[1]:  # Lightbar
                        self._tab_instances[1].load_state(data)
                    if self._tab_instances[2]:  # Battery
                        self._tab_instances[2].load_state(data)
                    if self._tab_instances[3]:  # Power
                        self._tab_instances[3].load_state(data, restore_profile=restore_power_profile)
                    if self._tab_instances[4]:  # Face Unlock
                        self._tab_instances[4].load_state(data)
                    if self._tab_instances[5]:  # Toggles
                        self._tab_instances[5].load_state(data)
                    self.status_var.set(f"Loaded config from {path}")
                except Exception as exc:
                    show_message(self.root, "Error", f"Could not load config: {exc}")
            else:
                self._pending_config = {}
                if self._tab_instances[0]:
                    self._tab_instances[0].load_state({})
                if self._tab_instances[2]:
                    self._tab_instances[2].load_state({})
                if self._tab_instances[3]:
                    self._tab_instances[3].load_state({}, restore_profile=restore_power_profile)
        finally:
            self.is_loading = False

    def schedule_resume_check(self):
        self.root.after(self._resume_check_interval_ms, self._check_resume)

    def _check_resume(self):
        now = time.time()
        drift = now - self._last_resume_check
        self._last_resume_check = now
        if drift > (self._resume_check_interval_ms / 1000.0) * 2:
            self.status_var.set("System resume detected, reapplying saved settings (power profile preserved)")
            self.load_config(restore_power_profile=False)
        self.schedule_resume_check()

    def _release_fans_on_exit(self):
        """Release manual fan control so EC firmware takes over."""
        try:
            r = subprocess.run(["systemctl", "is-active", "fan-curve.service"], capture_output=True, text=True, timeout=2)
            if r.stdout.strip() == "active":
                return
        except Exception:
            pass
        if self.backend and self.backend._fans:
            try:
                self.backend._fans.disable_manual_control()
            except Exception:
                pass

    def _signal_handler(self, signum, frame):
        """Handle SIGTERM/SIGINT: release fans then exit."""
        self._release_fans_on_exit()
        self._restore_gnome_kbd_on_exit()
        sys.exit(0)

    def _on_close(self):
        self.save_config()
        self._save_window_geometry()
        self._release_fans_on_exit()
        self._restore_gnome_kbd_on_exit()
        self.root.destroy()



    def load_config_file(self):
        path = filedialog.askopenfilename(title="Load config", filetypes=[("JSON", "*.json"), ("All", "*")])
        if path: self.load_config(Path(path))

    def save_config(self):
        if getattr(self, 'is_loading', False):
            return
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {}
            data["theme"] = self._current_theme_name
            if self._tab_instances[0]: data.update(self._tab_instances[0].get_state())
            if self._tab_instances[1]: data.update(self._tab_instances[1].get_state())
            if self._tab_instances[2]: data.update(self._tab_instances[2].get_state())
            if self._tab_instances[3]: data.update(self._tab_instances[3].get_state())
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Signal daemon that config was updated (touch marker file)
            try:
                Path("/tmp/.nuc_studio_config_updated").write_text(str(time.time()))
            except Exception:
                pass
            self.status_var.set(f"Configuration saved to {CONFIG_FILE}")
        except Exception as exc: show_message(self.root, "Save failed", f"Could not save config: {exc}")


    def _restore_window_geometry(self):
        """Restore the window size and position from the saved configuration."""
        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                geom = config.get("window_geometry")
                if geom:
                    x, y, w, h = geom
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _save_window_geometry(self):
        """Save the current window size and position to the configuration file."""
        try:
            geom = self.root.geometry().split('+')
            width_height = geom[0]
            x = geom[1]
            y = geom[2]
            with CONFIG_FILE.open("r+", encoding="utf-8") as f:
                config = json.load(f)
                config["window_geometry"] = [int(coord) for coord in (x, y, *width_height.split('x'))]
                f.seek(0)
                json.dump(config, f, indent=2)
                f.truncate()
        except Exception:
            pass

_GNOME_KBD_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
_GNOME_KBD_KEYS = [
    "keyboard-brightness-up-static",
    "keyboard-brightness-down-static",
    "keyboard-brightness-toggle-static",
]

def _disable_gnome_kbd_keys():
    """Disable GNOME keyboard brightness keys (run as the logged-in user BEFORE pkexec)."""
    backup = {}
    for key in _GNOME_KBD_KEYS:
        try:
            result = subprocess.run(
                ["gsettings", "get", _GNOME_KBD_SCHEMA, key],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                backup[key] = result.stdout.strip()
            subprocess.run(
                ["gsettings", "set", _GNOME_KBD_SCHEMA, key, "[]"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
    # Save backup so the root process can restore later
    backup_path = Path("/tmp/.nuc_studio_gnome_kbd_backup")
    try:
        with open(backup_path, "w") as f:
            json.dump(backup, f)
        os.chmod(str(backup_path), 0o644)
    except Exception:
        pass

def _restore_gnome_kbd_keys_as_user(user=None, uid=None):
    """Restore GNOME keyboard brightness keys. Can run as root using runuser."""
    backup_path = Path("/tmp/.nuc_studio_gnome_kbd_backup")
    if not backup_path.exists():
        return
    try:
        with open(backup_path) as f:
            backup = json.load(f)
    except Exception:
        return
    for key, original in backup.items():
        try:
            if user and uid and str(os.getuid()) != uid:
                env = os.environ.copy()
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
                env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
                subprocess.run(
                    ["runuser", "-u", user, "--", "gsettings", "set", _GNOME_KBD_SCHEMA, key, original],
                    capture_output=True, env=env, timeout=5
                )
            else:
                subprocess.run(
                    ["gsettings", "set", _GNOME_KBD_SCHEMA, key, original],
                    capture_output=True, timeout=5
                )
        except Exception:
            pass
    try:
        backup_path.unlink()
    except Exception:
        pass


def main():
    import sys as _sys

    # Force dedicated GPU rendering (NVIDIA RTX 3070) and high-DPI scaling
    os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
    os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    os.environ.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
    os.environ.setdefault("GDK_SCALE", "1")
    os.environ.setdefault("TK_SCALING", "1.0")
    # Xrender acceleration for Tk canvas operations
    os.environ.setdefault("TK_USE_RENDER", "1")
    # Disable Tk's software AA (faster on GPU-composited desktops)
    os.environ.setdefault("GDK_RENDERING", "image")

    # Re-launch as root if not already
    if os.geteuid() != 0:
        # Disable GNOME keyboard brightness keys while running as the user
        # (gsettings must run in the user's dbus session, not root's)
        _disable_gnome_kbd_keys()

        # Save display env, then pkexec with env preserved via wrapper
        display = os.environ.get('DISPLAY', ':0')
        wayland = os.environ.get('WAYLAND_DISPLAY', '')
        xdg_rt = os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
        xauth = os.environ.get('XAUTHORITY', '')
        dbus = os.environ.get('DBUS_SESSION_BUS_ADDRESS', f'unix:path=/run/user/{os.getuid()}/bus')

        # Find Xwayland auth if not set
        if not xauth:
            import glob
            matches = glob.glob(f'/run/user/{os.getuid()}/.mutter-Xwaylandauth.*')
            if matches:
                xauth = matches[0]

        # Write env to a world-readable temp file
        env_path = f'/tmp/.nuc_studio_env_{os.getpid()}'
        with open(env_path, 'w') as f:
            f.write(f"DISPLAY={display}\n")
            f.write(f"WAYLAND_DISPLAY={wayland}\n")
            f.write(f"XDG_RUNTIME_DIR={xdg_rt}\n")
            f.write(f"XAUTHORITY={xauth}\n")
            f.write(f"DBUS_SESSION_BUS_ADDRESS={dbus}\n")
        os.chmod(env_path, 0o644)

        os.execvp("pkexec", ["pkexec", "/usr/local/bin/nuc-studio", "--env-file", env_path])

    # If launched with --env-file, load display env
    if '--env-file' in _sys.argv:
        idx = _sys.argv.index('--env-file')
        if idx + 1 < len(_sys.argv):
            env_path = _sys.argv[idx + 1]
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            k, v = line.split('=', 1)
                            if v:
                                os.environ[k] = v
                os.unlink(env_path)
            except Exception:
                pass
            # Remove from argv so tkinter doesn't see it
            _sys.argv = [a for i, a in enumerate(_sys.argv) if i != idx and i != idx + 1]

    root = tk.Tk(className='nuc-studio')
    app = NUCApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
