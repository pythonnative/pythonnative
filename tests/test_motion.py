"""Motion end to end, headless: hooks, shared values, layout animations, and components (RFC 0009).

Everything here renders through the reconciler into the host build of the
renderer core, so worklets run in the same VM as on a device, driven by the
virtual clock.
"""

from __future__ import annotations

from typing import Any, List

import pytest

import pythonnative as pn
from pythonnative import gestures
from pythonnative.motion import FadeIn, FadeOut, Keyframes, LayoutAnimationConfig, LinearTransition, SlideIn
from pythonnative.testing import FakeClock, render


def settle_animations(tree: Any, clock: FakeClock, seconds: float = 2.0) -> None:
    clock.advance(seconds)
    tree.settle()


# ----------------------------------------------------------------------
# Shared values and hooks
# ----------------------------------------------------------------------


def test_shared_values_read_write_and_await_from_python(pn_clock: FakeClock) -> None:
    holder: List[Any] = []

    @pn.component
    def Box() -> pn.Node:
        offset = pn.use_shared_value(1.0)
        holder.append(offset)
        style = pn.use_animated_style(lambda: {"opacity": offset.value})
        return pn.View(style=[{"width": 10, "height": 10}, style], test_id="box")

    tree = render(Box())
    offset = holder[-1]
    box = tree.get_by_test_id("box")
    assert offset.value == 1.0
    offset.value = 0.25
    assert offset.value == 0.25  # a read right after a write sees it
    tree.settle()
    assert tree.presented_style(box)["opacity"] == 0.25

    results: List[bool] = []

    async def run() -> None:
        results.append(await offset.animate(pn.with_timing(1.0, duration=100)))

    task = pn.runtime.get_loop().create_task(run())
    settle_animations(tree, pn_clock)
    assert task.done() and results == [True]
    assert offset.value == 1.0
    assert tree.presented_style(box)["opacity"] == 1.0


def test_interrupted_awaits_report_false(pn_clock: FakeClock) -> None:
    holder: List[Any] = []

    @pn.component
    def Box() -> pn.Node:
        holder.append(pn.use_shared_value(0.0))
        return pn.View()

    tree = render(Box())
    value = holder[-1]
    results: List[bool] = []

    async def run() -> None:
        results.append(await value.animate(pn.with_timing(10.0, duration=1000)))

    pn.runtime.get_loop().create_task(run())
    pn_clock.advance(0.1)
    tree.settle()
    value.value = 3.0
    settle_animations(tree, pn_clock)
    assert results == [False] and value.value == 3.0


def test_derived_values_reactions_and_run_on_python(pn_clock: FakeClock) -> None:
    crossings: List[bool] = []
    holder: List[Any] = []

    @pn.component
    def Meter() -> pn.Node:
        level = pn.use_shared_value(0.0)
        doubled = pn.use_derived_value(lambda: level.value * 2)
        holder.append((level, doubled))

        def crossed(high: bool) -> None:
            crossings.append(high)

        pn.use_animated_reaction(lambda: doubled.value > 10, lambda high, _before: pn.run_on_python(crossed, high))
        return pn.View()

    tree = render(Meter())
    level, doubled = holder[-1]
    level.value = 6.0
    tree.settle()
    assert doubled.value == 12.0
    level.value = 2.0
    tree.settle()
    assert crossings == [False, True, False]
    with pytest.raises(AttributeError, match="read-only"):
        doubled.value = 3


def test_frame_callbacks_run_while_active(pn_clock: FakeClock) -> None:
    holder: List[Any] = []

    @pn.component
    def Spinner(active: bool) -> pn.Node:
        angle = pn.use_shared_value(0.0)
        holder.append(angle)

        @pn.worklet
        def spin(frame: pn.FrameInfo) -> None:
            angle.value = angle.value + frame.delta_ms

        pn.use_frame_callback(spin, active=active)
        return pn.View()

    tree = render(Spinner(True))
    pn_clock.advance(0.5)
    tree.settle()
    moved = holder[-1].value
    assert moved > 100
    tree.rerender(Spinner(False))
    pn_clock.advance(0.5)
    tree.settle()
    assert holder[-1].value == pytest.approx(moved, abs=50)


def test_scroll_worklets_run_in_the_core(pn_clock: FakeClock) -> None:
    @pn.component
    def Header() -> pn.Node:
        scroll = pn.use_shared_value(0.0)

        @pn.worklet
        def track(event: pn.ScrollEvent) -> None:
            scroll.value = event.y

        fade = pn.use_animated_style(lambda: {"opacity": pn.interpolate(scroll.value, (0, 100), (1, 0), "clamp")})
        return pn.Column(
            pn.View(style=[{"height": 40}, fade], test_id="header"),
            pn.ScrollView(pn.View(style={"height": 1000}), on_scroll=track),
        )

    tree = render(Header())
    scroll = next(view for view in tree.views() if view.type_name == "ScrollView")
    tree.fire(scroll, "on_scroll", {"x": 0, "y": 50})
    assert tree.presented_style(tree.get_by_test_id("header"))["opacity"] == 0.5


def test_gesture_worklets_keep_working_while_python_callbacks_run_too(pn_clock: FakeClock) -> None:
    ended: List[float] = []

    @pn.component
    def Card() -> pn.Node:
        x = pn.use_shared_value(0.0)

        @pn.worklet
        def drag(event: gestures.GestureEvent) -> None:
            x.value = event.translation_x

        moved = pn.use_animated_style(lambda: {"transform": [{"translate_x": x.value}]})
        return pn.View(
            style=[{"width": 100, "height": 100}, moved],
            gestures=[gestures.Pan(on_change=drag, on_end=lambda event: ended.append(event.translation_x))],
            test_id="card",
        )

    tree = render(Card())
    card = tree.get_by_test_id("card")
    tree.drag(card, dx=60)
    assert tree.presented_style(card)["transform"][0]["translate_x"] > 40
    assert len(ended) == 1


def test_animated_styles_override_static_keys_and_restore_them(pn_clock: FakeClock) -> None:
    holder: List[Any] = []

    @pn.component
    def Box() -> pn.Node:
        lifted = pn.use_shared_value(True)
        holder.append(lifted)
        style = pn.use_animated_style(lambda: {"opacity": 0.5, "transform": [{"scale": 2}]} if lifted.value else {})
        return pn.View(style=[{"opacity": 0.9, "transform": [{"rotate": 10}]}, style], test_id="box")

    tree = render(Box())
    box = tree.get_by_test_id("box")
    assert tree.presented_style(box)["transform"] == [{"scale": 2}]
    holder[-1].value = False
    tree.settle()
    assert tree.presented_style(box)["opacity"] == 0.9
    assert tree.presented_style(box)["transform"] == [{"rotate": 10}]


def test_layout_props_animate_through_the_layout_worker(pn_clock: FakeClock) -> None:
    holder: List[Any] = []

    @pn.component
    def Bar() -> pn.Node:
        width = pn.use_shared_value(10.0)
        holder.append(width)
        style = pn.use_animated_style(lambda: {"width": width.value})
        return pn.Row(pn.View(style=[{"height": 10, "background_color": "#FF000000"}, style], test_id="bar"))

    tree = render(Bar())
    holder[-1].value = 80.0
    tree.settle()
    tree.backend.native.drain()
    assert tree.presented_frame(tree.get_by_test_id("bar"))[2] == 80.0


def test_worklet_errors_reach_the_error_handler(pn_clock: FakeClock) -> None:
    reported: List[Any] = []
    pn.set_error_handler(lambda error, phase: reported.append((type(error).__name__, phase, str(error))))
    try:

        @pn.component
        def Broken() -> pn.Node:
            value = pn.use_shared_value(0.0)
            style = pn.use_animated_style(lambda: {"opacity": 1 / value.value})
            return pn.View(style=[style])

        render(Broken())
        assert reported and reported[0][:2] == ("WorkletError", "worklet")
        assert "ZeroDivisionError" in reported[0][2]
    finally:
        pn.set_error_handler(None)


def test_shared_values_and_bindings_are_released_on_unmount(pn_clock: FakeClock) -> None:
    from pythonnative.motion.runtime import runtime

    @pn.component
    def Box() -> pn.Node:
        value = pn.use_shared_value(0.0)
        style = pn.use_animated_style(lambda: {"opacity": value.value})
        return pn.View(style=[style])

    tree = render(Box())
    target = runtime.target(tree.backend)
    assert target is not None and target.shared and target.bindings
    tree.unmount()
    assert not target.shared and not target.bindings


# ----------------------------------------------------------------------
# Layout animations
# ----------------------------------------------------------------------


def test_entering_exiting_and_layout_presets(pn_clock: FakeClock) -> None:
    @pn.component
    def Items(names: List[str]) -> pn.Node:
        return pn.Column(
            *(
                pn.View(
                    pn.Text(name),
                    style={"height": 20, "opacity": 1},
                    entering=FadeIn(duration=100),
                    exiting=FadeOut(duration=100),
                    layout=LinearTransition(duration=100),
                    test_id=name,
                ).with_key(name)
                for name in names
            )
        )

    tree = render(Items(["a"]))
    tree.rerender(Items(["b", "a"]))
    b = tree.get_by_test_id("b")
    assert tree.presented_style(b)["opacity"] == 0.0  # entering starts transparent
    a_tag = tree.get_by_test_id("a").tag
    settle_animations(tree, pn_clock)
    assert tree.presented_style(b)["opacity"] == 1
    assert tree.presented_frame(a_tag)[1] == 20  # moved down by the new row

    tree.rerender(Items(["a"]))
    assert tree.query_by_test_id("b") is None  # the component unmounted at once
    assert b.tag in tree.backend.native.views  # but the native view is still animating out
    settle_animations(tree, pn_clock)
    assert b.tag not in tree.backend.native.views
    assert tree.presented_frame(a_tag)[1] == 0


def test_a_commit_during_a_delayed_entering_keeps_its_first_frame(pn_clock: FakeClock) -> None:
    """A re-render that sets a key the entering animation holds puts the held value back."""

    @pn.component
    def Items(names: List[str], opacity: float) -> pn.Node:
        return pn.Column(
            *(
                pn.View(
                    style={"height": 20, "opacity": opacity},
                    entering=FadeIn(duration=200, delay=500),
                    test_id=name,
                ).with_key(name)
                for name in names
            )
        )

    tree = render(Items(["a"], 1.0))
    tree.rerender(Items(["a", "b"], 1.0))
    b = tree.get_by_test_id("b").tag
    pn_clock.advance(0.1)
    tree.settle()
    before = len(tree.backend.animated)
    # On a device the commit sets the view's opacity to 0.9 directly, so the
    # core has to send the held 0 again rather than wait for the delay to end.
    tree.rerender(Items(["a", "b"], 0.9))
    assert (b, "opacity", 0.0) in tree.backend.animated[before:]
    settle_animations(tree, pn_clock)
    assert tree.presented_style(b)["opacity"] == 0.9


def test_keyframes_and_slide_presets(pn_clock: FakeClock) -> None:
    pop = Keyframes(
        {0.0: {"opacity": 0, "transform": [{"scale": 0.5}]}, 1.0: {"opacity": 1, "transform": [{"scale": 1}]}}
    )

    @pn.component
    def Card(show: bool) -> pn.Node:
        return pn.Column(
            pn.View(style={"height": 10}, entering=pop, test_id="pop") if show else None,
            pn.View(style={"height": 10}, entering=SlideIn(edge="bottom"), test_id="slide") if show else None,
        )

    tree = render(Card(False))
    tree.rerender(Card(True))
    assert tree.presented_style(tree.get_by_test_id("pop"))["transform"] == [{"scale": 0.5}]
    slide = tree.presented_style(tree.get_by_test_id("slide"))["transform"][0]
    assert slide["translate_y"] > 0
    settle_animations(tree, pn_clock)
    # Keyframed keys go back to the view's own style (it has no opacity) when done.
    assert "opacity" not in tree.presented_style(tree.get_by_test_id("pop"))


def test_custom_layout_animations_are_worklets(pn_clock: FakeClock) -> None:
    @pn.worklet
    def grow(values: Any) -> Any:
        return {"initial": {"opacity": 0}, "animate": {"opacity": pn.with_timing(1, duration=50)}}

    @pn.component
    def Box(show: bool) -> pn.Node:
        return pn.Column(pn.View(style={"height": 10}, entering=grow, test_id="box") if show else None)

    tree = render(Box(False))
    tree.rerender(Box(True))
    assert tree.presented_style(tree.get_by_test_id("box"))["opacity"] == 0
    settle_animations(tree, pn_clock)
    assert tree.presented_style(tree.get_by_test_id("box")).get("opacity") in (None, 1)


def test_layout_animation_config_skips_entering_on_mount(pn_clock: FakeClock) -> None:
    @pn.component
    def Screen() -> pn.Node:
        return LayoutAnimationConfig(pn.View(style={"height": 5}, entering=FadeIn(), test_id="row"), skip_entering=True)

    tree = render(pn.Column())
    tree.rerender(pn.Column(Screen()))
    assert "opacity" not in tree.presented_style(tree.get_by_test_id("row"))


def test_list_item_animations_cross_as_presets() -> None:
    tree = render(
        pn.FlatList(
            data=["a"],
            render_item=lambda item, index: pn.Text(item),
            key_extractor=lambda item, index: item,
            item_entering=FadeIn(duration=120),
            item_layout=LinearTransition(),
        )
    )
    native = tree.backend.native.find("VirtualList")[0]
    assert native.props["item_entering"]["type"] == "fade_in" and native.props["item_entering"]["duration"] == 120
    assert native.props["item_layout"]["type"] == "linear"
    with pytest.raises(TypeError, match="motion preset"):
        render(
            pn.FlatList(data=[], render_item=lambda item, index: pn.Text(item), item_entering=Keyframes({0: {}, 1: {}}))
        )


# ----------------------------------------------------------------------
# Components built on Motion
# ----------------------------------------------------------------------


def test_bottom_sheet_snaps_by_position_and_velocity(pn_clock: FakeClock) -> None:
    changes: List[int] = []
    closed: List[bool] = []
    sheet = pn.Ref[Any](None)

    tree = render(
        pn.View(
            pn.BottomSheet(
                pn.Text("filters"),
                snap_points=(200, 400),
                on_change=changes.append,
                on_close=lambda: closed.append(True),
                ref=sheet,
            )
        )
    )
    handle = tree.get_by_role("adjustable")
    surface = handle.parent
    assert surface is not None
    assert tree.presented_style(surface)["transform"] == [{"translate_y": 200.0}]
    tree.drag(handle, dy=-150, duration=0.3)
    assert changes == []  # reported once it settles, not at release
    settle_animations(tree, pn_clock)
    assert changes == [1] and tree.presented_style(surface)["transform"] == [{"translate_y": 0}]
    tree.drag(handle, dy=500, duration=0.1)
    assert closed == []
    settle_animations(tree, pn_clock)
    assert closed == [True]
    tree.act(lambda: sheet.current.snap_to(0))
    settle_animations(tree, pn_clock)
    assert tree.presented_style(surface)["transform"] == [{"translate_y": 200}]


def test_swipeable_opens_past_its_threshold_and_closes(pn_clock: FakeClock) -> None:
    events: List[str] = []
    tree = render(
        pn.View(
            pn.Swipeable(
                pn.Text("row", style={"height": 40}),
                right_actions=pn.Text("delete"),
                on_open=events.append,
                on_close=lambda: events.append("closed"),
            ),
            style={"width": 300},
        )
    )
    row = tree.get_by_text("row").parent
    assert row is not None
    tree.drag(row, dx=-20, duration=0.5)  # slow and short: springs back
    settle_animations(tree, pn_clock)
    assert events == []  # it was closed and stayed closed
    tree.drag(row, dx=-70, duration=0.2)
    assert events == []  # reported once it settles, not at release
    settle_animations(tree, pn_clock)
    assert events == ["right"]
    assert tree.presented_style(row)["transform"] == [{"translate_x": -80.0}]
    tree.drag(row, dx=70, duration=0.2)
    settle_animations(tree, pn_clock)
    assert events == ["right", "closed"]


def test_drawer_opens_with_an_edge_swipe(pn_clock: FakeClock) -> None:
    @pn.component
    def Feed() -> pn.Node:
        return pn.Text("feed")

    @pn.component
    def Settings() -> pn.Node:
        return pn.Text("settings")

    Drawer = pn.DrawerNavigator(pn.Screen(Feed, title="Feed"), pn.Screen(Settings, title="Settings"), drawer_width=200)
    tree = render(pn.NavigationContainer(Drawer))
    edges = [view for view in tree.views() if view.props.get("width") == 24 and view.props.get("gestures")]
    assert edges
    tree.drag(edges[0], dx=150, duration=0.2)
    settle_animations(tree, pn_clock)
    label = tree.get_by_text("Settings").parent
    panel = label.parent if label is not None else None
    assert panel is not None
    assert tree.presented_style(panel)["transform"] == [{"translate_x": 0.0}]


def test_run_on_python_calls_in_flight_survive_a_rerender(pn_clock: FakeClock) -> None:
    """A row re-rendered while its worklet's call is queued still delivers the call."""
    from pythonnative.motion.runtime import runtime

    seen: List[str] = []

    @pn.component
    def Row(label: str) -> pn.Node:
        def opened(side: str) -> None:
            seen.append(f"{label}:{side}")

        @pn.worklet
        def release(event: gestures.GestureEvent) -> None:
            pn.run_on_python(opened, "right")

        return pn.View(style={"width": 100, "height": 40}, gestures=[gestures.Pan(on_end=release)], test_id="row")

    tree = render(Row("a"))
    row = tree.get_by_test_id("row")
    native = tree.backend.native
    # The UI thread sends the call, but Python re-renders before handling it.
    messages: List[Any] = []
    original = native.callback
    assert original is not None
    native.callback = lambda *message: messages.append(message)
    tree.drag(row, dx=40)
    native.callback = original
    tree.rerender(Row("b"))
    for message in messages:
        original(*message)
    tree.settle()
    assert seen == ["a:right"]
    assert runtime is not None


def test_unmounted_bindings_release_their_callback_slots(pn_clock: FakeClock) -> None:
    """Rows that mount and unmount don't leave callback ids behind."""
    from pythonnative.motion.runtime import runtime

    @pn.component
    def Row() -> pn.Node:
        level = pn.use_shared_value(0.0)

        def crossed(high: bool) -> None:
            pass

        pn.use_animated_reaction(lambda: level.value > 1, lambda high, _before: pn.run_on_python(crossed, high))
        return pn.View()

    @pn.component
    def Rows(count: int) -> pn.Node:
        return pn.View(*[Row().with_key(str(i)) for i in range(count)])

    before = len(runtime._callback_slots)
    tree = render(Rows(5))
    assert len(runtime._callback_slots) == before + 5
    for count in (0, 5, 0, 5, 0):
        tree.rerender(Rows(count))
        tree.settle()
    assert len(runtime._callback_slots) == before


def test_handles_report_like_drags_do(pn_clock: FakeClock) -> None:
    changes: List[int] = []
    sides: List[str] = []
    sheet = pn.Ref[Any](None)
    row = pn.Ref[Any](None)
    tree = render(
        pn.View(
            pn.BottomSheet(pn.Text("filters"), snap_points=(200, 400), index=-1, on_change=changes.append, ref=sheet),
            pn.Swipeable(
                pn.Text("row"),
                right_actions=pn.Text("delete"),
                on_open=sides.append,
                on_close=lambda: sides.append("closed"),
                ref=row,
            ),
        )
    )
    tree.act(lambda: sheet.current.expand())
    tree.act(lambda: row.current.open_right())
    settle_animations(tree, pn_clock)
    tree.act(lambda: row.current.close())
    settle_animations(tree, pn_clock)
    assert changes == [1] and sides == ["right", "closed"]


def test_bottom_sheet_follows_a_window_that_changes_size(pn_clock: FakeClock) -> None:
    from pythonnative.platform_metrics import WindowDimensions

    @pn.component
    def App(height: float) -> pn.Node:
        return pn.View(pn.BottomSheet(pn.Text("x"), snap_points=(200, "50%"), index=0))

    import pythonnative.components.bottom_sheet as sheet_module

    sizes = [WindowDimensions(width=390, height=600, scale=3, font_scale=1)]
    original = sheet_module.use_window_dimensions

    sheet_module.use_window_dimensions = lambda: sizes[-1]
    try:
        tree = render(App(600))
        surface = tree.get_by_role("adjustable").parent
        assert surface is not None
        sizes.append(WindowDimensions(width=390, height=800, scale=3, font_scale=1))
        tree.rerender(App(800))
        settle_animations(tree, pn_clock)
        assert tree.presented_style(surface)["height"] == 400
        # 50% of 800 is the tallest detent now, so the 200pt detent sits 200pt down.
        assert tree.presented_style(surface)["transform"] == [{"translate_y": 200.0}]
    finally:
        sheet_module.use_window_dimensions = original


def test_a_short_slow_drag_below_the_lowest_detent_closes_the_sheet(pn_clock: FakeClock) -> None:
    """Closing is decided at the sheet's visual bottom, not the lower spot it parks at."""
    closed: List[bool] = []
    tree = render(
        pn.View(
            pn.BottomSheet(pn.Text("x"), snap_points=(200, 400), index=0, on_close=lambda: closed.append(True)),
            style={"height": 800},
        )
    )
    handle = tree.get_by_role("adjustable")
    # From 200pt below fully open, 120pt more puts the sheet past halfway to
    # its bottom edge (400pt), so it closes.
    tree.drag(handle, dy=120, duration=2.0)
    settle_animations(tree, pn_clock)
    assert closed == [True]
