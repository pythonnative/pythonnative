package com.pythonnative.runtime.modules

import android.content.Context
import android.content.SharedPreferences
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject

/** `Storage`: `get/set/delete/all_keys/clear` over the `pn_async_storage` SharedPreferences file. */
class StorageModule : com.pythonnative.generated.StorageImplementation {
    private fun prefs(): SharedPreferences =
        PNBridge.context().getSharedPreferences("pn_async_storage", Context.MODE_PRIVATE)
    override fun get(key: String): String? = prefs().getString(key, null)
    override fun set(key: String, value: String) { prefs().edit().putString(key, value).apply() }
    override fun delete(key: String) { prefs().edit().remove(key).apply() }
    override fun all_keys(): List<String> = prefs().all.keys.sorted()
    override fun clear() { prefs().edit().clear().apply() }
}

/**
 * `SecureStore`: `set_item/get_item/delete_item` over `EncryptedSharedPreferences`.
 *
 * security-crypto 1.1 deprecates the whole API in favour of hand-rolled Keystore code, but the
 * file name and schemes must stay identical to what earlier PythonNative releases wrote so that
 * existing secrets remain readable, hence the suppression.
 */
@Suppress("DEPRECATION")
class SecureStoreModule : com.pythonnative.generated.SecureStoreImplementation {
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

    override fun clear() {
        val store = prefs() ?: throw IllegalStateException("Secure storage unavailable")
        check(store.edit().clear().commit()) { "Secure storage could not be cleared" }
    }
    override fun set_item(key: String, value: String): Boolean {
        val store = prefs() ?: return false
        return store.edit().putString(key, value).commit()
    }
    override fun get_item(key: String): String? = prefs()?.getString(key, null)
    override fun delete_item(key: String): Boolean {
        val store = prefs() ?: return false
        return store.edit().remove(key).commit()
    }
}
