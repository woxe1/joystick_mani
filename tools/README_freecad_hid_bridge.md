# FreeCAD HID Bridge (Windows)

## Mode A: Mouse Emulation (legacy)

Reads STM32 HID and emulates `Shift + MMB drag`.

```powershell
py -m pip install hidapi pynput
py tools/freecad_hid_bridge.py
```

Use this only if direct FreeCAD orbit mode is not needed.

## Mode B: Direct FreeCAD Orbit Commands (recommended)

Does not emulate system mouse.
PC bridge sends joystick axes via UDP, FreeCAD macro rotates camera directly.

### 1) Install Python package for bridge

```powershell
py -m pip install hidapi
```

### 2) Start FreeCAD macro

1. Open FreeCAD.
2. `Macro -> Macros... -> Create` (or open existing macro).
3. Paste file content from `tools/freecad_udp_orbit_macro.py`.
4. Execute macro.
5. In FreeCAD Python console you should see:
   `[UDP orbit] listening on 127.0.0.1:50055`

### 3) Run HID -> UDP bridge

```powershell
py tools/freecad_hid_udp_bridge.py
```

Optional one-time axis calibration (recommended if directions are mixed):

```powershell
py tools/freecad_hid_udp_bridge.py --calibrate
```

Follow prompts for: center, right, left, up, down.
This saves `tools/freecad_hid_calibration.json`.

To apply saved calibration matrix during normal run:

```powershell
py tools/freecad_hid_udp_bridge.py --use-calibration
```

### 4) Test

- Focus 3D view in FreeCAD.
- Select a body/solid first (recommended).
- Move joystick.
- View should rotate without grabbing your normal mouse.

## Notes

- Device VID:PID is hardcoded as `0483:A4F1`.
- Stop terminal bridge with `Ctrl+C`.
- Stop FreeCAD macro from Python console:
  `stop_udp_orbit()`
- Orbit pivot: selected object center; if nothing selected, scene center.
- Direction tuning is in `tools/freecad_hid_udp_bridge.py`:
  `SWAP_XY`, `INVERT_X`, `INVERT_Y`, `ROTATE_DEG`.
