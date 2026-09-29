"""Generate recursive native records, enums, unions, and Python annotations."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def identifier(value: str) -> str:
    """Make a deterministic native type name from a schema path."""
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^a-zA-Z0-9]+", value) if part)


def quoted(value: str, *, kotlin: bool = False) -> str:
    """Quote a literal for Swift or Kotlin generated source."""
    escapes = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    if kotlin:
        escapes["$"] = "\\$"
    result = []
    for char in value:
        if char in escapes:
            result.append(escapes[char])
        elif ord(char) < 32 or char in "\u2028\u2029":
            result.append(f"\\u{ord(char):04x}" if kotlin else f"\\u{{{ord(char):x}}}")
        else:
            result.append(char)
    return '"' + "".join(result) + '"'


class NativeTypes:
    """One shared type table for components, events, and service interfaces."""

    def __init__(self) -> None:
        self.swift: list[str] = []
        self.kotlin: list[str] = []
        self.python: dict[str, str] = {}
        self._names: dict[str, str] = {}
        self._schemas: dict[str, dict[str, Any]] = {}

    def types(self, schema: dict[str, Any], hint: str) -> tuple[str, str, str]:
        """Return Python, Swift, and Kotlin representations, adding definitions."""
        alternatives = schema.get("anyOf")
        if alternatives is not None:
            nonnull = [item for item in alternatives if item.get("type") != "null"]
            if len(nonnull) == 1 and len(nonnull) < len(alternatives):
                py, sw, kt = self.types(nonnull[0], hint)
                return py + " | None", sw.rstrip("?") + "?", kt.rstrip("?") + "?"
        if "enum" in schema or alternatives is not None or "properties" in schema or "prefixItems" in schema:
            name = self._named(schema, hint)
            if "python_type" in schema:
                self.python[name] = schema["python_type"]
                py = name
            elif "enum" in schema:
                py = "Literal[" + ", ".join(repr(item) for item in schema["enum"]) + "]"
            elif alternatives is not None:
                py = " | ".join(self.types(item, hint + str(index))[0] for index, item in enumerate(alternatives))
            elif "prefixItems" in schema:
                py = (
                    "tuple["
                    + ", ".join(
                        self.types(item, hint + str(index))[0] for index, item in enumerate(schema["prefixItems"])
                    )
                    + "]"
                )
            else:
                py = "dict[str, Any]"
            return py, name, name
        kind = schema.get("type", "json")
        if kind == "array":
            py, sw, kt = self.types(schema.get("items", {}), hint + "Item")
            container = schema.get("python_container", "list")
            return f"{container}[{py}{', ...' if container == 'tuple' else ''}]", f"[{sw}]", f"List<{kt}>"
        if kind == "object":
            py, sw, kt = self.types(schema.get("additionalProperties", {}), hint + "Value")
            return f"dict[str, {py}]", f"[String: {sw}]", f"Map<String, {kt}>"
        return {
            "string": ("str", "String", "String"),
            "integer": ("int", "Int64", "Long"),
            "number": ("float", "Double", "Double"),
            "boolean": ("bool", "Bool", "Boolean"),
            "null": ("None", "PNJSONValue", "PNJSONValue"),
            "event": ("Callable[..., Any]", "Bool", "Boolean"),
        }.get(kind, ("Any", "PNJSONValue", "PNJSONValue"))

    def kotlin_decode(self, schema: dict[str, Any], value: str, hint: str) -> str:
        """Decode one Kotlin expression recursively, retaining its static type."""
        _, _, kt = self.types(schema, hint)
        alternatives = schema.get("anyOf")
        if alternatives is not None:
            nonnull = [item for item in alternatives if item.get("type") != "null"]
            if len(nonnull) == 1 and len(nonnull) < len(alternatives):
                inner = self.kotlin_decode(nonnull[0], value, hint)
                return f"if (PNValues.isNull({value})) null else {inner}"
        if "enum" in schema or alternatives is not None or "properties" in schema or "prefixItems" in schema:
            return f"{kt}.decode({value})"
        kind = schema.get("type", "json")
        accessor = {
            "string": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
            "event": "boolean",
        }.get(kind)
        if accessor:
            return f"PNValues.{accessor}({value})"
        if kind == "array":
            inner = self.kotlin_decode(schema.get("items", {}), "item", hint + "Item")
            return f"PNValues.array({value}).map {{ item -> {inner} }}"
        if kind == "object":
            inner = self.kotlin_decode(schema.get("additionalProperties", {}), "objectValue.get(key)", hint + "Value")
            return f"PNValues.objectValue({value}).let {{ objectValue -> objectValue.keys().asSequence().associateWith {{ key -> {inner} }} }}"  # noqa: E501
        return f"PNJSONValue({value} ?: JSONObject.NULL)"

    def _named(self, schema: dict[str, Any], hint: str) -> str:
        portable = {key: value for key, value in schema.items() if key != "native"}
        signature = json.dumps(portable, sort_keys=True)
        if signature in self._names:
            return self._names[signature]
        declared = schema.get("python_type", "").partition(":")[2]
        name = "PN" + identifier(declared or hint)
        if name in self._schemas and self._schemas[name] != portable:
            name += hashlib.sha256(signature.encode()).hexdigest()[:8]
        self._names[signature] = name
        self._schemas[name] = portable
        if "enum" in schema:
            self._enum(name, schema)
        elif "anyOf" in schema:
            self._union(name, schema)
        else:
            self._record(name, schema)
        return name

    def _enum(self, name: str, schema: dict[str, Any]) -> None:
        values = schema["enum"]
        if not values:
            raise TypeError(f"Native enum {name} must have a value")
        # String literals form useful native enums, with readable cases and a
        # raw value for platform APIs that still accept strings.
        if all(isinstance(value, str) for value in values):
            names = [re.sub(r"\W", "_", value) or "empty" for value in values]
            names = [f"value_{value}" if value[0].isdigit() else value for value in names]
            if len(set(names)) == len(names):
                self.swift.extend(
                    [f"public enum {name}: String, Codable {{"]
                    + [f"    case `{case}` = {quoted(value)}" for case, value in zip(names, values)]
                    + ["}", ""]
                )
                self.kotlin.extend(
                    [f"enum class {name}(val rawValue: String) : PNNativeValue {{"]
                    + [
                        f"    `{case}`({quoted(value, kotlin=True)}){';' if index == len(values) - 1 else ','}"
                        for index, (case, value) in enumerate(zip(names, values))
                    ]
                    + [
                        "    override fun nativeValue(): Any = rawValue",
                        "    companion object {",
                        f"        fun decode(value: Any?): {name} = entries.firstOrNull {{ it.rawValue == value }}",
                        f'            ?: throw IllegalArgumentException("Invalid {name}")',
                        "    }",
                        "}",
                        "",
                    ]
                )
                return
        sw = [f"public enum {name}: Codable {{"]
        sw.extend(f"    case value{index}" for index in range(len(values)))
        sw.extend(
            [
                "    public init(from decoder: Decoder) throws {",
                "        let container = try decoder.singleValueContainer()",
                "        let value = try container.decode(PNJSONValue.self)",
            ]
        )
        for index, value in enumerate(values):
            literal = quoted(json.dumps(value))
            sw.append(
                f"        if value == (try PNValues.decode(PNJSONValue.self, PNValues.defaultValue({literal}))) {{ self = .value{index}; return }}"  # noqa: E501
            )
        sw.extend(
            [
                f'        throw NativeDecodeError.invalid("{name}")',
                "    }",
                "    public func encode(to encoder: Encoder) throws {",
                "        var container = encoder.singleValueContainer()",
                "        switch self {",
            ]
        )
        for index, value in enumerate(values):
            sw.append(
                f"        case .value{index}: try container.encode(PNValues.decode(PNJSONValue.self, PNValues.defaultValue({quoted(json.dumps(value))})))"  # noqa: E501
            )
        sw.extend(["        }", "    }", "}", ""])
        self.swift.extend(sw)
        kt = [f"enum class {name}(private val wire: Any) : PNNativeValue {{"]
        for index, value in enumerate(values):
            kt.append(
                f"    VALUE{index}(PNValues.defaultValue({quoted(json.dumps(value), kotlin=True)})){';' if index == len(values) - 1 else ','}"  # noqa: E501
            )
        kt.extend(
            [
                "    override fun nativeValue(): Any = wire",
                "    companion object {",
                f"        fun decode(value: Any?): {name} = entries.firstOrNull {{ candidate ->",
                "            if (candidate.wire is Number && value is Number) candidate.wire.toDouble() == value.toDouble() else candidate.wire == value",  # noqa: E501
                f'        }} ?: throw IllegalArgumentException("Invalid {name}")',
                "    }",
                "}",
                "",
            ]
        )
        self.kotlin.extend(kt)

    def _union(self, name: str, schema: dict[str, Any]) -> None:
        variants = [(item, self.types(item, name + str(index))) for index, item in enumerate(schema["anyOf"])]
        sw = [f"public enum {name}: Codable {{"]
        sw.extend(f"    case option{index}({types[1]})" for index, (_, types) in enumerate(variants))
        sw.extend(
            [
                "    public init(from decoder: Decoder) throws {",
                "        let container = try decoder.singleValueContainer()",
            ]
        )
        for index, (_, types) in enumerate(variants):
            sw.append(
                f"        if let value = try? container.decode({types[1]}.self) {{ self = .option{index}(value); return }}"  # noqa: E501
            )
        sw.extend(
            [
                f'        throw NativeDecodeError.invalid("{name}")',
                "    }",
                "    public func encode(to encoder: Encoder) throws {",
                "        var container = encoder.singleValueContainer()",
                "        switch self {",
            ]
        )
        sw.extend(
            f"        case .option{index}(let value): try container.encode(value)" for index in range(len(variants))
        )
        sw.extend(["        }", "    }", "}", ""])
        self.swift.extend(sw)
        kt = [f"sealed class {name} : PNNativeValue {{"]
        for index, (_, types) in enumerate(variants):
            kt.append(
                f"    data class Option{index}(val value: {types[2]}) : {name}() {{ override fun nativeValue(): Any = PNValues.encode(value) }}"  # noqa: E501
            )
        kt.extend(["    companion object {", f"        fun decode(value: Any?): {name} {{"])
        for index, (item, _) in enumerate(variants):
            decoded = self.kotlin_decode(item, "value", name + str(index))
            kt.append(f"            try {{ return Option{index}({decoded}) }} catch (_: Exception) {{ }}")
        kt.extend([f'            throw IllegalArgumentException("Invalid {name}")', "        }", "    }", "}", ""])
        self.kotlin.extend(kt)

    def _record(self, name: str, schema: dict[str, Any]) -> None:
        tuple_items = schema.get("prefixItems")
        fields = (
            schema.get("properties", {})
            if tuple_items is None
            else {f"item{index}": item for index, item in enumerate(tuple_items)}
        )
        required = set(schema.get("required", fields if tuple_items is not None else ()))
        defaults = schema.get("defaults", {})
        declarations = []
        nullable_omissions = set()
        for key, value in fields.items():
            _, swift_type, kotlin_type = self.types(value, name + identifier(key))
            if key not in required and key not in defaults:
                if swift_type.endswith("?"):
                    nullable_omissions.add(key)
                    swift_type, kotlin_type = f"PNPresence<{swift_type}>", f"PNPresence<{kotlin_type}>"
                else:
                    swift_type, kotlin_type = swift_type + "?", kotlin_type + "?"
            declarations.append((key, value, swift_type, kotlin_type))
        sw = [f"public struct {name}: Codable {{"]
        sw.extend(f"    public let `{key}`: {st}" for key, _, st, _ in declarations)
        params = ", ".join(f"`{key}`: {st}" for key, _, st, _ in declarations)
        sw.extend(
            [
                f"    public init({params}) {{",
                *[f"        self.`{key}` = `{key}`" for key, _, _, _ in declarations],
                "    }",
            ]
        )
        kt = [f"data class {name}(" if declarations else f"class {name}("]
        kt.extend(
            f"    val `{key}`: {ktype}{',' if index < len(declarations) - 1 else ''}"
            for index, (key, _, _, ktype) in enumerate(declarations)
        )
        kt.extend([") : PNNativeValue {"])
        if tuple_items is None:
            if declarations:
                sw.append(
                    "    private enum CodingKeys: String, CodingKey { "
                    + "; ".join(f"case `{key}`" for key, _, _, _ in declarations)
                    + " }"
                )
            sw.extend(["    public init(from decoder: Decoder) throws {"])
            if declarations:
                sw.append("        let container = try decoder.container(keyedBy: CodingKeys.self)")
            kt.append("    override fun nativeValue(): Any = JSONObject().also { result ->")
            for key, value, st, _ in declarations:
                decode = f"try container.decode({st}.self, forKey: .`{key}`)"
                if key in defaults:
                    default = (
                        f"try PNValues.decode({st}.self, PNValues.defaultValue({quoted(json.dumps(defaults[key]))}))"
                    )
                    decode = f"container.contains(.`{key}`) ? ({decode}) : ({default})"
                elif key in nullable_omissions:
                    inner = st.removeprefix("PNPresence<").removesuffix(">")
                    decode = (
                        f"container.contains(.`{key}`) ? "
                        f".present(try container.decode({inner}.self, forKey: .`{key}`)) : .absent"
                    )
                elif key not in required:
                    decode = f"try container.decodeIfPresent({st.rstrip('?')}.self, forKey: .`{key}`)"
                sw.append(f"        self.`{key}` = {decode}")
                if key in nullable_omissions:
                    kt.append(
                        f"        if (`{key}` is PNPresence.Present) "
                        f"result.put({quoted(key, kotlin=True)}, PNValues.encode(`{key}`.value))"
                    )
                else:
                    kt.append(
                        f"        result.put({quoted(key, kotlin=True)}, PNValues.encode(`{key}`))"
                        if key in required or key in defaults
                        else (
                            f"        if (`{key}` != null) "
                            f"result.put({quoted(key, kotlin=True)}, PNValues.encode(`{key}`))"
                        )
                    )
            kt.extend(
                [
                    "    }",
                    "    companion object {",
                    f"        fun decode(value: Any?): {name} {{",
                    "            val objectValue = PNValues.objectValue(value)",
                ]
            )
            expressions = []
            for key, value, _, _ in declarations:
                raw = f"objectValue.get({quoted(key, kotlin=True)})"
                if key in defaults:
                    raw = f"if (objectValue.has({quoted(key, kotlin=True)})) objectValue.get({quoted(key, kotlin=True)}) else PNValues.defaultValue({quoted(json.dumps(defaults[key]), kotlin=True)})"  # noqa: E501
                elif key not in required:
                    raw = f"objectValue.opt({quoted(key, kotlin=True)})"
                decoded = self.kotlin_decode(value, f"({raw})", name + identifier(key))
                if key in nullable_omissions:
                    decoded = (
                        f"if (objectValue.has({quoted(key, kotlin=True)})) "
                        f"PNPresence.Present({decoded}) else PNPresence.Absent"
                    )
                elif key not in required and key not in defaults:
                    decoded = f"if (PNValues.isNull({raw})) null else {decoded}"
                expressions.append(decoded)
            kt.append(f"            return {name}(" + ", ".join(expressions) + ")")
            sw.extend(["    }", "    public func encode(to encoder: Encoder) throws {"])
            if declarations:
                sw.append("        var container = encoder.container(keyedBy: CodingKeys.self)")
            for key, _, _, _ in declarations:
                if key in nullable_omissions:
                    sw.append(
                        f"        if case .present(let value) = `{key}` {{ "
                        f"try container.encode(value, forKey: .`{key}`) }}"
                    )
                else:
                    encode = "encode" if key in required or key in defaults else "encodeIfPresent"
                    sw.append(f"        try container.{encode}(`{key}`, forKey: .`{key}`)")
            if not declarations:
                sw.append("        var container = encoder.singleValueContainer()")
                sw.append("        try container.encode([String: PNJSONValue]())")
            sw.extend(["    }", "}", ""])
        else:
            sw.extend(
                [
                    "    public init(from decoder: Decoder) throws {",
                    "        var container = try decoder.unkeyedContainer()",
                ]
            )
            sw.extend(f"        `{key}` = try container.decode({st}.self)" for key, _, st, _ in declarations)
            sw.extend(
                [
                    '        if !container.isAtEnd { throw NativeDecodeError.invalid("Tuple length") }',
                    "    }",
                    "    public func encode(to encoder: Encoder) throws {",
                    "        var container = encoder.unkeyedContainer()",
                ]
            )
            sw.extend(f"        try container.encode(`{key}`)" for key, _, _, _ in declarations)
            sw.extend(["    }", "}", ""])
            kt.extend(
                [
                    "    override fun nativeValue(): Any = JSONArray().also { result ->",
                    *[f"        result.put(PNValues.encode(`{key}`))" for key, _, _, _ in declarations],
                    "    }",
                    "    companion object {",
                    f"        fun decode(value: Any?): {name} {{",
                    "            val items = PNValues.array(value)",
                    f'            require(items.size == {len(declarations)}) {{ "Tuple length" }}',
                ]
            )
            expressions = [
                self.kotlin_decode(value, f"items[{index}]", name + identifier(key))
                for index, (key, value, _, _) in enumerate(declarations)
            ]
            kt.append(f"            return {name}(" + ", ".join(expressions) + ")")
        kt.extend(["        }", "    }", "}", ""])
        self.swift.extend(sw)
        self.kotlin.extend(kt)

    def python_imports(self) -> list[str]:
        """Return aliases to the original Python declarations for generated APIs."""
        imports = []
        for name, qualified in sorted(self.python.items()):
            module, _, member = qualified.partition(":")
            if member.isidentifier():
                imports.append(f"from {module} import {member} as {name}")
            else:
                imports.append(f"{name} = resolve_type({qualified!r})")
        return imports
