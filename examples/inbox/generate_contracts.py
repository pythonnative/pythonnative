"""Regenerate the plugin manifest after editing app/native_contracts.py."""

import json
from pathlib import Path

from app import native_contracts  # noqa: F401

from pythonnative.sdk.schema import manifest

contracts = manifest()
contracts["components"] = {"InboxBadge": contracts["components"]["InboxBadge"]}
contracts["modules"] = {"InboxTools": contracts["modules"]["InboxTools"]}
Path(__file__).with_name("native").joinpath("schema.json").write_text(
    json.dumps(contracts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
