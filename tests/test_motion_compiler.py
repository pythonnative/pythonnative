"""The worklet compiler and release precompilation (RFC 0009)."""

from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from pythonnative.motion import WorkletError, worklet
from pythonnative.motion import worklets as worklets_module
from pythonnative.motion.compiler import compile_node
from pythonnative.motion.precompile import find_worklets, precompile_source, precompile_tree
from pythonnative.motion.program import Program


def compile_source(source: str) -> Program:
    tree = ast.parse(textwrap.dedent(source))
    node = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.Lambda)))
    return compile_node(node, "app/screen.py", "f", node.lineno)


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ("while x:\n        pass", "for i in range(n)"),
        ("try:\n        pass\n    except Exception:\n        pass", "`try`"),
        ("import math", "import"),
        ("global y", "shared value"),
        ("g = lambda: 1", "lambda"),
        ("return f'{x}'", "f-strings"),
        ("return {i for i in range(3)}", "sets"),
        ("return x[1:2]", "slices"),
        ("del x", "`del`"),
        ("x.items = 1", "`.value`"),
        ("return x.keys()", "method calls"),
        ("return (y := 2)", "`:=`"),
        ("for i in range(3):\n        pass\n    else:\n        pass", "for ... else"),
        ("return print(*x)", "star"),
        ("return ~x", "`~`"),
    ],
)
def test_unsupported_constructs_name_the_problem_and_its_place(body: str, fragment: str) -> None:
    with pytest.raises(WorkletError) as caught:
        compile_source(f"def f(x):\n    {body}\n")
    error = caught.value
    assert fragment in error.message
    assert error.filename == "app/screen.py" and error.lineno >= 2


def test_parameters_must_be_positional() -> None:
    for signature in ("x=1", "*args", "**kwargs", "*, x"):
        with pytest.raises(WorkletError, match="positional"):
            compile_source(f"def f({signature}):\n    return 1\n")


def test_captures_fold_attribute_chains_but_not_value() -> None:
    program = compile_source("""
        def f(event):
            return styles.colors.accent, SNAP[2], offset.value, pn.with_spring(0), event.y
        """)
    described = {(capture.describe(), capture.mode) for capture in program.captures}
    assert ("styles.colors.accent", "value") in described
    assert ("SNAP[2]", "value") in described
    assert ("offset", "value") in described
    assert ("pn.with_spring", "call") in described
    assert all(capture.root != "event" for capture in program.captures)


def test_run_on_python_marks_its_target_as_a_callback() -> None:
    program = compile_source("def f(i):\n    run_on_python(done, i)\n")
    assert [(c.describe(), c.mode) for c in program.captures] == [("run_on_python", "call"), ("done", "callback")]


def test_capturing_an_unsupported_value_or_call_fails_at_install() -> None:
    import pythonnative as pn
    from pythonnative.motion.worklets import Encoder, closure_wire

    def plain() -> int:
        return 1

    @worklet
    def calls_python() -> int:
        return plain()

    with pytest.raises(WorkletError, match="mark it @pn.worklet"):
        closure_wire(calls_python, encoder=Encoder())

    holder = object()

    @worklet
    def captures_object() -> Any:
        return holder

    with pytest.raises(WorkletError, match="can't capture"):
        closure_wire(captures_object, encoder=Encoder())

    @worklet
    def uses_easing() -> Any:
        return pn.with_timing(1, easing=pn.Easing.ease_out)

    encoder = Encoder()
    closure_wire(uses_easing, encoder=encoder)  # Easing curves encode as data


def test_worklet_only_apis_need_a_marker() -> None:
    from pythonnative.motion.worklets import require_worklet

    def plain() -> None:
        return None

    with pytest.raises(TypeError, match="@pn.worklet function or an inline lambda"):
        require_worklet(plain, "use_animated_style")
    assert require_worklet(lambda: None, "use_animated_style") is not None


def test_find_worklets_covers_decorators_lambdas_and_keywords() -> None:
    tree = ast.parse(textwrap.dedent("""
            @pn.worklet
            def a(): ...
            @worklet
            def b(): ...
            def c(): ...
            style = pn.use_animated_style(lambda: {})
            pn.with_timing(1, on_finish=lambda done: None)
            ignored = map(lambda v: v, [])
            """))
    found = list(find_worklets(tree))
    assert sorted(getattr(node, "name", "<lambda>") for node in found) == ["<lambda>", "<lambda>", "a", "b"]


def test_precompile_keys_tell_lambdas_on_one_line_apart(tmp_path: Path) -> None:
    source = (
        "import pythonnative as pn\n\n"
        "a = pn.use_animated_style(lambda: {'opacity': 1}); b = pn.use_animated_style(lambda: {'opacity': 0})\n"
    )
    entries, errors = precompile_source(source, "app/screen.py")
    assert not errors
    lambdas = entries["3:<lambda>"]
    assert len(lambdas) == 2 and lambdas[0]["body"] != lambdas[1]["body"]


def test_release_tables_replace_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A release build ships no source: the precompiled table is what compiles worklets."""
    package = tmp_path / "app"
    package.mkdir()
    source = textwrap.dedent("""
        import pythonnative as pn

        @pn.worklet
        def double(x):
            return x * 2

        triple = pn.worklet(lambda x: x * 3)
        """)
    (package / "motions.py").write_text(source)
    assert precompile_tree(package, "app") == []
    table = json.loads((package / "pn_worklets.json").read_text())
    assert set(table["app/motions.py"]) == {"4:double", "8:<lambda>"}

    namespace: dict[str, Any] = {}
    exec(compile(source, "/bundle/app/motions.py", "exec"), namespace)  # no source on disk at this path
    monkeypatch.setattr(worklets_module, "_precompiled", table)
    worklets_module.forget_programs()
    try:
        for name in ("double", "triple"):
            _ident, program = worklets_module.program_for(namespace[name])
            assert program.params == 1
    finally:
        worklets_module.forget_programs()


def test_precompile_reports_every_broken_worklet(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import pythonnative as pn\n\n@pn.worklet\ndef f():\n    while True:\n        pass\n"
    )
    errors = precompile_tree(tmp_path, "app")
    assert len(errors) == 1 and errors[0].filename == "app/bad.py" and errors[0].lineno == 5
    assert not (tmp_path / "pn_worklets.json").exists()
