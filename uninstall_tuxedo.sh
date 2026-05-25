#!/bin/bash
# Comprehensive uninstaller for TUXEDO Control Center on Fedora/Linux

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[!] Beginning comprehensive uninstallation of TUXEDO Control Center...${NC}"

# 1. Stop and disable systemd services
echo -e "\n${GREEN}[+] Stopping TUXEDO systemd services...${NC}"
for svc in tccd.service tccd-sleep.service tuxedod.service tuxedo-keyboard.service; do
    sudo systemctl stop "$svc" 2>/dev/null
    sudo systemctl disable "$svc" 2>/dev/null
done

# 2. Unload kernel modules
echo -e "\n${GREEN}[+] Unloading TUXEDO kernel modules...${NC}"
for mod in tuxedo_keyboard tuxedo_io tuxedo_compatibility_check tuxedo_nb05_keyboard tuxedo_nb05_power_profiles tuxedo_nb05_sensors tuxedo_nb05_ec tuxedo_nb04_keyboard tuxedo_nb04_wmi_ab tuxedo_nb04_wmi_bs; do
    sudo rmmod "$mod" 2>/dev/null
done

# 3. Try removing packages via DNF (if installed via package manager)
echo -e "\n${GREEN}[+] Attempting to remove RPM packages via DNF...${NC}"
sudo dnf remove -y tuxedo-control-center tuxedo-keyboard tuxedo-drivers tuxedo-suite 2>/dev/null

# 4. Remove DKMS modules if left behind
echo -e "\n${GREEN}[+] Removing TUXEDO DKMS modules...${NC}"
if command -v dkms &> /dev/null; then
    dkms status 2>/dev/null | grep -i "tuxedo" | while IFS=',' read -r name_ver rest; do
        mod=$(echo "$name_ver" | xargs)
        sudo dkms remove "$mod" --all 2>/dev/null
    done
fi

# 5. Remove leftover DKMS source directories
echo -e "\n${GREEN}[+] Removing DKMS source directories...${NC}"
sudo rm -rf /usr/src/tuxedo-keyboard-* /usr/src/tuxedo-drivers-*

# 6. Remove physical installation directories
echo -e "\n${GREEN}[+] Removing installation files from /opt/...${NC}"
sudo rm -rf /opt/tuxedo-control-center

# 7. Remove system-wide systemd and dbus configs
echo -e "\n${GREEN}[+] Removing systemd and DBus configurations...${NC}"
for f in tccd.service tccd-sleep.service tuxedod.service tuxedo-keyboard.service; do
    sudo rm -f "/etc/systemd/system/$f"
    sudo rm -f "/lib/systemd/system/$f"
    sudo rm -f "/usr/lib/systemd/system/$f"
done
sudo rm -f /etc/dbus-1/system.d/com.tuxedocomputers.tccd.conf
sudo rm -f /etc/modules-load.d/tuxedo-keyboard.conf
sudo rm -f /etc/modprobe.d/tuxedo-keyboard.conf

# 8. Remove Desktop Shortcuts
echo -e "\n${GREEN}[+] Removing desktop shortcuts...${NC}"
sudo rm -f /usr/share/applications/tuxedo-control-center.desktop
sudo rm -f /usr/share/applications/tuxedo-suite.desktop
rm -f ~/.local/share/applications/tuxedo-control-center.desktop
rm -f ~/.local/share/applications/tuxedo-suite.desktop
rm -f ~/.config/autostart/tuxedo-control-center.desktop
rm -f ~/.config/autostart/tuxedo-suite.desktop

# 9. Remove User Configurations
echo -e "\n${GREEN}[+] Removing user configuration files...${NC}"
rm -rf ~/.config/tuxedo-control-center
sudo rm -rf /etc/tuxedo-control-center
sudo rm -rf /etc/tuxedo

# 10. Remove any leftover tuxedo repos
echo -e "\n${GREEN}[+] Removing TUXEDO DNF repositories...${NC}"
sudo rm -f /etc/yum.repos.d/tuxedo*.repo

# 11. Reload systemd daemon
echo -e "\n${GREEN}[+] Reloading systemd...${NC}"
sudo systemctl daemon-reload

# 12. Verify
echo -e "\n${GREEN}[+] Verifying cleanup...${NC}"
REMAINING=$(rpm -qa 2>/dev/null | grep -i tuxedo)
if [ -n "$REMAINING" ]; then
    echo -e "${RED}[!] Warning: These TUXEDO packages are still installed:${NC}"
    echo "$REMAINING"
else
    echo -e "${GREEN}    No TUXEDO packages remain.${NC}"
fi

echo -e "\n${GREEN}[✔] TUXEDO Control Center has been successfully removed.${NC}"
