package com.pythonnative.runtime

import android.app.Activity
import android.content.Context
import android.content.res.Configuration
import android.util.Log
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.bridge.ViewRegistry
import com.pythonnative.runtime.core.PNCore
import com.pythonnative.runtime.layout.Measurement
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.ModuleEnvelope
import com.pythonnative.runtime.modules.Promise
import com.pythonnative.runtime.screens.Viewport
import org.json.JSONObject

/**
 * The single Java class Python touches.
 *
 * Python commits, lays out, animates, and runs view commands through the
 * renderer core ([PNCore]), which it opens with ctypes; only native module
 * calls come here ([call], mirroring `pn_bridge_call` on iOS). Each hops to
 * the main thread for the duration of the call. Native-to-Python messages
 * go through a mailbox drained on a dedicated thread, so the main thread
 * never waits for Python.
 */
object PNBridge {
    /** Logcat tag used by the whole runtime. */
    const val TAG = "PythonNative"

    private val pythonQueue = java.util.concurrent.Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "PythonNative-events").apply { isDaemon = true }
    }
    @Volatile private var host: PythonHost? = null
    private var activity: Activity? = null
    private val hostReadyListeners = ArrayList<Runnable>()
    private val modulePromises = java.util.concurrent.ConcurrentHashMap<Long, Promise>()

    /** Tag to view bookkeeping shared by the mounter and managers. */
    val registry = ViewRegistry()

    private val continuousEvents = setOf("on_scroll", "on_window", "on_selection_change", "on_gesture_update")

    /** One queued callback; `continuous` is computed once, before the mailbox lock. */
    private class Message(val kind: String, val tag: Long, val name: String, val payload: String) {
        val continuous = kind == "event" && (name in continuousEvents ||
            name.startsWith("gesture:") && JSONObject(payload).optJSONArray("args")?.optJSONObject(0)?.optString("state") == "changed")
    }
    private val mailbox = java.util.ArrayDeque<Message>()
    private var draining = false

    /**
     * Install the Python callback target once Python has started. Delivers
     * the messages queued before it existed, then runs the host-ready
     * listeners.
     */
    @JvmStatic
    fun setHost(host: PythonHost) {
        val pending = synchronized(hostReadyListeners) {
            this.host = host
            ArrayList(hostReadyListeners).also { hostReadyListeners.clear() }
        }
        scheduleDrain()
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
        val ready = synchronized(hostReadyListeners) {
            (host != null).also { if (!it) hostReadyListeners.add(runnable) }
        }
        if (ready) runnable.run()
    }

    /**
     * Record the current activity; modules and managers derive their
     * `Context` from it. The first call also loads the renderer core, so it
     * must happen before Python starts.
     */
    @JvmStatic
    fun setContext(activity: Activity) {
        this.activity = activity
        PNRegistry.ensureBuiltins()
        PNCore.install(activity)
        Measurement.prepare(activity)
        BuiltinModules.onContextAttached(activity)
    }

    /**
     * Apply a configuration change the activity handled in place (the
     * template declares `android:configChanges`, so rotation, dark mode,
     * font scale, density, and locale changes don't recreate it). Screens
     * publish their new `layout` themselves; this re-measures text and
     * widgets, re-reads reduce motion, and tells Python about the new
     * appearance and locale.
     */
    @JvmStatic
    fun configurationChanged(activity: Activity, previous: Configuration?, current: Configuration) {
        Measurement.configurationChanged(activity)
        PNCore.updateReduceMotion(activity)
        callPython("host", 0, "appearance", Viewport.describe(activity.window.decorView).toString())
        if (previous == null || previous.locales != current.locales) BuiltinModules.localization.publish()
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

    /**
     * Call a native module method; `argsJson` is `{"call_id": n, "args": {...}}`.
     * Pending mount transactions apply first, so a module sees every view
     * Python committed before the call (`Host.attach_root`).
     */
    @JvmStatic
    fun call(module: String, method: String, argsJson: String): String? {
        if (!MainThread.isMain()) return MainThread.call { call(module, method, argsJson) }
        PNCore.drainMounts()
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
            .put("protocol", PNCore.protocolVersion()).put("yoga", com.pythonnative.generated.PNContracts.yogaVersion)
            .put("schema", com.pythonnative.generated.PNContracts.fingerprint)).toString()
        val target = PNRegistry.module(module)
            ?: return ModuleEnvelope.error("unknown module '$module'", "unknown_module")
        if (!com.pythonnative.generated.PNContracts.validateModule(module, method, args))
            return ModuleEnvelope.error("Invalid native method arguments", "invalid_arguments")
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
     * Queue one callback for Python. Messages are delivered in order on the
     * events thread; consecutive continuous events for the same view
     * coalesce. Messages sent before Python has started wait for [setHost].
     * View events reach this through the core (`PNCore.event`), which stamps
     * them; any thread may call it.
     */
    fun callPython(kind: String, tag: Long, name: String, payloadJson: String) {
        val message = Message(kind, tag, name, payloadJson)
        synchronized(mailbox) {
            val last = mailbox.peekLast()
            if (message.continuous && last?.continuous == true && last.tag == tag && last.name == name) mailbox.removeLast()
            mailbox.addLast(message)
        }
        scheduleDrain()
    }

    private fun scheduleDrain() {
        val target = host ?: return
        val schedule = synchronized(mailbox) {
            val needed = !draining && mailbox.isNotEmpty()
            if (needed) draining = true
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
    }

    // ------------------------------------------------------------------
    // Threading helpers
    // ------------------------------------------------------------------

    /** Whether the caller is on the main thread. */
    fun isMainThread(): Boolean = MainThread.isMain()

    /** Post `runnable` to the main thread. */
    fun post(runnable: Runnable) = MainThread.post(runnable)
}
