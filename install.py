# -*- coding: utf-8 -*-
"""Установка скилла smath-worksheets в DSH.

    python install.py
    python install.py --target "C:\\путь\\.dsh\\skills"
    python install.py --list           # показать корни скиллов

Копирует SKILL.md, README.md, lib/, scripts/, references/, examples/ в
<target>/smath-worksheets/. Существующая установка перезаписывается
(старая версия сохраняется рядом как .bak-YYYYMMDD).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS = ["SKILL.md", "README.md", "LICENSE", "install.py",
         "lib", "scripts", "references", "examples"]
SKIP_SUFFIXES = {".pyc", ".png"}


def skill_roots() -> list[Path]:
    home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh"))
    return [Path.cwd() / ".dsh" / "skills",
            Path.cwd() / ".agents" / "skills",
            home / "skills",
            Path.home() / ".agents" / "skills"]


def install(target: Path) -> Path:
    dest = target / "smath-worksheets"
    if dest.exists():
        backup = dest.with_name(dest.name + ".bak-" + dt.date.today().strftime("%Y%m%d"))
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        shutil.copytree(dest, backup)
        print("старая версия сохранена:", backup)
    dest.mkdir(parents=True, exist_ok=True)
    for item in ITEMS:
        src = HERE / item
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest / item, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*SKIP_SUFFIXES))
        else:
            shutil.copy2(src, dest / item)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", help="корень скиллов (по умолчанию ~/.dsh/skills)")
    ap.add_argument("--list", action="store_true", help="показать корни")
    a = ap.parse_args()

    if a.list:
        for r in skill_roots():
            print(("есть  " if r.is_dir() else "нет   ") + str(r))
        return

    target = Path(a.target) if a.target else skill_roots()[2]
    dest = install(target)
    n = sum(1 for p in dest.rglob("*") if p.is_file())
    print("установлено в", dest, "(файлов: %d)" % n)
    print("скилл подхватится на следующем шаге модели (каталог перечитывается).")


if __name__ == "__main__":
    main()
