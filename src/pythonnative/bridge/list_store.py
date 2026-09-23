"""Revisioned list patch semantics shared by validation and headless renderers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from ..profiling import count


@dataclass(frozen=True)
class ListRow:
    """Wire metadata for one logical row; application values stay in Python."""

    key: str
    revision: int
    extent: float
    sticky: bool = False

    def wire(self) -> list[Any]:
        """Return the compact row record used by each renderer."""
        return [self.key, self.revision, self.extent, self.sticky]


@dataclass
class ListStore:
    """Apply list patches atomically, copying order only for structural edits."""

    revision: int = 0
    keys: list[str] = field(default_factory=list)
    rows: dict[str, ListRow] = field(default_factory=dict)

    def apply(self, packet: Any) -> None:
        """Validate the entire packet before publishing any of its changes."""
        self.prepare(packet)()

    def prepare(self, packet: Any) -> Callable[[], None]:
        """Validate a patch and return its publication without editing live state."""
        if not isinstance(packet, dict) or set(packet) != {"base", "revision", "changes"}:
            raise ValueError("Invalid list packet")
        base, revision, changes = (packet[key] for key in ("base", "revision", "changes"))
        if (
            type(base) is not int
            or base != self.revision
            or type(revision) is not int
            or revision != base + 1
            or revision > 9_007_199_254_740_991
        ):
            raise ValueError("Stale list revision")
        if not isinstance(changes, list):
            raise ValueError("List changes must be an array")
        keys = self.keys
        edited: dict[str, ListRow] = {}
        deleted: set[str] = set()
        reset = False

        def exists(key: Any) -> bool:
            return isinstance(key, str) and key not in deleted and (key in edited or not reset and key in self.rows)

        def order() -> list[str]:
            nonlocal keys
            if keys is self.keys:
                keys = list(keys)
                count("list.order_copies")
            return keys

        def row(values: Any) -> ListRow:
            if not isinstance(values, list) or len(values) != 4:
                raise ValueError("Invalid list row")
            key, version, extent, sticky = values
            if (
                not isinstance(key, str)
                or not key
                or type(version) is not int
                or not 1 <= version <= 9_007_199_254_740_991
            ):
                raise ValueError("Invalid list key or item revision")
            if type(extent) not in (int, float) or not math.isfinite(extent) or extent <= 0 or type(sticky) is not bool:
                raise ValueError("Invalid list extent or sticky flag")
            count("list.rows_validated")
            return ListRow(key, version, float(extent), sticky)

        for change in changes:
            if not isinstance(change, list) or not change:
                raise ValueError("Invalid list change")
            code = change[0]
            if code == "reset" and len(change) == 2 and isinstance(change[1], list):
                if reset or edited or deleted or keys is not self.keys:
                    raise ValueError("List reset must be the first change")
                reset, keys = True, []
                for values in change[1]:
                    item = row(values)
                    if item.key in edited:
                        raise ValueError("List keys must be unique")
                    keys.append(item.key)
                    edited[item.key] = item
            elif code == "i" and len(change) == 3:
                index, item = change[1], row(change[2])
                if type(index) is not int or not 0 <= index <= len(keys) or exists(item.key):
                    raise ValueError("Invalid list insertion")
                order().insert(index, item.key)
                edited[item.key] = item
                deleted.discard(item.key)
            elif code == "u" and len(change) == 2:
                item = row(change[1])
                if not exists(item.key):
                    raise ValueError("Unknown list update key")
                edited[item.key] = item
            elif code == "d" and len(change) == 2 and exists(change[1]):
                order().remove(change[1])
                edited.pop(change[1], None)
                deleted.add(change[1])
            elif code == "m" and len(change) == 3 and exists(change[1]):
                index = change[2]
                if type(index) is not int or not 0 <= index < len(keys):
                    raise ValueError("Invalid list move index")
                order().remove(change[1])
                keys.insert(index, change[1])
            else:
                raise ValueError("Invalid list change")

        def publish() -> None:
            if self.revision != base:
                raise ValueError("List changed before patch publication")
            if reset:
                self.rows = edited
            else:
                for key in deleted:
                    self.rows.pop(key, None)
                self.rows.update(edited)
            self.keys, self.revision = keys, revision
            count("list.patches", len(changes))

        return publish
