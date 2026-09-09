package com.pythonnative.runtime.modules

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationManagerCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.str
import org.json.JSONObject

/** Local notifications scheduled by the OS, independent of the Python process. */
class NotificationsModule : NativeModule {
    override val name = "Notifications"
    override fun call(method: String, args: JSONObject, promise: Promise) {
        val context = PNBridge.context()
        when (method) {
            "request_permission" -> {
                if (Build.VERSION.SDK_INT < 33) promise.resolve(NotificationManagerCompat.from(context).areNotificationsEnabled())
                else BuiltinModules.permissions.request("notifications") { promise.resolve(it == PermissionsModule.GRANTED) }
            }
            "schedule" -> promise.resolve(NotificationScheduler.schedule(context, args))
            "cancel" -> { NotificationScheduler.cancel(context, args.str("identifier") ?: "default"); promise.resolve(null) }
            "get_device_token" -> promise.resolve(null)
            else -> promise.rejectUnknownMethod(method)
        }
    }
}

/** Explicit, nonexported receiver: no bridge, Activity, or Python initialization. */
class NotificationReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != NotificationScheduler.ACTION) return
        NotificationScheduler.post(context, intent.getStringExtra("title") ?: "", intent.getStringExtra("body") ?: "",
            intent.getStringExtra("identifier") ?: "default")
    }
}

internal object NotificationScheduler {
    const val ACTION = "com.pythonnative.NOTIFICATION"
    private const val CHANNEL = "pn_default"
    private fun intent(context: Context, identifier: String) = Intent(context, NotificationReceiver::class.java)
        .setAction(ACTION).setData(Uri.Builder().scheme("pythonnative").authority("notification").appendPath(identifier).build())
        .putExtra("identifier", identifier)

    fun schedule(context: Context, args: JSONObject): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        val identifier = args.str("identifier") ?: "default"
        val delay = args.optDouble("delay_seconds", 0.0)
        require(delay.isFinite() && delay >= 0) { "delay_seconds must be finite and nonnegative" }
        cancel(context, identifier)
        val title = args.str("title") ?: ""
        val body = args.str("body") ?: ""
        if (delay == 0.0) return post(context, title, body, identifier)
        val operation = PendingIntent.getBroadcast(context, 0, intent(context, identifier).putExtra("title", title).putExtra("body", body),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        // Inexact scheduling needs no exact-alarm permission and may be deferred
        // by the OS. PendingIntent alarms survive ordinary process death.
        alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, System.currentTimeMillis() + (delay.coerceAtMost(315360000.0) * 1000).toLong(), operation)
        return true
    }

    fun cancel(context: Context, identifier: String) {
        PendingIntent.getBroadcast(context, 0, intent(context, identifier), PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE)?.let {
            (context.getSystemService(Context.ALARM_SERVICE) as AlarmManager).cancel(it)
            it.cancel()
        }
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(identifier, 0)
    }

    fun post(context: Context, title: String, body: String, identifier: String): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val builder = if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "PythonNative", NotificationManager.IMPORTANCE_DEFAULT))
            Notification.Builder(context, CHANNEL)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context)
        }
        builder.setContentTitle(title).setContentText(body).setSmallIcon(android.R.drawable.ic_dialog_info).setAutoCancel(true)
        context.packageManager.getLaunchIntentForPackage(context.packageName)?.let {
            builder.setContentIntent(PendingIntent.getActivity(context, 0, it, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        }
        return try { manager.notify(identifier, 0, builder.build()); true } catch (_: SecurityException) { false }
    }
}
