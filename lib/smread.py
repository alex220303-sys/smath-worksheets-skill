"""smread.py -- read a .sm worksheet back and execute its math regions.

Independent of smscript.py on purpose: the selftest proves that the bytes we
write can be parsed and evaluated by a second implementation.

Public API (stable):
    parse(path)              -> Worksheet
    evaluate(regions)        -> EvalResult(env, values, definitions, errors)
    build_tree(tokens)       -> Node
    Worksheet.math_regions() / Worksheet.text_regions() / Worksheet.summary()

Token kinds in a region's `tokens` list: ('operand', text, style),
('operator', text, args), ('function', text, args), ('bracket', '(', None).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

NS = "http://smath.info/schemas/worksheet/1.0"

CONSTANTS = {"π": math.pi, "e": math.e, "∞": math.inf}


# ---------------------------------------------------------------------------
# tolerating both the namespaced (0.96+) and the legacy (0.55) layout
# ---------------------------------------------------------------------------
def _local(tag):
    return tag.split("}")[-1]


def _attr(el, *names, default=None):
    for n in names:
        if n in el.attrib:
            return el.attrib[n]
    return default


class Token:
    __slots__ = ("kind", "text", "args", "style")

    def __init__(self, kind, text, args=None, style=None):
        self.kind, self.text, self.args, self.style = kind, text, args, style

    def __repr__(self):
        if self.kind == "operand":
            return self.text + ("[%s]" % self.style if self.style else "")
        if self.kind in ("operator", "function"):
            return "%s:%s/%s" % (self.kind, self.text, self.args)
        return "%s:%s" % (self.kind, self.text)


class Region:
    __slots__ = ("id", "left", "top", "width", "height", "kind", "text_lines",
                 "tokens", "result_tokens", "contract_tokens", "font_size",
                 "color", "bg_color", "border", "element")

    def __init__(self):
        self.id = self.left = self.top = self.width = self.height = None
        self.kind = None
        self.text_lines = []
        self.tokens = []
        self.result_tokens = []
        self.contract_tokens = []
        self.font_size = None
        self.color = self.bg_color = None
        self.border = False
        self.element = None

    @property
    def text(self):
        return "\n".join(self.text_lines)

    def __repr__(self):
        if self.kind == "math":
            return "Region(%r, math, %s)" % (self.id, " ".join(map(repr, self.tokens)))
        return "Region(%r, %s, %r)" % (self.id, self.kind, self.text[:40])


class Worksheet:
    def __init__(self, path=None):
        self.path = path
        self.regions = []
        self.settings = {}
        self.application = {}

    # convenience views
    def math_regions(self):
        return [r for r in self.regions if r.kind == "math"]

    def text_regions(self):
        return [r for r in self.regions if r.kind == "text"]

    def summary(self):
        out = ["file: %s" % self.path,
               "application: %r" % (self.application,),
               "paper: %sx%s %s margins=%s" % (
                   self.settings.get("paper", {}).get("width"),
                   self.settings.get("paper", {}).get("height"),
                   self.settings.get("paper", {}).get("orientation"),
                   self.settings.get("margins")),
               "regions: %d (%d math, %d text)" % (
                   len(self.regions), len(self.math_regions()),
                   len(self.text_regions()))]
        return "\n".join(out)

    def __repr__(self):
        return "Worksheet(%r, %d regions)" % (self.path, len(self.regions))


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
_OP_ARGS = {"+": 2, "-": 1, "*": 2, "/": 2, "^": 2, ":": 2, "=": 2,
            "≤": 2, "≥": 2, "≠": 2, "<": 2, ">": 2, "≡": 2, "±": 2,
            "%": 2, "&": 2, "|": 2, "!": 1}


def _read_e_tokens(container):
    toks = []
    if container is None:
        return toks
    for el in container:
        if _local(el.tag) != "e":
            continue
        typ = el.attrib.get("type")
        txt = el.text or ""
        if typ == "operand":
            toks.append(Token("operand", txt, None, el.attrib.get("style")))
        elif typ == "operator":
            n = int(el.attrib.get("args", _OP_ARGS.get(txt, 2)))
            toks.append(Token("operator", txt, n))
        elif typ == "function":
            toks.append(Token("function", txt, int(el.attrib.get("args", 1))))
        elif typ == "bracket":
            toks.append(Token("bracket", txt))
        else:
            raise ValueError("unknown <e type=%r>" % (typ,))
    return toks


def _parse_region(el):
    reg = Region()
    reg.element = el
    reg.id = int(el.attrib.get("id", -1))
    reg.left = int(float(el.attrib.get("left", 0)))
    reg.top = int(float(el.attrib.get("top", 0)))
    reg.width = int(float(el.attrib.get("width", 0)))
    reg.height = int(float(el.attrib.get("height", 0)))
    reg.font_size = int(float(_attr(el, "fontSize", "font-size", default=10)))
    reg.color = _attr(el, "color", default="#000000")
    reg.bg_color = _attr(el, "bgColor", "background-color", default="#ffffff")
    reg.border = str(_attr(el, "border", default="false")).lower() == "true"

    kinds = []
    for child in el:
        tag = _local(child.tag)
        kinds.append(tag)
        if tag == "text":
            reg.kind = "text"
            for p in child:
                if _local(p.tag) == "p":
                    reg.text_lines.append(p.text or "")
        elif tag == "math":
            reg.kind = "math"
            has_wrapper = False
            for part in child:
                ptag = _local(part.tag)
                if ptag == "input":
                    has_wrapper = True
                    reg.tokens = _read_e_tokens(part)
                elif ptag == "contract":
                    reg.contract_tokens = _read_e_tokens(part)
                elif ptag == "result":
                    reg.result_tokens = _read_e_tokens(part)
            if not has_wrapper:
                # legacy 0.55 layout: <math> directly contains <e> elements
                reg.tokens = _read_e_tokens(child)
        elif tag == "area":
            reg.kind = "area"
        elif tag == "plot":
            reg.kind = "plot"
    if reg.kind is None:
        reg.kind = ",".join(kinds) or "unknown"
    return reg


def parse(path):
    tree = ET.parse(str(path))
    root = tree.getroot()
    ws = Worksheet(path)
    # processing instruction <?application progid=... version=...?>
    try:
        with open(str(path), "r", encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                if "<?" in line and "application" in line:
                    import re as _re
                    for k, v in _re.findall(r'(\w+)\s*=\s*"([^"]*)"', line):
                        ws.application[k] = v
                    break
    except OSError:
        pass

    for el in root:
        if _local(el.tag) == "settings":
            for c in el:
                tag = _local(c.tag)
                if tag == "pageModel":
                    for cc in c:
                        t2 = _local(cc.tag)
                        if t2 == "paper":
                            ws.settings["paper"] = dict(cc.attrib)
                        elif t2 == "margins":
                            ws.settings["margins"] = dict(cc.attrib)
                elif tag == "calculation":
                    ws.settings["calculation"] = {_local(cc.tag): (cc.text or "")
                                                  for cc in c}
        elif _local(el.tag) == "region":
            ws.regions.append(_parse_region(el))
    ws.regions.sort(key=lambda r: r.id)
    return ws


def read_tokens(region):
    """Token list of a math region (shortcut used by tests)."""
    return region.tokens


# ---------------------------------------------------------------------------
# RPN -> tree
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ("kind", "text", "args", "style")

    def __init__(self, kind, text=None, args=(), style=None):
        self.kind, self.text, self.args, self.style = kind, text, list(args), style

    def __repr__(self):
        if self.kind in ("num", "sym", "unit", "str"):
            return "%s(%r)" % (self.kind, self.text)
        return "%s(%s)" % (self.kind, ", ".join(repr(a) for a in self.args))


def build_tree(tokens):
    """Reduce a postfix token list to a tree.  Brackets are display-only: they
    carry no stack effect (that is exactly how SMath uses them -- see NOTES)."""
    stack = []
    for t in tokens:
        if t.kind == "operand":
            if t.style == "unit":
                stack.append(Node("unit", t.text))
            elif t.style == "string":
                stack.append(Node("str", t.text))
            else:
                stack.append(Node("num", t.text) if _is_number(t.text)
                             else Node("sym", t.text))
        elif t.kind == "bracket":
            continue
        elif t.kind == "operator":
            n = t.args or 1
            if len(stack) < n:
                raise ValueError("stack underflow at operator %r (%d args, depth %d)"
                                 % (t.text, n, len(stack)))
            args = stack[-n:]
            del stack[-n:]
            if t.text in (":", "≡") and n == 2 and args[0].kind == "call" \
                    and args[0].text != "el":
                # f(x) := body   -- function definition
                # (attested: examples/GravitationAcceleration.sm region 2)
                # NOTE: <e args="2">el</e> is SMath's subscript pseudo-function,
                # so "x1 := 7" arrives as a call too -- it is *not* a funcdef.
                fn = args[0]
                stack.append(Node("funcdef", fn.text, list(fn.args) + [args[1]]))
            elif t.text == ":" and n == 2:
                stack.append(Node("assign", None, args))
            elif t.text == "≡" and n == 2:
                stack.append(Node("assign", None, args))
            elif n == 1:
                stack.append(Node("unop", t.text, args))
            else:
                stack.append(Node("binop", t.text, args))
        elif t.kind == "function":
            n = t.args or 1
            if len(stack) < n:
                raise ValueError("stack underflow at function %r (%d args, depth %d)"
                                 % (t.text, n, len(stack)))
            args = stack[-n:]
            del stack[-n:]
            stack.append(Node("call", t.text, args))
        else:                                    # pragma: no cover
            raise ValueError("bad token %r" % (t,))
    if len(stack) != 1:
        raise ValueError("dangling stack (%d items): %r" % (len(stack), stack))
    return stack[0]


def _is_number(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def node_identifier(node):
    """Return 'name' or 'name_sub' for a symbol node / el(name, sub)."""
    if node.kind == "sym":
        return node.text
    if node.kind == "call" and node.text == "el" and len(node.args) == 2 \
            and node.args[0].kind == "sym":
        return "%s_%s" % (node.args[0].text, node.args[1].text)
    return None


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------
class EvalError(Exception):
    pass


def _b(x):
    return bool(x)


def _integrate(body, var, lo, hi, n=2000):
    """Composite Simpson integration of `body` over `var` in [lo, hi]."""
    if n % 2:
        n += 1
    h = (hi - lo) / n
    total = 0.0
    for i in range(n + 1):
        x = lo + i * h
        y = _eval_node(body, {"__local__": (var, x)})
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        total += w * y
    return total * h / 3.0


def _eval_node(node, ctx):
    k = node.kind
    if k == "num":
        return float(node.text)
    if k == "str":
        return node.text
    if k == "unit":
        if node.text in ("°", "deg"):
            return math.pi / 180.0
        return 1.0
    if k == "sym":
        env = ctx.get("env", {})
        if node.text in env:
            return env[node.text]
        if node.text in CONSTANTS:
            return CONSTANTS[node.text]
        loc = ctx.get("__local__")
        if loc and loc[0] == node.text:
            return loc[1]
        raise EvalError("undefined variable %r" % node.text)
    if k == "binop":
        op = node.text
        a = _eval_node(node.args[0], ctx)
        b = _eval_node(node.args[1], ctx)
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*":
            if isinstance(a, str) or isinstance(b, str):
                return str(a) + str(b)
            return a * b
        if op == "/": return a / b
        if op == "^": return a ** b
        if op == "=": return a == b
        if op == "≤": return a <= b
        if op == "≥": return a >= b
        if op == "≠": return a != b
        if op == "<": return a < b
        if op == ">": return a > b
        if op == "≡": return a == b
        if op == "%": return math.fmod(a, b)
        if op == "±": return a + b
        if op == "&": return _b(a) and _b(b)
        if op == "|": return _b(a) or _b(b)
        raise EvalError("unsupported operator %r" % op)
    if k == "unop":
        op = node.text
        a = _eval_node(node.args[0], ctx)
        if op == "-": return -a
        if op == "!": return float(math.factorial(int(a)))
        raise EvalError("unsupported unary operator %r" % op)
    if k == "assign":
        return _do_assign(node, ctx)
    if k == "funcdef":
        params = [node_identifier(p) for p in node.args[:-1]]
        if any(p is None for p in params):
            raise EvalError("function definition with non-identifier parameters")
        ctx.setdefault("funcs", {})[node.text] = (params, node.args[-1])
        return None
    if k == "call":
        return _do_call(node, ctx)
    raise EvalError("unsupported node %r" % k)


def _do_assign(node, ctx):
    lhs, rhs = node.args
    name = node_identifier(lhs)
    if name is None:
        raise EvalError("assignment target is not a plain identifier: %r" % (lhs,))
    val = _eval_node(rhs, ctx)
    if isinstance(val, bool):
        val = float(val)
    if not isinstance(val, (int, float)):
        raise EvalError("cannot bind non-number %r to %r" % (val, name))
    ctx.setdefault("env", {})[name] = float(val)
    return float(val)


def _do_call(node, ctx):
    name = node.text
    a = node.args
    funcs = ctx.get("funcs") or {}
    if name in funcs:
        params, body = funcs[name]
        vals = [_eval_node(x, ctx) for x in a]
        sub = dict(ctx)
        sub["env"] = dict(ctx.get("env", {}))
        for p, v in zip(params, vals):
            sub["env"][p] = v
        return _eval_node(body, sub)
    if name == "el":
        if len(a) == 2 and a[0].kind == "sym":
            key = "%s_%s" % (a[0].text, a[1].text)
            env = ctx.get("env", {})
            if key in env:
                return env[key]
            if a[0].text in env:
                return env[a[0].text]
            raise EvalError("undefined subscripted variable %r" % key)
        raise EvalError("el with %d args (matrix element) not supported" % len(a))

    if name in ("sum", "product", "int") and len(a) == 4:
        body, var, lo_n, hi_n = a
        vname = var.text if var.kind == "sym" else None
        if vname is None:
            raise EvalError("%s: loop variable must be an identifier" % name)
        lo = _eval_node(lo_n, ctx)
        hi = _eval_node(hi_n, ctx)
        if name == "int":
            return _integrate(body, vname, lo, hi)
        total = 0.0 if name == "sum" else 1.0
        k = int(round(lo))
        stop = int(round(hi))
        while k <= stop:
            sub = dict(ctx)
            sub["__local__"] = (vname, float(k))
            v = _eval_node(body, sub)
            total = total + v if name == "sum" else total * v
            k += 1
        return total

    if name in ("if",) and len(a) == 3:
        cond = _eval_node(a[0], ctx)
        return _eval_node(a[1] if cond else a[2], ctx)

    vals = [_eval_node(x, ctx) for x in a]

    if name == "sin": return math.sin(vals[0])
    if name == "cos": return math.cos(vals[0])
    if name in ("tg", "tan"): return math.tan(vals[0])
    if name in ("ctg", "cot"): return 1.0 / math.tan(vals[0])
    if name in ("asin", "arcsin"): return math.asin(vals[0])
    if name in ("acos", "arccos"): return math.acos(vals[0])
    if name in ("atan", "arctg"): return math.atan(vals[0])
    if name in ("sh", "sinh"): return math.sinh(vals[0])
    if name in ("ch", "cosh"): return math.cosh(vals[0])
    if name in ("th", "tanh"): return math.tanh(vals[0])
    if name in ("cth", "coth"): return 1.0 / math.tanh(vals[0])
    if name == "sec": return 1.0 / math.cos(vals[0])
    if name in ("cosec", "csc"): return 1.0 / math.sin(vals[0])
    if name == "ln": return math.log(vals[0])
    if name == "lg" or name == "log10": return math.log10(vals[0])
    if name == "log":
        if len(vals) == 1:
            return math.log10(vals[0])
        return math.log(vals[1], vals[0])
    if name == "sqrt": return math.sqrt(vals[0])
    if name == "abs": return abs(vals[0])
    if name == "sign": return float((vals[0] > 0) - (vals[0] < 0))
    if name == "mod": return math.fmod(vals[0], vals[1])
    if name == "min": return min(vals)
    if name == "max": return max(vals)
    if name in ("nthroot", "root"):
        if len(vals) == 1:
            return math.sqrt(vals[0])
        return vals[0] ** (1.0 / vals[1])
    raise EvalError("unsupported function %r/%d" % (name, len(a)))


class EvalResult:
    def __init__(self):
        self.env = {}
        self.values = {}        # region id -> value (for display regions)
        self.definitions = {}   # name -> value at the moment of assignment
        self.errors = {}        # region id -> message
        self.order = []

    def get(self, rid):
        return self.values.get(rid)

    def __repr__(self):
        return "EvalResult(%d values, %d errors)" % (len(self.values),
                                                    len(self.errors))


def evaluate(regions, env=None):
    """Run every math region in id order.  Returns an EvalResult."""
    res = EvalResult()
    ctx = {"env": dict(env or {})}
    for reg in sorted((r for r in regions if r.kind == "math"), key=lambda r: r.id):
        if not reg.tokens:
            continue
        try:
            tree = build_tree(reg.tokens)
            value = _eval_node(tree, ctx)
            if tree.kind == "assign":
                res.definitions[node_identifier(tree.args[0])] = value
            res.values[reg.id] = value
            res.order.append((reg.id, value))
        except Exception as exc:                  # noqa: BLE001 - report, don't raise
            res.errors[reg.id] = "%s: %s" % (type(exc).__name__, exc)
    res.env = ctx["env"]
    return res


def verify_results(ws, res=None, rtol=1e-9):
    """Compare every cached <result> with the value our interpreter computes.

    Returns (ok, problems) where problems is a list of human-readable strings.
    """
    res = res or evaluate(ws.regions)
    problems = []
    for reg in ws.math_regions():
        if not reg.result_tokens:
            continue
        try:
            cached = _eval_node(build_tree(reg.result_tokens), {"env": {}})
        except Exception as exc:                  # noqa: BLE001
            problems.append("region %s: cannot read <result>: %s" % (reg.id, exc))
            continue
        got = res.values.get(reg.id)
        if got is None:
            problems.append("region %s: no computed value" % reg.id)
            continue
        if not _close(got, cached, rtol):
            problems.append("region %s: cached %r vs computed %r" % (reg.id, cached, got))
    return (not problems), problems


def _close(a, b, rtol=1e-9):
    try:
        if a == b:
            return True
        return abs(a - b) <= rtol * max(abs(a), abs(b), 1e-300)
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# CLI:  python smread.py file.sm  -> printed summary + computed values
# ---------------------------------------------------------------------------
def _main(argv):
    import sys
    if len(argv) < 2:
        print("usage: python smread.py <file.sm>")
        return 2
    ws = parse(argv[1])
    print(ws.summary())
    res = evaluate(ws.regions)
    for rid, val in res.order:
        print("  region %-3s => %r" % (rid, val))
    for rid, msg in res.errors.items():
        print("  region %-3s !! %s" % (rid, msg))
    ok, problems = verify_results(ws, res)
    print("cached <result> check:", "OK" if ok else problems)
    return 0 if not res.errors and ok else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv))
