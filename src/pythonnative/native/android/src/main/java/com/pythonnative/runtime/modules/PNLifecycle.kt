package com.pythonnative.runtime.modules

import android.app.Activity
import android.app.Application
import android.content.Intent
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNRegistry

/**
 * Application events a plugin can observe, the counterpart of Expo's
 * `ReactActivityLifecycleListener`. Every method has a default, so a hook
 * implements only what it needs. Register one from a plugin's `register` with
 * `registry.registerLifecycleHook`.
 *
 * Methods returning `Boolean` report whether the hook consumed the event.
 */
interface PNLifecycleHook {
    /** The process started, possibly with no activity (a push or background job). */
    fun onApplicationCreate(application: Application) {}
    fun onActivityCreated(activity: Activity) {}
    fun onNewIntent(intent: Intent): Boolean = false
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean = false
    fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray): Boolean = false
    fun onActivityResumed(activity: Activity) {}
    fun onActivityPaused(activity: Activity) {}
    fun onActivityStopped(activity: Activity) {}
    fun onActivityDestroyed(activity: Activity) {}
}

/** The registered hooks, called from `BuiltinModules` and the application class. */
object PNLifecycle {
    private val hooks = ArrayList<PNLifecycleHook>()

    internal fun add(hook: PNLifecycleHook) {
        hooks.add(hook)
    }

    fun forEach(action: (PNLifecycleHook) -> Unit) {
        PNRegistry.ensureBuiltins()
        hooks.toList().forEach(action)
    }

    /** Whether any hook consumed the event; every hook still sees it. */
    fun any(action: (PNLifecycleHook) -> Boolean): Boolean {
        PNRegistry.ensureBuiltins()
        return hooks.toList().map(action).any { it }
    }
}

/**
 * Starts Python for a plugin running with no activity. The app module owns
 * Chaquopy, so it installs [starter] from its `Application`; `ensureStarted`
 * is safe to call from any thread and runs at most once.
 */
object PNHeadless {
    @Volatile var starter: (() -> Unit)? = null

    /** Start Python if it isn't up, importing the app's entry module so its registrations run. */
    fun ensureStarted() {
        // Python's bridge opens the renderer core at startup, with or without a screen.
        com.pythonnative.runtime.core.PNCore.install(PNBridge.context())
        starter?.invoke()
    }
}
