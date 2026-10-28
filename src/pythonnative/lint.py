"""Static checks for the rules of hooks, behind `pn lint`.

The linter parses Python source with the standard library's `ast` module,
so it has no dependencies and never imports or runs the code it checks.
It reports four rules:

- ``PN101``: a hook is called conditionally: inside an ``if``, a loop, a
  ``try``, a ``match``, a comprehension, a lambda, a conditional
  expression, the right side of ``and``/``or``, a nested function, or
  after an early ``return``.
- ``PN102``: a hook is called outside a ``@component`` function or a
  ``use_*`` custom hook (including at module level).
- ``PN103``: an effect, memo, or callback reads a local name that its
  literal dependency list leaves out.
- ``PN104``: ``key=`` is passed to a module-level ``@component``; use
  ``.with_key(...)`` on the returned element instead.

A syntax error is reported as ``PN000``. A trailing ``# pn: ignore``
comment silences every finding on its line, and
``# pn: ignore[PN101,PN103]`` silences only the listed codes.

Example:
    ```python
    from pythonnative.lint import lint_source

    for finding in lint_source(source, "app/main.py"):
        print(finding.format())
    ```
"""

from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

__all__ = ["CODES", "Finding", "lint_paths", "lint_source"]

CODES: dict[str, str] = {
    "PN000": "the file could not be parsed",
    "PN101": "hook called conditionally, in a loop, or in a nested function",
    "PN102": "hook called outside a component or custom hook",
    "PN103": "dependency list is missing a name the callback reads",
    "PN104": "key= passed to a user component",
}
"""Every code `pn lint` can report, with a one-line summary."""

_HOOK_RE = re.compile(r"^_*use_[a-z]")
_IGNORE_RE = re.compile(r"#\s*pn:\s*ignore(?:\[([A-Za-z0-9,\s]*)\])?")
_DEPS_HOOKS = frozenset({"use_effect", "use_layout_effect", "use_memo", "use_callback", "use_focus_effect"})
_CALLBACK_KEYWORDS = ("effect", "factory", "callback")
_STABLE_PAIR_HOOKS = frozenset({"use_state", "use_reducer"})
# Hooks whose result is created once and keeps its identity for the component's lifetime.
_STABLE_HOOKS = frozenset({"use_ref", "use_animated_value"})
_SKIP_DIRS = frozenset({".git", "build", "dist", "__pycache__", "node_modules", "site"})

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
_Comprehension = ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
_ScopeNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef | _Comprehension
_NESTED_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


@dataclass(frozen=True)
class Finding:
    """One problem found by the linter.

    Attributes:
        path: The file the finding is in, as it was passed to the linter.
        line: 1-based line number.
        col: 1-based column number.
        code: Rule code, such as ``"PN101"``.
        message: Human-readable explanation.
    """

    path: str
    line: int
    col: int
    code: str
    message: str

    def format(self) -> str:
        """Return the finding as ``path:line:col: CODE message``."""
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Return the finding as a JSON-serializable dictionary."""
        return {
            "path": self.path,
            "line": self.line,
            "col": self.col,
            "code": self.code,
            "message": self.message,
        }


# ======================================================================
# Public entry points
# ======================================================================


def lint_source(source: str, filename: str) -> list[Finding]:
    """Lint one module's source text.

    Args:
        source: The Python source to check.
        filename: The path reported in each finding. The file isn't read.

    Returns:
        The findings, sorted by position, with suppressed ones removed.
        A syntax error yields a single ``PN000`` finding.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        message = f"syntax error: {exc.msg}"
        return [Finding(filename, exc.lineno or 1, exc.offset or 1, "PN000", message)]

    checker = _Checker(filename, _module_components(tree), _wrapped_functions(tree))
    checker.visit(tree)
    ignores = _ignore_comments(source)
    kept = [finding for finding in checker.findings if not _is_ignored(finding, ignores)]
    # Stable sort: findings on one position keep the order they were found in.
    return sorted(dict.fromkeys(kept), key=lambda f: (f.line, f.col))


def lint_paths(paths: Iterable[str | os.PathLike[str]]) -> list[Finding]:
    """Lint every Python file under ``paths``.

    Directories are searched recursively for ``*.py`` files, skipping
    ``.git``, ``build``, ``dist``, ``.venv*``, ``__pycache__``,
    ``node_modules``, and ``site``. A file named directly is linted
    whatever its suffix.

    Args:
        paths: Files and directories to check.

    Returns:
        All findings, ordered by path and then by position.

    Raises:
        FileNotFoundError: If one of ``paths`` doesn't exist.
    """
    findings: list[Finding] = []
    for file in _collect_files(paths):
        try:
            source = file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append(Finding(str(file), 1, 1, "PN000", f"can't decode as UTF-8: {exc.reason}"))
            continue
        findings.extend(lint_source(source, str(file)))
    return findings


# ======================================================================
# File discovery and suppression comments
# ======================================================================


def _collect_files(paths: Iterable[str | os.PathLike[str]]) -> Iterator[Path]:
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            candidates: Iterable[Path] = [path]
        elif path.is_dir():
            candidates = _walk_python_files(path)
        else:
            raise FileNotFoundError(f"no such file or directory: {raw}")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def _walk_python_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".venv"))
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _ignore_comments(source: str) -> dict[int, frozenset[str] | None]:
    """Map line numbers to the codes their ``# pn: ignore`` comment silences.

    ``None`` means every code.
    """
    comments: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comments.append((token.start[0], token.string))
    except (tokenize.TokenError, SyntaxError):
        comments = [(number, line) for number, line in enumerate(source.splitlines(), start=1) if "#" in line]

    ignores: dict[int, frozenset[str] | None] = {}
    for number, text in comments:
        match = _IGNORE_RE.search(text)
        if match is None:
            continue
        if match.group(1) is None:
            ignores[number] = None
        else:
            ignores[number] = frozenset(code.strip().upper() for code in match.group(1).split(",") if code.strip())
    return ignores


def _is_ignored(finding: Finding, ignores: dict[int, frozenset[str] | None]) -> bool:
    if finding.line not in ignores:
        return False
    codes = ignores[finding.line]
    return codes is None or finding.code in codes


# ======================================================================
# Name helpers
# ======================================================================


def _final_name(node: ast.expr) -> str | None:
    """Return ``use_state`` for ``use_state``, ``pn.use_state``, or ``a.b.use_state``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_hook_name(name: str | None) -> bool:
    """Whether ``name`` names a hook: ``use_`` then a lowercase letter, after any leading underscores."""
    return name is not None and _HOOK_RE.match(name) is not None


def _hook_called(node: ast.AST) -> str | None:
    """Return the hook name if ``node`` is a hook call, else ``None``."""
    if isinstance(node, ast.Call):
        name = _final_name(node.func)
        if _is_hook_name(name):
            return name
    return None


def _is_component(node: _FunctionNode) -> bool:
    """Whether ``node`` carries ``@component`` (bare, dotted, or called), even under ``@memo``."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _final_name(target) in ("component", "builtin_component"):
            return True
    return False


def _wrapped_functions(tree: ast.Module) -> frozenset[str]:
    """Names passed straight to ``component(fn)`` or ``Component(fn, ...)`` anywhere in the module.

    Those functions render as components even without the decorator.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _final_name(node.func) in ("component", "Component")
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            names.add(node.args[0].id)
    return frozenset(names)


def _module_components(tree: ast.Module) -> dict[str, _FunctionNode]:
    return {
        stmt.name: stmt
        for stmt in tree.body
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_component(stmt)
    }


def _declares_param(node: _FunctionNode, name: str) -> bool:
    args = node.args
    return any(arg.arg == name for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs))


# ======================================================================
# Scope analysis (for PN103)
# ======================================================================


def _scope_roots(scope: _ScopeNode) -> list[ast.AST]:
    """Return the nodes evaluated inside ``scope``'s own namespace."""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return list(scope.body)
    if isinstance(scope, ast.Lambda):
        return [scope.body]
    roots: list[ast.AST] = [scope.key, scope.value] if isinstance(scope, ast.DictComp) else [scope.elt]
    for generator in scope.generators:
        roots += [generator.target, generator.iter, *generator.ifs]
    return roots


def _walk_scope(roots: Iterable[ast.AST]) -> Iterator[ast.AST]:
    """Yield every node under ``roots`` without entering nested scopes.

    Nested scope nodes (functions, lambdas, classes, comprehensions) are
    yielded themselves, but their contents aren't.
    """
    stack = list(roots)[::-1]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, _NESTED_SCOPES):
            continue
        stack.extend(list(ast.iter_child_nodes(node))[::-1])


@dataclass
class _Bindings:
    """Names a scope binds, and which of those bindings are stable across renders."""

    stable: dict[str, bool] = field(default_factory=dict)
    defs: dict[str, _FunctionNode] = field(default_factory=dict)

    def add(self, name: str, *, stable: bool = False) -> None:
        self.stable[name] = self.stable.get(name, True) and stable

    @property
    def names(self) -> set[str]:
        return set(self.stable)


def _function_params(args: ast.arguments) -> list[str]:
    params = [arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg is not None:
        params.append(args.vararg.arg)
    if args.kwarg is not None:
        params.append(args.kwarg.arg)
    return params


def _empty_deps(call: ast.expr) -> bool:
    """Whether ``call`` passes a literal empty list or tuple as its dependencies."""
    if not isinstance(call, ast.Call):
        return False
    deps: Optional[ast.expr] = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "deps":
            deps = keyword.value
    return isinstance(deps, (ast.List, ast.Tuple)) and not deps.elts


def _stable_targets(roots: Iterable[ast.AST]) -> set[int]:
    """Return ids of ``Name`` targets bound to stable hook results.

    Those are the setter in ``value, set_value = use_state(...)``, the
    dispatcher in ``state, dispatch = use_reducer(...)``, any name
    assigned straight from ``use_ref(...)`` or ``use_animated_value(...)``, and any name assigned from
    ``use_memo(...)`` or ``use_callback(...)`` with a literal empty
    dependency list (computed once, so it never changes).
    """
    stable: set[int] = set()
    for node in _walk_scope(roots):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        hook = _hook_called(value)
        once = hook in ("use_memo", "use_callback") and _empty_deps(value)
        for target in targets:
            if (hook in _STABLE_HOOKS or once) and isinstance(target, ast.Name):
                stable.add(id(target))
            elif (
                hook in _STABLE_PAIR_HOOKS
                and isinstance(target, (ast.Tuple, ast.List))
                and len(target.elts) == 2
                and isinstance(target.elts[1], ast.Name)
            ):
                stable.add(id(target.elts[1]))
    return stable


def _bindings(scope: _ScopeNode) -> _Bindings:
    """Collect the names bound in ``scope``'s own namespace."""
    result = _Bindings()
    if isinstance(scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        for generator in scope.generators:
            for target in ast.walk(generator.target):
                if isinstance(target, ast.Name):
                    result.add(target.id)
        return result

    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        for param in _function_params(scope.args):
            result.add(param)

    roots = _scope_roots(scope)
    stable_ids = _stable_targets(roots)
    declared_outer: set[str] = set()
    for node in _walk_scope(roots):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            result.add(node.id, stable=id(node) in stable_ids)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.add(node.name)
            result.defs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            result.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # A function-local import binds the same object on every render.
            for alias in node.names:
                if alias.name != "*":
                    result.add(alias.asname or alias.name.split(".")[0], stable=True)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            result.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            result.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            result.add(node.rest)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            declared_outer.update(node.names)
    for name in declared_outer:
        result.stable.pop(name, None)
        result.defs.pop(name, None)
    return result


def _free_reads(scope: _ScopeNode) -> list[ast.Name]:
    """Return the ``Name`` loads in ``scope`` that resolve outside it."""
    local = _bindings(scope).names
    reads: list[ast.Name] = []
    for node in _walk_scope(_scope_roots(scope)):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in local:
                reads.append(node)
        elif isinstance(node, _NESTED_SCOPES):
            reads.extend(name for name in _free_reads(node) if name.id not in local)
        elif isinstance(node, ast.Nonlocal):
            # ``nonlocal x`` reads (and writes) the enclosing ``x``.
            for name in node.names:
                reads.append(ast.Name(id=name, ctx=ast.Load(), lineno=node.lineno, col_offset=node.col_offset))
    return reads


# ======================================================================
# The checker
# ======================================================================


@dataclass
class _Owner:
    """A component or custom hook whose body hooks may be called from."""

    node: _FunctionNode
    bindings: _Bindings
    early_return: bool = False


def _contains_return(stmt: ast.stmt) -> bool:
    return any(isinstance(node, ast.Return) for node in _walk_scope([stmt]))


class _Checker(ast.NodeVisitor):
    def __init__(self, filename: str, components: dict[str, _FunctionNode], wrapped: frozenset[str]) -> None:
        self.filename = filename
        self.components = components
        self.wrapped = wrapped
        self.findings: list[Finding] = []
        self.owner: _Owner | None = None
        # Why the current position is conditional relative to ``owner``, or None.
        self.reason: str | None = None
        # True while in the owner's own namespace (not a lambda, comprehension, or nested def).
        self.direct = False
        # The innermost enclosing non-owner function, for PN102 messages.
        self.function: str | None = None

    # -- helpers ---------------------------------------------------------

    def report(self, node: ast.AST, code: str, message: str) -> None:
        line = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0) + 1
        self.findings.append(Finding(self.filename, line, col, code, message))

    @contextmanager
    def conditional(self, reason: str, *, leaves_scope: bool = False) -> Iterator[None]:
        saved = (self.reason, self.direct)
        if self.reason is None:
            self.reason = reason
        if leaves_scope:
            self.direct = False
        try:
            yield
        finally:
            self.reason, self.direct = saved

    def block(self, stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            self.visit(stmt)
            if (
                self.owner is not None
                and self.direct
                and not isinstance(stmt, (ast.Return, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and _contains_return(stmt)
            ):
                self.owner.early_return = True

    def visit_all(self, nodes: Iterable[ast.AST | None]) -> None:
        for node in nodes:
            if node is not None:
                self.visit(node)

    # -- scopes ----------------------------------------------------------

    def visit_Module(self, node: ast.Module) -> None:
        self.block(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def _function(self, node: _FunctionNode) -> None:
        # Decorators and defaults run where the ``def`` is, not in the body.
        self.visit_all(node.decorator_list)
        self.visit_all(node.args.defaults)
        self.visit_all(node.args.kw_defaults)

        saved = (self.owner, self.reason, self.direct, self.function)
        try:
            if _is_component(node) or node.name in self.wrapped or _is_hook_name(node.name):
                self.owner = _Owner(node, _bindings(node))
                self.reason, self.direct, self.function = None, True, None
                self.block(node.body)
            elif self.owner is not None:
                with self.conditional(f"the nested function '{node.name}'", leaves_scope=True):
                    self.block(node.body)
            else:
                self.function = node.name
                self.block(node.body)
        finally:
            self.owner, self.reason, self.direct, self.function = saved

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.visit_all(node.decorator_list)
        self.visit_all(node.bases)
        self.visit_all(keyword.value for keyword in node.keywords)
        if self.owner is not None:
            with self.conditional(f"the nested class '{node.name}'", leaves_scope=True):
                self.block(node.body)
        else:
            saved = self.function
            self.function = node.name
            try:
                self.block(node.body)
            finally:
                self.function = saved

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.visit_all(node.args.defaults)
        self.visit_all(node.args.kw_defaults)
        with self.conditional("a lambda", leaves_scope=True):
            self.visit(node.body)

    def _comprehension(self, node: _Comprehension) -> None:
        first, *rest = node.generators
        # The first iterable is evaluated once, in the enclosing scope.
        self.visit(first.iter)
        with self.conditional("a comprehension", leaves_scope=True):
            self.visit(first.target)
            self.visit_all(first.ifs)
            for generator in rest:
                self.visit(generator)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._comprehension(node)

    # -- control flow ----------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        with self.conditional("an 'if' statement"):
            self.block(node.body)
            self.block(node.orelse)

    def _for(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        self.visit(node.target)
        with self.conditional("a 'for' loop"):
            self.block(node.body)
            self.block(node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self._for(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._for(node)

    def visit_While(self, node: ast.While) -> None:
        with self.conditional("a 'while' loop"):
            self.visit(node.test)
            self.block(node.body)
            self.block(node.orelse)

    def _try(self, node: ast.Try | ast.TryStar) -> None:
        with self.conditional("a 'try' statement"):
            self.block(node.body)
            for handler in node.handlers:
                self.visit_all([handler.type])
                self.block(handler.body)
            self.block(node.orelse)
            self.block(node.finalbody)

    def visit_Try(self, node: ast.Try) -> None:
        self._try(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._try(node)

    def _with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item)
        self.block(node.body)

    def visit_With(self, node: ast.With) -> None:
        self._with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._with(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        with self.conditional("a 'match' statement"):
            for case in node.cases:
                self.visit(case.pattern)
                self.visit_all([case.guard])
                self.block(case.body)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.visit(node.test)
        with self.conditional("a conditional expression"):
            self.visit(node.body)
            self.visit(node.orelse)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        first, *rest = node.values
        self.visit(first)
        operator = "and" if isinstance(node.op, ast.And) else "or"
        with self.conditional(f"the right side of '{operator}'"):
            self.visit_all(rest)

    # -- calls -----------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        hook = _hook_called(node)
        if hook is not None:
            self._check_hook_placement(node, hook)
            if self.owner is not None and self.direct and hook in _DEPS_HOOKS:
                self._check_deps(node, hook, self.owner)
        self._check_key(node)
        self.generic_visit(node)

    def _check_hook_placement(self, node: ast.Call, hook: str) -> None:
        if self.owner is None:
            if self.function is None:
                where = "at module level"
            else:
                where = f"in '{self.function}', which is neither a @component function nor a use_* custom hook"
            self.report(
                node,
                "PN102",
                f"hook '{hook}' is called {where}; call hooks only from a @component function "
                "or a use_* custom hook",
            )
        elif self.reason is not None:
            self.report(
                node,
                "PN101",
                f"hook '{hook}' is called inside {self.reason}; call hooks unconditionally "
                f"at the top level of '{self.owner.node.name}'",
            )
        elif self.owner.early_return:
            self.report(
                node,
                "PN101",
                f"hook '{hook}' is called after an early return; call hooks unconditionally "
                f"at the top level of '{self.owner.node.name}', before any return",
            )

    def _check_deps(self, node: ast.Call, hook: str, owner: _Owner) -> None:
        callback: ast.expr | None = node.args[0] if node.args else None
        deps: ast.expr | None = node.args[1] if len(node.args) >= 2 else None
        for keyword in node.keywords:
            if keyword.arg in _CALLBACK_KEYWORDS and callback is None:
                callback = keyword.value
            elif keyword.arg == "deps" and deps is None:
                deps = keyword.value
        if not isinstance(deps, (ast.List, ast.Tuple)):
            return

        scope: _ScopeNode | None = None
        own_name: str | None = None
        if isinstance(callback, ast.Lambda):
            scope = callback
        elif isinstance(callback, ast.Name) and callback.id in owner.bindings.defs:
            scope = owner.bindings.defs[callback.id]
            own_name = callback.id
        if scope is None:
            return

        listed = {name.id for element in deps.elts for name in ast.walk(element) if isinstance(name, ast.Name)}
        required = owner.bindings.stable
        reported: set[str] = set()
        reads = sorted(_free_reads(scope), key=lambda name: (name.lineno, name.col_offset))
        for read in reads:
            name = read.id
            if (
                name in reported
                or name == own_name
                or name in listed
                or name not in required
                or required[name]  # stable: a use_state setter, use_reducer dispatch, use_ref, or import
            ):
                continue
            reported.add(name)
            self.report(
                deps,
                "PN103",
                f"{hook} callback reads '{name}' but it is missing from the dependency list",
            )

    def _check_key(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name) or node.func.id not in self.components:
            return
        component = self.components[node.func.id]
        if _declares_param(component, "key"):
            return
        for keyword in node.keywords:
            if keyword.arg == "key":
                self.report(
                    keyword,
                    "PN104",
                    f"'{node.func.id}' is a user component, which doesn't accept key=; "
                    f"use {node.func.id}(...).with_key(...) instead",
                )
