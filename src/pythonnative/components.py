"""Built-in element factories for declarative UI composition.

Each function in this module returns an [`Element`][pythonnative.Element]
describing a native UI widget. Element factories are pure data: no
native views are created until the reconciler mounts the element tree.

All visual and layout properties are passed via the `style` parameter,
which accepts a dict or a list of dicts (later entries override
earlier ones; see [`resolve_style`][pythonnative.style.resolve_style]).

Layout properties supported by every component:

- `width`, `height`, `flex`, `flex_grow`, `flex_shrink`, `margin`,
  `min_width`, `max_width`, `min_height`, `max_height`, `align_self`.

Flex container properties (`View` / `Column` / `Row`):

- `flex_direction`, `justify_content`, `align_items`, `overflow`,
  `spacing`, `padding`.

[`View`][pythonnative.View] is the universal flex container (like React
Native's `View`). It defaults to `flex_direction: "column"`.
[`Column`][pythonnative.Column] and [`Row`][pythonnative.Row] are
convenience wrappers that fix the direction.

Example:
    ```python
    import pythonnative as pn

    pn.Column(
        pn.Text("Hello", style={"font_size": 18}),
        pn.Button("Tap", on_click=lambda: print("tapped")),
        style={"spacing": 12, "padding": 16},
    )
    ```
"""

from typing import Any, Callable, Dict, List, Literal, Optional

from .element import Element
from .style import (
    AutoCapitalize,
    Color,
    KeyboardType,
    ReturnKeyType,
    ScaleType,
    StyleProp,
    resolve_style,
)

# ======================================================================
# Leaf components
# ======================================================================


def _accessibility_props(
    accessibility_label: Optional[str],
    accessibility_hint: Optional[str],
    accessibility_role: Optional[str],
    accessible: Optional[bool],
) -> Dict[str, Any]:
    """Collect the four accessibility prop keys into a dict.

    Internal helper kept here so every component factory can expose
    the same four kwargs without repeating the ``if x is not None``
    plumbing. Returns an empty dict when no accessibility values are
    supplied so we don't bloat element props.
    """
    out: Dict[str, Any] = {}
    if accessibility_label is not None:
        out["accessibility_label"] = accessibility_label
    if accessibility_hint is not None:
        out["accessibility_hint"] = accessibility_hint
    if accessibility_role is not None:
        out["accessibility_role"] = accessibility_role
    if accessible is not None:
        out["accessible"] = accessible
    return out


def Text(
    text: str = "",
    *,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a string of text.

    Style properties: `font_size`, `color`, `bold`, `font_weight`,
    `font_family`, `italic`, `text_align`, `background_color`,
    `max_lines`, `letter_spacing`, `line_height`, `text_decoration`
    (`"underline"` / `"line_through"`), `border_radius`,
    `border_width`, `border_color`, `shadow_*`, `opacity`,
    `transform`, plus the common layout props.

    Args:
        text: Text content to display.
        style: Style dict (or list of dicts) controlling appearance and
            layout.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict; the reconciler populates
            ``ref["current"]`` with the underlying native view.
        key: Stable identity for keyed reconciliation in lists.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Text"`.
    """
    props: Dict[str, Any] = {"text": text}
    props.update(resolve_style(style))
    props.update(_accessibility_props(accessibility_label, accessibility_hint, accessibility_role, accessible))
    if ref is not None:
        props["ref"] = ref
    return Element("Text", props, [], key=key)


def Button(
    title: str = "",
    *,
    on_click: Optional[Callable[[], None]] = None,
    enabled: bool = True,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a tappable button.

    Style properties: `color`, `background_color`, `font_size`,
    `border_radius`, `border_width`, `border_color`, `shadow_*`,
    `opacity`, `transform`, plus the common layout props.

    Args:
        title: Button label.
        on_click: Callback invoked when the user taps the button.
        enabled: When `False`, the button is disabled and cannot be
            tapped.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict; the reconciler populates
            ``ref["current"]`` with the underlying native view.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Button"`.
    """
    props: Dict[str, Any] = {"title": title}
    if on_click is not None:
        props["on_click"] = on_click
    if not enabled:
        props["enabled"] = False
    props.update(resolve_style(style))
    # Buttons get accessibility_role="button" by default.
    if accessibility_label is not None:
        props["accessibility_label"] = accessibility_label
    if accessibility_hint is not None:
        props["accessibility_hint"] = accessibility_hint
    if accessible is not None:
        props["accessible"] = accessible
    props.setdefault("accessibility_role", "button")
    if ref is not None:
        props["ref"] = ref
    return Element("Button", props, [], key=key)


def TextInput(
    *,
    value: str = "",
    placeholder: str = "",
    on_change: Optional[Callable[[str], None]] = None,
    on_submit: Optional[Callable[[str], None]] = None,
    secure: bool = False,
    multiline: bool = False,
    keyboard_type: Optional[KeyboardType] = None,
    auto_capitalize: Optional[AutoCapitalize] = None,
    auto_correct: Optional[bool] = None,
    auto_focus: bool = False,
    return_key_type: Optional[ReturnKeyType] = None,
    max_length: Optional[int] = None,
    placeholder_color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display a text entry field (single-line by default, or `multiline`).

    Style properties: `font_size`, `color`, `background_color`,
    `border_*`, plus the common layout props.

    Args:
        value: Current text content (controlled-input pattern).
        placeholder: Hint shown when `value` is empty.
        on_change: Callback invoked with the new string each keystroke.
        on_submit: Callback invoked when the user submits (Return /
            Done / etc.). Receives the final text.
        secure: When `True`, characters are masked (use for passwords).
        multiline: When `True`, allows multiple lines of input.
        keyboard_type: One of ``"default"``, ``"email_address"``,
            ``"number_pad"``, ``"decimal_pad"``, ``"phone_pad"``,
            ``"url"``.
        auto_capitalize: One of ``"none"``, ``"sentences"``,
            ``"words"``, ``"characters"``.
        auto_correct: Enable/disable autocorrection.
        auto_focus: Request focus on mount.
        return_key_type: One of ``"default"``, ``"done"``, ``"go"``,
            ``"next"``, ``"send"``, ``"search"``.
        max_length: Maximum number of characters allowed.
        placeholder_color: Color to use for the placeholder string.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"TextInput"`.
    """
    props: Dict[str, Any] = {"value": value}
    if placeholder:
        props["placeholder"] = placeholder
    if on_change is not None:
        props["on_change"] = on_change
    if on_submit is not None:
        props["on_submit"] = on_submit
    if secure:
        props["secure"] = True
    if multiline:
        props["multiline"] = True
    if keyboard_type is not None:
        props["keyboard_type"] = keyboard_type
    if auto_capitalize is not None:
        props["auto_capitalize"] = auto_capitalize
    if auto_correct is not None:
        props["auto_correct"] = auto_correct
    if auto_focus:
        props["auto_focus"] = True
    if return_key_type is not None:
        props["return_key_type"] = return_key_type
    if max_length is not None:
        props["max_length"] = max_length
    if placeholder_color is not None:
        props["placeholder_color"] = placeholder_color
    props.update(resolve_style(style))
    props.update(_accessibility_props(accessibility_label, accessibility_hint, None, accessible))
    if ref is not None:
        props["ref"] = ref
    return Element("TextInput", props, [], key=key)


def Image(
    source: str = "",
    *,
    scale_type: Optional[ScaleType] = None,
    tint_color: Optional[Color] = None,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Display an image from a resource path or URL.

    Style properties: `background_color`, `border_*`, `opacity`,
    `transform`, plus the common layout props.

    Network images (``http://`` / ``https://``) are loaded
    asynchronously off the main thread on both iOS (via NSURLSession)
    and Android (via a worker thread + `BitmapFactory`).

    Args:
        source: Image resource name or URL.
        scale_type: Fit mode: `"cover"`, `"contain"`, `"stretch"`,
            `"center"`.
        tint_color: Color overlay applied to template images
            (monochrome icons).
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Image"`.
    """
    props: Dict[str, Any] = {}
    if source:
        props["source"] = source
    if scale_type is not None:
        props["scale_type"] = scale_type
    if tint_color is not None:
        props["tint_color"] = tint_color
    props.update(resolve_style(style))
    props.update(_accessibility_props(accessibility_label, None, "image", accessible))
    if ref is not None:
        props["ref"] = ref
    return Element("Image", props, [], key=key)


def Switch(
    *,
    value: bool = False,
    on_change: Optional[Callable[[bool], None]] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Display a toggle switch.

    Args:
        value: Current on/off state.
        on_change: Callback invoked with the new boolean state.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Switch"`.
    """
    props: Dict[str, Any] = {"value": value}
    if on_change is not None:
        props["on_change"] = on_change
    props.update(resolve_style(style))
    return Element("Switch", props, [], key=key)


def ProgressBar(
    *,
    value: float = 0.0,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Show determinate progress as a value between 0.0 and 1.0.

    For indeterminate progress, use
    [`ActivityIndicator`][pythonnative.ActivityIndicator] instead.

    Args:
        value: Fraction complete (clamped to `[0.0, 1.0]` by the
            platform handler).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"ProgressBar"`.
    """
    props: Dict[str, Any] = {"value": value}
    props.update(resolve_style(style))
    return Element("ProgressBar", props, [], key=key)


def ActivityIndicator(
    *,
    animating: bool = True,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Show an indeterminate loading spinner.

    Args:
        animating: When `False`, the spinner is hidden.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        `"ActivityIndicator"`.
    """
    props: Dict[str, Any] = {"animating": animating}
    props.update(resolve_style(style))
    return Element("ActivityIndicator", props, [], key=key)


def WebView(
    *,
    url: str = "",
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Embed web content from a URL.

    Args:
        url: HTTP(S) URL to load.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"WebView"`.
    """
    props: Dict[str, Any] = {}
    if url:
        props["url"] = url
    props.update(resolve_style(style))
    return Element("WebView", props, [], key=key)


def Spacer(
    *,
    size: Optional[float] = None,
    flex: Optional[float] = None,
    key: Optional[str] = None,
) -> Element:
    """Insert empty space inside a flex container.

    Pass `size` for a fixed gap, or `flex` to expand and absorb
    remaining space.

    Args:
        size: Fixed gap in dp/pt along the parent's main axis.
        flex: Flex-grow weight; useful for pushing siblings to the
            opposite end of a [`Row`][pythonnative.Row] or
            [`Column`][pythonnative.Column].
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Spacer"`.
    """
    props: Dict[str, Any] = {}
    if size is not None:
        # The layout engine sees ``width`` / ``height`` only, so a fixed
        # ``size`` is mirrored on both axes. Whichever axis the parent
        # container's ``flex_direction`` chooses as main becomes the
        # actual gap; the cross axis is constrained by the parent's
        # ``align_items`` (typically ``stretch``) anyway.
        props["size"] = size
        props["width"] = size
        props["height"] = size
    if flex is not None:
        props["flex"] = flex
    return Element("Spacer", props, [], key=key)


def Slider(
    *,
    value: float = 0.0,
    min_value: float = 0.0,
    max_value: float = 1.0,
    on_change: Optional[Callable[[float], None]] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Continuous-value slider between `min_value` and `max_value`.

    Args:
        value: Current slider value.
        min_value: Lower bound.
        max_value: Upper bound.
        on_change: Callback invoked with the new value as the user
            drags.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Slider"`.
    """
    props: Dict[str, Any] = {
        "value": value,
        "min_value": min_value,
        "max_value": max_value,
    }
    if on_change is not None:
        props["on_change"] = on_change
    props.update(resolve_style(style))
    return Element("Slider", props, [], key=key)


# ======================================================================
# Container components
# ======================================================================


def View(
    *children: Element,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessibility_role: Optional[str] = None,
    accessible: Optional[bool] = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Universal flex container (like React Native's `View`).

    Defaults to `flex_direction: "column"`. Override via `style`:

    ```python
    pn.View(child_a, child_b, style={"flex_direction": "row"})
    ```

    Flex container properties (inside `style`):

    - `flex_direction`: `"column"` (default), `"row"`,
      `"column_reverse"`, `"row_reverse"`.
    - `justify_content`: main-axis distribution. Accepts `"flex_start"`
      (default), `"center"`, `"flex_end"`, `"space_between"`,
      `"space_around"`, `"space_evenly"`.
    - `align_items`: cross-axis alignment. Accepts `"stretch"` (default),
      `"flex_start"`, `"center"`, `"flex_end"`.
    - `overflow`: `"visible"` (default) or `"hidden"`.
    - `spacing`, `padding`, `background_color`, `border_radius`,
      `border_width`, `border_color`, `shadow_color`, `shadow_offset`,
      `shadow_opacity`, `shadow_radius`, `elevation`, `opacity`,
      `transform`.

    Args:
        *children: Child elements rendered inside the container.
        style: Style dict (or list of dicts).
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessibility_role: Semantic role for assistive tech.
        accessible: Override whether the element is exposed to AT.
        ref: Optional ``use_ref()`` dict; the reconciler populates
            ``ref["current"]`` with the underlying native view.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"View"`.
    """
    props: Dict[str, Any] = {"flex_direction": "column"}
    props.update(resolve_style(style))
    props.update(_accessibility_props(accessibility_label, accessibility_hint, accessibility_role, accessible))
    if ref is not None:
        props["ref"] = ref
    return Element("View", props, list(children), key=key)


def Column(
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Arrange children vertically.

    Convenience wrapper around [`View`][pythonnative.View] with
    `flex_direction` fixed to `"column"`. Use `View` directly if you
    need to switch between row and column at runtime.

    Style properties: `spacing`, `padding`, `align_items`,
    `justify_content`, `background_color`, `overflow`, plus the common
    layout props.

    `align_items` controls cross-axis (horizontal) alignment:
    `"stretch"` (default), `"flex_start"` / `"leading"`, `"center"`, or
    `"flex_end"` / `"trailing"`.

    `justify_content` controls main-axis (vertical) distribution:
    `"flex_start"` (default), `"center"`, `"flex_end"`,
    `"space_between"`, `"space_around"`, `"space_evenly"`.

    Args:
        *children: Child elements stacked top to bottom.
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict for native-view access.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Column"`.
    """
    props: Dict[str, Any] = {"flex_direction": "column"}
    props.update(resolve_style(style))
    props["flex_direction"] = "column"
    if ref is not None:
        props["ref"] = ref
    return Element("Column", props, list(children), key=key)


def Row(
    *children: Element,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Arrange children horizontally.

    Convenience wrapper around [`View`][pythonnative.View] with
    `flex_direction` fixed to `"row"`. Use `View` directly if you need
    to switch between row and column at runtime.

    Style properties: `spacing`, `padding`, `align_items`,
    `justify_content`, `background_color`, `overflow`, plus the common
    layout props.

    `align_items` controls cross-axis (vertical) alignment:
    `"stretch"` (default), `"flex_start"` / `"top"`, `"center"`, or
    `"flex_end"` / `"bottom"`.

    `justify_content` controls main-axis (horizontal) distribution:
    `"flex_start"` (default), `"center"`, `"flex_end"`,
    `"space_between"`, `"space_around"`, `"space_evenly"`.

    Args:
        *children: Child elements arranged left to right.
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict for native-view access.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Row"`.
    """
    props: Dict[str, Any] = {"flex_direction": "row"}
    props.update(resolve_style(style))
    props["flex_direction"] = "row"
    if ref is not None:
        props["ref"] = ref
    return Element("Row", props, list(children), key=key)


def ScrollView(
    child: Optional[Element] = None,
    *,
    refresh_control: Optional[Dict[str, Any]] = None,
    style: StyleProp = None,
    ref: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap a single child in a scrollable container.

    Args:
        child: The single child to scroll. Wrap multiple elements in a
            [`Column`][pythonnative.Column] or
            [`Row`][pythonnative.Row] first.
        refresh_control: Optional pull-to-refresh spec, typically
            constructed via
            [`RefreshControl`][pythonnative.RefreshControl]. The dict
            must have ``refreshing`` (bool) and ``on_refresh`` (callable).
        style: Style dict (or list of dicts).
        ref: Optional ``use_ref()`` dict.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"ScrollView"`.
    """
    children = [child] if child is not None else []
    props: Dict[str, Any] = {}
    if refresh_control is not None:
        props["refresh_control"] = refresh_control
    props.update(resolve_style(style))
    if ref is not None:
        props["ref"] = ref
    return Element("ScrollView", props, children, key=key)


def SafeAreaView(
    *children: Element,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Container that respects safe-area insets (notch, status bar, home indicator).

    Args:
        *children: Child elements that should avoid system UI overlays.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"SafeAreaView"`.
    """
    props: Dict[str, Any] = {}
    props.update(resolve_style(style))
    return Element("SafeAreaView", props, list(children), key=key)


def Modal(
    *children: Element,
    visible: bool = False,
    on_dismiss: Optional[Callable[[], None]] = None,
    title: Optional[str] = None,
    animation_type: Literal["slide", "fade", "none"] = "slide",
    transparent: bool = False,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Overlay modal dialog backed by a real native presentation.

    The modal is shown when `visible=True` and hidden when `False`.
    Drive `visible` from a hook so the parent component can dismiss
    the modal in response to user actions. On iOS this presents a
    `UIViewController`; on Android it shows an `android.app.Dialog`.

    Children are mounted as the modal's content view, not into the
    on-tree placeholder, so they appear above all other native
    content and don't influence the underlying layout.

    Args:
        *children: Modal content.
        visible: Controls whether the modal is presented.
        on_dismiss: Callback invoked when the user dismisses the modal
            via system gesture (e.g., backdrop tap or back button).
        title: Optional title bar text.
        animation_type: ``"slide"`` (default), ``"fade"``, or ``"none"``.
        transparent: When ``True``, the underlying view is dimmed
            instead of fully covered.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Modal"`.
    """
    props: Dict[str, Any] = {
        "visible": visible,
        "animation_type": animation_type,
        "transparent": transparent,
    }
    if on_dismiss is not None:
        props["on_dismiss"] = on_dismiss
    if title is not None:
        props["title"] = title
    props.update(resolve_style(style))
    return Element("Modal", props, list(children), key=key)


def Pressable(
    child: Optional[Element] = None,
    *,
    on_press: Optional[Callable[[], None]] = None,
    on_long_press: Optional[Callable[[], None]] = None,
    pressed_opacity: float = 0.6,
    style: StyleProp = None,
    accessibility_label: Optional[str] = None,
    accessibility_hint: Optional[str] = None,
    accessible: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap any child element with tap and long-press handlers.

    Useful for making non-button elements (text, images, custom views)
    respond to user taps. The wrapper view fades to ``pressed_opacity``
    on touch-down and back to full opacity on touch-up, providing
    subtle visual feedback (matches React Native's `Pressable` default).

    Args:
        child: The single element to make pressable.
        on_press: Callback invoked on a normal tap.
        on_long_press: Callback invoked on a sustained press.
        pressed_opacity: Opacity (0-1) applied to the wrapper while
            the user's finger is down. Set to ``1.0`` for no visual
            feedback.
        style: Style dict applied to the wrapper.
        accessibility_label: Spoken description for screen readers.
        accessibility_hint: Spoken extra detail (iOS only).
        accessible: Override whether the element is exposed to AT.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Pressable"`.
    """
    props: Dict[str, Any] = {}
    if on_press is not None:
        props["on_press"] = on_press
    if on_long_press is not None:
        props["on_long_press"] = on_long_press
    if pressed_opacity != 0.6:
        props["pressed_opacity"] = pressed_opacity
    else:
        props.setdefault("pressed_opacity", 0.6)
    props.update(resolve_style(style))
    props.update(_accessibility_props(accessibility_label, accessibility_hint, "button", accessible))
    children = [child] if child is not None else []
    return Element("Pressable", props, children, key=key)


def ErrorBoundary(
    child: Optional[Element] = None,
    *,
    fallback: Optional[Any] = None,
    key: Optional[str] = None,
) -> Element:
    """Catch render errors in `child` and display `fallback` instead.

    `fallback` may be an [`Element`][pythonnative.Element] or a callable
    that receives the exception and returns an `Element`. Useful for
    isolating risky subtrees so a single failure doesn't crash the page.

    Args:
        child: Subtree to wrap.
        fallback: Element to render when `child` raises during render,
            or a callable `fallback(err) -> Element`.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"__ErrorBoundary__"`.

    Example:
        ```python
        import pythonnative as pn

        pn.ErrorBoundary(
            MyRiskyComponent(),
            fallback=lambda err: pn.Text(f"Error: {err}"),
        )
        ```
    """
    props: Dict[str, Any] = {}
    if fallback is not None:
        props["__fallback__"] = fallback
    children = [child] if child is not None else []
    return Element("__ErrorBoundary__", props, children, key=key)


def FlatList(
    *,
    data: Optional[List[Any]] = None,
    render_item: Optional[Callable[[Any, int], Element]] = None,
    key_extractor: Optional[Callable[[Any, int], str]] = None,
    item_height: Optional[float] = None,
    separator_height: float = 0,
    refresh_control: Optional[Dict[str, Any]] = None,
    on_item_press: Optional[Callable[[int], None]] = None,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized scrollable list that renders items from `data` lazily.

    Backed by `UITableView` on iOS and `RecyclerView` on Android via the
    `VirtualList` element. Each visible row is mounted on demand by a
    nested [`Reconciler`][pythonnative.reconciler.Reconciler] when
    ``item_height`` is specified.

    When ``item_height`` is omitted the implementation falls back to an
    eager (non-virtualized) ``ScrollView`` of every row — keep the data
    set small in that mode (the fallback is convenient for short
    lists where virtualization overhead would dominate).

    Args:
        data: Iterable of arbitrary item values.
        render_item: Function called per item, returning an
            [`Element`][pythonnative.Element]. Defaults to wrapping
            each item in a [`Text`][pythonnative.Text].
        key_extractor: Function returning a stable key per item.
        item_height: Fixed row height in layout units. Required to
            enable native virtualization. When omitted, the list
            falls back to an eager scroll of every row (not
            recommended for long lists).
        separator_height: Vertical gap between items, in layout units.
            Combined with ``item_height`` for the virtualized case.
        refresh_control: Optional ``{"refreshing": bool, "on_refresh":
            callable}`` for pull-to-refresh; see
            [`RefreshControl`][pythonnative.RefreshControl].
        on_item_press: Callback invoked with the row index when the
            user taps a row (virtualized backend only).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation of the list itself.

    Returns:
        An [`Element`][pythonnative.Element] of type `"VirtualList"`
        (virtualized) or `"ScrollView"` (eager fallback).

    Example:
        ```python
        import pythonnative as pn

        items = [{"id": i, "name": f"Item {i}"} for i in range(10000)]

        pn.FlatList(
            data=items,
            item_height=44,
            render_item=lambda item, _: pn.Text(item["name"]),
            key_extractor=lambda item, _: str(item["id"]),
        )
        ```
    """
    items_list = list(data or [])

    if item_height is None:
        # Eager fallback for short lists.
        items_eager: List[Element] = []
        for i, item in enumerate(items_list):
            el = render_item(item, i) if render_item else Text(str(item))
            if key_extractor is not None:
                el = Element(el.type, el.props, el.children, key=key_extractor(item, i))
            items_eager.append(el)
        inner = Column(*items_eager, style={"spacing": separator_height} if separator_height else None)
        sv_props: Dict[str, Any] = {}
        if refresh_control is not None:
            sv_props["refresh_control"] = refresh_control
        sv_props.update(resolve_style(style))
        return Element("ScrollView", sv_props, [inner], key=key)

    # Virtualized path: render_item is invoked lazily by the native
    # cell mount callback when each row scrolls into view.
    row_h = float(item_height) + float(separator_height)

    def _mount_row(
        index: int,
        content_view: Any,
        cell_width: float = 0.0,
        cell_height: float = 0.0,
    ) -> None:
        # Imported lazily so the components module stays importable in
        # off-device test environments.
        from .native_views import get_registry
        from .reconciler import Reconciler

        try:
            item = items_list[index]
        except IndexError:
            return

        element = render_item(item, index) if render_item else Text(str(item))
        backend = get_registry()
        reconciler = Reconciler(backend)
        native_root = reconciler.mount(element)

        layout_w = float(cell_width) if cell_width and cell_width > 0 else 0.0
        layout_h = float(cell_height) if cell_height and cell_height > 0 else float(item_height)
        if layout_w <= 0:
            try:
                bounds = content_view.bounds
                layout_w = float(bounds.size.width)
            except Exception:
                layout_w = 0.0
        if layout_w > 0 and layout_h > 0:
            backend.set_frame(native_root, "View", 0.0, 0.0, layout_w, layout_h)
            reconciler.set_viewport_size(layout_w, layout_h)

        backend.add_child(content_view, native_root, "View")

    list_props: Dict[str, Any] = {
        "count": len(items_list),
        "row_height": row_h,
        "mount_row": _mount_row,
    }
    if on_item_press is not None:
        list_props["on_row_press"] = on_item_press
    if refresh_control is not None:
        list_props["refresh_control"] = refresh_control
    list_props.update(resolve_style(style))
    return Element("VirtualList", list_props, [], key=key)


def SectionList(
    *,
    sections: Optional[List[Dict[str, Any]]] = None,
    render_item: Optional[Callable[[Any, int, int], Element]] = None,
    render_section_header: Optional[Callable[[Dict[str, Any], int], Element]] = None,
    item_height: Optional[float] = None,
    section_header_height: float = 32.0,
    separator_height: float = 0,
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Virtualized list that supports section headers.

    Internally flattens ``sections`` into a single virtualized list
    where each row is either a section header or a section item. The
    row mounter dispatches to ``render_section_header`` or
    ``render_item`` depending on the row's type.

    Args:
        sections: Each section is ``{"title": ..., "data": [...]}``.
        render_item: ``render_item(item, item_index, section_index) -> Element``.
        render_section_header: ``render_section_header(section, section_index) -> Element``.
        item_height: Fixed row height for items, in layout units.
        section_header_height: Fixed header height in layout units.
        separator_height: Gap appended below each item, in layout units.
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"VirtualList"`
        (virtualized). When ``item_height`` is omitted the layout
        falls back to an eager column.
    """
    sections_list = list(sections or [])

    flat: List[Dict[str, Any]] = []
    for s_idx, section in enumerate(sections_list):
        flat.append({"_kind": "header", "section": section, "section_index": s_idx})
        for i_idx, item in enumerate(section.get("data", []) or []):
            flat.append({"_kind": "item", "item": item, "item_index": i_idx, "section_index": s_idx})

    if item_height is None:
        # Eager fallback.
        children: List[Element] = []
        for entry in flat:
            if entry["_kind"] == "header":
                if render_section_header is not None:
                    children.append(render_section_header(entry["section"], entry["section_index"]))
                else:
                    children.append(Text(str(entry["section"].get("title", ""))))
            else:
                if render_item is not None:
                    children.append(render_item(entry["item"], entry["item_index"], entry["section_index"]))
                else:
                    children.append(Text(str(entry["item"])))
        inner = Column(*children, style={"spacing": separator_height} if separator_height else None)
        sv_props: Dict[str, Any] = {}
        sv_props.update(resolve_style(style))
        return Element("ScrollView", sv_props, [inner], key=key)

    # Virtualized: mixed row heights aren't supported in v1, so we
    # use the larger of section_header_height and item_height + sep.
    row_h = max(float(section_header_height), float(item_height) + float(separator_height))

    def _mount_row(index: int, content_view: Any) -> None:
        from .native_views import get_registry
        from .reconciler import Reconciler

        try:
            entry = flat[index]
        except IndexError:
            return
        if entry["_kind"] == "header":
            if render_section_header is not None:
                element = render_section_header(entry["section"], entry["section_index"])
            else:
                element = Text(str(entry["section"].get("title", "")))
        else:
            if render_item is not None:
                element = render_item(entry["item"], entry["item_index"], entry["section_index"])
            else:
                element = Text(str(entry["item"]))

        backend = get_registry()
        reconciler = Reconciler(backend)
        native_root = reconciler.mount(element)
        try:
            backend.add_child(content_view, native_root, "View")
        except Exception:
            pass

    list_props: Dict[str, Any] = {
        "count": len(flat),
        "row_height": row_h,
        "mount_row": _mount_row,
    }
    list_props.update(resolve_style(style))
    return Element("VirtualList", list_props, [], key=key)


# ======================================================================
# Status bar / keyboard / refresh / alert / picker
# ======================================================================


def StatusBar(
    *,
    style: Optional[Literal["light", "dark", "default"]] = None,
    background_color: Optional[Color] = None,
    hidden: Optional[bool] = None,
    key: Optional[str] = None,
) -> Element:
    """Configure the device's status bar appearance.

    StatusBar is a side-effect element: it doesn't render any visible
    content but applies its props to the host platform's status bar.
    Mount one near the top of your tree.

    Args:
        style: ``"light"`` (light icons over dark backgrounds),
            ``"dark"`` (dark icons over light backgrounds), or
            ``"default"`` (system default).
        background_color: Color of the status-bar background (Android
            only — iOS draws the bar transparent over your content).
        hidden: When ``True``, the status bar is hidden.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"StatusBar"`.
    """
    props: Dict[str, Any] = {}
    if style is not None:
        props["style"] = style
    if background_color is not None:
        props["background_color"] = background_color
    if hidden is not None:
        props["hidden"] = hidden
    return Element("StatusBar", props, [], key=key)


def KeyboardAvoidingView(
    *children: Element,
    behavior: Literal["padding", "position"] = "padding",
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """Wrap content that should shift up when the keyboard is shown.

    Subscribes to the platform-reported keyboard height (via
    [`use_keyboard_height`][pythonnative.use_keyboard_height]
    internally) and applies it as bottom padding so the focused
    text input stays visible.

    Args:
        *children: Children rendered inside the avoiding container.
        behavior: ``"padding"`` (adds bottom padding) or ``"position"``
            (translates the container upward).
        style: Style dict (or list of dicts).
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type
        `"KeyboardAvoidingView"`.
    """
    props: Dict[str, Any] = {"behavior": behavior}
    props.update(resolve_style(style))
    return Element("KeyboardAvoidingView", props, list(children), key=key)


def RefreshControl(
    *,
    refreshing: bool = False,
    on_refresh: Optional[Callable[[], None]] = None,
    tint_color: Optional[Color] = None,
) -> Dict[str, Any]:
    """Pull-to-refresh spec for [`ScrollView`][pythonnative.ScrollView] / [`FlatList`][pythonnative.FlatList].

    Returns a plain dict that should be passed as the
    ``refresh_control=`` prop. Modeled as a dict (not an Element) so
    the host scroll container can hold one without it appearing as a
    child node.

    Args:
        refreshing: Drive the spinner's visibility from a use_state
            value.
        on_refresh: Callback invoked when the user pulls down past
            the threshold. Set ``refreshing`` to True for the
            duration of the work, then back to False on completion.
        tint_color: Color of the spinner.

    Returns:
        Dict suitable for the ``refresh_control`` prop on a scroll
        container.

    Example:
        ```python
        import pythonnative as pn

        @pn.component
        def MyList():
            refreshing, set_refreshing = pn.use_state(False)

            def reload():
                set_refreshing(True)
                # ... fetch data ...
                set_refreshing(False)

            return pn.ScrollView(
                pn.Text("Pull me!"),
                refresh_control=pn.RefreshControl(
                    refreshing=refreshing, on_refresh=reload
                ),
            )
        ```
    """
    spec: Dict[str, Any] = {"refreshing": bool(refreshing)}
    if on_refresh is not None:
        spec["on_refresh"] = on_refresh
    if tint_color is not None:
        spec["tint_color"] = tint_color
    return spec


def Picker(
    *,
    value: Any = None,
    items: Optional[List[Dict[str, Any]]] = None,
    on_change: Optional[Callable[[Any], None]] = None,
    placeholder: str = "Select…",
    style: StyleProp = None,
    key: Optional[str] = None,
) -> Element:
    """A select / dropdown widget.

    Implemented as a plain
    [`Pressable`][pythonnative.Pressable] that, on tap, presents an
    [`Alert`][pythonnative.Alert]-style action sheet listing the
    options. Selecting an option fires ``on_change(value)``.

    Args:
        value: Currently selected value (matched against
            ``items[i]["value"]``).
        items: Each item is ``{"value": ..., "label": ...}``.
        on_change: Callback invoked with the selected value.
        placeholder: Label shown when nothing is selected.
        style: Style dict applied to the trigger pressable.
        key: Stable identity for keyed reconciliation.

    Returns:
        An [`Element`][pythonnative.Element] of type `"Pressable"`.
    """
    items_list = list(items or [])
    selected_label = placeholder
    for it in items_list:
        if it.get("value") == value:
            selected_label = str(it.get("label", value))
            break

    def _open() -> None:
        try:
            from .alerts import Alert
        except Exception:
            return

        def _make_btn(item: Dict[str, Any]) -> Dict[str, Any]:
            def _press() -> None:
                if on_change is not None:
                    try:
                        on_change(item.get("value"))
                    except Exception:
                        pass

            return {"label": str(item.get("label", item.get("value"))), "on_press": _press}

        buttons = [_make_btn(it) for it in items_list]
        buttons.append({"label": "Cancel", "style": "cancel"})
        Alert.show(title=placeholder, buttons=buttons, style="action_sheet")

    label_text = Text(selected_label)
    return Pressable(label_text, on_press=_open, style=style, key=key)
