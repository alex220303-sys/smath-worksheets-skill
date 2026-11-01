---
name: smath-worksheets
description: "Create, fix and verify SMath Studio worksheets (.sm) on this machine — formulas, Russian comments, working calculation tables. Use for любой расчёт в SMath, .sm файл, «сделай таблицу SMath», «файл не открывается в SMath», красные переменные, подстрочные индексы. Проверено на SMath Studio 1.5: рабочий формат файла, нотация индексов V.ут, вывод значений и проверка открытием."
---

# SMath Studio worksheets (.sm)

Всё ниже проверено в этой сессии на **SMath Studio 1.5.0.9678**
(`C:\Program Files (x86)\SMath Studio\SMathStudio_Desktop.exe`) открытием файлов
и скриншотами. Библиотеки-генератор и парсер лежат рядом: `lib/smscript.py`,
`lib/smread.py`; детали формата — `references/format-notes.md`.

## Четыре правила, без которых файл не работает

| # | Правило | Что бывает при нарушении |
|---|---|---|
| 1 | Шапка и `<settings>` — **только формат 0.88** | SMath падает с диалогом «Ссылка на объект не указывает на экземпляр объекта» |
| 2 | Подстрочный индекс в имени — **через точку**: `V.ут`, `P.н`, `λ.оI` | `el(x, i)` — это элемент массива: переменная не определена, в редакторе **красная**, значение не считается |
| 3 | У определения (`:=`) результат выводится только если в файле есть `<result action="numeric">` | формулы есть, а чисел нет вообще |
| 4 | Высоты областей — «с запасом»: текст с переносом, формулы с двухэтажными дробями | соседние области накладываются друг на друга |

## Правило 1 — рабочий шаблон файла

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<?application progid="SMath Studio" version="0.88"?>
<regions>
  <settings>
    <editable>true</editable>
    <calculation>
      <functions>1</functions>
      <precision>4</precision>
      <angle>radians</angle>
      <fractions>decimal</fractions>
      <recalculation>true</recalculation>
    </calculation>
    <dependences>
      <assembly name="SMath Studio" version="0.88" guid="a37cba83-b69c-4c71-9992-55ff666763bd" />
      <assembly name="Math Region" version="0.88" guid="02f1ab51-215b-466e-a74d-5d8b1cf85e8d" />
      <assembly name="Text Region" version="0.88" guid="485d28c5-349a-48b6-93be-12a35a1c1e39" />
    </dependences>
  </settings>
  <region id="0" left="9" top="9" width="700" height="24" color="#000000" bgColor="#ffffff" fontSize="10">
    <math>
      <input>
        <e type="operand">M</e>
        <e type="operand">28.0134</e>
        <e type="operator" args="2">:</e>
      </input>
      <result action="numeric"><e type="operand">28.0134</e></result>
    </math>
  </region>
</regions>
```

Не делать: `progid="SMath Studio Desktop"`, `xmlns="http://smath.info/schemas/worksheet/1.0"`,
`<settings dpi="96">`, `<identity>`, `<metadata>`, `<paper id="9">`, зависимости
с версией `1.5.0.9678`. Именно этот «современный» блок SMath 1.5 не переваривает,
хотя схема 1.0 встречается в файлах-сниппетах из установки.

## Правило 2 — индексы: точка, а не `el`

Запись `P.н` = <e type="operand">P.н</e> — это имя переменной с нижним индексом
(так в `examples/Beam.sm`: `L.A`, `L.B`). `el(V, ут)` — функция доступа к
элементу массива, для скалярных величин даёт «не определено» и красный цвет.

Практика: если в расчёте величины вида `V.ут`, `V.пр`, `V.исп`, `P.н`, `λ.оI` —
в XML каждый такой операнд должен быть **одним** `<e type="operand">` с точкой
внутри, без отдельных токенов и без `el`.

## Правило 3 — чтобы были видны числа

Определение (`:=`) показывает значение справа («`λ_оI := … = 0,8985`», как в
записке преподавателя) только при наличии:

```xml
<result action="numeric"><e type="operand">0.9203</e></result>
```

Внутри `<math>` после `<input>`. Значение в `<result>` — кэш: округлять до 5–6
значащих цифр, иначе в редакторе появляется хвост `1,33199999999998`. Региону с
результатом нужна высота ≥ 30 px. Для оценки значения без SMath есть
`lib/smread.py: evaluate(regions).definitions`.

## Правило 4 — геометрия областей

SMath не растягивает области: что не влезло — налезает на соседа. Эмпирика,
проверенная скриншотами:

* текст: `высота = 6 + число_строк*line_h`, где строки считаются **с переносом**:
  `chars_per_line ≈ (width − 12) / (0.52 * font_size)`, `line_h ≈ 1.8*font_size`;
* формула: `24 + 26*min(n_div,2) + 10*min(n_pow,2)` px, где `n_div` — число
  операторов `/` (SMath рисует их двухэтажной дробью), `n_pow` — число `^`;
* ширина листа A4 — 850 px, региональная ширина 700 px от `left=9` безопасна;
* `Flow` (см. `lib/smscript.py`) сам двигает курсор вниз на высоту области + gap.

## Как строить

```python
import sys; sys.path.insert(0, r"<skill>/lib")
from smscript import Doc, V, num, assign, sqrt, ln, pi

doc = Doc(font_size=10, title="Расчёт", author="Студент")
f = doc.flow(left=9, top=9, width=700, gap=3, font_size=10)
f.title("НАЗВАНИЕ РАБОТЫ")
f.text("1. ИСХОДНЫЕ ДАННЫЕ", bold=True, font_size=11)
f.assign(V("P", "н"), num(100000))          # P.н := 100000 = 1·10⁵
f.assign(V("T", "н"), V("t", "н") + num(273.15))
f.assign(V("R", "г"), num(8314.46) / V("M"))
doc.save(r"E:\путь\расчёт.sm")               # legacy=True по умолчанию
```

Библиотека сама: пишет формат 0.88, ставит точку в индексы, кэширует `<result>`
(вычисляя выражения своим `env`), считает высоты. Формулы задаются как выражения
на Python-операторах (`+ - * / **`), функции — `sqrt, ln, sin, cos, pi, call(...)`.

## Обязательная проверка после генерации

Не отдавать файл, пока не выполнены оба шага:

```powershell
python <skill>\scripts\check_open.py "E:\путь\файл.sm"     # открылся/ошибка
python <skill>\scripts\screenshot.py "E:\путь\файл.sm" "E:\путь\shot.png"
```

и на скриншот посмотреть глазами: переменные чёрные, справа видны значения,
нет наложений, кириллица читается.

`check_open.py` ловит диалог ошибки SMath и печатает его текст; без него «процесс
запустился» ничего не значит — см. «Ловушки».

## Ловушки этой машины

* Запускать `SMathStudio_Desktop.exe` **с рабочей папкой** = папка установки, иначе
  «Не удается найти указанный файл» даже для корректных файлов.
* Окна принадлежат дочернему процессу **`Solver.exe`** («SMath Solver - [файл.sm]»),
  а launcher завершается сразу с кодом 0. Нельзя судить об успехе по `poll()` —
  ищите окно по заголовку или диалог `#32770`.
* SMath Studio одноэкземплярный: перед каждым тестом
  `taskkill /F /IM Solver.exe` и `/IM SMathStudio_Desktop.exe`, иначе вместо нового
  окна активируется старое.
* Проверка значений без GUI: `lib/smread.py` парсит файл и считает все регионы;
  ключи определений приходят с точкой (`P.н`), при сверке с JSON приводите
  `k.replace(".", "_")`.
* Кириллица в путях работает; но не перезаписывайте .py/.sm файлы через
  PowerShell-пайпы — получается двойная кодировка (писать через `write`/`edit`).

## Когда что читать

* `references/format-notes.md` — полный разбор XML: что подтверждено образцами,
  какие атрибуты допустимы, как устроены регионы и токены (RPN-порядок).
* `lib/smscript.py` — генератор (Doc/Flow/Expr), `lib/smread.py` — парсер и
  вычислитель для сверки значений.
* `examples/minimal.py` — минимальный рабочий пример; `examples/minimal.sm` —
  результат, который открывается.
