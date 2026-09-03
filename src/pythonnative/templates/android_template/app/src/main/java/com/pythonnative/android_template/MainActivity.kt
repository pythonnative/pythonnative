package com.pythonnative.android_template

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
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
    private var batteryReceiver: BroadcastReceiver? = null

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
            py.getModule(getString(R.string.pn_entry_module))
            pythonReady = true
        } catch (e: Exception) {
            Log.e("PythonNative", "Bootstrap failed", e)
            showBootstrapError(e)
            return
        }

        // A cold start from a deep link carries the URL on the launch intent.
        intent?.dataString?.let { dispatchUrl(it) }

        registerNetworkCallback()
        registerBatteryReceiver()
    }

    override fun onDestroy() {
        super.onDestroy()
        batteryReceiver?.let {
            try {
                unregisterReceiver(it)
            } catch (e: Exception) {
                Log.e("PythonNative", "unregisterReceiver(battery) failed", e)
            }
            batteryReceiver = null
        }
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

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (!pythonReady) return
        try {
            Python.getInstance()
                .getModule("pythonnative.native_modules")
                .callAttr("dispatch_activity_result", requestCode, resultCode, data)
        } catch (e: Exception) {
            Log.e("PythonNative", "dispatch_activity_result failed", e)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (!pythonReady) return
        try {
            Python.getInstance()
                .getModule("pythonnative.native_modules")
                .callAttr("dispatch_permissions_result", requestCode, permissions.toList(), grantResults.toList())
        } catch (e: Exception) {
            Log.e("PythonNative", "dispatch_permissions_result failed", e)
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

    // MARK: - Battery forwarding

    // ACTION_BATTERY_CHANGED is a sticky broadcast, so registering also
    // delivers the current level immediately.
    private fun registerBatteryReceiver() {
        if (!pythonReady || batteryReceiver != null) return
        try {
            val receiver = object : BroadcastReceiver() {
                override fun onReceive(context: Context?, intent: Intent?) {
                    if (intent == null) return
                    val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                    val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                    val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                    val fraction = if (level >= 0 && scale > 0) level.toDouble() / scale.toDouble() else -1.0
                    val state = when (status) {
                        BatteryManager.BATTERY_STATUS_CHARGING -> "charging"
                        BatteryManager.BATTERY_STATUS_FULL -> "full"
                        BatteryManager.BATTERY_STATUS_DISCHARGING,
                        BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "unplugged"
                        else -> "unknown"
                    }
                    dispatchBattery(fraction, state)
                }
            }
            registerReceiver(receiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            batteryReceiver = receiver
        } catch (e: Exception) {
            Log.e("PythonNative", "registerReceiver(battery) failed", e)
        }
    }

    private fun dispatchBattery(level: Double, state: String) {
        if (!pythonReady) return
        try {
            Python.getInstance()
                .getModule("pythonnative.native_modules.battery")
                .callAttr("dispatch_battery", level, state)
        } catch (e: Exception) {
            Log.e("PythonNative", "dispatch_battery failed", e)
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
