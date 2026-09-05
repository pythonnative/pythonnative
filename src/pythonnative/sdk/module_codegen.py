"""Typed module facades and native dispatch adapters from Python protocols."""

from __future__ import annotations

from typing import Any

from .schema import MODULES


def _types(schema: dict[str, Any]) -> tuple[str, str, str]:
    if "anyOf" in schema:
        variants = [item for item in schema["anyOf"] if item.get("type") != "null"]
        if len(variants) == 1:
            python, swift, kotlin = _types(variants[0])
            return python + " | None", swift + "?", kotlin + "?"
    return {
        "string": ("str", "String", "String"),
        "integer": ("int", "Int", "Int"),
        "number": ("float", "Double", "Double"),
        "boolean": ("bool", "Bool", "Boolean"),
        "null": ("None", "Void", "Unit"),
    }.get(schema.get("type", ""), ("Any", "Any", "Any"))


def generate_modules() -> dict[str, str]:
    """Generate native interfaces, checked dispatch, and typed Python calls."""
    python = [
        '"""Generated native module facades."""',
        "from typing import Any",
        "from pythonnative.native_modules.registry import native_module",
        "",
    ]
    swift = ["import Foundation", ""]
    kotlin = [
        "package com.pythonnative.generated",
        "",
        "import org.json.JSONObject",
        "import com.pythonnative.runtime.modules.NativeModule",
        "import com.pythonnative.runtime.modules.Promise",
        "",
    ]
    for name, module in sorted(MODULES.items()):
        if not name.isidentifier():
            raise ValueError(f"Invalid module name: {name!r}")
        python.append(f"class {name}:")
        swift.extend([f"public protocol {name}Implementation {{", "    init()"])
        kotlin.append(f"interface {name}Implementation {{")
        method_info = []
        for method, contract in module.methods.items():
            if not method.isidentifier():
                raise ValueError(f"Invalid method name: {method!r}")
            result_py, result_swift, result_kotlin = _types(contract["result"])
            params_py, params_swift, params_kotlin, args = [], [], [], []
            for key, schema in contract["arguments"].items():
                if not key.isidentifier():
                    raise ValueError(f"Invalid argument name: {key!r}")
                pt, st, kt = _types(schema)
                params_py.append(f"{key}: {pt}")
                params_swift.append(f"{key}: {st}")
                params_kotlin.append(f"{key}: {kt}")
                args.append(key)
            asynchronous = contract["async"]
            python.extend(
                [
                    "    @staticmethod",
                    f"    {'async ' if asynchronous else ''}def {method}("
                    + ", ".join(params_py)
                    + f") -> {result_py}:",
                    f'        return {"await " if asynchronous else ""}native_module("{name}").'
                    f'{"call_async" if asynchronous else "call"}("{method}"'
                    + "".join(f", {key}={key}" for key in args)
                    + ")",
                    "",
                ]
            )
            if asynchronous:
                swift.append(
                    f"    func {method}("
                    + ", ".join(params_swift + [f"completion: @escaping (Result<{result_swift}, Error>) -> Void"])
                    + ")"
                )
                kotlin.append(
                    f"    fun {method}("
                    + ", ".join(params_kotlin + [f"completion: (Result<{result_kotlin}>) -> Unit"])
                    + ")"
                )
            else:
                swift.append(f"    func {method}(" + ", ".join(params_swift) + f") throws -> {result_swift}")
                kotlin.append(f"    fun {method}(" + ", ".join(params_kotlin) + f"): {result_kotlin}")
            method_info.append((method, contract, args))
        if not method_info:
            python.append("    pass")
        python.append("")
        swift.extend(
            [
                "}",
                "",
                f"public final class {name}Module<Implementation: {name}Implementation>: PNNativeModule {{",
                f'    public static var name: String {{ "{name}" }}',
                "    let implementation: Implementation",
                "    public init() { implementation = Implementation() }",
                "    public func call(_ method: String, args: [String: Any], promise: PNPromise) {",
                "        do {",
                "            switch method {",
            ]
        )
        kotlin.extend(
            [
                "}",
                "",
                f"class {name}Module(private val implementation: {name}Implementation): NativeModule {{",
                f'    override val name = "{name}"',
                "    override fun call(method: String, args: JSONObject, promise: Promise) {",
                "        try {",
                "            when (method) {",
            ]
        )
        for method, contract, args in method_info:
            swift.append(f'            case "{method}":')
            kotlin.append(f'                "{method}" -> {{')
            for key in args:
                _, st, kt = _types(contract["arguments"][key])
                if st.endswith("?"):
                    swift.append(f'                let {key} = args["{key}"] as? {st[:-1]}')
                else:
                    swift.append(
                        f'                guard let {key} = args["{key}"] as? {st} else {{ '
                        f'promise.reject("Invalid {key}"); return }}'
                    )
                accessor = {"String": "getString", "Int": "getInt", "Double": "getDouble", "Boolean": "getBoolean"}.get(
                    kt.rstrip("?"), "get"
                )
                expression = f'args.{accessor}("{key}")'
                if kt.endswith("?"):
                    expression = f'if (args.isNull("{key}")) null else {expression}'
                kotlin.append(f"                    val {key} = {expression}")
            sc = f"implementation.{method}(" + ", ".join(f"{key}: {key}" for key in args)
            kc = f"implementation.{method}(" + ", ".join(args)
            void = contract["result"].get("type") == "null"
            if contract["async"]:
                swift.append(f"                {sc}) {{ result in")
                swift.append(
                    "                    switch result { case .success(let value): promise.resolve("
                    + ("nil" if void else "value")
                    + "); case .failure(let error): promise.reject(error) }"
                )
                swift.append("                }")
                kotlin.append(
                    f"                    {kc}) {{ result -> result.fold({{ value -> promise.resolve("
                    + ("null" if void else "value")
                    + ') }, { error -> promise.reject(error.message ?: "Native call failed") }) }'
                )
            elif void:
                swift.append(f"                try {sc}); promise.resolve(nil)")
                kotlin.append(f"                    {kc}); promise.resolve(null)")
            else:
                swift.append(f"                promise.resolve(try {sc}))")
                kotlin.append(f"                    promise.resolve({kc}))")
            kotlin.append("                }")
        swift.extend(
            [
                '            default: promise.reject("Unknown method", code: "unknown_method")',
                "            }",
                "        } catch { promise.reject(error) }",
                "    }",
                "}",
                "",
            ]
        )
        kotlin.extend(
            [
                "                else -> promise.rejectUnknownMethod(method)",
                "            }",
                '        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }',
                "    }",
                "}",
                "",
            ]
        )
    return {
        "modules.py": "\n".join(python),
        "NativeModules.swift": "\n".join(swift),
        "NativeModules.kt": "\n".join(kotlin),
    }
