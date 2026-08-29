package com.pythonnative.android_template

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
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
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

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

        registerNetworkCallback()
    }

    override fun onDestroy() {
        super.onDestroy()
        networkCallback?.let {
            try {
                (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
                    .unregisterNetworkCallback(it)
            } catch (e: Exception) {
                Log.e("PythonNative", "unregisterNetworkCallback failed", e)
            }
            networkCallback = null
        }
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

    // MARK: - NetInfo forwarding

    // Live connectivity updates. The callback must be a NetworkCallback
    // subclass, which Chaquopy's dynamic_proxy can't create from Python
    // (interfaces only), so the registration lives here and forwards
    // into the pythonnative net_info module.
    private fun registerNetworkCallback() {
        if (!pythonReady || networkCallback != null) return
        try {
            val manager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) = dispatchNetInfo()
                override fun onLost(network: Network) = dispatchNetInfo()
                override fun onCapabilitiesChanged(
                    network: Network,
                    capabilities: NetworkCapabilities
                ) = dispatchNetInfo()
            }
            manager.registerDefaultNetworkCallback(callback)
            networkCallback = callback
        } catch (e: Exception) {
            Log.e("PythonNative", "registerDefaultNetworkCallback failed", e)
        }
    }

    private fun dispatchNetInfo() {
        // NetworkCallback fires on a ConnectivityManager binder thread;
        // hop to the main thread before crossing into Python.
        runOnUiThread {
            if (!pythonReady) return@runOnUiThread
            try {
                Python.getInstance()
                    .getModule("pythonnative.native_modules.net_info")
                    .callAttr("dispatch_android_change")
            } catch (e: Exception) {
                Log.e("PythonNative", "dispatch_android_change failed", e)
            }
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
