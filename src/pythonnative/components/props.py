"""Props shared by the built-in components, declared once as ``TypedDict``s.

Every built-in view accepts the [`AccessibilityProps`][pythonnative.AccessibilityProps]
keywords, and the plain containers and [`Pressable`][pythonnative.Pressable]
also accept the [`ViewProps`][pythonnative.ViewProps] layout and gesture
keywords. Factories declare them as ``**props: Unpack[...]``, so a type
checker validates each keyword exactly as if it were spelled out in the
signature, and the reference documentation describes each one here
instead of in every factory.

```python
pn.View(
    pn.Text("Delete"),
    accessibility_label="Delete message",
    accessibility_role="button",
    test_id="delete",
    on_layout=lambda event: print(event.width),
)
```
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Sequence, TypedDict, Union

from ..style import AccessibilityAction, AccessibilityState, AccessibilityValue, ImportantForAccessibility
from .events import LayoutEvent

__all__ = ["AccessibilityProps", "ViewProps"]


class AccessibilityProps(TypedDict, total=False):
    """Assistive-technology and UI-test keywords accepted by every built-in view.

    Attributes:
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail about the result of
            acting on the view (appended to the content description on
            Android).
        accessibility_role: Semantic role (``"button"``, ``"header"``,
            ``"link"``, ``"image"``, ...). Controls with a fixed role
            (``Checkbox``, ``Switch``) supply their own.
        accessible: Override whether the view is exposed to assistive
            technology as a single element.
        accessibility_state: Current widget state, an
            [`AccessibilityState`][pythonnative.AccessibilityState].
        accessibility_value: Current value: a string, or an
            [`AccessibilityValue`][pythonnative.AccessibilityValue] with
            ``min`` / ``max`` / ``now`` / ``text``.
        accessibility_actions: Custom actions a screen reader may
            invoke, each an
            [`AccessibilityAction`][pythonnative.AccessibilityAction].
        on_accessibility_action: Called with the action name when a
            screen reader triggers one of ``accessibility_actions``.
        accessibility_live_region: How assistive technology announces
            changes to this view: ``"none"``, ``"polite"``, or
            ``"assertive"``.
        important_for_accessibility: Whether assistive technology sees
            this view and its subtree: ``"auto"``, ``"yes"``, ``"no"``,
            or ``"no_hide_descendants"``.
        test_id: Stable identifier for UI tests, exposed as
            ``accessibilityIdentifier`` on iOS and ``resource-id`` on
            Android.
    """

    accessibility_label: str | None
    accessibility_hint: str | None
    accessibility_role: str | None
    accessible: bool | None
    accessibility_state: AccessibilityState | None
    accessibility_value: Union[str, AccessibilityValue, None]
    accessibility_actions: Sequence[AccessibilityAction] | None
    on_accessibility_action: Callable[[str], Any] | None
    accessibility_live_region: Literal["none", "polite", "assertive"] | None
    important_for_accessibility: ImportantForAccessibility | None
    test_id: str | None


class ViewProps(AccessibilityProps, total=False):
    """Layout and gesture keywords accepted by ``View``, ``Column``, ``Row``, and ``Pressable``.

    Includes every [`AccessibilityProps`][pythonnative.AccessibilityProps] key.

    Attributes:
        gestures: Gesture descriptors from
            [`pythonnative.gestures`][pythonnative.gestures] recognized
            natively on this view.
        hit_slop: Extra touch target beyond the view's bounds: one
            number for every edge, or a dict with ``top`` / ``right`` /
            ``bottom`` / ``left``.
        on_layout: Called with a [`LayoutEvent`][pythonnative.LayoutEvent]
            after layout and whenever the view's frame changes.
    """

    gestures: List[Any] | None
    hit_slop: Union[float, Dict[str, float], None]
    on_layout: Callable[[LayoutEvent], Any] | None
