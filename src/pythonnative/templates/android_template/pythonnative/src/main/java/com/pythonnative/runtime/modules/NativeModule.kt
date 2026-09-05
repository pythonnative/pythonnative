package com.pythonnative.runtime.modules

import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import org.json.JSONObject

/**
 * A named native module exposing methods to Python through
 * `PNBridge.call(module, method, argsJson)`.
 *
 * Implementations settle the [Promise] synchronously (the result is
 * returned inline) or later from any thread (the result is delivered
 * as a `module` callback on the main thread). Unknown methods should
 * call [Promise.rejectUnknownMethod].
 */
interface NativeModule {
    /** The module name Python addresses, for example `"Clipboard"`. */
    val name: String

    /** Handle one call; must settle `promise` exactly once (now or later). */
    fun call(method: String, args: JSONObject, promise: Promise)
}

/**
 * Result envelopes for module calls and events, as JSON strings.
 */
object ModuleEnvelope {
    /** Decode `{"call_id": n, "args": {...}}` into `(callId, args)`. */
    fun decodeCall(argsJson: String): Pair<Long, JSONObject> {
        val obj = if (argsJson.isBlank()) JSONObject() else JSONObject(argsJson)
        val callId = obj.optLong("call_id", 0L)
        val args = obj.optJSONObject("args") ?: JSONObject()
        return callId to args
    }

    /** `{"ok": true, "value": ...}` */
    fun ok(value: Any?): String = JSONObject().put("ok", true).put("value", JsonUtil.wrap(value)).toString()

    /** `{"ok": false, "error": message, "code": code}` */
    fun error(message: String, code: String? = null): String {
        val obj = JSONObject().put("ok", false).put("error", message)
        if (code != null) obj.put("code", code)
        return obj.toString()
    }

    /** `{"pending": true}` */
    fun pending(): String = JSONObject().put("pending", true).toString()

    /** `{"call_id": n, "ok": true, "value": ...}` for asynchronous settlement. */
    fun settled(callId: Long, value: Any?): String =
        JSONObject().put("call_id", callId).put("ok", true).put("value", JsonUtil.wrap(value)).toString()

    /** `{"call_id": n, "ok": false, "error": message, "code": code}` for asynchronous rejection. */
    fun settledError(callId: Long, message: String, code: String?): String {
        val obj = JSONObject().put("call_id", callId).put("ok", false).put("error", message)
        if (code != null) obj.put("code", code)
        return obj.toString()
    }

    /** `{"event": name, "payload": {...}}` */
    fun event(event: String, payload: Any?): String =
        JSONObject().put("event", event).put("payload", JsonUtil.wrap(payload)).toString()
}

/**
 * The settlement handle for one module call.
 *
 * If [resolve] or [reject] runs before the module's `call` returns,
 * the result is returned inline to Python. Otherwise Python receives
 * `{"pending": true}` and the eventual settlement is delivered on the
 * main thread as a `module` callback carrying the `call_id`.
 */
class Promise(val callId: Long, val module: String, private val dispatch: (Runnable) -> Unit = defaultDispatcher) {
    private var returned = false
    private var settledInline: String? = null

    /** Whether the promise has been resolved or rejected. */
    var isSettled = false
        private set

    /** Resolve with `value` (JSON-encodable: primitives, maps, lists, `JSONObject`). */
    fun resolve(value: Any?) {
        if (isSettled) return
        isSettled = true
        if (!returned) {
            settledInline = ModuleEnvelope.ok(value)
        } else {
            deliver(ModuleEnvelope.settled(callId, value))
        }
    }

    /** Reject with `message` and an optional machine-readable `code`. */
    fun reject(message: String, code: String? = null) {
        if (isSettled) return
        isSettled = true
        if (!returned) {
            settledInline = ModuleEnvelope.error(message, code)
        } else {
            deliver(ModuleEnvelope.settledError(callId, message, code))
        }
    }

    /** Reject because the module has no method named `method`. */
    fun rejectUnknownMethod(method: String) = reject("$module has no method '$method'", "unknown_method")

    /**
     * Called by the bridge after `call` returns: yields the inline
     * envelope when already settled, otherwise `{"pending": true}` and
     * arms asynchronous delivery.
     */
    fun markReturned(): String {
        returned = true
        return settledInline ?: ModuleEnvelope.pending()
    }

    private fun deliver(payload: String) {
        val moduleName = module
        dispatch(Runnable { PNBridge.callPython("module", 0, moduleName, payload) })
    }

    companion object {
        /** How asynchronous settlements reach the main thread (replaceable in tests). */
        var defaultDispatcher: (Runnable) -> Unit = { MainThread.post(it) }
    }
}

/** Unsolicited module events (`{"event": name, "payload": {...}}`). */
object ModuleEvents {
    /** Emit `event` for `module` on the main thread (posting if needed). */
    fun emit(module: String, event: String, payload: Any?) {
        val json = ModuleEnvelope.event(event, payload)
        MainThread.runOnMain { PNBridge.callPython("module", 0, module, json) }
    }
}
