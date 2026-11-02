package com.pythonnative.generated

import org.json.JSONObject
import com.pythonnative.runtime.modules.NativeModule
import com.pythonnative.runtime.modules.Promise

interface AccessibilityInfoImplementation {
    fun `announce`(`message`: String): Unit
    fun `is_reduce_motion_enabled`(): Boolean
    fun `is_screen_reader_enabled`(): Boolean
    fun `set_accessibility_focus`(`tag`: Long): Unit
}

class AccessibilityInfoModuleAdapter(private val implementation: AccessibilityInfoImplementation): NativeModule {
    override val name = "AccessibilityInfo"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "announce" -> {
                    val `message` = PNValues.string((args.opt("message")))
                    implementation.`announce`(`message`); promise.resolve(null)
                }
                "is_reduce_motion_enabled" -> {
                    promise.resolve(PNValues.encode(implementation.`is_reduce_motion_enabled`()))
                }
                "is_screen_reader_enabled" -> {
                    promise.resolve(PNValues.encode(implementation.`is_screen_reader_enabled`()))
                }
                "set_accessibility_focus" -> {
                    val `tag` = PNValues.integer((args.opt("tag")))
                    implementation.`set_accessibility_focus`(`tag`); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object AccessibilityInfoEvents {
    fun `change`(payload: Map<String, PNJSONValue>) = com.pythonnative.runtime.modules.ModuleEvents.emit("AccessibilityInfo", "change", PNValues.encode(payload))
}

interface AlertImplementation {
    fun `present`(`title`: String, `message`: String?, `buttons`: List<Map<String, PNJSONValue>>, `style`: String, completion: (Result<Long>) -> Unit): (() -> Unit)?
    fun `show`(`title`: String, `message`: String?, `buttons`: List<Map<String, PNJSONValue>>, `style`: String): Unit
}

class AlertModuleAdapter(private val implementation: AlertImplementation): NativeModule {
    override val name = "Alert"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "present" -> {
                    val `title` = PNValues.string((args.opt("title")))
                    val `message` = if (PNValues.isNull((args.opt("message")))) null else PNValues.string((args.opt("message")))
                    val `buttons` = PNValues.array((args.opt("buttons"))).map { item -> PNValues.objectValue(item).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } } }
                    val `style` = PNValues.string((args.opt("style")))
                    val cancellation = implementation.`present`(`title`, `message`, `buttons`, `style`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                "show" -> {
                    val `title` = PNValues.string((args.opt("title")))
                    val `message` = if (PNValues.isNull((args.opt("message")))) null else PNValues.string((args.opt("message")))
                    val `buttons` = PNValues.array((args.opt("buttons"))).map { item -> PNValues.objectValue(item).let { objectValue -> objectValue.keys().asSequence().associateWith { key -> PNJSONValue(objectValue.get(key) ?: JSONObject.NULL) } } }
                    val `style` = PNValues.string((args.opt("style")))
                    implementation.`show`(`title`, `message`, `buttons`, `style`); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface AppStateImplementation {
    fun `current_state`(): String
}

class AppStateModuleAdapter(private val implementation: AppStateImplementation): NativeModule {
    override val name = "AppState"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "current_state" -> {
                    promise.resolve(PNValues.encode(implementation.`current_state`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object AppStateEvents {
    fun `change`(payload: String) = com.pythonnative.runtime.modules.ModuleEvents.emit("AppState", "change", PNValues.encode(payload))
}

interface AssetsImplementation {
    fun `configure`(`overlay`: String?, `manifest`: PNAssetManifest): Unit
    fun `exists`(`path`: String): Boolean
    fun `read`(`path`: String): String?
}

class AssetsModuleAdapter(private val implementation: AssetsImplementation): NativeModule {
    override val name = "Assets"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "configure" -> {
                    val `overlay` = if (PNValues.isNull((args.opt("overlay")))) null else PNValues.string((args.opt("overlay")))
                    val `manifest` = PNAssetManifest.decode((args.opt("manifest")))
                    implementation.`configure`(`overlay`, `manifest`); promise.resolve(null)
                }
                "exists" -> {
                    val `path` = PNValues.string((args.opt("path")))
                    promise.resolve(PNValues.encode(implementation.`exists`(`path`)))
                }
                "read" -> {
                    val `path` = PNValues.string((args.opt("path")))
                    promise.resolve(PNValues.encode(implementation.`read`(`path`)))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface BatteryImplementation {
    fun `get_level`(): Double
    fun `get_state`(): String
}

class BatteryModuleAdapter(private val implementation: BatteryImplementation): NativeModule {
    override val name = "Battery"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "get_level" -> {
                    promise.resolve(PNValues.encode(implementation.`get_level`()))
                }
                "get_state" -> {
                    promise.resolve(PNValues.encode(implementation.`get_state`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object BatteryEvents {
    fun `change`(payload: Map<String, PNJSONValue>) = com.pythonnative.runtime.modules.ModuleEvents.emit("Battery", "change", PNValues.encode(payload))
}

interface ClipboardImplementation {
    fun `get_string`(): String
    fun `set_string`(`text`: String): Unit
}

class ClipboardModuleAdapter(private val implementation: ClipboardImplementation): NativeModule {
    override val name = "Clipboard"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "get_string" -> {
                    promise.resolve(PNValues.encode(implementation.`get_string`()))
                }
                "set_string" -> {
                    val `text` = PNValues.string((args.opt("text")))
                    implementation.`set_string`(`text`); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface DeviceImplementation {
    fun `info`(): Map<String, PNJSONValue>
}

class DeviceModuleAdapter(private val implementation: DeviceImplementation): NativeModule {
    override val name = "Device"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "info" -> {
                    promise.resolve(PNValues.encode(implementation.`info`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface HapticsImplementation {
    fun `cancel`(): Unit
    fun `impact`(`style`: String): Unit
    fun `notification`(`type`: String): Unit
    fun `selection`(): Unit
    fun `vibrate`(`duration_ms`: Long): Unit
}

class HapticsModuleAdapter(private val implementation: HapticsImplementation): NativeModule {
    override val name = "Haptics"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "cancel" -> {
                    implementation.`cancel`(); promise.resolve(null)
                }
                "impact" -> {
                    val `style` = PNValues.string((if (args.has("style")) args.opt("style") else PNValues.defaultValue("\"medium\"")))
                    implementation.`impact`(`style`); promise.resolve(null)
                }
                "notification" -> {
                    val `type` = PNValues.string((if (args.has("type")) args.opt("type") else PNValues.defaultValue("\"success\"")))
                    implementation.`notification`(`type`); promise.resolve(null)
                }
                "selection" -> {
                    implementation.`selection`(); promise.resolve(null)
                }
                "vibrate" -> {
                    val `duration_ms` = PNValues.integer((if (args.has("duration_ms")) args.opt("duration_ms") else PNValues.defaultValue("400")))
                    implementation.`vibrate`(`duration_ms`); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface ImagesImplementation {
    fun `clear_cache`(): Unit
    fun `get_size`(`uri`: String, completion: (Result<PNImageSize>) -> Unit): (() -> Unit)?
    fun `prefetch`(`uri`: String, completion: (Result<Boolean>) -> Unit): (() -> Unit)?
}

class ImagesModuleAdapter(private val implementation: ImagesImplementation): NativeModule {
    override val name = "Images"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "clear_cache" -> {
                    implementation.`clear_cache`(); promise.resolve(null)
                }
                "get_size" -> {
                    val `uri` = PNValues.string((args.opt("uri")))
                    val cancellation = implementation.`get_size`(`uri`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                "prefetch" -> {
                    val `uri` = PNValues.string((args.opt("uri")))
                    val cancellation = implementation.`prefetch`(`uri`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface KeyboardImplementation {
    fun `dismiss`(): Unit
    fun `is_visible`(): Boolean
}

class KeyboardModuleAdapter(private val implementation: KeyboardImplementation): NativeModule {
    override val name = "Keyboard"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "dismiss" -> {
                    implementation.`dismiss`(); promise.resolve(null)
                }
                "is_visible" -> {
                    promise.resolve(PNValues.encode(implementation.`is_visible`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object KeyboardEvents {
    fun `change`(payload: Map<String, PNJSONValue>) = com.pythonnative.runtime.modules.ModuleEvents.emit("Keyboard", "change", PNValues.encode(payload))
}

interface LinkingImplementation {
    fun `can_open_url`(`url`: String): Boolean
    fun `open_settings`(): Boolean
    fun `open_url`(`url`: String): Boolean
}

class LinkingModuleAdapter(private val implementation: LinkingImplementation): NativeModule {
    override val name = "Linking"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "can_open_url" -> {
                    val `url` = PNValues.string((args.opt("url")))
                    promise.resolve(PNValues.encode(implementation.`can_open_url`(`url`)))
                }
                "open_settings" -> {
                    promise.resolve(PNValues.encode(implementation.`open_settings`()))
                }
                "open_url" -> {
                    val `url` = PNValues.string((args.opt("url")))
                    promise.resolve(PNValues.encode(implementation.`open_url`(`url`)))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object LinkingEvents {
    fun `url`(payload: String) = com.pythonnative.runtime.modules.ModuleEvents.emit("Linking", "url", PNValues.encode(payload))
}

interface LocalizationImplementation {
    fun `get_locales`(): List<Map<String, PNJSONValue>>
    fun `get_timezone`(): String
}

class LocalizationModuleAdapter(private val implementation: LocalizationImplementation): NativeModule {
    override val name = "Localization"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "get_locales" -> {
                    promise.resolve(PNValues.encode(implementation.`get_locales`()))
                }
                "get_timezone" -> {
                    promise.resolve(PNValues.encode(implementation.`get_timezone`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object LocalizationEvents {
    fun `change`(payload: Map<String, PNJSONValue>) = com.pythonnative.runtime.modules.ModuleEvents.emit("Localization", "change", PNValues.encode(payload))
}

interface NetInfoImplementation {
    fun `fetch`(): Map<String, PNJSONValue>?
}

class NetInfoModuleAdapter(private val implementation: NetInfoImplementation): NativeModule {
    override val name = "NetInfo"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "fetch" -> {
                    promise.resolve(PNValues.encode(implementation.`fetch`()))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

object NetInfoEvents {
    fun `change`(payload: Map<String, PNJSONValue>) = com.pythonnative.runtime.modules.ModuleEvents.emit("NetInfo", "change", PNValues.encode(payload))
}

interface PermissionsImplementation {
    fun `check`(`permission`: String, completion: (Result<String>) -> Unit): (() -> Unit)?
    fun `request`(`permission`: String, completion: (Result<String>) -> Unit): (() -> Unit)?
}

class PermissionsModuleAdapter(private val implementation: PermissionsImplementation): NativeModule {
    override val name = "Permissions"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "check" -> {
                    val `permission` = PNValues.string((args.opt("permission")))
                    val cancellation = implementation.`check`(`permission`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                "request" -> {
                    val `permission` = PNValues.string((args.opt("permission")))
                    val cancellation = implementation.`request`(`permission`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface SecureStoreImplementation {
    fun `clear`(): Unit
    fun `delete_item`(`key`: String): Boolean
    fun `get_item`(`key`: String): String?
    fun `set_item`(`key`: String, `value`: String): Boolean
}

class SecureStoreModuleAdapter(private val implementation: SecureStoreImplementation): NativeModule {
    override val name = "SecureStore"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "clear" -> {
                    implementation.`clear`(); promise.resolve(null)
                }
                "delete_item" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    promise.resolve(PNValues.encode(implementation.`delete_item`(`key`)))
                }
                "get_item" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    promise.resolve(PNValues.encode(implementation.`get_item`(`key`)))
                }
                "set_item" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    val `value` = PNValues.string((args.opt("value")))
                    promise.resolve(PNValues.encode(implementation.`set_item`(`key`, `value`)))
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface ShareImplementation {
    fun `share`(`message`: String?, `url`: String?, `title`: String?, completion: (Result<Boolean>) -> Unit): (() -> Unit)?
}

class ShareModuleAdapter(private val implementation: ShareImplementation): NativeModule {
    override val name = "Share"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "share" -> {
                    val `message` = if (PNValues.isNull((if (args.has("message")) args.opt("message") else PNValues.defaultValue("null")))) null else PNValues.string((if (args.has("message")) args.opt("message") else PNValues.defaultValue("null")))
                    val `url` = if (PNValues.isNull((if (args.has("url")) args.opt("url") else PNValues.defaultValue("null")))) null else PNValues.string((if (args.has("url")) args.opt("url") else PNValues.defaultValue("null")))
                    val `title` = if (PNValues.isNull((if (args.has("title")) args.opt("title") else PNValues.defaultValue("null")))) null else PNValues.string((if (args.has("title")) args.opt("title") else PNValues.defaultValue("null")))
                    val cancellation = implementation.`share`(`message`, `url`, `title`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface StorageImplementation {
    fun `all_keys`(): List<String>
    fun `clear`(): Unit
    fun `delete`(`key`: String): Unit
    fun `get`(`key`: String): String?
    fun `set`(`key`: String, `value`: String): Unit
}

class StorageModuleAdapter(private val implementation: StorageImplementation): NativeModule {
    override val name = "Storage"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "all_keys" -> {
                    promise.resolve(PNValues.encode(implementation.`all_keys`()))
                }
                "clear" -> {
                    implementation.`clear`(); promise.resolve(null)
                }
                "delete" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    implementation.`delete`(`key`); promise.resolve(null)
                }
                "get" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    promise.resolve(PNValues.encode(implementation.`get`(`key`)))
                }
                "set" -> {
                    val `key` = PNValues.string((args.opt("key")))
                    val `value` = PNValues.string((args.opt("value")))
                    implementation.`set`(`key`, `value`); promise.resolve(null)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}

interface WebViewsImplementation {
    fun `eval_js`(`tag`: Long, `script`: String, completion: (Result<String>) -> Unit): (() -> Unit)?
}

class WebViewsModuleAdapter(private val implementation: WebViewsImplementation): NativeModule {
    override val name = "WebViews"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        try {
            require(PNContracts.validateModule(name, method, args)) { "Invalid native arguments" }
            when (method) {
                "eval_js" -> {
                    val `tag` = PNValues.integer((args.opt("tag")))
                    val `script` = PNValues.string((args.opt("script")))
                    val cancellation = implementation.`eval_js`(`tag`, `script`) { result ->
                        try {
                        result.fold({ value -> promise.resolve(PNValues.encode(value)) }, { error -> promise.reject(error) })
                        } catch (error: Exception) { promise.reject(error.message ?: "Invalid native result") }
                    }
                    if (cancellation != null) promise.onCancel(cancellation)
                }
                else -> promise.rejectUnknownMethod(method)
            }
        } catch (error: Exception) { promise.reject(error) }
    }
}
