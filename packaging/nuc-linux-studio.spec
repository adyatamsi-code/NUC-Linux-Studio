Name:           nuc-linux-studio
Version:        2.0
Release:        1%{?dist}
Summary:        Intel NUC X15 Laptop Hardware Control Suite
License:        GPL-2.0
URL:            https://github.com/adriansandru/nuc-linux-studio

BuildRequires:  kernel-devel
Requires:       dkms
Requires:       python3
Requires:       python3-evdev
Requires:       python3-pyusb
Requires:       python3-tkinter
Requires:       kernel-devel

%description
A complete hardware control suite for the Intel NUC X15 Laptop Kit,
providing fan control, power profile management, keyboard RGB lighting,
touchpad toggle, lightbar control, and battery health management.

Includes:
- nuc_wmi kernel module (DKMS)
- Touchpad LED/toggle daemon
- Keyboard brightness daemon
- Fan curve persistence daemon
- Battery boot-time charge limit service
- On-demand audio-reactive keyboard daemon (kbd-audio — started/stopped by app)
- Tkinter control panel application

Not packaged (development/documentation only):
- tools/   — hardware probing and test scripts
- docs/    — architecture and agent documentation
- backup/  — session backups
- tests/   — automated tests

%install
# Driver source for DKMS
mkdir -p %{buildroot}/usr/src/nuc_wmi-%{version}
install -m 644 driver/*.c %{buildroot}/usr/src/nuc_wmi-%{version}/
install -m 644 driver/*.h %{buildroot}/usr/src/nuc_wmi-%{version}/
install -m 644 driver/Makefile %{buildroot}/usr/src/nuc_wmi-%{version}/
install -m 644 driver/dkms.conf %{buildroot}/usr/src/nuc_wmi-%{version}/

# App files
mkdir -p %{buildroot}/opt/%{name}
cp -r ui %{buildroot}/opt/%{name}/
cp -r backend %{buildroot}/opt/%{name}/
install -m 755 cli.py %{buildroot}/opt/%{name}/

# Systemd services
mkdir -p %{buildroot}/usr/lib/systemd/system
cat > %{buildroot}/usr/lib/systemd/system/touchpad-led.service << 'EOF'
[Unit]
Description=NUC X15 Touchpad LED & Toggle Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/nuc-linux-studio/backend/touchpad_daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > %{buildroot}/usr/lib/systemd/system/kbd-brightness.service << 'EOF'
[Unit]
Description=NUC X15 Keyboard Brightness Daemon
After=multi-user.target systemd-udev-settle.service local-fs.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/nuc-linux-studio/backend/kbd_brightness_daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > %{buildroot}/usr/lib/systemd/system/fan-curve.service << 'EOF'
[Unit]
Description=NUC X15 Fan Curve Persistence Daemon
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/nuc-linux-studio/backend/fan_curve_daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Desktop entry
mkdir -p %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/share/applications/%{name}.desktop << 'EOF'
[Desktop Entry]
Name=NUC Linux Studio
Comment=Intel NUC X15 Hardware Control
Exec=pkexec /usr/bin/python3 /opt/nuc-linux-studio/ui/main.py
Icon=preferences-system
Terminal=false
Type=Application
Categories=System;Settings;HardwareSettings;
EOF

# Launcher script
mkdir -p %{buildroot}/usr/local/bin
cat > %{buildroot}/usr/local/bin/nuc-studio << 'LAUNCHER'
#!/bin/bash
exec pkexec /usr/bin/python3 /opt/nuc-linux-studio/ui/main.py "$@"
LAUNCHER
chmod +x %{buildroot}/usr/local/bin/nuc-studio

%post
dkms add -m nuc_wmi -v %{version} 2>/dev/null || true
dkms build -m nuc_wmi -v %{version} || true
dkms install -m nuc_wmi -v %{version} || true
modprobe nuc_wmi 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now touchpad-led.service 2>/dev/null || true
systemctl enable --now kbd-brightness.service 2>/dev/null || true
systemctl enable --now fan-curve.service 2>/dev/null || true
systemctl enable --now nuc-battery-limit.service 2>/dev/null || true
# kbd-audio.service is intentionally NOT enabled — on-demand, started by app when audio effect selected

%preun
systemctl disable --now touchpad-led.service 2>/dev/null || true
systemctl disable --now kbd-brightness.service 2>/dev/null || true
systemctl disable --now fan-curve.service 2>/dev/null || true
systemctl stop kbd-audio.service 2>/dev/null || true
systemctl disable kbd-audio.service 2>/dev/null || true
systemctl disable --now nuc-battery-limit.service 2>/dev/null || true
rmmod nuc_wmi 2>/dev/null || true
dkms remove nuc_wmi/%{version} --all 2>/dev/null || true

%files
/usr/src/nuc_wmi-%{version}
/opt/%{name}
/usr/lib/systemd/system/touchpad-led.service
/usr/lib/systemd/system/kbd-brightness.service
/usr/lib/systemd/system/fan-curve.service
/usr/lib/systemd/system/kbd-audio.service
/usr/lib/systemd/system/nuc-battery-limit.service
/usr/share/applications/%{name}.desktop
/usr/local/bin/nuc-studio

%changelog
* Sat May 17 2026 Adrian Sandru <adrian@nuc> - 2.6-1
- kbd-audio.service: on-demand only — not auto-enabled; app starts/stops via systemctl
- Audio daemon: mtime watchdog (30s) + 10s heartbeat touch — self-stops on app crash
- install.sh: --no-driver flag for fast redeploy (skip DKMS build)
- uninstall.sh: fixed duplicate log(), version variable, nuc-battery-limit cleanup
- requirements.txt: removed stale ite8291r3-ctl CLI entry, clarified package vs CLI

* Tue May 13 2026 Adrian Sandru <adrian@nuc> - 2.0-1
- Version 2.0: Dark/Light theme system, lightbar swatch calibration,
  face unlock status theming, mic status theming, per-tab apply_theme
- Full theme toggle (dark indigo/gold ↔ light ivory/sky-blue)
- Lightbar swatches remapped to physical LED output (R+G only, blue dead)
- Status indicator colors: neon green (dark) / grass green (light)

* Tue May 06 2026 Adrian Sandru <adrian@nuc> - 1.0-1
- Initial RPM package
- nuc_wmi DKMS driver, touchpad/kbd daemons, control panel app
