package com.pythonnative.android_template

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.PythonHost
import com.pythonnative.runtime.modules.PNHeadless
import com.pythonnative.runtime.modules.PNLifecycle

/**
 * Runs before any activity, so plugins can observe a process started for a
 * push message or a background job, and start Python without a screen.
 */
class PNApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        PNBridge.setApplicationContext(this)
        PNHeadless.starter = { PythonStartup.start(this) }
        PNLifecycle.forEach { it.onApplicationCreate(this) }
    }
}

/**
 * Starts the embedded runtime at most once, from whichever arrives first:
 * the activity's launch or a plugin running headless.
 */
object PythonStartup {
    private var started = false

    @Synchronized
    fun start(application: Application) {
        if (started) return
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(application))
        }
        val py = Python.getInstance()
        val filesDir = application.filesDir.absolutePath
        if (BuildConfig.DEBUG) {
            // Dev-only: the writable source overlay the dev client syncs
            // into. The dev server arrives as a connect link
            // (`pn-<app id>://connect?url=...`) through `Linking`.
            py.getModule("pythonnative.hot_reload").callAttr("configure_dev_environment", filesDir)
        }
        // Handshake with the runtime library (raises on a protocol
        // mismatch, before any screen is created), enable dev mode in
        // debug builds, warm the asyncio runtime, and import the entry
        // module so a broken app fails here with a full traceback.
        val entry = application.getString(R.string.pn_entry_module)
        py.getModule("pythonnative.bootstrap").callAttr("start", BuildConfig.DEBUG, true, entry)
        // Installing the host delivers the messages screens queued meanwhile.
        val bridge = py.getModule("pythonnative.bridge")
        PNBridge.setHost(object : PythonHost {
            override fun callback(kind: String, tag: Long, name: String, payloadJson: String) {
                bridge.callAttr("native_callback", kind, tag, name, payloadJson)
            }
        })
        started = true
    }
}
