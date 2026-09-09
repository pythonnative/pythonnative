"""Portable schemas agree with the fixtures consumed by every renderer."""

import json
from pathlib import Path
from typing import Any

import pytest

from pythonnative.sdk.schema import validate


@pytest.mark.parametrize(
    "case", json.loads((Path(__file__).parent / "contracts/validation.json").read_text()), ids=lambda case: case["name"]
)
def test_portable_fixture(case: dict[str, Any]) -> None:
    if case["valid"]:
        validate(case["value"], case["schema"])
    else:
        with pytest.raises(TypeError):
            validate(case["value"], case["schema"])


def test_bundled_ios_fixtures_match_shared_source() -> None:
    root = Path(__file__).parents[1]
    assert (root / "tests/contracts/validation.json").read_bytes() == (
        root / "src/pythonnative/native/ios/Tests/PythonNativeKitTests/Fixtures/validation.json"
    ).read_bytes()
