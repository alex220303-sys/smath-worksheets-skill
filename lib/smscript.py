"""smscript.py -- build SMath Studio worksheet files (.sm) from Python.

Self-contained (stdlib only).  Format knowledge derived from the SMath Studio
1.5.0 distribution corpus (see NOTES.md for the per-construct attestations).

Public API (stable):
    Doc, PageSetup, Flow
    V / var(name, sub=...), num(v) / N(v), pi, e_const
    number formatting/helpers: fmt_num
    operators:  binary node classes Add, Sub, Mul, Div, Pow + python operators
    functions:  sin cos tan asin acos atan sqrt exp ln log abs_ if_ mod sign
                sqrt root nth_root sum product integ min_ max_
    assign(target, expr)   -> "target := expr"
    funcdef(name, params, body)
    equation(lhs, rhs)     -> "lhs = rhs"
    Units: unit("m") and multiplication by Exprs

Example
-------
    from smscript import Doc, V, num, sin, pi, assign
    d = Doc(title="demo")
    f = d.flow()
    f.title("Demo")
    f.math(assign(V("a"), num(3)))
    f.math(V("a") * sin(pi / 4))
    d.save("demo.sm")
"""

from __future__ import annotations

import math
import os
import uuid
import xml.etree.ElementTree as ET

NS = "http://smath.info/schemas/worksheet/1.0"

# Version string copied verbatim from the format the 1.5.0 app writes/reads.
# (samples: examples/Beam.sm declares 0.98.6606.22069; room for both because the
#  file plugin in app/plugins/8ec52daf-.../SMathFileType.dll recognises the same
#  schema namespace, "dependencies" *and* the legacy "dependences" spelling.)
APP_PROGID = "SMath Studio Desktop"
APP_VERSION = "1.5.0.9678"          # = SMathStudio_Desktop.exe FileVersion

# Формат 0.88 — единственный, который SMath Studio 1.5.0.9678 гарантированно
# открывает (проверено на 088_formulas.sm и на сгенерированных файлах).
LEGACY_PROGID = "SMath Studio"
LEGACY_VERSION = "0.88"

GUID_APP = "a37cba83-b69c-4c71-9992-55ff666763bd"   # from Beam.sm
GUID_MATH = "02f1ab51-215b-466e-a74d-5d8b1cf85e8d"  # "Math Region"      (Beam.sm)
GUID_TEXT = "485d28c5-349a-48b6-93be-12a35a1c1e39"  # "Text Region"      (Beam.sm)

DEFAULT_COLOR = "#000000"
DEFAULT_BG = "#ffffff"

# ---------------------------------------------------------------------------
# papers.  width/height are in 1/100 inch: A4 = 827 x 1169 (Beam.sm), Letter =
# 850 x 1100 with paper id 1 (snippets/DegreeAngles.sm).  A4 uses id 9
# (Beam.sm).  Orientation "Landscape" just swaps width/height.
# ---------------------------------------------------------------------------
PAPERS = {
    "A4": (827, 1169, 9),
    "A4-landscape": (1169, 827, 9),
    "Letter": (850, 1100, 1),
    "Letter-landscape": (1100, 850, 1),
}


class PageSetup:
    """Page description.  Discussed in NOTES.md ("page setup")."""

    def __init__(self, paper="A4", margins=(39, 39, 39, 39), dpi=96,
                 orientation="Portrait", header=None, footer=None,
                 precision=4, exponential_threshold=5, fractions="decimal"):
        if isinstance(paper, (tuple, list)):
            w, h, pid = paper
        else:
            key = paper if paper in PAPERS else ("A4-landscape" if paper == "A4" and orientation == "Landscape" else paper)
            if key not in PAPERS:
                raise ValueError("unknown paper %r (known: %s)" % (paper, ", ".join(sorted(PAPERS))))
            w, h, pid = PAPERS[key]
        if orientation == "Landscape" and w < h:
            w, h = h, w
        self.width, self.height, self.paper_id = w, h, pid
        self.orientation = orientation
        if isinstance(margins, (int, float)):
            margins = (margins,) * 4
        self.margins = tuple(margins)  # left, right, top, bottom (1/100 inch)
        self.dpi = dpi
        self.header = header
        self.footer = footer
        self.precision = precision
        self.exponential_threshold = exponential_threshold
        self.fractions = fractions


# ---------------------------------------------------------------------------
# expression tree
# ---------------------------------------------------------------------------
# Token kinds emitted into <math><input>:
#   ('operand', text, style_or_None)      -> <e type="operand">text</e>
#   ('operator', text, args)              -> <e type="operator" args="N">op</e>
#   ('function', text, args)              -> <e type="function" args="N">name</e>
#   ('bracket', '(', None)                -> <e type="bracket">(</e>
#                                             (emitted *after* the grouped tokens:
#                                              samples 1_1.sm, 5_3.sm, 10_2.sm all
#                                              place the marker at the close point)
P_OR = 0        # comparisons / "=" / ":="
P_ADD = 1
P_MUL = 2
P_POW = 3
P_UN = 4
P_ATOM = 5

CONSTANTS = {
    "π": math.pi,
    "e": math.e,
    "∞": math.inf,
    "%": 0.01,          # not emitted; here only to make lookups explicit-safe
}
CONSTANTS.pop("%")

_UNARY_OPS = {"-", "!"}
_BINARY_OPS = {"+", "-", "*", "/", "^", ":", "=", "≤", "≥", "≠", "<", ">",
               "≡", "±", "%", "&", "|"}


def _fmt_plain(v):
    """Shortest round-tripping decimal string, no exponent notation."""
    if isinstance(v, int):
        return str(v)
    v = float(v)
    if v == int(v) and abs(v) < 1e16:
        return str(int(v))
    s = repr(v)
    if "e" in s or "E" in s:
        # caller is supposed to use _num_tokens for these; keep a plain fallback
        return "%.17g" % v
    return s


def _num_tokens(v):
    """Numeric literal -> token list.

    SMath's saved operands never use exponent notation (no 'E' operand exists in
    the corpus); big/small magnitudes are written as mantissa*10^exp, e.g.
    '(6.6728)*(10)^(-11)' in examples/GravitationAcceleration.sm.
    """
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        return [("operand", str(v), None)]
    v = float(v)
    if v == int(v) and abs(v) < 1e16:
        return [("operand", str(int(v)), None)]
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("cannot emit non-finite number %r" % (v,))
    s = repr(v)
    if "e" not in s and "E" not in s:
        return [("operand", s, None)]
    mant_s, exp_s = s.lower().split("e")
    exp = int(exp_s)
    mant = float(mant_s)
    toks = []
    neg_mant = mant < 0
    if abs(mant) != 1.0:
        toks += [("operand", _fmt_plain(abs(mant)), None)]
    toks += [("operand", "10", None)]
    if exp < 0:
        toks += [("operand", str(-exp), None), ("operator", "-", 1)]
    else:
        toks += [("operand", str(exp), None)]
    toks += [("operator", "^", 2)]
    if abs(mant) != 1.0:
        toks += [("operator", "*", 2)]
    if neg_mant:
        toks += [("operator", "-", 1)]
    return toks


class Expr:
    """Base class for the Python-side expression tree."""

    prec = P_ATOM
    units = False

    # -- emission ----------------------------------------------------------
    def tokens(self):
        return self._emit(0)

    def _emit(self, ctx):
        toks = self._raw()
        if self.prec < ctx:
            toks.append(("bracket", "(", None))
        return toks

    def _raw(self):                      # pragma: no cover - abstract
        raise NotImplementedError

    # -- evaluation --------------------------------------------------------
    def eval(self, env):
        raise NotImplementedError

    def has_units(self):
        return self.units

    # -- python operator sugar --------------------------------------------
    def __add__(self, o):  return Bin("+", self, o)
    def __radd__(self, o): return Bin("+", o, self)
    def __sub__(self, o):  return Bin("-", self, o)
    def __rsub__(self, o): return Bin("-", o, self)
    def __mul__(self, o):  return Bin("*", self, o)
    def __rmul__(self, o): return Bin("*", o, self)
    def __truediv__(self, o):  return Bin("/", self, o)
    def __rtruediv__(self, o): return Bin("/", o, self)
    def __pow__(self, o):  return Bin("^", self, o)
    def __rpow__(self, o): return Bin("^", o, self)
    def __neg__(self):     return Neg(self)
    def __pos__(self):     return self
    def __lt__(self, o):   return Bin("<", self, o)
    def __gt__(self, o):   return Bin(">", self, o)
    def __le__(self, o):   return Bin("≤", self, o)
    def __ge__(self, o):   return Bin("≥", self, o)
    def __repr__(self):    return "%s()" % type(self).__name__


class Num(Expr):
    def __init__(self, value):
        self.value = float(value)

    def _raw(self):
        return _num_tokens(self.value)

    def eval(self, env):
        return self.value

    def __repr__(self):
        return "Num(%r)" % self.value


class Var(Expr):
    """A variable.  sub=... gives SMath's name subscript, written as «имя.под».

    В SMath Studio подстрочный индекс в ИМЕНИ переменной записывается через
    точку: `V.ут` (= <e type="operand">V.ут</e>). Функция el(x, i) — это доступ
    к ЭЛЕМЕНТУ массива, и для скалярных величин она даёт неопределённую
    переменную (в редакторе — красный цвет). Пример: examples/Beam.sm — L.A, L.B.
    """

    def __init__(self, name, sub=None):
        self.name = str(name)
        self.sub = None if sub is None else str(sub)

    def _raw(self):
        if self.sub is None:
            return [("operand", self.name, None)]
        return [("operand", "%s.%s" % (self.name, self.sub), None)]

    def key(self):
        return self.name if self.sub is None else "%s_%s" % (self.name, self.sub)

    def eval(self, env):
        k = self.key()
        if k in env:
            return env[k]
        if k in CONSTANTS:
            return CONSTANTS[k]
        if self.sub is None:
            raise KeyError("undefined variable %r" % self.name)
        # el(x, 1) style subscript that we do not know -> try bare name
        if self.name in env:
            return env[self.name]
        raise KeyError("undefined variable %r" % k)

    def __repr__(self):
        return "V(%r%s)" % (self.name, "" if self.sub is None else ", %r" % self.sub)


class Unit(Expr):
    """A measurement unit operand (style="unit").

    Attested: examples/Beam.sm ('kN'), GravitationAcceleration.sm ('m','kg','s',
    'km'), snippets/DegreeAngles.sm ('°','deg').
    """

    units = True

    def __init__(self, name):
        self.name = str(name)

    def _raw(self):
        return [("operand", self.name, "unit")]

    def eval(self, env):
        if self.name in ("°", "deg"):
            return math.pi / 180.0
        return 1.0        # dimension-less stand-in; see NOTES.md "units"

    def __repr__(self):
        return "unit(%r)" % self.name


class Str(Expr):
    """A string literal operand (style="string"), e.g. 'The Sun'."""

    def __init__(self, s):
        self.s = str(s)

    def _raw(self):
        return [("operand", self.s, "string")]

    def eval(self, env):
        return self.s

    def __repr__(self):
        return "Str(%r)" % self.s


class Bin(Expr):
    _PREC = {"+": P_ADD, "-": P_ADD, "*": P_MUL, "/": P_MUL, "^": P_POW,
             ":": P_OR, "=": P_OR, "≤": P_OR, "≥": P_OR, "≠": P_OR,
             "<": P_OR, ">": P_OR, "≡": P_OR, "±": P_OR, "%": P_MUL,
             "&": P_OR, "|": P_OR}

    def __init__(self, op, left, right):
        if op not in self._PREC:
            raise ValueError("unsupported operator %r" % (op,))
        self.op = op
        self.left = _as_expr(left)
        self.right = _as_expr(right)
        self.prec = self._PREC[op]
        self.units = self.left.has_units() or self.right.has_units()

    def _raw(self):
        op = self.op
        if op == "^":                       # right associative, base may need ()
            lt = self.left._emit(P_UN)
            rt = self.right._emit(0)        # exponent is drawn as superscript
        elif op in ("+", "-") or op in ("*", "/"):
            lt = self.left._emit(self.prec)
            rt = self.right._emit(self.prec + 1 if op != "^" else self.prec)
        else:                               # comparisons / := / =
            lt = self.left._emit(0)
            rt = self.right._emit(0)
        return lt + rt + [("operator", op, 2)]

    def eval(self, env):
        op = self.op
        a = self.left.eval(env)
        if op == "±":
            b = self.right.eval(env)
            return a + b
        b = self.right.eval(env)
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*":
            try:
                return a * b
            except TypeError:
                return float("nan")
        if op == "/": return a / b
        if op == "^": return a ** b
        if op == "=": return a == b
        if op == "≤": return a <= b
        if op == "≥": return a >= b
        if op == "≠": return a != b
        if op == "<": return a < b
        if op == ">": return a > b
        if op == "%": return a % b
        if op in ("&", "|"): return bool(a) and bool(b) if op == "&" else bool(a) or bool(b)
        raise NotImplementedError("eval of operator %r" % op)

    def __repr__(self):
        return "(%r %s %r)" % (self.left, self.op, self.right)


class Neg(Expr):
    prec = P_UN
    _child_ctx = 3      # -(a*b) needs brackets, -(a^b) does not

    def __init__(self, child):
        self.child = _as_expr(child)
        self.units = self.child.has_units()

    def _raw(self):
        return self.child._emit(self._child_ctx) + [("operator", "-", 1)]

    def eval(self, env):
        return -self.child.eval(env)

    def __repr__(self):
        return "(-%r)" % (self.child,)


class Fact(Expr):
    """Postfix factorial: x!  (attested: 10_2.sm '<e args="1">!</e>')."""
    prec = P_ATOM

    def __init__(self, child):
        self.child = _as_expr(child)

    def _raw(self):
        return self.child._emit(P_ATOM) + [("operator", "!", 1)]

    def eval(self, env):
        return float(math.factorial(int(self.child.eval(env))))

    def __repr__(self):
        return "(%r!)" % (self.child,)


class Call(Expr):
    """Builtin function application.

    Emission is *argument tokens first, then the function element with args=N*
    (attested everywhere, e.g. sin: 4_2.sm, sqrt: 4_8.sm, ln: 10_2.sm,
    sum/4: examples/Simpson.sm, int/4: examples/Simpson.sm).
    """
    prec = P_ATOM

    def __init__(self, name, args, fn=None, arg_ctx=0):
        self.name = name
        self.args = [_as_expr(a) for a in args]
        self.fn = fn
        self.arg_ctx = arg_ctx
        self.units = any(a.has_units() for a in self.args)

    def _raw(self):
        toks = []
        for a in self.args:
            toks += a._emit(self.arg_ctx)
        toks.append(("function", self.name, len(self.args)))
        return toks

    def eval(self, env):
        vals = [a.eval(env) for a in self.args]
        if self.fn is None:
            raise NotImplementedError("no evaluator for %r" % self.name)
        return float(self.fn(*vals))

    def __repr__(self):
        return "%s(%s)" % (self.name, ", ".join(repr(a) for a in self.args))


class Paren(Expr):
    """Explicit brackets around a sub-expression (bracket marker after it)."""

    def __init__(self, child):
        self.child = _as_expr(child)
        self.units = self.child.has_units()

    def _raw(self):
        return self.child._emit(0) + [("bracket", "(", None)]

    def eval(self, env):
        return self.child.eval(env)

    def __repr__(self):
        return "Paren(%r)" % (self.child,)


class Assign(Expr):
    """x := expr       (attested: examples/Simpson.sm 'a' '1' <e args="2">:</e>)"""
    prec = P_OR

    def __init__(self, target, value):
        self.target = target if isinstance(target, Var) else Var(str(target))
        self.value = _as_expr(value)
        self.units = self.value.has_units()

    def _raw(self):
        return (self.target._emit(0) + self.value._emit(0)
                + [("operator", ":", 2)])

    def eval(self, env):
        v = self.value.eval(env)
        env[self.target.key()] = v
        return v

    def __repr__(self):
        return "Assign(%r, %r)" % (self.target, self.value)


class FuncDef(Expr):
    """f(x, y) := body

    Attested: examples/GravitationAcceleration.sm region 2
      <e>M.obj</e><e>R.obj</e><e type="function" args="2">gravity</e> ...body... <e args="2">:</e>
    i.e. parameter operands, then a function element whose args == #params.
    """
    prec = P_OR

    def __init__(self, name, params, body):
        self.name = name
        self.params = [Var(str(p)) for p in params]
        self.body = _as_expr(body)
        self.units = self.body.has_units()

    def _raw(self):
        toks = [("operand", p.name, None) for p in self.params]
        toks.append(("function", self.name, len(self.params)))
        toks += self.body._emit(0)
        toks.append(("operator", ":", 2))
        return toks

    def eval(self, env):
        raise NotImplementedError("function definitions are not evaluated")

    def __repr__(self):
        return "FuncDef(%s, %r, %r)" % (self.name, self.params, self.body)


def _as_expr(x):
    if isinstance(x, Expr):
        return x
    if isinstance(x, (int, float)):
        return Num(x)
    if isinstance(x, str):
        return Var(x)
    raise TypeError("cannot use %r as an expression" % (x,))


# ---------------------------------------------------------------------------
# constructors / sugar
# ---------------------------------------------------------------------------
def V(name, sub=None):
    return Var(name, sub)


var = V


def num(v):
    return Num(v)


N = num
number = num


def unit(name):
    return Unit(name)


pi = Var("π")
e_const = Var("e")
inf = Var("∞")


def assign(target, value):
    return Assign(target, value)


def funcdef(name, params, body):
    return FuncDef(name, params, body)


def call(name, *args):
    """Generic function call node, for user-defined functions and builtins that
    have no dedicated wrapper:  call("ff", num(3))  ->  ff(3)."""
    return Call(name, args)



def equation(lhs, rhs):
    return Bin("=", lhs, rhs)


def lt(a, b): return Bin("<", a, b)
def gt(a, b): return Bin(">", a, b)
def le(a, b): return Bin("≤", a, b)
def ge(a, b): return Bin("≥", a, b)
def ne(a, b): return Bin("≠", a, b)
def plus_minus(a, b): return Bin("±", a, b)


def _f1(name, fn):
    return lambda x: Call(name, (x,), fn)


sin = _f1("sin", math.sin)
cos = _f1("cos", math.cos)
tan = _f1("tg", math.tan)          # SMath's builtin spelling is tg (4_2.sm)
cot = _f1("ctg", math.tan)
asin = _f1("asin", math.asin)
acos = _f1("acos", math.acos)
atan = _f1("atan", math.atan)
sinh = _f1("sh", math.sinh)
cosh = _f1("ch", math.cosh)
tanh = _f1("th", math.tanh)
sqrt = _f1("sqrt", math.sqrt)
abs_ = _f1("abs", abs)
sign = _f1("sign", lambda x: (x > 0) - (x < 0))
ln = _f1("ln", math.log)
lg = _f1("log", math.log10)        # 1-argument log = decimal log
exp = lambda x: Bin("^", Var("e"), x)   # 'exp' is not attested -> e^x (4_2.sm)


def log(x, base=None):
    if base is None:
        return Call("log", (x,), math.log10)
    return Call("log", (base, x), lambda b, xx: math.log(xx, b))


def root(x, n):
    """n-th root of x, emitted as x^(1/n) -- 100% attested construct ('^')."""
    return Bin("^", _as_expr(x), Bin("/", Num(1), _as_expr(n)))


def nth_root(x, n):
    """Real n-th root (rendered as SMath's nthroot function, args=2)."""
    return Call("nthroot", (x, n), lambda xx, nn: xx ** (1.0 / nn))


def mod(a, b):
    return Call("mod", (a, b), lambda x, y: math.fmod(x, y))


def if_(cond, then, other):
    return Call("if", (cond, then, other), lambda c, t, o: t if c else o)


def min_(*a):
    return Call("min", a, min)


def max_(*a):
    return Call("max", a, max)


def sum_(body, k, lo, hi):
    """sum(body, k, lo, hi), encoded exactly like examples/Simpson.sm:

        <tokens of body> <k> <lo> <hi> <e type="function" args="4">sum</e>
    """
    return Call("sum", (body, k, lo, hi), None, arg_ctx=0)


def product(body, k, lo, hi):
    return Call("product", (body, k, lo, hi), None, arg_ctx=0)


def integ(body, x, lo, hi):
    """Definite integral int(body, x, lo, hi) -- 4 args (examples/Simpson.sm)."""
    return Call("int", (body, x, lo, hi), None, arg_ctx=0)


def solve(*a, **k):
    raise NotImplementedError(
        "SMath's solve() is not present anywhere in the sample corpus, so its "
        "argument encoding cannot be attested. Rewrite as root(lhs-rhs, var) "
        "or leave the equation for manual solving.")


def text_literal(s):
    return Str(s)


def fmt_num(v):
    """Human-readable number for reports (not for the XML)."""
    return _fmt_plain(float(v))


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------
def _e_tokens(parent, toks):
    for kind, text, extra in toks:
        el = ET.SubElement(parent, "e")
        if kind == "operand":
            el.set("type", "operand")
            if extra:
                el.set("style", extra)
            el.text = text
        elif kind == "operator":
            el.set("type", "operator")
            el.set("args", str(extra))
            el.text = text
        elif kind == "function":
            el.set("type", "function")
            el.set("args", str(extra))
            el.text = text
        elif kind == "bracket":
            el.set("type", "bracket")
            el.text = text
        else:                                    # pragma: no cover
            raise ValueError("bad token %r" % (kind,))


def estimate_tokens_visual_len(toks):
    n = 0.0
    for kind, text, extra in toks:
        if kind == "operand":
            n += max(1.6, 0.62 * len(text)) + 0.4
        elif kind == "operator":
            n += 1.1 if extra == 2 else 0.55
        elif kind == "function":
            n += 0.55 * len(text) + 0.6
        else:
            n += 0.35
    return n


def estimate_height(toks):
    """Region height in px for a math region.

    SMath clips region content to the box, so the estimate is deliberately
    generous.  Calibration points from examples/Beam.sm: a plain definition is
    24 px, a matrix/power row 45 px, an 8-line calc block 80 px.
    """
    n_div = sum(1 for k, t, _ in toks if k == "operator" and t == "/")
    n_pow = sum(1 for k, t, _ in toks if k == "operator" and t == "^")
    # SMath рисует "/" как ДВУХЭТАЖНУЮ дробь: строка формул с делением занимает
    # почти вдвое больше места. Проверено визуально на SMath Studio 1.5 —
    # при 14 px на деление соседние области наложились друг на друга.
    h = 24 + 26 * min(n_div, 2) + 10 * min(n_pow, 2)
    return h


# ---------------------------------------------------------------------------
# Region + document
# ---------------------------------------------------------------------------
class Region:
    __slots__ = ("id", "left", "top", "width", "height", "kind", "element",
                 "expr", "text", "result")

    def __init__(self, id, left, top, width, height, kind, element):
        self.id, self.left, self.top = id, left, top
        self.width, self.height, self.kind = width, height, kind
        self.element = element
        self.expr = None
        self.text = None
        self.result = None

    def __repr__(self):
        return "Region(id=%r, %s, %r,%r)" % (self.id, self.kind, self.left, self.top)


class Doc:
    """A worksheet under construction."""

    def __init__(self, page_setup=None, font_size=12, title=None, author=None,
                 description=None, keywords=None, company=None, language=None,
                 allow_units=True):
        if isinstance(page_setup, PageSetup):
            self.page = page_setup
        elif isinstance(page_setup, dict):
            self.page = PageSetup(**page_setup)
        elif page_setup is None:
            self.page = PageSetup(paper="A4")
        else:                                  # "A4" / "Letter" / custom tuple
            self.page = PageSetup(paper=page_setup)
        self.font_size = font_size
        self.meta = dict(title=title, author=author, description=description,
                         keywords=keywords, company=company, language=language)
        self.regions = []
        self.env = {}
        self.allow_units = bool(allow_units)
        self._next_id = 0
        self.used_text = False
        self.used_math = False

    # -- low level ---------------------------------------------------------
    def _new_region(self, kind, left, top, width, height, font_size, color,
                    background_color, border=False):
        el = ET.Element("region")
        el.set("id", str(self._next_id))
        el.set("left", str(int(round(left))))
        el.set("top", str(int(round(top))))
        el.set("width", str(int(round(width))))
        el.set("height", str(int(round(height))))
        if border:
            el.set("border", "true")
        el.set("color", color)
        el.set("bgColor", background_color)
        el.set("fontSize", str(font_size))
        reg = Region(self._next_id, left, top, width, height, kind, el)
        self._next_id += 1
        self.regions.append(reg)
        return reg

    # -- text --------------------------------------------------------------
    def text(self, left, top, width, text, bold=False, italic=False,
             underline=False, font_size=None, color=DEFAULT_COLOR,
             background_color=DEFAULT_BG, link=None, border=False, height=None,
             lang=None):
        """Add a text region.

        * multi-line text: literal newlines inside the single <p> (that is how
          examples/Beam.sm stores a two-line caption; there is no <br> anywhere
          in the corpus and every <text> has exactly one <p>).
        * bold -> <p bold="true">  (attested: book/1.sm, examples/Beam.sm)
        * link -> <p href="...">   (attested: book/1_1.sm)
        * italic / underline are written as attributes on <p>; they are *not*
          attested in the corpus (see NOTES.md "not attested").
        """
        fs = int(font_size or self.font_size)
        s = "" if text is None else str(text)
        lines = s.count("\n") + 1
        line_h = int(round(fs * 1.8))
        if height is None:
            # высота с учётом ПЕРЕНОСА длинных строк: иначе соседние области
            # накладываются друг на друга (проверено в SMath Studio 1.5)
            cpl = max(10, int((width - 12) / (0.52 * fs)))
            wrapped = sum(max(1, math.ceil(len(par) / cpl))
                          for par in s.split("\n"))
            height = 6 + max(lines, wrapped) * line_h
        reg = self._new_region("text", left, top, width, height, fs, color,
                               background_color, border)
        tel = ET.SubElement(reg.element, "text")
        if lang:
            tel.set("lang", lang)
        pel = ET.SubElement(tel, "p")
        if bold:
            pel.set("bold", "true")
        if italic:
            pel.set("italic", "true")
        if underline:
            pel.set("underline", "true")
        if link is not None:
            pel.set("href", link)
        pel.text = s
        reg.text = s
        self.used_text = True
        return reg

    # -- math --------------------------------------------------------------
    def math(self, left, top, expr, width=None, height=None, font_size=None,
             color=DEFAULT_COLOR, background_color=DEFAULT_BG, border=False,
             result=True, result_value=None):
        """Add a math region for `expr`.

        * expr = assign(...) / funcdef(...)  -> definition, no result shown.
        * anything else                      -> the expression plus a cached
          <result action="numeric"> value (attested: examples/Beam.sm region 57,
          examples/Simpson.sm region 10), which is how SMath displays results.
        """
        expr = _as_expr(expr)
        if not self.allow_units and expr.has_units():
            raise ValueError(
                "this Doc was created with allow_units=False but the expression "
                "contains measurement units (unit(...)); drop the units or use "
                "allow_units=True (see NOTES.md, 'units')")
        toks = expr.tokens()
        auto_height = height is None
        if width is None:
            width = max(260.0, min(820.0, estimate_tokens_visual_len(toks) * 7.6 + 30))
        if height is None:
            height = estimate_height(toks)
        fs = int(font_size or self.font_size)
        reg = self._new_region("math", left, top, width, height, fs, color,
                               background_color, border)
        mel = ET.SubElement(reg.element, "math")
        inel = ET.SubElement(mel, "input")
        _e_tokens(inel, toks)
        reg.expr = expr

        is_def = isinstance(expr, (Assign, FuncDef))
        value = None
        if is_def:
            try:
                value = expr.eval(self.env)
            except Exception:
                value = None
        else:
            try:
                if expr.has_units():
                    value = None
                else:
                    value = expr.eval(self.env)
                    value = float(value)
            except Exception:
                value = None

        if result_value is not None:
            value = float(result_value)

        if result and value is not None and isinstance(value, float) \
                and math.isfinite(value):
            # SMath показывает у определения «x := ... = значение» только если в
            # файле есть <result> (проверено на SMath Studio 1.5: без него
            # значения в определении не отображаются вовсе).
            rel = ET.SubElement(mel, "result")
            rel.set("action", "numeric")
            shown = float("%.6g" % value)          # без хвоста 1,33199999999998
            toks_res = _num_tokens(abs(shown))
            if shown < 0:
                toks_res.append(("operator", "-", 1))
            _e_tokens(rel, toks_res)
            reg.result = shown
            if auto_height and reg.height < 30:
                # a region that shows "expr = value" needs the extra result row
                # (examples/Beam.sm region 57 uses height 30 for exactly that)
                reg.height = 30
                reg.element.set("height", "30")
        self.used_math = True
        return reg

    # -- convenience -------------------------------------------------------
    def next_top(self):
        """Bottom-most y of all regions so far (+ a small gap), for a new column."""
        if not self.regions:
            return 9
        return max(r.top + r.height for r in self.regions) + 8

    def next_left(self):
        """Right-most x of all regions so far (+ a column gap)."""
        if not self.regions:
            return 9
        return max(r.left + r.width for r in self.regions) + 24

    def flow(self, left=None, top=None, width=560, gap=4, font_size=None):
        """A vertical cursor.  `top` defaults to the bottom of the sheet so far."""
        if top is None:
            top = self.next_top()
        return Flow(self, left=left, top=top, width=width, gap=gap,
                    font_size=font_size)

    def title(self, text, left=None, top=None, width=760, font_size=None,
              color="#0000ff", bold=True):
        fs = int(font_size or max(14, self.font_size + 2))
        h = 6 + int(round(fs * 1.8))
        if left is None:
            left = 9
        if top is None:
            top = self._autotop()
        self.text(left, top, width, text, bold=bold, font_size=fs, color=color,
                  height=h)
        self._last_bottom = top + h
        return self

    def header(self, text, left=None, top=None, width=760, font_size=None,
               bold=True):
        fs = int(font_size or self.font_size)
        h = 6 + int(round(fs * 1.8))
        if left is None:
            left = 9
        if top is None:
            top = self._autotop()
        self.text(left, top, width, text, bold=bold, font_size=fs, height=h)
        self._last_bottom = top + h
        return self

    def _autotop(self):
        if not hasattr(self, "_last_bottom"):
            self._last_bottom = 9
            return 9
        return self._last_bottom + 8

    # -- save --------------------------------------------------------------
    def _settings_element(self):
        st = ET.Element("settings")
        st.set("dpi", str(self.page.dpi))
        ident = ET.SubElement(st, "identity")
        ET.SubElement(ident, "id").text = str(uuid.uuid4())
        ET.SubElement(ident, "revision").text = "2"
        if any(self.meta.get(k) for k in ("title", "author", "description",
                                          "keywords", "company")):
            md = ET.SubElement(st, "metadata")
            if self.meta.get("language"):
                md.set("lang", self.meta["language"])
            for tag in ("title", "author", "description", "company", "keywords"):
                if self.meta.get(tag):
                    ET.SubElement(md, tag).text = str(self.meta[tag])
        calc = ET.SubElement(st, "calculation")
        ET.SubElement(calc, "precision").text = str(self.page.precision)
        ET.SubElement(calc, "exponentialThreshold").text = str(
            self.page.exponential_threshold)
        ET.SubElement(calc, "fractions").text = str(self.page.fractions)
        pm = ET.SubElement(st, "pageModel")
        pm.set("active", "false")
        pm.set("viewMode", "2")
        pm.set("printGrid", "false")
        pm.set("printAreas", "false")
        pm.set("simpleEqualsOnly", "true")
        pm.set("printBackgroundImages", "true")
        paper = ET.SubElement(pm, "paper")
        paper.set("id", str(self.page.paper_id))
        paper.set("orientation", self.page.orientation)
        paper.set("width", str(self.page.width))
        paper.set("height", str(self.page.height))
        mg = ET.SubElement(pm, "margins")
        for k, v in zip(("left", "right", "top", "bottom"), self.page.margins):
            mg.set(k, str(int(v)))
        if self.page.header is not None:
            h = ET.SubElement(pm, "header")
            h.set("alignment", "Center")
            h.set("color", "#a9a9a9")
            h.text = self.page.header
        if self.page.footer is not None:
            f = ET.SubElement(pm, "footer")
            f.set("alignment", "Center")
            f.set("color", "#a9a9a9")
            f.text = self.page.footer
        ET.SubElement(pm, "backgrounds")
        deps = ET.SubElement(st, "dependencies")
        GUIDS = [(GUID_APP, "SMath Studio Desktop")]
        if self.used_math:
            GUIDS.append((GUID_MATH, "Math Region"))
        if self.used_text:
            GUIDS.append((GUID_TEXT, "Text Region"))
        for guid, name in GUIDS:
            a = ET.SubElement(deps, "assembly")
            a.set("name", name)
            a.set("version", APP_VERSION)
            a.set("guid", guid)
        return st

    def _settings_element_legacy(self):
        """<settings> в формате 0.88 — SMath Studio 1.5 открывает его штатно.

        Проверено 2026-11-01: файл с шапкой и <settings> схемы 1.0 (атрибут dpi,
        paper id="9", зависимости "SMath Studio Desktop" 1.5.0.9678) роняет
        SMath Studio 1.5 с NullReferenceException («Ссылка на объект не
        указывает на экземпляр объекта»); формат 0.88 (пример 088_formulas.sm)
        открывается и считает правильно.
        """
        st = ET.Element("settings")
        ET.SubElement(st, "editable").text = "true"
        calc = ET.SubElement(st, "calculation")
        ET.SubElement(calc, "functions").text = "1"
        ET.SubElement(calc, "precision").text = str(self.page.precision)
        ET.SubElement(calc, "angle").text = "radians"
        ET.SubElement(calc, "fractions").text = str(self.page.fractions)
        ET.SubElement(calc, "recalculation").text = "true"
        deps = ET.SubElement(st, "dependences")
        for guid, name in ((GUID_APP, "SMath Studio"),
                           (GUID_MATH, "Math Region"),
                           (GUID_TEXT, "Text Region")):
            a = ET.SubElement(deps, "assembly")
            a.set("name", name)
            a.set("version", LEGACY_VERSION)
            a.set("guid", guid)
        return st

    def to_xml(self, legacy=True):
        if legacy:
            root = ET.Element("regions")
            root.append(self._settings_element_legacy())
            progid, version = LEGACY_PROGID, LEGACY_VERSION
        else:
            ET.register_namespace("", NS)
            root = ET.Element("{%s}regions" % NS)
            root.append(self._settings_element())
            progid, version = APP_PROGID, APP_VERSION
        for reg in self.regions:
            root.append(reg.element)
        ET.indent(root, space="  ")
        body = ET.tostring(root, encoding="unicode")
        head = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\r\n'
                '<?application progid="%s" version="%s"?>\r\n' % (progid, version))
        return head + body + "\r\n"

    def save(self, path, legacy=True):
        path = str(path)
        folder = os.path.dirname(os.path.abspath(path))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        data = self.to_xml(legacy=legacy)
        # samples (book/1.sm, examples/Beam.sm) start with a UTF-8 BOM
        with open(path, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + data.encode("utf-8"))
        return path


class Flow:
    """Vertical cursor: stacks regions and hands out the next `top`."""

    def __init__(self, doc, left=None, top=None, width=560, gap=4,
                 font_size=None):
        self.doc = doc
        self.left = 9 if left is None else left
        self.top = 9 if top is None else top
        self.width = width
        self.spacing = gap
        self.font_size = font_size or doc.font_size

    # -- regions -----------------------------------------------------------
    def text(self, text, width=None, gap=None, **kw):
        fs = kw.get("font_size") or self.font_size
        line_h = int(round(fs * 1.8))
        h = kw.pop("height", None) or 6 + (str(text).count("\n") + 1) * line_h
        reg = self.doc.text(self.left, self.top, width or self.width, text,
                            **kw)
        self.top = reg.top + reg.height + (self.spacing if gap is None else gap)
        return reg

    def header(self, text, **kw):
        return self.text(text, bold=kw.pop("bold", True), **kw)

    def title(self, text, **kw):
        fs = kw.pop("font_size", max(14, self.font_size + 2))
        color = kw.pop("color", "#0000ff")
        return self.text(text, bold=kw.pop("bold", True), font_size=fs,
                         color=color, **kw)

    def math(self, expr, width=None, gap=None, **kw):
        reg = self.doc.math(self.left, self.top, expr, width=width, **kw)
        self.top = reg.top + reg.height + (self.spacing if gap is None else gap)
        return reg

    def assign(self, target, value, **kw):
        return self.math(assign(target, value), **kw)

    def display(self, expr, **kw):
        return self.math(expr, **kw)

    def gap(self, n=12):
        self.top += n

    # SMath rows are ~18 px; expose a coarse row cursor as well
    def next_top(self):
        return self.top


# ---------------------------------------------------------------------------
# tiny self-check when run as a script
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    d = Doc(title="smoke")
    f = d.flow()
    f.title("Smoke test")
    f.assign(V("a"), 3)
    f.assign(V("b"), V("a") ** 2 + num(1))
    f.math(V("b") / num(2) + sqrt(num(2)))
    p = d.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke.sm"))
    print("wrote", p, len(d.to_xml()), "bytes of XML")
