# -*- coding: utf-8 -*-
"""Проверки без SMath Studio — то, что можно гонять в CI на любом раннере.

    python tests/test_sm.py [--verbose]

Проверяется то, из-за чего файлы раньше не открывались:
  * шапка и <settings> — формат 0.88 (не схема 1.0);
  * подстрочные индексы — одной точкой в операнде, без функции el();
  * у определений есть <result action="numeric">, иначе значения не видны;
  * сгенерированный лист читается независимым парсером (lib/smread.py) и
    значения сходятся с эталонными;
  * файл examples/minimal.sm в репозитории не испорчен.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import smread                     # noqa: E402
from smscript import Doc, V, num, sqrt, ln   # noqa: E402

VERBOSE = "--verbose" in sys.argv
FAILED: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        if VERBOSE:
            print("  ok  ", msg)
        return
    FAILED.append(msg)
    print("  FAIL", msg)


def expect_close(got, want, tol, msg) -> None:
    ok = got is not None and abs(got - want) <= tol * max(1.0, abs(want))
    check(ok, "%s (получено %r, ожидалось %r)" % (msg, got, want))


def build_sheet(path: Path) -> None:
    doc = Doc(font_size=10, title="CI check", author="CI")
    f = doc.flow(left=9, top=9, width=700, gap=3, font_size=10)
    f.text("ПРОВЕРКА")
    f.assign(V("P", "н"), num(100000))
    f.assign(V("P", "к"), num(1200000))
    f.assign(V("k"), num(1.4))
    f.assign(V("T", "н"), num(20) + num(273.15))
    f.assign(V("R", "г"), num(8314.46) / num(28.0134))
    f.assign(V("П", "0"), V("P", "к") / V("P", "н"))
    f.assign(V("a"), sqrt(V("k") * V("R", "г") * V("T", "н")))
    f.assign(V("z"), ln(V("П", "0")) / ln(num(3.5)))
    doc.save(path)


def test_generated(tmp: Path) -> None:
    print("1. Генерация листа и формат файла")
    p = tmp / "ci.sm"
    build_sheet(p)
    check(p.exists() and p.stat().st_size > 500, "файл создан и не пустой")
    raw = p.read_bytes()
    # SMath пишет файлы с BOM (так же выглядят образцы из поставки) — это норма
    check(raw.startswith(b"\xef\xbb\xbf"), "файл начинается с UTF-8 BOM (как образцы SMath)")
    text = raw.decode("utf-8-sig")

    check(text.startswith('<?xml version="1.0" encoding="utf-8"'), "XML-заголовок на месте")
    check('progid="SMath Studio" version="0.88"' in text,
          "шапка формата 0.88 (иначе SMath 1.5 падает)")
    check('progid="SMath Studio Desktop"' not in text,
          "нет шапки «SMath Studio Desktop» (она ломает открытие)")
    check("xmlns" not in text.split("?>")[2][:200],
          "нет namespace схемы 1.0 у корневого элемента")
    check("<editable>true</editable>" in text, "блок <settings> формата 0.88")
    check(">el<" not in text, "подстрочные индексы не через el() (это элемент массива)")
    check('type="operand">P.н<' in text, "индекс записан точкой: P.н")
    check(text.count('<result action="numeric">') >= 6,
          "у определений есть <result> (иначе значения не отображаются)")

    print("2. Независимый разбор и счёт (lib/smread.py)")
    ws = smread.parse(p)
    res = smread.evaluate(ws.regions)
    check(not res.errors, "нет ошибок вычисления (%s)" % (res.errors or "нет"))
    env = {k.replace(".", "_"): v for k, v in res.definitions.items()}
    expect_close(env.get("П_0"), 12.0, 1e-12, "Π.0 = P.к/P.н = 12")
    expect_close(env.get("T_н"), 293.15, 1e-12, "T.н = 20 + 273,15")
    expect_close(env.get("R_г"), 296.803, 1e-3, "R.г = 8314,46/28,0134")
    expect_close(env.get("a"), 349.01, 1e-2, "a = √(k·R.г·T.н)")
    expect_close(env.get("z"), 1.9835, 1e-3, "z = ln(Π.0)/ln(3,5)")


def test_committed_example() -> None:
    print("3. Файл examples/minimal.sm из репозитория")
    p = ROOT / "examples" / "minimal.sm"
    check(p.exists(), "файл на месте")
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    check('version="0.88"' in text, "в файле формат 0.88")
    check(">el<" not in text, "нет el() в индексах")
    ws = smread.parse(p)
    res = smread.evaluate(ws.regions)
    check(not res.errors, "пример разбирается без ошибок (%s)" % (res.errors or "нет"))
    env = {k.replace(".", "_"): v for k, v in res.definitions.items()}
    expect_close(env.get("П_0"), 12.0, 1e-12, "minimal.sm: Π.0 = 12")
    expect_close(env.get("R_г"), 296.803, 1e-3, "minimal.sm: R.г = 296,803")


def test_heights() -> None:
    print("4. Оценка высот областей (наложения)")
    from smscript import estimate_height
    toks_plain = [("operand", "a", None), ("operand", "2", None),
                  ("operator", ":", 2)]
    toks_frac = [("operand", "a", None), ("operand", "b", None),
                 ("operator", "/", 2)]
    check(estimate_height(toks_plain) >= 24, "простая строка — минимум 24 px")
    check(estimate_height(toks_frac) > estimate_height(toks_plain),
          "дробь выше простой строки (иначе налезает на соседей)")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        test_generated(Path(d))
    test_committed_example()
    test_heights()
    print()
    if FAILED:
        print("ПРОВАЛЕНО проверок: %d" % len(FAILED))
        for m in FAILED:
            print("  -", m)
        return 1
    print("Все проверки пройдены.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
