#!/usr/bin/env python3
"""Test ITE8291R3 music/audio mode via CMD 0x02"""
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
        0x09,   # HID SET_REPORT
        0x0300, # Feature report, report ID 0
        0x0001, # Interface 1
        payload)

dev = find_device()
if not dev:
    print("Device not found!")
    sys.exit(1)

# Detach kernel driver if attached
for cfg in dev:
    for intf in cfg:
        if intf.bInterfaceNumber == 1:
            if dev.is_kernel_driver_active(1):
                dev.detach_kernel_driver(1)
                print("Detached kernel driver from interface 1")

print("\n=== Step 1: Enter User/Direct Mode (0x33) ===")
send_ctrl(dev, 0x08, 0x02, 0x33, 0x00, 0x32, 0x00, 0x00, 0x00)
time.sleep(1)

print("\n=== Step 2: Send Audio Toggle CMD 0x02 (mode=1, sensitivity=0x80) ===")
send_ctrl(dev, 0x02, 0x01, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00)
print("\n>>> Play some music now! Watching for 15 seconds... <<<")
time.sleep(15)

print("\n=== Step 3: Disable audio mode ===")
send_ctrl(dev, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)

print("\n=== Step 4: Set breathing effect to restore normal state ===")
send_ctrl(dev, 0x08, 0x02, 0x02, 0x05, 0x32, 0x08, 0x00, 0x01)

print("\nDone! Did the keyboard react to audio?")

