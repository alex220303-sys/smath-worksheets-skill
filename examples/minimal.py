# -*- coding: utf-8 -*-
"""Минимальный рабочий лист SMath: три определения, два с индексами.

    python minimal.py            # создаст minimal.sm рядом с этим файлом

Проверка: python ../scripts/check_open.py minimal.sm → ОК
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from smscript import Doc, V, num, sqrt, ln   # noqa: E402

doc = Doc(font_size=10, title="Минимальный пример",
          author="SMath Studio skill")
f = doc.flow(left=9, top=9, width=700, gap=3, font_size=10)

f.title("МИНИМАЛЬНЫЙ РАБОЧИЙ ЛИСТ")
f.text("Проверка формата 0.88, индексов через точку и вывода результатов.")

f.text("1. ИСХОДНЫЕ ДАННЫЕ", bold=True, font_size=11)
f.assign(V("P", "н"), num(100000))                 # P.н := 100000
f.assign(V("P", "к"), num(1200000))                # P.к := 1200000
f.assign(V("k"), num(1.4))
f.assign(V("T", "н"), num(20) + num(273.15))
f.assign(V("R", "г"), num(8314.46) / num(28.0134))

f.text("2. РАСЧЁТ", bold=True, font_size=11)
f.assign(V("П", "0"), V("P", "к") / V("P", "н"))   # Π.0 := P.к/P.н = 12
f.assign(V("a"), sqrt(V("k") * V("R", "г") * V("T", "н")))
f.assign(V("z"), ln(V("П", "0")) / ln(num(3.5)))

doc.save(HERE / "minimal.sm")
print("готово:", HERE / "minimal.sm")
