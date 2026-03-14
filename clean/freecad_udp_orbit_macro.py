"""
FreeCAD macro: receive joystick axes over UDP and rotate active 3D view.
"""

import socket
import warnings

import FreeCAD as App
import FreeCADGui as Gui
from PySide2 import QtCore

warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyObject has no __module__ attribute",
    category=DeprecationWarning,
)

from pivy import coin

UDP_HOST = "127.0.0.1"
UDP_PORT = 50055

YAW_SPEED = 0.055
PITCH_SPEED = 0.030
DEADZONE = 0.03
SMOOTHING = 0.20
AXIS_LOCK_RATIO = 1.8
AXIS_LOCK_HARD_DEADZONE = 0.03
HORIZONTAL_GAIN = 1.0
INVERT_HORIZONTAL = True
LOG_ENABLED = False

_sock = None
_timer = None
_view = None
_fx = 0.0
_fy = 0.0
_STATE_KEY = "_udp_orbit_state_v1"


def _vec(x: float, y: float, z: float) -> coin.SbVec3f:
    return coin.SbVec3f(float(x), float(y), float(z))


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _log(msg: str) -> None:
    if LOG_ENABLED:
        print(msg)


def _pivot_from_selection_or_scene() -> coin.SbVec3f:
    sel = Gui.Selection.getSelectionEx()
    if sel:
        try:
            bb = sel[0].Object.Shape.BoundBox
            return _vec((bb.XMin + bb.XMax) * 0.5, (bb.YMin + bb.YMax) * 0.5, (bb.ZMin + bb.ZMax) * 0.5)
        except Exception:
            pass

    doc = App.ActiveDocument
    if doc is not None:
        bb = App.BoundBox()
        for obj in doc.Objects:
            try:
                if hasattr(obj, "Shape"):
                    bb.add(obj.Shape.BoundBox)
            except Exception:
                continue
        if bb.isValid():
            return _vec((bb.XMin + bb.XMax) * 0.5, (bb.YMin + bb.YMax) * 0.5, (bb.ZMin + bb.ZMax) * 0.5)

    return _vec(0.0, 0.0, 0.0)


def _apply_orbit(dx: float, dy: float) -> None:
    global _view
    if _view is None:
        return

    cam = _view.getCameraNode()
    if cam is None:
        return

    pivot = _pivot_from_selection_or_scene()
    pos = cam.position.getValue()
    rel = _vec(pos[0] - pivot[0], pos[1] - pivot[1], pos[2] - pivot[2])

    if rel.length() < 1e-6:
        rel = _vec(0.0, -200.0, 100.0)

    q = cam.orientation.getValue()
    up = q.multVec(_vec(0.0, 1.0, 0.0))
    right = q.multVec(_vec(1.0, 0.0, 0.0))

    yaw = coin.SbRotation(up, -dx * YAW_SPEED)
    right_after_yaw = yaw.multVec(right)
    pitch = coin.SbRotation(right_after_yaw, -dy * PITCH_SPEED)
    rot = pitch * yaw
    new_rel = rot.multVec(rel)

    new_pos = _vec(pivot[0] + new_rel[0], pivot[1] + new_rel[1], pivot[2] + new_rel[2])
    cam.position.setValue(new_pos)

    new_up = rot.multVec(up)
    cam.pointAt(pivot, new_up)
    _view.redraw()


def _axis_lock(x: float, y: float) -> tuple[float, float]:
    ax = abs(x)
    ay = abs(y)

    if ax < AXIS_LOCK_HARD_DEADZONE and ay < AXIS_LOCK_HARD_DEADZONE:
        return 0.0, 0.0

    if ax > ay * AXIS_LOCK_RATIO:
        return x, 0.0
    if ay > ax * AXIS_LOCK_RATIO:
        return 0.0, y
    return x, y


def _tick() -> None:
    global _view, _fx, _fy
    if _view is None:
        if Gui.ActiveDocument is None:
            return
        _view = Gui.ActiveDocument.ActiveView
        if _view is None:
            return

    got_packet = False
    x_in = 0.0
    y_in = 0.0

    while True:
        try:
            data, _ = _sock.recvfrom(64)
        except BlockingIOError:
            break
        except Exception as e:
            _log(f"[UDP orbit] recv error: {e}")
            break

        try:
            s = data.decode("ascii", errors="ignore").strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 2:
                continue
            x = float(parts[0])
            y = float(parts[1])
        except Exception:
            continue

        got_packet = True
        if abs(x) < DEADZONE:
            x = 0.0
        if abs(y) < DEADZONE:
            y = 0.0

        x, y = _axis_lock(x, y)
        if INVERT_HORIZONTAL:
            x = -x
        x_in = _clamp(x * HORIZONTAL_GAIN, -1.0, 1.0)
        y_in = y

    if not got_packet:
        x_in = 0.0
        y_in = 0.0

    _fx = (1.0 - SMOOTHING) * _fx + SMOOTHING * x_in
    _fy = (1.0 - SMOOTHING) * _fy + SMOOTHING * y_in

    if abs(_fx) < 0.002:
        _fx = 0.0
    if abs(_fy) < 0.002:
        _fy = 0.0

    if _fx != 0.0 or _fy != 0.0:
        _apply_orbit(_fx, _fy)


def stop_udp_orbit() -> None:
    global _timer, _sock
    if _timer is not None:
        _timer.stop()
        _timer = None
    if _sock is not None:
        try:
            _sock.close()
        except Exception:
            pass
        _sock = None
    try:
        if hasattr(Gui, _STATE_KEY):
            setattr(Gui, _STATE_KEY, None)
    except Exception:
        pass
    _log("[UDP orbit] stopped")


def start_udp_orbit() -> None:
    global _timer, _sock, _view, _fx, _fy

    old_state = getattr(Gui, _STATE_KEY, None)
    if old_state:
        try:
            old_timer = old_state.get("timer")
            if old_timer is not None:
                old_timer.stop()
        except Exception:
            pass
        try:
            old_sock = old_state.get("sock")
            if old_sock is not None:
                old_sock.close()
        except Exception:
            pass

    stop_udp_orbit()

    if Gui.ActiveDocument is None or Gui.ActiveDocument.ActiveView is None:
        raise RuntimeError("Open a FreeCAD document with active 3D view first")
    _view = Gui.ActiveDocument.ActiveView
    _fx = 0.0
    _fy = 0.0

    _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _sock.bind((UDP_HOST, UDP_PORT))
    except OSError as e:
        _sock.close()
        _sock = None
        raise RuntimeError(
            f"Cannot bind UDP {UDP_HOST}:{UDP_PORT}. "
            "Port is busy/blocked. Change UDP_PORT in both scripts."
        ) from e
    _sock.setblocking(False)

    _timer = QtCore.QTimer()
    _timer.timeout.connect(_tick)
    _timer.start(16)
    setattr(Gui, _STATE_KEY, {"sock": _sock, "timer": _timer})


start_udp_orbit()
