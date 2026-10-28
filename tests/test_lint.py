import argparse
import dataclasses
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

import pythonnative.cli.pn as pn_cli
from pythonnative.lint import CODES, Finding, lint_paths, lint_source


def lint(source: str) -> List[Finding]:
    return lint_source(textwrap.dedent(source), "app/main.py")


def codes(source: str) -> List[Tuple[str, int]]:
    return [(finding.code, finding.line) for finding in lint(source)]


def only(source: str, code: str) -> List[Finding]:
    return [finding for finding in lint(source) if finding.code == code]


def run_pn(args: List[str], cwd: str, env: Optional[Dict[str, str]] = None) -> "subprocess.CompletedProcess[str]":
    cmd = [sys.executable, "-m", "pythonnative.cli.pn"] + args
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True, env=env)


# ======================================================================
# Finding
# ======================================================================


def test_finding_format_and_dict() -> None:
    finding = Finding("app/main.py", 3, 5, "PN101", "hook 'use_state' is called inside an 'if' statement")

    assert finding.format() == "app/main.py:3:5: PN101 hook 'use_state' is called inside an 'if' statement"
    assert finding.to_dict() == {
        "path": "app/main.py",
        "line": 3,
        "col": 5,
        "code": "PN101",
        "message": "hook 'use_state' is called inside an 'if' statement",
    }


def test_finding_is_frozen() -> None:
    finding = Finding("a.py", 1, 1, "PN101", "m")

    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.line = 2  # type: ignore[misc]


def test_codes_are_documented() -> None:
    assert set(CODES) == {"PN000", "PN101", "PN102", "PN103", "PN104"}


def test_clean_component_has_no_findings() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def Counter(step: int = 1):
            count, set_count = pn.use_state(0)
            ref = pn.use_ref(None)
            pn.use_effect(lambda: print(count, step), [count, step])
            with open("x") as fh:
                pn.use_memo(lambda: fh, [fh])
            return pn.Button(f"{count}", on_press=lambda: set_count(count + step))
    """
    assert lint(source) == []


# ======================================================================
# PN101: conditional hooks
# ======================================================================


@pytest.mark.parametrize(
    "body, reason",
    [
        ("if flag:\n        pn.use_state(0)", "an 'if' statement"),
        ("if flag:\n        pass\n    elif other:\n        pn.use_state(0)", "an 'if' statement"),
        ("if flag:\n        pass\n    else:\n        pn.use_state(0)", "an 'if' statement"),
        ("for i in range(3):\n        pn.use_state(i)", "a 'for' loop"),
        ("for i in range(3):\n        pass\n    else:\n        pn.use_state(0)", "a 'for' loop"),
        ("while flag:\n        pn.use_state(0)", "a 'while' loop"),
        ("while pn.use_ref(0):\n        pass", "a 'while' loop"),
        ("try:\n        pn.use_state(0)\n    except Exception:\n        pass", "a 'try' statement"),
        ("try:\n        pass\n    except Exception:\n        pn.use_state(0)", "a 'try' statement"),
        ("try:\n        pass\n    finally:\n        pn.use_state(0)", "a 'try' statement"),
        (
            "try:\n        pass\n    except Exception:\n        pass\n    else:\n        pn.use_state(0)",
            "a 'try' statement",
        ),
        ("match flag:\n        case 1:\n            pn.use_state(0)", "a 'match' statement"),
        ("xs = [pn.use_state(i) for i in range(3)]", "a comprehension"),
        ("xs = {pn.use_state(i) for i in range(3)}", "a comprehension"),
        ("xs = {i: pn.use_state(i) for i in range(3)}", "a comprehension"),
        ("xs = list(pn.use_state(i) for i in range(3))", "a comprehension"),
        ("xs = [i for i in range(3) if pn.use_state(i)]", "a comprehension"),
        ("f = lambda: pn.use_state(0)", "a lambda"),
        ("x = pn.use_state(0) if flag else None", "a conditional expression"),
        ("x = None if flag else pn.use_state(0)", "a conditional expression"),
        ("x = flag and pn.use_state(0)", "the right side of 'and'"),
        ("x = flag or pn.use_state(0)", "the right side of 'or'"),
        ("def handler():\n        pn.use_state(0)", "the nested function 'handler'"),
        ("async def handler():\n        pn.use_state(0)", "the nested function 'handler'"),
        ("class Inner:\n        x = pn.use_state(0)", "the nested class 'Inner'"),
    ],
)
def test_pn101_flags_conditional_hooks(body: str, reason: str) -> None:
    source = f"import pythonnative as pn\n\n@pn.component\ndef App(flag, other):\n    {body}\n    return None\n"

    findings = lint_source(source, "app/main.py")

    assert [f.code for f in findings] == ["PN101"]
    assert f"inside {reason}" in findings[0].message
    assert "'App'" in findings[0].message


def test_pn101_async_for_and_trystar() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        async def App(items):
            async for item in items:
                pn.use_state(item)
            try:
                pass
            except* ValueError:
                pn.use_ref(None)
    """
    assert codes(source) == [("PN101", 7), ("PN101", 11)]


@pytest.mark.parametrize(
    "body",
    [
        "if pn.use_state(0):\n        pass",
        "for i in pn.use_memo(lambda: [1], []):\n        pass",
        "with pn.use_ref(None) as r:\n        pn.use_state(r)",
        "x = pn.use_state(0) and flag",
        "x = None if pn.use_ref(0) else 1",
        "xs = [i for i in pn.use_memo(lambda: [1], [])]",
        "match pn.use_state(0):\n        case _:\n            pass",
        "x = pn.use_state(pn.use_context(None))",
        "def handler(default=pn.use_ref(None)):\n        return default",
    ],
)
def test_pn101_allows_unconditional_positions(body: str) -> None:
    source = f"import pythonnative as pn\n\n@pn.component\ndef App(flag):\n    {body}\n    return None\n"

    assert lint_source(source, "app/main.py") == []


def test_pn101_reports_the_outermost_reason() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(flag):
            if flag:
                for i in range(2):
                    pn.use_state(i)
    """
    [finding] = lint(source)
    assert "inside an 'if' statement" in finding.message


def test_pn101_hooks_after_an_early_return() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(items):
            theme = pn.use_context(None)
            if not items:
                return None
            count, set_count = pn.use_state(0)
            with open("x"):
                pn.use_ref(None)
            return None
    """
    findings = lint(source)
    assert [(f.code, f.line) for f in findings] == [("PN101", 9), ("PN101", 11)]
    assert "after an early return" in findings[0].message


def test_pn101_early_return_detected_in_nested_blocks() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(flag):
            with open("x"):
                if flag:
                    return None
                pn.use_state(0)
            for i in range(3):
                if i:
                    return None
            pn.use_ref(None)
    """
    assert codes(source) == [("PN101", 9), ("PN101", 13)]


def test_pn101_return_in_nested_function_is_not_an_early_return() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(flag):
            def handler():
                if flag:
                    return 1
                return 2
            cb = lambda: 3
            count, set_count = pn.use_state(0)
            return None
    """
    assert lint(source) == []


def test_pn101_applies_inside_custom_hooks() -> None:
    source = """
        import pythonnative as pn

        def use_counter(flag):
            if flag:
                pn.use_state(0)

        def _use_private(flag):
            for _ in range(flag):
                pn.use_ref(None)
    """
    findings = lint(source)
    assert [(f.code, f.line) for f in findings] == [("PN101", 6), ("PN101", 10)]
    assert "'use_counter'" in findings[0].message
    assert "'_use_private'" in findings[1].message


def test_pn101_nested_component_and_hook_bodies_start_fresh() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(flag):
            if flag:
                @pn.component
                def Inner():
                    pn.use_state(0)
                    return None

                def use_inner():
                    return pn.use_ref(None)
            return None
    """
    assert lint(source) == []


def test_pn101_calls_to_custom_hooks_are_hooks() -> None:
    source = """
        import pythonnative as pn
        from app.hooks import use_counter

        @pn.component
        def App(flag):
            if flag:
                use_counter()
                hooks.use_ref()
                _use_private()
    """
    assert codes(source) == [("PN101", 8), ("PN101", 9), ("PN101", 10)]


# ======================================================================
# PN102: hooks outside components
# ======================================================================


def test_pn102_module_level_hook() -> None:
    [finding] = lint("import pythonnative as pn\nstate = pn.use_state(0)\n")

    assert finding.code == "PN102"
    assert (finding.line, finding.col) == (2, 9)
    assert "at module level" in finding.message


def test_pn102_plain_function_and_method() -> None:
    source = """
        import pythonnative as pn

        def helper():
            return pn.use_state(0)

        class Screen:
            def render(self):
                return pn.use_ref(None)

            x = pn.use_context(None)
    """
    findings = lint(source)
    assert [(f.code, f.line) for f in findings] == [("PN102", 5), ("PN102", 9), ("PN102", 11)]
    assert "in 'helper', which is neither" in findings[0].message
    assert "in 'render'" in findings[1].message
    assert "in 'Screen'" in findings[2].message


def test_pn102_default_argument_runs_at_definition_time() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(value=pn.use_state(0)):
            return None
    """
    [finding] = lint(source)
    assert finding.code == "PN102"
    assert "at module level" in finding.message


@pytest.mark.parametrize(
    "decorators",
    [
        "@component",
        "@pn.component",
        "@pythonnative.component",
        "@pn.component()",
        "@pn.memo\n@pn.component",
        "@memo\n@component",
        "@pn.memo(equal=eq)\n@pn.component",
    ],
)
def test_pn102_recognizes_component_decorators(decorators: str) -> None:
    source = f"{decorators}\ndef App():\n    count, set_count = pn.use_state(0)\n    return None\n"

    assert lint_source(source, "app/main.py") == []


def test_pn102_memo_alone_is_not_a_component() -> None:
    source = "@pn.memo\ndef App():\n    return pn.use_state(0)\n"

    assert [f.code for f in lint_source(source, "app/main.py")] == ["PN102"]


def test_pn102_function_wrapped_with_component_call_counts() -> None:
    source = """
        import pythonnative as pn
        from pythonnative.component import Component

        def make(kind):
            def render(**props):
                pn.use_ref(None)
                return None

            return Component(render, display_name=kind)

        def _body():
            return pn.use_state(0)

        Body = pn.component(_body)
    """
    assert lint(source) == []


def test_pn102_hooks_in_a_nested_function_of_a_component_are_pn101() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App():
            def on_press():
                pn.use_state(0)
            return None
    """
    assert codes(source) == [("PN101", 7)]


def test_pn102_hooks_in_a_nested_function_of_a_plain_function() -> None:
    source = """
        import pythonnative as pn

        def outer():
            def inner():
                pn.use_state(0)
    """
    [finding] = lint(source)
    assert finding.code == "PN102"
    assert "in 'inner'" in finding.message


@pytest.mark.parametrize(
    "call", ["user_id()", "use_()", "useState()", "use_State()", "pn.used()", "reuse_x()", "self.user_name()"]
)
def test_pn102_ignores_names_that_are_not_hooks(call: str) -> None:
    assert lint_source(f"def f():\n    {call}\n{call}\n", "a.py") == []


# ======================================================================
# PN103: exhaustive deps
# ======================================================================


def test_pn103_lambda_reads_a_missing_prop() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(user_id: int):
            pn.use_effect(lambda: print(user_id), [])
            return None
    """
    [finding] = lint(source)
    assert finding.code == "PN103"
    assert finding.message == "use_effect callback reads 'user_id' but it is missing from the dependency list"
    # Reported at the dependency list, so an ignore comment there works.
    assert (finding.line, finding.col) == (6, 43)


def test_pn103_named_function_callback() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App(query):
            results, set_results = pn.use_state([])
            page = 1

            async def load():
                set_results(await fetch(query, page))

            pn.use_effect(load, [query])
            return None
    """
    findings = only(source, "PN103")
    assert [f.message for f in findings] == [
        "use_effect callback reads 'page' but it is missing from the dependency list"
    ]


@pytest.mark.parametrize("hook", ["use_effect", "use_layout_effect", "use_memo", "use_callback", "use_focus_effect"])
def test_pn103_checks_every_deps_hook(hook: str) -> None:
    source = f"@component\ndef App(x):\n    pn.{hook}(lambda: x, [])\n    return None\n"

    [finding] = lint_source(source, "a.py")
    assert finding.message.startswith(f"{hook} callback reads 'x'")


def test_pn103_ignores_hooks_without_deps_semantics() -> None:
    source = """
        @component
        def App(x):
            pn.use_imperative_handle(ref, lambda: x, [])
            pn.use_state(lambda: x)
            pn.use_subscription(lambda cb: x, lambda: x)
            return None
    """
    assert lint(source) == []


@pytest.mark.parametrize("deps", ["None", "deps", "list(xs)", "tuple(xs)"])
def test_pn103_skips_non_literal_deps(deps: str) -> None:
    source = f"@component\ndef App(x, deps, xs):\n    use_effect(lambda: x, {deps})\n    return None\n"

    assert lint_source(source, "a.py") == []


def test_pn103_skips_omitted_deps() -> None:
    assert lint("@component\ndef App(x):\n    use_effect(lambda: x)\n    use_memo(lambda: x)\n") == []


def test_pn103_accepts_keyword_arguments_and_tuples() -> None:
    source = """
        @component
        def App(a, b, c):
            use_effect(effect=lambda: (a, b), deps=(a,))
            use_memo(lambda: c, deps=[])
            use_callback(callback=lambda: a, deps=[a])
            return None
    """
    assert [(f.line, f.message.split("'")[1]) for f in lint(source)] == [(4, "b"), (5, "c")]


def test_pn103_attribute_reads_count_as_the_root_name() -> None:
    source = """
        @component
        def App(props, style):
            use_effect(lambda: print(props.title, style["color"]), [])
            use_effect(lambda: print(props.title), [props.title])
            use_effect(lambda: print(props.title), [props])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["props", "style"]


def test_pn103_tuple_unpacking_targets_are_locals() -> None:
    source = """
        @component
        def App(pair):
            left, (right, extra) = pair
            use_memo(lambda: left + right + extra, [left])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["right", "extra"]


def test_pn103_state_value_is_required_but_setter_and_dispatch_are_not() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App():
            count, set_count = pn.use_state(0)
            state, dispatch = pn.use_reducer(reducer, {})
            [items, set_items] = use_state([])
            pn.use_effect(lambda: (set_count(1), dispatch("x"), set_items([])), [])
            pn.use_effect(lambda: print(count, state), [])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["count", "state"]


def test_pn103_refs_are_exempt() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def App():
            timer = pn.use_ref(None)
            box: pn.Ref[int] = pn.use_ref(0)
            pn.use_effect(lambda: print(timer.current, box.current), [])
            return None
    """
    assert lint(source) == []


def test_pn103_reassigned_stable_names_are_required() -> None:
    source = """
        @component
        def App(flag):
            value, set_value = use_state(0)
            ref = use_ref(None)
            if flag:
                set_value = print
                ref = None
            use_effect(lambda: (set_value(1), ref), [])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["set_value", "ref"]


def test_pn103_module_level_builtin_and_imported_names_are_exempt() -> None:
    source = """
        import pythonnative as pn

        LIMIT = 10

        def helper(x):
            return x

        @pn.component
        def App():
            import json
            from os import path as osp
            pn.use_effect(lambda: print(LIMIT, helper(1), len([]), json.dumps({}), osp.sep, pn.Text), [])
            return None
    """
    assert lint(source) == []


def test_pn103_local_functions_are_required_deps() -> None:
    source = """
        @component
        def App(x):
            def format_value():
                return x

            use_memo(lambda: format_value(), [])
            use_memo(lambda: format_value(), [format_value])
            return None
    """
    [finding] = lint(source)
    assert finding.message.split("'")[1] == "format_value"
    assert finding.line == 7


def test_pn103_callback_params_and_locals_are_not_deps() -> None:
    source = """
        @component
        def App(items):
            use_callback(lambda event, items=None: print(event, items), [])

            def handler(value):
                total = value * 2
                return [total + i for i in range(total)]

            use_callback(handler, [])
            return None
    """
    assert lint(source) == []


def test_pn103_nested_scopes_inside_the_callback_are_followed() -> None:
    source = """
        @component
        def App(a, b, c):
            def effect():
                def inner():
                    return a
                values = [b for _ in range(2)]
                return lambda: c
            use_effect(effect, [])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["a", "b", "c"]


def test_pn103_nonlocal_counts_as_a_read() -> None:
    source = """
        @component
        def App():
            counter = 0
            def effect():
                nonlocal counter
                counter += 1
            use_effect(effect, [])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["counter"]


def test_pn103_reports_each_missing_name_once_in_read_order() -> None:
    source = """
        @component
        def App(b, a):
            use_effect(lambda: (b, a, b, a), [])
            return None
    """
    assert [f.message.split("'")[1] for f in lint(source)] == ["b", "a"]


def test_pn103_recursive_callback_does_not_need_itself() -> None:
    source = """
        @component
        def App():
            def poll():
                schedule(poll)
            use_effect(poll, [])
            return None
    """
    assert lint(source) == []


def test_pn103_skips_callbacks_it_cannot_see() -> None:
    source = """
        @component
        def App(x, make):
            handler = make(x)
            use_effect(handler, [])
            use_effect(make(x), [])
            use_effect(external_effect, [])
            return None
    """
    assert lint(source) == []


def test_pn103_works_in_custom_hooks_and_conditionals() -> None:
    source = """
        def use_title(title):
            use_effect(lambda: set_title(title), [])

        @component
        def App(flag, x):
            if flag:
                use_effect(lambda: x, [])  # pn: ignore[PN101]
            return None
    """
    assert codes(source) == [("PN103", 3), ("PN103", 8)]


def test_pn103_is_not_checked_for_hooks_in_nested_functions() -> None:
    source = """
        @component
        def App(x):
            def later():
                use_effect(lambda: x, [])
            return None
    """
    assert codes(source) == [("PN101", 5)]


# ======================================================================
# PN104: key= on user components
# ======================================================================


def test_pn104_flags_key_on_a_module_level_component() -> None:
    source = """
        import pythonnative as pn

        @pn.component
        def Row(item):
            return pn.Text(item)

        @pn.memo
        @pn.component
        def Cell(item):
            return pn.Text(item)

        @pn.component
        def App(items):
            return pn.Column(
                *[Row(item, key=item) for item in items],
                Cell("x", key="c"),
            )
    """
    findings = lint(source)
    assert [(f.code, f.line) for f in findings] == [("PN104", 16), ("PN104", 17)]
    assert findings[0].col == 21
    assert findings[0].message == (
        "'Row' is a user component, which doesn't accept key=; use Row(...).with_key(...) instead"
    )


def test_pn104_ignores_builtins_with_key_and_other_calls() -> None:
    source = """
        import pythonnative as pn
        import widgets

        @pn.component
        def Row(item):
            return pn.Text(item, key=item)

        @pn.component
        def Keyed(item, key=None):
            return None

        def plain(key=None):
            return None

        @pn.component
        def App(items):
            def Local(key=None):
                return None
            return pn.Column(
                pn.View(key="a"),
                Row("x").with_key("x"),
                Keyed("y", key="y"),
                plain(key="z"),
                widgets.Row("x", key="w"),
                Local(key="l"),
            )
    """
    assert lint(source) == []


# ======================================================================
# Suppression and syntax errors
# ======================================================================


def test_ignore_comment_suppresses_all_codes_on_its_line() -> None:
    source = """
        state = use_state(0)  # pn: ignore
        other = use_state(0)
    """
    assert codes(source) == [("PN102", 3)]


def test_ignore_comment_with_codes() -> None:
    source = """
        @component
        def App(flag, x):
            if flag:
                use_effect(lambda: x, [])  # pn: ignore[PN103]
                use_effect(lambda: x, [])  # pn: ignore[PN101, PN103]
                use_effect(lambda: x, [])  # pn:ignore[pn101,PN103]
                use_effect(lambda: x, [])  # noqa  # pn: ignore[PN104]
            return None
    """
    assert codes(source) == [("PN101", 5), ("PN101", 8), ("PN103", 8)]


def test_ignore_comment_applies_to_the_finding_line_only() -> None:
    source = """
        @component
        def App(x):
            use_effect(  # pn: ignore
                lambda: x,
                [],
            )
            use_effect(
                lambda: x,
                [],  # pn: ignore[PN103]
            )
            return None
    """
    assert codes(source) == [("PN103", 6)]


def test_ignore_text_inside_a_string_is_not_a_comment() -> None:
    source = 'x = use_state("# pn: ignore")\n'

    assert [f.code for f in lint_source(source, "a.py")] == ["PN102"]


def test_syntax_error_is_pn000() -> None:
    [finding] = lint_source("def broken(:\n    pass\n", "bad.py")

    assert finding.code == "PN000"
    assert finding.path == "bad.py"
    assert finding.line == 1
    assert finding.message.startswith("syntax error:")


def test_findings_are_sorted_by_position() -> None:
    source = "b = use_ref()\na = use_state()\n"

    assert [f.line for f in lint_source(source, "a.py")] == [1, 2]


# ======================================================================
# lint_paths
# ======================================================================


BAD = "import pythonnative as pn\nstate = pn.use_state(0)\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_lint_paths_walks_directories_and_skips_tool_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "app" / "main.py", BAD)
    _write(tmp_path / "app" / "screens" / "home.py", BAD)
    _write(tmp_path / "app" / "notes.txt", BAD)
    for skipped in (".git", "build", "dist", ".venv", ".venv-313", "__pycache__", "node_modules", "site"):
        _write(tmp_path / skipped / "x.py", BAD)
        _write(tmp_path / "app" / skipped / "x.py", BAD)

    findings = lint_paths([tmp_path])

    assert sorted(Path(f.path).relative_to(tmp_path).as_posix() for f in findings) == [
        "app/main.py",
        "app/screens/home.py",
    ]


def test_lint_paths_accepts_files_of_any_suffix_and_dedupes(tmp_path: Path) -> None:
    script = _write(tmp_path / "script", BAD)
    main = _write(tmp_path / "main.py", BAD)

    findings = lint_paths([str(script), main, tmp_path])

    assert [f.path for f in findings] == [str(script), str(main)]


def test_lint_paths_reports_decode_errors_and_syntax_errors(tmp_path: Path) -> None:
    (tmp_path / "latin.py").write_bytes(b"x = '\xff'\n")
    _write(tmp_path / "broken.py", "def (\n")

    findings = lint_paths([tmp_path])

    assert [(Path(f.path).name, f.code) for f in findings] == [("broken.py", "PN000"), ("latin.py", "PN000")]


def test_lint_paths_raises_for_missing_paths(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nope"):
        lint_paths([tmp_path / "nope"])


def test_lint_paths_clean_tree(tmp_path: Path) -> None:
    _write(tmp_path / "ok.py", "@component\ndef App():\n    use_state(0)\n")

    assert lint_paths([tmp_path]) == []


# ======================================================================
# CLI
# ======================================================================


def test_lint_command_human_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "bad.py", BAD)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as info:
        pn_cli.lint_command(argparse.Namespace(paths=["bad.py"], json=False))

    assert info.value.code == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("bad.py:2:9: PN102 hook 'use_state' is called at module level")
    assert out[-1] == "Found 1 problem."


def test_lint_command_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "bad.py", BAD + "other = pn.use_ref()\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as info:
        pn_cli.lint_command(argparse.Namespace(paths=["bad.py"], json=True))

    assert info.value.code == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [(item["path"], item["line"], item["col"], item["code"]) for item in payload] == [
        ("bad.py", 2, 9, "PN102"),
        ("bad.py", 3, 9, "PN102"),
    ]
    assert set(payload[0]) == {"path", "line", "col", "code", "message"}
    assert captured.err.strip() == "Found 2 problems."


def test_lint_command_clean_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "ok.py", "x = 1\n")
    monkeypatch.chdir(tmp_path)

    pn_cli.lint_command(argparse.Namespace(paths=["ok.py"], json=False))
    assert capsys.readouterr().out.strip() == "No problems found."

    pn_cli.lint_command(argparse.Namespace(paths=["ok.py"], json=True))
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert captured.err.strip() == "No problems found."


def test_lint_command_defaults_to_app_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "outside.py", BAD)
    _write(tmp_path / "app" / "main.py", "x = 1\n")
    monkeypatch.chdir(tmp_path)

    pn_cli.lint_command(argparse.Namespace(paths=[], json=False))

    assert capsys.readouterr().out.strip() == "No problems found."


def test_lint_command_defaults_to_cwd_without_app_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "outside.py", BAD)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as info:
        pn_cli.lint_command(argparse.Namespace(paths=[], json=True))

    assert info.value.code == 1
    assert [item["path"] for item in json.loads(capsys.readouterr().out)] == ["outside.py"]


def test_cli_lint_exit_codes_through_argparse(tmp_path: Path) -> None:
    _write(tmp_path / "app" / "main.py", BAD)
    _write(tmp_path / "clean.py", "x = 1\n")

    dirty = run_pn(["lint"], str(tmp_path))
    assert dirty.returncode == 1, dirty.stderr
    assert dirty.stdout.startswith(f"{Path('app') / 'main.py'}:2:9: PN102 ")

    clean = run_pn(["lint", "clean.py"], str(tmp_path))
    assert clean.returncode == 0, clean.stderr

    missing = run_pn(["lint", "nope"], str(tmp_path))
    assert missing.returncode == 2
    assert "nope" in missing.stderr
    assert missing.stdout == ""


def test_cli_lint_json_through_argparse(tmp_path: Path) -> None:
    _write(tmp_path / "a.py", BAD)
    _write(tmp_path / "b.py", "x = 1\n")

    result = run_pn(["lint", "a.py", "b.py", "--json"], str(tmp_path))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert [item["code"] for item in payload] == ["PN102"]
    assert "Found 1 problem." in result.stderr


def test_cli_lint_help_lists_json(tmp_path: Path) -> None:
    result = run_pn(["lint", "--help"], str(tmp_path))

    assert result.returncode == 0
    assert "--json" in result.stdout
