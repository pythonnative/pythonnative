package com.pythonnative.generated

import org.json.JSONObject
import com.pythonnative.runtime.modules.NativeModule
import com.pythonnative.runtime.modules.Promise

interface AlertImplementation {
    fun present(title: String, message: String?, buttons: Any, style: String, completion: (Result<Int>) -> Unit)
    fun show(title: String, message: String?, buttons: Any, style: String): Unit
}

class AlertModuleAdapter(private val implementation: AlertImplementation): NativeModule {
    override val name = "Alert"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "present" -> {
                    val title = args.getString("title")
                    val message = if (args.isNull("message")) null else args.getString("message")
                    val buttons = args.get("buttons")
                    val style = args.getString("style")
                    implementation.present(title, message, buttons, style) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "show" -> {
                    val title = args.getString("title")
                    val message = if (args.isNull("message")) null else args.getString("message")
                    val buttons = args.get("buttons")
                    val style = args.getString("style")
                    implementation.show(title, message, buttons, style); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface AppStateImplementation {
    fun current_state(): String
}

class AppStateModuleAdapter(private val implementation: AppStateImplementation): NativeModule {
    override val name = "AppState"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "current_state" -> {
                    promise.resolve(implementation.current_state())
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface BatteryImplementation {
    fun get_level(): Double
    fun get_state(): String
}

class BatteryModuleAdapter(private val implementation: BatteryImplementation): NativeModule {
    override val name = "Battery"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "get_level" -> {
                    promise.resolve(implementation.get_level())
                }
                "get_state" -> {
                    promise.resolve(implementation.get_state())
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface BiometricsImplementation {
    fun authenticate(reason: String, completion: (Result<Boolean>) -> Unit)
    fun is_available(): Boolean
}

class BiometricsModuleAdapter(private val implementation: BiometricsImplementation): NativeModule {
    override val name = "Biometrics"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "authenticate" -> {
                    val reason = args.getString("reason")
                    implementation.authenticate(reason) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "is_available" -> {
                    promise.resolve(implementation.is_available())
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface CameraImplementation {
    fun pick_from_gallery(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit)
    fun take_photo(quality: Double, allow_editing: Boolean, completion: (Result<String?>) -> Unit)
}

class CameraModuleAdapter(private val implementation: CameraImplementation): NativeModule {
    override val name = "Camera"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "pick_from_gallery" -> {
                    val quality = args.getDouble("quality")
                    val allow_editing = args.getBoolean("allow_editing")
                    implementation.pick_from_gallery(quality, allow_editing) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "take_photo" -> {
                    val quality = args.getDouble("quality")
                    val allow_editing = args.getBoolean("allow_editing")
                    implementation.take_photo(quality, allow_editing) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface ClipboardImplementation {
    fun get_string(): String
    fun set_string(text: String): Unit
}

class ClipboardModuleAdapter(private val implementation: ClipboardImplementation): NativeModule {
    override val name = "Clipboard"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "get_string" -> {
                    promise.resolve(implementation.get_string())
                }
                "set_string" -> {
                    val text = args.getString("text")
                    implementation.set_string(text); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface DeviceImplementation {
    fun info(): Any
}

class DeviceModuleAdapter(private val implementation: DeviceImplementation): NativeModule {
    override val name = "Device"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "info" -> {
                    promise.resolve(implementation.info())
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface HapticsImplementation {
    fun cancel(): Unit
    fun impact(style: String): Unit
    fun notification(type: String): Unit
    fun selection(): Unit
    fun vibrate(duration_ms: Int): Unit
}

class HapticsModuleAdapter(private val implementation: HapticsImplementation): NativeModule {
    override val name = "Haptics"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "cancel" -> {
                    implementation.cancel(); promise.resolve(null)
                }
                "impact" -> {
                    val style = args.getString("style")
                    implementation.impact(style); promise.resolve(null)
                }
                "notification" -> {
                    val type = args.getString("type")
                    implementation.notification(type); promise.resolve(null)
                }
                "selection" -> {
                    implementation.selection(); promise.resolve(null)
                }
                "vibrate" -> {
                    val duration_ms = args.getInt("duration_ms")
                    implementation.vibrate(duration_ms); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface LinkingImplementation {
    fun can_open_url(url: String): Boolean
    fun open_settings(): Boolean
    fun open_url(url: String): Boolean
}

class LinkingModuleAdapter(private val implementation: LinkingImplementation): NativeModule {
    override val name = "Linking"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "can_open_url" -> {
                    val url = args.getString("url")
                    promise.resolve(implementation.can_open_url(url))
                }
                "open_settings" -> {
                    promise.resolve(implementation.open_settings())
                }
                "open_url" -> {
                    val url = args.getString("url")
                    promise.resolve(implementation.open_url(url))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface LocationImplementation {
    fun get_current(accuracy: Any, timeout: Double, completion: (Result<Any?>) -> Unit)
}

class LocationModuleAdapter(private val implementation: LocationImplementation): NativeModule {
    override val name = "Location"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "get_current" -> {
                    val accuracy = args.get("accuracy")
                    val timeout = args.getDouble("timeout")
                    implementation.get_current(accuracy, timeout) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface NetInfoImplementation {
    fun fetch(): Any?
}

class NetInfoModuleAdapter(private val implementation: NetInfoImplementation): NativeModule {
    override val name = "NetInfo"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "fetch" -> {
                    promise.resolve(implementation.fetch())
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface NotificationsImplementation {
    fun cancel(identifier: String, completion: (Result<Unit>) -> Unit)
    fun get_device_token(completion: (Result<String?>) -> Unit)
    fun request_permission(completion: (Result<Boolean>) -> Unit)
    fun schedule(title: String, body: String, delay_seconds: Double, identifier: String, completion: (Result<Boolean>) -> Unit)
}

class NotificationsModuleAdapter(private val implementation: NotificationsImplementation): NativeModule {
    override val name = "Notifications"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "cancel" -> {
                    val identifier = args.getString("identifier")
                    implementation.cancel(identifier) { result -> result.fold({ value -> promise.resolve(null) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "get_device_token" -> {
                    implementation.get_device_token() { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "request_permission" -> {
                    implementation.request_permission() { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                "schedule" -> {
                    val title = args.getString("title")
                    val body = args.getString("body")
                    val delay_seconds = args.getDouble("delay_seconds")
                    val identifier = args.getString("identifier")
                    implementation.schedule(title, body, delay_seconds, identifier) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface PermissionsImplementation {
    fun check(permission: String): String
    fun request(permission: String, completion: (Result<String>) -> Unit)
}

class PermissionsModuleAdapter(private val implementation: PermissionsImplementation): NativeModule {
    override val name = "Permissions"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "check" -> {
                    val permission = args.getString("permission")
                    promise.resolve(implementation.check(permission))
                }
                "request" -> {
                    val permission = args.getString("permission")
                    implementation.request(permission) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface SecureStoreImplementation {
    fun clear(): Unit
    fun delete_item(key: String): Boolean
    fun get_item(key: String): String?
    fun set_item(key: String, value: String): Boolean
}

class SecureStoreModuleAdapter(private val implementation: SecureStoreImplementation): NativeModule {
    override val name = "SecureStore"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "clear" -> {
                    implementation.clear(); promise.resolve(null)
                }
                "delete_item" -> {
                    val key = args.getString("key")
                    promise.resolve(implementation.delete_item(key))
                }
                "get_item" -> {
                    val key = args.getString("key")
                    promise.resolve(implementation.get_item(key))
                }
                "set_item" -> {
                    val key = args.getString("key")
                    val value = args.getString("value")
                    promise.resolve(implementation.set_item(key, value))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface ShareImplementation {
    fun share(message: String?, url: String?, title: String?, completion: (Result<Boolean>) -> Unit)
}

class ShareModuleAdapter(private val implementation: ShareImplementation): NativeModule {
    override val name = "Share"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "share" -> {
                    val message = if (args.isNull("message")) null else args.getString("message")
                    val url = if (args.isNull("url")) null else args.getString("url")
                    val title = if (args.isNull("title")) null else args.getString("title")
                    implementation.share(message, url, title) { result -> result.fold({ value -> promise.resolve(value) }, { error -> promise.reject(error.message ?: "Native call failed") }) }
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}

interface StorageImplementation {
    fun all_keys(): Any
    fun clear(): Unit
    fun delete(key: String): Unit
    fun get(key: String): String?
    fun set(key: String, value: String): Unit
}

class StorageModuleAdapter(private val implementation: StorageImplementation): NativeModule {
    override val name = "Storage"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            when (method) {
                "all_keys" -> {
                    promise.resolve(implementation.all_keys())
                }
                "clear" -> {
                    implementation.clear(); promise.resolve(null)
                }
                "delete" -> {
                    val key = args.getString("key")
                    implementation.delete(key); promise.resolve(null)
                }
                "get" -> {
                    val key = args.getString("key")
                    promise.resolve(implementation.get(key))
                }
                "set" -> {
                    val key = args.getString("key")
                    val value = args.getString("value")
                    implementation.set(key, value); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error.message ?: "Native call failed") }
    }
}
