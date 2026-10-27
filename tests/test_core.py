"""The renderer core (RFC 0007), driven through its C ABI on the host build.

These tests talk to the same library the apps link, through
``pythonnative.bridge.core``, with a ``FakeTransport`` playing the
platform's UI thread. They cover the core's own contract: validation and
rollback, layout and measurement, view flattening and the mount diff, list
datasets, commands, events, animation, and gestures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

import pythonnative  # noqa: F401  # registers the built-in contracts
from pythonnative.bridge import contract_document
from pythonnative.bridge.core import (
    POINTER_DOWN,
    POINTER_MOVE,
    POINTER_UP,
    PROTOCOL_VERSION,
    load_core,
)
from pythonnative.bridge.fake import FakeTransport

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = {"width": 320, "height": 480}


class Surface:
    """One core surface with a recording fake UI thread."""

    def __init__(self, surface: int = 40, measure: Optional[Dict[str, Tuple[float, float]]] = None) -> None:
        self.transport = FakeTransport(surface=surface, measure=measure)
        self.surface = surface
        self.messages: List[Tuple[str, int, str, Any]] = []
        self.transport.set_callback(
            lambda kind, tag, name, payload: self.messages.append((kind, tag, name, json.loads(payload or "null")))
        )
        self.core = self.transport.core
        self.core.load_contracts(contract_document(), "host")
        self.application = "app"
        self.revision = 0
        self.roots: List[int] = [1]

    def commit(
        self, *ops: List[Any], roots: Optional[List[int]] = None, layout: bool = True, ok: bool = True
    ) -> Dict[str, Any]:
        envelope: Dict[str, Any] = {
            "version": PROTOCOL_VERSION,
            "application": self.application,
            "surface": self.surface,
            "revision": self.revision + 1,
            "ops": list(ops),
        }
        if layout:
            envelope["layout"] = {"roots": roots or self.roots, **VIEWPORT, "selective": False}
        before = len(self.transport.transactions)
        ack = json.loads(self.transport.commit(json.dumps(envelope)))
        assert ack["ok"] is ok, ack
        if ok:
            self.revision += 1
        self.last = [op for t in self.transport.transactions[before:] for op in t.ops]
        return ack

    def frames(self, ack: Dict[str, Any]) -> Dict[int, Tuple[float, ...]]:
        return {int(f[0]): tuple(f[1:]) for f in ack["layout"]["frames"]}

    def kinds(self) -> List[Tuple[str, int]]:
        return [(op.kind, op.tag) for op in self.last if op.kind != "frame"]

    def view(self, tag: int) -> Any:
        return self.transport.views[tag]


# ----------------------------------------------------------------------
# Contracts
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", json.loads((ROOT / "tests/contracts/validation.json").read_text()), ids=lambda c: c["name"]
)
def test_shared_validation_corpus(case: Dict[str, Any]) -> None:
    assert load_core().check_value(json.dumps(case["schema"]), json.dumps(case["value"])) is case["valid"]


def test_protocol_and_fingerprint() -> None:
    surface = Surface()
    assert surface.core.protocol_version() == PROTOCOL_VERSION == 7
    from pythonnative.sdk.schema import fingerprint

    assert surface.core.fingerprint() == fingerprint()


def test_rejection_names_the_prop_and_leaves_the_tree() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}])
    ack = surface.commit(["c", 2, "Text", {"text": 3}], ["i", 1, 2, 0], ok=False)
    assert ack["failed"] is False and "Text.text" in ack["error"] and ack["op"] == 0
    assert surface.last == []
    # The rejected revision can be retried.
    surface.commit(["c", 2, "Text", {"text": "ok"}], ["i", 1, 2, 0])
    assert surface.view(2).props["text"] == "ok"


@pytest.mark.parametrize(
    "ops",
    [
        [["c", 1, "View", {}]],  # duplicate create
        [["u", 9, {}, []]],  # unknown tag
        [["i", 2, 1, 0]],  # cycle
        [["d", 1]],  # destroy with children
        [["i", 1, 2, 5]],  # index past the child count
        [["c", 3, "NoSuchView", {}]],
        [["u", 2, {"opacity": 1}, ["opacity"]]],  # set and removed
        [["u", 2, {"bogus": 1}, []]],
    ],
)
def test_structural_validation(ops: List[List[Any]]) -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}], ["c", 2, "View", {"background_color": "#000"}], ["i", 1, 2, 0])
    surface.commit(*ops, ok=False)
    assert surface.revision == 1 and set(surface.transport.views) == {1, 2}


def test_stale_revision_and_new_application() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}])
    surface.revision = 5
    surface.commit(["c", 2, "View", {}], ok=False)
    surface.revision = 1
    surface.application = "next"
    surface.revision = 0
    surface.commit(["c", 1, "View", {"background_color": "#fff"}])
    assert surface.last[0].kind == "reset" and surface.transport.views[1].props == {"background_color": "#fff"}


# ----------------------------------------------------------------------
# Layout and measurement
# ----------------------------------------------------------------------


def test_layout_frames_and_edge_families() -> None:
    surface = Surface()
    ack = surface.commit(
        ["c", 1, "View", {"padding": 10, "flex_direction": "row"}],
        ["c", 2, "View", {"width": 50, "height": 20, "margin": {"left": 5, "top": 3}}],
        ["c", 3, "View", {"flex": 1, "height": 20, "background_color": "#000"}],
        ["i", 1, 2, 0],
        ["i", 1, 3, 1],
    )
    frames = surface.frames(ack)
    assert frames[2] == (15.0, 13.0, 50.0, 20.0)
    assert frames[3] == (65.0, 10.0, 245.0, 20.0)
    ack = surface.commit(["u", 2, {}, ["margin"]])
    assert surface.frames(ack)[2] == (10.0, 10.0, 50.0, 20.0)


def test_text_measurement_goes_to_the_platform() -> None:
    surface = Surface(measure={"Text": (42.0, 18.0)})
    ack = surface.commit(["c", 1, "View", {}], ["c", 2, "Text", {"text": "Hi"}], ["i", 1, 2, 0])
    assert surface.frames(ack)[2][2:] == (320.0, 18.0)
    assert (2, "Text") in surface.transport.measured


def test_container_measurement_is_style_only() -> None:
    surface = Surface()
    ack = surface.commit(["c", 1, "View", {"align_items": "flex_start"}], ["c", 2, "Pressable", {}], ["i", 1, 2, 0])
    assert surface.frames(ack)[2][2:] == (0.0, 0.0)
    assert all(component != "Pressable" for _, component in surface.transport.measured)


def test_image_and_svg_sizes_come_from_the_core() -> None:
    surface = Surface()
    surface.transport.reports_images = False
    ack = surface.commit(
        ["c", 1, "View", {"align_items": "flex_start"}],
        ["c", 2, "Image", {"source": "logo.png"}],
        ["c", 3, "Svg", {"view_box": "0 0 48 24"}],
        ["i", 1, 2, 0],
        ["i", 1, 3, 1],
    )
    assert surface.frames(ack)[2][2:] == (0.0, 0.0)
    assert surface.frames(ack)[3][2:] == (48.0, 24.0)
    surface.transport.report_intrinsic(2, 640.0, 320.0)
    layout = [m for m in surface.messages if m[0] == "layout"][-1][3]
    assert {f[0]: tuple(f[1:]) for f in layout["frames"]}[2] == (0.0, 0.0, 320.0, 160.0)


def test_lists_fill_and_clip() -> None:
    surface = Surface()
    dataset = {"base": 0, "revision": 1, "changes": [["reset", [["a", 1, 44, False]]]]}
    ack = surface.commit(
        ["c", 1, "View", {"flex_direction": "row"}],
        ["c", 2, "VirtualList", {"dataset": dataset}],
        ["i", 1, 2, 0],
    )
    assert surface.frames(ack)[2][3] == 480.0
    assert surface.transport.list_keys(2) == ["a"]


def test_detached_roots_lay_out_in_reported_containers() -> None:
    surface = Surface()
    surface.commit(
        ["c", 1, "ScreenStack", {"flex": 1}],
        ["c", 2, "Screen", {"route_key": "a"}],
        ["c", 3, "View", {"flex": 1, "background_color": "#fff"}],
        ["i", 2, 3, 0],
        ["i", 1, 2, 0],
    )
    assert surface.view(3).frame[2:] == (320.0, 480.0)
    surface.transport.report_container(2, 300.0, 400.0, x=0.0, y=64.0)
    assert surface.view(3).frame[2:] == (300.0, 400.0)
    assert any(kind == "layout" for kind, *_ in surface.messages)
    window = json.loads(surface.core.measure(surface.surface, 3))["window"]
    assert window[1] == 64.0


def test_loading_more_contracts_keeps_mounted_components_valid() -> None:
    # Plugins register components after the first render, so contracts load
    # again while views exist. Existing nodes must keep pointing at their
    # components however many new ones the load adds.
    surface = Surface()
    surface.commit(["c", 1, "Column", {}], ["c", 2, "Text", {"text": "hi"}], ["i", 1, 2, 0])
    document = json.loads(contract_document())
    text = document["components"]["Text"]
    document["components"] = {f"PluginLabel{index}": dict(text) for index in range(200)}
    surface.core.load_contracts(json.dumps(document), "host")
    surface.commit(["u", 2, {"text": "bye"}, []])
    assert surface.view(2).props["text"] == "bye"
    ack = surface.commit(["u", 2, {"colour": "#fff"}, []], ok=False)
    assert "unknown Text prop colour" in ack["error"]
    surface.commit(["c", 3, "PluginLabel7", {"text": "plugin"}], ["i", 1, 3, 1])
    assert surface.view(3).type_name == "PluginLabel7"


# ----------------------------------------------------------------------
# Flattening and the mount diff
# ----------------------------------------------------------------------


def test_layout_only_views_are_flattened() -> None:
    surface = Surface()
    surface.commit(
        ["c", 1, "Column", {"padding": 8}],
        ["c", 2, "Row", {"padding": 4, "gap": 2}],
        ["c", 3, "Text", {"text": "a"}],
        ["i", 2, 3, 0],
        ["i", 1, 2, 0],
    )
    assert set(surface.transport.views) == {1, 3}
    assert surface.view(3).parent is surface.view(1)
    assert surface.view(3).frame[:2] == (12.0, 12.0)
    assert json.loads(surface.core.measure(surface.surface, 2))["mounted"] is False


def test_paint_props_unflatten_and_flatten_again() -> None:
    surface = Surface()
    surface.commit(
        ["c", 1, "Column", {}],
        ["c", 2, "Row", {"padding": 4}],
        ["c", 3, "Text", {"text": "a"}],
        ["i", 2, 3, 0],
        ["i", 1, 2, 0],
    )
    surface.commit(["u", 2, {"background_color": "#f00"}, []])
    assert ("create", 2) in surface.kinds()
    assert surface.view(3).parent is surface.view(2) and surface.view(2).parent is surface.view(1)
    assert surface.view(3).frame[:2] == (4.0, 4.0)
    surface.commit(["u", 2, {}, ["background_color"]])
    assert ("delete", 2) in surface.kinds() and 2 not in surface.transport.views
    assert surface.view(3).parent is surface.view(1) and surface.view(3).frame[:2] == (4.0, 4.0)


@pytest.mark.parametrize(
    "prop", [{"test_id": "row"}, {"accessibility_label": "Row"}, {"_pn_events": ["on_press"]}, {"opacity": 0.5}]
)
def test_identity_and_paint_props_keep_views_mounted(prop: Dict[str, Any]) -> None:
    surface = Surface()
    surface.commit(["c", 1, "Column", {}], ["c", 2, "Row", {"padding": 4, **prop}], ["i", 1, 2, 0])
    assert 2 in surface.transport.views


def test_flattening_can_be_disabled() -> None:
    surface = Surface()
    surface.core.set_flattening(False)
    try:
        surface.commit(["c", 1, "Column", {}], ["c", 2, "Row", {"padding": 4}], ["i", 1, 2, 0])
        assert 2 in surface.transport.views
    finally:
        surface.core.set_flattening(True)


def test_children_of_special_containers_never_flatten() -> None:
    surface = Surface()
    surface.commit(["c", 1, "ScrollView", {}], ["c", 2, "Column", {"padding": 4}], ["i", 1, 2, 0])
    assert 2 in surface.transport.views


@pytest.mark.parametrize(
    "painted, change, mounted",
    [
        (True, ["u", 3, {}, ["background_color"]], [2, 5, 4]),  # flattens away while it moves
        (False, ["u", 3, {"background_color": "#0f0"}, []], [2, 5, 3]),  # mounts while it moves
    ],
)
def test_moving_a_wrapper_while_it_flattens_keeps_sibling_order(
    painted: bool, change: List[Any], mounted: List[int]
) -> None:
    # Within one transaction a wrapper that flattens away is deleted only after
    # the inserts, and its children leave only when their new parent is
    # processed, so insert indices must count the views still in place.
    surface = Surface()
    surface.commit(
        ["c", 1, "Column", {}],
        ["c", 2, "Text", {"text": "a"}],
        ["c", 3, "View", {"background_color": "#f00"} if painted else {}],
        ["c", 4, "Text", {"text": "b"}],
        ["c", 5, "Text", {"text": "c"}],
        ["i", 3, 4, 0],
        ["i", 1, 2, 0],
        ["i", 1, 3, 1],
        ["i", 1, 5, 2],
    )
    surface.commit(["i", 1, 3, 2], change)
    assert [child.tag for child in surface.view(1).children] == mounted


@pytest.mark.parametrize("seed", range(60))
def test_flattening_matches_the_logical_tree_under_random_edits(seed: int) -> None:
    import random

    rng = random.Random(seed)
    surface = Surface(surface=1000 + seed)
    children: Dict[int, List[int]] = {1: []}
    painted: Dict[int, bool] = {1: True}
    next_tag = 2
    surface.commit(["c", 1, "Column", {}])

    def flat(tag: int) -> List[int]:
        out: List[int] = []
        for child in children.get(tag, []):
            out += flat(child) if child in children and not painted[child] else [child]
        return out

    for _ in range(20):
        ops: List[List[Any]] = []
        for _ in range(rng.randint(1, 3)):
            containers = list(children)
            roll = rng.random()
            if roll < 0.45:
                tag, next_tag = next_tag, next_tag + 1
                parent = rng.choice(containers)
                index = rng.randint(0, len(children[parent]))
                if rng.random() < 0.5:
                    ops.append(["c", tag, "Text", {"text": str(tag)}])
                else:
                    painted[tag] = rng.random() < 0.5
                    children[tag] = []
                    ops.append(["c", tag, "View", {"background_color": "#f00"} if painted[tag] else {}])
                ops.append(["i", parent, tag, index])
                children[parent].insert(index, tag)
            elif roll < 0.75:
                views = [tag for tag in children if tag != 1]
                if views:
                    tag = rng.choice(views)
                    painted[tag] = not painted[tag]
                    ops.append(
                        ["u", tag, {"background_color": "#0f0"}, []]
                        if painted[tag]
                        else ["u", tag, {}, ["background_color"]]
                    )
            else:
                parent = rng.choice(containers)
                if len(children[parent]) > 1:
                    tag = rng.choice(children[parent])
                    children[parent].remove(tag)
                    index = rng.randint(0, len(children[parent]))
                    children[parent].insert(index, tag)
                    ops.append(["i", parent, tag, index])
        if not ops:
            continue
        surface.commit(*ops)
        for tag in children:
            if painted[tag]:
                assert [child.tag for child in surface.view(tag).children] == flat(tag), (seed, ops)


def test_mount_order_and_update_normalization() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}], ["c", 2, "TextInput", {"value": "a"}], ["i", 1, 2, 0])
    kinds = [op.kind for op in surface.last if op.kind != "frame"]
    assert kinds == ["create", "create", "insert"]
    surface.commit(["u", 2, {"multiline": True}, ["value"]])
    update = next(op for op in surface.last if op.kind == "update")
    assert update.recreate is True and update.removed == ("value",) and "value" in update.props


def test_moves_use_the_fewest_inserts() -> None:
    surface = Surface()
    ops = [["c", 1, "View", {}]] + [["c", t, "View", {"background_color": "#000"}] for t in range(2, 7)]
    ops += [["i", 1, t, t - 2] for t in range(2, 7)]
    surface.commit(*ops)
    surface.commit(["i", 1, 6, 0])
    inserts = [op for op in surface.last if op.kind == "insert"]
    assert [(op.tag, op.index) for op in inserts] == [(6, 0)]
    assert [child.tag for child in surface.view(1).children] == [6, 2, 3, 4, 5]


def test_deletes_and_unmount() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}], ["c", 2, "Text", {"text": "x"}], ["i", 1, 2, 0])
    surface.commit(["d", 2])
    assert surface.kinds() == [("delete", 2)] and surface.view(1).children == []


# ----------------------------------------------------------------------
# Lists
# ----------------------------------------------------------------------


def test_shared_list_trace() -> None:
    surface = Surface()
    created = False
    for step in json.loads((ROOT / "tests/contracts/list-trace.json").read_text()):
        if not created:
            surface.commit(["c", 1, "VirtualList", {"dataset": step["packet"]}], layout=False, ok=step["valid"])
            created = step["valid"]
        else:
            surface.commit(["u", 1, {"dataset": step["packet"]}, []], layout=False, ok=step["valid"])
        assert surface.transport.list_keys(1) == step["keys"], step["name"]
        assert surface.transport.list_revisions.get(1, 0) == step["revision"], step["name"]
        assert surface.core.list_revision(surface.surface, 1) == step["revision"], step["name"]


# ----------------------------------------------------------------------
# Commands and events
# ----------------------------------------------------------------------


def test_commands_queue_behind_mounts() -> None:
    surface = Surface()
    surface.transport.command_results["get_value"] = "typed"
    surface.commit(["c", 1, "View", {}], ["c", 2, "TextInput", {"value": "a"}], ["i", 1, 2, 0])
    reply = json.loads(surface.core.command(surface.surface, 2, "get_value", "{}", 7))
    assert reply == {"ok": True, "queued": True}
    surface.transport.drain()
    assert surface.transport.commands[-1][:2] == (2, "get_value")
    assert ("command", 0, "", {"call_id": 7, "ok": True, "value": "typed"}) in surface.messages


def test_commands_reject_flattened_and_invalid_targets() -> None:
    surface = Surface()
    surface.commit(
        ["c", 1, "Column", {}], ["c", 2, "ScrollView", {}], ["c", 3, "Row", {}], ["i", 1, 3, 0], ["i", 1, 2, 1]
    )
    assert "isn't mounted" in json.loads(surface.core.command(surface.surface, 3, "scroll_to_end", "{}", 1))["error"]
    assert not json.loads(surface.core.command(surface.surface, 2, "scroll_to_offset", '{"bogus": 1}', 2))["ok"]


def test_events_are_stamped_with_the_mounted_revision() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}], ["c", 2, "Switch", {"value": False}], ["i", 1, 2, 0])
    surface.transport.fire(2, "on_change", True)
    surface.transport.fire(2, "on_change", False)
    events = [m for m in surface.messages if m[0] == "event"]
    assert [e[3]["sequence"] for e in events] == [1, 2]
    assert events[0][3]["revision"] == 1 and events[0][3]["args"] == [True]


def test_events_feed_animated_bindings_on_the_ui_thread() -> None:
    surface = Surface()
    graph = {"id": 9, "nodes": [{"id": 9, "kind": "value", "value": 0}], "bindings": [[3, "opacity", 9]]}
    surface.commit(
        ["c", 1, "View", {}],
        ["c", 2, "ScrollView", {"_pn_animated_events": {"on_scroll": {"y": 9}}, "_pn_events": ["on_scroll"]}],
        ["c", 3, "View", {"opacity": 1, "background_color": "#000"}],
        ["i", 1, 2, 0],
        ["i", 1, 3, 1],
    )
    surface.core.animate(surface.surface, 3, json.dumps({"op": "graph", "graph": graph}))
    surface.transport.drain()
    surface.transport.fire(2, "on_scroll", {"x": 0, "y": 0.25})
    assert (3, "opacity", 0.25) in surface.transport.writes


# ----------------------------------------------------------------------
# Animation
# ----------------------------------------------------------------------


def _run_frames(surface: Surface, start: float, frames: int, step: float = 1000 / 60) -> None:
    """Advance the core's animator as the display link would, applying writes after each frame."""
    from pythonnative.bridge import fake

    for index in range(frames):
        surface.core.animation_frame(start + index * step)
        fake._take_writes()


def test_timing_driver_on_a_direct_prop() -> None:
    surface = Surface()
    surface.commit(["c", 1, "View", {}], ["c", 2, "View", {"opacity": 1, "background_color": "#000"}], ["i", 1, 2, 0])
    request = {
        "op": "start",
        "id": 1,
        "prop": "opacity",
        "spec": {"kind": "timing", "to": 0, "duration_ms": 100, "easing": "linear"},
    }
    assert json.loads(surface.core.animate(surface.surface, 2, json.dumps(request)))["ok"]
    surface.transport.drain()
    _run_frames(surface, 0, 12)
    values = [value for tag, prop, value in surface.transport.writes if tag == 2 and prop == "opacity"]
    assert values[0] < 1 and values[-1] == 0
    done = [m[3] for m in surface.messages if m[0] == "animation"]
    assert done == [{"id": 1, "finished": True, "value": 0.0}]


def test_spring_and_decay_settle() -> None:
    surface = Surface()
    for anim_id, spec in (
        (2, {"kind": "spring", "from": 0, "to": 1}),
        (3, {"kind": "decay", "from": 0, "velocity": 1, "deceleration": 0.99}),
    ):
        request = {"op": "start", "id": anim_id, "prop": f"_pn_value:{anim_id}", "spec": dict(spec, report=False)}
        assert json.loads(surface.core.animate(surface.surface, 0, json.dumps(request)))["ok"]
    surface.transport.drain()
    _run_frames(surface, 0, 600)
    done = {m[3]["id"]: m[3] for m in surface.messages if m[0] == "animation" and "finished" in m[3]}
    assert done[2]["finished"] and done[2]["value"] == 1.0
    assert done[3]["finished"] and done[3]["value"] == pytest.approx(100.0)


def test_cancel_reports_the_current_value_and_reports_stream() -> None:
    surface = Surface()
    request = {
        "op": "start",
        "id": 4,
        "prop": "_pn_value:4",
        "spec": {"kind": "timing", "from": 0, "to": 10, "duration_ms": 1000, "easing": "linear", "report": True},
    }
    surface.core.animate(surface.surface, 0, json.dumps(request))
    surface.transport.drain()
    _run_frames(surface, 0, 5)
    reports = [m[3]["value"] for m in surface.messages if m[0] == "animation" and "finished" not in m[3]]
    assert len(reports) == 5 and reports == sorted(reports)
    surface.core.animate(surface.surface, 0, json.dumps({"op": "cancel", "id": 4}))
    surface.transport.drain()
    final = [m[3] for m in surface.messages if m[0] == "animation" and "finished" in m[3]][-1]
    assert final["finished"] is False and final["value"] == pytest.approx(reports[-1])


def test_sampled_easing_and_reduce_motion() -> None:
    surface = Surface()
    samples = [i / 4 for i in range(5)]
    request = {
        "op": "start",
        "id": 5,
        "prop": "_pn_value:5",
        "spec": {"kind": "timing", "from": 0, "to": 1, "duration_ms": 1000, "easing": {"samples": samples}},
    }
    assert json.loads(surface.core.animate(surface.surface, 0, json.dumps(request)))["ok"]
    surface.core.set_reduce_motion(True)
    try:
        surface.transport.drain()
        _run_frames(surface, 0, 1)
        final = [m[3] for m in surface.messages if m[0] == "animation" and "finished" in m[3]][-1]
        assert final == {"id": 5, "finished": True, "value": 1.0}
    finally:
        surface.core.set_reduce_motion(False)


def test_invalid_animation_requests_are_refused() -> None:
    surface = Surface()
    bad = [
        {"op": "start", "id": 1, "prop": "width", "spec": {"kind": "timing", "to": 1}},
        {"op": "start", "id": 1, "prop": "opacity", "spec": {"kind": "timing", "to": 1, "easing": "wobble"}},
        {"op": "start", "id": 1, "prop": "opacity", "spec": {"kind": "teleport", "to": 1}},
        {"op": "explode"},
    ]
    for request in bad:
        assert json.loads(surface.core.animate(surface.surface, 0, json.dumps(request)))["ok"] is False


# ----------------------------------------------------------------------
# Gestures
# ----------------------------------------------------------------------


def _gesture_surface(*specs: Dict[str, Any]) -> Surface:
    surface = Surface()
    surface.commit(
        ["c", 1, "View", {}],
        [
            "c",
            2,
            "View",
            {
                "width": 100,
                "height": 100,
                "gestures": list(specs),
                "_pn_events": [f"gesture:{i}" for i in range(len(specs))],
            },
        ],
        ["i", 1, 2, 0],
    )
    return surface


def _gesture_events(surface: Surface) -> List[Tuple[str, Dict[str, Any]]]:
    return [(m[2], m[3]["args"][0]) for m in surface.messages if m[0] == "event" and m[2].startswith("gesture:")]


def test_tap_and_pan_activation() -> None:
    surface = _gesture_surface({"kind": "tap"}, {"kind": "pan", "active_offset_x": [-20, 20], "min_distance": None})
    surface.transport.pointer(2, [(POINTER_DOWN, 0, 10, 10, 10, 60, 0.0), (POINTER_UP, 0, 11, 10, 11, 60, 0.05)])
    assert [name for name, _ in _gesture_events(surface)] == ["gesture:0"]
    assert _gesture_events(surface)[0][1]["absolute_y"] == 60
    surface.messages.clear()
    active = surface.transport.pointer(
        2,
        [
            (POINTER_DOWN, 0, 10, 10, 10, 10, 1.0),
            (POINTER_MOVE, 0, 25, 10, 25, 10, 1.02),  # inside the active offset: still waiting
            (POINTER_MOVE, 0, 40, 10, 40, 10, 1.04),  # crosses it: began
            (POINTER_MOVE, 0, 50, 10, 50, 10, 1.06),
        ],
    )
    states = [(name, payload["state"]) for name, payload in _gesture_events(surface)]
    assert active is True and states == [("gesture:1", "began"), ("gesture:1", "changed")]


def test_exclusive_double_tap_waits_for_single() -> None:
    surface = _gesture_surface(
        {"kind": "tap", "n_taps": 2, "wait_for": []}, {"kind": "tap", "wait_for": [0], "simultaneous": []}
    )
    surface.transport.pointer(2, [(POINTER_DOWN, 0, 5, 5, 5, 5, 0.0), (POINTER_UP, 0, 5, 5, 5, 5, 0.05)])
    assert _gesture_events(surface) == []
    deadline = surface.transport.gesture_deadline(2)
    assert deadline is not None
    surface.transport.poll_gestures(2, deadline + 0.01)
    assert [name for name, _ in _gesture_events(surface)] == ["gesture:1"]


def test_long_press_and_pinch() -> None:
    surface = _gesture_surface({"kind": "long_press", "min_duration_ms": 200}, {"kind": "pinch"})
    surface.transport.pointer(2, [(POINTER_DOWN, 0, 5, 5, 5, 5, 0.0)])
    surface.transport.poll_gestures(2, 0.25)
    assert ("gesture:0", "began") in [(n, p["state"]) for n, p in _gesture_events(surface)]
    surface.transport.pointer(2, [(POINTER_UP, 0, 5, 5, 5, 5, 0.3)])
    surface.messages.clear()
    surface.transport.pointer(
        2,
        [
            (POINTER_DOWN, 0, 0, 0, 0, 0, 1.0),
            (POINTER_DOWN, 1, 10, 0, 10, 0, 1.0),
            (POINTER_MOVE, 1, 20, 0, 20, 0, 1.1),
        ],
    )
    scales = [p.get("scale") for n, p in _gesture_events(surface) if n == "gesture:1"]
    assert scales == [1.0, 2.0]
