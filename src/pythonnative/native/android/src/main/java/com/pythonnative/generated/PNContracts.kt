package com.pythonnative.generated

import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject

/**
 * The contract this library was generated from. The renderer core compiles
 * the same contracts and validates every commit, command, and module call;
 * nothing on the Kotlin side interprets them.
 */
object PNContracts {
    const val fingerprint = "4f3c6c610fd0f6b21949e7ed16e03fd100dd347c3e29be0dedd509b0fdb386dc"
    const val protocolVersion = 7
    const val yogaVersion = "3.2.1"

    /** Whether a native module call's arguments satisfy its contract. */
    fun validateModule(name: String, method: String, args: JSONObject): Boolean =
        name in setOf("DevSupport", "Host", "Runtime") || PNCore.validateModule(name, method, args.toString())
}
