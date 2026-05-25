#!/usr/bin/env python3
"""Touchpad diagnostic tool - run as root after fresh reboot."""
import os, fcntl, struct, time, subprocess
from pathlib import Path

def HIDIOCSFEATURE(l): return 0xc0004806 | (l << 16)
def HIDIOCGFEATURE(l): return 0xc0004807 | (l << 16)

def find_hidraw():
    base = Path("/sys/class/hidraw")
    for d in base.iterdir():
        uevent = d / "device" / "uevent"
        if uevent.exists() and "UNIW0001" in uevent.read_text():
            return f"/dev/{d.name}"
    return None

def get_report_id(hidraw):
    desc = Path(f"/sys/class/hidraw/{Path(hidraw).name}/device/report_descriptor").read_bytes()
    pattern = bytes([0x05, 0x0d, 0x09, 0x22, 0xa1, 0x00, 0x09, 0x57, 0x09, 0x58])
    idx = desc.find(pattern)
    if idx == -1: return -1
    for i in range(idx + len(pattern), len(desc) - 1):
        if desc[i] == 0x85: return desc[i+1]
    return -1

def read_hid(dev, rid):
    fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
    buf = bytearray(2); buf[0] = rid
    try:
        fcntl.ioctl(fd, HIDIOCGFEATURE(2), buf)
        return buf[1]
    except:
        return None
    finally:
        os.close(fd)

def write_hid(dev, rid, val):
    fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(2), struct.pack('2B', rid, val))
        return True
    except Exception as e:
        print(f"  WRITE FAILED: {e}")
        return False
    finally:
        os.close(fd)

def read_ec():
    for base in ("/sys/devices/platform/nuc_wmi", "/sys/devices/platform/qc71_laptop"):
        p = Path(base) / "touchpad_enabled"
        if p.exists():
            return int(p.read_text().strip())
    return None

def write_ec(val):
    for base in ("/sys/devices/platform/nuc_wmi", "/sys/devices/platform/qc71_laptop"):
        p = Path(base) / "touchpad_enabled"
        if p.exists():
            p.write_text(str(val))
            return True
    return False

def status():
    dev = find_hidraw()
    rid = get_report_id(dev) if dev else -1
    hid = read_hid(dev, rid) if dev and rid > 0 else None
    ec = read_ec()
    print(f"  hidraw: {dev}, report_id: {rid}")
    print(f"  HID value: {'0x'+format(hid,'02x') if hid is not None else 'None'}")
    print(f"  EC sysfs: {ec}")
    return dev, rid, hid, ec

if __name__ == "__main__":
    import sys
    print("=== Touchpad Diagnostic ===")
    dev = find_hidraw()
    if not dev:
        print("ERROR: No touchpad hidraw found!")
        sys.exit(1)
    rid = get_report_id(dev)
    print(f"Device: {dev}, Report ID: {rid}")
    print()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        status()
    elif cmd == "on":
        print("Writing HID=0x03 (ON)...")
        write_hid(dev, rid, 0x03)
        write_ec(1)
        time.sleep(0.3)
        status()
    elif cmd == "off":
        print("Writing HID=0x00 (OFF)...")
        write_hid(dev, rid, 0x00)
        write_ec(0)
        time.sleep(0.3)
        status()
    elif cmd == "cycle":
        print("OFF->ON cycle...")
        write_hid(dev, rid, 0x00)
        write_ec(0)
        time.sleep(1)
        write_hid(dev, rid, 0x03)
        write_ec(1)
        time.sleep(0.3)
        status()
    elif cmd == "monitor":
        print("Monitoring HID value (Ctrl+C to stop)...")
        last = read_hid(dev, rid)
        print(f"  Initial: 0x{last:02x}" if last is not None else "  Initial: None")
        while True:
            time.sleep(0.1)
            val = read_hid(dev, rid)
            if val != last:
                print(f"  CHANGE: 0x{last if last is not None else 0:02x} -> 0x{val:02x}  [{time.strftime('%H:%M:%S')}]")
                last = val
    else:
        print(f"Usage: {sys.argv[0]} [status|on|off|cycle|monitor]")

