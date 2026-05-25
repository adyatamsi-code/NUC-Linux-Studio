#!/bin/bash
# systemd sleep hook: /usr/lib/systemd/system-sleep/nuc-touchpad-resume.sh
# Signals the touchpad daemon immediately on resume by writing a trigger file.
# The daemon polls for this file and reacts faster than suspend_stats polling.

case "$1" in
    post)
        # Create trigger file that daemon watches
        echo "$(date +%s)" > /tmp/nuc_touchpad_resume_trigger
        ;;
esac
