"""The worklet instruction set the renderer core runs (RFC 0009).

These numbers mirror ``native/core/src/motion_vm.h``. A program is a JSON
document: constants, a capture count, flat ``[op, arg, op, arg, ...]``
code, and one source line per instruction. The core verifies every program
before it runs (operand indices, jump targets, stack depth) and gives each
run an instruction budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# Opcodes.
NOP = 0
CONST = 1
LOAD = 2
STORE = 3
CAPTURE = 4
POP = 5
DUP = 6
SWAP = 7
VALUE_GET = 8
VALUE_SET = 9
FIELD = 10
INDEX = 11
BINARY = 12
COMPARE = 13
UNARY = 14
JUMP = 15
JUMP_IF_FALSE = 16
JUMP_IF_TRUE = 17
JUMP_IF_FALSE_OR_POP = 18
JUMP_IF_TRUE_OR_POP = 19
BUILD_SEQ = 20
BUILD_MAP = 21
CALL = 22
RETURN = 23
LEN = 24
UNPACK = 25
CANCEL = 26

# BINARY operands.
ADD, SUB, MUL, TRUEDIV, FLOORDIV, MOD, POW = range(7)
# COMPARE operands.
LT, LE, EQ, NE, GT, GE, IN, NOT_IN, IS, IS_NOT = range(10)
# UNARY operands.
NEG, POS, NOT = range(3)

JUMPS = frozenset({JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, JUMP_IF_FALSE_OR_POP, JUMP_IF_TRUE_OR_POP})

_OPCODES = (
    "NOP CONST LOAD STORE CAPTURE POP DUP SWAP VALUE_GET VALUE_SET FIELD INDEX BINARY COMPARE UNARY JUMP "
    "JUMP_IF_FALSE JUMP_IF_TRUE JUMP_IF_FALSE_OR_POP JUMP_IF_TRUE_OR_POP BUILD_SEQ BUILD_MAP CALL RETURN LEN "
    "UNPACK CANCEL"
).split()
NAMES = {globals()[name]: name for name in _OPCODES}


@dataclass(frozen=True)
class Capture:
    """A name the worklet reads from its closure, globals, or builtins.

    ``path`` is the root name followed by attribute (``".name"``) and
    constant subscript (``[key]``) steps, which are evaluated once, when the
    worklet is installed. ``mode`` says how the value may be used:
    ``"value"`` (a constant, a shared value, or a worklet passed along),
    ``"call"`` (called directly: a worklet or a supported builtin), or
    ``"callback"`` (the first argument of ``run_on_python``).
    """

    root: str
    steps: Tuple[Tuple[str, Any], ...] = ()
    mode: str = "value"

    def describe(self) -> str:
        """The capture as source text, for error messages."""
        text = self.root
        for kind, key in self.steps:
            text += f".{key}" if kind == "attr" else f"[{key!r}]"
        return text


@dataclass
class Program:
    """A compiled worklet: what the core runs, and what Python resolves at install."""

    name: str
    file: str
    line: int
    params: int
    locals: int
    consts: List[Any]
    code: List[int]
    lines: List[int]
    captures: List[Capture] = field(default_factory=list)

    def document(self) -> Dict[str, Any]:
        """The JSON document the core decodes and verifies."""
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "params": self.params,
            "locals": self.locals,
            "captures": len(self.captures),
            "consts": self.consts,
            "code": self.code,
            "lines": self.lines,
        }

    def disassemble(self) -> str:
        """A readable listing (debugging and tests)."""
        out = []
        for index in range(0, len(self.code), 2):
            op, arg = self.code[index], self.code[index + 1]
            out.append(f"{index // 2:4d}  line {self.lines[index // 2]:<4d} {NAMES.get(op, op):<22} {arg}")
        return "\n".join(out)

    def to_json(self) -> Dict[str, Any]:
        """Everything needed to rebuild the program without its source (release builds)."""
        return {
            **self.document(),
            "capture_specs": [
                [capture.root, [list(step) for step in capture.steps], capture.mode] for capture in self.captures
            ],
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Program":
        """Rebuild a program written by [`to_json`][pythonnative.motion.program.Program.to_json]."""
        captures = [
            Capture(root, tuple((kind, key) for kind, key in steps), mode)
            for root, steps, mode in data["capture_specs"]
        ]
        return cls(
            name=data["name"],
            file=data["file"],
            line=data["line"],
            params=data["params"],
            locals=data["locals"],
            consts=list(data["consts"]),
            code=list(data["code"]),
            lines=list(data["lines"]),
            captures=captures,
        )
