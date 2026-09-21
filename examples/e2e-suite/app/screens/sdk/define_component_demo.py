"""Demo screen for [`pn.define_component`][pythonnative.define_component].

``define_component(name, props)`` registers a dataclass schema for a
custom native component and returns a typed element factory. The demo
declares a component that has no native renderer in this app, so it
never mounts the element; it inspects the factory instead: the element
type, the validated props, the implicitly added ``style`` argument
(resolved into the wire props), rejection of unknown keywords, and the registry entry that
the contract generator would emit. The registration is removed when the
demo unmounts so the SDK demo's registry count stays stable.
"""

from __future__ import annotations

from dataclasses import dataclass

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section

_NAME = "E2EBadge"


@dataclass(frozen=True)
class _BadgeProps(pn.Props):
    """Props for the demo-only custom component."""

    label: str = ""
    count: int = 0


def _rejects_unknown_prop(factory) -> bool:
    try:
        factory(label="x", bogus=1)
    except TypeError:
        return True
    return False


@pn.component
def DefineComponentDemo() -> pn.Element:
    """Inspect the element factory returned by define_component."""
    factory = pn.use_memo(lambda: pn.define_component(_NAME, _BadgeProps), [])
    pn.use_effect(lambda: lambda: pn.sdk.unregister_component(_NAME), [])
    element = factory(label="hello", count=3, style=pn.style(padding=4))

    return demo_screen(
        "define_component",
        "Declare a custom native component and inspect its typed factory.",
        section(
            "Factory",
            result_text("Factory type", element.type),
            result_text("Label prop", element.props.get("label")),
            result_text("Count prop", element.props.get("count")),
            # The factory resolves ``style`` at the boundary and merges its
            # keys into the wire props, so the padding lands on the element.
            result_text("Style accepted", "yes" if element.props.get("padding") == 4 else "no"),
            result_text("Rejects unknown prop", "yes" if _rejects_unknown_prop(factory) else "no"),
            result_text("Registered", "yes" if _NAME in pn.sdk.list_components() else "no"),
            result_text("Props type", pn.sdk.get_props_type(_NAME).__name__),
            hint("The element is inspected, not mounted: this app ships no native renderer for it."),
        ),
    )
