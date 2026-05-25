#!/bin/bash
set -e

# NUC Linux Studio - Uninstall Script

VERSION="2.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }

# Release fan control back to EC before stopping the daemon
release_fan_control() {
    for platform in nuc_wmi qc71_laptop; do
        manual="/sys/devices/platform/${platform}/manual_control"
        hwmon_base="/sys/devices/platform/${platform}/hwmon"
        if [[ -f "$manual" ]]; then
            echo 0 > "$manual" 2>/dev/null || true
        fi
        if [[ -d "$hwmon_base" ]]; then
            for hwmon in "$hwmon_base"/hwmon*; do
                [[ -f "$hwmon/pwm1_enable" ]] && echo 0 > "$hwmon/pwm1_enable" 2>/dev/null || true
                [[ -f "$hwmon/pwm2_enable" ]] && echo 0 > "$hwmon/pwm2_enable" 2>/dev/null || true
            done
        fi
    done
}

log "Releasing fan control to EC..."
release_fan_control

log "Stopping services..."
systemctl disable --now touchpad-led.service 2>/dev/null || true
systemctl disable --now kbd-brightness.service 2>/dev/null || true
systemctl disable --now fan-curve.service 2>/dev/null || true
systemctl stop kbd-audio.service 2>/dev/null || true
systemctl disable kbd-audio.service 2>/dev/null || true
systemctl disable --now nuc-battery-limit.service 2>/dev/null || true

# Stop and disable OSD user service
REAL_USER=$(logname 2>/dev/null || echo "")
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    REAL_UID=$(id -u "$REAL_USER")
    sudo -u "$REAL_USER" \
        XDG_RUNTIME_DIR="/run/user/${REAL_UID}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${REAL_UID}/bus" \
        systemctl --user disable --now nuc-osd.service 2>/dev/null || true
fi

log "Unloading driver..."
rmmod nuc_wmi 2>/dev/null || true

log "Removing DKMS module..."
dkms remove nuc_wmi/${VERSION} --all 2>/dev/null || true

log "Removing files..."
rm -rf /usr/src/nuc_wmi-${VERSION}
rm -rf /opt/nuc-linux-studio
rm -f /usr/lib/systemd/system/touchpad-led.service
rm -f /usr/lib/systemd/system/kbd-brightness.service
rm -f /usr/lib/systemd/system/fan-curve.service
rm -f /usr/lib/systemd/system/kbd-audio.service
rm -f /usr/lib/systemd/system/nuc-battery-limit.service
rm -f /usr/lib/systemd/user/nuc-osd.service
rm -f /etc/xdg/autostart/nuc-osd.desktop
rm -f /usr/share/applications/nuc-studio.desktop
rm -f /usr/share/applications/nuc-linux-studio.desktop
rm -f /usr/share/polkit-1/actions/org.nuc-linux-studio.policy
rm -f /usr/local/bin/nuc-studio
rm -f /etc/udev/rules.d/99-nuc-ucsi-upower-fix.rules
rm -f /etc/udev/rules.d/99-ite8291r3.rules
rm -f /etc/modprobe.d/nuc-studio.conf
rm -rf /var/lib/nuc-linux-studio

systemctl daemon-reload

log "NUC Linux Studio uninstalled."
