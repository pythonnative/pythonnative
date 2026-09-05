"""Versioned commit validation and surface ownership.

A commit is validated in full before it changes a native tree. Revisions are
strictly consecutive within an application and surface. A failed native mount
poisons that surface until the host explicitly resets and remounts it.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = 2


class CommitError(RuntimeError):
    """A malformed, stale, or failed native transaction."""


@dataclass
class ViewState:
    """Wire-visible view state used to validate a whole transaction."""

    type_name: str
    props: dict[str, Any]
    parent: int | None = None
    children: list[int] = field(default_factory=list)


@dataclass
class CommitState:
    """Committed revision and structural state for one native surface."""

    application: str = ""
    surface: int = 0
    revision: int = 0
    views: dict[int, ViewState] = field(default_factory=dict)

    def prepare(self, envelope: Any) -> CommitState:
        """Validate without mutating this state and return the candidate state."""
        if not isinstance(envelope, dict) or envelope.get("version") != PROTOCOL_VERSION:
            raise CommitError("Expected a protocol v2 commit envelope; rebuild the native client")
        application, surface, revision = (envelope.get(k) for k in ("application", "surface", "revision"))
        if not isinstance(application, str) or not application or type(surface) is not int or surface <= 0:
            raise CommitError("Invalid application or surface identity")
        if self.application and (application, surface) != (self.application, self.surface):
            raise CommitError("Commit belongs to another application or surface")
        if type(revision) is not int or revision != self.revision + 1:
            raise CommitError(f"Expected revision {self.revision + 1}, received {revision!r}")
        ops = envelope.get("ops")
        if not isinstance(ops, list):
            raise CommitError("Commit ops must be a list")
        result = CommitState(application, surface, revision, copy.deepcopy(self.views))
        for index, op in enumerate(ops):
            try:
                result._validate_op(op)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                raise CommitError(f"Invalid op {index}: {exc}") from exc
        return result

    def _validate_op(self, op: Any) -> None:
        if not isinstance(op, list) or len(op) < 2:
            raise ValueError("Expected an operation array")
        code, tag = op[:2]
        lengths = {"c": 4, "u": 3, "i": 4, "d": 2, "f": 6}
        if code not in lengths or len(op) != lengths[code] or type(tag) is not int or tag <= 0:
            raise ValueError("Invalid opcode, arity, or tag")
        if code == "c":
            if tag in self.views or not isinstance(op[2], str) or not op[2] or not isinstance(op[3], dict):
                raise ValueError("Invalid or duplicate create")
            self.views[tag] = ViewState(op[2], dict(op[3]))
            return
        view = self.views[tag]
        if code == "u":
            if not isinstance(op[2], dict):
                raise ValueError("Update requires a property mapping")
            for name, value in op[2].items():
                if value is None:
                    view.props.pop(name, None)
                else:
                    view.props[name] = value
        elif code == "i":
            child_tag, index = op[2:]
            if type(child_tag) is not int or type(index) is not int or index < 0:
                raise ValueError("Invalid child or insertion index")
            child = self.views[child_tag]
            ancestor: int | None = tag
            while ancestor is not None:
                if ancestor == child_tag:
                    raise ValueError("Insertion creates a cycle")
                ancestor = self.views[ancestor].parent
            if child.parent is not None:
                self.views[child.parent].children.remove(child_tag)
            if index > len(view.children):
                raise ValueError("Insertion index exceeds child count")
            view.children.insert(index, child_tag)
            child.parent = tag
        elif code == "d":
            if view.children:
                raise ValueError("Destroy children before their parent")
            if view.parent is not None:
                self.views[view.parent].children.remove(tag)
            del self.views[tag]
        elif code == "f":
            if any(type(n) not in (float, int) or not math.isfinite(n) for n in op[2:]):
                raise ValueError("Frame values must be finite numbers")
            if op[4] < 0 or op[5] < 0:
                raise ValueError("Frame sizes must be nonnegative")

    def acknowledgement(self) -> dict[str, Any]:
        """Identify the exact revision native successfully mounted."""
        return {"ok": True, "application": self.application, "surface": self.surface, "revision": self.revision}
