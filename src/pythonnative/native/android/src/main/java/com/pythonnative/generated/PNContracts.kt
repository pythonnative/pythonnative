package com.pythonnative.generated

import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject

/**
 * The contract this library was generated from. The renderer core compiles
 * the same contracts and validates every commit, command, and module call;
 * nothing on the Kotlin side interprets them.
 */
object PNContracts {
    const val fingerprint = "b89b466f083ea2df7473d29e351ce99257f66792a17955c6ce3c2c0f238ae5c3"
    const val protocolVersion = 7
    const val yogaVersion = "3.2.1"

    /** Whether a native module call's arguments satisfy its contract. */
    fun validateModule(name: String, method: String, args: JSONObject): Boolean =
        name in setOf("DevSupport", "Host", "Runtime") || PNCore.validateModule(name, method, args.toString())
}
