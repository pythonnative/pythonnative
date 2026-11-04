package com.pythonnative.plugins.notifications

import android.app.Activity
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
import com.pythonnative.generated.NotificationsImplementation
import com.pythonnative.generated.NotificationsModuleAdapter
import com.pythonnative.generated.PNJSONValue
import com.pythonnative.generated.PNNotificationsSetListeningEvent
import com.pythonnative.generated.PNValues
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNLifecycleHook
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions
import com.pythonnative.runtime.modules.PermissionsModule
import org.json.JSONObject

private const val POST_NOTIFICATIONS = "android.permission.POST_NOTIFICATIONS"

/** Registers `Notifications` and its lifecycle hook, and owns the `notifications` permission. */
object NotificationsPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { NotificationsModuleAdapter(NotificationsModule()) }
        registry.registerLifecycleHook(NotificationsHook)
        PNPermissions.register("notifications", POST_NOTIFICATIONS, minSdk = 33)
    }
}

/**
 * One module event, held back until Python subscribes. The bridge's mailbox
 * only waits for Python to start, and an app subscribes later than that, from
 * a screen's effect.
 */
internal class PNBufferedEvent(private val module: String, private val event: String) {
    private val pending = ArrayDeque<Any>()
    private var listening = false

    @Synchronized
    fun isListening(): Boolean = listening

    @Synchronized
    fun send(payload: Any) {
        if (listening) {
            ModuleEvents.emit(module, event, payload)
            return
        }
        if (pending.size == LIMIT) pending.removeFirst()
        pending.addLast(payload)
    }

    @Synchronized
    fun setListening(value: Boolean) {
        listening = value
        if (!value) return
        val replay = pending.toList()
        pending.clear()
        for (payload in replay) ModuleEvents.emit(module, event, payload)
    }

    @Synchronized
    fun dropOldest() {
        pending.removeFirstOrNull()
    }

    private companion object {
        const val LIMIT = 64
    }
}

/** What's waiting for Python, and whether an activity is on screen. */
internal object NotificationEvents {
    val received = PNBufferedEvent("Notifications", "received")
    val responses = PNBufferedEvent("Notifications", "response")
    @Volatile var foreground = false
    private var launchResponse: Map<String, Any>? = null
    private var launchBuffered = false

    @Synchronized
    fun launched(payload: Map<String, Any>) {
        launchResponse = payload
        launchBuffered = !responses.isListening()
        responses.send(payload)
    }

    /** Reading the launching tap claims it, so it isn't replayed to `on_response` too. */
    @Synchronized
    fun readLaunchResponse(): Map<String, Any>? {
        if (launchBuffered) {
            responses.dropOldest()
            launchBuffered = false
        }
        return launchResponse
    }

    @Synchronized
    fun setListeningToResponses(listening: Boolean) {
        if (listening) launchBuffered = false
        responses.setListening(listening)
    }
}

/**
 * A tap comes back as the content intent's extras: through `onCreate` when it
 * launched the activity, and `onNewIntent` when an activity already existed
 * (`MainActivity` is `singleTask`). After process death the system recreates
 * that activity with its original intent first, and then delivers the new one,
 * so a tap counts as launching until the first resume.
 */
internal object NotificationsHook : PNLifecycleHook {
    private var launching = false

    override fun onActivityCreated(activity: Activity) {
        launching = true
        activity.intent?.let { intent -> NotificationPresenter.claimTap(activity, intent)?.let { NotificationEvents.launched(it) } }
    }

    override fun onNewIntent(intent: Intent): Boolean {
        if (!NotificationPresenter.tapIn(intent)) return false
        NotificationPresenter.claimTap(PNBridge.context(), intent)?.let { payload ->
            if (launching) NotificationEvents.launched(payload) else NotificationEvents.responses.send(payload)
        }
        return true
    }

    override fun onActivityResumed(activity: Activity) {
        launching = false
        NotificationEvents.foreground = true
    }

    override fun onActivityPaused(activity: Activity) {
        NotificationEvents.foreground = false
    }
}

/** `Notifications`: local notifications scheduled by the OS, independent of the Python process. */
class NotificationsModule : NotificationsImplementation {
    override fun request_permission(completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        if (Build.VERSION.SDK_INT < 33) {
            completion(Result.success(NotificationManagerCompat.from(PNBridge.context()).areNotificationsEnabled()))
            return null
        }
        return BuiltinModules.permissions.request("notifications") { result ->
            completion(result.map { it == PermissionsModule.GRANTED })
        }
    }

    override fun schedule(
        badge: Long?,
        body: String,
        data: Map<String, PNJSONValue>?,
        delay_seconds: Double,
        identifier: String,
        sound: Boolean,
        title: String,
        completion: (Result<Boolean>) -> Unit,
    ): (() -> Unit)? {
        val content = NotificationContent(title, body, identifier, if (data == null) "{}" else PNValues.encode(data).toString(), badge?.toInt(), sound)
        completion(runCatching { NotificationScheduler.schedule(PNBridge.context(), content, delay_seconds) })
        return null
    }

    override fun cancel(identifier: String, completion: (Result<Unit>) -> Unit): (() -> Unit)? {
        completion(runCatching { NotificationScheduler.cancel(PNBridge.context(), identifier) })
        return null
    }

    override fun cancel_all(completion: (Result<Unit>) -> Unit): (() -> Unit)? {
        completion(runCatching { NotificationScheduler.cancelAll(PNBridge.context()) })
        return null
    }

    override fun set_badge(count: Long, completion: (Result<Unit>) -> Unit): (() -> Unit)? {
        // The contract limits this to iOS, so Python raises before reaching here.
        completion(Result.failure(PNModuleError("Android has no API that sets a launcher badge", "unsupported")))
        return null
    }

    override fun last_response(): Map<String, PNJSONValue>? =
        NotificationEvents.readLaunchResponse()?.mapValues { PNJSONValue(it.value) }

    override fun set_listening(event: PNNotificationsSetListeningEvent, listening: Boolean) {
        when (event) {
            PNNotificationsSetListeningEvent.`received` -> NotificationEvents.received.setListening(listening)
            PNNotificationsSetListeningEvent.`response` -> NotificationEvents.setListeningToResponses(listening)
        }
    }
}

/** A notification to post. [data] is a JSON object, which fits in intent extras as it is. */
internal class NotificationContent(
    val title: String,
    val body: String,
    val identifier: String,
    val data: String = "{}",
    val badge: Int? = null,
    val sound: Boolean = true,
)

/** Explicit, nonexported receiver: no bridge, Activity, or Python initialization. */
class NotificationReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != NotificationScheduler.ACTION) return
        val identifier = intent.getStringExtra(NotificationPresenter.IDENTIFIER) ?: "default"
        NotificationScheduler.forget(context, identifier)
        NotificationPresenter.post(
            context,
            NotificationContent(
                intent.getStringExtra(NotificationPresenter.TITLE) ?: "",
                intent.getStringExtra(NotificationPresenter.BODY) ?: "",
                identifier,
                intent.getStringExtra(NotificationPresenter.DATA) ?: "{}",
                if (intent.hasExtra(NotificationScheduler.BADGE)) intent.getIntExtra(NotificationScheduler.BADGE, 0) else null,
                intent.getBooleanExtra(NotificationScheduler.SOUND, true),
            ),
        )
    }
}

internal object NotificationScheduler {
    const val ACTION = "com.pythonnative.NOTIFICATION"
    const val BADGE = "pn_notification_badge"
    const val SOUND = "pn_notification_sound"
    private const val PREFERENCES = "pn_notifications"
    private const val SCHEDULED = "scheduled"

    private fun intent(context: Context, identifier: String) = Intent(context, NotificationReceiver::class.java)
        .setAction(ACTION).setData(Uri.Builder().scheme("pythonnative").authority("notification").appendPath(identifier).build())
        .putExtra(NotificationPresenter.IDENTIFIER, identifier)

    fun schedule(context: Context, content: NotificationContent, delay: Double): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        require(delay.isFinite() && delay >= 0) { "delay_seconds must be finite and nonnegative" }
        cancel(context, content.identifier)
        if (delay == 0.0) return NotificationPresenter.post(context, content)
        val intent = intent(context, content.identifier)
            .putExtra(NotificationPresenter.TITLE, content.title)
            .putExtra(NotificationPresenter.BODY, content.body)
            .putExtra(NotificationPresenter.DATA, content.data)
            .putExtra(SOUND, content.sound)
        content.badge?.let { intent.putExtra(BADGE, it) }
        val operation = PendingIntent.getBroadcast(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        // Inexact scheduling needs no exact-alarm permission and may be deferred
        // by the OS. PendingIntent alarms survive ordinary process death.
        alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, System.currentTimeMillis() + (delay.coerceAtMost(315360000.0) * 1000).toLong(), operation)
        remember(context, content.identifier)
        return true
    }

    fun cancel(context: Context, identifier: String) {
        PendingIntent.getBroadcast(context, 0, intent(context, identifier), PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE)?.let {
            (context.getSystemService(Context.ALARM_SERVICE) as AlarmManager).cancel(it)
            it.cancel()
        }
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(identifier, 0)
        forget(context, identifier)
    }

    fun cancelAll(context: Context) {
        for (identifier in scheduled(context)) cancel(context, identifier)
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancelAll()
    }

    // AlarmManager can't list a process's alarms, so `cancelAll` needs its own record.
    private fun scheduled(context: Context): Set<String> =
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getStringSet(SCHEDULED, null).orEmpty().toSet()

    private fun remember(context: Context, identifier: String) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putStringSet(SCHEDULED, scheduled(context) + identifier).apply()
    }

    fun forget(context: Context, identifier: String) {
        val current = scheduled(context)
        if (identifier !in current) return
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putStringSet(SCHEDULED, current - identifier).apply()
    }
}

internal object NotificationPresenter {
    private const val TAP = "pn_notification_tap"
    const val IDENTIFIER = "pn_notification_identifier"
    const val TITLE = "pn_notification_title"
    const val BODY = "pn_notification_body"
    const val DATA = "pn_notification_data"
    private const val FCM_MESSAGE_ID = "google.message_id"
    private const val CHANNEL = "pn_default"
    private const val SILENT_CHANNEL = "pn_silent"
    private const val PREFERENCES = "pn_notifications"
    private const val CLAIMED = "claimed"
    private const val CLAIMED_LIMIT = 32

    /** Post [content], and report it to Python when the app is on screen. */
    fun post(context: Context, content: NotificationContent): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val builder = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(context, channel(manager, content.sound))
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context).also { if (content.sound) it.setDefaults(Notification.DEFAULT_SOUND) }
        }
        builder.setContentTitle(content.title).setContentText(content.body).setSmallIcon(smallIcon(context)).setAutoCancel(true)
        content.badge?.let { builder.setNumber(it) }
        context.packageManager.getLaunchIntentForPackage(context.packageName)?.let {
            it.putExtra(TAP, java.util.UUID.randomUUID().toString())
                .putExtra(IDENTIFIER, content.identifier).putExtra(TITLE, content.title).putExtra(BODY, content.body).putExtra(DATA, content.data)
            // Extras don't distinguish PendingIntents, so each identifier gets its own request code.
            builder.setContentIntent(PendingIntent.getActivity(context, content.identifier.hashCode(), it, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        }
        try {
            manager.notify(content.identifier, 0, builder.build())
        } catch (_: SecurityException) {
            return false
        }
        if (NotificationEvents.foreground) NotificationEvents.received.send(payload(content.identifier, content.title, content.body, content.data))
        return true
    }

    private fun channel(manager: NotificationManager, sound: Boolean): String {
        val id = if (sound) CHANNEL else SILENT_CHANNEL
        if (Build.VERSION.SDK_INT >= 26 && manager.getNotificationChannel(id) == null) {
            val name = if (sound) "Notifications" else "Silent notifications"
            val channel = NotificationChannel(id, name, NotificationManager.IMPORTANCE_DEFAULT)
            if (!sound) channel.setSound(null, null)
            manager.createNotificationChannel(channel)
        }
        return id
    }

    private fun smallIcon(context: Context): Int {
        val configured = context.resources.getIdentifier("pn_notification_icon", "drawable", context.packageName)
        if (configured != 0) return configured
        // Android 8.0's System UI crashes on an adaptive icon in a notification.
        if (Build.VERSION.SDK_INT == 26) return android.R.drawable.ic_dialog_info
        return context.applicationInfo.icon.takeIf { it != 0 } ?: android.R.drawable.ic_dialog_info
    }

    private fun payload(identifier: String, title: String, body: String, data: String): Map<String, Any> = mapOf(
        "identifier" to identifier,
        "title" to title,
        "body" to body,
        "data" to runCatching { JSONObject(data) }.getOrDefault(JSONObject()),
    )

    /** Whether [intent] carries a tap, ours or FCM's. */
    fun tapIn(intent: Intent): Boolean = extras(intent)?.let { it.containsKey(TAP) || it.containsKey(FCM_MESSAGE_ID) } ?: false

    /**
     * The tap [intent] carries, unless it was already reported. An activity's
     * intent outlives its process and comes back unchanged when the system
     * recreates the activity, so removing the extras wouldn't be enough. FCM's
     * system-posted notification launches with the message's data as plain
     * extras and no title or body.
     */
    fun claimTap(context: Context, intent: Intent): Map<String, Any>? {
        val extras = extras(intent) ?: return null
        val tap = extras.getString(TAP)
        if (tap != null) {
            if (!firstClaim(context, tap)) return null
            return payload(extras.getString(IDENTIFIER) ?: "", extras.getString(TITLE) ?: "", extras.getString(BODY) ?: "", extras.getString(DATA) ?: "{}") + ("action" to "default")
        }
        val messageId = extras.getString(FCM_MESSAGE_ID) ?: return null
        if (!firstClaim(context, messageId)) return null
        val data = JSONObject()
        for (key in extras.keySet()) {
            if (key.startsWith("google.") || key.startsWith("gcm.") || key == "from" || key == "collapse_key") continue
            extras.getString(key)?.let { data.put(key, it) }
        }
        return mapOf("identifier" to messageId, "title" to "", "body" to "", "data" to data, "action" to "default")
    }

    private fun extras(intent: Intent) = try {
        intent.extras
    } catch (error: RuntimeException) {
        // The launcher activity is exported, so its extras can be anything.
        PNLog.swallowed("Notifications.tap", error)
        null
    }

    @Synchronized
    private fun firstClaim(context: Context, tap: String): Boolean {
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val claimed = preferences.getString(CLAIMED, "").orEmpty().split(' ').filter { it.isNotEmpty() }
        if (tap in claimed) return false
        preferences.edit().putString(CLAIMED, (listOf(tap) + claimed).take(CLAIMED_LIMIT).joinToString(" ")).apply()
        return true
    }
}
