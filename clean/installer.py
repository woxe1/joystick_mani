"""
One-file installer/runtime entrypoint for JoystickMani FreeCAD integration.

Build as a single EXE with PyInstaller. The resulting executable has two modes:
1) default install mode: copies scripts into FreeCAD and registers Windows autostart
2) runtime mode: `--run-bridge` launches the HID->UDP bridge in background
"""

from __future__ import annotations

import argparse
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "JoystickMani"
TASK_NAME = "JoystickMani HID Bridge"
BRIDGE_SCRIPT = "freecad_hid_udp_bridge.py"
AUTOSTART_SCRIPT = "freecad_udp_orbit_autostart.py"
MACRO_SCRIPT = "freecad_udp_orbit_macro.py"
RUNTIME_EXE_NAME = "joystick_mani_runtime.exe"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / APP_NAME


def freecad_macro_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "FreeCAD" / "Macro"


def freecad_mod_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "FreeCAD" / "Mod" / "JoystickOrbit"


def runtime_exe_path() -> Path:
    return install_dir() / RUNTIME_EXE_NAME


def bridge_script_path() -> Path:
    return install_dir() / BRIDGE_SCRIPT


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def install_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def remove_file_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def remove_dir_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def create_freecad_init_files() -> None:
    ensure_dir(freecad_mod_dir())
    autostart_path = freecad_macro_dir() / AUTOSTART_SCRIPT

    init_py = 'import FreeCAD as App\n\nApp.Console.PrintMessage("[JoystickOrbit] Init.py loaded\\n")\n'
    init_gui_py = (
        "import FreeCAD as App\n\n"
        f'AUTOSTART_PATH = r"{autostart_path}"\n\n'
        'App.Console.PrintMessage(f"[JoystickOrbit] loading {AUTOSTART_PATH}\\n")\n\n'
        "try:\n"
        '    namespace = {"__file__": AUTOSTART_PATH, "__name__": "__main__"}\n'
        '    exec(open(AUTOSTART_PATH, encoding="utf-8").read(), namespace)\n'
        '    App.Console.PrintMessage("[JoystickOrbit] autostart loaded\\n")\n'
        "except Exception as exc:\n"
        '    App.Console.PrintError(f"[JoystickOrbit] autostart failed: {exc!r}\\n")\n'
    )

    (freecad_mod_dir() / "Init.py").write_text(init_py, encoding="utf-8")
    (freecad_mod_dir() / "InitGui.py").write_text(init_gui_py, encoding="utf-8")


def copy_runtime_payload() -> None:
    src_dir = resource_dir()
    dst_dir = install_dir()
    ensure_dir(dst_dir)

    install_file(src_dir / BRIDGE_SCRIPT, dst_dir / BRIDGE_SCRIPT)
    install_file(src_dir / AUTOSTART_SCRIPT, freecad_macro_dir() / AUTOSTART_SCRIPT)
    install_file(src_dir / MACRO_SCRIPT, freecad_macro_dir() / MACRO_SCRIPT)

    calibration_src = src_dir / "freecad_hid_calibration.json"
    if calibration_src.exists():
        install_file(calibration_src, dst_dir / "freecad_hid_calibration.json")

    if is_frozen():
        install_file(Path(sys.executable), runtime_exe_path())
    else:
        install_file(Path(__file__).resolve(), runtime_exe_path().with_suffix(".py"))

    create_freecad_init_files()


def build_task_command(use_calibration: bool) -> str:
    exe = runtime_exe_path()
    args = ["--run-bridge"]
    if use_calibration:
        args.append("--use-calibration")

    arg_list = ",".join(f"'{arg}'" for arg in args)
    exe_str = str(exe).replace("'", "''")
    return (
        'powershell.exe -NoProfile -WindowStyle Hidden -Command '
        f'"Start-Process -FilePath \'{exe_str}\' -ArgumentList {arg_list} -WindowStyle Hidden"'
    )


def register_task(use_calibration: bool) -> None:
    task_command = build_task_command(use_calibration)
    subprocess.run(
        [
            "schtasks",
            "/Create",
            "/F",
            "/SC",
            "ONLOGON",
            "/TN",
            TASK_NAME,
            "/TR",
            task_command,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def unregister_task() -> None:
    subprocess.run(
        [
            "schtasks",
            "/Delete",
            "/F",
            "/TN",
            TASK_NAME,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def run_bridge(runtime_args: list[str]) -> int:
    script = bridge_script_path()
    if not script.exists():
        script = resource_dir() / BRIDGE_SCRIPT
    if not script.exists():
        raise FileNotFoundError(f"Bridge script not found: {script}")

    sys.argv = [str(script), *runtime_args]
    runpy.run_path(str(script), run_name="__main__")
    return 0


def install(use_calibration: bool) -> int:
    copy_runtime_payload()
    register_task(use_calibration)
    print(f"{APP_NAME} installed into {install_dir()}")
    print(f"FreeCAD macros installed into {freecad_macro_dir()}")
    print(f"Windows autostart task created: {TASK_NAME}")
    return 0


def uninstall() -> int:
    unregister_task()

    remove_file_if_exists(freecad_macro_dir() / AUTOSTART_SCRIPT)
    remove_file_if_exists(freecad_macro_dir() / MACRO_SCRIPT)

    mod_dir = freecad_mod_dir()
    remove_file_if_exists(mod_dir / "Init.py")
    remove_file_if_exists(mod_dir / "InitGui.py")
    remove_dir_if_empty(mod_dir)
    remove_dir_if_empty(mod_dir.parent)

    app_dir = install_dir()
    if app_dir.exists():
        shutil.rmtree(app_dir, ignore_errors=True)

    print(f"{APP_NAME} uninstalled")
    print(f"Windows autostart task removed: {TASK_NAME}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-bridge", action="store_true", help="Run installed HID bridge instead of installer")
    parser.add_argument("--uninstall", action="store_true", help="Remove installed files and Windows autostart")
    parser.add_argument("--use-calibration", action="store_true", help="Enable saved calibration in autostart task")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.run_bridge:
        runtime_args = []
        if args.use_calibration:
            runtime_args.append("--use-calibration")
        return run_bridge(runtime_args)
    if args.uninstall:
        return uninstall()
    return install(args.use_calibration)


if __name__ == "__main__":
    raise SystemExit(main())
