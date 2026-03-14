"""
FreeCAD autostart helper for `freecad_udp_orbit_macro.py`.
"""

from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide2 import QtCore

LOG_ENABLED = True
CHECK_INTERVAL_MS = 500
STATE_KEY = "_udp_orbit_autostart_v1"
MACRO_PATH = Path(__file__).with_name("freecad_udp_orbit_macro.py")
_WAITING_STATE = None


def _log(msg: str) -> None:
    if LOG_ENABLED:
        App.Console.PrintMessage(f"{msg}\n")


def _log_error(msg: str) -> None:
    App.Console.PrintError(f"{msg}\n")


def _set_waiting_state(state: str | None) -> None:
    global _WAITING_STATE
    if _WAITING_STATE == state:
        return
    _WAITING_STATE = state
    if state == "document":
        _log("[UDP orbit autostart] waiting for active document")
    elif state == "view":
        _log("[UDP orbit autostart] waiting for active 3D view")


def _stop_existing() -> None:
    state = getattr(Gui, STATE_KEY, None)
    if not state:
        return
    timer = state.get("timer")
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
    setattr(Gui, STATE_KEY, None)


def _start_macro_when_ready() -> None:
    if Gui.ActiveDocument is None:
        _set_waiting_state("document")
        return

    view = Gui.ActiveDocument.ActiveView
    if view is None:
        _set_waiting_state("view")
        return

    _set_waiting_state(None)

    state = getattr(Gui, STATE_KEY, None) or {}
    namespace = state.get("namespace")
    if namespace is None:
        namespace = {"__file__": str(MACRO_PATH), "__name__": "__main__"}
        state["namespace"] = namespace
        setattr(Gui, STATE_KEY, state)

    try:
        _log(f"[UDP orbit autostart] starting {MACRO_PATH}")
        exec(MACRO_PATH.read_text(encoding="utf-8"), namespace)
        _stop_existing()
        _log("[UDP orbit autostart] macro started")
    except Exception as exc:
        _log_error(f"[UDP orbit autostart] failed: {exc!r}")


def start_udp_orbit_autostart() -> None:
    _stop_existing()

    if not MACRO_PATH.exists():
        raise RuntimeError(f"Macro file not found: {MACRO_PATH}")

    timer = QtCore.QTimer()
    timer.timeout.connect(_start_macro_when_ready)
    timer.start(CHECK_INTERVAL_MS)
    setattr(Gui, STATE_KEY, {"timer": timer, "namespace": {"__file__": str(MACRO_PATH), "__name__": "__main__"}})
    _log("[UDP orbit autostart] watcher started")
    _start_macro_when_ready()


start_udp_orbit_autostart()
