"""Typed records, a native badge, and a cancellable native inbox service."""

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Protocol

from pythonnative.sdk import element_factory, register_component
from pythonnative.sdk.schema import ModuleSchema, NativeField, register_schema


@dataclass(frozen=True, slots=True)
class InboxRecord:
    """Portable data shared with the native extension."""

    identifier: str
    title: str
    labels: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True, slots=True)
class InboxBatch:
    """The native service's filtered result and bundled resource message."""

    records: list[InboxRecord]
    message: str


@dataclass(frozen=True)
class InboxBadgeProps:
    """A measured native label with a typed press event."""

    count: Annotated[int, NativeField(invalidates_layout=True)] = 0
    on_press: Callable[[int], Any] | None = None


class InboxToolsProtocol(Protocol):
    async def prepare(self, records: list[InboxRecord], *, limit: int = 10, delay_ms: int = 50) -> InboxBatch: ...


register_component(name="InboxBadge", props=InboxBadgeProps)
register_schema(ModuleSchema.from_protocol("InboxTools", InboxToolsProtocol, events={"prepared": InboxBatch}))
InboxBadge = element_factory("InboxBadge")

from .api import InboxTools  # noqa: E402

__all__ = ["InboxBadge", "InboxBadgeProps", "InboxBatch", "InboxRecord", "InboxTools"]
