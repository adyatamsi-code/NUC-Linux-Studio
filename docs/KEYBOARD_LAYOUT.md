# Intel NUC X15 / TongFang QC71 Keyboard Layout & Sizing

This document contains the reference physical sizing of the keys for the Intel NUC X15 Laptop Kit (TongFang chassis). This is a standard 15.6" Tenkeyless (TKL) layout with an extra navigation column on the right.

Sizing is typically measured in "U" units, where `1U` represents the width of a standard alphanumeric key. The standard key pitch (center-to-center distance) on these laptops is ~19mm.

## General Physical Dimensions (Approximate)
- **Standard Key (1U):** 15mm x 15mm (with a 4mm gap between keys)
- **Total Keyboard Width:** ~280mm
- **Total Keyboard Height:** ~105mm
- **Aspect Ratio:** The physical keyboard is approximately 2.7 times wider than it is tall (Aspect Ratio ≈ 2.7).

## UI Implementation Guide (Tkinter)

To render the keyboard proportionally in a UI without stretching the keys into rectangles, follow these exact layout rules:

### 1. The Grid Unit System
Use a base grid where **1 column = 0.25U**. 
A standard `1U` key will span exactly `4` columns.
The total width of the keyboard is **17U**, which equates to **68 grid columns**.

### 2. Proportional Row Spans (`SPAN_BY_ROW_EXACT`)
Pass this list into the `columnspan` argument for each button in your grid loop.

```python
SPAN_BY_ROW_EXACT = [
    # Row 0 (Function Keys): Esc(4), F1-F4(4x4), F5-F8(4x4), F9-F12(4x4), PrtSc(4), Ins(4), Del(4) + Nav Gap(4) + Mute/Mic(4)
    [4]*17,                                              
    
    # Row 1 (Numbers): `(4), 1-0(10x4), -(4), =(4), Backspace(8) + Nav Gap(4) + Home(4)
    [4]*13 + [8, 4, 4],                                     
    
    # Row 2 (QWERTY): Tab(6), Q-P(10x4), [(4), ](4), \(6) + Nav Gap(4) + PgUp(4)
    [6] + [4]*12 + [6, 4, 4],                               
    
    # Row 3 (ASDFG): Caps(7), A-L(9x4), ;(4), '(4), Enter(9) + Nav Gap(4) + PgDn(4)
    [7] + [4]*11 + [9, 4, 4],                               
    
    # Row 4 (ZXCVB): LShift(9), Z-/(10x4), RShift(11) + Up Arrow(4) + End(4)
    [9] + [4]*10 + [11, 4, 4],                            
    
    # Row 5 (Spacebar row): LCtrl(5), Fn(4), Win(4), LAlt(5), Space(26), RAlt(5), RCtrl(5), Left(4), Down(4), Right(4)
    [5, 4, 4, 5, 26, 5, 5, 4, 4, 4]                   
]
```

### 3. Aspect Ratio Scaling (The Copilot Prompt)
To ensure the keys scale properly when the app window is resized, you **must not** let the `grid()` manager stretch the buttons organically. You must use an intermediate wrapper frame.

Instruct Copilot to use the following structure:
1. Create an outer container frame: `self.keyboard_container = tk.Frame(...)` and `pack(fill=BOTH, expand=True)` or `grid(sticky="nsew")`.
2. Create an inner frame: `self.grid_frame = tk.Frame(self.keyboard_container)`.
3. Center the inner frame using `place`: `self.grid_frame.place(relx=0.5, rely=0.5, anchor="center")`.
4. Bind the `<Configure>` event of the **outer** container to an aspect ratio calculator.

**Aspect Ratio Calculator Snippet:**
```python
def _on_resize_keyboard(self, event):
    """Forces the keyboard grid to maintain a realistic aspect ratio."""
    TARGET_ASPECT_RATIO = 2.7 # Realistic laptop keyboard ratio (keys are near-square)
    
    available_width = event.width
    available_height = event.height
    
    if available_width <= 1 or available_height <= 1:
        return
        
    current_ratio = available_width / available_height
    
    if current_ratio > TARGET_ASPECT_RATIO:
        # Window is too wide, height is the limiting factor
        new_height = available_height
        new_width = int(new_height * TARGET_ASPECT_RATIO)
    else:
        # Window is too tall, width is the limiting factor
        new_width = available_width
        new_height = int(new_width / TARGET_ASPECT_RATIO)
        
    # Apply the exact pixel dimensions to the inner grid frame
    self.grid_frame.config(width=new_width, height=new_height)
    self.grid_frame.grid_propagate(False) # Prevent grid contents from overriding the forced pixel size
```

By ensuring `self.grid_frame` has exactly 68 `columnconfigure(weight=1)` and 6 `rowconfigure(weight=1)`, and forcing its overall width/height via the `<Configure>` event, the buttons inside will scale beautifully and remain perfectly proportional to a real keyboard regardless of how the user stretches the window.

### 4. Inter-Key Gap Rules

Gaps between keys must be **uniform** in both X and Y directions. Compute the gap from the width of a standard 1U key, NOT from row height or column width independently:

```python
unit_key_w = kb_w / 16.0          # width of a 1U key (4 grid columns)
gap = max(1, int(unit_key_w * 0.05))  # 5% of 1U key width, same for X and Y
```

**Critical**: subtract this gap from each side of each key rectangle (pad inward), do NOT shrink the overall keyboard to accommodate gaps. Instead, adjust the aspect ratio so keys remain near-square after gap subtraction.

### 5. Font Sizing

Font sizes must be proportional to the **rendered key height** (after gap subtraction), not the raw row height:

```python
key_h = y2 - y1  # actual rendered key height
font_size = max(3, int(key_h * 0.10))  # 10% of key height for regular keys
arrow_font = max(4, int(key_h * 0.14))  # 14% for arrow symbols
```
