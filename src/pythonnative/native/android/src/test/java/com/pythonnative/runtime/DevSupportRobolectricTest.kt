package com.pythonnative.runtime

import android.app.Activity
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ScrollView
import android.widget.TextView
import com.pythonnative.generated.PNValues
import com.pythonnative.generated.ViewProps
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.bridge.TransactionApplier
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.components.ComponentManager
import com.pythonnative.runtime.components.SpacerManager
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.Promise
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** Reads a typed prop whose value doesn't decode, as a decoder bug would. */
private class UndecodableManager : ComponentManager() {
    override fun createView(context: android.content.Context, tag: Long, props: JSONObject): View = View(context)
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewProps(JSONObject().put("opacity", "loud"), validated = true).opacity
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class DevSupportRobolectricTest {
    private lateinit var activity: Activity
    private lateinit var applier: TransactionApplier
    private val devSupport get() = BuiltinModules.devSupport

    @Before fun start() {
        activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        PNBridge.setContext(activity)
        applier = TransactionApplier(PNBridge.registry)
    }

    @After fun stop() {
        call("set_inspecting", JSONObject().put("enabled", false))
        call("set_perf_monitor", JSONObject().put("visible", false).put("lines", JSONArray()))
        call("highlight", JSONObject().put("tag", JSONObject.NULL).put("label", ""))
        com.pythonnative.runtime.modules.HostModule().call("dismiss_error", JSONObject(), Promise(0, "Host"))
        for (record in PNBridge.registry.all()) applier.applyOp(Op.Destroy(record.tag))
        PNRegistry.registerComponent("Spacer") { SpacerManager() }
        devSupport.detach(activity)
        PNBridge.clearContext(activity)
        activity.finish()
    }

    private fun call(method: String, args: JSONObject = JSONObject()): JSONObject {
        val promise = Promise(0, "DevSupport")
        PNRegistry.module("DevSupport")!!.call(method, args, promise)
        return JSONObject(promise.markReturned())
    }

    private fun idle() = shadowOf(Looper.getMainLooper()).idle()

    private fun descendants(view: View): List<View> =
        if (view is ViewGroup) listOf(view) + (0 until view.childCount).flatMap { descendants(view.getChildAt(it)) } else listOf(view)

    @Test fun menuTriggersAreInertUntilEnabled() {
        val module = devSupport
        if (!module.isEnabled) {
            assertFalse(module.onMenuKey())
            assertFalse(module.trigger("menu"))
        }
        assertTrue(call("enable").getBoolean("ok"))
        assertTrue(module.isEnabled)
        assertTrue(module.onMenuKey())
        val stats = call("frame_stats").getJSONObject("value")
        assertTrue(stats.has("fps"))
        assertEquals(0, stats.getInt("dropped"))
        assertEquals("unknown_method", call("show_menu").getString("code"))
    }

    @Test fun highlightsInspectsAndShowsTheMonitor() {
        val manager = PNRegistry.managerFor("View")!!
        val outer = FrameLayout(activity)
        val inner = TextView(activity).apply { text = "Hi" }
        outer.addView(inner, FrameLayout.LayoutParams(50, 20).apply { leftMargin = 10; topMargin = 10 })
        activity.setContentView(outer, ViewGroup.LayoutParams(200, 200))
        PNBridge.registry.register(ViewRecord(98001, "View", outer, manager))
        PNBridge.registry.register(ViewRecord(98002, "Text", inner, manager))
        idle()
        val decor = activity.window.decorView as ViewGroup
        val origin = IntArray(2).also { outer.getLocationInWindow(it) }

        // Text views don't take touches, but the inspector still selects them.
        assertEquals(98002L, devSupport.inspect(decor, origin[0] + 15, origin[1] + 15))
        assertEquals(98001L, devSupport.inspect(decor, origin[0] + 150, origin[1] + 150))

        assertTrue(call("highlight", JSONObject().put("tag", 98002).put("label", "App › Text")).getBoolean("value"))
        assertSame(decor, devSupport.highlightView?.parent)
        assertFalse(call("highlight", JSONObject().put("tag", JSONObject.NULL).put("label", "")).getBoolean("value"))
        assertNull(devSupport.highlightView)

        call("set_inspecting", JSONObject().put("enabled", true))
        assertSame(decor, devSupport.inspectorView?.parent)
        assertEquals(98002L, devSupport.inspect(decor, origin[0] + 15, origin[1] + 15))
        call("set_inspecting", JSONObject().put("enabled", false))
        assertNull(devSupport.inspectorView)

        call("set_perf_monitor", JSONObject().put("visible", true).put("lines", JSONArray().put("Py 2 ms")))
        val monitor = devSupport.monitorView!!
        assertSame(decor, monitor.parent)
        assertTrue(monitor.text.startsWith("UI "))
        assertTrue(monitor.text.endsWith("fps\nPy 2 ms"))
        call("set_perf_monitor", JSONObject().put("visible", false).put("lines", JSONArray()))
        assertNull(devSupport.monitorView)
    }

    @Test fun errorScreenRendersTheStructuredReport() {
        val frames = JSONArray()
            .put(JSONObject().put("file", "/lib/runtime.py").put("line", 3).put("function", "run").put("code", "")
                .put("title", "/lib/runtime.py:3 in run").put("excerpt", "").put("framework", true))
            .put(JSONObject().put("file", "/lib/hooks.py").put("line", 9).put("function", "call").put("code", "")
                .put("title", "/lib/hooks.py:9 in call").put("excerpt", "").put("framework", true))
            .put(JSONObject().put("file", "app/main.py").put("line", 15).put("function", "Counter").put("code", "1 / 0")
                .put("title", "app/main.py:15 in Counter").put("excerpt", "  14 | def Counter():\n> 15 |     1 / 0").put("framework", false))
        val report = JSONObject().put("screen", 0).put("level", "error").put("phase", "render")
            .put("type", "ZeroDivisionError").put("message", "division by zero")
            .put("title", "ZeroDivisionError in render: division by zero")
            .put("component_stack", JSONArray()
                .put(JSONObject().put("name", "Counter").put("file", "app/main.py").put("line", 14))
                .put(JSONObject().put("name", "App").put("file", JSONObject.NULL).put("line", JSONObject.NULL)))
            .put("frames", frames).put("text", "Traceback (most recent call last): ...").put("timestamp", 0)
        val promise = Promise(0, "Host")
        com.pythonnative.runtime.modules.HostModule().call("show_error", report, promise)
        assertTrue(JSONObject(promise.markReturned()).getBoolean("ok"))
        val dialog = com.pythonnative.runtime.modules.ErrorOverlay.visible
        assertNotNull(dialog)
        val views = descendants(dialog!!.window!!.decorView)
        val texts = views.mapNotNull { (it as? TextView)?.text?.toString() }
        for (expected in listOf("ZeroDivisionError", "division by zero", "Error during render", "<Counter> (app/main.py:14)\n<App>",
            "2 framework frames", "app/main.py:15 in Counter")) {
            assertTrue("missing $expected in $texts", expected in texts)
        }
        val descriptions = views.mapNotNull { it.contentDescription?.toString() }.toSet()
        assertTrue(descriptions.containsAll(listOf("pn-error-trace", "pn-error-reload", "pn-error-dismiss", "pn-error-copy")))
        assertTrue(views.first { it.contentDescription == "pn-error-trace" } is ScrollView)

        val toggle = views.first { it.tag == "pn-error-framework-frames" }
        val detail = (toggle.parent as ViewGroup).getChildAt(1)
        assertEquals(View.GONE, detail.visibility)
        toggle.performClick()
        assertEquals(View.VISIBLE, detail.visibility)

        val excerpt = com.pythonnative.runtime.modules.ErrorOverlay.excerpt("  14 | def Counter():\n> 15 |     1 / 0") as android.text.Spanned
        assertEquals(0, excerpt.getSpans(0, 5, android.text.style.BackgroundColorSpan::class.java).size)
        assertEquals(1, excerpt.getSpans(excerpt.length - 1, excerpt.length, android.text.style.BackgroundColorSpan::class.java).size)

        views.first { it.contentDescription == "pn-error-dismiss" }.performClick()
        assertNull(com.pythonnative.runtime.modules.ErrorOverlay.visible)
    }

    @Test fun generatedGettersRecordDecodeFailuresInsteadOfThrowing() {
        PNValues.takeDecodeFailure()
        val props = ViewProps(JSONObject().put("opacity", "loud").put("flex", 1), validated = true)
        assertNull(props.opacity)
        assertEquals(1.0, props.flex!!, 0.0)
        val failure = PNValues.takeDecodeFailure()
        assertTrue(failure, failure!!.startsWith("field opacity didn't decode"))
        assertNull(PNValues.takeDecodeFailure())
    }

    @Test fun decodeFailureFailsTheOperation() {
        PNRegistry.registerComponent("Spacer") { UndecodableManager() }
        try {
            applier.applyOp(Op.Create(9901, "Spacer", JSONObject()))
            fail("expected the create to fail")
        } catch (error: IllegalStateException) {
            assertTrue(error.message, error.message!!.startsWith("props for Spacer tag 9901: field opacity didn't decode"))
        }
    }
}
