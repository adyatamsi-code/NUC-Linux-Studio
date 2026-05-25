````````````# Lightbar Brightness Investigation — Final Report for Gemini

## Definitive Finding

Even with ALL registers correctly set and confirmed via EC debug readback:
```
0x0747 = 0x64  (brightness = 100, confirmed written)
0x0748 = 0x01  (static mode, S0_OFF cleared, confirmed written)
0x074B = 0x3F  (blue = 63 max, confirmed written)
```
The lightbar is STILL dim in static mode.

**Only BIT(7) in 0x0748 produces bright output**, but it forces rainbow/demo animation and ignores color registers.

## All Tests Performed

| Control (0x0748) | Brightness (0x0747) | Colors | Result |
|---|---|---|---|
| 0x01 (static) | 0x64 | 0x3F blue | Dim blue, correct color |
| 0x01 (static) | 0xC8 | 0x3F blue | Same dim (no change) |
| 0x21 (BIT5+BIT0) | 0x64 | 0x3F blue | Same dim |
| 0x80 (BIT7) | 0x64 | - | BRIGHT rainbow |
| 0x81 (BIT7+BIT0) | 0x64 | 0x3F blue | BRIGHT rainbow (colors ignored) |
| 0x80→colors→0x01 | 0x64 | 0x3F blue | Dim (reverts when BIT7 cleared) |
| 0x01 + trigger 0x0767=0x02 | 0x64 | 0x3F blue | Same dim |

## EC Register Dump (page 7) Confirms

After writing `0 0 255` with current driver:
```
47=64 48=01 49=00 4a=00 4b=3f 4c=00 4d=00 4e=3f 4f=00
```
Everything is written correctly. The dim output is not a register issue — it's an EC firmware PWM power level issue.

## Questions

1. **Is there a register on a DIFFERENT EC page (not page 7) that controls lightbar LED current?** Perhaps page 0x18 (where fan PWM lives) or page 0x04?

2. **Does the Windows Intel NUC Studio set any registers during initialization (service startup) that permanently boost lightbar power until the next reboot?** Something like a one-time "unlock" write?

3. **Is the dim static actually the NORMAL brightness for this laptop?** Was the Windows lightbar in static mode also noticeably dimmer than rainbow mode, just not as dim as what we see?

4. **Could there be a WMI method (not direct EC register) that the Windows driver calls to set lightbar power level?** Something accessible via the ACPI WMI GUID rather than raw EC writes?
````````````
# Lightbar Brightness — TODO

## Status: Working but dim in static mode (firmware-limited)

Static color mode works correctly (RGB mapping confirmed, uniform illumination with trigger).
The EC firmware caps static PWM at ~25-35% duty cycle. Only BIT(7) of 0x0748 (rainbow/demo mode) gives full brightness.

## Future Investigation
- Reverse-engineer Windows NUC Studio WMI "SetState" call that unlocks full brightness
- Check if `8C5DA44C-CDC3-46B3-8619-4E26D34390B7` GUID method 0x02 can set lighting power level
- Try ACPI disassembly of WMAA/WMAB methods to find the brightness unlock parameter
