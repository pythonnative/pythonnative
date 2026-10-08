package com.pythonnative.android_template

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.util.Log
import android.util.TypedValue
import android.view.View
import android.view.ViewTreeObserver
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.PythonHost
import com.pythonnative.runtime.modules.BuiltinModules

/**
 * The single activity. It starts Python on a background thread (the
 * protocol handshake and the entry module import included), then wires the
 * `PNBridge` host callback into `pythonnative.bridge.native_callback`, and
 * forwards activity callbacks to the Kotlin native modules. The main thread
 * never waits for Python: screens live in `ScreenFragment`s inside the
 * `NavHostFragment` from `activity_main.xml`, and their messages wait in the
 * bridge's mailbox until the host is installed, while the system splash
 * screen stays up.
 */
class MainActivity : AppCompatActivity() {
    private val TAG = javaClass.simpleName
    @Volatile private var pythonReady = false
    private var settled = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate() called")
        PNBridge.setContext(this)

        // Keep the splash screen (the window background before Android 12)
        // drawn until Python has started.
        val content = findViewById<View>(android.R.id.content)
        content.viewTreeObserver.addOnPreDrawListener(object : ViewTreeObserver.OnPreDrawListener {
            override fun onPreDraw(): Boolean {
                if (!settled) return false
                content.viewTreeObserver.removeOnPreDrawListener(this)
                return true
            }
        })

        // The NavHost loads the initial screen from nav_graph's startDestination.
        setContentView(R.layout.activity_main)

        val devServer = intent?.getStringExtra("pn_dev_server")
        val entry = getString(R.string.pn_entry_module)
        startup.execute {
            val failure = runCatching { startPython(devServer, entry) }.exceptionOrNull()
            runOnUiThread { pythonStarted(failure) }
        }
    }

    /** Runs on the startup thread: everything here may take a while. */
    private fun startPython(devServer: String?, entry: String) {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(applicationContext))
        }
        val py = Python.getInstance()
        if (BuildConfig.DEBUG) {
            // Dev-only: the writable source overlay the dev client syncs
            // into, and the dev server `pn run` asked us to connect to
            // (an intent extra; a remembered server is used otherwise).
            py.getModule("pythonnative.hot_reload").callAttr(
                "configure_dev_environment",
                filesDir.absolutePath,
                devServer
            )
        }
        // Handshake with the runtime library (raises on a protocol
        // mismatch, before any screen is created), enable dev mode in
        // debug builds, warm the asyncio runtime, and import the entry
        // module so a broken app fails here with a full traceback.
        py.getModule("pythonnative.bootstrap").callAttr("start", BuildConfig.DEBUG, true, entry)
        // Installing the host delivers the messages screens queued meanwhile.
        val bridge = py.getModule("pythonnative.bridge")
        PNBridge.setHost(object : PythonHost {
            override fun callback(kind: String, tag: Long, name: String, payloadJson: String) {
                bridge.callAttr("native_callback", kind, tag, name, payloadJson)
            }
        })
    }

    private fun pythonStarted(failure: Throwable?) {
        settled = true
        if (isDestroyed) return
        if (failure != null) {
            Log.e("PythonNative", "Bootstrap failed", failure)
            showBootstrapError(failure)
            return
        }
        pythonReady = true
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) BuiltinModules.onActivityResumed()
    }

    override fun onDestroy() {
        super.onDestroy()
        BuiltinModules.onActivityDestroyed(this)
        PNBridge.clearContext(this)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        BuiltinModules.onActivityResult(requestCode, resultCode, data)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        BuiltinModules.onRequestPermissionsResult(requestCode, permissions, grantResults)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        BuiltinModules.onNewIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        if (pythonReady) BuiltinModules.onActivityResumed()
    }

    override fun onPause() {
        super.onPause()
        if (pythonReady) BuiltinModules.onActivityPaused()
    }

    override fun onStop() {
        super.onStop()
        if (pythonReady) BuiltinModules.onActivityStopped()
    }

    private fun showBootstrapError(error: Throwable) {
        val text = TextView(this)
        text.text = "PythonNative could not start\n\n" + Log.getStackTraceString(error)
        text.setTextColor(Color.WHITE)
        text.setBackgroundColor(Color.rgb(191, 26, 26))
        text.typeface = Typeface.MONOSPACE
        text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
        val pad = (16 * resources.displayMetrics.density).toInt()
        text.setPadding(pad, pad * 3, pad, pad * 2)
        val scroll = ScrollView(this)
        scroll.setBackgroundColor(Color.rgb(191, 26, 26))
        scroll.addView(text)
        setContentView(scroll)
    }
}

/** One thread for Python's startup, shared by every activity instance. */
private val startup = java.util.concurrent.Executors.newSingleThreadExecutor { runnable ->
    Thread(runnable, "PythonNative-startup").apply { isDaemon = true }
}
