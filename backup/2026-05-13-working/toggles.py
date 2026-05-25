import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import shutil
from pathlib import Path
import shlex
from backend import BackendError
from ..utils import show_message

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Map: (display name, systemd service name)
DAEMONS = [
    ("Touchpad Daemon", "touchpad-led.service"),
    ("Kbd Brightness Daemon", "kbd-brightness.service"),
    ("Fan Curve Daemon", "fan-curve.service"),
]


class TogglesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self._daemon_labels = {}
        self._daemon_btns = {}
        self._service_poll_job = None
        self.create_widgets()
        self.after(1000, self._schedule_touchpad_refresh)
        self.after(1000, self._poll_services)

    def create_widgets(self):
        from ui import themes
        t = themes.get()
        ttk.Label(self, text="Hardware Toggles", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 12))

        # Fn Lock
        fn_frame = ttk.LabelFrame(self, text="Fn Lock", padding=8)
        fn_frame.pack(fill=tk.X, pady=(0, 12))

        self.fn_lock_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            fn_frame, text="Fn Lock enabled (Fn+Esc toggles Fn lock)",
            variable=self.fn_lock_var, command=self.apply_fn_lock,
            fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
            activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
            font=("Arial", 10, "bold"),
            bd=0, highlightthickness=0, relief="flat"
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(fn_frame, text="When enabled, function keys (F1-F12) act as media/special keys by default. Hold Fn for standard F-keys.",
                  foreground="gray", wraplength=550, font=("Arial", 9)).pack(anchor="w")

        # Touchpad Toggle (interactive)
        tp_frame = ttk.LabelFrame(self, text="Touchpad", padding=8)
        tp_frame.pack(fill=tk.X, pady=(0, 12))

        self.touchpad_var = tk.BooleanVar(value=True)
        self.touchpad_check = tk.Checkbutton(
            tp_frame, text="Touchpad enabled",
            variable=self.touchpad_var, command=self.apply_touchpad_toggle,
            fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
            activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
            font=("Arial", 10, "bold"),
            bd=0, highlightthickness=0, relief="flat"
        )
        self.touchpad_check.pack(anchor="w", pady=(0, 4))

        tp_status_row = ttk.Frame(tp_frame)
        tp_status_row.pack(anchor="w", pady=(0, 4))
        ttk.Label(tp_status_row, text="Status:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self.touchpad_status_label = ttk.Label(tp_status_row, text="Enabled", font=("Arial", 10, "bold"), foreground=t["status_green"])
        self.touchpad_status_label.pack(side=tk.LEFT)

        ttk.Label(tp_frame, text="Toggle the touchpad on/off. You can also use Fn+F7. The LED indicator shows the current state.",
                  foreground="gray", wraplength=550, font=("Arial", 9)).pack(anchor="w")

        # Super Key Lock
        super_frame = ttk.LabelFrame(self, text="Super/Windows Key", padding=8)
        super_frame.pack(fill=tk.X, pady=(0, 12))

        self.super_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            super_frame, text="Lock Super/Windows key (disable during gaming)",
            variable=self.super_key_var, command=self.apply_super_key,
            fg=t["radio_fg"], selectcolor=t["radio_bg"], bg=t["radio_bg"],
            activebackground=t["radio_bg"], activeforeground=t["radio_fg"],
            font=("Arial", 10, "bold"),
            bd=0, highlightthickness=0, relief="flat"
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(super_frame, text="Prevents accidental Alt+Tab or Super key presses during gameplay.",
                  foreground="gray", wraplength=550, font=("Arial", 9)).pack(anchor="w")

        # Microphone Mute Status
        mic_frame = ttk.LabelFrame(self, text="Microphone", padding=8)
        mic_frame.pack(fill=tk.X, pady=(0, 12))

        mic_status_row = ttk.Frame(mic_frame)
        mic_status_row.pack(anchor="w", pady=(0, 4))
        ttk.Label(mic_status_row, text="Status:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._mic_status_label = ttk.Label(mic_status_row, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._mic_status_label.pack(side=tk.LEFT)

        ttk.Label(mic_frame, text="Use Fn+F5 to toggle mic mute. The OS does not display the mic mute state natively.",
                  foreground="gray", wraplength=550, font=("Arial", 9)).pack(anchor="w")

        # ── System Services ──────────────────────────────────────────
        svc_frame = ttk.LabelFrame(self, text="System Services", padding=8)
        svc_frame.pack(fill=tk.X, pady=(12, 8))

        # Use grid for proper column alignment across all rows
        # Buttons go directly into svc_frame columns 2 and 3 for perfect alignment
        svc_frame.columnconfigure(0, weight=0, minsize=200)   # label column
        svc_frame.columnconfigure(1, weight=0, minsize=180)   # status column
        svc_frame.columnconfigure(2, weight=1)                # spacer - push buttons right
        svc_frame.columnconfigure(3, weight=0)                # button column left
        svc_frame.columnconfigure(4, weight=0)                # button column right

        row_idx = 0

        # Driver row
        ttk.Label(svc_frame, text="Driver (nuc_wmi):", font=("Arial", 10)).grid(row=row_idx, column=0, sticky="w", padx=(0, 8), pady=3)
        self._driver_status = ttk.Label(svc_frame, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._driver_status.grid(row=row_idx, column=1, sticky="w", padx=(0, 12), pady=3)
        # Cell left: Load + Unload packed in a frame
        drv_cell1 = ttk.Frame(svc_frame)
        drv_cell1.grid(row=row_idx, column=3, sticky="e", padx=(0, 2), pady=3)
        self._driver_load_btn = tk.Button(drv_cell1, text="Load", font=("Arial", 10),
                                          fg="white", bg=t["svc_btn_load"], relief="flat", padx=10, pady=3,
                                          command=self._load_driver)
        self._driver_load_btn.pack(side=tk.LEFT, padx=(0, 2))
        self._driver_unload_btn = tk.Button(drv_cell1, text="Unload", font=("Arial", 10),
                                            fg="white", bg=t["svc_btn_unload"], relief="flat", padx=10, pady=3,
                                            command=self._unload_driver)
        self._driver_unload_btn.pack(side=tk.LEFT, padx=(2, 0))
        # Cell right: Rebuild & Load
        self._driver_rebuild_btn = tk.Button(svc_frame, text="Rebuild & Load", font=("Arial", 10),
                                             fg="white", bg=t["svc_btn_rebuild"], relief="flat", padx=10, pady=3,
                                             command=self._rebuild_driver)
        self._driver_rebuild_btn.grid(row=row_idx, column=4, sticky="e", padx=(2, 0), pady=3)

        # Daemon rows
        for label, svc_name in DAEMONS:
            row_idx += 1
            ttk.Label(svc_frame, text=f"{label}:", font=("Arial", 10)).grid(row=row_idx, column=0, sticky="w", padx=(0, 8), pady=3)
            status_lbl = ttk.Label(svc_frame, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
            status_lbl.grid(row=row_idx, column=1, sticky="w", padx=(0, 12), pady=3)
            self._daemon_labels[svc_name] = status_lbl
            restart_btn = tk.Button(svc_frame, text="Restart", font=("Arial", 10),
                                    fg="white", bg=t["svc_btn_restart"], relief="flat", padx=10, pady=3,
                                    command=lambda s=svc_name: self._restart_daemon(s))
            restart_btn.grid(row=row_idx, column=3, sticky="e", padx=(0, 2), pady=3)
            stop_btn = tk.Button(svc_frame, text="Stop", font=("Arial", 10),
                                 fg="white", bg=t["svc_btn_stop"], relief="flat", padx=10, pady=3,
                                 command=lambda s=svc_name: self._stop_daemon(s))
            stop_btn.grid(row=row_idx, column=4, sticky="e", padx=(2, 0), pady=3)
            self._daemon_btns[svc_name] = (restart_btn, stop_btn)

        # Status label
        self.status_lbl = ttk.Label(self, text="", foreground="gray")
        self.status_lbl.pack(anchor="w", pady=(8, 0))

    def apply_touchpad_toggle(self):
        if not self.app.backend:
            return
        try:
            self.app.backend.set_touchpad_toggle_state(self.touchpad_var.get())
            state_text = "enabled" if self.touchpad_var.get() else "disabled"
            self.status_lbl.config(text=f"Touchpad {state_text}")
            self._refresh_touchpad_status()
        except BackendError as exc:
            show_message(self.app.root, "Error", str(exc))
            # Revert checkbox to actual state
            self._refresh_touchpad_status()

    def apply_fn_lock(self):
        if not self.app.backend:
            return
        try:
            self.app.backend.set_fn_lock_toggle_state(self.fn_lock_var.get())
            self.status_lbl.config(text=f"Fn lock {'enabled' if self.fn_lock_var.get() else 'disabled'}")
        except BackendError as exc:
            show_message(self.app.root, "Error", str(exc))

    def apply_super_key(self):
        if not self.app.backend:
            return
        try:
            self.app.backend.set_super_key_toggle_state(self.super_key_var.get())
            self.status_lbl.config(text=f"Super key {'locked' if self.super_key_var.get() else 'unlocked'}")
        except BackendError as exc:
            show_message(self.app.root, "Error", str(exc))

    def load_state(self, data):
        if not self.app.backend:
            return
        try:
            fn_state = self.app.backend.get_fn_lock_toggle_state()
            if fn_state is not None:
                self.fn_lock_var.set(fn_state)
        except Exception:
            pass
        self._refresh_touchpad_status()
        try:
            sk_state = self.app.backend.get_super_key_toggle_state()
            if sk_state is not None:
                self.super_key_var.set(sk_state)
            else:
                # Feature not available — disable the checkbox
                self.super_key_var.set(False)
                for child in self.winfo_children():
                    if isinstance(child, ttk.LabelFrame) and "Super" in str(child.cget("text")):
                        for w in child.winfo_children():
                            if isinstance(w, tk.Checkbutton):
                                w.config(state="disabled")
                        ttk.Label(child, text="(Not supported on this hardware)", foreground="orange", font=("Arial", 9)).pack(anchor="w")
                        break
        except Exception:
            pass
        # Start periodic touchpad status refresh
        self._schedule_touchpad_refresh()

    def _refresh_touchpad_status(self):
        """Update the touchpad status label and checkbox from the backend."""
        if not self.app.backend:
            return
        from ui import themes
        t = themes.get()
        try:
            tp_state = self.app.backend.get_touchpad_toggle_state()
            if tp_state is not None:
                self.touchpad_var.set(tp_state)
                if tp_state:
                    self.touchpad_status_label.config(text="Enabled", foreground=t["status_green"])
                else:
                    self.touchpad_status_label.config(text="Disabled", foreground=t["status_red"])
            else:
                self.touchpad_status_label.config(text="Unknown", foreground="gray")
        except Exception:
            self.touchpad_status_label.config(text="Unknown", foreground="gray")

    def _schedule_touchpad_refresh(self):
        """Refresh touchpad + mic mute status every 2 seconds."""
        self._refresh_touchpad_status()
        self._refresh_mic_status()
        self.after(1500, self._schedule_touchpad_refresh)

    def _refresh_mic_status(self):
        """Check mic mute state via wpctl or pactl."""
        import threading
        def _check():
            muted = None
            try:
                r = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
                                   capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    muted = "MUTED" in r.stdout.upper()
            except Exception:
                pass
            if muted is None:
                try:
                    r = subprocess.run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"],
                                       capture_output=True, text=True, timeout=3)
                    if r.returncode == 0:
                        muted = r.stdout.strip().lower().endswith("yes")
                except Exception:
                    pass
            self.after(0, lambda: self._update_mic_label(muted))
        threading.Thread(target=_check, daemon=True).start()

    def _update_mic_label(self, muted):
        from ui import themes
        t = themes.get()
        if muted is None:
            self._mic_status_label.config(text="Unknown", foreground="gray")
        elif muted:
            self._mic_status_label.config(text="🔇 Muted", foreground=t["status_red"])
        else:
            self._mic_status_label.config(text="🎤 Active", foreground=t["status_green"])

    # ── Service management ────────────────────────────────────────

    def _is_driver_loaded(self) -> bool:
        try:
            r = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=3)
            return "nuc_wmi" in r.stdout
        except Exception:
            return False

    def _is_daemon_running(self, svc_name: str) -> bool:
        try:
            r = subprocess.run(["systemctl", "is-active", svc_name],
                              capture_output=True, text=True, timeout=3)
            return r.stdout.strip() == "active"
        except Exception:
            return False

    def _refresh_services(self):
        from ui import themes
        t = themes.get()
        # Driver
        if self._is_driver_loaded():
            self._driver_status.config(text="Loaded ✓", foreground=t["status_green"])
        else:
            self._driver_status.config(text="Not Loaded ✗", foreground=t["status_red"])
        # Daemons
        for _, svc_name in DAEMONS:
            lbl = self._daemon_labels.get(svc_name)
            if lbl:
                if self._is_daemon_running(svc_name):
                    lbl.config(text="Running ✓", foreground=t["status_green"])
                else:
                    lbl.config(text="Stopped ✗", foreground=t["status_red"])

    def _poll_services(self):
        self._refresh_services()
        self._service_poll_job = self.after(5000, self._poll_services)

    def _set_service_buttons_state(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self._driver_load_btn.config(state=state)
        self._driver_unload_btn.config(state=state)
        self._driver_rebuild_btn.config(state=state)
        for restart_btn, stop_btn in self._daemon_btns.values():
            restart_btn.config(state=state)
            stop_btn.config(state=state)

    def _run_privileged(self, script: str, start_text: str, success_text: str, callback=None):
        """Run an elevated shell script in a worker thread and surface failures in the UI."""

        if not script.strip():
            self.status_lbl.config(text="No command to run")
            return

        self.status_lbl.config(text=start_text)
        self._set_service_buttons_state(False)

        def worker():
            try:
                cmd = ["pkexec", "bash", "-lc", script]
                if not shutil.which("pkexec"):
                    cmd = ["sudo", "bash", "-lc", script]
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.after(0, lambda: self._on_privileged_done(result, success_text, callback))
            except Exception as exc:
                self.after(0, lambda: self._on_privileged_error(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_privileged_done(self, result, success_text: str, callback=None):
        self._set_service_buttons_state(True)
        if result.returncode == 0:
            self.status_lbl.config(text=success_text)
            if callback:
                callback()
            return

        err = (result.stderr or result.stdout or "Unknown error").strip().splitlines()
        self.status_lbl.config(text=f"Failed: {err[-1] if err else 'Unknown error'}")
        if callback:
            callback()

    def _on_privileged_error(self, exc: Exception):
        self._set_service_buttons_state(True)
        self.status_lbl.config(text=f"Error: {exc}")

    def _load_driver(self):
        driver_dir = PROJECT_ROOT / "driver"
        ko = driver_dir / "nuc_wmi.ko"
        if not ko.exists():
            self.status_lbl.config(text="nuc_wmi.ko not found — use Rebuild & Load")
            return
        ko_q = shlex.quote(str(ko))
        script = f"rmmod nuc_wmi 2>/dev/null || true; insmod {ko_q}"
        self._run_privileged(script, "Loading driver...", "Driver loaded", callback=self._refresh_services)

    def _unload_driver(self):
        self._run_privileged("rmmod nuc_wmi 2>/dev/null || true", "Unloading driver...", "Driver unloaded", callback=self._refresh_services)

    def _rebuild_driver(self):
        driver_dir = PROJECT_ROOT / "driver"
        driver_dir_q = shlex.quote(str(driver_dir))
        script = f"""
set -e
cd {driver_dir_q}
make clean 2>/dev/null || true
make -j$(nproc)
test -f nuc_wmi.ko
rmmod nuc_wmi 2>/dev/null || true
insmod ./nuc_wmi.ko
"""
        self._run_privileged(script, "Rebuilding and loading driver...", "Driver rebuilt and loaded", callback=self._refresh_services)

    def _restart_daemon(self, svc_name: str):
        self._run_privileged(f"systemctl restart {svc_name}", f"Restarting {svc_name}...", f"Restarted {svc_name}", callback=self._refresh_services)

    def _stop_daemon(self, svc_name: str):
        self._run_privileged(f"systemctl stop {svc_name}", f"Stopping {svc_name}...", f"Stopped {svc_name}", callback=self._refresh_services)

    def apply_theme(self):
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()
        # Checkbuttons
        def _restyle(parent):
            for child in parent.winfo_children():
                wclass = child.winfo_class()
                if wclass == "Checkbutton":
                    child.configure(fg=t["radio_fg"], bg=t["radio_bg"],
                                    selectcolor=t["radio_bg"],
                                    activebackground=t["radio_bg"],
                                    activeforeground=t["radio_fg"])
                elif wclass == "Button" and not isinstance(child, ttk.Button):
                    # Service buttons — preserve their specific bg colors
                    pass
                if hasattr(child, 'winfo_children'):
                    _restyle(child)
        _restyle(self)
        # Service buttons
        self._driver_load_btn.configure(bg=t["svc_btn_load"])
        self._driver_unload_btn.configure(bg=t["svc_btn_unload"])
        self._driver_rebuild_btn.configure(bg=t["svc_btn_rebuild"])
        for restart_btn, stop_btn in self._daemon_btns.values():
            restart_btn.configure(bg=t["svc_btn_restart"])
            stop_btn.configure(bg=t["svc_btn_stop"])
        # Refresh status colors
        self._refresh_services()
        self._refresh_touchpad_status()

    def get_state(self):
        return {}

