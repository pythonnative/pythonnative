package com.pythonnative.runtime.modules

import android.content.Context
import android.content.SharedPreferences
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject

/** `Storage`: `get/set/delete/all_keys/clear` over the `pn_async_storage` SharedPreferences file. */
class StorageModule : NativeModule {
    override val name = "Storage"

    private fun prefs(): SharedPreferences =
        PNBridge.context().getSharedPreferences("pn_async_storage", Context.MODE_PRIVATE)

    override fun call(method: String, args: JSONObject, promise: Promise) {
        val key = args.str("key")
        when (method) {
            "get", "get_item" -> promise.resolve(prefs().getString(key ?: "", null))
            "set", "set_item" -> {
                prefs().edit().putString(key ?: "", args.str("value") ?: "").apply()
                promise.resolve(null)
            }
            "delete", "remove", "remove_item" -> {
                prefs().edit().remove(key ?: "").apply()
                promise.resolve(null)
            }
            "all_keys", "get_all_keys" -> promise.resolve(prefs().all.keys.sorted())
            "clear" -> {
                prefs().edit().clear().apply()
                promise.resolve(null)
            }
            else -> promise.rejectUnknownMethod(method)
        }
    }
}

/**
 * `SecureStore`: `set_item/get_item/delete_item` over `EncryptedSharedPreferences`.
 *
 * security-crypto 1.1 deprecates the whole API in favour of hand-rolled Keystore code, but the
 * file name and schemes must stay identical to what earlier PythonNative releases wrote so that
 * existing secrets remain readable, hence the suppression.
 */
@Suppress("DEPRECATION")
class SecureStoreModule : NativeModule {
    override val name = "SecureStore"
    private var prefs: SharedPreferences? = null

    private fun prefs(): SharedPreferences? {
        prefs?.let { return it }
        return try {
            val ctx = PNBridge.context()
            val master = androidx.security.crypto.MasterKey.Builder(ctx)
                .setKeyScheme(androidx.security.crypto.MasterKey.KeyScheme.AES256_GCM)
                .build()
            androidx.security.crypto.EncryptedSharedPreferences.create(
                ctx,
                "com.pythonnative.securestore",
                master,
                androidx.security.crypto.EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                androidx.security.crypto.EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            ).also { prefs = it }
        } catch (e: Exception) {
            PNLog.rateLimited("securestore", "EncryptedSharedPreferences unavailable", e)
            null
        }
    }

    override fun call(method: String, args: JSONObject, promise: Promise) {
        val key = args.str("key") ?: ""
        val store = prefs()
        when (method) {
            "set_item" -> {
                if (store == null) return promise.resolve(false)
                store.edit().putString(key, args.str("value") ?: "").apply()
                promise.resolve(true)
            }
            "get_item" -> promise.resolve(store?.getString(key, null))
            "delete_item" -> {
                if (store == null) return promise.resolve(false)
                store.edit().remove(key).apply()
                promise.resolve(true)
            }
            else -> promise.rejectUnknownMethod(method)
        }
    }
}
