# Clean Package

This folder contains the minimal files needed to deploy the FreeCAD joystick setup:

- `freecad_hid_udp_bridge.py`
- `freecad_udp_orbit_autostart.py`
- `freecad_udp_orbit_macro.py`
- `installer.py`
- `build_installer.ps1`

## Recommended packaging flow

Build a single EXE installer with:

```powershell
powershell -ExecutionPolicy Bypass -File .\clean\build_installer.ps1
```

Result:

```text
dist\joystick_mani_installer.exe
```

## What the installer does

- copies the HID bridge into `%LocalAppData%\JoystickMani`
- copies the FreeCAD macro files into `%AppData%\FreeCAD\Macro`
- creates `%AppData%\FreeCAD\Mod\JoystickOrbit\Init.py`
- creates `%AppData%\FreeCAD\Mod\JoystickOrbit\InitGui.py`
- copies the installer EXE into `%LocalAppData%\JoystickMani\joystick_mani_runtime.exe`
- creates a Windows `Task Scheduler` task named `JoystickMani HID Bridge`

The task launches:

```text
%LocalAppData%\JoystickMani\joystick_mani_runtime.exe --run-bridge
```

If you want calibration in autostart, run the installer with:

```text
joystick_mani_installer.exe --use-calibration
```

## Uninstall

Use the same EXE:

```text
joystick_mani_installer.exe --uninstall
```

This removes:

- `%LocalAppData%\JoystickMani`
- `%AppData%\FreeCAD\Macro\freecad_udp_orbit_autostart.py`
- `%AppData%\FreeCAD\Macro\freecad_udp_orbit_macro.py`
- `%AppData%\FreeCAD\Mod\JoystickOrbit\Init.py`
- `%AppData%\FreeCAD\Mod\JoystickOrbit\InitGui.py`
- Windows task `JoystickMani HID Bridge`
