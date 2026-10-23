package com.pythonnative.generated

import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject

/**
 * The contract this library was generated from. The renderer core compiles
 * the same contracts and validates every commit, command, and module call;
 * nothing on the Kotlin side interprets them.
 */
object PNContracts {
    const val fingerprint = "{{fingerprint}}"
    const val protocolVersion = {{protocol}}
    const val yogaVersion = "{{yoga}}"

    /** Whether a native module call's arguments satisfy its contract. */
    fun validateModule(name: String, method: String, args: JSONObject): Boolean =
        name in setOf("DevSupport", "Host", "Runtime") || PNCore.validateModule(name, method, args.toString())
}
