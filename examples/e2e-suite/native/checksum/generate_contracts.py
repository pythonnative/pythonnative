"""Regenerate ``schema.json`` from the contract in the demo screen. Run from this directory."""

import json
from pathlib import Path
from typing import Protocol

from pythonnative.sdk.schema import MODULES, ModuleSchema, manifest, register_schema


class ChecksumService(Protocol):
    def adler32(self, text: str) -> int: ...

    def configured_value(self) -> str: ...


known = set(MODULES)
register_schema(ModuleSchema.from_protocol("Checksum", ChecksumService))
document = manifest()
document["components"] = {}
document["modules"] = {name: value for name, value in document["modules"].items() if name not in known}
Path(__file__).with_name("schema.json").write_text(json.dumps(document, indent=2, sort_keys=True, default=str) + "\n")
