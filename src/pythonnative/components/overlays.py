"""Overlay factories: ``Modal`` (native presentation) and ``Portal`` (window overlay)."""

from typing import Any, Callable, Literal, Optional

from ..element import Element
from ..style import StyleProp
from ._base import _make_element


def Modal(
    *children: Element,
    visible: bool = False,
    on_dismiss: Optional[Callable[[], Any]] = None,
    on_show: Optional[Callable[[], Any]] = None,
    on_request_close: Optional[Callable[[], Any]] = None,
    title: Optional[str] = None,
    animation_type: Literal["slide", "fade", "none"] = "slide",
    transparent: bool = False,
    presentation_style: Literal["page_sheet", "form_sheet", "full_screen", "overlay"] = "page_sheet",
    dismiss_on_backdrop: bool = True,
    status_bar_translucent: bool = False,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Overlay modal dialog backed by a real native presentation.

    The modal is shown when ``visible=True`` and hidden when ``False``.
    Drive ``visible`` from a hook so the parent component can dismiss
    the modal in response to user actions. On iOS this presents a
    ``UIViewController``; on Android it shows an ``android.app.Dialog``.

    Children are mounted as the modal's content view, not into the
    on-tree placeholder, so they appear above all other native content
    and don't influence the underlying layout.

    Args:
        *children: Modal content.
        visible: Controls whether the modal is presented.
        on_dismiss: Callback invoked once the modal has closed after
            ``visible`` became ``False``.
        on_show: Callback invoked once the modal has finished
            presenting.
        on_request_close: Callback invoked when the user asks to close
            the modal from outside your content: the Android back
            button, an iOS sheet pull-down, or a tap on an overlay's
            backdrop. Set ``visible=False`` in response; when unset the
            modal stays open.
        title: Optional title-bar text.
        animation_type: ``"slide"`` (default), ``"fade"``, or ``"none"``.
        transparent: When ``True``, the underlying view is dimmed
            instead of fully covered.
        presentation_style: iOS presentation style,
            ``"page_sheet"`` (default), ``"form_sheet"``,
            ``"full_screen"``, or ``"overlay"`` (custom dimmed
            overlay). On Android, ``"overlay"`` keeps the dialog
            non-fullscreen.
        dismiss_on_backdrop: When ``True`` (default), a tap on the
            dimmed backdrop of a ``transparent`` / ``"overlay"`` modal
            (outside its content) calls ``on_request_close``. ``False``
            ignores those taps and also locks an iOS sheet against the
            pull-down.
        status_bar_translucent: Draw the modal under a translucent
            status bar (Android only).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Modal"``.
    """
    return _make_element(
        "Modal",
        *children,
        style=style,
        key=key,
        visible=visible,
        animation_type=animation_type,
        transparent=transparent,
        presentation_style=presentation_style,
        dismiss_on_backdrop=False if dismiss_on_backdrop is False else None,
        status_bar_translucent=status_bar_translucent or None,
        on_dismiss=on_dismiss,
        on_show=on_show,
        on_request_close=on_request_close,
        title=title,
    )


def Portal(*children: Element, key: Optional[str] = None) -> Element:
    """Render ``children`` into a full-screen overlay above everything else.

    Like React DOM's ``createPortal``: the children stay part of this
    component's tree for state, context, and events, but their native
    views mount in a transparent overlay attached to the window (above
    the screen's content) instead of inside the surrounding parent.
    Use it for toasts, dropdowns, tooltips, and lightweight custom
    overlays that must escape ``overflow: "hidden"`` ancestors. For a
    system-styled dialog with its own presentation and dismissal
    gestures, use [`Modal`][pythonnative.Modal] instead.

    The overlay itself does not intercept touches; only the children
    themselves are hit-testable. Children are laid out against the
    full viewport, so position them with absolute insets:

    ```python
    pn.Portal(
        pn.View(
            pn.Text("Saved!"),
            style=pn.style(position="absolute", bottom=40, left=40, right=40),
        ),
    )
    ```

    Args:
        *children: Overlay content.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type ``"Portal"``.
    """
    return Element("Portal", {}, list(children), key=key)
