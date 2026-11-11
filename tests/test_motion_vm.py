"""The worklet VM agrees with CPython (RFC 0009).

Every case runs twice: as ordinary Python, and compiled to the core's
bytecode and interpreted by the host build of the renderer core. Results
must match exactly, and so must the exception type when CPython raises.
"""

from __future__ import annotations

import itertools
import json
import linecache
import math
import random
from typing import Any, Callable, Dict, List

import pytest

from pythonnative.bridge.core import load_core
from pythonnative.motion.worklets import Encoder, closure_wire, worklet

_counter = itertools.count()


def make(source: str, env: Dict[str, Any] | None = None) -> Callable[..., Any]:
    """Define a worklet from source the compiler can find, as if it lived in a file."""
    filename = f"<worklet-{next(_counter)}>"
    lines = source.splitlines(keepends=True)
    linecache.cache[filename] = (len(source), None, lines, filename)
    namespace: Dict[str, Any] = {"math": math, **(env or {})}
    exec(compile(source, filename, "exec"), namespace)
    fn = next(value for key, value in namespace.items() if key == "f")
    return worklet(fn)


def in_core(fn: Callable[..., Any], *args: Any) -> Dict[str, Any]:
    encoder = Encoder(lambda callback: 1)
    wire = closure_wire(fn, encoder=encoder)
    request = {
        "programs": {str(ident): program.document() for ident, program in encoder.programs.items()},
        "closure": wire,
        "args": list(args),
        "shared": {str(value.id): value._value for value in encoder.shared},
    }
    return json.loads(load_core().worklet_eval(json.dumps(request)))


def _jsonish(value: Any) -> Any:
    """Tuples cross the core as JSON arrays."""
    if isinstance(value, (tuple, list)):
        return [_jsonish(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonish(item) for key, item in value.items()}
    return value


def same(fn: Callable[..., Any], *args: Any) -> None:
    expected: Any = None
    try:
        expected = fn(*args)
        raised = None
    except Exception as error:  # noqa: BLE001 - the VM must raise the same type
        raised = type(error).__name__
    if isinstance(expected, complex) and raised is None:
        # Worklets have no complex numbers: a negative base to a fractional power raises.
        raised = "ValueError"
    reply = in_core(fn, *args)
    if raised is not None:
        assert not reply["ok"] and reply["error_type"] == raised, (args, reply)
        return
    assert reply["ok"], (args, reply)
    got = reply["value"]
    expected = _jsonish(expected)
    if isinstance(expected, float) and isinstance(got, (int, float)):
        assert got == pytest.approx(expected, rel=1e-12, abs=1e-12) or (math.isnan(expected) and math.isnan(got))
        assert isinstance(got, float), f"{args}: VM returned int {got} for float {expected}"
    else:
        assert got == expected and type(got) is type(expected), (args, got, expected)


NUMBERS = [0, 1, -1, 2, -3, 7, -7, 10, 0.0, 0.5, -0.5, 2.5, 3.5, -2.5, 1e-9, 123.456, -0.0]
BINARY = ["+", "-", "*", "/", "//", "%", "**"]
COMPARE = ["<", "<=", "==", "!=", ">", ">="]


@pytest.mark.parametrize("operator", BINARY)
def test_arithmetic_matches_python(operator: str) -> None:
    fn = make(f"def f(a, b):\n    return a {operator} b\n")
    for a, b in itertools.product(NUMBERS, NUMBERS):
        if operator == "**" and (abs(b) > 8 or (isinstance(a, float) and abs(a) > 100)):
            continue
        same(fn, a, b)


@pytest.mark.parametrize("operator", COMPARE)
def test_comparisons_match_python(operator: str) -> None:
    fn = make(f"def f(a, b):\n    return a {operator} b\n")
    for a, b in itertools.product(NUMBERS[:10], NUMBERS[:10]):
        same(fn, a, b)


def test_generated_expressions_match_python() -> None:
    rng = random.Random(9)
    atoms = ["a", "b", "c", "1", "2", "-3", "0.5", "True", "None"]

    def expression(depth: int) -> str:
        if depth == 0 or rng.random() < 0.3:
            return rng.choice(atoms)
        kind = rng.random()
        if kind < 0.4:
            return f"({expression(depth - 1)} {rng.choice(BINARY[:6])} {expression(depth - 1)})"
        if kind < 0.6:
            return f"({expression(depth - 1)} {rng.choice(COMPARE)} {expression(depth - 1)})"
        if kind < 0.75:
            return f"({expression(depth - 1)} {rng.choice(['and', 'or'])} {expression(depth - 1)})"
        if kind < 0.85:
            return f"({expression(depth - 1)} if {expression(depth - 1)} else {expression(depth - 1)})"
        if kind < 0.92:
            return f"(not {expression(depth - 1)})"
        return f"(-{expression(depth - 1)})"

    for _ in range(300):
        body = expression(4)
        fn = make(f"def f(a, b, c):\n    return {body}\n")
        for args in ((3, -2, 0.25), (0, 5, -1.5), (-4, -4, 2)):
            same(fn, *args)


def test_builtins_and_math_match_python() -> None:
    cases = [
        "abs(a)",
        "round(a)",
        "round(a, 1)",
        "int(a)",
        "float(a)",
        "bool(a)",
        "min(a, b, 2)",
        "max((a, b))",
        "math.floor(a)",
        "math.ceil(a)",
        "math.sqrt(abs(a))",
        "math.atan2(a, b)",
        "math.hypot(a, b)",
        "math.copysign(1, a)",
        "math.pi * a",
        "len((a, b, 3))",
    ]
    for case in cases:
        fn = make(f"def f(a, b):\n    return {case}\n")
        for a, b in ((2.5, -1), (-3.5, 4), (0.5, 0.5), (7, 2), (-0.0, 3)):
            same(fn, a, b)


def test_statements_loops_and_comprehensions_match_python() -> None:
    source = """
def f(n, step):
    total = 0
    pairs = []
    for i in range(n, -n, step):
        if i % 3 == 0:
            continue
        if total > 50:
            break
        total += i * i
        pairs = pairs + [(i, total)]
    a, b = (total, len(pairs))
    squares = [x * x for x in range(n) if x % 2]
    labels = {"t": total, "first": pairs[0] if pairs else None, "s": squares}
    for left, right in pairs:
        a -= left
    return (a, b, labels, 1 < n <= 10 != step)
"""
    fn = make(source)
    for n, step in ((5, -1), (6, -2), (3, -3), (0, -1)):
        same(fn, n, step)


def test_errors_carry_type_and_line() -> None:
    fn = make("def f(x):\n    y = x + 1\n    return y / 0\n")
    reply = in_core(fn, 2)
    assert reply == {"ok": False, "error_type": "ZeroDivisionError", "message": "division by zero", "line": 3}
    for source, error in (
        ("def f(x):\n    return x['k']\n", "KeyError"),
        ("def f(x):\n    return (1, 2)[5]\n", "IndexError"),
        ("def f(x):\n    return 'a' < 1\n", "TypeError"),
        ("def f(x):\n    a, b = (1, 2, 3)\n    return a\n", "ValueError"),
        ("def f(x):\n    return math.sqrt(-1)\n", "ValueError"),
    ):
        reply = in_core(make(source), {"k": 1} if "k" in source and "KeyError" != error else {})
        assert reply["error_type"] == error, (source, reply)


def test_the_instruction_budget_stops_runaway_loops() -> None:
    fn = make("def f(n):\n    t = 0\n    for i in range(n):\n        t += i\n    return t\n")
    assert in_core(fn, 100)["value"] == 4950
    reply = in_core(fn, 10_000_000)
    assert reply["error_type"] == "RuntimeError" and "budget" in reply["message"]


def test_captures_and_linked_worklets() -> None:
    from pythonnative.motion import SharedValue

    level = SharedValue(4)
    table: Dict[str, Any] = {"scale": 3, "points": (10, 20)}

    @worklet
    def helper(x: float) -> float:
        return x * table["scale"]

    @worklet
    def f(x: float) -> List[Any]:
        level.value = level.value + 1
        return [helper(x), table["points"][1], level.value, math.tau]

    reply = in_core(f, 2)
    assert reply["value"] == [6, 20, 5, math.tau]
    assert reply["writes"] == {str(level.id): 5}


def test_motion_helpers_match_python() -> None:
    import pythonnative as pn

    env = {"pn": pn}
    for case in (
        "pn.interpolate(a, (0, 10), (0, 100))",
        "pn.interpolate(a, (0, 10), (0, 100), 'clamp')",
        "pn.interpolate(a, (0, 5, 10), (1, 0, 1), ('identity', 'clamp'))",
        "pn.clamp(a, 0, 3)",
        "pn.snap_point(a, b, (0, 100, 200))",
        "pn.interpolate_color(a, (0, 10), ('#000000', '#FFFFFF'))",
    ):
        fn = make(f"def f(a, b):\n    return {case}\n", env)
        for a, b in ((-5, 0), (2.5, 400), (7, -900), (12, 0)):
            same(fn, a, b)


def test_animation_descriptors_built_in_a_worklet_match_python() -> None:
    import pythonnative as pn

    fn = make(
        "def f(x):\n"
        "    first = pn.with_timing(x, duration=100)\n"
        "    return pn.with_sequence(first, pn.with_delay(50, pn.with_spring(0, velocity=3)))\n",
        {"pn": pn},
    )
    reply = in_core(fn, 5)
    expected = pn.with_sequence(pn.with_timing(5, duration=100), pn.with_delay(50, pn.with_spring(0, velocity=3)))
    assert reply["value"] == expected.__pn_wire__()


def test_repeat_and_delay_descriptors_carry_reduce_motion() -> None:
    import pythonnative as pn

    fn = make(
        "def f(x):\n"
        "    step = pn.with_timing(x, duration=100, reduce_motion='never')\n"
        "    return pn.with_repeat(pn.with_delay(20, step, reduce_motion='never'), times=3, reduce_motion='never')\n",
        {"pn": pn},
    )
    expected: Any = pn.with_repeat(
        pn.with_delay(20, pn.with_timing(5, duration=100, reduce_motion="never"), reduce_motion="never"),
        times=3,
        reduce_motion="never",
    )
    assert in_core(fn, 5)["value"] == expected.__pn_wire__()
    default: Any = pn.with_repeat(pn.with_timing(1))
    assert default.__pn_wire__()["reduce_motion"] == "system"


@pytest.mark.parametrize("times", [0, -1, 0.5])
def test_repeat_needs_at_least_one_run(times: float) -> None:
    import pythonnative as pn

    # Python and the core both refuse a count below 1, rather than looping forever.
    same(make("def f(x):\n    return pn.with_repeat(pn.with_timing(1), times=x)\n", {"pn": pn}), times)


_VALID_PROGRAM: Dict[str, Any] = {
    "name": "f",
    "file": "f.py",
    "line": 1,
    "params": 1,
    "locals": 1,
    "captures": 0,
    "consts": [1, None],
    "code": [2, 0, 1, 0, 12, 0, 23, 0],  # return x + 1
    "lines": [1, 1, 1, 1],
}


def _eval_program(program: Dict[str, Any]) -> Dict[str, Any]:
    request = {
        "programs": {"1": program},
        "closure": {"__closure__": {"program": 1, "captures": []}},
        "args": [2],
        "shared": {},
    }
    return json.loads(load_core().worklet_eval(json.dumps(request)))


@pytest.mark.parametrize(
    ("code", "problem"),
    [
        ([15, 9, 23, 0], "jump out of range"),
        ([5, 0, 23, 0], "stack underflow"),
        ([1, 7, 23, 0], "bad constant"),
        ([2, 3, 23, 0], "bad local"),
        ([4, 0, 23, 0], "bad capture"),
        ([12, 99, 23, 0], "stack underflow"),
        ([2, 0, 2, 0, 12, 99, 23, 0], "bad operator"),
        ([99, 0, 23, 0], "unknown opcode 99"),
        ([2, 0, 16, 3, 1, 0, 23, 0], "inconsistent stack"),
    ],
)
def test_the_verifier_rejects_malformed_programs_without_running_them(code: List[int], problem: str) -> None:
    assert _eval_program(_VALID_PROGRAM) == {"ok": True, "value": 3, "writes": {}, "calls": []}
    result = _eval_program({**_VALID_PROGRAM, "code": code, "lines": [1] * (len(code) // 2)})
    assert result["ok"] is False
    assert result["error_type"] == "ValueError"
    assert result["message"].endswith(problem), result["message"]
