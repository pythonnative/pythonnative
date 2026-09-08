package com.pythonnative.runtime.modules

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject
import kotlin.math.abs

/**
 * `Notifications`: `request_permission()` (async; `POST_NOTIFICATIONS`
 * on API 33+), `schedule({title, body, delay_seconds, identifier})`
 * (a Handler-delayed local notification, in-process only),
 * `cancel(identifier)`, and `get_device_token()` (`null`; no built-in
 * push on Android).
 */
class NotificationsModule : NativeModule {
    override val name = "Notifications"
    private val delayed = HashMap<String, Runnable>()

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "request_permission" -> requestPermission(promise)
            "schedule" -> promise.resolve(schedule(args))
            "cancel" -> {
                cancel(args.str("identifier") ?: "")
                promise.resolve(null)
            }
            "get_device_token" -> promise.resolve(null)
            else -> promise.rejectUnknownMethod(method)
        }
    }

    private fun requestPermission(promise: Promise) {
        if (Build.VERSION.SDK_INT < 33) return promise.resolve(true)
        BuiltinModules.permissions.request("notifications") { status ->
            promise.resolve(status == PermissionsModule.GRANTED)
        }
    }

    private fun schedule(args: JSONObject): Boolean {
        val title = args.str("title") ?: ""
        val body = args.str("body") ?: ""
        val identifier = args.str("identifier") ?: "pn_${System.currentTimeMillis()}"
        val delaySeconds = JsonUtil.toDouble(args.opt("delay_seconds"), 0.0)
        cancel(identifier)
        if (delaySeconds <= 0.0) return post(title, body, identifier)
        val runnable = Runnable {
            delayed.remove(identifier)
            post(title, body, identifier)
        }
        delayed[identifier] = runnable
        MainThread.postDelayed(runnable, (delaySeconds * 1000).toLong())
        return true
    }

    private fun cancel(identifier: String) {
        delayed.remove(identifier)?.let { MainThread.remove(it) }
        try {
            manager()?.cancel(notificationId(identifier))
        } catch (e: Exception) {
            PNLog.swallowed("Notifications.cancel", e)
        }
    }

    private fun manager(): NotificationManager? =
        PNBridge.context().getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager

    private fun post(title: String, body: String, identifier: String): Boolean {
        return try {
            val ctx = PNBridge.context()
            val nm = manager() ?: return false
            val builder = if (Build.VERSION.SDK_INT >= 26) {
                nm.createNotificationChannel(NotificationChannel(CHANNEL_ID, "PythonNative", NotificationManager.IMPORTANCE_DEFAULT))
                Notification.Builder(ctx, CHANNEL_ID)
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(ctx)
            }
            builder.setContentTitle(title).setContentText(body).setSmallIcon(android.R.drawable.ic_dialog_info)
            nm.notify(notificationId(identifier), builder.build())
            true
        } catch (e: Exception) {
            PNLog.swallowed("Notifications.post", e)
            false
        }
    }

    private fun notificationId(identifier: String): Int = abs(identifier.hashCode()) % Int.MAX_VALUE

    private companion object {
        const val CHANNEL_ID = "pn_default"
    }
}
