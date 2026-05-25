#!/bin/bash
# NUC Linux Studio - Quick deploy script
set -e

SRC="/home/adriansandru/Downloads/Project-nuc"
DEST="/opt/nuc-linux-studio"

echo "=== Deploying NUC Linux Studio ==="

echo "Copying backend files..."
sudo cp "$SRC/backend/__init__.py" "$DEST/backend/"
sudo cp "$SRC/backend/audio_daemon.py" "$DEST/backend/"
sudo cp "$SRC/backend/battery.py" "$DEST/backend/"
sudo cp "$SRC/backend/battery_limit_apply.py" "$DEST/backend/"
sudo cp "$SRC/backend/core.py" "$DEST/backend/"
sudo cp "$SRC/backend/facade.py" "$DEST/backend/"
sudo cp "$SRC/backend/fan_curve_daemon.py" "$DEST/backend/"
sudo cp "$SRC/backend/fans.py" "$DEST/backend/"
sudo cp "$SRC/backend/kbd_brightness_daemon.py" "$DEST/backend/"
sudo cp "$SRC/backend/keyboard.py" "$DEST/backend/"
sudo cp "$SRC/backend/osd.py" "$DEST/backend/"
sudo cp "$SRC/backend/power.py" "$DEST/backend/"
sudo cp "$SRC/backend/touchpad_daemon.py" "$DEST/backend/"
sudo cp "$SRC/backend/usb_utils.py" "$DEST/backend/"
sudo cp "$SRC/ui/tabs/keyboard.py" "$DEST/ui/tabs/"

echo "Installing OSD autostart..."
sudo mkdir -p /etc/xdg/autostart
sudo cp "$SRC/packaging/nuc-osd.desktop" /etc/xdg/autostart/nuc-osd.desktop

echo "Clearing Python cache..."
sudo find "$DEST" -name "*.pyc" -delete 2>/dev/null || true
sudo find "$DEST" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "Restarting daemons..."
sudo systemctl restart kbd-audio.service touchpad-led.service kbd-brightness.service

echo "Restarting upower (clears stale sysfs fds that cause CPU hog)..."
sudo systemctl restart upower.service

echo "Re-applying battery charge limit..."
sudo /usr/bin/python3 /opt/nuc-linux-studio/backend/battery_limit_apply.py

# Kill any existing OSD and restart it as the user
pkill -f "python3.*osd.py" 2>/dev/null || true
sleep 1

# Kill any existing OSD and restart it as the user
pkill -9 -f "python3.*osd.py" 2>/dev/null || true
sleep 1

echo "Starting OSD for user $REAL_USER (uid=$REAL_UID)..."
setsid sudo -u "$REAL_USER" env \
    GDK_BACKEND=x11 \
    DISPLAY=:0 \
    XDG_RUNTIME_DIR=/run/user/${REAL_UID} \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${REAL_UID}/bus \
    /usr/bin/python3 /opt/nuc-linux-studio/backend/osd.py > /tmp/nuc-osd.log 2>&1 &

sleep 3

echo ""
echo "=== Service Status ==="
sudo systemctl status kbd-audio.service touchpad-led.service kbd-brightness.service --no-pager -l | grep -E "Active:|python3|started|error|failed" | head -20

echo ""
echo "=== OSD Status ==="
if pgrep -f "python3.*osd.py" > /dev/null; then
    echo "OSD running (PID: $(pgrep -f 'python3.*osd.py'))"
else
    echo "OSD NOT running! Check /tmp/nuc-osd.log"
fi

echo ""
echo "=== Done ==="

