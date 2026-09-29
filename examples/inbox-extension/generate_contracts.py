"""Regenerate the extension manifest and Python facade from its declarations."""

import json
import tempfile
from pathlib import Path

import inbox_extension  # noqa: F401

from pythonnative.sdk import generate
from pythonnative.sdk.schema import COMPONENTS, MODULES, manifest

spec = manifest()
spec["components"] = {"InboxBadge": spec["components"]["InboxBadge"]}
spec["modules"] = {"InboxTools": spec["modules"]["InboxTools"]}
root = Path(__file__).with_name("src") / "inbox_extension"
root.joinpath("native/schema.json").write_text(json.dumps(spec, indent=2) + "\n")
for name in list(COMPONENTS):
    if name != "InboxBadge":
        del COMPONENTS[name]
for name in list(MODULES):
    if name != "InboxTools":
        del MODULES[name]
with tempfile.TemporaryDirectory() as directory:
    generate(Path(directory))
    root.joinpath("api.py").write_text(Path(directory, "modules.py").read_text())
