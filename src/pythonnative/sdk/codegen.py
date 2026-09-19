"""Compile Python contracts into typed native interfaces and documentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..bridge.codec import to_jsonable
from .native_types import NativeTypes, identifier
from .schema import COMPONENTS, fingerprint, manifest


def generate(destination: str | Path) -> list[Path]:
    """Write deterministic Swift, Kotlin, Python, and browser contract artifacts."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    spec = to_jsonable(manifest())
    encoded = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    types = NativeTypes()
    swift = ["import Foundation", "import UIKit", ""]
    kotlin = [
        "package com.pythonnative.generated",
        "",
        "import android.view.View",
        "import org.json.JSONObject",
        "import com.pythonnative.runtime.components.PNEvents",
        "",
    ]

    # A View prop is shared (a getter on the base class, and a type named after
    # View) when every component that declares it declares the same schema.
    # Compare JSON forms: extension manifests arrive through JSON, so a
    # built-in tuple and an extension's list must still count as equal, or a
    # plugin build would rename the built-in types hand-written code uses.
    def canonical(field: Any) -> str:
        return json.dumps(to_jsonable(field), sort_keys=True, default=str)

    view_props = dict(COMPONENTS["View"].props) if "View" in COMPONENTS else {}
    common = {
        key: field
        for key, field in view_props.items()
        if all(
            key not in component.props or canonical(component.props[key]) == canonical(field)
            for component in COMPONENTS.values()
        )
    }

    def getters(fields: dict[str, Any], hint: str) -> None:
        for key, field in fields.items():
            if field.get("native", {}).get("python_only"):
                continue
            _, st, kt = types.types(field, hint + identifier(key))
            swift.extend(
                [
                    f'    public var has_{key}: Bool {{ values["{key}"] != nil }}',
                    f'    public var `{key}`: {st.rstrip("?")}? {{ guard let value = values["{key}"], !(value is NSNull) else {{ return nil }}; return try! PNValues.decode({st.rstrip("?")}.self, value) }}',  # noqa: E501
                ]
            )
            decoded = types.kotlin_decode(field, f'values.get("{key}")', hint + identifier(key))
            kotlin.extend(
                [
                    f'    val has_{key}: Boolean get() = values.has("{key}")',
                    f'    val `{key}`: {kt.rstrip("?")}? get() = if (PNValues.isNull(values.opt("{key}"))) null else {decoded}',  # noqa: E501
                ]
            )

    swift.extend(
        [
            "open class PNViewProps {",
            "    public let values: [String: Any]",
            "    public init(_ values: [String: Any]) { self.values = values }",
        ]
    )
    kotlin.append("open class PNViewProps(val values: JSONObject) {")
    getters(common, "View")
    swift.extend(["}", ""])
    kotlin.extend(["}", ""])
    python = []
    docs = [
        "# Native contracts",
        "",
        f"Runtime fingerprint: `{fingerprint()}`.",
        "",
        "These contracts describe native host views. Composed Python components use these views internally.",
        "",
    ]
    sw_events, kt_events = ["public enum PNComponentEvents {"], ["object PNComponentEvents {"]
    for name, component in sorted(COMPONENTS.items()):
        if not name.isidentifier():
            raise ValueError(f"Invalid native component name {name!r}")
        swift.extend(
            [
                f"public final class {name}Props: PNViewProps, PNNativeProps {{",
                "    public init(_ values: [String: Any], partial: Bool = true) throws {",
                f'        guard PNContracts.validate("{name}", partial ? values.filter {{ !($0.value is NSNull) }} : values, partial: partial) else {{ throw NativeDecodeError.invalid("{name} props") }}',  # noqa: E501
                "        super.init(values)",
                "    }",
            ]
        )
        kotlin.extend(
            [
                f"class {name}Props(values: JSONObject, partial: Boolean = true): PNViewProps(values) {{",
                f'    init {{ require(PNContracts.validate("{name}", if (partial) PNValues.withoutNulls(values) else values, partial)) {{ "Invalid {name} props" }} }}',  # noqa: E501
            ]
        )
        parameters, values = [], []
        sw_events.append(f"    public enum {name} {{")
        kt_events.append(f"    object {name} {{")
        fields = dict(component.props)
        refresh = fields.get("refresh_control", {}).get("properties", {})
        for key, field in fields.items():
            if not key.isidentifier():
                raise ValueError(f"Invalid property name {key!r}")
            hint = name + identifier(key)
            pt, st, kt = types.types(field, hint)
            default = "" if key in component.required else " = UNSET"
            parameters.append(f"{key}: {pt}{' | UnsetType' if default else ''}{default}")
            values.append(f'"{key}": {key}')
        getters({key: value for key, value in fields.items() if key not in common}, name)
        for key, field in (fields | {key: value for key, value in refresh.items() if key.startswith("on_")}).items():
            alternatives = field.get("anyOf", [field])
            event = next((item for item in alternatives if item.get("type") == "event"), None)
            if event is None:
                continue
            arguments = event.get("arguments")
            if arguments is None:
                sw_events.append(
                    f'        @discardableResult public static func `{key}`(_ view: UIView, _ arguments: [Any?] = []) -> String? {{ PNEvents.emitIfWired(view, "{key}", arguments) }}'  # noqa: E501
                )
                kt_events.append(
                    f'        fun `{key}`(view: android.view.View, vararg arguments: Any?): Boolean = PNEvents.fire(view, "{key}", *arguments)'  # noqa: E501
                )
                continue
            swparams, ktparams, swvalues, ktvalues = [], [], [], []
            for index, argument in enumerate(arguments):
                _, st, kt = types.types(argument, name + identifier(key) + "Argument" + str(index))
                swparams.append(f"_ argument{index}: {st}")
                ktparams.append(f"argument{index}: {kt}")
                swvalues.append(f"PNValues.encode(argument{index})")
                ktvalues.append(f"PNValues.encode(argument{index})")
            sw_events.append(
                f"        @discardableResult public static func `{key}`("
                + ", ".join(["_ view: UIView"] + swparams)
                + f') -> String? {{ PNEvents.emitIfWired(view, "{key}", ['
                + ", ".join(swvalues)
                + "]) }"
            )
            kt_events.append(
                f"        fun `{key}`("
                + ", ".join(["view: android.view.View"] + ktparams)
                + f'): Boolean = PNEvents.fire(view, "{key}"'
                + (", " if ktvalues else "")
                + ", ".join(ktvalues)
                + ")"
            )
        swift.extend(["}", ""])
        kotlin.extend(["}", ""])
        sw_events.append("    }")
        kt_events.append("    }")
        python.extend(
            [
                f"def {name}(*children: Element, "
                + ", ".join(parameters + ["key: str | None = None"])
                + ") -> Element:",
                f'    """Create a validated {name} native element."""',
                "    props = {" + ", ".join(values) + "}",
                "    props = {name: value for name, value in props.items() if value is not UNSET}",
                f'    COMPONENTS["{name}"].validate(props)',
                f'    return Element("{name}", props, children, key=key)',
                "",
            ]
        )
        docs.extend(
            [
                f"## {name}",
                "",
                f"Measurement: {component.measurement}.",
                "",
                "| Property | Type | Platforms | Affects layout | Creation only |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for key, field in component.props.items():
            metadata = field.get("native", {})
            docs.append(
                f"| `{key}` | `{types.types(field, name + identifier(key))[0]}` | {', '.join(metadata.get('platforms', ('ios', 'android', 'web')))} | {metadata.get('invalidates_layout', False)} | {metadata.get('recreate', False)} |"  # noqa: E501
            )
        docs.append("")
    sw_events.append("}")
    kt_events.append("}")
    from .module_codegen import generate_modules

    modules = generate_modules(types)
    headers = [
        '"""Generated Python interfaces. Regenerate from the declarations."""',
        "",
        "# ruff: noqa: E501, E402, F401, I001",
        "# fmt: off",
        "from __future__ import annotations",
        "from typing import Any, Callable, Literal",
        "from pythonnative.mutations import UNSET, UnsetType",
        "from pythonnative.sdk.types import decode_value, resolve_type",
        *types.python_imports(),
        "",
    ]
    templates = Path(__file__).with_name("templates")
    outputs: dict[str, Any] = {
        "schema.json": encoded,
        "schema.js": "export default " + encoded.strip() + ";\n",
        "NativeProps.swift": "\n".join(swift + sw_events),
        "NativeProps.kt": "\n".join(kotlin + kt_events),
        "NativeValues.swift": (templates / "values.swift").read_text() + "\n" + "\n".join(types.swift),
        "NativeValues.kt": (templates / "values.kt").read_text() + "\n" + "\n".join(types.kotlin),
        "components.py": "\n".join(
            headers
            + ["from pythonnative.element import Element", "from pythonnative.sdk.schema import COMPONENTS", ""]
            + python
        ),
        "README.md": "\n".join(docs),
        **modules,
    }
    outputs["modules.py"] = "\n".join(
        headers + ["from pythonnative.native_modules.registry import native_module", "", modules["modules.py"]]
    )
    compact = json.dumps(spec, separators=(",", ":"), sort_keys=True)
    for extension in ("swift", "kt"):
        template = (templates / f"contracts.{extension}").read_text(encoding="utf-8")
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
    paths = []
    for name, contents in outputs.items():
        if name.endswith(".py"):
            contents = contents.rstrip() + "\n"
        path = destination / name
        path.write_text(contents, encoding="utf-8")
        paths.append(path)
    return paths
