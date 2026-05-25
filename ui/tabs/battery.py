import tkinter as tk
from tkinter import ttk
from backend import BackendError
from ..utils import show_message

class BatteryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=12)
        self.app = app
        self.charge_limit_var = tk.IntVar(value=80)
        self._slide_job = None
        self._cached_capacity = 0
        self._cached_ssd_health = None
        self._cached_disk_used_pct = None
        self._cached_disk_used_gb = None
        self._cached_disk_total_gb = None
        self._ssd_drive_widgets = {}
        self.create_widgets()
        self.after(100, self.update_status)

    def _get_theme(self):
        from ui import themes
        return themes.get()

    def create_widgets(self):
        t = self._get_theme()
        ttk.Label(self, text="Battery & SSD Health", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 20))

        main_row = ttk.Frame(self)
        main_row.pack(fill=tk.BOTH, expand=True)

        # Left side: single canvas — battery on top, NVMe icon below (stacked vertically)
        self._gauge_frame = tk.Frame(main_row, bg=t["battery_gauge_bg"])
        self._gauge_frame.pack(side=tk.LEFT, anchor="n", padx=(0, 20))

        # Canvas is tall enough for battery (~660) + NVMe 1.5× icon (~900) stacked
        self.gauge_canvas = tk.Canvas(self._gauge_frame, width=720, height=1560,
                                      bg=t["battery_gauge_bg"], highlightthickness=0)
        self.gauge_canvas.pack()

        # Right side
        info_frame = tk.Frame(main_row, bg=t["bg"])
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        status_top = tk.Frame(info_frame, bg=t["bg"])
        status_top.pack(fill=tk.X, pady=(0, 24))
        self.capacity_label = tk.Label(status_top, text="--%", font=("Arial", 36, "bold"),
                                       fg=t["battery_pct_fg"], bg=t["bg"])
        self.capacity_label.pack(side=tk.LEFT)
        status_text_frame = tk.Frame(status_top, bg=t["bg"])
        status_text_frame.pack(side=tk.LEFT, padx=16, fill=tk.Y)
        self.status_label = tk.Label(status_text_frame, text="Status Unknown",
                                     font=("Arial", 14), fg=t["fg"], bg=t["bg"])
        self.status_label.pack(anchor="w", pady=(4, 0))
        self.battery_info = tk.Label(status_text_frame, text="Path: unknown",
                                     font=("Arial", 10), fg=t["fg_secondary"], bg=t["bg"])
        self.battery_info.pack(anchor="w", pady=(4, 0))

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 20))

        # ── Battery Health ──────────────────────────────────────────────────────
        self._health_header_frame = tk.Frame(info_frame, bg=t["bg"])
        self._health_header_frame.pack(fill=tk.X, pady=(0, 10))
        self._health_title_lbl = tk.Label(self._health_header_frame, text="Battery Health",
                                          font=("Arial", 14, "bold"), fg=t["fg"], bg=t["bg"])
        self._health_title_lbl.pack(side=tk.LEFT)
        self.health_pct_label = tk.Label(self._health_header_frame, text="–",
                                         font=("Arial", 22, "bold"), fg=t["battery_pct_fg"], bg=t["bg"])
        self.health_pct_label.pack(side=tk.RIGHT)

        self.health_bar_canvas = tk.Canvas(info_frame, height=22,
                                           bg=t["battery_health_track"], highlightthickness=0)
        self.health_bar_canvas.pack(fill=tk.X, pady=(0, 8))
        self.health_bar_canvas.bind("<Configure>", lambda e: self._redraw_health_bar())

        self._stats_row = tk.Frame(info_frame, bg=t["bg"])
        self._stats_row.pack(fill=tk.X, pady=(0, 4))
        self._stat_col_frames = []

        def _stat_col(parent, label_text, value_text, value_color=None):
            col = tk.Frame(parent, bg=t["bg"])
            col.pack(side=tk.LEFT, padx=(0, 32))
            caption = tk.Label(col, text=label_text, font=("Arial", 9),
                                fg=t["fg_secondary"], bg=t["bg"])
            caption.pack(anchor="w")
            lbl = tk.Label(col, text=value_text, font=("Arial", 12, "bold"),
                           fg=value_color or t["fg"], bg=t["bg"])
            lbl.pack(anchor="w")
            self._stat_col_frames.append((col, caption, lbl))
            return lbl

        self._design_cap_lbl  = _stat_col(self._stats_row, "Design Capacity", "–")
        self._current_cap_lbl = _stat_col(self._stats_row, "Current Max",     "–")
        self._wear_lbl        = _stat_col(self._stats_row, "Wear Level",      "–")
        self._cycles_lbl      = _stat_col(self._stats_row, "Cycle Count",     "–")
        self._voltage_lbl     = _stat_col(self._stats_row, "Voltage Now",     "–")

        self.health_rating_label = tk.Label(info_frame, text="", font=("Arial", 11, "italic"),
                                            fg=t["fg_secondary"], bg=t["bg"])
        self.health_rating_label.pack(anchor="w", pady=(2, 0))

        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 20))

        # ── Charge Limit ───────────────────────────────────────────────────────
        self._charge_limit_title_lbl = tk.Label(info_frame, text="Charge Limit", font=("Arial", 14, "bold"),
                 fg=t["fg"], bg=t["bg"])
        self._charge_limit_title_lbl.pack(anchor="w", pady=(0, 6))
        self._charge_limit_desc_lbl = tk.Label(info_frame,
                 text="Limit the maximum charge level. Keeping the battery below 100% reduces\n"
                      "time spent at peak voltage, slowing electrolyte oxidation over time.",
                 font=("Arial", 11), fg=t["fg_secondary"], bg=t["bg"])
        self._charge_limit_desc_lbl.pack(anchor="w", pady=(0, 12))

        limit_wrapper = tk.Frame(info_frame, bg=t["bg"])
        limit_wrapper.pack(anchor="w", pady=(0, 16))
        self.charge_value_label = tk.Label(limit_wrapper, text="80%", width=4,
                                           font=("Arial", 14, "bold"),
                                           fg=t["battery_pct_fg"], bg=t["bg"])
        self.charge_value_label.pack(side=tk.RIGHT, padx=(10, 0), anchor="center")
        limit_container = tk.Frame(limit_wrapper, bg=t["bg"])
        limit_container.pack(side=tk.LEFT)

        self._preset_row = tk.Frame(limit_container, bg=t["scale_bg"])
        self._preset_row.pack(fill=tk.X, pady=0)
        self._preset_buttons = []
        for col_idx, (preset_val, preset_label, preset_desc) in enumerate([
            (60,  "60% — Long Storage", "Best for long-term storage / always-plugged-in"),
            (80,  "80% — Daily Use",    "Recommended for everyday laptop use"),
            (100, "100% — Max Charge",  "Full charge for travel / long sessions"),
        ]):
            self._preset_row.columnconfigure(col_idx, weight=1, uniform="presets")
            btn = tk.Button(self._preset_row, text=preset_label, font=("Arial", 10),
                            fg=t["btn_fg"], bg=t["btn_bg"], relief="flat", padx=10, pady=4,
                            cursor="hand2",
                            command=lambda v=preset_val: self._apply_preset(v))
            btn.grid(row=0, column=col_idx, sticky="ew")
            self._preset_buttons.append(btn)
            btn.bind("<Enter>", lambda e, tip=preset_desc: self.app.status_var.set(tip))
            btn.bind("<Leave>", lambda e: self.app.status_var.set(""))

        self.charge_slider = tk.Scale(limit_container, from_=20, to=100, orient=tk.HORIZONTAL,
                                      variable=self.charge_limit_var, command=self.on_slide,
                                      sliderlength=30, width=20, showvalue=False,
                                      bg=t["scale_bg"], fg=t["scale_fg"], troughcolor=t["scale_trough"],
                                      highlightthickness=1,
                                      highlightbackground=t["scale_bg"],
                                      highlightcolor=t["scale_bg"],
                                      bd=0, relief="flat",
                                      activebackground=t["scale_active"],
                                      repeatdelay=150, repeatinterval=50)
        self.charge_slider.pack(fill=tk.X)

        self._ticks_canvas = tk.Canvas(limit_container, height=28, bg=t["bg"], highlightthickness=0)
        self._ticks_canvas.pack(fill=tk.X)
        self._ticks_canvas.bind("<Configure>", self._draw_ticks)
        self._tick_fg = t["fg_secondary"]
        self._limit_wrapper = limit_wrapper

        # ── SSD Health ─────────────────────────────────────────────────────────
        ttk.Separator(info_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(20, 16))
        self._ssd_title_row = tk.Frame(info_frame, bg=t["bg"])
        self._ssd_title_row.pack(fill=tk.X, pady=(0, 10))
        self._ssd_title_lbl = tk.Label(self._ssd_title_row, text="SSD Health",
                                       font=("Arial", 14, "bold"), fg=t["fg"], bg=t["bg"])
        self._ssd_title_lbl.pack(side=tk.LEFT)
        self._ssd_refresh_btn = tk.Button(self._ssd_title_row, text="↻ Refresh",
                                          font=("Arial", 9), fg=t["btn_fg"], bg=t["btn_bg"],
                                          relief="flat", padx=8, pady=2, cursor="hand2",
                                          command=self._refresh_ssd)
        self._ssd_refresh_btn.pack(side=tk.RIGHT)

        self._ssd_container = tk.Frame(info_frame, bg=t["bg"])
        self._ssd_container.pack(fill=tk.X)

    # ── SSD panel build/update ──────────────────────────────────────────────────

    def _refresh_ssd(self):
        """Fetch SSD SMART data and update panels in-place (no flicker)."""
        from ui import themes
        t = themes.get()

        ssd_data = self.app.backend.get_ssd_info() if self.app.backend else {"drives": []}
        drives   = ssd_data.get("drives", [])

        if drives:
            d0 = drives[0]
            self._cached_ssd_health    = float(d0["health_pct"]) if d0.get("health_pct") is not None else None
            self._cached_disk_used_pct = d0.get("disk_used_pct")
            self._cached_disk_used_gb  = d0.get("disk_used_gb")
            self._cached_disk_total_gb = d0.get("disk_total_gb")
        else:
            self._cached_ssd_health = self._cached_disk_used_pct = None

        # Redraw canvas (battery + NVMe icon)
        self._draw_gauge(self._cached_capacity, self.charge_limit_var.get())

        if not drives:
            for w in self._ssd_container.winfo_children():
                w.destroy()
            self._ssd_drive_widgets = {}
            tk.Label(self._ssd_container, text="No NVMe drives detected.",
                     font=("Arial", 10), fg=t["fg_muted"], bg=t["bg"]).pack(anchor="w")
            return

        current_devices = {d["device"] for d in drives}
        for dev in list(self._ssd_drive_widgets):
            if dev not in current_devices:
                self._ssd_drive_widgets[dev]["panel"].destroy()
                del self._ssd_drive_widgets[dev]

        for drive in drives:
            dev = drive["device"]
            if dev not in self._ssd_drive_widgets:
                self._build_ssd_drive_panel(drive, t)
            else:
                self._update_ssd_drive_panel(drive, t)

    def _build_ssd_drive_panel(self, drive: dict, t: dict):
        """Build the panel for one NVMe drive (first time only)."""
        panel = tk.Frame(self._ssd_container, bg=t["bg"])
        panel.pack(fill=tk.X, pady=(0, 12))
        dev  = drive.get("device", "?")
        refs = {"panel": panel}

        hdr = tk.Frame(panel, bg=t["bg"])
        hdr.pack(fill=tk.X)
        model   = drive.get("model", "")
        cap     = drive.get("capacity_gb")
        cap_str = f"  {int(cap):.0f} GB" if cap else ""
        serial  = drive.get("serial", "")
        refs["hdr_lbl"] = tk.Label(hdr, text=f"{dev}  {model}{cap_str}",
                                   font=("Arial", 12, "bold"), fg=t["fg"], bg=t["bg"])
        refs["hdr_lbl"].pack(side=tk.LEFT)
        refs["serial_lbl"] = tk.Label(hdr, text=f"S/N: {serial}" if serial else "",
                                      font=("Arial", 10), fg=t["fg_secondary"], bg=t["bg"])
        refs["serial_lbl"].pack(side=tk.RIGHT)

        hdr2 = tk.Frame(panel, bg=t["bg"])
        hdr2.pack(fill=tk.X, pady=(8, 4))
        refs["health_title"] = tk.Label(hdr2, text="Drive Health",
                                        font=("Arial", 14, "bold"), fg=t["fg"], bg=t["bg"])
        refs["health_title"].pack(side=tk.LEFT)
        refs["health_pct_lbl"] = tk.Label(hdr2, text="–",
                                          font=("Arial", 22, "bold"), fg=t["battery_pct_fg"], bg=t["bg"])
        refs["health_pct_lbl"].pack(side=tk.RIGHT)

        refs["health_bar"] = tk.Canvas(panel, height=22, bg=t["battery_health_track"], highlightthickness=0)
        refs["health_bar"].pack(fill=tk.X, pady=(0, 4))

        refs["health_rating"] = tk.Label(panel, text="", font=("Arial", 11, "italic"),
                                         fg=t["fg_secondary"], bg=t["bg"])
        refs["health_rating"].pack(anchor="w", pady=(0, 6))

        # Stats rows — each column is a persistent Frame+Label pair stored in refs
        stats1 = tk.Frame(panel, bg=t["bg"])
        stats1.pack(fill=tk.X, pady=(4, 0))
        refs["stats1"] = stats1
        refs["stats1_cols"] = {}   # key -> (col_frame, caption_lbl, value_lbl)

        stats2 = tk.Frame(panel, bg=t["bg"])
        stats2.pack(fill=tk.X, pady=(8, 0))
        refs["stats2"] = stats2
        refs["stats2_cols"] = {}

        refs["warn_lbl"] = tk.Label(panel, text="", font=("Arial", 10),
                                    fg=t["battery_fill_low"], bg=t["bg"], justify="left")
        refs["warn_lbl"].pack(anchor="w")

        self._ssd_drive_widgets[dev] = refs
        self._update_ssd_drive_panel(drive, t)

    def _update_ssd_drive_panel(self, drive: dict, t: dict):
        """Update a drive panel in-place — no widget destruction, no flicker."""
        dev  = drive.get("device", "?")
        refs = self._ssd_drive_widgets.get(dev)
        if refs is None:
            return

        # ── Re-theme structural frames ──
        for key in ("panel", "stats1", "stats2"):
            if key in refs and refs[key].winfo_exists():
                refs[key].configure(bg=t["bg"])

        # ── Re-theme labels that must stay bg-correct but whose fg we control separately ──
        for key in ("hdr_lbl", "serial_lbl", "health_title", "warn_lbl"):
            if key in refs and refs[key].winfo_exists():
                refs[key].configure(bg=t["bg"])
        refs["hdr_lbl"].configure(fg=t["fg"])
        refs["serial_lbl"].configure(fg=t["fg_secondary"])
        refs["health_title"].configure(fg=t["fg"])

        # ── Health % label + bar + rating ──
        health_pct = drive.get("health_pct")
        pct_used   = drive.get("percentage_used")

        if health_pct is not None:
            hp = float(health_pct)
            h_color = (t["battery_fill_high"] if hp >= 80
                       else t["battery_fill_mid"] if hp >= 60
                       else t["battery_fill_low"])
            used_str = f"  ({pct_used}% media used)" if pct_used is not None else ""
            refs["health_pct_lbl"].configure(text=f"{hp:.0f}%{used_str}",
                                             fg=h_color, bg=t["bg"])
            refs["health_rating"].configure(text=self._ssd_health_rating(hp),
                                            fg=h_color, bg=t["bg"])

            bc = refs["health_bar"]
            bc.configure(bg=t["battery_health_track"])
            def _draw_bar(_bc=bc, _hp=hp, _hc=h_color, _t=t):
                w = _bc.winfo_width() or 440
                h = 22
                _bc.delete("all")
                _bc.create_rectangle(0, 0, w, h, fill=_t["battery_health_track"], outline="")
                _bc.create_rectangle(0, 0, int(w * _hp / 100), h, fill=_hc, outline="")
                for pct in (20, 40, 60, 80):
                    x = int(w * pct / 100)
                    _bc.create_line(x, 0, x, h, fill=_t["battery_gauge_bg"], width=2)
            _draw_bar()
            refs["health_bar"].bind("<Configure>", lambda e, f=_draw_bar: f())
        else:
            refs["health_pct_lbl"].configure(text="–", fg=t["fg_muted"], bg=t["bg"])
            refs["health_rating"].configure(text="No health data", fg=t["fg_muted"], bg=t["bg"])

        # ── Stats rows — persistent columns, updated in-place ──
        def _sync_stats(frame, cols_dict, items):
            """Create missing columns, update existing ones, hide extras."""
            if items:
                if not frame.winfo_ismapped():
                    frame.pack(fill=tk.X, pady=(4, 0))
            else:
                frame.pack_forget()
                return
            for i, (lbl_text, val_text, warn) in enumerate(items):
                key = str(i)
                fg_val = t["battery_fill_low"] if warn else t["fg"]
                if key not in cols_dict:
                    col_f = tk.Frame(frame, bg=t["bg"])
                    col_f.pack(side=tk.LEFT, padx=(0, 32))
                    cap_lbl = tk.Label(col_f, text=lbl_text, font=("Arial", 9),
                                       fg=t["fg_secondary"], bg=t["bg"])
                    cap_lbl.pack(anchor="w")
                    val_lbl = tk.Label(col_f, text=val_text, font=("Arial", 12, "bold"),
                                       fg=fg_val, bg=t["bg"])
                    val_lbl.pack(anchor="w")
                    cols_dict[key] = (col_f, cap_lbl, val_lbl)
                else:
                    col_f, cap_lbl, val_lbl = cols_dict[key]
                    col_f.configure(bg=t["bg"])
                    cap_lbl.configure(text=lbl_text, fg=t["fg_secondary"], bg=t["bg"])
                    val_lbl.configure(text=val_text, fg=fg_val, bg=t["bg"])
                    # Ensure visible
                    if not col_f.winfo_ismapped():
                        col_f.pack(side=tk.LEFT, padx=(0, 32))
            # Hide unused columns
            for key in list(cols_dict):
                if int(key) >= len(items):
                    cols_dict[key][0].pack_forget()

        temp         = drive.get("temperature")
        spare        = drive.get("available_spare")
        spare_thresh = drive.get("available_spare_threshold")
        poh          = drive.get("power_on_hours")
        cycles       = drive.get("power_cycles")
        written      = drive.get("data_written_tb")
        read_tb      = drive.get("data_read_tb")
        unsafe       = drive.get("unsafe_shutdowns")
        errors       = drive.get("media_errors")
        crit         = drive.get("critical_warning", 0)
        used_gb      = drive.get("disk_used_gb")
        total_gb     = drive.get("disk_total_gb")
        free_gb      = (total_gb - used_gb) if (total_gb and used_gb) else None

        items1 = []
        if temp is not None:
            items1.append(("Temperature", f"{temp} °C", int(temp) >= 65))
        if spare is not None:
            spare_str = f"{spare}%  (min {spare_thresh}%)" if spare_thresh else f"{spare}%"
            items1.append(("Available Spare", spare_str, int(spare) <= int(spare_thresh or 5)))
        if poh is not None:
            items1.append(("Power-On Time", f"{int(poh):,} h  ({int(poh)//24:,} d)", False))
        if cycles is not None:
            items1.append(("Power Cycles", f"{int(cycles):,}", False))
        _sync_stats(refs["stats1"], refs["stats1_cols"], items1)

        items2 = []
        if used_gb is not None and total_gb is not None:
            items2.append(("Storage Used", f"{used_gb:.0f} / {total_gb:.0f} GB", False))
            items2.append(("Storage Free", f"{free_gb:.0f} GB", False))
        if written is not None:
            items2.append(("Total Written", f"{written} TB", False))
        if read_tb is not None:
            items2.append(("Total Read", f"{read_tb} TB", False))
        if unsafe is not None:
            items2.append(("Unsafe Shutdowns", f"{int(unsafe):,}", int(unsafe) > 100))
        if errors is not None:
            items2.append(("Media Errors", f"{int(errors):,}", int(errors) > 0))
        _sync_stats(refs["stats2"], refs["stats2_cols"], items2)

        # ── Warning banner ──
        crit_msgs = []
        if crit:
            crit_msgs.append(f"⚠ Critical warning flag: {crit:#04x}")
        if spare is not None and spare_thresh is not None and int(spare) <= int(spare_thresh):
            crit_msgs.append("⚠ Available spare below threshold — drive may fail soon")
        if errors is not None and int(errors) > 0:
            crit_msgs.append(f"⚠ {int(errors)} media error(s) detected")
        refs["warn_lbl"].configure(text="\n".join(crit_msgs) if crit_msgs else "",
                                   fg=t["battery_fill_low"], bg=t["bg"])

    def _ssd_health_rating(self, health_pct) -> str:
        if health_pct >= 90:   return "Excellent — minimal wear"
        elif health_pct >= 70: return "Good — normal wear"
        elif health_pct >= 50: return "Moderate — plan for replacement"
        else:                  return "Replace soon — high wear"

    # ── Main canvas drawing ─────────────────────────────────────────────────────

    def _draw_gauge(self, capacity, limit):
        """Draw lithium prismatic cell (top) + technically-accurate NVMe M.2 stick (bottom)."""
        from ui import themes
        import math
        t = themes.get()
        c = self.gauge_canvas
        c.delete("all")

        # ═══════════════════════════════════════════════════════════════════════
        #  LITHIUM PRISMATIC CELL  (laptop / EV pouch style)
        #  Layout:
        #    - Positive tab: flat, low-profile metallic strip at top (Al foil tab)
        #    - Cell body: tall rectangular can with laser-welded seam lines
        #    - Negative tab: wider copper strip at bottom
        #    - Safety vent scored into top face
        #    - 20 horizontal fill segments inside
        # ═══════════════════════════════════════════════════════════════════════
        cx, cy = 360, 320
        bw, bh = 300, 480
        x1, y1 = cx - bw/2, cy - bh/2
        x2, y2 = cx + bw/2, cy + bh/2

        wall_color    = t["battery_terminal"]
        wall_hi_color = t["battery_terminal_outline"]
        body_bg       = t["battery_body_bg"]
        empty_color   = t["battery_empty_bar"]
        fill_high     = t["battery_fill_high"]
        fill_mid      = t["battery_fill_mid"]
        fill_low_col  = t["battery_fill_low"]
        charge_col    = t["battery_charge_line"]

        # ── Cell body : flat-cornered aluminium can ───────────────────────────
        c.create_rectangle(x1, y1, x2, y2, fill=body_bg, outline=wall_color, width=6)
        # Laser-weld seam line down the sides (thin inner lines)
        seam_inset = 10
        c.create_line(x1 + seam_inset, y1 + 16, x1 + seam_inset, y2 - 16,
                      fill=wall_hi_color, width=1)
        c.create_line(x2 - seam_inset, y1 + 16, x2 - seam_inset, y2 - 16,
                      fill=wall_hi_color, width=1)
        # Can surface highlight (suggests metal sheen)
        c.create_line(x1 + 22, y1 + 20, x1 + 22, y2 - 20, fill=wall_hi_color, width=2)
        c.create_line(x2 - 22, y1 + 20, x2 - 22, y2 - 20, fill=wall_hi_color, width=2)

        # ── Safety vent (scored into top face, typical of prismatic cells) ────
        vy = y1 + 22
        vc_w = 90
        c.create_rectangle(cx - vc_w//2, vy - 5, cx + vc_w//2, vy + 5,
                            fill=wall_hi_color, outline=wall_color, width=1)
        c.create_text(cx, vy, text="VENT", font=("Arial", 7), fill=body_bg, anchor="center")

        # ── Fill segments (20 bars) ───────────────────────────────────────────
        bar_pad  = 14
        bar_gap  = 5
        num_bars = 20
        area_top = y1 + bar_pad
        area_bot = y2 - bar_pad
        bar_h    = (area_bot - area_top - (num_bars - 1) * bar_gap) / num_bars
        bx1      = x1 + bar_pad
        bx2      = x2 - bar_pad

        for i in range(num_bars):
            bar_pct_low = (num_bars - 1 - i) * 5
            byt1 = area_top + i * (bar_h + bar_gap)
            byt2 = byt1 + bar_h
            if capacity >= bar_pct_low + 5:
                col = (fill_low_col if capacity <= 20
                       else fill_mid if capacity <= 50
                       else fill_high)
                c.create_rectangle(bx1, byt1, bx2, byt2, fill=col, outline="")
            elif capacity > bar_pct_low:
                col = (fill_low_col if capacity <= 20
                       else fill_mid if capacity <= 50
                       else fill_high)
                c.create_rectangle(bx1, byt1, bx2, byt2, fill=empty_color, outline="")
                frac = (capacity - bar_pct_low) / 5.0
                c.create_rectangle(bx1, byt2 - bar_h * frac, bx2, byt2, fill=col, outline="")
            else:
                c.create_rectangle(bx1, byt1, bx2, byt2, fill=empty_color, outline="")

        # ── Charge / Limit marker lines ───────────────────────────────────────
        limit_y  = y2 - (limit    / 100.0) * bh
        charge_y = y2 - (capacity / 100.0) * bh
        charge_y = max(y1 + 10, min(y2 - 10, charge_y))

        c.create_line(x1 - 28, limit_y,  x2 + 28, limit_y,
                      fill=t["battery_pct_fg"], width=5, dash=(8, 4))
        c.create_text(x2 + 40, limit_y - 18, text="Limit",
                      font=("Arial", 13, "bold"), fill=t["battery_pct_fg"], anchor="w")
        c.create_text(x2 + 40, limit_y + 18, text=f"{limit}%",
                      font=("Arial", 15, "bold"), fill=t["battery_pct_fg"], anchor="w")
        c.create_line(x1 - 28, charge_y, x2 + 28, charge_y,
                      fill=charge_col, width=5, dash=(8, 4))
        c.create_text(x1 - 40, charge_y - 18, text="Charge",
                      font=("Arial", 13, "bold"), fill=charge_col, anchor="e")
        c.create_text(x1 - 40, charge_y + 18, text=f"{capacity}%",
                      font=("Arial", 15, "bold"), fill=charge_col, anchor="e")

        # ── Positive terminal : flat Al strip at top (low profile, flush) ─────
        # Typical lithium prismatic: positive tab is a thin aluminium strip
        # flush at the top of the can — NOT a raised cylinder nub.
        pos_tab_w = 120
        pos_tab_h = 14    # very flat, ~2mm foil
        pos_tab_x1 = cx - pos_tab_w // 2
        pos_tab_y2 = y1   # flush with top of can
        pos_tab_y1 = pos_tab_y2 - pos_tab_h
        # Aluminium tab: slightly lighter shade than can wall
        c.create_rectangle(pos_tab_x1, pos_tab_y1, pos_tab_x1 + pos_tab_w, pos_tab_y2,
                            fill=wall_hi_color, outline=wall_color, width=2)
        # Foil thickness sheen line
        c.create_line(pos_tab_x1 + 4, pos_tab_y1 + 3,
                      pos_tab_x1 + pos_tab_w - 4, pos_tab_y1 + 3,
                      fill=wall_color, width=1)

        # ── Negative terminal : wider copper tab at bottom ────────────────────
        neg_tab_w = 160
        neg_tab_h = 14
        neg_tab_x1 = cx - neg_tab_w // 2
        c.create_rectangle(neg_tab_x1, y2, neg_tab_x1 + neg_tab_w, y2 + neg_tab_h,
                            fill=wall_color, outline=wall_hi_color, width=2)
        c.create_line(neg_tab_x1 + 4, y2 + 3,
                      neg_tab_x1 + neg_tab_w - 4, y2 + 3,
                      fill=wall_hi_color, width=1)

        # ── "+" / "−" polarity labels ──────────────────────────────────────────
        c.create_text(cx, pos_tab_y1 - 10,
                      text="+", font=("Arial", 16, "bold"), fill=t["battery_pct_fg"], anchor="s")
        c.create_text(cx, y2 + neg_tab_h + 10,
                      text="−", font=("Arial", 16, "bold"), fill=t["fg_secondary"], anchor="n")

        base_h = neg_tab_h  # used for NVMe y_offset below

        # ═══════════════════════════════════════════════════════════════════════
        #  NVMe M.2 2280 STICK — Technically accurate background
        #
        #  Layer order (back→front):
        #   1. PCB body (FR4 substrate)
        #   2. Copper trace routing (serpentine high-speed lanes + power planes)
        #   3. NAND Flash packages × 4 (two per side simulation, both drawn front)
        #   4. NVMe Controller IC with solder balls / pads
        #   5. Decoupling capacitors (0402/0201 SMD)
        #   6. Crystal oscillator
        #   7. Disk-usage fill bars (overlay, drawn over everything)
        #   8. Screw-mount hole + ring
        #   9. M-Key edge connector with gold fingers
        #  10. Usage marker dashed line + labels
        # ═══════════════════════════════════════════════════════════════════════
        y_offset = y2 + base_h + 80

        ncx   = cx
        pcb_w = 240
        pcb_h = 660
        tab_w = int(pcb_w * 0.85)
        tab_h = 42
        pcb_y1 = y_offset
        pcb_y2 = pcb_y1 + pcb_h
        tab_y2 = pcb_y2 + tab_h

        # ── Theme palette ─────────────────────────────────────────────────────
        pcb_body  = t["battery_body_bg"]
        pcb_hi    = t["battery_empty_bar"]
        chip_body = t["bg_secondary"]
        chip_hi   = t["bg_tertiary"]
        chip_dot  = t["accent"]
        chip_text = t["fg_secondary"]
        gold_col  = t["accent"]
        title_col = t["fg_muted"]
        trace_col = t["fg_muted"]   # subtle trace lines

        # ── 1. PCB body (flat-cornered, represents FR4 substrate) ─────────────
        c.create_rectangle(ncx - pcb_w//2, pcb_y1, ncx + pcb_w//2, pcb_y2,
                           fill=pcb_body, outline=pcb_hi, width=2)

        # ── 2. Copper trace routing (high-speed differential pairs) ───────────
        # PCIe × 4 differential pairs: 8 traces running vertically, tight spacing
        # Represented as thin parallel lines in the centre corridor
        trace_x_start = ncx - 24
        for ti in range(8):
            tx = trace_x_start + ti * 6
            # Serpentine section at top (signal length matching)
            sy = pcb_y1 + 160
            snake_h = 18
            snake_w = 8
            dir_ = 1 if ti % 2 == 0 else -1
            c.create_line(tx, pcb_y1 + 130, tx, sy, fill=trace_col, width=1)
            c.create_line(tx, sy, tx + dir_*snake_w, sy, fill=trace_col, width=1)
            c.create_line(tx + dir_*snake_w, sy, tx + dir_*snake_w, sy + snake_h,
                          fill=trace_col, width=1)
            c.create_line(tx + dir_*snake_w, sy + snake_h, tx, sy + snake_h,
                          fill=trace_col, width=1)
            c.create_line(tx, sy + snake_h, tx, pcb_y2 - 30, fill=trace_col, width=1)

        # Power plane boundary (dashed rectangle representing copper pour)
        pp_margin = 18
        c.create_rectangle(ncx - pcb_w//2 + pp_margin, pcb_y1 + pp_margin,
                            ncx + pcb_w//2 - pp_margin, pcb_y2 - pp_margin,
                            fill="", outline=trace_col, width=1, dash=(4, 6))

        # ── 3. NAND Flash packages × 4 (stacked NAND simulation) ─────────────
        # Real M.2 2280: 2-4 NAND packages on front, sometimes 2 on back (double-sided)
        # Draw 4 packages in 2 columns × 2 rows in the lower 2/3 of PCB
        nand_w, nand_h = 90, 90
        nand_row_gap   = 18
        nand_col_gap   = 16
        nand_y_start   = pcb_y1 + 240
        nand_positions = [
            (ncx - pcb_w//4 - nand_w//2, nand_y_start),
            (ncx + pcb_w//4 - nand_w//2, nand_y_start),
            (ncx - pcb_w//4 - nand_w//2, nand_y_start + nand_h + nand_row_gap),
            (ncx + pcb_w//4 - nand_w//2, nand_y_start + nand_h + nand_row_gap),
        ]
        for ni, (nx, ny) in enumerate(nand_positions):
            # Package body
            c.create_rectangle(nx, ny, nx + nand_w, ny + nand_h,
                               fill=chip_body, outline=chip_hi, width=2)
            # Bevel highlight (top-left corner bright edge)
            c.create_line(nx + 2, ny + 2, nx + nand_w - 2, ny + 2, fill=chip_hi, width=1)
            c.create_line(nx + 2, ny + 2, nx + 2, ny + nand_h - 2, fill=chip_hi, width=1)
            # Bond wire leads — 7 pads per side (left and right edges)
            lead_count = 7
            lead_spacing = nand_h // (lead_count + 1)
            for li in range(lead_count):
                ly = ny + (li + 1) * lead_spacing
                # Left leads
                c.create_rectangle(nx - 8, ly - 2, nx, ly + 2, fill=chip_hi, outline="")
                # Right leads
                c.create_rectangle(nx + nand_w, ly - 2, nx + nand_w + 8, ly + 2,
                                   fill=chip_hi, outline="")
            # Pin-1 marker dot
            c.create_oval(nx + 4, ny + 4, nx + 10, ny + 10, fill=chip_dot, outline="")
            # NAND label
            c.create_text(nx + nand_w//2, ny + nand_h//2 - 8,
                          text="NAND", font=("Arial", 7, "bold"), fill=chip_text, anchor="center")
            c.create_text(nx + nand_w//2, ny + nand_h//2 + 6,
                          text=f"TLC {128*(ni+1)}G", font=("Arial", 6), fill=chip_text, anchor="center")

        # ── 4. NVMe Controller (top area, centred, BGA package) ───────────────
        ctrl_w, ctrl_h = 80, 80
        ctrl_x = ncx - ctrl_w // 2
        ctrl_y = pcb_y1 + 110
        c.create_rectangle(ctrl_x, ctrl_y, ctrl_x + ctrl_w, ctrl_y + ctrl_h,
                           fill=chip_body, outline=chip_hi, width=2)
        # BGA solder ball array — 5×5 dot grid visible through die
        bga_margin = 14
        bga_cols, bga_rows = 5, 5
        bga_pitch_x = (ctrl_w - 2*bga_margin) // (bga_cols - 1)
        bga_pitch_y = (ctrl_h - 2*bga_margin) // (bga_rows - 1)
        for br in range(bga_rows):
            for bc in range(bga_cols):
                bx = ctrl_x + bga_margin + bc * bga_pitch_x
                by = ctrl_y + bga_margin + br * bga_pitch_y
                c.create_oval(bx - 2, by - 2, bx + 2, by + 2, fill=chip_hi, outline="")
        # Chip label overlay
        c.create_text(ctrl_x + ctrl_w//2, ctrl_y - 10,
                      text="NVMe Ctrl", font=("Arial", 7, "bold"), fill=chip_text, anchor="s")
        # Pin-1 corner marker
        c.create_oval(ctrl_x + 3, ctrl_y + 3, ctrl_x + 9, ctrl_y + 9, fill=chip_dot, outline="")

        # ── 5. Decoupling capacitors (0402 SMD, scattered near ctrl + NAND) ───
        cap_positions = [
            (ncx - 44, pcb_y1 + 98), (ncx + 34, pcb_y1 + 98),
            (ncx - 44, ctrl_y + ctrl_h + 8), (ncx + 34, ctrl_y + ctrl_h + 8),
            (ncx - 80, nand_y_start - 12), (ncx + 56, nand_y_start - 12),
            (ncx - 80, nand_y_start + nand_h + nand_row_gap + nand_h + 12),
            (ncx + 56, nand_y_start + nand_h + nand_row_gap + nand_h + 12),
        ]
        for (cpx, cpy) in cap_positions:
            # 0402 cap body (1.0 × 0.5 mm equivalent)
            c.create_rectangle(cpx - 7, cpy - 3, cpx + 7, cpy + 3,
                               fill=chip_body, outline=chip_hi, width=1)
            # End terminations (silver pads)
            c.create_rectangle(cpx - 7, cpy - 3, cpx - 3, cpy + 3, fill=chip_hi, outline="")
            c.create_rectangle(cpx + 3, cpy - 3, cpx + 7, cpy + 3, fill=chip_hi, outline="")

        # ── 6. Crystal oscillator (small rectangular package) ─────────────────
        xtal_x = ncx + pcb_w//2 - 38
        xtal_y = pcb_y1 + 108
        xtal_w, xtal_h = 22, 14
        c.create_rectangle(xtal_x, xtal_y, xtal_x + xtal_w, xtal_y + xtal_h,
                           fill=chip_hi, outline=chip_body, width=1)
        c.create_text(xtal_x + xtal_w//2, xtal_y + xtal_h//2,
                      text="Xtal", font=("Arial", 5), fill=pcb_body, anchor="center")

        # ── 7. Disk-usage fill bars (overlay over entire PCB, fills to screw hole) ──
        # Bars go from pcb_y1 (screw hole level) all the way to pcb_y2
        disk_pct = self._cached_disk_used_pct
        used_gb  = self._cached_disk_used_gb
        total_gb = self._cached_disk_total_gb
        free_gb  = (total_gb - used_gb) if (total_gb and used_gb) else None

        if disk_pct is None:
            store_fill = t["battery_empty_bar"]
        elif disk_pct >= 90:
            store_fill = t["battery_fill_low"]
        elif disk_pct >= 70:
            store_fill = t["battery_fill_mid"]
        else:
            store_fill = t["battery_fill_high"]
        store_empty = t["battery_empty_bar"]

        bar_area_top = pcb_y1         # start right at top of PCB (screw hole level)
        bar_area_bot = pcb_y2
        bar_area_h   = bar_area_bot - bar_area_top
        ssd_num_bars = 20
        ssd_bar_gap  = 5
        ssd_bar_h    = (bar_area_h - (ssd_num_bars - 1) * ssd_bar_gap) / ssd_num_bars
        # Bars use full PCB width minus wall inset
        bar_inset = 8
        sbx1 = ncx - pcb_w//2 + bar_inset
        sbx2 = ncx + pcb_w//2 - bar_inset

        for i in range(ssd_num_bars):
            bar_pct_low = (ssd_num_bars - 1 - i) * (100 / ssd_num_bars)
            byt1 = bar_area_top + i * (ssd_bar_h + ssd_bar_gap)
            byt2 = byt1 + ssd_bar_h
            if disk_pct is not None and disk_pct >= bar_pct_low + (100 / ssd_num_bars):
                col = store_fill
            elif disk_pct is not None and disk_pct > bar_pct_low:
                col = store_fill
            else:
                col = store_empty
            # Semi-transparent overlay: stipple for bg components to show through
            c.create_rectangle(sbx1, byt1, sbx2, byt2,
                               fill=col, outline="", stipple="gray50")

        # ── 8. Screw mounting hole + anti-pad ring (top of PCB) ───────────────
        mh_r = 14
        mh_cx = ncx
        mh_cy = pcb_y1 + 22
        # Anti-pad (copper keepout ring)
        c.create_oval(mh_cx - mh_r - 6, mh_cy - mh_r - 6,
                      mh_cx + mh_r + 6, mh_cy + mh_r + 6,
                      fill="", outline=pcb_hi, width=2, dash=(3, 4))
        # Gold ring (plated through-hole barrel)
        c.create_oval(mh_cx - mh_r, mh_cy - mh_r, mh_cx + mh_r, mh_cy + mh_r,
                      fill=gold_col, outline=pcb_hi, width=2)
        # Drill hole (empty)
        c.create_oval(mh_cx - mh_r + 5, mh_cy - mh_r + 5,
                      mh_cx + mh_r - 5, mh_cy + mh_r - 5,
                      fill=t["battery_gauge_bg"], outline="")

        # ── Usage marker dashed line ───────────────────────────────────────────
        if disk_pct is not None:
            used_y = bar_area_bot - (disk_pct / 100.0) * bar_area_h
            used_y = max(bar_area_top + 10, min(bar_area_bot - 10, used_y))
            c.create_line(ncx - pcb_w//2 - 22, used_y, ncx + pcb_w//2 + 22, used_y,
                          fill=store_fill, width=4, dash=(8, 4))
            c.create_text(ncx + pcb_w//2 + 34, used_y - 18, text="Used",
                          font=("Arial", 12, "bold"), fill=store_fill, anchor="w")
            c.create_text(ncx + pcb_w//2 + 34, used_y + 16, text=f"{disk_pct:.0f}%",
                          font=("Arial", 14, "bold"), fill=store_fill, anchor="w")

        # ── Silkscreen labels ──────────────────────────────────────────────────
        c.create_text(ncx + pcb_w//2 - 8, pcb_y1 + 44,
                      text="M.2 2280", font=("Arial", 8), fill=title_col, anchor="ne")

        # ── 9. M-Key edge connector with gold fingers ──────────────────────────
        c.create_rectangle(ncx - tab_w//2, pcb_y2, ncx + tab_w//2, tab_y2,
                           fill=pcb_body, outline=pcb_hi, width=2)

        notch_center = ncx - tab_w//2 + int(tab_w * 0.67)
        notch_w  = 18
        pin_w    = 10
        pin_gap  = 5
        pin_y1_c = pcb_y2 + 6
        pin_y2_c = tab_y2 - 6

        lx = ncx - tab_w//2 + 8
        while lx + pin_w <= notch_center - notch_w//2 - 2:
            c.create_rectangle(lx, pin_y1_c, lx + pin_w, pin_y2_c, fill=gold_col, outline="")
            lx += pin_w + pin_gap

        notch_x1 = notch_center - notch_w//2
        notch_x2 = notch_center + notch_w//2
        c.create_rectangle(notch_x1, pcb_y2 - 2, notch_x2, tab_y2 + 2,
                           fill=t["battery_gauge_bg"], outline=t["battery_gauge_bg"])
        c.create_line(notch_x1, pcb_y2, notch_x1, tab_y2, fill=pcb_hi, width=1)
        c.create_line(notch_x2, pcb_y2, notch_x2, tab_y2, fill=pcb_hi, width=1)

        rx = notch_x2 + pin_gap
        while rx + pin_w <= ncx + tab_w//2 - 8:
            c.create_rectangle(rx, pin_y1_c, rx + pin_w, pin_y2_c, fill=gold_col, outline="")
            rx += pin_w + pin_gap

        # ── Storage labels below connector ────────────────────────────────────
        label_y = tab_y2 + 22
        if disk_pct is not None and used_gb is not None and total_gb is not None:
            c.create_text(ncx, label_y,      text=f"{disk_pct:.0f}% used",
                          font=("Arial", 14, "bold"), fill=store_fill, anchor="n")
            c.create_text(ncx, label_y + 34, text=f"{used_gb:.0f} GB used",
                          font=("Arial", 11), fill=t["fg_secondary"], anchor="n")
            c.create_text(ncx, label_y + 58, text=f"{free_gb:.0f} GB free  /  {total_gb:.0f} GB total",
                          font=("Arial", 11), fill=t["fg_secondary"], anchor="n")
        else:
            c.create_text(ncx, label_y, text="Storage: No data",
                          font=("Arial", 13), fill=t["fg_secondary"], anchor="n")


    # ── Remaining methods (unchanged logic) ────────────────────────────────────

    def _apply_preset(self, value: int):
        self.charge_limit_var.set(value)
        self.charge_value_label.config(text=f"{value}%")
        self._draw_gauge(self._cached_capacity, value)
        if self._slide_job:
            self.after_cancel(self._slide_job)
        self._slide_job = self.after(200, self.apply_limit)

    def _draw_ticks(self, event=None):
        from ui import themes
        t = themes.get()
        c = self._ticks_canvas
        c.configure(bg=t["bg"])
        c.delete("all")
        w = c.winfo_width()
        if w <= 1:
            return
        half_slider = 15
        inset = half_slider + 14
        trough_width = w - 2 * inset
        def pct_to_x(pct):
            return inset + (pct - 20) / 80.0 * trough_width
        fg = t["fg_secondary"]
        c.create_text(pct_to_x(20),  14, text="20%",  font=("Arial", 9), fill=fg, anchor="center")
        c.create_text(pct_to_x(60),  14, text="60%",  font=("Arial", 9), fill=fg, anchor="center")
        c.create_text(pct_to_x(100), 14, text="100%", font=("Arial", 9), fill=fg, anchor="center")

    def _redraw_health_bar(self):
        from ui import themes
        t = themes.get()
        self.health_bar_canvas.configure(bg=t["battery_health_track"])
        try:
            hp = float(self.health_pct_label.cget("text").replace("%", "").split()[0])
        except Exception:
            return
        self._draw_health_bar(hp)

    def _draw_health_bar(self, health_pct):
        from ui import themes
        t = themes.get()
        c = self.health_bar_canvas
        c.delete("all")
        w = c.winfo_width() or 440
        h = 22
        c.create_rectangle(0, 0, w, h, fill=t["battery_health_track"], outline="")
        color = (t["battery_fill_high"] if health_pct >= 80
                 else t["battery_fill_mid"] if health_pct >= 60
                 else t["battery_fill_low"])
        c.create_rectangle(0, 0, int(w * health_pct / 100), h, fill=color, outline="")
        for pct in (20, 40, 60, 80):
            x = int(w * pct / 100)
            c.create_line(x, 0, x, h, fill=t["battery_gauge_bg"], width=2)

    def _health_rating(self, health_pct) -> str:
        if   health_pct >= 90: return "✓ Excellent — minimal wear, battery is in great shape"
        elif health_pct >= 80: return "✓ Good — normal wear, no action needed"
        elif health_pct >= 65: return "✓ Normal — moderate wear, runtime slightly reduced"
        elif health_pct >= 50: return "⚠ Worn — noticeably shorter runtime, plan for replacement"
        elif health_pct >= 35: return "⚠ Replace soon — capacity is significantly reduced"
        else:                  return "✗ Replace now — battery is severely degraded"

    def on_slide(self, value):
        val = int(float(value))
        self.charge_value_label.config(text=f"{val}%")
        self._draw_gauge(self._cached_capacity, val)
        if self._slide_job:
            self.after_cancel(self._slide_job)
        self._slide_job = self.after(200, self.apply_limit)

    def get_state(self):
        return {"charge_limit": self.charge_limit_var.get()}

    def load_state(self, data):
        if "charge_limit" in data:
            self.charge_limit_var.set(data["charge_limit"])
            self.charge_value_label.config(text=f"{self.charge_limit_var.get()}%")
            self.apply_limit()

    def apply_limit(self):
        if not self.app.backend:
            if not getattr(self.app, 'is_loading', False):
                show_message(self.app.root, "Unavailable", "Backend not available, battery limit not supported.")
            return
        try:
            self.app.backend.set_battery_charge_limit(self.charge_limit_var.get())
            self.app.status_var.set(f"Battery charge limit set to {self.charge_limit_var.get()}%")
            self.app.save_config()
            self.update_status()
        except BackendError as exc:
            if not getattr(self.app, 'is_loading', False):
                show_message(self.app.root, "Error", f"Battery limit failed:\n\n{exc}")

    def _retheme_all(self, widget, t):
        """Recursively re-apply bg (never fg) to plain tk widgets."""
        try:
            wclass = widget.winfo_class()
        except Exception:
            return
        if wclass.startswith("T"):
            for child in widget.winfo_children():
                self._retheme_all(child, t)
            return
        try:
            if wclass == "Frame":
                bg = t["battery_gauge_bg"] if widget is self._gauge_frame else t["bg"]
                widget.configure(bg=bg)
            elif wclass == "Label":
                widget.configure(bg=t["bg"])
                # Do NOT override fg here — fg is set by data-driven methods
            elif wclass == "Scale":
                widget.configure(bg=t["scale_bg"], fg=t["scale_fg"],
                                 troughcolor=t["scale_trough"],
                                 activebackground=t["scale_active"],
                                 highlightbackground=t["scale_bg"],
                                 highlightcolor=t["scale_bg"])
            elif wclass == "Button":
                widget.configure(bg=t["btn_bg"], fg=t["btn_fg"])
        except Exception:
            pass
        for child in widget.winfo_children():
            self._retheme_all(child, t)

    def apply_theme(self):
        from ui import themes
        t = themes.get()

        # Re-apply bg to all plain tk widgets (never fg — that's data-driven)
        self._retheme_all(self, t)

        # Canvas backgrounds
        self.gauge_canvas.configure(bg=t["battery_gauge_bg"])
        self.health_bar_canvas.configure(bg=t["battery_health_track"])
        self._ticks_canvas.configure(bg=t["bg"])

        # Data-driven fg overrides for static labels
        self.capacity_label.configure(fg=t["battery_pct_fg"])
        self.charge_value_label.configure(fg=t["battery_pct_fg"])
        self._health_title_lbl.configure(fg=t["fg"])
        self._ssd_title_lbl.configure(fg=t["fg"])
        self._charge_limit_title_lbl.configure(fg=t["fg"], bg=t["bg"])
        self._charge_limit_desc_lbl.configure(fg=t["fg_secondary"], bg=t["bg"])

        # Battery stat columns (Design Capacity, Voltage, etc.)
        for (col, caption, value_lbl) in self._stat_col_frames:
            col.configure(bg=t["bg"])
            caption.configure(fg=t["fg_secondary"], bg=t["bg"])
            value_lbl.configure(fg=t["fg"], bg=t["bg"])

        self.health_rating_label.configure(fg=t["fg_secondary"], bg=t["bg"])

        # Preset row
        self._preset_row.configure(bg=t["scale_bg"])
        for btn in self._preset_buttons:
            btn.configure(fg=t["btn_fg"], bg=t["btn_bg"])

        # Redraw canvases
        self._redraw_health_bar()
        self._draw_ticks()

        # Re-fetch and redraw SSD panels fully so stats survive theme change
        self._refresh_ssd()

        # Redraw NVMe icon + battery
        self._draw_gauge(self._cached_capacity, self.charge_limit_var.get())

        # Refresh live battery data labels
        self.update_status()

    def _get_cached_drive_data(self):
        """Return minimal drive dicts from cached widget refs for theme-only updates."""
        result = []
        for dev, refs in self._ssd_drive_widgets.items():
            # Extract health/rating from stored labels so _update_ssd_drive_panel
            # can re-colour without re-fetching SMART data
            hp_text = refs.get("health_pct_lbl", None)
            hp = None
            if hp_text and hp_text.winfo_exists():
                try:
                    hp = float(hp_text.cget("text").split("%")[0])
                except Exception:
                    pass
            result.append({"device": dev, "health_pct": hp})
        return result

    def update_status(self):
        from ui import themes
        t = themes.get()
        info = self.app.backend.get_battery_info() if self.app.backend else {}
        cap  = info.get("capacity")
        if cap is not None:
            cap = int(cap)
            self._cached_capacity = cap
            self.capacity_label.config(text=f"{cap}%", fg=t["battery_pct_fg"])
            status = info.get("status", "Unknown")
            if   "Charging"    in status: status_fg = t["status_green"]
            elif "Discharging" in status: status_fg = t["battery_charge_line"]
            elif "Full"        in status: status_fg = t["battery_pct_fg"]
            else:                         status_fg = t["fg"]
            self.status_label.config(text=status, fg=status_fg)
        else:
            cap = 0
            self._cached_capacity = 0
            self.capacity_label.config(text="--%", fg=t["fg_muted"])
            self.status_label.config(text="Unavailable", fg=t["fg_muted"])

        self._draw_gauge(cap, self.charge_limit_var.get())

        health_pct = info.get("health_pct")
        if health_pct is not None:
            hp = float(health_pct)
            h_color = (t["battery_fill_high"] if hp >= 80
                       else t["battery_fill_mid"] if hp >= 60
                       else t["battery_fill_low"])
            self.health_pct_label.config(text=f"{hp:.1f}%", fg=h_color)
            self._draw_health_bar(hp)
            self.health_rating_label.config(text=self._health_rating(hp), fg=h_color)
        else:
            self.health_pct_label.config(text="–", fg=t["fg_muted"])
            self.health_rating_label.config(text="Health data unavailable", fg=t["fg_muted"])

        def _to_mah(val_str):
            try:  return f"{int(val_str) // 1000} mAh"
            except Exception:  return "–"

        self._design_cap_lbl.config(text=_to_mah(info.get("charge_full_design")) if info.get("charge_full_design") else "–")
        self._current_cap_lbl.config(text=_to_mah(info.get("charge_full")) if info.get("charge_full") else "–")
        wear_pct = info.get("wear_pct")
        self._wear_lbl.config(text=f"{wear_pct:.1f}%" if wear_pct is not None else "–")

        cycle_count = info.get("cycle_count")
        try:
            cc = int(cycle_count) if cycle_count is not None else None
            self._cycles_lbl.config(text=str(cc) if cc is not None else "N/A")
        except Exception:
            self._cycles_lbl.config(text="N/A")

        voltage_now = info.get("voltage_now")
        try:
            v = int(voltage_now) / 1_000_000 if voltage_now else None
            self._voltage_lbl.config(text=f"{v:.2f} V" if v else "–")
        except Exception:
            self._voltage_lbl.config(text="–")

        paths = info.get("paths", [])
        self.battery_info.config(text=f"Device: {paths[0].split('/')[-1]}" if paths else "Device: unknown")

        if not self._ssd_container.winfo_children() and not self._ssd_drive_widgets:
            self.after(200, self._refresh_ssd)
