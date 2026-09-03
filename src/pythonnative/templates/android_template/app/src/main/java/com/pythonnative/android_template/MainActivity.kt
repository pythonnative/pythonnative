package com.pythonnative.android_template

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.util.Log
import android.util.TypedValue
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.PythonHost
import com.pythonnative.runtime.modules.BuiltinModules

/**
 * The single activity. It starts Python, wires the `PNBridge` host
 * callback into `pythonnative.bridge.native_callback`, runs the
 * protocol handshake, and forwards activity callbacks to the Kotlin
 * native modules. Screens live in `ScreenFragment`s inside the
 * `NavHostFragment` from `activity_main.xml`.
 */
class MainActivity : AppCompatActivity() {
    private val TAG = javaClass.simpleName
    private var pythonReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate() called")

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        try {
            PNBridge.setContext(this)
            val py = Python.getInstance()
            PNBridge.setHost(object : PythonHost {
                override fun callback(kind: String, tag: Long, name: String, payloadJson: String): String? =
                    py.getModule("pythonnative.bridge")
                        .callAttr("native_callback", kind, tag, name, payloadJson)
                        ?.toString()
            })
            if (BuildConfig.DEBUG) {
                // Dev-only writable source overlay for hot reload.
                py.getModule("pythonnative.hot_reload").callAttr(
                    "configure_dev_environment",
                    filesDir.absolutePath
                )
            }
            // Handshake with the runtime library (raises on a protocol
            // mismatch, before any screen is created), enable dev mode in
            // debug builds, and warm the asyncio runtime.
            py.getModule("pythonnative.bootstrap").callAttr("start", BuildConfig.DEBUG, true)
            // Import the entry module now so a broken app fails here,
            // with a full traceback, instead of inside the first fragment.
            py.getModule(getString(R.string.pn_entry_module))
            pythonReady = true
            // Set content view to the NavHost layout; the initial screen
            // loads via nav_graph startDestination.
            setContentView(R.layout.activity_main)
        } catch (e: Exception) {
            Log.e("PythonNative", "Bootstrap failed", e)
            showBootstrapError(e)
            return
        }
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

    private fun showBootstrapError(error: Exception) {
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
