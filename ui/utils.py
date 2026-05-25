import tkinter as tk
from tkinter import ttk

KEY_LAYOUT = [
    ["ESC", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "INS", "SCRLK", "DEL"],
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "BACKSPACE", "HOME"],
    ["TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\", "PGUP"],
    ["CAPS", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "ENTER", "PGDN"],
    ["SHIFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "SHIFT", "↑", "END"],
    ["CTRL", "FN", "WIN", "ALT", "SPACE", "ALT", "MENU", "CTRL", "←", "↓", "→"],
]

# Key display: (main_top_text, bottom_numpad_fn_text)
FN_KEY_SYMBOLS = {
    "ESC": ("ESC", "FN LK"),
    "F1": ("F1", "Zᶻ"),
    "F2": ("F2", "🔇"),
    "F3": ("F3", "🔉"),
    "F4": ("F4", "🔊"),
    "F5": ("F5", "🎤"),
    "F7": ("F7", "▭"),
    "F8": ("F8", "💡"),
    "F9": ("F9", "🔅"),
    "F10": ("F10", "🔆"),
    "F11": ("F11", "⧉"),
    "F12": ("F12", "✈"),
    "INS": ("INSERT", "PRT SC"),
    "SCRLK": ("SCR LK", "NUM LK"),
    "BACKSPACE": ("←\nBACKSPACE", ""),
    "ENTER": ("⏎\nENTER", ""),
    "MENU": ("≡", ""),
    "WIN": ("❖", ""),
    "SPACE": ("━", ""),
    "←": ("◁", ""),
    "→": ("▷", ""),
    "↑": ("△", ""),
    "↓": ("▽", ""),
    # Number row: side by side symbols as requested
    "`": ("`  ~", ""),
    "1": ("1  !", ""),
    "2": ("2  @", ""),
    "3": ("3  #", ""),
    "4": ("4  $", ""),
    "5": ("5  %", ""),
    "6": ("6  ^", ""),
    "7": ("7  &", "7"),
    "8": ("8  *", "8"),
    "9": ("9  (", "9"),
    "0": ("0  )", "/"),
    "-": ("-  _", ""),
    "=": ("=  +", ""),
    # Punctuation with shift + numpad
    ";": (";  :", "-"),
    "'": ("'  \"", ""),
    ",": (",  <", ""),
    ".": (".  >", "."),
    "/": ("/  ?", "+"),
    "[": ("[  {", ""),
    "]": ("]  }", ""),
    "\\": ("\\  |", ""),
    # Letter keys with numpad overlay
    "U": ("U", "4"),
    "I": ("I", "5"),
    "O": ("O", "6"),
    "P": ("P", "*"),
    "J": ("J", "1"),
    "K": ("K", "2"),
    "L": ("L", "3"),
    "M": ("M", "0"),
}

DEFAULT_COLOR = "#2d2640"
FAN_CURVE_TEMPS = [30, 50, 70, 90]
FAN_CURVE_CPU_SPEEDS = [30, 50, 70, 100]
FAN_CURVE_DGPU_SPEEDS = [25, 45, 65, 95]
FAN_CURVE_NAMES = ["CPU", "dGPU"]

def sanitize_color(color):
    if not color or not isinstance(color, str):
        return DEFAULT_COLOR
    if color.startswith("#") and len(color) == 7:
        return color
    return DEFAULT_COLOR

def get_closest_color(r, g, b):
    colors = {
        "red": (255, 0, 0), "orange": (255, 128, 0),
        "yellow": (255, 255, 0), "green": (0, 255, 0),
        "blue": (0, 0, 255), "teal": (0, 255, 255),
        "purple": (128, 0, 128)
    }
    return min(colors.keys(), key=lambda k: (r-colors[k][0])**2 + (g-colors[k][1])**2 + (b-colors[k][2])**2)

def show_message(parent, title, message):
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("600x250")
    dialog.transient(parent)
    dialog.grab_set()
    ttk.Label(dialog, text="Message details (you can copy the text below):").pack(anchor="w", padx=12, pady=(12, 4))
    text_frame = ttk.Frame(dialog)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
    text = tk.Text(text_frame, wrap=tk.WORD)
    text.insert(tk.END, str(message))
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar = ttk.Scrollbar(text_frame, command=text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text.config(yscrollcommand=scrollbar.set)
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=12)