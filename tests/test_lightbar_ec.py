import os
import sys
import time

def write_ec(driver, addr, value):
    path = f"/sys/kernel/debug/{driver}/ec"
    if not os.path.exists(path):
        return False
    try:
        with open(path, "w") as f:
            f.seek(addr)
            f.write(str(value))
        return True
    except Exception as e:
        print(f"Error writing to {path} at {hex(addr)}: {e}")
        return False

def read_ec(driver, addr):
    path = f"/sys/kernel/debug/{driver}/ec"
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            f.seek(addr)
            val = f.read().strip()
            return int(val, 16) if val else None
    except Exception as e:
        print(f"Error reading from {path} at {hex(addr)}: {e}")
        return None

def check_ec():
    driver = "qc71_laptop"

    if not os.path.exists(f"/sys/kernel/debug/{driver}/ec"):
        print(f"Debugfs EC interface not found at /sys/kernel/debug/{driver}/ec. Make sure qc71_laptop is loaded and CONFIG_DEBUG_FS is enabled in kernel.")
        sys.exit(1)

    print(f"Using driver: {driver}")

    # Addresses
    CTRL_ADDR = 0x0748
    RED_ADDR = 0x0749
    GREEN_ADDR = 0x074A
    BLUE_ADDR = 0x074B

    # Read current state
    ctrl = read_ec(driver, CTRL_ADDR)
    r = read_ec(driver, RED_ADDR)
    g = read_ec(driver, GREEN_ADDR)
    b = read_ec(driver, BLUE_ADDR)
    print(f"Current EC State -> CTRL: {hex(ctrl) if ctrl else 'None'}, R: {r}, G: {g}, B: {b}")

    print("\n--- Test 1: Max Blue (36 on 0x074B) ---")
    write_ec(driver, RED_ADDR, 0)
    write_ec(driver, GREEN_ADDR, 0)
    write_ec(driver, BLUE_ADDR, 36)
    write_ec(driver, CTRL_ADDR, ctrl & ~0x80 if ctrl else 0) # Disable rainbow
    write_ec(driver, CTRL_ADDR, ctrl & ~0x04 if ctrl else 0) # Ensure it's ON
    print("Please check the lightbar. Is it Blue?")
    time.sleep(3)

    print("\n--- Test 2: Absolute Max Blue (255 on 0x074B) ---")
    write_ec(driver, BLUE_ADDR, 255)
    print("Please check the lightbar. Is it Blue and brighter?")
    time.sleep(3)
    
    print("\n--- Test 3: tuxedo-keyboard Blue address (36 on 0x1808) ---")
    write_ec(driver, BLUE_ADDR, 0) # Reset old address
    write_ec(driver, 0x1803, 0)
    write_ec(driver, 0x1805, 0)
    write_ec(driver, 0x1808, 36)
    print("Please check the lightbar. Is it Blue?")
    time.sleep(3)

    print("\n--- Test 4: Green (36 on 0x074A) ---")
    write_ec(driver, 0x1808, 0) # Reset alternate address
    write_ec(driver, GREEN_ADDR, 36)
    print("Please check the lightbar. Is it Green?")
    time.sleep(3)

    print("\n--- Test 5: Red (36 on 0x0749) ---")
    write_ec(driver, GREEN_ADDR, 0)
    write_ec(driver, RED_ADDR, 36)
    print("Please check the lightbar. Is it Red?")
    time.sleep(3)

    print("\nTurning off lightbar...")
    write_ec(driver, RED_ADDR, 0)
    write_ec(driver, GREEN_ADDR, 0)
    write_ec(driver, BLUE_ADDR, 0)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Please run this script with sudo.")
        sys.exit(1)
    check_ec()
