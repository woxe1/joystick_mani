"""
Read STM32 HID (0483:A4F1) and send normalized axes to FreeCAD over UDP.

Packet format (ASCII):
    "x y\n"
where x,y are floats in range -1.0..1.0
"""

import socket
import time
import math
import json
import argparse
from pathlib import Path

import hid  # pip install hidapi

VID = 0x0483
PID = 0xA4F1

UDP_HOST = "127.0.0.1"
UDP_PORT = 50055

POLL_TIMEOUT_MS = 20
SEND_INTERVAL_S = 0.02
DEBUG = True
LOG_ENABLED = False
RECONNECT_INTERVAL_S = 1.0
DEADZONE_COUNTS = 6
BIAS_TRACK_WINDOW = 24
BIAS_ALPHA = 0.02
REST_WINDOW_COUNTS = 18
REST_HOLD_S = 0.20
BIAS_ALPHA_REST = 0.10
REST_ZERO_COUNTS = 12
SOFT_DEADZONE = 0.14
RESPONSE_GAMMA = 1.9

# Direction calibration (start from neutral; tune only if needed)
SWAP_XY = False
INVERT_X = False
INVERT_Y = False
ROTATE_DEG = 0.0
CALIB_FILE = Path(__file__).with_name("freecad_hid_calibration.json")


def to_int8(v: int) -> int:
    return v - 256 if v > 127 else v


def decode_xy(report: bytes) -> tuple[int, int]:
    if len(report) >= 3 and report[0] == 0:
        x_raw = report[1]
        y_raw = report[2]
    elif len(report) >= 2:
        x_raw = report[0]
        y_raw = report[1]
    else:
        return 0, 0
    return to_int8(x_raw), to_int8(y_raw)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def log(msg: str) -> None:
    if LOG_ENABLED:
        print(msg)


def transform_xy(x: float, y: float) -> tuple[float, float]:
    if SWAP_XY:
        x, y = y, x

    if INVERT_X:
        x = -x
    if INVERT_Y:
        y = -y

    if ROTATE_DEG != 0.0:
        a = math.radians(ROTATE_DEG)
        ca = math.cos(a)
        sa = math.sin(a)
        xr = x * ca - y * sa
        yr = x * sa + y * ca
        x, y = xr, yr

    return clamp(x, -1.0, 1.0), clamp(y, -1.0, 1.0)


def apply_matrix(x: float, y: float, m: tuple[float, float, float, float] | None) -> tuple[float, float]:
    if m is None:
        return x, y
    m00, m01, m10, m11 = m
    xr = m00 * x + m01 * y
    yr = m10 * x + m11 * y
    return xr, yr


def save_calibration(m: tuple[float, float, float, float]) -> None:
    payload = {"matrix": [float(v) for v in m]}
    CALIB_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"Saved calibration to {CALIB_FILE}")


def load_calibration() -> tuple[float, float, float, float] | None:
    if not CALIB_FILE.exists():
        return None
    try:
        payload = json.loads(CALIB_FILE.read_text(encoding="utf-8"))
        vals = payload.get("matrix", [])
        if len(vals) != 4:
            return None
        return float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3])
    except Exception:
        return None


def capture_mean(dev: hid.device, seconds: float = 0.7) -> tuple[float, float]:
    end = time.time() + seconds
    sx = 0.0
    sy = 0.0
    n = 0
    while time.time() < end:
        data = dev.read(64, POLL_TIMEOUT_MS)
        if not data:
            continue
        x, y = decode_xy(bytes(data))
        sx += x
        sy += y
        n += 1
    if n == 0:
        return 0.0, 0.0
    return sx / n, sy / n


def run_calibration(dev: hid.device) -> tuple[float, float, float, float]:
    log("Calibration mode.")
    log("Press Enter and hold each position steady for ~1 second.")
    input("1) Center stick, then Enter...")
    cx, cy = capture_mean(dev)
    input("2) Full RIGHT, hold, then Enter...")
    rx, ry = capture_mean(dev)
    input("3) Full LEFT, hold, then Enter...")
    lx, ly = capture_mean(dev)
    input("4) Full UP, hold, then Enter...")
    ux, uy = capture_mean(dev)
    input("5) Full DOWN, hold, then Enter...")
    dx, dy = capture_mean(dev)

    log(
        "Captured means: "
        f"C=({cx:+.1f},{cy:+.1f}) "
        f"R=({rx:+.1f},{ry:+.1f}) "
        f"L=({lx:+.1f},{ly:+.1f}) "
        f"U=({ux:+.1f},{uy:+.1f}) "
        f"D=({dx:+.1f},{dy:+.1f})"
    )

    vrx = (rx - lx) * 0.5
    vry = (ry - ly) * 0.5
    vux = (ux - dx) * 0.5
    vuy = (uy - dy) * 0.5

    det = vrx * vuy - vry * vux
    if abs(det) < 1e-6:
        raise RuntimeError(
            "Calibration failed: singular axis matrix. "
            "Check wiring/ADC mapping and repeat with full stick travel."
        )

    inv = (vuy / det, -vux / det, -vry / det, vrx / det)
    save_calibration(inv)
    log(f"Calibration done. Matrix={inv}")
    return inv


def shape_axis(v: float) -> float:
    av = abs(v)
    if av <= SOFT_DEADZONE:
        return 0.0

    t = (av - SOFT_DEADZONE) / (1.0 - SOFT_DEADZONE)
    t = clamp(t, 0.0, 1.0)
    out = t ** RESPONSE_GAMMA
    return out if v >= 0.0 else -out


def select_device() -> dict | None:
    devices = hid.enumerate(VID, PID)
    if not devices:
        return None

    selected = devices[0]
    for d in devices:
        if d.get("usage_page") == 0x01 and d.get("usage") == 0x08:
            selected = d
            break
    return selected


def open_device() -> tuple[hid.device, dict]:
    selected = select_device()
    if selected is None:
        raise RuntimeError(f"HID {VID:04X}:{PID:04X} not found")

    dev = hid.device()
    dev.open_path(selected["path"])
    dev.set_nonblocking(True)
    return dev, selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true", help="Run interactive axis calibration and save matrix")
    parser.add_argument("--use-calibration", action="store_true", help="Apply saved calibration matrix")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log(f"Sending UDP to {UDP_HOST}:{UDP_PORT}")
    matrix = None
    if args.use_calibration:
        matrix = load_calibration()
        if matrix is not None:
            log(f"Using saved calibration matrix: {matrix}")
        else:
            log("No valid calibration file found. Running without matrix.")
    else:
        log("Running without calibration matrix.")

    dev = None
    announced_wait = False
    last_send = 0.0
    bias_x = 0.0
    bias_y = 0.0
    rest_since = 0.0
    try:
        while True:
            if dev is None:
                try:
                    dev, selected = open_device()
                    announced_wait = False
                    bias_x = 0.0
                    bias_y = 0.0
                    rest_since = 0.0
                    last_send = 0.0
                    log(f"Connected HID {VID:04X}:{PID:04X} path={selected['path']}")
                    log("Auto-bias compensation enabled")
                    if args.calibrate:
                        matrix = run_calibration(dev)
                except Exception as exc:
                    if not announced_wait:
                        log(f"HID unavailable, waiting for reconnect: {exc}")
                        announced_wait = True
                    time.sleep(RECONNECT_INTERVAL_S)
                    continue

            try:
                data = dev.read(64, POLL_TIMEOUT_MS)
            except Exception as exc:
                log(f"HID read failed, reconnecting: {exc}")
                try:
                    dev.close()
                except Exception:
                    pass
                dev = None
                continue

            if not data:
                continue

            raw_x, raw_y = decode_xy(bytes(data))
            x_i = raw_x
            y_i = raw_y

            if abs(x_i) < BIAS_TRACK_WINDOW and abs(y_i) < BIAS_TRACK_WINDOW:
                bias_x = (1.0 - BIAS_ALPHA) * bias_x + BIAS_ALPHA * x_i
                bias_y = (1.0 - BIAS_ALPHA) * bias_y + BIAS_ALPHA * y_i

            x_i = int(round(x_i - bias_x))
            y_i = int(round(y_i - bias_y))

            now = time.time()
            if abs(x_i) < REST_WINDOW_COUNTS and abs(y_i) < REST_WINDOW_COUNTS:
                if rest_since == 0.0:
                    rest_since = now
                elif (now - rest_since) >= REST_HOLD_S:
                    bias_x = (1.0 - BIAS_ALPHA_REST) * bias_x + BIAS_ALPHA_REST * raw_x
                    bias_y = (1.0 - BIAS_ALPHA_REST) * bias_y + BIAS_ALPHA_REST * raw_y
                    x_i = int(round(raw_x - bias_x))
                    y_i = int(round(raw_y - bias_y))
                    if abs(x_i) <= REST_ZERO_COUNTS:
                        x_i = 0
                    if abs(y_i) <= REST_ZERO_COUNTS:
                        y_i = 0
            else:
                rest_since = 0.0

            if abs(x_i) <= DEADZONE_COUNTS:
                x_i = 0
            if abs(y_i) <= DEADZONE_COUNTS:
                y_i = 0

            if now - last_send < SEND_INTERVAL_S:
                continue
            last_send = now

            x = clamp(x_i / 127.0, -1.0, 1.0)
            y = clamp(y_i / 127.0, -1.0, 1.0)
            x, y = apply_matrix(x, y, matrix)
            x, y = transform_xy(x, y)
            x = shape_axis(x)
            y = shape_axis(y)
            payload = f"{x:.4f} {y:.4f}\n".encode("ascii")
            sock.sendto(payload, (UDP_HOST, UDP_PORT))

            if DEBUG and LOG_ENABLED:
                print(
                    f"hid=({x_i:4d},{y_i:4d}) "
                    f"bias=({bias_x:+.2f},{bias_y:+.2f}) "
                    f"udp=({x:+.3f},{y:+.3f})"
                )
    except KeyboardInterrupt:
        pass
    finally:
        if dev is not None:
            dev.close()
        sock.close()
        log("Bridge stopped.")


if __name__ == "__main__":
    main()
