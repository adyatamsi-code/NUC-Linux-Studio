"""
Shared USB bind/unbind helpers for the ITE8291R3 keyboard backlight.

Used by both keyboard.py (KeyboardController) and audio_daemon.py so the
same driver-rebind logic lives in exactly one place.
"""
import glob
import time
from pathlib import Path

# ITE Semiconductor vendor ID — matches all ITE8291R3 variants (PID 6004/6006/ce00)
_ITE_VENDOR = "048d"


def unbind_ite_driver() -> bool:
    """Unbind the ite8291r3 kernel driver (and any usbhid/usbfs squatter) from
    the ITE USB interface so userspace can claim the device directly.

    Returns True if the ITE device was found, False otherwise.
    """
    try:
        for dev_path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            vendor = Path(dev_path).read_text().strip()
            if vendor != _ITE_VENDOR:
                continue
            dev_dir = Path(dev_path).parent
            intf = dev_dir.name + ":1.1"
            for drv in ("ite8291r3", "usbfs", "usbhid"):
                unbind = Path(f"/sys/bus/usb/drivers/{drv}/unbind")
                if unbind.exists():
                    try:
                        unbind.write_text(intf)
                    except Exception:
                        pass
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False


def rebind_ite_driver() -> None:
    """Rebind the ITE USB interface back to the ite8291r3 kernel driver."""
    try:
        for dev_path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
            vendor = Path(dev_path).read_text().strip()
            if vendor != _ITE_VENDOR:
                continue
            dev_dir = Path(dev_path).parent
            intf = dev_dir.name + ":1.1"
            # Evict any usbfs squatter first
            usbfs_unbind = Path("/sys/bus/usb/drivers/usbfs/unbind")
            if usbfs_unbind.exists():
                try:
                    usbfs_unbind.write_text(intf)
                except Exception:
                    pass
            time.sleep(0.1)
            bind = Path("/sys/bus/usb/drivers/ite8291r3/bind")
            if bind.exists():
                try:
                    bind.write_text(intf)
                except Exception:
                    pass
            time.sleep(0.2)
            return
    except Exception:
        pass

