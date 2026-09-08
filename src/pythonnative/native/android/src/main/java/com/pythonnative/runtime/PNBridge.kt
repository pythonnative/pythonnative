package com.pythonnative.runtime

import android.app.Activity
import android.content.Context
import android.util.Log
import com.pythonnative.runtime.animation.PNAnimator
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.bridge.TransactionApplier
import com.pythonnative.runtime.bridge.ViewRegistry
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.ModuleEnvelope
import com.pythonnative.runtime.modules.Promise
import org.json.JSONObject
import java.util.Locale

/**
 * The single Java class Python touches.
 *
 * Every entry point mirrors one C symbol of the iOS bridge and is
 * expected to run on the main thread (Python's asyncio loop lives
 * there). Calls from other threads are logged but still executed so a
 * misbehaving caller fails loudly in logcat instead of silently.
 */
object PNBridge {
    /** Logcat tag used by the whole runtime. */
    const val TAG = "PythonNative"

    /** Protocol version compiled into this library. */
    const val PROTOCOL_VERSION = 2

    private val pythonQueue = java.util.concurrent.Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "PythonNative-events").apply { isDaemon = true }
    }
    @Volatile private var host: PythonHost? = null
    private var activity: Activity? = null
    private val hostReadyListeners = ArrayList<Runnable>()
    private val modulePromises = java.util.concurrent.ConcurrentHashMap<Long, Promise>()

    /** Tag to view bookkeeping shared by the applier and managers. */
    val registry = ViewRegistry()

    private data class Message(val kind: String, val tag: Long, val name: String, val payload: String) {
        val continuous get() = kind == "event" && (name in setOf("on_scroll", "on_selection_change", "on_gesture_update") ||
            name.startsWith("gesture:") && JSONObject(payload).optJSONArray("args")?.optJSONObject(0)?.optString("state") == "changed")
    }
    private val mailbox = java.util.ArrayDeque<Message>()
    private var draining = false

    private val commits = com.pythonnative.runtime.bridge.CommitState()
    private val applier by lazy { TransactionApplier(registry) }

    /** The protocol version Python must match before starting. */
    @JvmStatic
    fun protocolVersion(): Int = PROTOCOL_VERSION

    /** Install the Python callback target; flushes callbacks queued before it existed. */
    @JvmStatic
    fun setHost(host: PythonHost) {
        this.host = host
        val pending = ArrayList(hostReadyListeners)
        hostReadyListeners.clear()
        for (listener in pending) {
            try {
                listener.run()
            } catch (e: Exception) {
                Log.e(TAG, "host-ready listener failed", e)
            }
        }
    }

    /** Whether a [PythonHost] has been installed. */
    fun hasHost(): Boolean = host != null

    /** Run `runnable` now if a host is installed, otherwise once [setHost] is called. */
    fun runWhenHostReady(runnable: Runnable) {
        if (host != null) runnable.run() else hostReadyListeners.add(runnable)
    }

    /** Record the current activity; modules and managers derive their `Context` from it. */
    @JvmStatic
    fun setContext(activity: Activity) {
        this.activity = activity
        PNRegistry.ensureBuiltins()
        BuiltinModules.onContextAttached(activity)
    }

    /** Forget `activity` if it is the current one (called from `Activity.onDestroy`). */
    @JvmStatic
    fun clearContext(activity: Activity) {
        if (this.activity === activity) this.activity = null
    }

    /** The current activity, or `null` before [setContext]. */
    fun activity(): Activity? = activity

    /** The context used to create views; throws before [setContext]. */
    fun context(): Context =
        activity ?: throw IllegalStateException("PNBridge.setContext(activity) has not been called")

    /** Display density of the current context (1.0 when no context is attached). */
    fun density(): Float {
        val ctx = activity ?: return 1f
        val d = ctx.resources.displayMetrics.density
        return if (d > 0f) d else 1f
    }

    // ------------------------------------------------------------------
    // Python -> native
    // ------------------------------------------------------------------

    /** Apply one serialized transaction (a JSON array of ops). */
    @JvmStatic
    fun apply(transactionJson: String): String {
        if (!MainThread.isMain()) return MainThread.call { apply(transactionJson) }
        return commits.apply(transactionJson, applier)
    }

    /**
     * Measure the view with `tag` under the given constraints (dp; `1e6`
     * means unconstrained) and return `"w,h"` in dp.
     */
    @JvmStatic
    fun measure(tag: Long, maxWidth: Double, maxHeight: Double): String {
        if (!MainThread.isMain()) return MainThread.call { measure(tag, maxWidth, maxHeight) }
        val record = registry.get(tag)
        if (record == null) {
            Log.w(TAG, "measure: unknown tag $tag")
            return "0,0"
        }
        val size = try {
            record.manager.measure(record.view, maxWidth, maxHeight)
        } catch (e: Exception) {
            Log.e(TAG, "measure failed for ${record.typeName}#$tag", e)
            floatArrayOf(0f, 0f)
        }
        return String.format(Locale.US, "%.3f,%.3f", size[0], size[1])
    }

    /** Run an imperative command on one view and return its JSON result. */
    @JvmStatic
    fun command(tag: Long, name: String, argsJson: String): String? {
        if (!MainThread.isMain()) return MainThread.call { command(tag, name, argsJson) }
        val record = registry.get(tag) ?: return null
        return try {
            val args = if (argsJson.isBlank()) JSONObject() else JSONObject(argsJson)
            JsonUtil.encode(record.manager.command(record.view, name, args))
        } catch (e: Exception) {
            Log.e(TAG, "command '$name' failed for ${record.typeName}#$tag", e)
            null
        }
    }

    /** Handle an animation request (`set`, `start`, or `cancel`) for one view. */
    @JvmStatic
    fun animate(tag: Long, requestJson: String): String? {
        if (!MainThread.isMain()) return MainThread.call { animate(tag, requestJson) }
        val record = registry.get(tag) ?: return null
        return try {
            PNAnimator.handle(record, JSONObject(requestJson))
        } catch (e: Exception) {
            Log.e(TAG, "animate failed for ${record.typeName}#$tag: $requestJson", e)
            null
        }
    }

    /** Call a native module method; `argsJson` is `{"call_id": n, "args": {...}}`. */
    @JvmStatic
    fun call(module: String, method: String, argsJson: String): String? {
        if (!MainThread.isMain()) return MainThread.call { call(module, method, argsJson) }
        val (callId, args) = try {
            ModuleEnvelope.decodeCall(argsJson)
        } catch (e: Exception) {
            return ModuleEnvelope.error("malformed call envelope: ${e.message}", "bad_request")
        }
        if (method == "_pn_cancel") {
            modulePromises.remove(args.optLong("call_id"))?.takeIf { it.module == module }?.cancel()
            return ModuleEnvelope.ok(null)
        }
        if (module == "Runtime") return JSONObject().put("ok", true).put("value", JSONObject()
            .put("protocol", 2).put("yoga", "3.2.1").put("schema", com.pythonnative.generated.PNContracts.fingerprint)
            .put("animation_graph", true).put("logical_lists", true).put("native_layout", true)).toString()
        if (module == "Layout") return JSONObject().put("ok", true).put("value",
            com.pythonnative.runtime.layout.NativeLayout.compute(args)).toString()
        val target = PNRegistry.module(module)
            ?: return ModuleEnvelope.error("unknown module '$module'", "unknown_module")
        val promise = Promise(callId, module)
        if (callId > 0) {
            modulePromises[callId] = promise
            promise.onFinished = { modulePromises.remove(callId) }
        }
        try {
            target.call(method, args, promise)
        } catch (e: Exception) {
            Log.e(TAG, "module $module.$method threw", e)
            if (!promise.isSettled) promise.reject(e.message ?: e.toString(), "exception")
        }
        return promise.markReturned()
    }

    // ------------------------------------------------------------------
    // native -> Python
    // ------------------------------------------------------------------

    /**
     * Deliver one callback to Python. Returns `null` when no host is
     * installed or the Python handler raised (the error is logged).
     */
    fun callPython(kind: String, tag: Long, name: String, payloadJson: String): String? {
        val target = host
        if (target == null) {
            Log.w(TAG, "callPython($kind, $tag, $name) dropped: no PythonHost installed")
            return null
        }
        if (kind == "event") com.pythonnative.runtime.animation.AnimationGraph.event(tag, name, org.json.JSONArray(payloadJson))
        var editRevision = 0L
        if (kind == "event" && name == "on_change") registry.get(tag)?.let { record ->
            if (record.typeName == "TextInput") {
                editRevision = ((record.state["edit_revision"] as? Number)?.toLong() ?: 0L) + 1L
                record.state["edit_revision"] = editRevision
            }
        }
        val payload = if (kind == "event") commits.event(org.json.JSONArray(payloadJson), editRevision) else payloadJson
        val message = Message(kind, tag, name, payload)
        val schedule = synchronized(mailbox) {
            val last = mailbox.peekLast()
            if (message.continuous && last?.continuous == true && last.tag == tag && last.name == name) mailbox.removeLast()
            mailbox.addLast(message)
            val needed = !draining
            draining = true
            needed
        }
        if (schedule) pythonQueue.execute {
            while (true) {
                val next = synchronized(mailbox) {
                    mailbox.pollFirst().also { if (it == null) draining = false }
                } ?: break
                try { target.callback(next.kind, next.tag, next.name, next.payload) }
                catch (error: Exception) { Log.e(TAG, "Python callback ${next.kind}/${next.name} raised", error) }
            }
        }
        return null
    }

    // ------------------------------------------------------------------
    // Threading helpers
    // ------------------------------------------------------------------

    /** Whether the caller is on the main thread. */
    fun isMainThread(): Boolean = MainThread.isMain()

    /** Post `runnable` to the main thread. */
    fun post(runnable: Runnable) = MainThread.post(runnable)

    private fun assertMain(entry: String) {
        if (!MainThread.isMain()) {
            Log.w(TAG, "PNBridge.$entry called off the main thread (${Thread.currentThread().name})")
        }
    }
}
