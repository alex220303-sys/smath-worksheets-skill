# smscript / smread — SMath Studio worksheet (.sm) generation notes

> **ВАЖНО (проверено 2026-11-01, SMath Studio 1.5.0.9678).** Заметки ниже
> написаны до того, как файлы начали реально открываться в SMath, и в двух
> местах они **неверны**:
>
> 1. *Шапка/`<settings>` схемы 1.0* (`progid="SMath Studio Desktop"`,
>    `xmlns=…worksheet/1.0`, `<settings dpi>`, `<identity>`, `<paper id="9">`,
>    зависимости версии 1.5.0.9678) — SMath падает на таком файле
>    («Ссылка на объект не указывает на экземпляр объекта»). Рабочий формат —
>    **0.88**, как в `088_formulas.sm`; теперь `Doc.save()` пишет именно его
>    (`legacy=True`, см. `_settings_element_legacy`).
> 2. *Подстрочный индекс через `el(name, sub)`* — это доступ к элементу массива:
>    переменная оказывается неопределённой и красной. Индекс в имени пишется
>    точкой: `P.н`, `V.ут`, `λ.оI` (подтверждено `examples/Beam.sm`: `L.A`, `L.B`).
> 3. Результат у определения (`:=`) отображается только при наличии
>    `<result action="numeric">` в регионе — добавлено в `Doc.math`.
> 4. Высоты областей: текст считается с переносом строк, формула — с учётом
>    двухэтажных дробей (иначе области накладываются).
>
> Остальное (RPN-порядок токенов, регионы, атрибуты, ограничения приложения)
> ниже остаётся верным.

Everything here was reverse-engineered from the SMath Studio 1.5.0 distribution
that is extracted at `E:\AI\work\smath\app` (57 `.sm` files in `book/`,
`examples/`, `snippets/`).  The file-format vocabulary was cross-checked against
the strings of the real reader `/plugins/8ec52daf-.../SMathFileType.dll`
(assembly `SMathFileType, Version=1.75.9678.0`, i.e. the plugin that ships with
1.5.0.9678).  Every construct the library emits is copied from at least one
sample; the sample is named below and again in the docstring of the code that
emits it.

* `smscript.py`  — build a document (`Doc`, `Flow`, expression tree) and save it.
* `smread.py`    — parse a `.sm` back (`parse`) and execute its RPN (`evaluate`).
  It is an independent implementation on purpose: `selftest.py` proves that the
  bytes `smscript` writes are understood by a second interpreter.
* `selftest.py`  — builds `demo.sm`, re-parses, re-evaluates and compares with
  plain-Python reference values; also round-trips an edge-case sheet, a units
  sheet, and the whole 57-file distribution corpus.

> The SMath Studio executable **does** have a console mode
> (`SMathStudio_Desktop.exe file.sm -s -t -b`, `-s|-silent`, `-t|-test`,
> `-e|-export`), but in this installation every automation command aborts with
> *“Automation and integration features are not available.  Please check your
> license.”*  So the app cannot be used as an oracle here — do not burn time on
> it unless a license is installed.

---

## 1. Code example (builds a sheet with a heading, three assignments and one
##    displayed result)

```python
from smscript import Doc, Flow, V, num, sin, cos, sqrt, pi, assign

doc = Doc(page_setup="A4", font_size=10, title="Demo sheet")
f = doc.flow(width=600)          # vertical cursor; top follows the sheet

f.title("Crank mechanism")
f.text("Input data", bold=True)
f.math(assign(V("r"), num(0.05)))                       # r := 0.05
f.math(assign(V("l"), num(0.2)))                        # l := 0.2
f.math(assign(V("phi"), num(30) * pi / num(180)))       # phi := 30*pi/180

f.text("Result", bold=True)
f.math(V("r") * sin(V("phi")) / V("l"))                 # shows "... = 0.125"

doc.save("demo.sm")
```

The result region is emitted exactly like `examples/Beam.sm` region 57 does it:
`<input>` carries the expression, a cached `<result action="numeric">` carries
the number (that is how SMath displays a value — there is no trailing `=` token).

---

## 2. Exact file skeleton

```
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<?application progid="SMath Studio Desktop" version="1.5.0.9678"?>
<regions xmlns="http://smath.info/schemas/worksheet/1.0">
  <settings dpi="96">
    <identity><id>GUID</id><revision>2</revision></identity>
    <metadata><title>..</title><author>..</author><description>..</description>
              <company>..</company><keywords>..</keywords></metadata>   <!-- optional -->
    <calculation><precision>4</precision><exponentialThreshold>5</exponentialThreshold>
                 <fractions>decimal</fractions></calculation>
    <pageModel active="false" viewMode="2" printGrid="false" printAreas="false"
               simpleEqualsOnly="true" printBackgroundImages="true">
      <paper id="9" orientation="Portrait" width="827" height="1169" />
      <margins left="39" right="39" top="39" bottom="39" />
      <header .../>  <footer .../>          <!-- optional -->
      <backgrounds />
    </pageModel>
    <dependencies>
      <assembly name="SMath Studio Desktop" version="1.5.0.9678" guid="a37cba83-b69c-4c71-9992-55ff666763bd" />
      <assembly name="Math Region"          version="1.5.0.9678" guid="02f1ab51-215b-466e-a74d-5d8b1cf85e8d" />
      <assembly name="Text Region"          version="1.5.0.9678" guid="485d28c5-349a-48b6-93be-12a35a1c1e39" />
    </dependencies>
  </settings>
  <region id="0" left="9" top="9" width="560" height="31" color="#0000ff"
          bgColor="#ffffff" fontSize="14">
    <text><p bold="true">Heading</p></text>
  </region>
  <region id="1" left="9" top="44" width="320" height="24" color="#000000"
          bgColor="#ffffff" fontSize="12">
    <math>
      <input>
        <e type="operand">a</e>
        <e type="operand">3</e>
        <e type="operator" args="2">:</e>
      </input>
    </math>
  </region>
</regions>
```

The file is written as **UTF-8 with BOM** (all samples start with `EF BB BF`).
`<settings>` comes first, regions follow in ascending `id` order.

### 2.1 Elements / attributes the library relies on (and where they are attested)

| element / attribute | meaning | attested in |
|---|---|---|
| `<?application progid= version=?>` | which app wrote the file | every sample |
| `<regions xmlns="http://smath.info/schemas/worksheet/1.0">` | schema namespace (the 0.55 `book/*.sm` files have no namespace and use `font-size`/`background-color`) | `examples/Beam.sm`, `snippets/DegreeAngles.sm` |
| `<settings dpi="96">` | sheet defaults | `Beam.sm` |
| `<identity><id><revision>` | document identity | `Beam.sm`, `book/contents.sm` |
| `<metadata lang="..">` + `title/author/description/company/keywords` | document properties | `Beam.sm` |
| `<calculation><precision>/<exponentialThreshold>/<fractions>` | display precision 4, `decimal` | `Beam.sm`, `DegreeAngles.sm` |
| `<pageModel active viewMode printGrid printAreas simpleEqualsOnly printBackgroundImages>` | page model flags | `Beam.sm` |
| `<paper id orientation width height>` | size in **1/100 inch**; A4 = 827×1169 with `id="9"`, Letter = 850×1100 with `id="1"` | `Beam.sm` (A4), `DegreeAngles.sm` (Letter) |
| `<margins left right top bottom>` | margins, 1/100 inch | `Beam.sm` |
| `<backgrounds />` | empty background list (required element) | `Beam.sm` |
| `<dependencies><assembly name version guid>` | which plugins the sheet needs | `Beam.sm` (legacy spelling `dependences` is also recognised by the plugin: `DegreeAngles.sm`) |
| `<region id left top width height [border] color bgColor fontSize>` | a region; coordinates are px relative to the **printable area** (inside the margins), `color`/`bgColor`/`fontSize` are inherited by its content | `Beam.sm` region 46 (`border="true"`), region 57 |
| `<text [lang]>` `<p [bold] [href] [build-in]>` | text region; **one** `<p>` per `<text>`, line breaks are literal `\n` inside the `<p>` | `Beam.sm` region 8 (two-line `<p>`), `book/1.sm` (`bold`), `book/1_1.sm` (`href`) |
| `<math>` `<input>` `<e …>` | math region; `<input>` holds the postfix expression | `Beam.sm`; legacy 0.55 files put `<e>` directly in `<math>` (`book/4_1.sm`) |
| `<result action="numeric">` | cached evaluated value = what SMath displays | `Beam.sm` region 57, `Simpson.sm` region 10 |
| `<contract>` | result **unit** presentation (`kN`) | `Beam.sm` region 57 |
| `<e type="operand" [style="unit"/"string"]>text</e>` | literal / variable / unit / string | units: `Beam.sm`, `GravitationAcceleration.sm`, `DegreeAngles.sm`; string: `GravitationAcceleration.sm` (`The Sun`) |
| `<e type="operator" args="N">op</e>` | operator, N = operand count | everywhere |
| `<e type="function" args="N">name</e>` | function/command, N = argument count | everywhere |
| `<e type="bracket">(</e>` | bracket marker (see §3.4) | `book/1_1.sm`, `book/5_3.sm`, `book/10_2.sm` |

Operator spellings that exist in the corpus (the library only emits the first
group): `+ - * / ^ : = ≤ ≥ ≠ < > ≡ ± % & | !` (`!` = factorial, `:` = `:=`,
`≡` = definition with display, `±` is a two-argument plus/minus).

---

## 3. RPN rules (the part that is easy to get wrong)

A math region is a **postfix** list. There is no tree in the XML, no closing
bracket, no parenthesis nesting — just a flat list of `<e>` elements that a
stack machine reduces left to right.

### 3.1 Operands
An `<e type="operand">` pushes one value. The text is the literal:
`0.14778393974594012`, `1.4`, `x`, `π`, `β`, `R.ogr`, `10`, `∞`, `e`.
* Numbers never use exponent notation in the corpus — magnitudes are written
  `mantissa 10 exp ^ *`, e.g. `6.6728*10^(-11)` in
  `examples/GravitationAcceleration.sm`. `_num_tokens()` does the same
  (`6.6728`, `10`, `11`, unary `-`, `^`, `*`).
* Constants are plain operands: `π` (`book/4_1.sm`), `e` (`book/4_2.sm`),
  `∞` (`book/10_2.sm`).
* Greek letters are single Unicode characters in the operand text (`α β γ π φ λ
  ξ σ`).

### 3.2 Operators, `args`, unary minus
`args="N"` = how many stack items the operator consumes. Order in the token
stream is the natural left-to-right reading order, so
`a + b` → `<e>a</e><e>b</e><e args="2">+</e>`.
* binary: `+ - * / ^ : = ≤ ≥ ≠ < > ≡ ± % & |` all `args="2"`
* unary minus: `<e args="1">-</e>` after its operand —
  `10^(-11)` → `10`, `11`, `-`(args 1), `^`(args 2)
  (`GravitationAcceleration.sm`; also `book/4_2.sm` for `e^-α`).
* postfix factorial: `args="1"` `!` (`book/10_2.sm`).

### 3.3 Functions
`args="N"` = number of preceding stack items that are the arguments:
`sin(x)` → `<e>x</e><e type="function" args="1">sin</e>`.
Multi-argument functions push their arguments in reading order before the
function element; two special four-argument forms put the *body* first and the
control operands last:

```
sum(body, k, from, to)   ->  <body tokens> k from to  <e args="4">sum</e>
int(body, x, from, to)   ->  <body tokens> x from to  <e args="4">int</e>
if(cond, a, b)           ->  <cond> <a> <b>  <e args="3">if</e>
```
(`examples/Simpson.sm` regions 8 and 12, `Dichotomy.sm` region 14.)

`el` is SMath's **subscript pseudo-function**:
`x₁` → `<e>x</e><e>1</e><e type="function" args="2">el</e>`
(`examples/Thomas.sm` region 2), and `el(A, i, j)` with `args="3"` is a matrix
element (`GravitationAcceleration.sm` region 9). The library uses `el`/2 for all
subscripted identifiers.

### 3.4 Brackets — the trick
`<e type="bracket">(</e>` is **only ever `(`**, never `)`, and it does *not*
consume a stack item. It is emitted **after** the tokens of the sub-expression it
parenthesises, i.e. at the point where that sub-expression has just been
completed:

```
(a·b)^m      ->  a b *  (  m ^          (book/1_1.sm region 12)
(a^m)^n      ->  a m ^  (  n ^          (book/1_1.sm region 18)
(c·2·n - 1)  ->  c 2 * n * 1 -  (  =    (book/5_3.sm region 17)
```
This is exactly what `Expr._emit(ctx)` produces: a child is bracketed when its
precedence is lower than the context requires. `smread.build_tree()` treats the
marker as a no-op, which is also how evaluation is unaffected.

### 3.5 `:=` versus `=` (results)
* Definition: `<lhs tokens> <rhs tokens> <e type="operator" args="2">:</e>`
  (`a := 1` → `a 1 :`, `examples/Simpson.sm` region 3). A definition region has
  **no** `<result>` child; SMath shows just the definition.
* Display of a value: the region's `<input>` is the bare expression and the value
  lives in `<result action="numeric">` (`Beam.sm` region 57:
  `<input><e>R.A</e></input><contract>kN</contract><result action="numeric">
  <e>12.4533</e><e args="1">-</e></result>` — note the unary minus for −12.4533
  and that units are kept in `<contract>`, not in the number).
  `smscript.Doc.math()` computes the value in Python and writes that cache, so a
  freshly generated sheet already shows numbers; SMath recomputes on load
  anyway.
* The old `book/*.sm` files sometimes carry a binary `=` operator for equations
  (`α sin α cos / =` in `book/4_2.sm`); the library can emit it with
  `equation(lhs, rhs)` but does not use it for results.

### 3.6 Identifiers: Greek, subscripts, primes
* Greek: just put the Unicode character in the operand text.
* Subscripts: `V` with subscript `т` → `V`, `т`, `el`(args 2). In the Python API:
  `V("V", sub="т")` or `V("R", sub="огр")`. Round-trips as the key `V_т` /
  `R_огр` in `smread`.
* Documents also contain dotted names (`R.A`, `M.obj`, `arrow.F` in `Beam.sm`
  and `GravitationAcceleration.sm`); those are plain operand text and are
  emitted verbatim.
* **Primes are not attested anywhere in the corpus.** If you need `Pн'`, put the
  apostrophe in the name (`V("Pн'")`) — it is emitted verbatim, but nobody has
  verified that SMath's reader accepts it. Prefer a subscript.

### 3.7 Units
A unit is an operand with `style="unit"`; compound units are built with the
ordinary operators: `10^5 Pa` → `10 5 ^ Pa[unit] *`, `kg/(m·s²)` →
`kg[unit] m[unit] s[unit] 2 ^ * /` (`examples/Beam.sm` regions 2/12,
`examples/GravitationAcceleration.sm` region 3, `snippets/DegreeAngles.sm` for
`°` and `deg`).
Caveats (see §6): `smread` treats a unit operand as the factor 1 (except
`°`/`deg` = π/180), and a region whose expression contains units gets **no**
cached `<result>` (we cannot know the result's unit), so SMath has to compute it.

---

## 4. Layout / geometry

* Coordinates are pixels inside the printable area; 1/100 inch squared for paper.
* Row pitch of a `fontSize="10"` block is 18 px; `examples/Beam.sm` uses region
  heights 24 (plain text/math), 30 (one line with a result), 45–80 (powers,
  matrices, multi-line blocks) and tops 9, 45, 72, 90, 108, …
* `Doc`/`Flow` reproduce that: text height = `6 + lines*round(1.8*fontSize)`,
  math height = `24 + 14*min(#divisions,3) + 8*min(#powers,2)`.
  Heights are deliberately **generous** — SMath clips a region's content to its
  box, so too small is fatal while too large only adds whitespace.
* Widths default to `max(260, estimated_visual_width*7.6+30)` clamped to 820;
  `Flow(width=…)` sets the column width. Long formulas should get 400–700 px.
* `Flow` stacks regions, returns the region, and exposes `next_top()`.
  `Doc.next_top()` / `Doc.next_left()` give the free space for a new column.
* `Doc.title()` = `fontSize 14`, bold, `color="#0000ff"` (as in `Beam.sm`).

## 5. Page setup

```python
Doc(page_setup="A4")                                   # A4 portrait, 10 mm margins
Doc(page_setup=PageSetup(margins=(39,39,39,39),        # left right top bottom, 1/100 in
                         header="&[DATE] &[FILENAME]",
                         footer="&[PAGENUM] / &[COUNT]",
                         precision=6, exponential_threshold=3,
                         fractions="decimal"))         # pageModel/calculation contents
Doc(page_setup=PageSetup(paper="Letter"))              # 850x1100, paper id 1
Doc(page_setup=PageSetup(paper=(1000, 1400, 9)))       # custom width/height/paper-id
```
`PageSetup(orientation="Landscape")` swaps width/height.  Only A4 and Letter are
attested; any other size must be passed as an explicit
`(width, height, paper_id)` triple.

---

## 6. What is *not* supported (deliberately)

| construct | why / what to do |
|---|---|
| `solve(...)` | never appears in the corpus, argument encoding unknown — `smscript.solve()` raises with this message. Rewrite as `root(lhs-rhs, var)` or leave the equation for SMath. |
| plots (`<plot …>`) | `<plot>` exists (`Beam.sm` region 47) but carries plotter state (`scale_x`, `transpose_y`, …) produced by the Plot plug-in; hand-made values are risky. Not emitted. |
| matrices / vectors (`mat`, `line`, `stack`, `el`/3) | encoding is known (`entries… rows cols mat/args`) from `Thomas.sm` region 1 and `Beam.sm` region 9, but not implemented in the generator. `smread` parses them but cannot evaluate them. |
| programming constructs (`for/3`, `while/2`, `line/4`), `lim/3`, `diff`, `∫` with symbolic bounds | parse-level only in `smread`; never emitted. |
| `exp(x)` | the name `exp` is not attested; `smscript.exp(x)` emits `e^x`, which is (`book/4_2.sm`). |
| `italic="true"` / `underline="true"` on `<p>` | not attested in any sample (only `bold`, `href`, `build-in`). Emitted when requested — the modern TextRegion is HTML-based (`span`/`style`), so an unknown attribute is ignored rather than fatal, but treat the rendering as unverified. |
| unit-bearing results with a cached number | `<result>`+`<contract>` is attested, but the unit algebra is not modelled; the library omits `<result>` for such regions and lets SMath compute. Use `allow_units=False` on the `Doc` to make units an error instead. |
| tables | the tag does not exist anywhere in the corpus. |
| multi-language text (`<text lang="eng">`) | attested, but a region tagged for one language may be hidden when the SMath UI is in another language. The library omits `lang` (that is the legacy 0.55 behaviour and always displays). |

## 7. Numbers used by the shipped selftest

The task statement pins `R=0.147783, e=0.0177340, c=12.439205, L=0.517241,
n=774.267`.  Evaluating the *given formulas* gives

```
c = 12.439205227623242     R = 0.14778393974594012
e = 0.017734072769512815   L = 0.5172437891107904    n = 775.3992701992008
```

i.e. `c`, `e` and `R` agree to the stated digits, `L` differs in the 6th digit
and `n` differs by 1.5e-3 relative (`774.267` would need `R ≈ 0.1480` or a
different `U`).  The selftest therefore asserts the **formulas** at 1e-9
relative against independent Python values and only reports the literals.
