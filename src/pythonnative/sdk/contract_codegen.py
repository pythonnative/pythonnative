"""Compile schema predicates and property metadata into executable native code."""

from __future__ import annotations

import json
from typing import Any

from .native_types import quoted


class ContractCompiler:
    """Deduplicate recursive predicates across components, commands, and modules."""

    def __init__(self, kotlin: bool = False) -> None:
        self.kotlin = kotlin
        self.predicates: dict[str, str] = {}
        self.functions: list[str] = []

    def quote(self, value: str) -> str:
        """Quote a string in the output language."""
        return quoted(value, kotlin=self.kotlin)

    def predicate(self, schema: dict[str, Any]) -> str:
        """Return the generated function name for a schema's value constraints."""
        # Documentation and Python/native metadata don't affect value matching.
        keys = ("type", "anyOf", "enum", "items", "prefixItems", "properties", "required", "additionalProperties")
        shape = {key: schema[key] for key in keys if key in schema}
        identity = json.dumps(shape, sort_keys=True)
        if identity in self.predicates:
            return self.predicates[identity]
        name = f"match{len(self.predicates)}"
        self.predicates[identity] = name
        kt, q = self.kotlin, self.quote
        lines: list[str] = []
        expr = "true"
        if "anyOf" in shape:
            expr = " || ".join(f"{self.predicate(item)}(value)" for item in shape["anyOf"]) or "false"
        elif "enum" in shape:
            choices = []
            for value in shape["enum"]:
                if value is None:
                    choices.append("value == JSONObject.NULL" if kt else "value is NSNull")
                elif isinstance(value, str):
                    choices.append(f"value == {q(value)}" if kt else f"(value as? String) == {q(value)}")
                elif isinstance(value, bool):
                    literal = str(value).lower()
                    choices.append(
                        f"value is Boolean && value == {literal}"
                        if kt
                        else f"isBoolean(value) && (value as? NSNumber)?.boolValue == {literal}"
                    )
                else:
                    choices.append(
                        f"isNumber(value) && (value as Number).toDouble() == {float(value)}"
                        if kt
                        else f"isNumber(value) && (value as? NSNumber)?.doubleValue == {float(value)}"
                    )
            expr = " || ".join(f"({choice})" for choice in choices) or "false"
        elif shape.get("type") == "array":
            lines.append(
                "if (value !is JSONArray) return false"
                if kt
                else "guard let value = value as? [Any] else { return false }"
            )
            if "prefixItems" in shape:
                fields = shape["prefixItems"]
                expr = f"value.length() == {len(fields)}" if kt else f"value.count == {len(fields)}"
                expr += "".join(
                    f" && {self.predicate(field)}(value.get({i}))" if kt else f" && {self.predicate(field)}(value[{i}])"
                    for i, field in enumerate(fields)
                )
            else:
                item = self.predicate(shape.get("items", {}))
                expr = (
                    f"(0 until value.length()).all {{ {item}(value.get(it)) }}"
                    if kt
                    else f"value.allSatisfy {{ {item}($0) }}"
                )
        elif shape.get("type") == "object":
            lines.append(
                "if (value !is JSONObject) return false"
                if kt
                else "guard let value = value as? [String: Any] else { return false }"
            )
            for key in shape.get("required", []):
                lines.append(
                    f"if (!value.has({q(key)})) return false"
                    if kt
                    else f"guard value[{q(key)}] != nil else {{ return false }}"
                )
            fields = shape.get("properties", {})
            additional = shape.get("additionalProperties", True)
            fallback = (
                f"{self.predicate(additional)}(item)" if isinstance(additional, dict) else str(additional).lower()
            )
            if kt:
                lines += [
                    "for (key in value.keys()) {",
                    "    val item = value.get(key)",
                    "    val valid = when (key) {",
                ]
                lines += [f"        {q(key)} -> {self.predicate(field)}(item)" for key, field in sorted(fields.items())]
                lines += [f"        else -> {fallback}", "    }", "    if (!valid) return false", "}"]
            else:
                lines += ["for (key, item) in value {", "    let valid: Bool", "    switch key {"]
                lines += [
                    f"    case {q(key)}: valid = {self.predicate(field)}(item)" for key, field in sorted(fields.items())
                ]
                lines += [f"    default: valid = {fallback}", "    }", "    if !valid { return false }", "}"]
        else:
            expr = {
                "null": "value == JSONObject.NULL" if kt else "value is NSNull",
                "string": "value is String",
                "boolean": "isBoolean(value)",
                "event": "isBoolean(value)",
                "number": "isNumber(value)",
                "integer": "isInteger(value)",
            }.get(shape.get("type", ""), "true")
        signature = (
            f"    private fun {name}(value: Any): Boolean {{"
            if kt
            else f"    private static func {name}(_ value: Any) -> Bool {{"
        )
        self.functions.append(
            "\n".join([signature, *["        " + line for line in lines], "        return " + expr, "    }"])
        )
        return name

    def generate(self, spec: dict[str, Any], fingerprint: str, template: str) -> str:
        """Generate the executable contracts and retain no runtime schema document."""
        kt, q = self.kotlin, self.quote
        descriptors: dict[str, str] = {}
        fields: list[str] = []
        components: list[str] = []
        for name, component in sorted(spec["components"].items()):
            entries = []
            for key, schema in sorted(component["props"].items()):
                metadata = schema.get("native", {})
                allowed = ("android" if kt else "ios") in metadata.get("platforms", ["android", "ios", "web"])
                layout = metadata.get("invalidates_layout", True)
                recreate = metadata.get("recreate", False)
                required = key in component.get("required", [])
                default = component.get("defaults", {}).get(key)
                identity = json.dumps([schema, allowed, layout, recreate, required, default], sort_keys=True)
                if identity not in descriptors:
                    field = f"field{len(descriptors)}"
                    descriptors[identity] = field
                    match = self.predicate(schema)
                    default_expr = f"PNValues.defaultValue({q(json.dumps(default, separators=(',', ':')))})"
                    args = [
                        f"::{match}" if kt else match,
                        *[str(v).lower() for v in (allowed, layout, recreate, required)],
                        default_expr,
                    ]
                    declaration = (
                        f"    private val {field} = Field(" if kt else f"    private static let {field} = Field("
                    )
                    fields.append(declaration + ", ".join(args) + ")")
                field = descriptors[identity]
                entries.append(f"{q(key)} to {field}" if kt else f"{q(key)}: {field}")
            builder = f"component{len(components)}"
            declaration = (
                f"    private fun {builder}(): Map<String, Field> = mapOf(\n"
                if kt
                else f"    private static func {builder}() -> [String: Field] {{ [\n"
            )
            self.functions.append(
                declaration + ",\n".join("        " + e for e in entries) + ("\n    )" if kt else "\n    ] }")
            )
            components.append(f"        {q(name)} to {builder}()" if kt else f"        {q(name)}: {builder}()")
        commands: list[str] = []
        modules: list[str] = []
        for group, target in ((spec["components"], commands), (spec["modules"], modules)):
            for name, item in sorted(group.items()):
                for method, contract in sorted(item.get("commands" if target is commands else "methods", {}).items()):
                    arguments = contract.get("arguments", {})
                    predicate = self.predicate(
                        {
                            "type": "object",
                            "properties": arguments,
                            "required": contract.get("required", list(arguments)),
                            "additionalProperties": False,
                        }
                    )
                    key = q(name + "." + method)
                    target.append(f"        {key} to ::{predicate}" if kt else f"        {key}: {predicate}")
        substitutions = {
            "fingerprint": fingerprint,
            "predicates": "\n".join(self.functions),
            "fields": "\n".join(fields),
            "components": ",\n".join(components),
            "commands": ",\n".join(commands),
            "modules": ",\n".join(modules),
        }
        for key, value in substitutions.items():
            template = template.replace("{{" + key + "}}", value)
        return template
