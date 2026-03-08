"""
Bridge STM32 Custom HID (2-axis report) to middle-mouse drag control.

Tested logic:
- Reads HID device with VID:PID 0483:A4F1
- Converts X/Y report into short MMB-drag impulses
- Releases MMB after idle timeout to avoid stuck button
"""

import time

import hid  # pip install hidapi
from pynput.mouse import Button, Controller  # pip install pynput
from pynput.keyboard import Controller as KeyboardController, Key

VID = 0x0483
PID = 0xA4F1

DEADZONE = 2
SCALE = 2
POLL_TIMEOUT_MS = 20
IDLE_RELEASE_S = 0.08
USE_SHIFT_FOR_ORBIT = True
DEBUG = True


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


def main() -> None:
    mouse = Controller()
    keyboard = KeyboardController()
    dev = hid.device()

    devices = hid.enumerate(VID, PID)
    if not devices:
        raise RuntimeError(f"HID {VID:04X}:{PID:04X} not found")

    if DEBUG:
        print(f"Found {len(devices)} HID interface(s)")
        for idx, d in enumerate(devices):
            print(
                f"[{idx}] usage_page=0x{d.get('usage_page', 0):X} "
                f"usage=0x{d.get('usage', 0):X} path={d.get('path')}"
            )

    # Prefer Generic Desktop / Multi-axis Controller interface if available.
    selected = devices[0]
    for d in devices:
        if d.get("usage_page") == 0x01 and d.get("usage") == 0x08:
            selected = d
            break

    dev.open_path(selected["path"])
    dev.set_nonblocking(True)

    print(f"Connected HID {VID:04X}:{PID:04X} path={selected['path']}")
    print("Bridge active. Press Ctrl+C to stop.")

    middle_pressed = False
    shift_pressed = False
    last_move_ts = 0.0
    last_report_ts = time.time()

    try:
        while True:
            data = dev.read(64, POLL_TIMEOUT_MS)
            if not data:
                now = time.time()
                if middle_pressed and (now - last_move_ts) > IDLE_RELEASE_S:
                    mouse.release(Button.middle)
                    middle_pressed = False
                    if shift_pressed:
                        keyboard.release(Key.shift)
                        shift_pressed = False
                if DEBUG and (now - last_report_ts) > 2.0:
                    print("No HID reports in the last 2s")
                    last_report_ts = now
                continue

            x, y = decode_xy(bytes(data))
            last_report_ts = time.time()
            if DEBUG:
                print(f"report={list(data[:4])} decoded=({x},{y})")

            if abs(x) <= DEADZONE:
                x = 0
            if abs(y) <= DEADZONE:
                y = 0

            if x == 0 and y == 0:
                now = time.time()
                if middle_pressed and (now - last_move_ts) > IDLE_RELEASE_S:
                    mouse.release(Button.middle)
                    middle_pressed = False
                    if shift_pressed:
                        keyboard.release(Key.shift)
                        shift_pressed = False
                continue

            if not middle_pressed:
                if USE_SHIFT_FOR_ORBIT and not shift_pressed:
                    keyboard.press(Key.shift)
                    shift_pressed = True
                mouse.press(Button.middle)
                middle_pressed = True

            mouse.move(x * SCALE, y * SCALE)
            last_move_ts = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        if middle_pressed:
            mouse.release(Button.middle)
        if shift_pressed:
            keyboard.release(Key.shift)
        dev.close()
        print("Bridge stopped.")


if __name__ == "__main__":
    main()
