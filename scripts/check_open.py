# -*- coding: utf-8 -*-
"""Проверить, открывается ли .sm в SMath Studio (без диалога ошибки).

    python check_open.py <файл|папка> [<файл|папка> ...]

Успех  — окно «SMath Solver - [имя файла]», ошибка — диалог #32770 с текстом.
Печатает строку на каждый файл и итог. Требует pywin32 (win32gui).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import win32gui

EXE = r"C:\Program Files (x86)\SMath Studio\SMathStudio_Desktop.exe"


def kill_stray() -> None:
    for name in ("Solver.exe", "SMathStudio_Desktop.exe"):
        subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)


def windows():
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            out.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def child_texts(hwnd):
    out = []

    def cb(h, _):
        t = win32gui.GetWindowText(h)
        if t.strip():
            out.append(t)
        return True

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:                                       # noqa: BLE001
        pass
    return out


def open_ok(path: Path, wait: float = 20.0) -> str:
    """20 с — холодный старт SMath после taskkill бывает медленным."""
    path = path.resolve()          # SMath запускается с cwd = папка установки,
                                   # относительный путь он там и будет искать
    kill_stray()
    time.sleep(0.4)
    # рабочая папка ОБЯЗАТЕЛЬНО папка установки, иначе SMath не находит сборки
    subprocess.Popen([EXE, str(path)], cwd=str(Path(EXE).parent))
    deadline = time.time() + wait
    status = "нет окна SMath за %.0f с" % wait
    while time.time() < deadline:
        time.sleep(0.5)
        for h, cls, title in windows():
            if cls == "#32770" and ("SMath" in title or "Solver" in title):
                txt = " | ".join(child_texts(h))[:220]
                kill_stray()
                return "ОШИБКА: " + (txt or title)
            if "SMath" in title and "[" in title:
                if path.name.lower() in title.lower():
                    kill_stray()
                    return "ОК"
                status = "открыто другое окно: %r" % title[:80]
    kill_stray()
    return status


def main() -> None:
    targets: list[Path] = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            targets += sorted(p.rglob("*.sm"))
        elif p.is_file():
            targets.append(p)
    if not targets:
        print(__doc__)
        return
    print("проверяю файлов:", len(targets), flush=True)
    bad = []
    for i, t in enumerate(targets, 1):
        res = open_ok(t)
        print("[%2d/%d] %-44s %s" % (i, len(targets), t.name, res), flush=True)
        if res != "ОК":
            bad.append((t, res))
    print("\nитого: файлов %d, не открылись %d" % (len(targets), len(bad)))
    for t, res in bad:
        print("   ", t, "->", res)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
