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
            // Set content view to the NavHost layout; the initial screen
            // loads via nav_graph startDestination.
            setContentView(R.layout.activity_main)
            val py = Python.getInstance()
            if (BuildConfig.DEBUG) {
                // Dev-only writable source overlay for hot reload.
                py.getModule("pythonnative.hot_reload").callAttr(
                    "configure_dev_environment",
                    filesDir.absolutePath
                )
            }
            // Import the entry module now so a broken app fails here,
            // with a full traceback, instead of inside the first fragment.
            py.getModule("app.main")
            pythonReady = true
        } catch (e: Exception) {
            Log.e("PythonNative", "Bootstrap failed", e)
            showBootstrapError(e)
            return
        }

        // A cold start from a deep link carries the URL on the launch intent.
        intent?.dataString?.let { dispatchUrl(it) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        intent.dataString?.let { dispatchUrl(it) }
    }

    // MARK: - AppState forwarding

    override fun onResume() {
        super.onResume()
        dispatchAppState("active")
    }

    override fun onPause() {
        super.onPause()
        dispatchAppState("inactive")
    }

    override fun onStop() {
        super.onStop()
        dispatchAppState("background")
    }

    private fun dispatchAppState(state: String) {
        if (!pythonReady) return
        try {
            Python.getInstance()
                .getModule("pythonnative.native_modules.app_state")
                .callAttr("dispatch_app_state", state)
        } catch (e: Exception) {
            Log.e("PythonNative", "dispatch_app_state($state) failed", e)
        }
    }

    // MARK: - Deep links

    private fun dispatchUrl(url: String) {
        if (!pythonReady) return
        try {
            Python.getInstance()
                .getModule("pythonnative.native_modules.linking")
                .callAttr("dispatch_url", url)
        } catch (e: Exception) {
            Log.e("PythonNative", "dispatch_url failed", e)
        }
    }

    // MARK: - Bootstrap error UI

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
