import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import shutil
import threading
import os
import re
from pathlib import Path


def _get_real_user():
    """Get the real (non-root) user who launched the app."""
    for var in ("SUDO_USER", "PKEXEC_UID", "LOGNAME", "USER"):
        val = os.environ.get(var)
        if var == "PKEXEC_UID" and val:
            try:
                import pwd
                return pwd.getpwuid(int(val)).pw_name
            except Exception:
                continue
        if val and val != "root":
            return val
    # Fallback: first real user in /home
    try:
        homes = [d.name for d in Path("/home").iterdir() if d.is_dir() and d.name != "lost+found"]
        if homes:
            return homes[0]
    except Exception:
        pass
    return None


def _howdy_cmd(args, **kwargs):
    """Run a howdy command. App already runs as root via pkexec, so no extra elevation needed."""
    user = _get_real_user()
    user_flag = ["-U", user] if user else []
    return subprocess.run(["howdy"] + user_flag + args, **kwargs)


class FaceUnlockTab(ttk.Frame):
    # Config file for face grouping & column widths
    _FACE_CONFIG_DIR = Path("/home") 
    
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self._preview_running = False
        self._preview_process = None
        self._face_groups = {}
        self._folder_assignments = {}  # {snapshot_id: folder_name}
        self._folder_names = {}        # {folder_name: display_name}  
        self._auto_preview_started = False
        self._drag_data = {"item": None, "type": None}
        self.create_widgets()
        self.after(500, self._refresh_status)

    def create_widgets(self):
        from ui import themes
        t = themes.get()
        ttk.Label(self, text="Face Unlock (Howdy)", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 12))

        # ── Two-column layout ─────────────────────────────────────────
        main_pane = ttk.Frame(self)
        main_pane.pack(fill=tk.BOTH, expand=True)
        main_pane.columnconfigure(0, weight=5)
        main_pane.columnconfigure(1, weight=7)
        main_pane.rowconfigure(0, weight=1)

        left_col = ttk.Frame(main_pane)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        right_col = ttk.Frame(main_pane)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ══════════ LEFT COLUMN ══════════

        # ── Setup Section (Install Howdy / PAM) — at top so always visible ──
        self._setup_frame = ttk.LabelFrame(left_col, text="Setup", padding=8)
        self._setup_frame.pack(fill=tk.X, pady=(0, 8))

        _SETUP_BTN_W = 26  # uniform width for both setup buttons

        setup_row1 = ttk.Frame(self._setup_frame)
        setup_row1.pack(fill=tk.X, pady=(0, 6))
        self._install_btn = tk.Button(setup_row1, text="📦 Install Howdy",
                                      font=("Arial", 10, "bold"), fg="white", bg="#4CAF50",
                                      relief="flat", padx=16, pady=6, width=_SETUP_BTN_W,
                                      command=self._install_howdy)
        self._install_btn.pack(side=tk.LEFT, padx=(0, 12))
        self._install_lbl = ttk.Label(setup_row1,
                                      text="Howdy provides Windows Hello-style face authentication for Linux.",
                                      foreground="gray", font=("Arial", 9))
        self._install_lbl.pack(side=tk.LEFT)

        setup_row2 = ttk.Frame(self._setup_frame)
        setup_row2.pack(fill=tk.X, pady=(0, 4))
        self._pam_btn = tk.Button(setup_row2, text="🔗 Enable PAM Integration",
                                  font=("Arial", 10, "bold"), fg="white", bg="#FF9800",
                                  relief="flat", padx=16, pady=6, width=_SETUP_BTN_W,
                                  command=self._enable_pam)
        self._pam_btn.pack(side=tk.LEFT, padx=(0, 12))
        self._pam_setup_lbl = ttk.Label(setup_row2,
                                        text="Adds howdy to sudo, login, and polkit so face unlock works everywhere.",
                                        foreground="gray", font=("Arial", 9))
        self._pam_setup_lbl.pack(side=tk.LEFT)

        self._install_progress_frame = ttk.Frame(self._setup_frame)
        self._install_progress_bar = ttk.Progressbar(self._install_progress_frame, mode="indeterminate", length=300)
        self._install_progress_bar.pack(side=tk.LEFT, padx=(0, 8))
        self._install_progress_lbl = ttk.Label(self._install_progress_frame, text="", foreground="gray")
        self._install_progress_lbl.pack(side=tk.LEFT)

        # ── Status Section ────────────────────────────────────────────
        status_frame = ttk.LabelFrame(left_col, text="Status", padding=8)
        status_frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(status_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Howdy Installed:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._howdy_status = ttk.Label(row1, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._howdy_status.pack(side=tk.LEFT)

        row2 = ttk.Frame(status_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="IR Camera:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._camera_status = ttk.Label(row2, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._camera_status.pack(side=tk.LEFT)

        row3 = ttk.Frame(status_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="Camera Device:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._camera_device = ttk.Label(row3, text="—", font=("Arial", 10), foreground="gray")
        self._camera_device.pack(side=tk.LEFT)

        row4 = ttk.Frame(status_frame)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="Enrolled Faces:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._faces_status = ttk.Label(row4, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._faces_status.pack(side=tk.LEFT)

        row5 = ttk.Frame(status_frame)
        row5.pack(fill=tk.X, pady=2)
        ttk.Label(row5, text="PAM Integration:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._pam_status = ttk.Label(row5, text="Checking…", font=("Arial", 10, "bold"), foreground="gray")
        self._pam_status.pack(side=tk.LEFT)

        # ── Enrolled Faces (Grouped by Face) ──────────────────────────
        faces_frame = ttk.LabelFrame(left_col, text="Enrolled Biometric Data", padding=8)
        faces_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        tree_frame = ttk.Frame(faces_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._faces_tree = ttk.Treeview(tree_frame, columns=("id", "date", "label"), show="tree headings",
                                         height=5, selectmode="browse")
        self._faces_tree.heading("#0", text="Face", anchor="w")
        self._faces_tree.heading("id", text="ID", anchor="w")
        self._faces_tree.heading("date", text="Date", anchor="w")
        self._faces_tree.heading("label", text="Snapshot Label", anchor="w")
        self._faces_tree.column("#0", width=200, minwidth=150, stretch=True)
        self._faces_tree.column("id", width=40, minwidth=30, stretch=False)
        self._faces_tree.column("date", width=130, minwidth=100, stretch=False)
        self._faces_tree.column("label", width=160, minwidth=100, stretch=True)

        style = ttk.Style()
        style.configure("Treeview", background="#2d2640", foreground="#F0EDE5",
                         fieldbackground="#2d2640", font=("Liberation Sans Narrow", 9), rowheight=34)
        style.configure("Treeview.Heading", background="#1a1625", foreground="#E8B931",
                         font=("Liberation Sans Narrow", 12, "bold"), padding=(6, 4))
        style.map("Treeview", background=[("selected", "#D4A017")],
                  foreground=[("selected", "#1a1625")])

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._faces_tree.yview)
        self._faces_tree.configure(yscrollcommand=scrollbar.set)
        self._faces_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Drag and drop: snapshots into folders
        self._faces_tree.bind("<ButtonPress-1>", self._on_drag_start)
        self._faces_tree.bind("<B1-Motion>", self._on_drag_motion)
        self._faces_tree.bind("<ButtonRelease-1>", self._on_drag_drop)

        # Save column widths on resize
        self._faces_tree.bind("<ButtonRelease-1>", self._on_tree_click_or_resize, add="+")

        btn_row = ttk.Frame(faces_frame)
        btn_row.pack(fill=tk.X)

        self._enroll_btn = tk.Button(btn_row, text="➕ Add Face", font=("Arial", 10),
                                     fg="white", bg="#4CAF50", relief="flat", padx=12, pady=4,
                                     command=self._add_new_face)
        self._enroll_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._add_snapshot_btn = tk.Button(btn_row, text="📸 Add Snapshot", font=("Arial", 10),
                                           fg="white", bg="#2196F3", relief="flat", padx=12, pady=4,
                                           command=self._add_snapshot_to_face)
        self._add_snapshot_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._delete_btn = tk.Button(btn_row, text="🗑 Delete Selected", font=("Arial", 10),
                                     fg="white", bg="#F44336", relief="flat", padx=12, pady=4,
                                     command=self._delete_face)
        self._delete_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._rename_btn = tk.Button(btn_row, text="✏️ Rename", font=("Arial", 10),
                                      fg="white", bg="#795548", relief="flat", padx=12, pady=4,
                                      command=self._rename_selected)
        self._rename_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._refresh_btn = tk.Button(btn_row, text="🔄 Refresh", font=("Arial", 10),
                                       fg="white", bg="#607D8B", relief="flat", padx=12, pady=4,
                                       command=self._refresh_status)
        self._refresh_btn.pack(side=tk.LEFT)

        # ── Settings ─────────────────────────────────────────────────
        settings_frame = ttk.LabelFrame(left_col, text="Settings", padding=8)
        settings_frame.pack(fill=tk.X, pady=(0, 8))

        cert_row = ttk.Frame(settings_frame)
        cert_row.pack(fill=tk.X, pady=2)
        ttk.Label(cert_row, text="Certainty (lower = stricter):", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))
        self._certainty_var = tk.StringVar(value="3.5")
        self._certainty_entry = ttk.Entry(cert_row, textvariable=self._certainty_var, width=6)
        self._certainty_entry.pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(cert_row, text="Apply", font=("Arial", 9),
                  fg="white", bg="#4CAF50", relief="flat", padx=8,
                  command=self._apply_certainty).pack(side=tk.LEFT)

        ttk.Label(settings_frame,
                  text="Tip: Add multiple snapshots per face (glasses on/off,\ndifferent lighting) for better recognition.",
                  foreground="gray", font=("Arial", 9)).pack(anchor="w", pady=(6, 0))


        # ══════════ RIGHT COLUMN — Camera Preview ══════════

        preview_frame = ttk.LabelFrame(right_col, text="Camera Preview", padding=8)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        from ui import themes
        t = themes.get()
        self._cam_canvas = tk.Canvas(preview_frame, bg=t["camera_bg"], highlightthickness=0)
        self._cam_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self._cam_image_id = None
        self._cam_photo = None

        preview_btn_row = ttk.Frame(preview_frame)
        preview_btn_row.pack(fill=tk.X)

        self._preview_btn = tk.Button(preview_btn_row, text="📷 IR Camera", font=("Arial", 10),
                                       fg="white", bg="#9C27B0", relief="flat", padx=12, pady=4,
                                       command=self._toggle_preview)
        self._preview_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._rgb_preview_btn = tk.Button(preview_btn_row, text="📹 RGB Camera", font=("Arial", 10),
                                          fg="white", bg="#00796B", relief="flat", padx=12, pady=4,
                                          command=self._toggle_rgb_preview)
        self._rgb_preview_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._test_btn = tk.Button(preview_btn_row, text="🧪 Test Recognition", font=("Arial", 10),
                                    fg="white", bg="#FF9800", relief="flat", padx=12, pady=4,
                                    command=self._test_recognition)
        self._test_btn.pack(side=tk.LEFT)

        # Status bar
        self._status_lbl = ttk.Label(self, text="", foreground="gray")
        self._status_lbl.pack(anchor="w", pady=(4, 0))

    def apply_theme(self):
        """Explicitly restyle all widgets in this tab for the current theme."""
        from ui import themes
        t = themes.get()
        self._cam_canvas.configure(bg=t["camera_bg"])
        # Re-tag tree items
        self._faces_tree.tag_configure("face", foreground=t["accent"], font=("Segoe UI", 11, "bold"))
        self._faces_tree.tag_configure("snapshot",
            foreground="#555555" if t["name"] == "light" else "#C0C0C0",
            font=("Segoe UI", 11))

    # ══════════════════════════════════════════════════════════════════
    # Status refresh
    # ══════════════════════════════════════════════════════════════════

    def _refresh_status(self):
        threading.Thread(target=self._refresh_status_bg, daemon=True).start()

    def _refresh_status_bg(self):
        howdy_installed = self._check_howdy_installed()
        ir_camera = self._find_ir_camera()
        faces = self._get_enrolled_faces() if howdy_installed else []
        pam_services = self._get_pam_status() if howdy_installed else []
        certainty = self._get_certainty() if howdy_installed else "3.5"
        device_path = self._get_device_path() if howdy_installed else None

        self.after(0, lambda: self._update_ui(howdy_installed, ir_camera, faces, pam_services, certainty, device_path))

    def _update_ui(self, howdy_installed, ir_camera, faces, pam_services, certainty, device_path):
        from ui import themes
        t = themes.get()
        show_setup = False
        if howdy_installed:
            self._howdy_status.config(text="Installed ✓", foreground=t["status_green"])
            self._install_btn.config(state=tk.DISABLED, text="✓ Howdy Installed", bg="#555")
        else:
            self._howdy_status.config(text="Not Installed ✗", foreground=t["status_red"])
            self._install_btn.config(state=tk.NORMAL, text="📦 Install Howdy", bg=t["svc_btn_load"])
            show_setup = True

        if ir_camera:
            self._camera_status.config(text=f"Detected ✓ ({ir_camera['name']})", foreground=t["status_green"])
            self._camera_device.config(text=ir_camera['device'], foreground=t["fg"])
        else:
            self._camera_status.config(text="Not Detected ✗", foreground=t["status_red"])
            self._camera_device.config(text="—", foreground="gray")

        if pam_services:
            self._pam_status.config(text=f"Enabled ({', '.join(pam_services)})", foreground=t["status_green"])
            self._pam_btn.config(state=tk.DISABLED, text="✓ PAM Integrated", bg="#555")
        elif howdy_installed:
            self._pam_status.config(text="Not configured ⚠", foreground="#FF9800")
            self._pam_btn.config(state=tk.NORMAL, text="🔗 Enable PAM Integration", bg="#FF9800")
            show_setup = True
        else:
            self._pam_status.config(text="N/A", foreground="gray")
            self._pam_btn.config(state=tk.DISABLED, bg="#555")
            show_setup = True

        # Setup frame is always visible — buttons show disabled state when not needed

        self._populate_face_tree(faces)

        face_group_count = len(self._face_groups)
        total_snapshots = sum(len(snaps) for snaps in self._face_groups.values())
        if faces:
            self._faces_status.config(
                text=f"{face_group_count} face(s), {total_snapshots} snapshot(s)",
                foreground=t["status_green"])
        else:
            self._faces_status.config(
                text="No faces enrolled" if howdy_installed else "N/A",
                foreground=t["status_red"] if howdy_installed else "gray")

        self._certainty_var.set(certainty)


    def _populate_face_tree(self, faces):
        """Group face entries by folder assignment and populate the treeview."""
        self._faces_tree.delete(*self._faces_tree.get_children())
        self._face_groups = {}

        # Load saved folder assignments
        self._load_face_config()

        all_snaps = []
        for face in faces:
            parts = face.split(",", 2)
            if len(parts) == 3:
                face_id, date, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
            else:
                face_id, date, label = face.strip(), "", "unknown"
            all_snaps.append({"id": face_id, "date": date, "label": label})

        # Assign snapshots to folders
        for snap in all_snaps:
            sid = snap["id"]
            if sid in self._folder_assignments:
                folder = self._folder_assignments[sid]
            else:
                # Auto-assign based on label prefix convention
                folder = self._extract_face_name(snap["label"])
                self._folder_assignments[sid] = folder

            if folder not in self._face_groups:
                self._face_groups[folder] = []
            self._face_groups[folder].append(snap)

        for face_name, snapshots in self._face_groups.items():
            display_name = self._folder_names.get(face_name, face_name)
            parent_id = self._faces_tree.insert("", tk.END, text=f"📁 {display_name}",
                                                 values=("", "", f"{len(snapshots)} snapshot(s)"),
                                                 open=True, tags=("face",))
            for snap in snapshots:
                self._faces_tree.insert(parent_id, tk.END,
                                        text=f"    📸 {snap['label']}",
                                        values=(snap["id"], snap["date"], snap["label"]),
                                        tags=("snapshot",))

        from ui import themes
        t = themes.get()
        self._faces_tree.tag_configure("face", foreground=t["accent"], font=("Segoe UI", 11, "bold"))
        self._faces_tree.tag_configure("snapshot",
            foreground="#555555" if t["name"] == "light" else "#C0C0C0",
            font=("Segoe UI", 11))

        # Save assignments
        self._save_face_config()

    def _extract_face_name(self, label):
        """Extract a face name from a label for auto-grouping.
        Convention: 'adrian-glasses-on' groups under 'adrian'."""
        label = label.strip()
        if not label:
            return "default"
        parts = label.split("-", 1)
        if len(parts) > 1 and len(parts[0]) >= 2:
            return parts[0]
        return label

    def _get_face_config_path(self):
        user = _get_real_user() or "root"
        return Path(f"/home/{user}/.config/nuc_linux_studio/face_groups.json")

    def _load_face_config(self):
        path = self._get_face_config_path()
        if path.exists():
            try:
                import json
                data = json.loads(path.read_text())
                self._folder_assignments = data.get("folder_assignments", {})
                self._folder_names = data.get("folder_names", {})
                # Load saved column widths
                col_widths = data.get("column_widths", {})
                if col_widths:
                    for col_id, width in col_widths.items():
                        try:
                            self._faces_tree.column(col_id, width=int(width))
                        except Exception:
                            pass
            except Exception:
                pass

    def _save_face_config(self):
        path = self._get_face_config_path()
        try:
            import json
            # Save current column widths
            col_widths = {}
            for col_id in ("#0", "id", "date", "label"):
                try:
                    col_widths[col_id] = self._faces_tree.column(col_id, "width")
                except Exception:
                    pass
            data = {
                "folder_assignments": self._folder_assignments,
                "folder_names": self._folder_names,
                "column_widths": col_widths,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    # ── Drag and drop ──────────────────────────────────────────────

    def _on_drag_start(self, event):
        item = self._faces_tree.identify_row(event.y)
        if not item:
            return
        tags = self._faces_tree.item(item, "tags")
        if "snapshot" in tags:
            self._drag_data["item"] = item
            self._drag_data["type"] = "snapshot"
            self._faces_tree.selection_set(item)

    def _on_drag_motion(self, event):
        if not self._drag_data["item"]:
            return
        target = self._faces_tree.identify_row(event.y)
        if target:
            # Highlight potential drop target
            self._faces_tree.selection_set(target)

    def _on_drag_drop(self, event):
        if not self._drag_data["item"] or self._drag_data["type"] != "snapshot":
            self._drag_data = {"item": None, "type": None}
            return

        source_item = self._drag_data["item"]
        target_item = self._faces_tree.identify_row(event.y)
        self._drag_data = {"item": None, "type": None}

        if not target_item or target_item == source_item:
            return

        # Determine target folder
        target_tags = self._faces_tree.item(target_item, "tags")
        if "face" in target_tags:
            target_folder_item = target_item
        elif "snapshot" in target_tags:
            target_folder_item = self._faces_tree.parent(target_item)
            if not target_folder_item:
                return
        else:
            return

        # Get target folder name
        target_text = self._faces_tree.item(target_folder_item, "text").replace("📁 ", "").strip()
        # Find the internal folder key
        target_folder_key = None
        for key, display in self._folder_names.items():
            if display == target_text:
                target_folder_key = key
                break
        if target_folder_key is None:
            # Display name IS the key
            for key in self._face_groups:
                display = self._folder_names.get(key, key)
                if display == target_text:
                    target_folder_key = key
                    break
        if target_folder_key is None:
            target_folder_key = target_text

        # Move snapshot
        vals = self._faces_tree.item(source_item, "values")
        snap_id = str(vals[0]) if vals else None
        if not snap_id:
            return

        self._folder_assignments[snap_id] = target_folder_key
        self._save_face_config()
        self._status_lbl.config(text=f"✓ Moved snapshot {snap_id} to folder '{target_text}'")
        self._refresh_status()

    # ══════════════════════════════════════════════════════════════════
    # Checks
    # ══════════════════════════════════════════════════════════════════

    def _check_howdy_installed(self):
        try:
            r = subprocess.run(["which", "howdy"], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def _find_ir_camera(self):
        base = Path("/sys/class/video4linux")
        if not base.exists():
            return None
        for dev_dir in sorted(base.iterdir()):
            name_path = dev_dir / "name"
            if name_path.exists():
                try:
                    name = name_path.read_text().strip()
                    if "IR" in name.upper():
                        return {"device": f"/dev/{dev_dir.name}", "name": name}
                except Exception:
                    pass
        return None

    def _get_enrolled_faces(self):
        try:
            r = _howdy_cmd(["list", "--plain"], capture_output=True, text=True, timeout=10)
            lines = r.stdout.strip().splitlines()
            faces = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or "," in line):
                    faces.append(line)
            return faces
        except Exception:
            return []

    def _get_pam_status(self):
        services = []
        pam_dir = Path("/etc/pam.d")
        for service in ["sudo", "gdm-password", "login", "polkit-1"]:
            pam_file = pam_dir / service
            if pam_file.exists():
                try:
                    content = pam_file.read_text()
                    if "howdy" in content and not all(
                        line.strip().startswith("#") for line in content.splitlines() if "howdy" in line
                    ):
                        services.append(service)
                except Exception:
                    pass
        return services

    def _get_certainty(self):
        try:
            config = Path("/etc/howdy/config.ini").read_text()
            for line in config.splitlines():
                if line.strip().startswith("certainty"):
                    return line.split("=")[1].strip()
        except Exception:
            pass
        return "3.5"

    def _get_device_path(self):
        try:
            config = Path("/etc/howdy/config.ini").read_text()
            for line in config.splitlines():
                if line.strip().startswith("device_path"):
                    return line.split("=")[1].strip()
        except Exception:
            pass
        return None

    # ══════════════════════════════════════════════════════════════════
    # Face enrollment — grouped
    # ══════════════════════════════════════════════════════════════════

    def _add_new_face(self):
        """Enroll a new face (creates a new group)."""
        self._enroll_face_dialog(
            title="Add New Face",
            prompt="Enter a name for this face:",
            hint="(e.g. 'adrian', 'guest')",
            label_template="{name}"
        )

    def _add_snapshot_to_face(self):
        """Add a snapshot to the currently selected face group."""
        sel = self._faces_tree.selection()
        if not sel:
            self._status_lbl.config(text="Select a face group first")
            return

        item = sel[0]
        parent = self._faces_tree.parent(item)
        face_item = parent if parent else item

        face_text = self._faces_tree.item(face_item, "text")
        face_name = face_text.replace("📁 ", "").strip()

        self._enroll_face_dialog(
            title=f"Add Snapshot to '{face_name}'",
            prompt=f"Enter a qualifier for this snapshot of '{face_name}':",
            hint="(e.g. 'glasses-on', 'dim-light', 'hat')",
            label_template=f"{face_name}-{{qualifier}}"
        )

    def _enroll_face_dialog(self, title, prompt, hint, label_template):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg="#2d2640")
        dlg.geometry("560x220")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        tk.Label(dlg, text=prompt, bg="#2d2640", fg="white",
                 font=("Arial", 11)).pack(pady=(16, 4), padx=16, anchor="w")
        tk.Label(dlg, text=hint, bg="#2d2640", fg="gray",
                 font=("Arial", 9)).pack(padx=16, anchor="w")

        entry = tk.Entry(dlg, font=("Arial", 12), bg="#0d1117", fg="white",
                         insertbackground="white", relief="flat", bd=2)
        entry.pack(fill=tk.X, padx=16, pady=8)
        entry.focus_set()

        result = [None]

        def on_ok(event=None):
            val = entry.get().strip()
            if val:
                result[0] = val
                dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg="#2d2640")
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Button(btn_frame, text="Enroll", font=("Arial", 10), fg="white", bg="#4CAF50",
                  relief="flat", padx=16, pady=4, command=on_ok).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10), fg="white", bg="#555",
                  relief="flat", padx=16, pady=4, command=on_cancel).pack(side=tk.LEFT)
        entry.bind("<Return>", on_ok)

        dlg.wait_window()
        val = result[0]
        if not val:
            return

        if "{qualifier}" in label_template:
            label = label_template.replace("{qualifier}", val)
        elif "{name}" in label_template:
            label = label_template.replace("{name}", val)
        else:
            label = val

        self._status_lbl.config(text="Enrolling face — look at the IR camera…")
        # Stop preview to free the camera for howdy
        if self._preview_running:
            self._stop_preview()
        threading.Thread(target=self._run_enroll, args=(label,), daemon=True).start()

    def _run_enroll(self, label):
        try:
            r = _howdy_cmd(["-y", "add", label],
                           capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                self.after(0, lambda: self._status_lbl.config(text=f"✓ Face '{label}' enrolled successfully!"))
            else:
                err = r.stderr.strip() or r.stdout.strip()
                self.after(0, lambda: self._status_lbl.config(text=f"✗ Enrollment failed: {err[:80]}"))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._status_lbl.config(text="✗ Enrollment timed out — try again"))
        except Exception as e:
            self.after(0, lambda: self._status_lbl.config(text=f"✗ Error: {e}"))
        self.after(1000, self._refresh_status)

    def _delete_face(self):
        sel = self._faces_tree.selection()
        if not sel:
            self._status_lbl.config(text="Select a face entry to delete")
            return

        item = sel[0]
        tags = self._faces_tree.item(item, "tags")

        if "face" in tags:
            face_text = self._faces_tree.item(item, "text").replace("📁 ", "").strip()
            children = self._faces_tree.get_children(item)
            ids = []
            for child in children:
                vals = self._faces_tree.item(child, "values")
                if vals and vals[0]:
                    ids.append(str(vals[0]))
            if not ids:
                self._status_lbl.config(text="No snapshots to delete")
                return
            if not messagebox.askyesno("Delete Face",
                                       f"Delete ALL {len(ids)} snapshot(s) for '{face_text}'?"):
                return
            self._status_lbl.config(text=f"Deleting all snapshots for '{face_text}'…")
            threading.Thread(target=self._run_delete_multiple, args=(ids,), daemon=True).start()
        else:
            vals = self._faces_tree.item(item, "values")
            face_id = str(vals[0]) if vals else None
            label = str(vals[2]) if vals and len(vals) > 2 else ""
            if not face_id or not face_id.isdigit():
                self._status_lbl.config(text="Could not parse face ID")
                return
            if not messagebox.askyesno("Delete Snapshot",
                                       f"Delete snapshot ID {face_id} ({label})?"):
                return
            self._status_lbl.config(text=f"Deleting snapshot ID {face_id}…")
            threading.Thread(target=self._run_delete, args=(face_id,), daemon=True).start()

    def _run_delete(self, face_id):
        try:
            r = _howdy_cmd(["-y", "remove", face_id],
                          capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                self.after(0, lambda: self._status_lbl.config(text=f"✓ Snapshot ID {face_id} deleted"))
            else:
                err = r.stderr.strip() or r.stdout.strip()
                self.after(0, lambda: self._status_lbl.config(text=f"✗ Delete failed: {err[:80]}"))
        except Exception as e:
            self.after(0, lambda: self._status_lbl.config(text=f"✗ Error: {e}"))
        self.after(1000, self._refresh_status)

    def _run_delete_multiple(self, ids):
        failed = []
        for face_id in ids:
            try:
                r = _howdy_cmd(["-y", "remove", face_id],
                              capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    failed.append(face_id)
            except Exception:
                failed.append(face_id)
        if failed:
            self.after(0, lambda: self._status_lbl.config(
                text=f"✗ Failed to delete IDs: {', '.join(failed)}"))
        else:
            self.after(0, lambda: self._status_lbl.config(
                text=f"✓ Deleted {len(ids)} snapshot(s)"))
        self.after(1000, self._refresh_status)

    def _rename_selected(self):
        """Rename the selected snapshot label or folder display name independently."""
        sel = self._faces_tree.selection()
        if not sel:
            self._status_lbl.config(text="Select a snapshot or face group to rename")
            return

        item = sel[0]
        tags = self._faces_tree.item(item, "tags")

        if "face" in tags:
            # Rename the folder display name (independent from snapshot labels)
            old_display = self._faces_tree.item(item, "text").replace("📁 ", "").strip()
            # Find internal folder key
            folder_key = None
            for key in self._face_groups:
                display = self._folder_names.get(key, key)
                if display == old_display:
                    folder_key = key
                    break
            if not folder_key:
                folder_key = old_display

            self._rename_folder_dialog(folder_key, old_display)
        else:
            # Rename individual snapshot label in howdy's models file
            vals = self._faces_tree.item(item, "values")
            face_id = str(vals[0]) if vals else None
            old_label = str(vals[2]) if vals and len(vals) > 2 else ""
            if not face_id or not face_id.isdigit():
                self._status_lbl.config(text="Could not parse face ID")
                return
            self._rename_snapshot_dialog(face_id, old_label)

    def _rename_folder_dialog(self, folder_key, old_display):
        """Rename a folder's display name (does NOT touch howdy snapshot labels)."""
        dlg = tk.Toplevel(self)
        dlg.title(f"Rename Folder '{old_display}'")
        dlg.configure(bg="#2d2640")
        dlg.geometry("500x180")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        tk.Label(dlg, text=f"Enter new display name for folder '{old_display}':",
                 bg="#2d2640", fg="white", font=("Arial", 11)).pack(pady=(16, 4), padx=16, anchor="w")

        entry = tk.Entry(dlg, font=("Arial", 12), bg="#0d1117", fg="white",
                         insertbackground="white", relief="flat", bd=2)
        entry.pack(fill=tk.X, padx=16, pady=8)
        entry.insert(0, old_display)
        entry.select_range(0, tk.END)
        entry.focus_set()

        result = [None]
        def on_ok(event=None):
            val = entry.get().strip()
            if val:
                result[0] = val
                dlg.destroy()
        def on_cancel():
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg="#2d2640")
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Button(btn_frame, text="Rename", font=("Arial", 10), fg="white", bg="#795548",
                  relief="flat", padx=16, pady=4, command=on_ok).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10), fg="white", bg="#555",
                  relief="flat", padx=16, pady=4, command=on_cancel).pack(side=tk.LEFT)
        entry.bind("<Return>", on_ok)
        dlg.wait_window()

        new_name = result[0]
        if not new_name or new_name == old_display:
            return

        self._folder_names[folder_key] = new_name
        self._save_face_config()
        self._status_lbl.config(text=f"✓ Folder renamed to '{new_name}'")
        self._refresh_status()

    def _rename_snapshot_dialog(self, face_id, old_label):
        """Rename an individual snapshot's label in howdy's models file."""
        dlg = tk.Toplevel(self)
        dlg.title("Rename Snapshot")
        dlg.configure(bg="#2d2640")
        dlg.geometry("500x180")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        tk.Label(dlg, text=f"Enter new label for snapshot '{old_label}':",
                 bg="#2d2640", fg="white", font=("Arial", 11)).pack(pady=(16, 4), padx=16, anchor="w")

        entry = tk.Entry(dlg, font=("Arial", 12), bg="#0d1117", fg="white",
                         insertbackground="white", relief="flat", bd=2)
        entry.pack(fill=tk.X, padx=16, pady=8)
        entry.insert(0, old_label)
        entry.select_range(0, tk.END)
        entry.focus_set()

        result = [None]
        def on_ok(event=None):
            val = entry.get().strip()
            if val:
                result[0] = val
                dlg.destroy()
        def on_cancel():
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg="#2d2640")
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Button(btn_frame, text="Rename", font=("Arial", 10), fg="white", bg="#795548",
                  relief="flat", padx=16, pady=4, command=on_ok).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10), fg="white", bg="#555",
                  relief="flat", padx=16, pady=4, command=on_cancel).pack(side=tk.LEFT)
        entry.bind("<Return>", on_ok)
        dlg.wait_window()

        new_label = result[0]
        if not new_label or new_label == old_label:
            return

        self._status_lbl.config(text="Renaming…")
        threading.Thread(target=self._run_rename_snapshot, args=(face_id, new_label), daemon=True).start()

    def _run_rename_snapshot(self, face_id, new_label):
        """Rename a single snapshot in howdy's models.dat."""
        user = _get_real_user() or "root"
        models_file = None
        for base in ("/etc/howdy/models", "/lib64/security/howdy/models",
                     "/usr/lib64/security/howdy/models", "/lib/security/howdy/models",
                     "/usr/lib/security/howdy/models"):
            p = Path(base) / f"{user}.dat"
            if p.exists():
                models_file = p
                break

        if not models_file:
            self.after(0, lambda: self._status_lbl.config(text=f"✗ Models file not found for user '{user}'"))
            return

        try:
            import json
            data = json.loads(models_file.read_text())
            changed = False
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("id", "")) == face_id:
                    entry["label"] = new_label
                    changed = True
                    break
            if changed:
                models_file.write_text(json.dumps(data))
                self.after(0, lambda: self._status_lbl.config(text=f"✓ Snapshot renamed to '{new_label}'"))
            else:
                self.after(0, lambda: self._status_lbl.config(text="✗ Snapshot not found in models file"))
        except Exception as e:
            self.after(0, lambda: self._status_lbl.config(text=f"✗ Rename error: {e}"))
        self.after(1000, self._refresh_status)

    def _on_tree_click_or_resize(self, event):
        """Save column widths when headers are resized."""
        self.after(500, self._save_face_config)

    # ══════════════════════════════════════════════════════════════════
    # Camera preview
    # ══════════════════════════════════════════════════════════════════

    def _toggle_preview(self):
        if self._preview_running:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self):
        ir_cam = self._find_ir_camera()
        if not ir_cam:
            self._status_lbl.config(text="✗ IR camera not found")
            return
        device = ir_cam['device']
        try:
            import cv2
            from PIL import Image, ImageTk
        except ImportError as e:
            self._status_lbl.config(text=f"✗ Missing dependency: {e}")
            return

        dev_index = int(device.replace("/dev/video", ""))
        self._cap = cv2.VideoCapture(dev_index, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            self._status_lbl.config(text=f"✗ Could not open {device}")
            return

        self._preview_running = True
        self._preview_btn.config(text="⏹ Stop IR", bg="#F44336")
        self._status_lbl.config(text=f"Preview running from {device}")
        self._update_preview_frame()

    def _update_preview_frame(self):
        if not self._preview_running or not hasattr(self, '_cap') or not self._cap:
            return
        try:
            import cv2
            from PIL import Image, ImageTk

            ret, frame = self._cap.read()
            if ret:
                if len(frame.shape) == 2:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
                else:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame_rgb.shape[:2]
                canvas_w = self._cam_canvas.winfo_width() or 320
                canvas_h = self._cam_canvas.winfo_height() or 180
                scale = min(canvas_w / w, canvas_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
                img = Image.fromarray(frame_resized)
                self._cam_photo = ImageTk.PhotoImage(image=img)
                if self._cam_image_id:
                    self._cam_canvas.itemconfig(self._cam_image_id, image=self._cam_photo)
                else:
                    self._cam_image_id = self._cam_canvas.create_image(
                        canvas_w // 2, canvas_h // 2, image=self._cam_photo)
        except Exception:
            pass
        if self._preview_running:
            self.after(66, self._update_preview_frame)

    def _stop_preview(self):
        self._preview_running = False
        if hasattr(self, '_cap') and self._cap:
            self._cap.release()
            self._cap = None
        self._preview_btn.config(text="📷 IR Camera", bg="#9C27B0")
        self._rgb_preview_btn.config(text="📹 RGB Camera", bg="#00796B")
        self._status_lbl.config(text="Preview stopped")
        if self._cam_image_id:
            self._cam_canvas.delete(self._cam_image_id)
            self._cam_image_id = None
        self._cam_photo = None

    def _find_rgb_camera(self):
        """Find the regular (non-IR) webcam."""
        base = Path("/sys/class/video4linux")
        if not base.exists():
            return None
        for dev_dir in sorted(base.iterdir()):
            name_path = dev_dir / "name"
            if name_path.exists():
                try:
                    name = name_path.read_text().strip()
                    if "IR" not in name.upper() and "Webcam" in name:
                        return {"device": f"/dev/{dev_dir.name}", "name": name}
                except Exception:
                    pass
        return None

    def _toggle_rgb_preview(self):
        if self._preview_running:
            self._stop_preview()
        else:
            self._start_rgb_preview()

    def _start_rgb_preview(self):
        rgb_cam = self._find_rgb_camera()
        if not rgb_cam:
            self._status_lbl.config(text="✗ RGB camera not found")
            return
        device = rgb_cam['device']
        try:
            import cv2
            from PIL import Image, ImageTk
        except ImportError as e:
            self._status_lbl.config(text=f"✗ Missing dependency: {e}")
            return

        dev_index = int(device.replace("/dev/video", ""))
        self._cap = cv2.VideoCapture(dev_index, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            self._status_lbl.config(text=f"✗ Could not open {device}")
            return

        self._preview_running = True
        self._rgb_preview_btn.config(text="⏹ Stop RGB", bg="#F44336")
        self._status_lbl.config(text=f"RGB preview running from {device}")
        self._update_preview_frame()

    # ══════════════════════════════════════════════════════════════════
    # Test recognition
    # ══════════════════════════════════════════════════════════════════

    def _test_recognition(self):
        if hasattr(self, '_test_process') and self._test_process and self._test_process.poll() is None:
            self._test_process.terminate()
            return
        self._status_lbl.config(text="Testing recognition — look at the camera…")
        threading.Thread(target=self._run_test, daemon=True).start()

    def _run_test(self):
        try:
            env = os.environ.copy()
            self._test_process = subprocess.Popen(
                ["howdy", "-U", _get_real_user() or "root", "test"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env
            )
            self.after(0, lambda: self._status_lbl.config(text="Test window open — close it when done"))
            self.after(0, lambda: self._test_btn.config(text="⏹ Stop Test", bg="#F44336"))
            self._poll_test()
        except Exception as e:
            self.after(0, lambda: self._status_lbl.config(text=f"✗ Error: {e}"))

    def _poll_test(self):
        if hasattr(self, '_test_process') and self._test_process and self._test_process.poll() is not None:
            rc = self._test_process.returncode
            self._test_process = None
            self._test_btn.config(text="🧪 Test Recognition", bg="#FF9800")
            if rc == 0:
                self._status_lbl.config(text="✓ Test completed")
            else:
                self._status_lbl.config(text=f"✗ Test exited with code {rc}")
        elif hasattr(self, '_test_process') and self._test_process:
            self.after(500, self._poll_test)

    # ══════════════════════════════════════════════════════════════════
    # Settings
    # ══════════════════════════════════════════════════════════════════

    def _apply_certainty(self):
        val = self._certainty_var.get().strip()
        try:
            float(val)
        except ValueError:
            self._status_lbl.config(text="✗ Invalid certainty value (use a number like 3.5)")
            return
        script = f"sed -i 's/^certainty.*/certainty = {val}/' /etc/howdy/config.ini"
        try:
            subprocess.run(["bash", "-c", script],
                          capture_output=True, timeout=10)
            self._status_lbl.config(text=f"✓ Certainty set to {val}")
        except Exception as e:
            self._status_lbl.config(text=f"✗ Error: {e}")

    # ══════════════════════════════════════════════════════════════════
    # Install Howdy
    # ══════════════════════════════════════════════════════════════════

    def _install_howdy(self):
        self._install_btn.config(state=tk.DISABLED, text="Installing…", bg="#555")
        self._install_progress_frame.pack(fill=tk.X, pady=(6, 0))
        self._install_progress_bar.start(20)
        self._install_progress_lbl.config(text="Running dnf install howdy…")
        threading.Thread(target=self._run_install_howdy, daemon=True).start()

    def _run_install_howdy(self):
        try:
            r = subprocess.run(["dnf", "install", "-y", "howdy"],
                              capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                self.after(0, lambda: self._install_progress_lbl.config(text="✓ Howdy installed!"))
                self._auto_configure_camera()
            else:
                err = r.stderr.strip()[-100:] if r.stderr else "Unknown error"
                self.after(0, lambda: self._install_progress_lbl.config(text=f"✗ Install failed: {err}"))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._install_progress_lbl.config(text="✗ Install timed out"))
        except Exception as e:
            self.after(0, lambda: self._install_progress_lbl.config(text=f"✗ Error: {e}"))
        finally:
            self.after(0, lambda: self._install_progress_bar.stop())
            self.after(2000, self._refresh_status)

    def _auto_configure_camera(self):
        ir = self._find_ir_camera()
        if ir:
            device = ir['device']
            try:
                subprocess.run([
                    "bash", "-c",
                    f"sed -i 's|^device_path.*|device_path = {device}|' /etc/howdy/config.ini"
                ], capture_output=True, timeout=5)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    # PAM Integration
    # ══════════════════════════════════════════════════════════════════

    def _enable_pam(self):
        self._pam_btn.config(state=tk.DISABLED, text="Configuring…", bg="#555")
        threading.Thread(target=self._run_enable_pam, daemon=True).start()

    def _run_enable_pam(self):
        services = ["sudo", "gdm-password", "login", "polkit-1"]
        succeeded = []
        failed = []

        for service in services:
            pam_file = Path(f"/etc/pam.d/{service}")
            try:
                if not pam_file.exists():
                    continue

                content = pam_file.read_text()
                if "howdy" in content:
                    succeeded.append(service)
                    continue

                # Determine which pam module to use
                if Path("/lib64/security/howdy/pam.py").exists():
                    howdy_pam = "auth    sufficient    pam_python.so /lib64/security/howdy/pam.py"
                elif Path("/usr/lib64/security/pam_howdy.so").exists():
                    howdy_pam = "auth    sufficient    pam_howdy.so"
                elif Path("/usr/lib/security/pam_howdy.so").exists():
                    howdy_pam = "auth    sufficient    pam_howdy.so"
                else:
                    howdy_pam = "auth    sufficient    pam_python.so /lib64/security/howdy/pam.py"

                lines = content.splitlines()
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith("#%PAM") or line.strip().startswith("# PAM"):
                        insert_idx = i + 1
                        break
                    if line.strip().startswith("auth"):
                        insert_idx = i
                        break

                lines.insert(insert_idx, howdy_pam)
                pam_file.write_text("\n".join(lines) + "\n")
                succeeded.append(service)

            except Exception as e:
                failed.append(f"{service}: {e}")

        if succeeded:
            msg = f"✓ PAM enabled for: {', '.join(succeeded)}"
            if failed:
                msg += f" | Failed: {', '.join(failed)}"
            self.after(0, lambda: self._status_lbl.config(text=msg))
        else:
            self.after(0, lambda: self._status_lbl.config(
                text=f"✗ PAM integration failed: {'; '.join(failed)}"))

        self.after(1000, self._refresh_status)

    # ══════════════════════════════════════════════════════════════════

    def get_state(self):
        return {}

    def load_state(self, data):
        self._refresh_status()

