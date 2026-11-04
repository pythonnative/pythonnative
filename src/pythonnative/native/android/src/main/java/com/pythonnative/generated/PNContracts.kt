package com.pythonnative.generated

import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject

/**
 * The contract this library was generated from. The renderer core compiles
 * the same contracts and validates every commit, command, and module call;
 * nothing on the Kotlin side interprets them.
 */
object PNContracts {
    const val fingerprint = "d0f4503111acbb6117870bb5bdd997964a29ec05d3190445e2c12ce446b18c4d"
    const val protocolVersion = 7
    const val yogaVersion = "3.2.1"

    /** Whether a native module call's arguments satisfy its contract. */
    fun validateModule(name: String, method: String, args: JSONObject): Boolean =
        name in setOf("DevSupport", "Host", "Runtime") || PNCore.validateModule(name, method, args.toString())
}
