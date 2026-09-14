package com.pythonnative.runtime

import android.app.Activity
import android.app.AlarmManager
import android.app.NotificationManager
import android.content.Context
import android.text.InputType
import android.widget.EditText
import android.widget.FrameLayout
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.TransactionApplier
import com.pythonnative.runtime.modules.NotificationScheduler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NativeLifecycleTest {
    @Test fun generatedRecordsPreserveNullPresenceAndEscapedDefaults() {
        for (optional in listOf(null, JSONObject.NULL, "value")) {
            val note = JSONObject().put("required", JSONObject.NULL)
            if (optional != null) note.put("optional", optional)
            val decoded = com.pythonnative.generated.PNNativeFixtureDefault.decode(JSONObject().put("note", note))
            val encoded = decoded.nativeValue() as JSONObject
            val returned = encoded.getJSONObject("note")
            assertTrue(returned.has("required") && returned.isNull("required"))
            assertEquals(optional != null, returned.has("optional"))
            if (optional != null) assertEquals(optional, returned.get("optional"))
            assertTrue(encoded.has("nullable") && encoded.isNull("nullable"))
            assertEquals("\$total \"quoted\" \\path\n\u0000\b", encoded.getString("label"))
        }
    }

    private lateinit var activity: Activity
    private lateinit var applier: TransactionApplier

    @Before fun start() {
        activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        PNBridge.setContext(activity)
        applier = TransactionApplier(PNBridge.registry)
    }

    @After fun stop() {
        for (record in PNBridge.registry.all()) applier.applyOp(Op.Destroy(record.tag))
        PNBridge.clearContext(activity)
        activity.finish()
    }

    @Test fun generatedStorageAdapterPreservesNullAndClipboardUsesText() {
        val storage = com.pythonnative.generated.StorageModuleAdapter(com.pythonnative.runtime.modules.StorageModule())
        val absent = com.pythonnative.runtime.modules.Promise(100, "Storage")
        storage.call("get", JSONObject().put("key", "missing-overhaul"), absent)
        assertTrue(JSONObject(absent.markReturned()).isNull("value"))
        val clipboard = com.pythonnative.generated.ClipboardModuleAdapter(com.pythonnative.runtime.modules.ClipboardModule())
        clipboard.call("set_string", JSONObject().put("text", "typed clipboard"), com.pythonnative.runtime.modules.Promise(101, "Clipboard"))
        val value = com.pythonnative.runtime.modules.Promise(102, "Clipboard")
        clipboard.call("get_string", JSONObject(), value)
        assertEquals("typed clipboard", JSONObject(value.markReturned()).getString("value"))
    }

    @Test fun generatedAdapterRejectsInvalidLateNativeResult() {
        var complete: ((Result<Map<String, Double>?>) -> Unit)? = null
        val implementation = object : com.pythonnative.generated.LocationImplementation {
            override fun get_current(accuracy: com.pythonnative.generated.PNLocationGetCurrentAccuracy, timeout: Double, completion: (Result<Map<String, Double>?>) -> Unit): (() -> Unit)? {
                complete = completion
                return null
            }
        }
        val adapter = com.pythonnative.generated.LocationModuleAdapter(implementation)
        val promise = com.pythonnative.runtime.modules.Promise(200, "Location")
        adapter.call("get_current", JSONObject(), promise)
        assertTrue(JSONObject(promise.markReturned()).getBoolean("pending"))
        complete!!(Result.success(mapOf("latitude" to Double.NaN)))
        assertTrue(promise.isSettled)
    }

    @Test fun sliderUpdatesRangeAndRestoresPlatformColors() {
        applier.applyOp(Op.Create(70, "Slider", JSONObject().put("value", 0.5).put("min_value", 0).put("max_value", 1)
            .put("minimum_track_color", "#ff0000").put("thumb_color", "#00ff00")))
        val slider = PNBridge.registry.get(70)?.view as android.widget.SeekBar
        assertNotNull(slider.progressTintList)
        assertEquals(500, slider.progress)
        applier.applyOp(Op.Update(70, JSONObject().put("min_value", 0).put("max_value", 2), listOf("minimum_track_color", "thumb_color")))
        assertEquals(250, slider.progress)
        assertNull(slider.progressTintList)
        assertNull(slider.thumbTintList)
    }

    @Test fun inputRecreationRetainsIdentityParentValueAndSelection() {
        applier.applyOp(Op.Create(1, "TextInput", JSONObject().put("value", "hello").put("multiline", false).put("font_size", 24)))
        val parent = FrameLayout(activity)
        activity.setContentView(parent)
        val original = PNBridge.registry.get(1)!!.view as EditText
        parent.addView(original)
        original.requestFocus()
        original.setSelection(1, 3)
        applier.applyOp(Op.Update(1, JSONObject().put("multiline", true).put("font_size", JSONObject.NULL)))
        val replacement = PNBridge.registry.get(1)!!.view as EditText
        assertNotSame(original, replacement)
        assertSame(parent, replacement.parent)
        assertEquals(1, parent.childCount)
        assertEquals("hello", replacement.text.toString())
        assertEquals(1, replacement.selectionStart)
        assertEquals(3, replacement.selectionEnd)
        assertTrue(replacement.inputType and InputType.TYPE_TEXT_FLAG_MULTI_LINE != 0)
        assertTrue(replacement.textSize < original.textSize)
        applier.applyOp(Op.Destroy(1))
        assertEquals(0, parent.childCount)
        assertNull(PNBridge.registry.get(1))
    }

    @Test fun scheduledNotificationDeliversWithoutAnActivityOrPythonHost() {
        val context = activity.applicationContext
        val args = JSONObject().put("title", "Persisted reminder").put("delay_seconds", 60).put("identifier", "survives")
        assertTrue(NotificationScheduler.schedule(context, args.optString("title"), args.optString("body"), args.optDouble("delay_seconds"), args.optString("identifier")))
        val alarms = shadowOf(context.getSystemService(Context.ALARM_SERVICE) as AlarmManager)
        val alarm = alarms.nextScheduledAlarm
        assertNotNull(alarm)
        PNBridge.clearContext(activity)
        alarm!!.operation!!.send()
        shadowOf(android.os.Looper.getMainLooper()).idle()
        val notifications = shadowOf(context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
        assertEquals("Persisted reminder", notifications.getNotification("survives", 0).extras.getString("android.title"))
        NotificationScheduler.cancel(context, "survives")
        assertNull(notifications.getNotification("survives", 0))
    }

    @Test fun containerResetRetainsPhysicalIdentityAndInsertedChildren() {
        applier.applyOp(Op.Create(10, "View", JSONObject().put("background_color", "#ff0000")))
        applier.applyOp(Op.Create(11, "Text", JSONObject().put("text", "child")))
        applier.applyOp(Op.Insert(10, 11, 0))
        val original = PNBridge.registry.get(10)!!.view
        applier.applyOp(Op.Update(10, JSONObject().put("background_color", JSONObject.NULL)))
        val replacement = PNBridge.registry.get(10)!!.view as android.view.ViewGroup
        assertSame(original, replacement)
        assertSame(replacement, PNBridge.registry.get(11)!!.view.parent)
        assertEquals(1, replacement.childCount)
    }

    @Test fun replacingAndCancelingIdentifiersDoesNotLeaveDuplicateAlarms() {
        val context = activity.applicationContext
        val args = JSONObject().put("title", "A").put("delay_seconds", 60).put("identifier", "same")
        assertTrue(NotificationScheduler.schedule(context, args.optString("title"), args.optString("body"), args.optDouble("delay_seconds"), args.optString("identifier")))
        assertTrue(NotificationScheduler.schedule(context, "B", args.optString("body"), args.optDouble("delay_seconds"), args.optString("identifier")))
        val alarms = shadowOf(context.getSystemService(Context.ALARM_SERVICE) as AlarmManager)
        assertEquals(1, alarms.scheduledAlarms.size)
        NotificationScheduler.cancel(context, "same")
        assertTrue(alarms.scheduledAlarms.isEmpty())
    }
}
