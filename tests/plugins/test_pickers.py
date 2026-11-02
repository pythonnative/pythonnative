"""``pythonnative.pickers``: the facade, the fallback, the contract, and the plugin manifest."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, List

import pytest

import pythonnative.pickers as pickers
from pythonnative.native_modules.registry import native_module
from pythonnative.pickers import PickedFile, pick_documents, pick_images, pick_videos
from pythonnative.project.plugins import load_plugin
from pythonnative.sdk import schema

NATIVE = Path(pickers.__file__).parent / "native"


def _record(monkeypatch: pytest.MonkeyPatch, answer: Any = ()) -> List[Any]:
    module = native_module("Pickers")
    seen: List[Any] = []

    async def call_async(method: str, **kwargs: Any) -> Any:
        seen.append((method, kwargs))
        return list(answer)

    monkeypatch.setattr(module, "call_async", call_async)
    monkeypatch.setattr(pickers, "native_module", lambda name: module)
    return seen


def test_every_picker_looks_canceled_off_device() -> None:
    assert asyncio.run(pick_images()) == []
    assert asyncio.run(pick_videos()) == []
    assert asyncio.run(pick_documents()) == []


def test_arguments_reach_the_module(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record(monkeypatch)
    asyncio.run(pick_images(3, 0.5))
    asyncio.run(pick_videos(limit=0))
    asyncio.run(pick_documents(types=("application/pdf", "image/*"), multiple=True))
    assert seen == [
        ("pick_images", {"limit": 3, "quality": 0.5}),
        ("pick_videos", {"limit": 0}),
        ("pick_documents", {"types": ["application/pdf", "image/*"], "multiple": True}),
    ]


def test_defaults_choose_one_item_and_any_document(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _record(monkeypatch)
    asyncio.run(pick_images())
    asyncio.run(pick_documents())
    assert seen == [
        ("pick_images", {"limit": 1, "quality": 0.9}),
        ("pick_documents", {"types": None, "multiple": False}),
    ]


def test_results_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    chosen = PickedFile(path="/cache/a.jpg", name="a.jpg", mime_type="image/jpeg", size=12)
    _record(monkeypatch, [chosen])
    assert asyncio.run(pick_images()) == [chosen]


@pytest.mark.parametrize("call", [lambda: pick_images(limit=-1), lambda: pick_videos(limit=-1)])
def test_a_negative_limit_is_rejected(call: Any) -> None:
    with pytest.raises(ValueError, match="limit"):
        asyncio.run(call())


def test_quality_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="quality"):
        asyncio.run(pick_images(quality=2))


def test_a_lone_mime_type_string_is_rejected() -> None:
    # It would otherwise be split into one "type" per character.
    with pytest.raises(TypeError, match="types"):
        asyncio.run(pick_documents(types="application/pdf"))


def test_picked_file_is_a_frozen_record() -> None:
    chosen = PickedFile(path="/a", name="a", mime_type="text/plain", size=1)
    with pytest.raises(AttributeError):
        chosen.size = 2  # type: ignore[misc]


def test_contract_declares_only_the_module() -> None:
    document = json.loads((NATIVE / "schema.json").read_text())
    assert set(document["modules"]) == {"Pickers"}
    assert document["components"] == {}
    methods = document["modules"]["Pickers"]["methods"]
    assert set(methods) == {"pick_images", "pick_videos", "pick_documents"}
    assert all(method["async"] for method in methods.values())


def test_module_is_declared_in_the_live_schema() -> None:
    assert schema.MODULES["Pickers"].methods["pick_documents"]["defaults"] == {"types": None, "multiple": False}


def test_plugin_loads_and_needs_no_permission() -> None:
    plugin = load_plugin(NATIVE)
    assert plugin.name == "pickers"
    assert plugin.requires_permissions == ()
    assert plugin.ios_entry == "PickersPlugin"
    assert plugin.android_entry == "com.pythonnative.plugins.pickers.PickersPlugin"
    assert plugin.web_entry == "web/index.js"
    assert plugin.maven_dependencies == ()
