"""Generated Python interfaces. Regenerate from the declarations."""

# ruff: noqa: E501, E402, F401, I001
# fmt: off
from __future__ import annotations
from typing import Any, Callable, Literal
from pythonnative.mutations import UNSET, UnsetType
from pythonnative.sdk.types import decode_value, resolve_type
from pythonnative.style import DynamicColor as PNDynamicColor
from pythonnative.style import EdgeInsets as PNEdgeInsets
from inbox_extension import InboxBatch as PNInboxBatch
from inbox_extension import InboxRecord as PNInboxRecord
from pythonnative.style import ShadowOffset as PNShadowOffset
from pythonnative.style import Style as PNStyle
from pythonnative.style import TransformPerspective as PNTransformPerspective
from pythonnative.style import TransformRotate as PNTransformRotate
from pythonnative.style import TransformRotateX as PNTransformRotateX
from pythonnative.style import TransformRotateY as PNTransformRotateY
from pythonnative.style import TransformRotateZ as PNTransformRotateZ
from pythonnative.style import TransformScale as PNTransformScale
from pythonnative.style import TransformScaleX as PNTransformScaleX
from pythonnative.style import TransformScaleY as PNTransformScaleY
from pythonnative.style import TransformSkewX as PNTransformSkewX
from pythonnative.style import TransformSkewY as PNTransformSkewY
from pythonnative.style import TransformTranslate as PNTransformTranslate

from pythonnative.native_modules.registry import native_module

class InboxTools:
    @staticmethod
    async def prepare(*, records: list[PNInboxRecord], limit: int = decode_value(10, {'type': 'integer'}), delay_ms: int = decode_value(50, {'type': 'integer'})) -> PNInboxBatch:
        """Invoke the checked InboxTools.prepare native method."""
        return await native_module("InboxTools").call_async("prepare", records=records, limit=limit, delay_ms=delay_ms)

    @staticmethod
    def on_prepared(callback: Callable[[PNInboxBatch], Any]) -> Callable[[], None]:
        """Subscribe to the typed InboxTools.prepared event."""
        return native_module("InboxTools").add_listener("prepared", callback)
