"""Generate component props decoders and portable native metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..bridge.codec import to_jsonable
from .schema import COMPONENTS, fingerprint, manifest


def generate(destination: str | Path) -> list[Path]:
    """Write deterministic Swift, Kotlin, Python, and browser schema artifacts."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    spec = manifest()
    encoded = json.dumps(spec, indent=2, sort_keys=True, default=str) + "\n"
    swift = ["import Foundation", "", "// Generated from Python schemas. Regenerate instead of editing."]
    kotlin = [
        "package com.pythonnative.generated",
        "",
        "import org.json.JSONObject",
        "",
        "// Generated from Python schemas.",
    ]
    python = [
        '"""Generated native component factories."""',
        "from typing import Any",
        "from pythonnative.element import Element",
        "from pythonnative.sdk.schema import COMPONENTS",
        "",
    ]
    docs = ["# Native contracts", "", f"Runtime fingerprint: `{fingerprint()}`.", ""]
    names = {
        "string": ("String", "String", "str"),
        "boolean": ("Bool", "Boolean", "bool"),
        "integer": ("Int", "Int", "int"),
        "number": ("Double", "Double", "float"),
    }
    for name, component in sorted(COMPONENTS.items()):
        if not name.isidentifier():
            raise ValueError(f"Invalid native component name {name!r}")
        swift.extend(
            [
                f"public struct {name}Props {{",
                "    public let values: [String: Any]",
                "    public init(_ values: [String: Any]) throws {",
                "        self.values = values",
            ]
        )
        kotlin.extend([f"data class {name}Props(val values: JSONObject) {{", "    init {"])
        parameters = []
        values = []
        for key, field in component.props.items():
            if not key.isidentifier():
                raise ValueError(f"Invalid property name {key!r}")
            kind = field.get("type")
            swift_type, kotlin_type, python_type = names.get(kind, ("Any", "Any", "Any"))
            if key in component.required:
                swift.append(
                    f'        guard values["{key}"] is {swift_type} else {{ '
                    f'throw NativeDecodeError.invalid("{name}.{key}") }}'
                )
                kotlin.append(
                    f'        require(values.has("{key}") && !values.isNull("{key}")) {{ "Missing {name}.{key}" }}'
                )
            default = component.defaults.get(key)
            if hasattr(default, "value"):
                default = default.value
            if default is None and python_type != "Any":
                python_type += " | None"
            parameters.append(f"{key}: {python_type}" + (f" = {default!r}" if key not in component.required else ""))
            values.append(f'"{key}": {key}')
        swift.append("    }")
        kotlin.append("    }")
        for key, field in component.props.items():
            kind = field.get("type")
            st, kt, _ = names.get(kind, ("Any", "Any", "Any"))
            expression = f'values["{key}"]' + (f" as? {st}" if st != "Any" else "")
            swift.append(f"    public var {key}: {st}? {{ {expression} }}")
            accessor = {"string": "getString", "boolean": "getBoolean", "integer": "getInt", "number": "getDouble"}.get(
                kind, "get"
            )
            kotlin.append(
                f'    val {key}: {kt}? get() = if (values.isNull("{key}")) null else values.{accessor}("{key}")'
            )
        swift.extend(["}", ""])
        kotlin.extend(["}", ""])
        python.extend(
            [
                f"def {name}(*children: Element, "
                + ", ".join(parameters + ["key: str | None = None"])
                + ") -> Element:",
                f'    """Create a validated {name} native element."""',
                "    props = {" + ", ".join(values) + "}",
                f'    COMPONENTS["{name}"].validate(props)',
                f'    return Element("{name}", props, list(children), key=key)',
                "",
            ]
        )
        docs.extend(
            [
                f"## {name}",
                "",
                f"Measurement: {component.measurement}.",
                "",
                "| Property | Type | Required |",
                "| --- | --- | --- |",
            ]
        )
        docs.extend(
            f"| `{key}` | `{field.get('type', 'union')}` | {key in component.required} |"
            for key, field in component.props.items()
        )
        docs.append("")
    swift.extend(["public enum NativeDecodeError: Error { case invalid(String) }", ""])
    outputs: dict[str, Any] = {
        "schema.json": encoded,
        "schema.js": "export default " + encoded.strip() + ";\n",
        "NativeProps.swift": "\n".join(swift),
        "NativeProps.kt": "\n".join(kotlin),
        "components.py": "\n".join(python),
        "README.md": "\n".join(docs),
    }
    compact = json.dumps(to_jsonable(spec), separators=(",", ":"), sort_keys=True)
    templates = Path(__file__).with_name("templates")
    for extension in ("swift", "kt"):
        template = (templates / f"contracts.{extension}").read_text(encoding="utf-8")
        # Escaped Swift strings and Kotlin raw strings have different interpolation rules.
        data = (
            compact.replace("\\", "\\\\")
            if extension == "swift"
            else ",\n".join(
                '"""' + compact[i : i + 8000].replace("$", "${'$'}") + '"""' for i in range(0, len(compact), 8000)
            )
        )
        outputs[f"PNContracts.{extension}"] = template.replace("{{fingerprint}}", fingerprint()).replace(
            "{{specification}}", data
        )
    from .module_codegen import generate_modules

    outputs.update(generate_modules())
    paths = []
    for name, contents in outputs.items():
        path = destination / name
        path.write_text(contents, encoding="utf-8")
        paths.append(path)
    return paths
