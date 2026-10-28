"""Headless backend: the shipping renderer core plus an inspectable tree.

[`FakeBackend`][pythonnative.testing.FakeBackend] is the bridge backend
committing to the host build of the renderer core (RFC 0007), so every
test validates, lays out, animates, and recognizes gestures with the code
the apps link. Beside that it keeps the logical tree of
[`FakeView`][pythonnative.testing.FakeView] objects the reconciler built,
with the frames the core computed, so tests can assert on structure,
props, and frames without a device. The transport's ``views`` show what
the UI thread mounted, flattened layout-only views excluded.

The fake raises on malformed transactions, including unknown tags, double
destroys, and insertion into a destroyed parent, and the core rejects
invalid props the way it does on a device.

Recorded op shapes (in ``FakeBackend.ops``):

- ``("create", type_name, view.id)``
- ``("update", type_name, view.id, tuple(sorted(changed_keys)))``
- ``("insert_child", parent.id, child.id, index)``
- ``("destroy", view.id)``
- ``("set_frame", view.id, x, y, w, h)`` (frames the core reported)

Imperative commands (``FakeBackend.command``) are recorded in
``FakeBackend.commands`` and answered for the view types that have typed
handles: ``TextInput`` (``get_value``, ``focus``, ``blur``, ``clear``,
``select_all``, ``set_selection``), ``ScrollView`` (``scroll_to_offset``,
``scroll_to_end``, ``get_scroll_offset``), ``WebView`` (``can_go_back``,
``can_go_forward``, ``get_url``, ``get_title``, ``load_url``, and the
navigation verbs), and ``VirtualList`` (``scroll_to_index``,
``scroll_to_end``).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from ..bridge.fake import FakeTransport
from ..mutations import CreateOp, DestroyOp, InsertOp, Mutation, UpdateOp
from ..native_views.bridge_backend import BridgeBackend

__all__ = ["DEFAULT_INTRINSIC", "IMPLICIT_ROLES", "FakeBackend", "FakeView"]

# Surface 1 is the device's; each headless backend gets its own.
_surfaces = itertools.count(2)

DEFAULT_INTRINSIC: Dict[str, Tuple[float, float]] = {
    "Text": (60.0, 16.0),
    "Button": (80.0, 32.0),
    "Image": (40.0, 40.0),
    "TextInput": (120.0, 32.0),
    "TabBar": (320.0, 49.0),
}
"""Sizes the fake platform measures for content-sized leaves.

``Image`` reports its size as if it had loaded, the way a platform's image
loader reports intrinsic sizes to the core."""

IMPLICIT_ROLES: Dict[str, str] = {
    "Button": "button",
    "Pressable": "button",
    "Picker": "button",
    "DatePicker": "button",
    "Switch": "switch",
    "Checkbox": "checkbox",
    "TextInput": "textbox",
    "Image": "image",
    "ImageBackground": "image",
    "Slider": "adjustable",
    "ProgressBar": "progressbar",
}
"""Accessibility role each native type implies when no ``accessibility_role`` prop is set.

``get_by_role`` consults this table after the explicit prop, so
``pn.Button("Save")`` matches ``get_by_role("button")`` and
``pn.Switch()`` matches ``get_by_role("switch")``. ``Text`` has no
implicit role; ``pn.Text("Title", accessibility_role="header")`` matches
``get_by_role("header")`` through the prop.
"""


class FakeView:
    """Simulated native view: type, props, children, and last frame.

    Attributes:
        tag: The reconciler-assigned tag (use with ``fire`` / events).
        type_name: Native type, e.g. ``"Text"``.
        props: Native-safe props (event callbacks are stripped; they
            live in the event registry keyed by ``tag``).
        children: Child views in order.
        frame: ``(x, y, width, height)`` from the last layout pass.
    """

    _next_id = 0

    def __init__(self, tag: int, type_name: str, props: Dict[str, Any]) -> None:
        FakeView._next_id += 1
        self.id = FakeView._next_id
        self.tag = tag
        self.type_name = type_name
        self.props: Dict[str, Any] = dict(props)
        self.children: List[FakeView] = []
        self.parent: Optional[FakeView] = None
        self.frame: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.destroyed = False

    def __repr__(self) -> str:
        suffix = ""
        if self.text:
            suffix = f" {self.text!r}"
        elif self.value:
            suffix = f" value={self.value!r}"
        elif self.placeholder:
            suffix = f" placeholder={self.placeholder!r}"
        return f"<{self.type_name} tag={self.tag}{suffix}>"

    # -- content --------------------------------------------------------

    @property
    def text(self) -> Optional[str]:
        """Visible static text: ``Text.text`` or ``Button.title``.

        A ``TextInput``'s contents are exposed separately as ``value`` and
        ``placeholder`` so ``get_by_text`` never matches a form field.
        """
        for key in ("text", "title"):
            value = self.props.get(key)
            if isinstance(value, str):
                return value
        return None

    @property
    def placeholder(self) -> Optional[str]:
        """The ``placeholder`` prop of a ``TextInput`` (or ``Picker``), if set."""
        value = self.props.get("placeholder")
        return value if isinstance(value, str) else None

    @property
    def value(self) -> Optional[str]:
        """The string ``value`` prop (a ``TextInput``'s display value), if set."""
        value = self.props.get("value")
        return value if isinstance(value, str) else None

    @property
    def role(self) -> Optional[str]:
        """Effective accessibility role: the ``accessibility_role`` prop, else the type's implicit role.

        See [`IMPLICIT_ROLES`][pythonnative.testing.IMPLICIT_ROLES] for
        the implicit table.
        """
        explicit = self.props.get("accessibility_role")
        if isinstance(explicit, str):
            return explicit
        return IMPLICIT_ROLES.get(self.type_name)

    @property
    def accessible_name(self) -> Optional[str]:
        """What assistive technology would announce for this view.

        The ``accessibility_label`` prop wins; otherwise the view's own
        text or title, a ``Checkbox``'s ``label``, and finally the text
        of descendant views joined with single spaces (so a
        ``Pressable`` wrapping ``Text("Save")`` is named ``"Save"``).
        """
        if self.label is not None:
            return self.label
        if self.text is not None:
            return self.text
        inline = self.props.get("label")
        if isinstance(inline, str):
            return inline
        parts = [child.text for child in self.walk() if child is not self and child.text]
        return " ".join(parts) if parts else None

    @property
    def disabled(self) -> bool:
        """Whether the view is disabled via the ``disabled`` prop or ``accessibility_state``."""
        if self.props.get("disabled"):
            return True
        state = self.props.get("accessibility_state")
        return bool(isinstance(state, dict) and state.get("disabled"))

    @property
    def hidden(self) -> bool:
        """Whether this view is removed from layout (``display: "none"``)."""
        return self.props.get("display") == "none" or self.type_name == "Screen" and self.props.get("active") is False

    @property
    def test_id(self) -> Optional[str]:
        """The ``test_id`` prop, if set."""
        return self.props.get("test_id")

    @property
    def label(self) -> Optional[str]:
        """The ``accessibility_label`` prop, if set."""
        return self.props.get("accessibility_label")

    # -- traversal ------------------------------------------------------

    def walk(self, *, include_hidden: bool = True) -> Iterator["FakeView"]:
        """Yield this view and every descendant, depth-first.

        With ``include_hidden=False`` subtrees under a ``display: "none"``
        view are skipped (what a user can see).
        """
        if not include_hidden and self.hidden:
            return
        yield self
        for child in self.children:
            yield from child.walk(include_hidden=include_hidden)

    def find_all(self, predicate_or_type: Any) -> List["FakeView"]:
        """Every view in this subtree matching a type name or predicate."""
        if isinstance(predicate_or_type, str):
            wanted = predicate_or_type

            def predicate(v: "FakeView") -> bool:
                return v.type_name == wanted

        else:
            predicate = predicate_or_type
        return [v for v in self.walk() if predicate(v)]

    def find_first(self, predicate_or_type: Any) -> Optional["FakeView"]:
        """Return the first view in this subtree matching a type name or predicate, or ``None``."""
        found = self.find_all(predicate_or_type)
        return found[0] if found else None

    def dump(self, indent: int = 0) -> str:
        """Indented, human-readable subtree (for failing-test output)."""
        line = " " * indent + repr(self)
        x, y, w, h = self.frame
        if w or h:
            line += f" @({x:g},{y:g} {w:g}x{h:g})"
        return "\n".join([line, *(c.dump(indent + 2) for c in self.children)])


@dataclass(frozen=True)
class ListRowSnapshot:
    """One row of a list's dataset as the UI thread holds it."""

    key: str
    revision: int
    extent: float
    sticky: bool


@dataclass(frozen=True)
class ListSnapshot:
    """A ``VirtualList``'s dataset as the UI thread's data source sees it."""

    revision: int
    keys: List[str]
    rows: Dict[str, ListRowSnapshot]


class FakeBackend(BridgeBackend):
    """The bridge backend over the host core, recording one tuple per applied mutation.

    Args:
        intrinsic: Override the sizes the fake platform measures (defaults to
            [`DEFAULT_INTRINSIC`][pythonnative.testing.backend.DEFAULT_INTRINSIC]).
    """

    selective_layout = False

    def __init__(self, intrinsic: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self.intrinsic = dict(DEFAULT_INTRINSIC if intrinsic is None else intrinsic)
        surface = next(_surfaces)
        transport = FakeTransport(surface=surface, measure=self.intrinsic)
        super().__init__(transport, surface=surface)
        self.native = transport
        """The [`FakeTransport`][pythonnative.bridge.fake.FakeTransport]: what the UI thread mounted."""
        transport.measurer = self._measure
        transport.command_handler = self._run_command
        self.views: Dict[int, FakeView] = {}
        self.ops: List[Any] = []
        self.batches: List[List[Any]] = []
        self.measure_calls: List[int] = []
        self.commands: List[Tuple[int, str, Dict[str, Any]]] = []
        self.last_create_props: Dict[str, Any] = {}
        self.last_update_changes: Dict[str, Any] = {}
        self.focused_tag: Optional[int] = None
        """Tag of the ``TextInput`` that last received ``focus`` (``None`` after ``blur``)."""
        self.selections: Dict[int, Tuple[int, int]] = {}
        """``(start, end)`` selection per ``TextInput`` tag, set by ``set_selection`` and ``select_all``."""
        self.scroll_offsets: Dict[int, Dict[str, float]] = {}
        """Content offset per ``ScrollView`` tag, updated by ``scroll_to_offset`` and ``scroll_to_end``."""

    @property
    def animated(self) -> List[Tuple[int, str, Any]]:
        """Every ``(tag, prop, value)`` the core's animator wrote, in order."""
        return self.native.writes

    # ------------------------------------------------------------------
    # Commit channel
    # ------------------------------------------------------------------

    def apply_mutations(self, ops: Sequence[Mutation]) -> Any:
        """Record one batch in ``ops`` and ``batches``, then commit it to the core.

        Raises ``AssertionError`` on malformed transactions (unknown tags, double creates or destroys).
        """
        batch: List[Any] = []
        for op in ops:
            recorded = self._apply_one(op)
            self.ops.append(recorded)
            batch.append(recorded)
        self.batches.append(batch)
        return super().apply_mutations(ops)

    def accept_layout(self, payload: Any) -> None:
        """Record the core's frames on the logical views, then publish them."""
        if isinstance(payload, dict) and isinstance(payload.get("frames"), list):
            for tag, x, y, width, height in payload["frames"]:
                view = self.views.get(int(tag))
                # A root's frame belongs to the screen host, as on a device.
                if view is None or view.parent is None:
                    continue
                frame = (float(x), float(y), float(width), float(height))
                if view.frame != frame:
                    view.frame = frame
                    self.ops.append(("set_frame", view.id, *frame))
        super().accept_layout(payload)

    def _apply_one(self, op: Mutation) -> Tuple[Any, ...]:
        if isinstance(op, CreateOp):
            if op.tag in self.views:
                raise AssertionError(f"create: tag {op.tag} already registered")
            view = FakeView(op.tag, op.type_name, op.props)
            self.views[op.tag] = view
            self.last_create_props = dict(op.props)
            return ("create", op.type_name, view.id)

        if isinstance(op, UpdateOp):
            view = self._require(op.tag, "update")
            from ..mutations import UNSET

            for key, value in op.changed_props.items():
                if value is UNSET:
                    view.props.pop(key, None)
                else:
                    view.props[key] = value
            self.last_update_changes = dict(op.changed_props)
            return ("update", view.type_name, view.id, tuple(sorted(op.changed_props)))

        if isinstance(op, InsertOp):
            parent = self._require(op.parent_tag, "insert_child")
            child = self._require(op.child_tag, "insert_child")
            if child.parent is not None:
                child.parent.children.remove(child)
                child.parent = None
            index = max(0, min(op.index, len(parent.children)))
            parent.children.insert(index, child)
            child.parent = parent
            return ("insert_child", parent.id, child.id, index)

        if isinstance(op, DestroyOp):
            if op.tag not in self.views:
                raise AssertionError(f"destroy: unknown tag {op.tag}")
            view = self.views.pop(op.tag)
            if view.parent is not None:
                view.parent.children.remove(view)
                view.parent = None
            view.destroyed = True
            self.selections.pop(op.tag, None)
            self.scroll_offsets.pop(op.tag, None)
            if self.focused_tag == op.tag:
                self.focused_tag = None
            return ("destroy", view.id)

        raise AssertionError(f"unknown mutation op: {op!r}")

    def _require(self, tag: int, op_name: str) -> FakeView:
        view = self.views.get(tag)
        if view is None:
            raise AssertionError(f"{op_name}: unknown tag {tag}")
        return view

    # ------------------------------------------------------------------
    # The fake platform
    # ------------------------------------------------------------------

    def _measure(
        self, tag: int, component: str, props: Dict[str, Any], max_width: float, max_height: float
    ) -> Tuple[float, float]:
        view = self.views.get(tag)
        if view is not None:
            self.measure_calls.append(view.id)
        return self.intrinsic.get(component, (0.0, 0.0))

    def resolve_view(self, tag: int) -> Optional[FakeView]:  # type: ignore[override]
        """Return the logical view registered under ``tag``, or ``None``."""
        return self.views.get(tag)

    def command(self, tag: int, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Queue a view command through the core; the fake UI thread answers it.

        ``TextInput``: ``get_value`` returns the ``value`` prop; ``focus``
        and ``blur`` track ``focused_tag`` and fire ``on_focus`` /
        ``on_blur`` when the app wired them; ``clear`` empties the value;
        ``select_all`` and ``set_selection(start, end)`` record
        ``selections``. ``ScrollView``: ``scroll_to_offset(x, y)`` and
        ``scroll_to_end`` update ``scroll_offsets``; ``get_scroll_offset``
        returns ``{"x": ..., "y": ...}``. ``WebView``: ``can_go_back`` and
        ``can_go_forward`` are ``False``, ``get_url`` returns the ``url``
        prop, ``load_url(url)`` replaces it. ``VirtualList``:
        ``scroll_to_index`` and ``scroll_to_end`` drive the list request
        protocol. Every command is recorded in ``commands``.

        Returns:
            A future holding the command's result.
        """
        return super().command(tag, name, args)

    def _run_command(self, native: Any, name: str, arguments: Dict[str, Any]) -> Any:
        self.commands.append((native.tag, name, dict(arguments)))
        view = self.views.get(native.tag)
        if view is None:
            return None
        if view.type_name == "VirtualList":
            if name == "scroll_to_index":
                self.request_list(view.tag, int(arguments["index"]))
            elif name == "scroll_to_end":
                self.request_list(view.tag, max(0, len(self.native.list_keys(view.tag)) - 1))
            return None
        if view.type_name == "TextInput":
            return self._text_input_command(view, name, arguments)
        if view.type_name == "ScrollView":
            return self._scroll_view_command(view, name, arguments)
        if view.type_name == "WebView":
            return self._web_view_command(view, name, arguments)
        return None

    def _text_input_command(self, view: FakeView, name: str, arguments: Dict[str, Any]) -> Any:
        from ..events import dispatch_event

        value = view.value or ""
        if name == "get_value":
            return value
        if name == "focus":
            previous = self.focused_tag
            self.focused_tag = view.tag
            if previous is not None and previous != view.tag and previous in self.views:
                dispatch_event(previous, "on_blur")
            if previous != view.tag:
                dispatch_event(view.tag, "on_focus")
            return None
        if name == "blur":
            if self.focused_tag == view.tag:
                self.focused_tag = None
                dispatch_event(view.tag, "on_blur")
            return None
        if name == "clear":
            view.props["value"] = ""
            self.selections[view.tag] = (0, 0)
            return None
        if name == "select_all":
            self.selections[view.tag] = (0, len(value))
            return None
        if name == "set_selection":
            start = int(arguments.get("start", 0))
            end = int(arguments.get("end", start))
            self.selections[view.tag] = (start, end)
            return None
        return None

    def _scroll_view_command(self, view: FakeView, name: str, arguments: Dict[str, Any]) -> Any:
        offset = self.scroll_offsets.setdefault(view.tag, {"x": 0.0, "y": 0.0})
        if name == "get_scroll_offset":
            return dict(offset)
        if name == "scroll_to_offset":
            if "x" in arguments and arguments["x"] is not None:
                offset["x"] = float(arguments["x"])
            if "y" in arguments and arguments["y"] is not None:
                offset["y"] = float(arguments["y"])
            return None
        if name == "scroll_to_end":
            horizontal = bool(view.props.get("horizontal"))
            _, _, width, height = view.frame
            if horizontal:
                extent = max((c.frame[0] + c.frame[2] for c in view.children), default=0.0)
                offset["x"] = max(0.0, extent - width)
            else:
                extent = max((c.frame[1] + c.frame[3] for c in view.children), default=0.0)
                offset["y"] = max(0.0, extent - height)
            return None
        if name == "scroll_to_top":
            offset["x"] = 0.0
            offset["y"] = 0.0
            return None
        return None

    def _web_view_command(self, view: FakeView, name: str, arguments: Dict[str, Any]) -> Any:
        if name in ("can_go_back", "can_go_forward"):
            return False
        if name == "get_url":
            return view.props.get("url")
        if name == "get_title":
            return None
        if name == "load_url":
            url = arguments.get("url")
            if isinstance(url, str):
                view.props["url"] = url
            return None
        return None

    def list_store(self, tag: int) -> ListSnapshot:
        """The dataset the UI thread's data source holds for the ``VirtualList`` ``tag``."""
        rows = [ListRowSnapshot(*row) for row in self.native.list_rows(tag)]
        return ListSnapshot(
            self.native.list_revisions.get(tag, 0), [row.key for row in rows], {row.key: row for row in rows}
        )

    def request_list(self, tag: int, first: int, *, extent: float = 800.0) -> None:
        """Simulate a native viewport using the shared list request protocol."""
        from ..events import dispatch_event

        view = self._require(tag, "request_list")
        if view.type_name != "VirtualList":
            raise TypeError("request_list requires a VirtualList tag")
        rows = self.native.list_rows(tag)
        revision = self.native.list_revisions.get(tag, 0)
        keys = [row[0] for row in rows]
        heights = [row[2] for row in rows]
        sticky = [row[3] for row in rows]
        first = max(0, min(first, len(keys) - 1))
        last, covered = first, 0.0
        while last < len(keys) and covered < extent:
            covered += heights[last]
            last += 1
        offset = sum(heights[:first])
        pinned = next((i for i in range(first, -1, -1) if keys and sticky[i]), -1)
        horizontal = bool(view.props.get("horizontal"))
        dispatch_event(
            tag,
            "on_window",
            {
                "revision": revision,
                "sticky": pinned,
                "first": first,
                "last": last - 1,
                "extent": extent,
                "range": sum(heights),
                "x": offset if horizontal else 0,
                "y": 0 if horizontal else offset,
            },
        )
        dispatch_event(
            tag,
            "on_scroll",
            {
                "extent": extent,
                "range": sum(heights),
                "x": offset if horizontal else 0,
                "y": 0 if horizontal else offset,
            },
        )
        if keys:
            dispatch_event(
                tag,
                "on_bind_row",
                {
                    "sticky": pinned,
                    "key": keys[first],
                    "index": first,
                    "revision": revision,
                    "extent": extent,
                    "width": view.frame[2],
                },
            )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def live_view_count(self) -> int:
        """Return how many logical views are registered (created and not yet destroyed)."""
        return len(self.views)

    def mounted_view_count(self) -> int:
        """Return how many views the UI thread mounted (flattened views excluded)."""
        return len(self.native.views)

    def ops_of(self, kind: str) -> List[Any]:
        """Every recorded op tuple whose first element is ``kind``."""
        return [op for op in self.ops if op[0] == kind]

    def detached_views(self, type_name: Optional[str] = None) -> List[FakeView]:
        """Live views never inserted into a parent (``Portal`` overlays, the root)."""
        out = [v for v in self.views.values() if v.parent is None]
        if type_name is not None:
            out = [v for v in out if v.type_name == type_name]
        return out
