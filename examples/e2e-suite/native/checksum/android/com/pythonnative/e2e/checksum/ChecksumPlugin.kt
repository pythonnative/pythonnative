package com.pythonnative.e2e.checksum

import android.content.pm.PackageManager
import com.pythonnative.generated.ChecksumImplementation
import com.pythonnative.generated.ChecksumModuleAdapter
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry

/** Exercises a plugin's CMake target and a manifest entry it declares. */
object ChecksumPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { ChecksumModuleAdapter(ChecksumModule()) }
    }
}

class ChecksumModule : ChecksumImplementation {
    private external fun adler32Native(input: ByteArray): Long

    override fun adler32(text: String): Long = adler32Native(text.toByteArray())

    override fun configured_value(): String {
        val context = PNBridge.context()
        val info = context.packageManager.getApplicationInfo(context.packageName, PackageManager.GET_META_DATA)
        return info.metaData?.getString("pn.e2e.plugin_key") ?: "missing"
    }

    private companion object {
        init {
            System.loadLibrary("pn_e2e_checksum")
        }
    }
}
