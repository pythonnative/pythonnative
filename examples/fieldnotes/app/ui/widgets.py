"""The small pieces every screen is built from."""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional

import pythonnative as pn
from pythonnative.style import AutoCapitalize, KeyboardType

from .theme import Styles

BannerKind = Literal["info", "warning", "error", "success"]

_BANNER_ICONS: dict[BannerKind, pn.IconName] = {
    "info": "info",
    "warning": "triangle-alert",
    "error": "circle-alert",
    "success": "circle-check",
}


@pn.component
def ScreenHeader(title: str, action: Optional[pn.Element] = None) -> pn.Node:
    """A tab's large title. Tabs sit under the root stack, whose bar is hidden for them."""
    styles = pn.use_styles(Styles)
    return pn.View(pn.Text(title, style=styles.title, accessibility_role="header"), action, style=styles.header)


@pn.component
def Section(title: str, *children: pn.Node) -> pn.Node:
    """A titled card."""
    styles = pn.use_styles(Styles)
    return pn.Column(
        pn.Text(title, style=styles.section_title, accessibility_role="header"),
        pn.Column(*children, style=styles.card),
        style=pn.style(gap=6),
    )


@pn.component
def Banner(message: str, kind: BannerKind = "info", action: Optional[pn.Element] = None) -> pn.Node:
    """A line of status above a screen's content, colored by what it means."""
    styles = pn.use_styles(Styles)
    colors = styles.colors
    color: pn.Color = {
        "info": colors.text_secondary,
        "warning": colors.warning,
        "error": colors.error,
        "success": colors.success,
    }[kind]
    return pn.View(
        pn.Icon(_BANNER_ICONS[kind], size=18, color=color),
        pn.Text(message, style=[styles.caption, styles.grow, {"color": color}]),
        action,
        style=[styles.banner, {"background_color": colors.surface, "border_width": 1, "border_color": color}],
    )


@pn.component
def ActionButton(
    label: str,
    icon: pn.IconName,
    on_press: Callable[[], Any],
    disabled: bool = False,
    test_id: Optional[str] = None,
) -> pn.Node:
    """A secondary action: an icon and a word, on a chip."""
    styles = pn.use_styles(Styles)
    return pn.Pressable(
        pn.Icon(icon, size=18, color=styles.colors.primary),
        pn.Text(label, style=styles.label),
        on_press=on_press,
        disabled=disabled,
        accessibility_label=label,
        accessibility_role="button",
        accessibility_state={"disabled": disabled},
        test_id=test_id,
        style=[styles.action, {"opacity": 0.45} if disabled else None],
    )


@pn.component
def PrimaryButton(label: str, on_press: Callable[[], Any], disabled: bool = False) -> pn.Node:
    """The one main action on a screen."""
    styles = pn.use_styles(Styles)
    return pn.Pressable(
        pn.Text(label, style=styles.primary_text),
        on_press=on_press,
        disabled=disabled,
        accessibility_label=label,
        accessibility_role="button",
        accessibility_state={"disabled": disabled},
        style=[styles.primary_action, {"opacity": 0.45} if disabled else None],
    )


@pn.component
def Chip(label: str, on_press: Optional[Callable[[], Any]] = None, active: bool = False) -> pn.Node:
    """A tag, pressable when it filters something."""
    styles = pn.use_styles(Styles)
    text = pn.Text(label, style=styles.chip_text_active if active else styles.chip_text)
    style = styles.chip_active if active else styles.chip
    if on_press is None:
        return pn.View(text, style=style)
    return pn.Pressable(
        text,
        on_press=on_press,
        accessibility_label=label,
        accessibility_role="button",
        accessibility_state={"selected": active},
        style=style,
    )


@pn.component
def Field(
    label: str,
    value: str,
    on_change: Callable[[str], Any],
    placeholder: str = "",
    multiline: bool = False,
    keyboard_type: Optional[KeyboardType] = None,
    auto_capitalize: Optional[AutoCapitalize] = None,
) -> pn.Node:
    """A labeled text input."""
    styles = pn.use_styles(Styles)
    return pn.Column(
        pn.Text(label, style=styles.caption),
        pn.TextInput(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            placeholder_color=styles.colors.text_secondary,
            multiline=multiline,
            keyboard_type=keyboard_type,
            auto_capitalize=auto_capitalize,
            accessibility_label=label,
            test_id=f"field-{label.casefold().replace(' ', '-')}",
            return_key_type=None if multiline else "done",
            style=[styles.field, styles.notes_field if multiline else None],
        ),
        style=pn.style(gap=4),
    )


@pn.component
def EmptyState(icon: pn.IconName, title: str, message: str, action: Optional[pn.Element] = None) -> pn.Node:
    """What a list shows when there's nothing in it, and what to do about that."""
    styles = pn.use_styles(Styles)
    return pn.Column(
        pn.Icon(icon, size=40, color=styles.colors.text_secondary),
        pn.Text(title, style=styles.heading),
        pn.Text(message, style=styles.center_text),
        action,
        style=styles.empty,
    )
