package com.pythonnative.runtime.modules

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.BatteryManager
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import org.json.JSONObject

/**
 * `Battery`: `get_level()` (0..1 or -1) and `get_state()`
 * (`unknown|unplugged|charging|full`), plus `change` events from the
 * sticky `ACTION_BATTERY_CHANGED` broadcast.
 */
class BatteryModule : NativeModule {
    override val name = "Battery"
    private var receiver: BroadcastReceiver? = null

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "get_level" -> promise.resolve(level())
            "get_state" -> promise.resolve(state())
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun manager(): BatteryManager? =
        PNBridge.context().getSystemService(Context.BATTERY_SERVICE) as? BatteryManager

    private fun level(): Double {
        val pct = manager()?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: return -1.0
        return if (pct in 0..100) pct / 100.0 else -1.0
    }

    private fun state(): String = stateName(manager()?.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) ?: -1)

    private fun stateName(status: Int): String = when (status) {
        BatteryManager.BATTERY_STATUS_CHARGING -> "charging"
        BatteryManager.BATTERY_STATUS_FULL -> "full"
        BatteryManager.BATTERY_STATUS_DISCHARGING, BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "unplugged"
        else -> "unknown"
    }

    fun attach(activity: Activity) {
        if (receiver != null) return
        val r = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent == null) return
                val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                val fraction = if (level >= 0 && scale > 0) level.toDouble() / scale.toDouble() else -1.0
                ModuleEvents.emit(name, "change", JSONObject().put("level", fraction).put("state", stateName(status)))
            }
        }
        try {
            activity.registerReceiver(r, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            receiver = r
        } catch (e: Exception) {
            PNLog.swallowed("Battery.attach", e)
        }
    }

    fun detach(activity: Activity) {
        receiver?.let {
            try {
                activity.unregisterReceiver(it)
            } catch (e: Exception) {
                PNLog.swallowed("Battery.detach", e)
            }
        }
        receiver = null
    }
}

/**
 * `NetInfo.fetch()` → `{is_connected, type, is_internet_reachable}`;
 * a default `NetworkCallback` emits `change` events on the main thread.
 */
class NetInfoModule : NativeModule {
    override val name = "NetInfo"
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var last: JSONObject? = null

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "fetch" -> promise.resolve(snapshot())
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun manager(): ConnectivityManager? =
        PNBridge.context().getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager

    fun snapshot(): JSONObject {
        val offline = JSONObject().put("is_connected", false).put("type", "none").put("is_internet_reachable", false)
        return try {
            val manager = manager() ?: return offline
            val network = manager.activeNetwork ?: return offline
            val caps = manager.getNetworkCapabilities(network) ?: return offline
            val kind = when {
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                else -> "other"
            }
            JSONObject()
                .put("is_connected", true)
                .put("type", kind)
                .put("is_internet_reachable", caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
        } catch (e: Exception) {
            offline
        }
    }

    fun attach(activity: Activity) {
        if (callback != null) return
        try {
            val manager = activity.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val cb = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) = changed()
                override fun onLost(network: Network) = changed()
                override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) = changed()
            }
            manager.registerDefaultNetworkCallback(cb)
            callback = cb
        } catch (e: Exception) {
            PNLog.swallowed("NetInfo.attach", e)
        }
    }

    private fun changed() {
        // NetworkCallback fires on a binder thread; hop to main before reading state.
        MainThread.post {
            val current = snapshot()
            if (last?.toString() == current.toString()) return@post
            last = current
            ModuleEvents.emit(name, "change", current)
        }
    }

    fun detach(activity: Activity) {
        callback?.let {
            try {
                (activity.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager).unregisterNetworkCallback(it)
            } catch (e: Exception) {
                PNLog.swallowed("NetInfo.detach", e)
            }
        }
        callback = null
    }
}

/** `AppState.current_state()` plus `change` events (`active|inactive|background`). */
class AppStateModule : NativeModule {
    override val name = "AppState"
    private var state = "active"

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "current_state" -> promise.resolve(state)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    fun transition(next: String) {
        if (state == next) return
        state = next
        ModuleEvents.emit(name, "change", JSONObject().put("state", next))
    }
}
