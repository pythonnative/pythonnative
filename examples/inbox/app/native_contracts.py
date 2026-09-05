"""The inbox's native extension API is declared in Python."""

from dataclasses import dataclass
from typing import Annotated, Protocol

from pythonnative.sdk import element_factory, register_component
from pythonnative.sdk.schema import ModuleSchema, NativeField, register_schema


@dataclass(frozen=True)
class InboxBadgeProps:
    count: Annotated[int, NativeField(invalidates_layout=True)] = 0


class InboxToolsProtocol(Protocol):
    def format_count(self, count: int) -> str: ...

    async def ready(self) -> str: ...


register_component(name="InboxBadge", props=InboxBadgeProps)
register_schema(ModuleSchema.from_protocol("InboxTools", InboxToolsProtocol))
InboxBadge = element_factory("InboxBadge")
