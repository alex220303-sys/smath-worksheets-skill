# -*- coding: utf-8 -*-
"""Открыть .sm в SMath Studio, развернуть окно и снять скриншот.

    python screenshot.py <файл.sm> <png> [секунды] [прокрутка]

Прокрутка: отрицательное число — вверх, положительное — вниз (шаги колеса).
Требует pywin32 и Pillow.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

import win32gui
from PIL import ImageGrab

EXE = r"C:\Program Files (x86)\SMath Studio\SMathStudio_Desktop.exe"
SW_MAXIMIZE = 3
MOUSEEVENTF_WHEEL = 0x0800


def kill_stray() -> None:
    for name in ("Solver.exe", "SMathStudio_Desktop.exe"):
        subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    target, png = Path(sys.argv[1]), Path(sys.argv[2])
    wait = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
    scroll = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    kill_stray()
    time.sleep(0.5)
    subprocess.Popen([EXE, str(target)], cwd=str(Path(EXE).parent))

    hwnd = None
    deadline = time.time() + wait
    while time.time() < deadline and hwnd is None:
        time.sleep(0.6)

        def cb(h, _):
            nonlocal hwnd
            t = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and "[" in t and "SMath" in t:
                hwnd = h
            return True

        win32gui.EnumWindows(cb, None)
    if hwnd is None:
        print("окно SMath не найдено (см. check_open.py — вероятно ошибка файла)")
        kill_stray()
        return

    win32gui.ShowWindow(hwnd, SW_MAXIMIZE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:                                       # noqa: BLE001
        pass
    time.sleep(2.0)
    if scroll:
        ctypes.windll.user32.SetCursorPos(*win32gui.GetWindowRect(hwnd)[:2])
        for _ in range(abs(scroll)):
            ctypes.windll.user32.mouse_event(
                MOUSEEVENTF_WHEEL, 0, 0, -120 if scroll > 0 else 120, 0)
            time.sleep(0.05)
        time.sleep(1.0)
    img = ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd), all_screens=True)
    img.save(png)
    print("окно:", win32gui.GetWindowText(hwnd)[:60], "| скриншот:", png, img.size)
    kill_stray()


if __name__ == "__main__":
    main()
