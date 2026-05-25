#!/usr/bin/env python3
"""Test ITE8291R3 music/audio mode - attempt 2: without direct mode"""
import usb.core
import usb.util
import sys
import time

VENDOR_ID = 0x048D
PRODUCT_IDS = [0x6004, 0x6006, 0xCE00]

def find_device():
    for pid in PRODUCT_IDS:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=pid)
        if dev:
            print(f"Found ITE8291R3: VID={VENDOR_ID:#06x} PID={pid:#06x}")
            return dev
    return None

def send_ctrl(dev, *payload):
    payload = list(payload)
    if len(payload) < 8:
        payload += [0] * (8 - len(payload))
    print(f"  Sending: {[hex(b) for b in payload]}")
    dev.ctrl_transfer(
        usb.util.build_request_type(
            usb.util.CTRL_OUT,
            usb.util.CTRL_TYPE_CLASS,
            usb.util.CTRL_RECIPIENT_INTERFACE),
        0x09, 0x0300, 0x0001, payload)

dev = find_device()
if not dev:
    print("Device not found!"); sys.exit(1)

for cfg in dev:
    for intf in cfg:
        if intf.bInterfaceNumber == 1:
            if dev.is_kernel_driver_active(1):
                dev.detach_kernel_driver(1)

print("\n=== Test A: Set aurora effect first, then send CMD 0x02 ===")
send_ctrl(dev, 0x08, 0x02, 0x0E, 0x05, 0x32, 0x08, 0x00, 0x01)
time.sleep(2)

print("\n=== Sending audio enable CMD 0x02 (mode=1) ===")
send_ctrl(dev, 0x02, 0x01, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00)
print(">>> Play music! 15 seconds... <<<")
time.sleep(15)

print("\n=== Test B: Try CMD 0x02 with different sensitivity values ===")
for sens in [0x01, 0x05, 0x0A, 0x32, 0x50]:
    print(f"\n--- Sensitivity {sens:#04x} ---")
    send_ctrl(dev, 0x02, 0x01, sens, 0x00, 0x00, 0x00, 0x00, 0x00)
    time.sleep(5)

print("\n=== Test C: Try CMD 0x02 with mode=0x02 ===")
send_ctrl(dev, 0x02, 0x02, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00)
print(">>> 10 seconds... <<<")
time.sleep(10)

print("\n=== Disable and restore ===")
send_ctrl(dev, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)
send_ctrl(dev, 0x08, 0x02, 0x02, 0x05, 0x32, 0x08, 0x00, 0x01)
print("\nDone!")

