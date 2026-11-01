# smath-worksheets

[![CI](https://github.com/alex220303-sys/smath-worksheets-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/alex220303-sys/smath-worksheets-skill/actions/workflows/ci.yml)
![Verified on SMath Studio 1.5.0.9678](https://img.shields.io/badge/verified%20on%20SMath%20Studio-1.5.0.9678-blue)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Agent skill for generating **SMath Studio** worksheets (`.sm`) that actually open,
compute and look right — verified against SMath Studio 1.5.0.9678.

Скилл для агента (DeepSeek Harness / Claude Code / любой системы со `SKILL.md`):
генерация рабочих таблиц SMath Studio с формулами, русскими комментариями и
видимыми результатами.

## Зачем это нужно

Наивная генерация `.sm` даёт файл, который SMath открывает с ошибкой
«Ссылка на объект не указывает на экземпляр объекта», либо файл открывается, но:

* переменные с индексами подсвечены **красным** (`el(x, i)` — это элемент
  массива, а не подстрочный индекс);
* у определений не видно **значений** — только формулы;
* текстовые блоки и дроби **налезают** друг на друга.

Этот репозиторий содержит готовую библиотеку, которая всё это учитывает, и
скрипты проверки, которые открывают файл в настоящем SMath и снимают скриншот.

## Что внутри

| Путь | Назначение |
|---|---|
| `SKILL.md` | сам скилл: 4 правила, шаблон файла, рабочий процесс, ловушки |
| `lib/smscript.py` | генератор листа: `Doc`, `Flow`, выражения, запись формата 0.88 |
| `lib/smread.py` | независимый парсер и вычислитель `.sm` (сверка значений без GUI) |
| `scripts/check_open.py` | открыть `.sm` в SMath и отличить «ОК» от диалога ошибки |
| `scripts/screenshot.py` | открыть, развернуть окно, снять скриншот (визуальная проверка) |
| `references/format-notes.md` | разбор XML-формата: регионы, RPN-токены, ограничения |
| `examples/minimal.py`, `examples/minimal.sm` | минимальный рабочий лист |
| `tests/test_sm.py` | быстрые проверки без SMath: формат, индексы, `<result>`, значения |
| `.github/workflows/` | CI: автотесты на push и ручная проверка открытия в SMath |

## Установка

```powershell
python install.py                 # в C:\Users\<вы>\.dsh\skills\smath-worksheets
python install.py --target "C:\путь\.dsh\skills"
```

Скопировать вручную тоже можно: нужна папка `smath-worksheets` с `SKILL.md`
внутри одного из корней скиллов (`~/.dsh/skills`, `<project>/.dsh/skills`, …).

## Быстрый старт

Установите зависимости (`pip install pywin32 Pillow` — они нужны только для
проверки открытия и скриншотов; сам генератор `lib/smscript.py` обходится
стандартной библиотекой), затем создайте и проверьте лист:

```powershell
pip install pywin32 Pillow
```

```python
import sys; sys.path.insert(0, r"<repo>/lib")
from smscript import Doc, V, num, sqrt

doc = Doc(font_size=10, title="Расчёт", author="Студент")
f = doc.flow(left=9, top=9, width=700, gap=3, font_size=10)
f.title("ТЕРМОДИНАМИЧЕСКИЙ РАСЧЁТ")
f.text("1. ИСХОДНЫЕ ДАННЫЕ", bold=True)
f.assign(V("P", "н"), num(100000))        # P.н := 100000 = 1·10⁵
f.assign(V("a"), sqrt(num(1.4) * num(296.8) * num(293.15)))
doc.save("расчёт.sm")
```

```powershell
python scripts/check_open.py "расчёт.sm"          # ОК / текст ошибки
python scripts/screenshot.py "расчёт.sm" "shot.png"
```

Быстрая самопроверка без SMath (формат, индексы, значения) — одна команда:

```powershell
python tests/test_sm.py --verbose
```

## Как это выглядит

Рабочие листы, сгенерированные этой библиотекой (SMath Studio 1.5, все переменные
определены, справа видны значения):

| Задание № 1 — поршневой компрессор | Задание № 2 — ротационно-пластинчатый |
|---|---|
| ![Задание 1](docs/smath-zadanie1.png) | ![Задание 2](docs/smath-zadanie2.png) |

## Проверки и CI

Что проверяется без SMath (это и есть `tests/test_sm.py`, бейдж CI вверху):

* шапка и `<settings>` — формат 0.88, а не схема 1.0 (иначе SMath 1.5 падает);
* подстрочные индексы записаны точкой (`P.н`), без функции `el()`;
* у определений есть `<result action="numeric">` — без него не видно значений;
* сгенерированный лист разбирается независимым парсером `lib/smread.py`, и
  значения сходятся с эталонными (Π₀, R_г, скорость звука, число ступеней);
* файл `examples/minimal.sm` из репозитория не испорчен;
* оценка высот областей растёт для дробей (иначе блоки налезают друг на друга).

```powershell
python tests/test_sm.py --verbose
```

`.github/workflows/ci.yml` запускает это на каждый push и pull request:
`ubuntu-latest` и `windows-latest`, Python 3.10 и 3.12.

**Чего CI не делает:** не открывает файл в самом SMath Studio. Для этого нужен
Windows с установленным SMath и графической сессией — на облачных раннерах
такого нет. Поэтому реальная проверка открытия вынесена в отдельный ручной
workflow `.github/workflows/smath-open.yml`: **Actions → «SMath open (manual)» →
Run workflow**. Он рассчитан на self-hosted Windows-раннер с метками
`self-hosted`, `windows`, `smath` и дополнительно сохраняет скриншот в артефакты.

## Технические требования

* Windows (SMath Studio — WinForms-приложение), установленный SMath Studio
  (`C:\Program Files (x86)\SMath Studio\SMathStudio_Desktop.exe`).
* Python 3.10+, `pywin32`, `Pillow` — только для скриптов проверки; сама
  библиотека `lib/smscript.py` зависимостей не имеет (стандартная библиотека).

## Ключевые факты формата (коротко)

1. Шапка и `<settings>` — формат **0.88** (`progid="SMath Studio" version="0.88"`).
   Схема 1.0 с `SMath Studio Desktop 1.5.0.9678` роняет SMath 1.5.
2. Подстрочный индекс — точка в имени: `<e type="operand">V.ут</e>`.
3. Определение показывает значение только при `<result action="numeric">`.
4. Высота области: текст — с учётом переноса, формулы — с учётом двухэтажных дробей.

Подробности — в `SKILL.md` и `references/format-notes.md`.

## Лицензия

MIT — см. `LICENSE`.
