import os

def check_blue():
    path = "/sys/class/leds/uniwill:multicolor:status/multi_intensity"
    if not os.path.exists(path):
        print("Path not found")
        return
    
    with open(path, "w") as f:
        f.write("0 0 255")
    print("Wrote blue")

if __name__ == "__main__":
    check_blue()
