#!/bin/bash
# /usr/lib/systemd/system-sleep/nuc-touchpad-sleep.sh
# Forces touchpad ON before suspend to prevent zombie state on resume.
# The daemon will restore the user's desired state after resume.
#
# IMPORTANT: We write /tmp/nuc_touchpad_suspend_suppress BEFORE the HID
# force-ON so the daemon's HID poller ignores the resulting 0x00->0x03
# transition and does NOT misinterpret it as a user double-tap toggle
# (which would corrupt the persistent state file before suspend).

SUPPRESS_FILE=/tmp/nuc_touchpad_suspend_suppress

case "$1" in
    pre)
        # Suppress HID poller BEFORE we touch the hardware
        echo "$(date +%s)" > "$SUPPRESS_FILE"

        # Force touchpad ON before suspend
        echo "nuc-touchpad: forcing ON before suspend" | systemd-cat -t nuc-touchpad

        # Find the touchpad hidraw device
        for hidraw in /sys/class/hidraw/hidraw*; do
            uevent="$hidraw/device/uevent"
            if [ -f "$uevent" ] && grep -q "UNIW0001" "$uevent" 2>/dev/null; then
                dev="/dev/$(basename $hidraw)"
                # Write HID feature report: report_id=7, value=0x03 (ON)
                python3 -c "
import os, fcntl, struct
fd = os.open('$dev', os.O_RDWR | os.O_NONBLOCK)
buf = struct.pack('2B', 7, 0x03)
fcntl.ioctl(fd, 0xc0024806, buf)
os.close(fd)
print('Forced touchpad ON on $dev')
" 2>&1 | systemd-cat -t nuc-touchpad
                break
            fi
        done
        ;;
    post)
        # Remove suppress marker so the HID poller resumes normal operation.
        # The daemon handles full resume state restoration on its own.
        rm -f "$SUPPRESS_FILE"
        ;;
esac
