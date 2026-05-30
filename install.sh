#!/bin/bash
set -e

# NUC Linux Studio - Local Install Script
# Installs driver (DKMS), app, daemons, and services
#
# Usage:
#   sudo ./install.sh              — full install (DKMS build + app + services)
#   sudo ./install.sh --no-driver  — fast redeploy (app + services only, skip DKMS)
#
# NOT installed to /opt/ (dev/docs only — never packaged):
#   tools/   docs/   backup/   tests/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="nuc-linux-studio"
VERSION="2.0"
INSTALL_DIR="/opt/${APP_NAME}"
DKMS_SRC="/usr/src/nuc_wmi-${VERSION}"
SKIP_DRIVER=0

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --no-driver) SKIP_DRIVER=1 ;;
        *) ;;
    esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# Release fan control back to EC firmware
release_fan_control() {
    for platform in nuc_wmi qc71_laptop; do
        manual="/sys/devices/platform/${platform}/manual_control"
        hwmon_base="/sys/devices/platform/${platform}/hwmon"
        if [[ -f "$manual" ]]; then
            echo 0 > "$manual" 2>/dev/null && log "Fan control released to EC (${platform})" || true
        fi
        if [[ -d "$hwmon_base" ]]; then
            for hwmon in "$hwmon_base"/hwmon*; do
                [[ -f "$hwmon/pwm1_enable" ]] && echo 0 > "$hwmon/pwm1_enable" 2>/dev/null || true
                [[ -f "$hwmon/pwm2_enable" ]] && echo 0 > "$hwmon/pwm2_enable" 2>/dev/null || true
            done
        fi
    done
}

# Check root
[[ $EUID -ne 0 ]] && err "This script must be run as root (sudo ./install.sh)"

# Check dependencies
log "Checking dependencies..."
for cmd in python3 make dkms; do
    command -v $cmd &>/dev/null || err "Missing dependency: $cmd"
done

# Check kernel headers
KVER=$(uname -r)
[[ -d "/usr/src/kernels/${KVER}" ]] || [[ -d "/lib/modules/${KVER}/build" ]] || \
    err "Kernel headers not found for ${KVER}. Install kernel-devel."

# Install Python dependencies
log "Installing Python dependencies..."
pip3 install evdev 2>/dev/null || dnf install -y python3-evdev 2>/dev/null || true

# ite8291r3 keyboard backlight is now handled by the kernel module — no external tool needed

if [[ "$SKIP_DRIVER" == "1" ]]; then
    log "Skipping DKMS driver build (--no-driver flag set)"
else
    # Remove old DKMS module if present
    if dkms status nuc_wmi/${VERSION} &>/dev/null; then
        log "Removing old DKMS module..."
        dkms remove nuc_wmi/${VERSION} --all 2>/dev/null || true
    fi

    # Unload old driver
    if lsmod | grep -q nuc_wmi; then
        log "Unloading existing nuc_wmi module..."
        rmmod nuc_wmi 2>/dev/null || true
    fi

    # Install DKMS source
    log "Installing DKMS source to ${DKMS_SRC}..."
    rm -rf "${DKMS_SRC}"
    mkdir -p "${DKMS_SRC}"
    cp "${SCRIPT_DIR}"/driver/*.c "${DKMS_SRC}/"
    cp "${SCRIPT_DIR}"/driver/*.h "${DKMS_SRC}/"
    cp "${SCRIPT_DIR}"/driver/Makefile "${DKMS_SRC}/"
    cp "${SCRIPT_DIR}"/driver/dkms.conf "${DKMS_SRC}/"

    # Build and install via DKMS
    log "Building driver via DKMS..."
    dkms add -m nuc_wmi -v ${VERSION}
    dkms build -m nuc_wmi -v ${VERSION}
    dkms install -m nuc_wmi -v ${VERSION}

    # Blacklist conflicting modules (nuc_wmi replaces qc71_laptop)
    log "Blacklisting conflicting modules..."
    cat > /etc/modprobe.d/nuc-studio.conf << EOF
blacklist qc71_laptop
blacklist asus_wmi
blacklist uniwill_laptop
EOF
    rmmod qc71_laptop 2>/dev/null || true
    rmmod asus_wmi 2>/dev/null || true
    rmmod uniwill_laptop 2>/dev/null || true

    # Load the driver
    log "Loading nuc_wmi module..."
    modprobe nuc_wmi || insmod "/lib/modules/${KVER}/extra/nuc_wmi.ko" 2>/dev/null || true

    # Load ite8291r3 keyboard backlight driver
    log "Loading ite8291r3 module..."
    modprobe ite8291r3 || insmod "/lib/modules/${KVER}/extra/ite8291r3.ko" 2>/dev/null || true

    # Install udev rules for ITE8291R3 auto-bind and permissions
    log "Installing udev rules..."
    cp "${SCRIPT_DIR}/driver/99-ite8291r3.rules" /etc/udev/rules.d/
fi

# Install udev rules and UPower fix (driver-related, skip when --no-driver)
if [[ "$SKIP_DRIVER" != "1" ]]; then
    # Fix: UCSI USB-C power supply boot race condition with UPower.
    log "Installing UPower UCSI workaround..."
    cat > /etc/udev/rules.d/99-nuc-ucsi-upower-fix.rules << 'EOF'
# NUC X15: Restart UPower after UCSI USB-C power supply fully initializes.
# Fixes boot race where UPower sees the device before native-path is set,
# causing "instance with invalid (NULL) class pointer" assertion loop.
SUBSYSTEM=="power_supply", ACTION=="change", ATTR{type}=="USB", DEVPATH=="*USBC*", RUN+="/usr/bin/systemctl restart upower.service"
EOF

    udevadm control --reload-rules
    udevadm trigger

    # Restart UPower so it drops the broken device
    systemctl restart upower 2>/dev/null || true

    # Bind ite8291r3 to the device now (in case udev hasn't triggered yet)
    for dev in /sys/bus/usb/devices/*; do
        if [[ -f "$dev/idVendor" ]] && [[ "$(cat "$dev/idVendor" 2>/dev/null)" == "048d" ]]; then
            devname=$(basename "$dev")
            echo "${devname}:1.1" > /sys/bus/usb/drivers/ite8291r3/bind 2>/dev/null || true
        fi
    done
fi

# Stop kbd-audio before copying app files — prevents holding USB device open during deploy
# (kbd-audio is on-demand only; the app starts/stops it when audio effect is selected)
log "Stopping audio daemon before deploy (if running)..."
systemctl stop kbd-audio.service 2>/dev/null || true

# Install app files
log "Installing app to ${INSTALL_DIR}..."
rm -rf "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cp -r "${SCRIPT_DIR}/ui" "${INSTALL_DIR}/"
cp -r "${SCRIPT_DIR}/backend" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/cli.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/setup.py" "${INSTALL_DIR}/" 2>/dev/null || true

# Clear Python bytecode cache to ensure fresh code is used
log "Clearing Python cache..."
find "${INSTALL_DIR}" -name "*.pyc" -delete 2>/dev/null || true
find "${INSTALL_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${SCRIPT_DIR}" -name "*.pyc" -delete 2>/dev/null || true
find "${SCRIPT_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install systemd services
log "Installing systemd services..."
cat > /usr/lib/systemd/system/touchpad-led.service << EOF
[Unit]
Description=NUC X15 Touchpad LED & Toggle Daemon
After=multi-user.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/touchpad_daemon.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /usr/lib/systemd/system/kbd-brightness.service << EOF
[Unit]
Description=NUC X15 Keyboard Brightness Daemon
After=multi-user.target systemd-udev-settle.service local-fs.target dev-bus-usb.device
Wants=systemd-udev-settle.service dev-bus-usb.device

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/kbd_brightness_daemon.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /usr/lib/systemd/system/fan-curve.service << EOF
[Unit]
Description=NUC X15 Fan Curve Persistence Daemon
After=multi-user.target systemd-udev-settle.service
Wants=systemd-udev-settle.service

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/fan_curve_daemon.py
ExecStop=/bin/bash -c 'for p in nuc_wmi qc71_laptop; do f=/sys/devices/platform/\$p/manual_control; [ -f "\$f" ] && echo 0 > "\$f"; for h in /sys/devices/platform/\$p/hwmon/hwmon*; do [ -f "\$h/pwm1_enable" ] && echo 0 > "\$h/pwm1_enable"; [ -f "\$h/pwm2_enable" ] && echo 0 > "\$h/pwm2_enable"; done; done'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /usr/lib/systemd/system/kbd-audio.service << EOF
[Unit]
Description=NUC X15 Keyboard Audio Reactive Daemon
After=multi-user.target pipewire.service pulseaudio.service

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/audio_daemon.py
Restart=on-failure
RestartSec=3
# No [Install] section — this service is on-demand only.
# Started/stopped by the app via: systemctl start/stop kbd-audio.service
# Never run: systemctl enable kbd-audio.service
EOF

cat > /usr/lib/systemd/system/nuc-battery-limit.service << EOF
[Unit]
Description=NUC X15 Battery Charge Limit (apply saved setting at boot)
# Must run after power-profiles-daemon so we override whatever profile it sets
After=multi-user.target power-profiles-daemon.service
Wants=power-profiles-daemon.service

[Service]
Type=oneshot
# Short delay to let power-profiles-daemon finish its own startup writes
ExecStartPre=/bin/sleep 2
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/backend/battery_limit_apply.py
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Install systemd-sleep hook — releases fan control before suspend so the EC
# doesn't fight stale PWM values on resume (fans at full blast after wake).
log "Installing fan-curve suspend/resume sleep hook..."
mkdir -p /usr/lib/systemd/system-sleep
cp "${SCRIPT_DIR}/packaging/nuc-fan-curve-sleep" /usr/lib/systemd/system-sleep/nuc-fan-curve
chmod +x /usr/lib/systemd/system-sleep/nuc-fan-curve

# Install udev rule to reapply battery limit whenever AC adapter changes state
# (power-profiles-daemon resets charge_control_end_threshold on AC plug/unplug events)
cat > /etc/udev/rules.d/99-nuc-battery-limit.rules << 'UDEV_EOF'
# Reapply saved battery charge limit after AC adapter state changes.
# power-profiles-daemon resets charge_control_end_threshold on these events.
SUBSYSTEM=="power_supply", ATTR{type}=="Mains", ACTION=="change", \
    RUN+="/usr/bin/systemd-run --no-block --unit=nuc-battery-limit-ac.service /usr/bin/python3 /opt/nuc-linux-studio/backend/battery_limit_apply.py"
UDEV_EOF
udevadm control --reload-rules

# Create persistent state directory
mkdir -p /var/lib/nuc-linux-studio

# Remove stale service overrides from previous manual installs
rm -f /etc/systemd/system/touchpad-led.service
rm -f /etc/systemd/system/kbd-brightness.service
rm -f /etc/systemd/system/fan-curve.service
rm -f /etc/systemd/system/kbd-audio.service
rm -f /etc/systemd/system/nuc-battery-limit.service

# Release fan control to EC before restarting the daemon
log "Releasing fan control to EC..."
release_fan_control

# Enable and start services
# NOTE: kbd-audio.service is intentionally NOT enabled or auto-started here.
# It is an on-demand service started/stopped by the app when audio effect is selected.
# Installing the unit file makes `systemctl start kbd-audio` work when needed.
systemctl daemon-reload
systemctl enable touchpad-led.service kbd-brightness.service fan-curve.service nuc-battery-limit.service
systemctl restart touchpad-led.service kbd-brightness.service fan-curve.service
systemctl start nuc-battery-limit.service

# Install .desktop file
log "Installing desktop entry..."
# Install app icon
mkdir -p /usr/share/icons/hicolor/256x256/apps
mkdir -p /usr/share/icons/hicolor/128x128/apps
mkdir -p /usr/share/icons/hicolor/64x64/apps
mkdir -p /usr/share/icons/hicolor/48x48/apps
cp "${SCRIPT_DIR}/ui/assets/inuc_icon.png" /usr/share/icons/hicolor/256x256/apps/nuc-linux-studio.png
cp "${SCRIPT_DIR}/ui/assets/inuc_icon_128.png" /usr/share/icons/hicolor/128x128/apps/nuc-linux-studio.png
cp "${SCRIPT_DIR}/ui/assets/inuc_icon_64.png" /usr/share/icons/hicolor/64x64/apps/nuc-linux-studio.png
cp "${SCRIPT_DIR}/ui/assets/inuc_icon_48.png" /usr/share/icons/hicolor/48x48/apps/nuc-linux-studio.png
gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null || true

cat > /usr/share/applications/nuc-studio.desktop << 'EOF'
[Desktop Entry]
Name=NUC Linux Studio
Comment=NUC X15 hardware control panel
Exec=/usr/local/bin/nuc-studio
Icon=nuc-linux-studio
Terminal=false
Type=Application
Categories=System;Settings;HardwareSettings;
Keywords=nuc;keyboard;battery;fans;lightbar;touchpad;
StartupNotify=true
StartupWMClass=nuc-studio
EOF

# Install launcher script
cat > /usr/local/bin/nuc-studio << 'LAUNCHER'
#!/bin/bash
# Load display env from file if provided
ENV_FILE=""
PASS_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        *)
            PASS_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -n "$ENV_FILE" ]] && [[ -f "$ENV_FILE" ]]; then
    while IFS='=' read -r key value; do
        [[ -n "$key" ]] && [[ -n "$value" ]] && export "$key=$value"
    done < "$ENV_FILE"
fi

# Fallback: detect display from active session
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    export DISPLAY=":0"
    export XDG_RUNTIME_DIR="/run/user/1000"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus"
    for f in /run/user/1000/.mutter-Xwaylandauth.*; do
        [ -f "$f" ] && export XAUTHORITY="$f" && break
    done
fi

# Force dedicated GPU rendering (NVIDIA RTX 3070)
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export __VK_LAYER_NV_optimus=NVIDIA_only

exec /usr/bin/python3 /opt/nuc-linux-studio/ui/main.py "${PASS_ARGS[@]}"
LAUNCHER
chmod +x /usr/local/bin/nuc-studio

# Install polkit rule so the .desktop file can launch without terminal
cat > /usr/share/polkit-1/actions/org.nuc-linux-studio.policy << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.nuc-linux-studio.run">
    <description>Run NUC Linux Studio</description>
    <message>Authentication is required to run NUC Linux Studio</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/bin/nuc-studio</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate>
  </action>
</policyconfig>
EOF

log "============================================"
log "  NUC Linux Studio installed successfully!"
log "============================================"
log ""
log "  Launch:   nuc-studio"
log "  Driver:   modprobe nuc_wmi"
log "  Services: systemctl status touchpad-led kbd-brightness fan-curve"
log ""

# Install OSD as a systemd user unit (runs in the user's graphical session)
log "Installing OSD systemd user unit..."
mkdir -p /usr/lib/systemd/user
cp "${SCRIPT_DIR}/packaging/nuc-osd.service" /usr/lib/systemd/user/nuc-osd.service

# Remove old XDG autostart entry if present
rm -f /etc/xdg/autostart/nuc-osd.desktop

REAL_USER=$(logname 2>/dev/null || echo "")
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    REAL_UID=$(id -u "$REAL_USER")
    # Reload user daemon and enable+start the OSD service in the user's session
    sudo -u "$REAL_USER" \
        XDG_RUNTIME_DIR="/run/user/${REAL_UID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${REAL_UID}/bus" \
        systemctl --user daemon-reload 2>/dev/null || true
    sudo -u "$REAL_USER" \
        XDG_RUNTIME_DIR="/run/user/${REAL_UID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${REAL_UID}/bus" \
        systemctl --user enable nuc-osd.service 2>/dev/null || true
    sudo -u "$REAL_USER" \
        XDG_RUNTIME_DIR="/run/user/${REAL_UID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${REAL_UID}/bus" \
        systemctl --user restart nuc-osd.service 2>/dev/null || true
    log "OSD user service enabled and started for user $REAL_USER"
fi

