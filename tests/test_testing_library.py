"""Tests for ``pythonnative.testing``: queries, wait_for, within, press, FakeClock, commands, and the plugin."""

from __future__ import annotations

import asyncio
import re
import time

import pytest

import pythonnative as pn
from pythonnative import runtime
from pythonnative.testing import (
    IMPLICIT_ROLES,
    FakeBackend,
    FakeClock,
    FakeView,
    Scope,
    current_fake_clock,
    fake_clock,
    render,
    wait_for,
    within,
)

# ----------------------------------------------------------------------
# FakeView content properties
# ----------------------------------------------------------------------


def test_fake_view_text_excludes_placeholder_and_value() -> None:
    result = render(
        pn.Column(
            pn.Text("Label"),
            pn.Button("Go"),
            pn.TextInput(value="typed", placeholder="Email"),
        )
    )
    field = result.get_by_type("TextInput")
    assert field.text is None
    assert field.value == "typed"
    assert field.placeholder == "Email"
    assert result.text() == ["Label", "Go"]
    assert result.query_by_text("typed") is None
    assert result.query_by_text("Email") is None
    assert "value='typed'" in repr(field)


def test_fake_view_role_and_accessible_name() -> None:
    result = render(
        pn.Column(
            pn.Button("Save", test_id="save"),
            pn.Switch(accessibility_label="Wifi"),
            pn.Checkbox(label="Agree", test_id="agree"),
            pn.TextInput(placeholder="Name", test_id="name"),
            pn.Image("x.png", test_id="pic"),
            pn.Text("Title", accessibility_role="header"),
            pn.Pressable(pn.Text("Open"), pn.Text("now"), test_id="open"),
            pn.Text("plain"),
        )
    )
    assert result.get_by_test_id("save").role == "button"
    assert result.get_by_test_id("save").accessible_name == "Save"
    switch = result.get_by_type("Switch")
    assert switch.role == "switch" and switch.accessible_name == "Wifi"
    assert result.get_by_test_id("agree").role == "checkbox"
    assert result.get_by_test_id("agree").accessible_name == "Agree"
    assert result.get_by_test_id("name").role == "textbox"
    assert result.get_by_test_id("pic").role == "image"
    assert result.get_by_text("Title").role == "header"
    pressable = result.get_by_test_id("open")
    assert pressable.role == "button"
    assert pressable.accessible_name == "Open now"
    assert result.get_by_text("plain").role is None
    for type_name in ("Button", "Pressable", "Switch", "Checkbox", "TextInput", "Image"):
        assert type_name in IMPLICIT_ROLES


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------


@pn.component
def Form() -> pn.Element:
    email, set_email = pn.use_state("")
    return pn.Column(
        pn.Text("Sign up", accessibility_role="header"),
        pn.TextInput(value=email, placeholder="Email", on_change=set_email, test_id="email"),
        pn.TextInput(value="fixed", placeholder="Code"),
        pn.Button("Save", on_press=lambda: None),
        pn.Button("Cancel", on_press=lambda: None, accessibility_label="Dismiss"),
        pn.Switch(accessibility_label="Remember me"),
        pn.Column(
            pn.Text("Summary"),
            pn.TextInput(value=email, placeholder="Copy"),
            test_id="summary",
        ),
    )


def test_get_by_role_matches_explicit_and_implicit_roles() -> None:
    result = render(Form())
    assert result.get_by_role("header").text == "Sign up"
    assert result.get_by_role("switch").label == "Remember me"
    assert len(result.get_all_by_role("button")) == 2
    assert len(result.get_all_by_role("textbox")) == 3
    with pytest.raises(LookupError, match="get_by_role"):
        result.get_by_role("button")
    assert result.query_by_role("slider") is None


def test_get_by_role_name_matches_label_then_text() -> None:
    result = render(Form())
    assert result.get_by_role("button", name="Save").props["title"] == "Save"
    assert result.get_by_role("button", name="Dismiss").props["title"] == "Cancel"
    assert result.query_by_role("button", name="Cancel") is None, "the label replaces the title as the name"
    assert result.get_by_role("button", name=re.compile("^Sa")).props["title"] == "Save"
    assert result.get_by_role("button", name="av", exact=False).props["title"] == "Save"
    assert result.get_by_role("switch", name=lambda n: n is not None and n.startswith("Remember"))
    with pytest.raises(LookupError, match=r"name='Nope'"):
        result.get_by_role("button", name="Nope")


def test_placeholder_and_display_value_queries() -> None:
    result = render(Form())
    assert result.get_by_placeholder_text("Email").test_id == "email"
    assert result.get_by_placeholder_text("mail", exact=False).test_id == "email"
    assert result.query_by_placeholder_text("Phone") is None
    assert len(result.get_all_by_placeholder_text(re.compile("^C"))) == 2
    assert result.get_by_display_value("fixed").placeholder == "Code"
    assert len(result.get_all_by_display_value("")) == 2
    result.change_text(result.get_by_placeholder_text("Email"), "a@b.c")
    assert len(result.get_all_by_display_value("a@b.c")) == 2
    assert len(result.get_all_by_display_value("a@b", exact=False)) == 2
    with pytest.raises(LookupError, match="get_by_display_value"):
        result.get_by_display_value("a@b.c")
    assert result.query_by_display_value("zzz") is None


def test_hidden_subtrees_are_skipped_unless_requested() -> None:
    result = render(
        pn.Column(
            pn.Button("Visible", on_press=lambda: None),
            pn.Column(pn.Button("Hidden", on_press=lambda: None), style={"display": "none"}),
        )
    )
    assert len(result.get_all_by_role("button")) == 1
    assert len(result.get_all_by_role("button", hidden=True)) == 2
    assert result.query_by_role("button", name="Hidden") is None
    assert result.get_by_role("button", name="Hidden", hidden=True)


# ----------------------------------------------------------------------
# within
# ----------------------------------------------------------------------


def test_within_scopes_every_query_to_the_subtree() -> None:
    result = render(Form())
    result.change_text(result.get_by_test_id("email"), "a@b.c")
    card = within(result.get_by_test_id("summary"))
    assert isinstance(card, Scope)
    assert card.get_by_text("Summary")
    assert card.get_by_display_value("a@b.c").placeholder == "Copy"
    assert card.get_by_placeholder_text("Copy")
    assert card.get_by_role("textbox")
    assert card.query_by_text("Sign up") is None
    assert card.query_by_role("button") is None
    assert card.get_all_by_type("Text") == [card.get_by_text("Summary")]
    assert card.text() == ["Summary"]
    assert card.get_by_test_id("summary") is card.view, "the scope root is a candidate"
    with pytest.raises(LookupError) as info:
        card.get_by_text("Sign up")
    assert "Summary" in str(info.value) and "Sign up" not in str(info.value).split("\n\n", 1)[1]
    assert result.within(result.get_by_test_id("summary")).view is card.view
    assert card.find_by_text("Summary", timeout=0.1)


# ----------------------------------------------------------------------
# wait_for and find_by_*
# ----------------------------------------------------------------------


@pn.component
def Loader() -> pn.Element:
    ready, set_ready = pn.use_state(False)

    async def load() -> None:
        await asyncio.sleep(0.02)
        set_ready(True)

    pn.use_effect(load, [])
    return pn.Column(
        pn.Text("Loaded" if ready else "Loading"),
        pn.TextInput(value="v" if ready else "", placeholder="P"),
    )


def test_wait_for_returns_the_predicates_truthy_value() -> None:
    result = render(Loader(), settle_first=False)
    view = wait_for(lambda: result.query_by_text("Loaded"))
    assert isinstance(view, FakeView) and view.text == "Loaded"
    assert wait_for(lambda: 42) == 42


def test_wait_for_tolerates_lookup_errors_until_they_stop() -> None:
    result = render(Loader(), settle_first=False)
    assert wait_for(lambda: result.get_by_text("Loaded")).text == "Loaded"


def test_wait_for_times_out_with_tree_dump() -> None:
    result = render(pn.Text("only"))
    started = time.monotonic()
    with pytest.raises(TimeoutError) as info:
        wait_for(lambda: result.query_by_text("never"), timeout=0.05, interval=0.005)
    assert time.monotonic() - started < 1.0
    assert "'only'" in str(info.value)
    with pytest.raises(TimeoutError, match="get_by_text"):
        wait_for(lambda: result.get_by_text("never"), timeout=0.02)


def test_wait_for_propagates_unexpected_exceptions() -> None:
    with pytest.raises(ZeroDivisionError):
        wait_for(lambda: 1 // 0, timeout=0.1)


def test_find_by_variants_wait_for_async_content() -> None:
    result = render(Loader(), settle_first=False)
    assert result.find_by_text("Loaded").text == "Loaded"
    result = render(Loader(), settle_first=False)
    assert result.find_by_display_value("v").placeholder == "P"
    assert result.find_by_placeholder_text("P")
    assert result.find_by_role("textbox")
    assert result.find_by_type("Text")
    with pytest.raises(TimeoutError):
        result.find_by_test_id("missing", timeout=0.02)
    with pytest.raises(TimeoutError):
        result.find_by_label("missing", timeout=0.02)


# ----------------------------------------------------------------------
# press and disabled targets
# ----------------------------------------------------------------------


def test_press_refuses_disabled_targets_unless_forced() -> None:
    presses: list[str] = []
    result = render(
        pn.Column(
            pn.Button("Off", on_press=lambda: presses.append("button"), disabled=True),
            pn.Pressable(
                pn.Text("Inner", test_id="inner"),
                on_press=lambda: presses.append("pressable"),
                accessibility_state={"disabled": True},
            ),
            # A raw element: the Pressable factory's ``disabled`` keyword is not what this test is about.
            pn.Element(
                "Pressable",
                {"disabled": True, "test_id": "deep", "on_press": lambda: presses.append("deep")},
                [pn.Text("Deep")],
            ),
            pn.Button("On", on_press=lambda: presses.append("on")),
        )
    )
    with pytest.raises(AssertionError, match="is disabled"):
        result.press(result.get_by_text("Off"))
    with pytest.raises(AssertionError, match="is disabled"):
        result.press(result.get_by_test_id("deep"))
    assert presses == []
    result.press(result.get_by_text("Off"), force=True)
    assert presses == ["button"]
    result.press(result.get_by_text("On"))
    assert presses == ["button", "on"]
    inner = result.get_by_test_id("inner")
    assert inner.parent is not None and inner.parent.disabled
    with pytest.raises(AssertionError, match="inside disabled"):
        result.press(inner)
    with pytest.raises(AssertionError, match="is disabled"):
        result.press(inner.parent.tag)
    assert presses == ["button", "on"]


def test_act_settles_state_updates() -> None:
    setters: list = []

    @pn.component
    def Counter() -> pn.Element:
        count, set_count = pn.use_state(0)
        setters.append(set_count)
        return pn.Text(f"Count: {count}")

    result = render(Counter())

    def bump_twice() -> None:
        setters[-1](lambda c: c + 1)
        setters[-1](lambda c: c + 1)

    result.act(bump_twice)
    assert result.get_by_text("Count: 2")


# ----------------------------------------------------------------------
# FakeClock
# ----------------------------------------------------------------------


def test_fake_clock_drives_asyncio_sleep_without_waiting(pn_clock: FakeClock) -> None:
    done: list[str] = []

    @pn.component
    def Delayed() -> pn.Element:
        saved, set_saved = pn.use_state(False)

        async def effect() -> None:
            await asyncio.sleep(2.5)
            done.append("slept")
            set_saved(True)

        pn.use_effect(effect, [])
        return pn.Text("Saved" if saved else "Saving")

    started = time.monotonic()
    result = render(Delayed())
    assert result.get_by_text("Saving")
    pn_clock.advance(1.0)
    assert done == [] and result.query_by_text("Saved") is None
    pn_clock.advance(1.5)
    assert done == ["slept"]
    assert result.get_by_text("Saved")
    assert time.monotonic() - started < 1.0


def test_fake_clock_fires_repeating_timers_in_order(pn_clock: FakeClock) -> None:
    ticks: list[float] = []
    loop = runtime.get_loop()
    start = pn_clock.now

    def tick() -> None:
        ticks.append(round(pn_clock.now - start, 1))
        if len(ticks) < 5:
            loop.call_later(1.0, tick)

    loop.call_later(1.0, tick)
    pn_clock.advance(3.5)
    assert ticks == [1.0, 2.0, 3.0]
    assert pn_clock.now - start >= 3.5
    pn_clock.advance(10.0)
    assert ticks == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_fake_clock_drains_tasks_woken_by_timers(pn_clock: FakeClock) -> None:
    order: list[str] = []

    async def worker() -> None:
        order.append("start")
        await asyncio.sleep(1.0)
        order.append("one")
        await asyncio.sleep(0)
        order.append("two")
        await asyncio.sleep(1.0)
        order.append("three")

    runtime.run_async(worker())
    pn_clock.run_until_idle()
    assert order == ["start"]
    pn_clock.advance(1.0)
    assert order == ["start", "one", "two"]
    pn_clock.advance(1.0)
    assert order == ["start", "one", "two", "three"]


def test_fake_clock_context_manager_installs_and_restores() -> None:
    loop = runtime.get_loop()
    real_time = loop.time
    assert current_fake_clock() is None
    with fake_clock() as clock:
        assert current_fake_clock() is clock
        assert clock.loop is loop
        before = clock.now
        clock.advance(100.0)
        assert clock.now - before >= 100.0
        assert clock.offset == pytest.approx(100.0, abs=0.5)
        assert loop.time() >= real_time() + 99.0
        with pytest.raises(ValueError):
            clock.advance(-1.0)
        with pytest.raises(RuntimeError):
            with fake_clock():
                pass
    assert current_fake_clock() is None
    assert loop.time() < real_time() + 1.0


def test_settle_under_fake_clock_does_not_wait_for_long_timers(pn_clock: FakeClock) -> None:
    @pn.component
    def Slow() -> pn.Element:
        async def effect() -> None:
            await asyncio.sleep(60.0)

        pn.use_effect(effect, [])
        return pn.Text("hi")

    started = time.monotonic()
    result = render(Slow())
    result.settle()
    assert time.monotonic() - started < 0.5, "render and settle return without waiting on the 60s timer"


# ----------------------------------------------------------------------
# FakeBackend.command
# ----------------------------------------------------------------------


def test_text_input_commands() -> None:
    focus: list[str] = []
    result = render(
        pn.Column(
            pn.TextInput(
                value="hello",
                test_id="a",
                on_focus=lambda: focus.append("focus a"),
                on_blur=lambda: focus.append("blur a"),
            ),
            pn.TextInput(value="", test_id="b"),
        )
    )
    backend = result.backend
    a, b = result.get_by_test_id("a"), result.get_by_test_id("b")
    assert backend.command(a.tag, "get_value", {}) == "hello"
    assert backend.command(a.tag, "focus", {}) is None
    assert backend.focused_tag == a.tag and focus == ["focus a"]
    backend.command(a.tag, "focus", {})
    assert focus == ["focus a"], "refocusing does not fire again"
    backend.command(a.tag, "select_all", {})
    assert backend.selections[a.tag] == (0, 5)
    backend.command(a.tag, "set_selection", {"start": 1, "end": 3})
    assert backend.selections[a.tag] == (1, 3)
    backend.command(b.tag, "focus", {})
    assert backend.focused_tag == b.tag and focus == ["focus a", "blur a"]
    backend.command(b.tag, "blur", {})
    assert backend.focused_tag is None
    backend.command(a.tag, "clear", {})
    assert backend.command(a.tag, "get_value", {}) == "" and a.value == ""
    assert backend.commands[0] == (a.tag, "get_value", {})
    assert backend.command(a.tag, "unknown", None) is None
    assert backend.command(999, "get_value", {}) is None


def test_scroll_view_commands_track_an_offset_per_view() -> None:
    # Raw elements keep this independent of the ScrollView factory's axis keyword.
    vertical = pn.Element("ScrollView", {"height": 500}, [pn.Element("View", {"height": 2000}, [])])
    horizontal = pn.Element(
        "ScrollView", {"horizontal": True, "width": 300}, [pn.Element("View", {"width": 1000, "height": 50}, [])]
    )
    result = render(pn.Column(vertical, horizontal))
    backend = result.backend
    v, h = result.get_all_by_type("ScrollView")
    assert backend.command(v.tag, "get_scroll_offset", {}) == {"x": 0.0, "y": 0.0}
    backend.command(v.tag, "scroll_to_offset", {"x": 0, "y": 120, "animated": False})
    assert backend.command(v.tag, "get_scroll_offset", {}) == {"x": 0.0, "y": 120.0}
    assert backend.command(h.tag, "get_scroll_offset", {}) == {"x": 0.0, "y": 0.0}
    backend.command(v.tag, "scroll_to_end", {})
    assert backend.command(v.tag, "get_scroll_offset", {}) == {"x": 0.0, "y": 1500.0}
    backend.command(h.tag, "scroll_to_end", {})
    assert backend.command(h.tag, "get_scroll_offset", {})["x"] == 700.0
    backend.command(v.tag, "scroll_to_top", {})
    assert backend.scroll_offsets[v.tag] == {"x": 0.0, "y": 0.0}


def test_web_view_commands_return_stubs() -> None:
    result = render(pn.WebView(url="https://example.com"))
    backend = result.backend
    web = result.get_by_type("WebView")
    assert backend.command(web.tag, "can_go_back", {}) is False
    assert backend.command(web.tag, "can_go_forward", {}) is False
    assert backend.command(web.tag, "get_url", {}) == "https://example.com"
    assert backend.command(web.tag, "get_title", {}) is None
    assert backend.command(web.tag, "reload", {}) is None
    backend.command(web.tag, "load_url", {"url": "https://example.org"})
    assert backend.command(web.tag, "get_url", {}) == "https://example.org"


def test_command_signature_is_tag_name_args() -> None:
    backend = FakeBackend()
    assert backend.command(1, "anything", {"x": 1}) is None
    assert backend.commands == [(1, "anything", {"x": 1})]


# ----------------------------------------------------------------------
# pytest plugin
# ----------------------------------------------------------------------


def test_plugin_is_registered_through_the_entry_point(request: pytest.FixtureRequest) -> None:
    manager = request.config.pluginmanager
    assert manager.hasplugin("pythonnative")
    plugin = manager.getplugin("pythonnative")
    assert plugin.__name__ == "pythonnative.testing.pytest_plugin"


def test_plugin_resets_the_runtime_between_tests_part_one() -> None:
    loop = runtime.get_loop()
    runtime.run_async(asyncio.sleep(1000))
    loop_holder.append(loop)


loop_holder: list = []


def test_plugin_resets_the_runtime_between_tests_part_two() -> None:
    assert loop_holder, "runs after part one"
    old = loop_holder[0]
    assert old.is_closed()
    assert runtime.get_loop() is not old
