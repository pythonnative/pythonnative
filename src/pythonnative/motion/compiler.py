"""Compile worklets: Python functions the renderer core runs on the UI thread (RFC 0009).

A worklet is ordinary, type-checked Python written in a subset the core can
verify and bound. This module parses its source with ``ast``, checks it
against the subset, and emits a [`Program`][pythonnative.motion.program.Program]:
stack-machine code plus the names it reads from outside (its captures),
which [`pythonnative.motion.worklets`][pythonnative.motion.worklets] resolves
each time the worklet is installed.

The subset:

- Parameters: positional only, without defaults. An annotation on an event
  parameter is for the type checker; the core reads the event's fields by name.
- Literals: ``int``, ``float``, ``bool``, ``None``, ``str``, tuples, lists, and
  dicts.
- Operators: arithmetic (``+ - * / // % **``), unary ``-``, ``+``, and ``not``,
  comparisons (chained, ``in``, ``is``), ``and``, ``or``, and conditional
  expressions.
- Statements: assignment (including augmented and tuple unpacking),
  ``if``/``elif``/``else``, ``for`` over ``range(...)`` or a sequence,
  ``break``, ``continue``, ``return``, ``pass``, and expression statements.
- List and tuple comprehensions over ``range(...)`` or a sequence.
- Calls to other worklets, ``abs``, ``min``, ``max``, ``round``, ``int``,
  ``float``, ``bool``, ``len``, ``math`` functions, and the motion helpers.
- ``.value`` on shared values, ``.cancel()`` on a shared value, and fields of
  event parameters.

Anything else raises [`WorkletError`][pythonnative.motion.compiler.WorkletError]
with the file, line, and column, and a suggestion.
"""

from __future__ import annotations

import ast
import linecache
import textwrap
import types
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from . import program as op
from .program import Capture, Program

__all__ = ["WorkletError", "compile_function", "compile_node", "find_node"]


class WorkletError(Exception):
    """A worklet uses Python the UI thread can't run, or failed while running there.

    Attributes:
        message: What went wrong.
        filename: The worklet's source file.
        lineno: The line, or 0 when unknown.
        col: The column, or 0 when unknown.
        error_type: For a runtime failure, the Python exception it raised
            (``"ZeroDivisionError"``, ``"TypeError"``, ...).
    """

    def __init__(self, message: str, filename: str = "", lineno: int = 0, col: int = 0, error_type: str = "") -> None:
        self.message = message
        self.filename = filename
        self.lineno = lineno
        self.col = col
        self.error_type = error_type
        where = f"{filename}:{lineno}:{col + 1}: " if filename and lineno else ""
        prefix = f"{error_type}: " if error_type else ""
        super().__init__(f"{where}{prefix}{message}")


_BINARY = {
    ast.Add: op.ADD,
    ast.Sub: op.SUB,
    ast.Mult: op.MUL,
    ast.Div: op.TRUEDIV,
    ast.FloorDiv: op.FLOORDIV,
    ast.Mod: op.MOD,
    ast.Pow: op.POW,
}
_COMPARE = {
    ast.Lt: op.LT,
    ast.LtE: op.LE,
    ast.Eq: op.EQ,
    ast.NotEq: op.NE,
    ast.Gt: op.GT,
    ast.GtE: op.GE,
    ast.In: op.IN,
    ast.NotIn: op.NOT_IN,
    ast.Is: op.IS,
    ast.IsNot: op.IS_NOT,
}
_UNSUPPORTED = {
    ast.While: "`while` loops can't run on the UI thread; use `for i in range(n)`",
    ast.Try: "`try` isn't supported in worklets; check values with `if` instead",
    ast.With: "`with` isn't supported in worklets",
    ast.AsyncWith: "`async with` isn't supported in worklets",
    ast.AsyncFor: "`async for` isn't supported in worklets",
    ast.Import: "worklets can't import; import at module level and the worklet captures the name",
    ast.ImportFrom: "worklets can't import; import at module level and the worklet captures the name",
    ast.FunctionDef: "define worklets at module level or in the component, not inside another worklet",
    ast.AsyncFunctionDef: "worklets can't be async",
    ast.ClassDef: "worklets can't define classes",
    ast.Global: "worklets can't use `global`; write to a shared value instead",
    ast.Nonlocal: "worklets can't use `nonlocal`; write to a shared value instead",
    ast.Delete: "`del` isn't supported in worklets",
    ast.Raise: "worklets can't raise; return early instead",
    ast.Assert: "worklets can't assert",
    ast.Lambda: "a worklet can't define a lambda; use another @pn.worklet function",
    ast.JoinedStr: "f-strings aren't supported in worklets",
    ast.Await: "worklets can't await",
    ast.Yield: "worklets can't yield",
    ast.YieldFrom: "worklets can't yield",
    ast.SetComp: "sets aren't supported in worklets",
    ast.Set: "sets aren't supported in worklets",
    ast.DictComp: "dict comprehensions aren't supported in worklets",
    ast.NamedExpr: "`:=` isn't supported in worklets",
    ast.Slice: "slices aren't supported in worklets",
    ast.Starred: "star arguments aren't supported in worklets",
    ast.Match: "`match` isn't supported in worklets",
}


@dataclass
class _Loop:
    breaks: List[int]
    continues: List[int]


class _Compiler:
    def __init__(self, node: Any, filename: str, name: str, firstlineno: int) -> None:
        self.node = node
        self.filename = filename
        self.name = name
        self.firstlineno = firstlineno
        self.code: List[int] = []
        self.lines: List[int] = []
        self.consts: List[Any] = []
        self._const_index: Dict[Tuple[str, Any], int] = {}
        self.locals: Dict[str, int] = {}
        self.captures: List[Capture] = []
        self._capture_index: Dict[Tuple[str, Tuple[Tuple[str, Any], ...], str], int] = {}
        self.line = firstlineno
        self.loops: List[_Loop] = []
        self.temps = 0

    # -- errors --------------------------------------------------------------

    def fail(self, node: Any, message: str) -> WorkletError:
        return WorkletError(message, self.filename, getattr(node, "lineno", self.line), getattr(node, "col_offset", 0))

    # -- emission -------------------------------------------------------------

    def emit(self, opcode: int, arg: int = 0) -> int:
        self.code.extend((opcode, arg))
        self.lines.append(self.line)
        return len(self.lines) - 1

    def here(self) -> int:
        return len(self.lines)

    def patch(self, index: int, target: int) -> None:
        self.code[index * 2 + 1] = target

    def const(self, value: Any) -> int:
        key = (type(value).__name__, value if not isinstance(value, list) else tuple(value))
        if key not in self._const_index:
            self._const_index[key] = len(self.consts)
            self.consts.append(value)
        return self._const_index[key]

    def capture(self, root: str, steps: Tuple[Tuple[str, Any], ...] = (), mode: str = "value") -> int:
        key = (root, steps, mode)
        if key not in self._capture_index:
            self._capture_index[key] = len(self.captures)
            self.captures.append(Capture(root, steps, mode))
        return self._capture_index[key]

    def local(self, name: str) -> int:
        if name not in self.locals:
            self.locals[name] = len(self.locals)
        return self.locals[name]

    def temp(self) -> int:
        self.temps += 1
        return self.local(f"$t{self.temps}")

    # -- entry ----------------------------------------------------------------

    def compile(self) -> Program:
        node = self.node
        args = node.args
        if args.vararg or args.kwarg or args.kwonlyargs or args.defaults or args.kw_defaults:
            raise self.fail(node, "worklet parameters must be positional, without defaults or *args")
        for argument in [*args.posonlyargs, *args.args]:
            self.local(argument.arg)
        params = len(self.locals)
        body = node.body
        if isinstance(node, ast.Lambda):
            self._assigned([ast.Expr(value=body)])
            self.line = getattr(body, "lineno", self.line)
            self.expr(body)
            self.emit(op.RETURN)
        else:
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]  # docstring
            self._assigned(body)
            self.block(body)
            self.emit(op.CONST, self.const(None))
            self.emit(op.RETURN)
        return Program(
            name=self.name,
            file=self.filename,
            line=self.firstlineno,
            params=params,
            locals=len(self.locals),
            consts=self.consts,
            code=self.code,
            lines=self.lines,
            captures=self.captures,
        )

    def _assigned(self, body: Sequence[ast.AST]) -> None:
        """Python's rule: a name assigned anywhere in the function is local."""
        for statement in body:
            for child in ast.walk(statement):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    self.local(child.id)

    # -- statements -------------------------------------------------------------

    def block(self, statements: Sequence[ast.stmt]) -> None:
        for statement in statements:
            self.statement(statement)

    def statement(self, node: ast.stmt) -> None:
        self.line = getattr(node, "lineno", self.line)
        for kind, message in _UNSUPPORTED.items():
            if isinstance(node, kind):
                raise self.fail(node, message)
        if isinstance(node, ast.Expr):
            self.expr(node.value)
            self.emit(op.POP)
        elif isinstance(node, ast.Assign):
            self.expr(node.value)
            for index, target in enumerate(node.targets):
                if index < len(node.targets) - 1:
                    self.emit(op.DUP)
                self.store(target)
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.expr(node.value)
                self.store(node.target)
        elif isinstance(node, ast.AugAssign):
            binary = _BINARY.get(type(node.op))
            if binary is None:
                raise self.fail(node, f"{type(node.op).__name__} isn't supported in worklets")
            target = node.target
            if isinstance(target, ast.Name):
                self.load_name(target)
                self.expr(node.value)
                self.emit(op.BINARY, binary)
                self.store(target)
            elif isinstance(target, ast.Attribute) and target.attr == "value":
                self.expr(target.value)
                self.emit(op.DUP)
                self.emit(op.VALUE_GET)
                self.expr(node.value)
                self.emit(op.BINARY, binary)
                self.emit(op.VALUE_SET)
            else:
                raise self.fail(node, "only names and `shared.value` can be updated in place")
        elif isinstance(node, ast.If):
            self.expr(node.test)
            jump = self.emit(op.JUMP_IF_FALSE)
            self.block(node.body)
            if node.orelse:
                skip = self.emit(op.JUMP)
                self.patch(jump, self.here())
                self.block(node.orelse)
                self.patch(skip, self.here())
            else:
                self.patch(jump, self.here())
        elif isinstance(node, ast.For):
            if node.orelse:
                raise self.fail(node, "`for ... else` isn't supported in worklets")
            self.loop(node.target, node.iter, lambda: self.block(node.body))
        elif isinstance(node, ast.Return):
            if node.value is None:
                self.emit(op.CONST, self.const(None))
            else:
                self.expr(node.value)
            self.emit(op.RETURN)
        elif isinstance(node, ast.Pass):
            pass
        elif isinstance(node, ast.Break):
            if not self.loops:
                raise self.fail(node, "`break` outside a loop")
            self.loops[-1].breaks.append(self.emit(op.JUMP))
        elif isinstance(node, ast.Continue):
            if not self.loops:
                raise self.fail(node, "`continue` outside a loop")
            self.loops[-1].continues.append(self.emit(op.JUMP))
        else:
            raise self.fail(node, f"{type(node).__name__} statements aren't supported in worklets")

    def store(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.emit(op.STORE, self.local(target.id))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                if isinstance(item, ast.Starred):
                    raise self.fail(item, "star unpacking isn't supported in worklets")
            self.emit(op.UNPACK, len(target.elts))
            for item in target.elts:
                self.store(item)
        elif isinstance(target, ast.Attribute) and target.attr == "value":
            # The value is on the stack; the shared value goes beneath it.
            self.expr(target.value)
            self.emit(op.SWAP)
            self.emit(op.VALUE_SET)
        elif isinstance(target, ast.Attribute):
            raise self.fail(target, f"a worklet can only assign `.value`, not `.{target.attr}`")
        elif isinstance(target, ast.Subscript):
            raise self.fail(target, "item assignment isn't supported in worklets; build a new tuple or dict")
        else:
            raise self.fail(target, "unsupported assignment target")

    def loop(self, target: ast.expr, iterator: ast.expr, body: Callable[[], None]) -> None:
        """``for target in range(...)`` or ``for target in sequence``."""
        if (
            isinstance(iterator, ast.Call)
            and isinstance(iterator.func, ast.Name)
            and iterator.func.id == "range"
            and iterator.func.id not in self.locals
        ):
            arguments = iterator.args
            if iterator.keywords or not 1 <= len(arguments) <= 3:
                raise self.fail(iterator, "range() takes one to three positional arguments")
            start, stop, step = self.temp(), self.temp(), self.temp()
            if len(arguments) == 1:
                self.emit(op.CONST, self.const(0))
                self.emit(op.STORE, start)
                self.expr(arguments[0])
                self.emit(op.STORE, stop)
            else:
                self.expr(arguments[0])
                self.emit(op.STORE, start)
                self.expr(arguments[1])
                self.emit(op.STORE, stop)
            if len(arguments) == 3:
                self.expr(arguments[2])
            else:
                self.emit(op.CONST, self.const(1))
            self.emit(op.STORE, step)
            counter = self.temp()
            self.emit(op.LOAD, start)
            self.emit(op.STORE, counter)
            top = self.here()
            # (step > 0 and counter < stop) or (step < 0 and counter > stop)
            self.emit(op.LOAD, step)
            self.emit(op.CONST, self.const(0))
            self.emit(op.COMPARE, op.GT)
            ascending = self.emit(op.JUMP_IF_FALSE)
            self.emit(op.LOAD, counter)
            self.emit(op.LOAD, stop)
            self.emit(op.COMPARE, op.LT)
            decided = self.emit(op.JUMP)
            self.patch(ascending, self.here())
            self.emit(op.LOAD, counter)
            self.emit(op.LOAD, stop)
            self.emit(op.COMPARE, op.GT)
            self.patch(decided, self.here())
            leave = self.emit(op.JUMP_IF_FALSE)
            self.emit(op.LOAD, counter)
            self.store(target)
            self.loops.append(_Loop([], []))
            body()
            loop = self.loops.pop()
            advance = self.here()
            for jump in loop.continues:
                self.patch(jump, advance)
            self.emit(op.LOAD, counter)
            self.emit(op.LOAD, step)
            self.emit(op.BINARY, op.ADD)
            self.emit(op.STORE, counter)
            self.emit(op.JUMP, top)
            end = self.here()
            self.patch(leave, end)
            for jump in loop.breaks:
                self.patch(jump, end)
            return
        items, count, index = self.temp(), self.temp(), self.temp()
        self.expr(iterator)
        self.emit(op.STORE, items)
        self.emit(op.LOAD, items)
        self.emit(op.LEN)
        self.emit(op.STORE, count)
        self.emit(op.CONST, self.const(0))
        self.emit(op.STORE, index)
        top = self.here()
        self.emit(op.LOAD, index)
        self.emit(op.LOAD, count)
        self.emit(op.COMPARE, op.LT)
        leave = self.emit(op.JUMP_IF_FALSE)
        self.emit(op.LOAD, items)
        self.emit(op.LOAD, index)
        self.emit(op.INDEX)
        self.store(target)
        self.loops.append(_Loop([], []))
        body()
        loop = self.loops.pop()
        advance = self.here()
        for jump in loop.continues:
            self.patch(jump, advance)
        self.emit(op.LOAD, index)
        self.emit(op.CONST, self.const(1))
        self.emit(op.BINARY, op.ADD)
        self.emit(op.STORE, index)
        self.emit(op.JUMP, top)
        end = self.here()
        self.patch(leave, end)
        for jump in loop.breaks:
            self.patch(jump, end)

    # -- expressions ----------------------------------------------------------

    def expr(self, node: ast.expr) -> None:
        previous = self.line
        self.line = getattr(node, "lineno", self.line)
        try:
            self._expr(node)
        finally:
            self.line = previous

    def _expr(self, node: ast.expr) -> None:
        for kind, message in _UNSUPPORTED.items():
            if isinstance(node, kind):
                raise self.fail(node, message)
        if isinstance(node, ast.Constant):
            value = node.value
            if not (value is None or isinstance(value, (bool, int, float, str))):
                raise self.fail(node, f"{type(value).__name__} constants aren't supported in worklets")
            self.emit(op.CONST, self.const(value))
        elif isinstance(node, ast.Name):
            self.load_name(node)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                self.expr(item)
            self.emit(op.BUILD_SEQ, len(node.elts))
        elif isinstance(node, ast.Dict):
            for key, item in zip(node.keys, node.values):
                if key is None:
                    raise self.fail(node, "`**` in dict literals isn't supported in worklets")
                self.expr(key)
                self.expr(item)
            self.emit(op.BUILD_MAP, len(node.keys))
        elif isinstance(node, ast.BinOp):
            binary = _BINARY.get(type(node.op))
            if binary is None:
                raise self.fail(node, f"the {type(node.op).__name__} operator isn't supported in worklets")
            self.expr(node.left)
            self.expr(node.right)
            self.emit(op.BINARY, binary)
        elif isinstance(node, ast.UnaryOp):
            self.expr(node.operand)
            if isinstance(node.op, ast.USub):
                self.emit(op.UNARY, op.NEG)
            elif isinstance(node.op, ast.UAdd):
                self.emit(op.UNARY, op.POS)
            elif isinstance(node.op, ast.Not):
                self.emit(op.UNARY, op.NOT)
            else:
                raise self.fail(node, "`~` isn't supported in worklets")
        elif isinstance(node, ast.BoolOp):
            jump = op.JUMP_IF_FALSE_OR_POP if isinstance(node.op, ast.And) else op.JUMP_IF_TRUE_OR_POP
            exits = []
            for index, operand in enumerate(node.values):
                self.expr(operand)
                if index < len(node.values) - 1:
                    exits.append(self.emit(jump))
            for index in exits:
                self.patch(index, self.here())
        elif isinstance(node, ast.Compare):
            self.compare(node)
        elif isinstance(node, ast.IfExp):
            self.expr(node.test)
            otherwise = self.emit(op.JUMP_IF_FALSE)
            self.expr(node.body)
            done = self.emit(op.JUMP)
            self.patch(otherwise, self.here())
            self.expr(node.orelse)
            self.patch(done, self.here())
        elif isinstance(node, ast.Attribute):
            self.attribute(node)
        elif isinstance(node, ast.Subscript):
            path = self.capture_path(node)
            if path is not None:
                self.emit(op.CAPTURE, self.capture(*path))
                return
            self.expr(node.value)
            self.expr(node.slice)
            self.emit(op.INDEX)
        elif isinstance(node, ast.Call):
            self.call(node)
        elif isinstance(node, (ast.ListComp, ast.GeneratorExp)):
            self.comprehension(node)
        else:
            raise self.fail(node, f"{type(node).__name__} expressions aren't supported in worklets")

    def load_name(self, node: ast.Name) -> None:
        if node.id in self.locals:
            self.emit(op.LOAD, self.locals[node.id])
        else:
            self.emit(op.CAPTURE, self.capture(node.id))

    def capture_path(self, node: ast.expr) -> Optional[Tuple[str, Tuple[Tuple[str, Any], ...]]]:
        """The constant path of an attribute/subscript chain on a captured name, if it is one.

        ``.value`` and ``.cancel`` are never folded: they act on a shared
        value at run time.
        """
        steps: List[Tuple[str, Any]] = []
        current: ast.expr = node
        while True:
            if isinstance(current, ast.Attribute):
                if current.attr in ("value", "cancel"):
                    return None
                steps.append(("attr", current.attr))
                current = current.value
            elif isinstance(current, ast.Subscript):
                key = current.slice
                if not isinstance(key, ast.Constant) or not isinstance(key.value, (int, str)):
                    return None
                steps.append(("item", key.value))
                current = current.value
            elif isinstance(current, ast.Name):
                if current.id in self.locals:
                    return None
                return current.id, tuple(reversed(steps))
            else:
                return None

    def attribute(self, node: ast.Attribute) -> None:
        if node.attr == "value":
            self.expr(node.value)
            self.emit(op.VALUE_GET)
            return
        path = self.capture_path(node)
        if path is not None:
            self.emit(op.CAPTURE, self.capture(*path))
            return
        self.expr(node.value)
        self.emit(op.FIELD, self.const(node.attr))

    def compare(self, node: ast.Compare) -> None:
        operators = [_COMPARE.get(type(item)) for item in node.ops]
        if any(item is None for item in operators):
            raise self.fail(node, "unsupported comparison")
        if len(node.ops) == 1:
            self.expr(node.left)
            self.expr(node.comparators[0])
            self.emit(op.COMPARE, operators[0])  # type: ignore[arg-type]
            return
        # a < b < c: each operand once, stopping at the first false comparison.
        left = self.temp()
        self.expr(node.left)
        self.emit(op.STORE, left)
        exits = []
        for index, (comparison, right_node) in enumerate(zip(operators, node.comparators)):
            right = self.temp()
            self.expr(right_node)
            self.emit(op.STORE, right)
            self.emit(op.LOAD, left)
            self.emit(op.LOAD, right)
            self.emit(op.COMPARE, comparison)  # type: ignore[arg-type]
            if index < len(operators) - 1:
                exits.append(self.emit(op.JUMP_IF_FALSE_OR_POP))
            left = right
        for index in exits:
            self.patch(index, self.here())

    def call(self, node: ast.Call) -> None:
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                raise self.fail(argument, "star arguments aren't supported in worklets")
        for keyword in node.keywords:
            if keyword.arg is None:
                raise self.fail(keyword, "`**` arguments aren't supported in worklets")
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "cancel":
            if node.args or node.keywords:
                raise self.fail(node, "cancel() takes no arguments")
            self.expr(func.value)
            self.emit(op.CANCEL)
            return
        if isinstance(func, ast.Name) and func.id == "range" and "range" not in self.locals:
            raise self.fail(node, "range() is only supported as a `for` loop or comprehension iterator")
        path = self.capture_path(func)
        if path is None:
            if isinstance(func, ast.Attribute):
                raise self.fail(node, f"method calls like `.{func.attr}()` aren't supported in worklets")
            if isinstance(func, ast.Name):
                self.load_name(func)  # a local holding a worklet
            else:
                raise self.fail(node, "only named functions can be called in worklets")
        else:
            root, steps = path
            callback = (steps[-1][1] if steps else root) == "run_on_python"
            self.emit(op.CAPTURE, self.capture(root, steps, "call"))
            if callback and node.args:
                first = node.args[0]
                target = self.capture_path(first)
                if target is None:
                    raise self.fail(first, "run_on_python() needs a Python function the worklet captures by name")
                self.emit(op.CAPTURE, self.capture(target[0], target[1], "callback"))
                for argument in node.args[1:]:
                    self.expr(argument)
                self._finish_call(node, len(node.args))
                return
        for argument in node.args:
            self.expr(argument)
        self._finish_call(node, len(node.args))

    def _finish_call(self, node: ast.Call, positional: int) -> None:
        if positional > 255 or len(node.keywords) > 255:
            raise self.fail(node, "too many arguments")
        for keyword in node.keywords:
            self.expr(keyword.value)
        if node.keywords:
            self.emit(op.CONST, self.const([keyword.arg for keyword in node.keywords]))
        self.emit(op.CALL, positional | (len(node.keywords) << 8))

    def comprehension(self, node: Any) -> None:
        if len(node.generators) != 1:
            raise self.fail(node, "comprehensions in worklets take one `for` clause")
        generator = node.generators[0]
        if generator.is_async:
            raise self.fail(node, "async comprehensions aren't supported in worklets")
        result = self.temp()
        self.emit(op.BUILD_SEQ, 0)
        self.emit(op.STORE, result)
        for name in ast.walk(generator.target):
            if isinstance(name, ast.Name):
                self.local(name.id)

        def body() -> None:
            skips = []
            for condition in generator.ifs:
                self.expr(condition)
                skips.append(self.emit(op.JUMP_IF_FALSE))
            self.emit(op.LOAD, result)
            self.expr(node.elt)
            self.emit(op.BUILD_SEQ, 1)
            self.emit(op.BINARY, op.ADD)
            self.emit(op.STORE, result)
            for skip in skips:
                self.patch(skip, self.here())

        self.loop(generator.target, generator.iter, body)
        self.emit(op.LOAD, result)


def compile_node(node: Any, filename: str, name: str, firstlineno: int) -> Program:
    """Compile a ``FunctionDef`` or ``Lambda`` node.

    Raises:
        WorkletError: When it uses Python a worklet can't.
    """
    if isinstance(node, ast.AsyncFunctionDef):
        raise WorkletError("worklets can't be async", filename, node.lineno, node.col_offset)
    return _Compiler(node, filename, name, firstlineno).compile()


# ======================================================================
# Finding a function's syntax tree
# ======================================================================

_trees: Dict[str, Optional[ast.Module]] = {}


def _module_tree(filename: str) -> Optional[ast.Module]:
    if filename not in _trees:
        lines = linecache.getlines(filename)
        if not lines:
            _trees[filename] = None
        else:
            try:
                _trees[filename] = ast.parse("".join(lines), filename)
            except SyntaxError:
                _trees[filename] = None
    return _trees[filename]


def forget_sources(filename: Optional[str] = None) -> None:
    """Drop cached syntax trees (Fast Refresh calls this when a file changes)."""
    if filename is None:
        _trees.clear()
        linecache.clearcache()
    else:
        _trees.pop(filename, None)
        linecache.checkcache(filename)


def node_matches(node: Any, code: types.CodeType, positions: Set[Tuple[int, int]]) -> bool:
    """Whether a ``FunctionDef`` or ``Lambda`` node is the source of ``code``."""
    if isinstance(node, ast.Lambda):
        return code.co_name == "<lambda>" and (node.body.lineno, node.body.col_offset) in positions
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        return node.name == code.co_name and first == code.co_firstlineno
    return False


def code_positions(code: types.CodeType) -> Set[Tuple[int, int]]:
    """The ``(line, column)`` each of ``code``'s instructions starts at."""
    return {(line, col) for line, _end, col, _end_col in code.co_positions() if line is not None and col is not None}


def find_node(code: types.CodeType) -> Optional[Any]:
    """The syntax tree node a code object was compiled from, when its source is available."""
    tree = _module_tree(code.co_filename)
    if tree is None:
        return None
    positions = code_positions(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)) and node_matches(
            node, code, positions
        ):
            return node
    return None


def compile_function(fn: Callable[..., Any]) -> Program:
    """Compile a function from its source.

    Raises:
        WorkletError: When the source isn't available or uses Python a worklet can't.
    """
    code = getattr(fn, "__code__", None)
    if not isinstance(code, types.CodeType):
        raise WorkletError(f"{fn!r} isn't a Python function, so it can't be a worklet")
    node = find_node(code)
    if node is None:
        # Fall back to the function's own source text (an interactive session, a REPL cell).
        try:
            import inspect

            source = textwrap.dedent(inspect.getsource(fn))
            tree = ast.parse(source)
        except (OSError, TypeError, SyntaxError) as exc:
            raise WorkletError(
                f"can't read the source of {code.co_qualname}; release builds precompile worklets with `pn build`",
                code.co_filename,
                code.co_firstlineno,
            ) from exc
        candidates = [
            child for child in ast.walk(tree) if isinstance(child, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        node = candidates[0] if candidates else None
        if node is None:
            raise WorkletError(f"can't find the source of {code.co_qualname}", code.co_filename, code.co_firstlineno)
    return compile_node(node, code.co_filename, code.co_qualname, code.co_firstlineno)
