package com.pythonnative.runtime

import android.app.Activity
import android.content.Context
import android.text.InputType
import android.widget.EditText
import android.widget.FrameLayout
import com.pythonnative.runtime.mount.MountOp
import com.pythonnative.runtime.mount.Mounter
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
    private lateinit var applier: Mounter

    @Before fun start() {
        activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        PNBridge.setContext(activity)
        applier = Mounter(PNBridge.registry)
    }

    @After fun stop() {
        for (record in PNBridge.registry.all()) applier.applyOp(MountOp.Delete(record.tag))
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

    @Test fun lifecycleHooksSeeEventsAndReportWhetherTheyConsumedThem() {
        val seen = ArrayList<Int>()
        val hook = object : com.pythonnative.runtime.modules.PNLifecycleHook {
            override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?): Boolean {
                seen.add(requestCode)
                return requestCode == 7
            }
        }
        com.pythonnative.runtime.bridge.PNRegistry.registerLifecycleHook(hook)
        assertTrue(com.pythonnative.runtime.modules.BuiltinModules.onActivityResult(7, 0, null))
        assertFalse(com.pythonnative.runtime.modules.BuiltinModules.onActivityResult(8, 0, null))
        assertEquals(listOf(7, 8), seen)
    }

    @Test fun permissionsAnswerForRegisteredNamesAndRejectOthers() {
        com.pythonnative.runtime.modules.PNPermissions.register("pn_test_permission", "android.permission.CAMERA")
        val module = com.pythonnative.runtime.modules.PermissionsModule()
        var status: Result<String>? = null
        module.check("pn_test_permission") { status = it }
        assertEquals(com.pythonnative.runtime.modules.PermissionsModule.DENIED, status!!.getOrThrow())
        module.check("pn_no_such_permission") { status = it }
        val failure = status!!.exceptionOrNull() as com.pythonnative.runtime.modules.PNModuleError
        assertEquals("plugin_not_enabled", failure.code)
    }

    @Test fun generatedAdapterRejectsInvalidLateNativeResult() {
        var complete: ((Result<com.pythonnative.generated.PNImageSize>) -> Unit)? = null
        val implementation = object : com.pythonnative.generated.ImagesImplementation {
            override fun clear_cache() {}
            override fun prefetch(uri: String, completion: (Result<Boolean>) -> Unit): (() -> Unit)? = null
            override fun get_size(uri: String, completion: (Result<com.pythonnative.generated.PNImageSize>) -> Unit): (() -> Unit)? {
                complete = completion
                return null
            }
        }
        val adapter = com.pythonnative.generated.ImagesModuleAdapter(implementation)
        val promise = com.pythonnative.runtime.modules.Promise(200, "Images")
        adapter.call("get_size", JSONObject().put("uri", "x"), promise)
        assertTrue(JSONObject(promise.markReturned()).getBoolean("pending"))
        complete!!(Result.success(com.pythonnative.generated.PNImageSize(width = Double.NaN, height = 1.0)))
        assertTrue(promise.isSettled)
    }

    @Test fun sliderUpdatesRangeAndRestoresPlatformColors() {
        applier.applyOp(MountOp.Create(70, "Slider", JSONObject().put("value", 0.5).put("min_value", 0).put("max_value", 1)
            .put("minimum_track_color", "#ff0000").put("thumb_color", "#00ff00")))
        val slider = PNBridge.registry.get(70)?.view as android.widget.SeekBar
        assertNotNull(slider.progressTintList)
        assertEquals(500, slider.progress)
        applier.applyOp(MountOp.Update(70, JSONObject().put("min_value", 0).put("max_value", 2)
            .put("minimum_track_color", JSONObject.NULL).put("thumb_color", JSONObject.NULL), listOf("minimum_track_color", "thumb_color")))
        assertEquals(250, slider.progress)
        assertNull(slider.progressTintList)
        assertNull(slider.thumbTintList)
    }

    @Test fun inputRecreationRetainsIdentityParentValueAndSelection() {
        applier.applyOp(MountOp.Create(1, "TextInput", JSONObject().put("value", "hello").put("multiline", false).put("font_size", 24)))
        val parent = FrameLayout(activity)
        activity.setContentView(parent)
        val original = PNBridge.registry.get(1)!!.view as EditText
        parent.addView(original)
        original.requestFocus()
        original.setSelection(1, 3)
        applier.applyOp(MountOp.Update(1, JSONObject().put("multiline", true).put("font_size", JSONObject.NULL), recreate = true))
        val replacement = PNBridge.registry.get(1)!!.view as EditText
        assertNotSame(original, replacement)
        assertSame(parent, replacement.parent)
        assertEquals(1, parent.childCount)
        assertEquals("hello", replacement.text.toString())
        assertEquals(1, replacement.selectionStart)
        assertEquals(3, replacement.selectionEnd)
        assertTrue(replacement.inputType and InputType.TYPE_TEXT_FLAG_MULTI_LINE != 0)
        assertTrue(replacement.textSize < original.textSize)
        applier.applyOp(MountOp.Delete(1))
        assertEquals(0, parent.childCount)
        assertNull(PNBridge.registry.get(1))
    }

    @Test fun containerResetRetainsPhysicalIdentityAndInsertedChildren() {
        applier.applyOp(MountOp.Create(10, "View", JSONObject().put("background_color", "#ff0000")))
        applier.applyOp(MountOp.Create(11, "Text", JSONObject().put("text", "child")))
        applier.applyOp(MountOp.Insert(10, 11, 0))
        val original = PNBridge.registry.get(10)!!.view
        applier.applyOp(MountOp.Update(10, JSONObject().put("background_color", JSONObject.NULL)))
        val replacement = PNBridge.registry.get(10)!!.view as android.view.ViewGroup
        assertSame(original, replacement)
        assertSame(replacement, PNBridge.registry.get(11)!!.view.parent)
        assertEquals(1, replacement.childCount)
    }

}
