package com.pythonnative.generated

import com.pythonnative.runtime.core.PNCore
import org.json.JSONObject

/**
 * The contract this library was generated from. The renderer core compiles
 * the same contracts and validates every commit, command, and module call;
 * nothing on the Kotlin side interprets them.
 */
object PNContracts {
    const val fingerprint = "b0e877e93fc406ca1947e2d6e08b438f7b93722f0de9e4ddaf14a21ebf5acbe5"
    const val protocolVersion = 8
    const val yogaVersion = "3.2.1"

    /** Whether a native module call's arguments satisfy its contract. */
    fun validateModule(name: String, method: String, args: JSONObject): Boolean =
        name in setOf("DevSupport", "Host", "Runtime") || PNCore.validateModule(name, method, args.toString())
}
