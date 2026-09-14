"""Typed native method interfaces and cancellable dispatch adapters."""

from __future__ import annotations

from .native_types import NativeTypes, identifier, quoted
from .schema import MODULES


def generate_modules(types: NativeTypes) -> dict[str, str]:
    """Generate recursive native interfaces and ordinary Python methods."""
    python = []
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
        methods = []
        for method, contract in module.methods.items():
            if not method.isidentifier():
                raise ValueError(f"Invalid method name: {method!r}")
            prefix = name + identifier(method)
            result_py, result_swift, result_kotlin = types.types(contract["result"], prefix + "Result")
            void = contract["result"].get("type") == "null"
            if void:
                result_swift, result_kotlin = "Void", "Unit"
            params_py, params_swift, params_kotlin, arguments = [], [], [], []
            for key, schema in contract["arguments"].items():
                if not key.isidentifier():
                    raise ValueError(f"Invalid argument name: {key!r}")
                pt, st, kt = types.types(schema, prefix + identifier(key))
                default = ""
                if key in contract.get("defaults", {}):
                    default = f" = decode_value({contract['defaults'][key]!r}, {schema!r})"
                params_py.append(f"{key}: {pt}{default}")
                params_swift.append(f"`{key}`: {st}")
                params_kotlin.append(f"`{key}`: {kt}")
                arguments.append(key)
            asynchronous = contract["async"]
            python.extend(
                [
                    "    @staticmethod",
                    f"    {'async ' if asynchronous else ''}def {method}("
                    + ("*, " if params_py else "")
                    + ", ".join(params_py)
                    + f") -> {result_py}:",
                    f'        """Invoke the checked {name}.{method} native method."""',
                    f'        return {"await " if asynchronous else ""}native_module("{name}").'
                    f'{"call_async" if asynchronous else "call"}("{method}"'
                    + "".join(f", {key}={key}" for key in arguments)
                    + ")",
                    "",
                ]
            )
            if asynchronous:
                swift.append(
                    f"    func `{method}`("
                    + ", ".join(params_swift + [f"completion: @escaping (Result<{result_swift}, Error>) -> Void"])
                    + ") -> (() -> Void)?"
                )
                kotlin.append(
                    f"    fun `{method}`("
                    + ", ".join(params_kotlin + [f"completion: (Result<{result_kotlin}>) -> Unit"])
                    + "): (() -> Unit)?"
                )
            else:
                swift.append(f"    func `{method}`(" + ", ".join(params_swift) + f") throws -> {result_swift}")
                kotlin.append(f"    fun `{method}`(" + ", ".join(params_kotlin) + f"): {result_kotlin}")
            methods.append((method, contract, arguments, prefix, void))
        for event, payload in module.events.items():
            pt, st, kt = types.types(payload, name + identifier(event) + "Event")
            python.extend(
                [
                    "    @staticmethod",
                    f"    def on_{event}(callback: Callable[[{pt}], Any]) -> Callable[[], None]:",
                    f'        """Subscribe to the typed {name}.{event} event."""',
                    f'        return native_module("{name}").add_listener("{event}", callback)',
                    "",
                ]
            )
        if not methods:
            python.append("    pass")
        python.append("")
        swift.extend(
            [
                "}",
                "",
                f"public final class {name}ModuleAdapter<Implementation: {name}Implementation>: PNNativeModule {{",
                f'    public static var name: String {{ "{name}" }}',
                "    private let implementation: Implementation",
                "    public init() { implementation = Implementation() }",
                "    public init(implementation: Implementation) { self.implementation = implementation }",
                "    public func call(_ method: String, args: [String: Any], promise: PNPromise) {",
                "        do {",
                f'            guard PNContracts.validateModule("{name}", method, args) else {{ throw NativeDecodeError.invalid("{name}.\\(method)") }}',  # noqa: E501
                "            switch method {",
            ]
        )
        kotlin.extend(
            [
                "}",
                "",
                f"class {name}ModuleAdapter(private val implementation: {name}Implementation): NativeModule {{",
                f'    override val name = "{name}"',
                "    override fun call(method: String, args: JSONObject, promise: Promise) {",
                "        try {",
                '            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }',
                "            when (method) {",
            ]
        )
        for method, contract, arguments, prefix, void in methods:
            swift.append(f'            case "{method}":')
            kotlin.append(f'                "{method}" -> {{')
            for key in arguments:
                schema = contract["arguments"][key]
                _, st, _ = types.types(schema, prefix + identifier(key))
                swraw = f'args["{key}"]'
                ktraw = f'args.opt("{key}")'
                if key in contract.get("defaults", {}):
                    import json

                    default = json.dumps(contract["defaults"][key])
                    swraw += f" ?? PNValues.defaultValue({quoted(default)})"
                    ktraw = f'if (args.has("{key}")) {ktraw} else PNValues.defaultValue({quoted(default, kotlin=True)})'
                swift.append(f"                let `{key}` = try PNValues.decode({st}.self, {swraw})")
                kotlin.append(
                    f"                    val `{key}` = "
                    + types.kotlin_decode(schema, f"({ktraw})", prefix + identifier(key))
                )
            swcall = f"implementation.`{method}`(" + ", ".join(f"`{key}`: `{key}`" for key in arguments)
            ktcall = f"implementation.`{method}`(" + ", ".join(f"`{key}`" for key in arguments)
            if contract["async"]:
                swift.append(f"                let cancellation = {swcall}) {{ result in")
                swift.append("                    switch result {")
                swift.append(
                    "                    case .success(let value): "
                    + (
                        "promise.resolve(nil)"
                        if void
                        else "do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }"
                    )
                )
                swift.extend(
                    [
                        "                    case .failure(let error): promise.reject(error)",
                        "                    }",
                        "                }",
                        "                if let cancellation = cancellation { promise.onCancel(cancellation) }",
                    ]
                )
                kotlin.append(f"                    val cancellation = {ktcall}) {{ result ->")
                kotlin.append("                        try {")
                kotlin.append(
                    "                        result.fold({ value -> promise.resolve("
                    + ("null" if void else "PNValues.encode(value)")
                    + ') }, { error -> promise.reject(error.message ?: "Native call failed") })'
                )
                kotlin.extend(
                    [
                        '                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }',  # noqa: E501
                        "                    }",
                        "                    if (cancellation != null) promise.onCancel(cancellation)",
                    ]
                )
            elif void:
                swift.append(f"                try {swcall}); promise.resolve(nil)")
                kotlin.append(f"                    {ktcall}); promise.resolve(null)")
            else:
                swift.append(f"                promise.resolve(try PNValues.checkedEncode({swcall})))")
                kotlin.append(f"                    promise.resolve(PNValues.encode({ktcall})))")
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
        if module.events:
            swift.append(f"public enum {name}Events {{")
            kotlin.append(f"object {name}Events {{")
            for event, payload in module.events.items():
                _, st, kt = types.types(payload, name + identifier(event) + "Event")
                swift.append(
                    f'    public static func `{event}`(_ payload: {st}) {{ PNModuleEvents.emit(module: "{name}", event: "{event}", payload: PNValues.encode(payload)) }}'  # noqa: E501
                )
                kotlin.append(
                    f'    fun `{event}`(payload: {kt}) = com.pythonnative.runtime.modules.ModuleEvents.emit("{name}", "{event}", PNValues.encode(payload))'  # noqa: E501
                )
            swift.extend(["}", ""])
            kotlin.extend(["}", ""])

    return {
        "modules.py": "\n".join(python),
        "NativeModules.swift": "\n".join(swift),
        "NativeModules.kt": "\n".join(kotlin).replace("$", "\\$"),
    }
