package com.pythonnative.plugins.push

import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.pythonnative.generated.PNPushSetListeningEvent
import com.pythonnative.generated.PushImplementation
import com.pythonnative.generated.PushModuleAdapter
import com.pythonnative.plugins.notifications.NotificationContent
import com.pythonnative.plugins.notifications.NotificationPresenter
import com.pythonnative.plugins.notifications.PNBufferedEvent
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.PNHeadless
import com.pythonnative.runtime.modules.PNModuleError
import org.json.JSONObject

/** Registers `Push`. FCM reaches the app through [PNFirebaseMessagingService]. */
object PushPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { PushModuleAdapter(PushModule()) }
    }
}

/** Hands FCM's callbacks to Python, whether or not the process has an activity. */
internal object PushDelivery {
    val tokens = PNBufferedEvent("Push", "token")
    val messages = PNBufferedEvent("Push", "message")

    fun token(token: String) {
        startPython()
        tokens.send(token)
    }

    fun message(title: String?, body: String?, data: Map<String, String>) {
        startPython()
        val payload = HashMap<String, Any>()
        title?.let { payload["title"] = it }
        body?.let { payload["body"] = it }
        payload["data"] = JSONObject(data)
        messages.send(payload)
    }

    /** A failed start leaves the event buffered, for when an activity starts Python and reports the failure. */
    private fun startPython() {
        try {
            // Python loads the renderer core on start, and with no activity nothing has installed it yet.
            PNHeadless.ensureStarted()
        } catch (error: Exception) {
            PNLog.swallowed("Push.ensureStarted", error)
        }
    }
}

/**
 * FCM's entry point, on a worker thread, possibly in a process started just for
 * this. FCM calls [onMessageReceived] for a notification message only in the
 * foreground, where the system doesn't show it, so this posts it as iOS's
 * foreground presentation would.
 */
class PNFirebaseMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        PushDelivery.token(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val notification = message.notification
        PushDelivery.message(notification?.title, notification?.body, message.data)
        if (notification != null) {
            val data = JSONObject(message.data as Map<*, *>).toString()
            val identifier = message.messageId ?: java.util.UUID.randomUUID().toString()
            NotificationPresenter.post(this, NotificationContent(notification.title ?: "", notification.body ?: "", identifier, data))
        }
    }
}

/** `Push`: the FCM registration token and remote messages. */
class PushModule : PushImplementation {
    override fun get_device_token(completion: (Result<String?>) -> Unit): (() -> Unit)? {
        if (!isConfigured(PNBridge.context())) {
            completion(Result.failure(PNModuleError("Set [plugins.push].google_services_file in pythonnative.toml to use FCM", "not_configured")))
            return null
        }
        var cancelled = false
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (cancelled) return@addOnCompleteListener
            if (task.isSuccessful) {
                completion(Result.success(task.result))
            } else {
                completion(Result.failure(PNModuleError(task.exception?.message ?: "FCM didn't issue a token", "fcm")))
            }
        }
        return { cancelled = true }
    }

    override fun set_listening(event: PNPushSetListeningEvent, listening: Boolean) {
        when (event) {
            PNPushSetListeningEvent.`token` -> PushDelivery.tokens.setListening(listening)
            PNPushSetListeningEvent.`message` -> PushDelivery.messages.setListening(listening)
        }
    }

    // Firebase's own content provider initializes it from google-services.json's
    // generated resources, and logs and moves on when they're absent.
    private fun isConfigured(context: Context): Boolean = FirebaseApp.getApps(context).isNotEmpty()
}
