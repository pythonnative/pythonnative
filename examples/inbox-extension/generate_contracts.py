"""Regenerate the extension manifest from its public Python definitions."""

import json
from pathlib import Path

import inbox_extension  # noqa: F401

from pythonnative.sdk.schema import manifest

spec = manifest()
spec["components"] = {"InboxBadge": spec["components"]["InboxBadge"]}
spec["modules"] = {"InboxTools": spec["modules"]["InboxTools"]}
Path(__file__).with_name("src").joinpath("inbox_extension/native/schema.json").write_text(
    json.dumps(spec, indent=2) + "\n"
)
