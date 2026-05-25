#!/bin/bash
set -e

# NUC Linux Studio - Local Install Script
# Installs driver (DKMS), app, daemons, and services

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="nuc-linux-studio"
VERSION="2.0"
INSTALL_DIR="/opt/${APP_NAME}"
DKMS_SRC="/usr/src/nuc_wmi-${VERSION}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

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

# Fix: UCSI USB-C power supply boot race condition with UPower.
# UPower starts before the UCSI device is fully initialized, gets a NULL
# native path, and enters a GLib assertion failure busy-loop (10-50% CPU).
# This udev rule restarts UPower when the UCSI power supply appears,
# ensuring it re-enumerates with a valid device.
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
After=multi-user.target systemd-udev-settle.service local-fs.target
Wants=systemd-udev-settle.service

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/kbd_brightness_daemon.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /usr/lib/systemd/system/fan-curve.service << EOF
[Unit]
Description=NUC X15 Fan Curve Persistence Daemon
After=multi-user.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u ${INSTALL_DIR}/backend/fan_curve_daemon.py
Restart=always
RestartSec=3

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
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create persistent state directory
mkdir -p /var/lib/nuc-linux-studio

# Remove stale service overrides from previous manual installs
rm -f /etc/systemd/system/touchpad-led.service
rm -f /etc/systemd/system/kbd-brightness.service
rm -f /etc/systemd/system/fan-curve.service
rm -f /etc/systemd/system/kbd-audio.service

# Enable and start services
systemctl daemon-reload
systemctl enable touchpad-led.service kbd-brightness.service fan-curve.service kbd-audio.service
systemctl restart touchpad-led.service kbd-brightness.service fan-curve.service kbd-audio.service

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

cat > /usr/share/applications/nuc-linux-studio.desktop << 'EOF'
[Desktop Entry]
Name=NUC Linux Studio
Comment=Intel NUC X15 Hardware Control
Exec=/usr/local/bin/nuc-studio
Icon=nuc-linux-studio
Terminal=false
Type=Application
Categories=System;Settings;HardwareSettings;
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

