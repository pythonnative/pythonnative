package com.pythonnative.runtime

import android.app.Activity
import android.app.Dialog
import android.graphics.drawable.RippleDrawable
import android.text.method.LinkMovementMethod
import android.view.View
import android.widget.EditText
import android.widget.TextView
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.TransactionApplier
import com.pythonnative.runtime.components.ScrollViewManager
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.views.PNHorizontalScrollView
import com.pythonnative.runtime.views.PNNestedScrollView
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RoundTwoRobolectricTest {
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

    private fun events(vararg names: String): JSONArray = JSONArray().apply { names.forEach { put(it) } }

    @Test fun newModulesAreRegisteredAndAnswer() {
        val keyboard = com.pythonnative.generated.KeyboardModuleAdapter(BuiltinModules.keyboard)
        val visible = com.pythonnative.runtime.modules.Promise(1, "Keyboard")
        keyboard.call("is_visible", JSONObject(), visible)
        assertEquals(false, JSONObject(visible.markReturned()).getBoolean("value"))
        val localization = com.pythonnative.generated.LocalizationModuleAdapter(BuiltinModules.localization)
        val locales = com.pythonnative.runtime.modules.Promise(2, "Localization")
        localization.call("get_locales", JSONObject(), locales)
        val first = JSONObject(locales.markReturned()).getJSONArray("value").getJSONObject(0)
        assertTrue(first.getString("language_tag").isNotEmpty())
        assertTrue(first.has("is_rtl"))
        val timezone = com.pythonnative.runtime.modules.Promise(3, "Localization")
        localization.call("get_timezone", JSONObject(), timezone)
        assertEquals(java.util.TimeZone.getDefault().id, JSONObject(timezone.markReturned()).getString("value"))
        val a11y = com.pythonnative.generated.AccessibilityInfoModuleAdapter(BuiltinModules.accessibilityInfo)
        val reader = com.pythonnative.runtime.modules.Promise(4, "AccessibilityInfo")
        a11y.call("is_screen_reader_enabled", JSONObject(), reader)
        assertEquals(false, JSONObject(reader.markReturned()).getBoolean("value"))
        val motion = com.pythonnative.runtime.modules.Promise(5, "AccessibilityInfo")
        a11y.call("is_reduce_motion_enabled", JSONObject(), motion)
        assertTrue(JSONObject(motion.markReturned()).has("value"))
        val announce = com.pythonnative.runtime.modules.Promise(6, "AccessibilityInfo")
        a11y.call("announce", JSONObject().put("message", "Saved"), announce)
        assertTrue(JSONObject(announce.markReturned()).getBoolean("ok"))
        assertNotNull(com.pythonnative.runtime.bridge.PNRegistry.module("Keyboard"))
        assertNotNull(com.pythonnative.runtime.bridge.PNRegistry.module("Localization"))
        assertNotNull(com.pythonnative.runtime.bridge.PNRegistry.module("AccessibilityInfo"))
    }

    @Test fun scrollViewTypedPropsAndEventPayload() {
        val props = JSONObject().put("horizontal", false).put("scroll_event_throttle", 32)
            .put("content_inset", JSONObject().put("top", 10).put("bottom", 20)).put("deceleration_rate", "fast")
            .put("_pn_events", events("on_scroll"))
        applier.applyOp(Op.Create(30, "ScrollView", props))
        val outer = PNBridge.registry.get(30)!!.view as SwipeRefreshLayout
        val sv = outer.getChildAt(0) as PNNestedScrollView
        val density = activity.resources.displayMetrics.density
        assertEquals((10 * density).toInt(), sv.paddingTop)
        assertEquals((20 * density).toInt(), sv.paddingBottom)
        assertFalse(sv.clipToPadding)
        assertTrue(sv.flingScale < 1f)
        assertEquals(32.0, PNBridge.registry.get(30)!!.state["throttle_ms"])
        val manager = PNBridge.registry.get(30)!!.manager as ScrollViewManager
        val payload = com.pythonnative.generated.PNValues.encode(manager.scrollEvent(sv)) as JSONObject
        assertEquals(setOf("x", "y", "content_width", "content_height", "viewport_width", "viewport_height"), payload.keys().asSequence().toSet())
        applier.applyOp(Op.Update(30, JSONObject().put("deceleration_rate", "normal").put("content_inset", JSONObject.NULL)))
        assertEquals(1f, sv.flingScale, 0f)
        assertEquals(0, sv.paddingTop)
        applier.applyOp(Op.Create(31, "ScrollView", JSONObject().put("horizontal", true)))
        assertTrue(PNBridge.registry.get(31)!!.view is PNHorizontalScrollView)
    }

    @Test fun textPressableSpansAndLabelPress() {
        val spans = JSONArray().put(JSONObject().put("text", "Read the ")).put(JSONObject().put("text", "terms").put("pressable", true))
        applier.applyOp(Op.Create(32, "Text", JSONObject().put("spans", spans).put("_pn_events", events("on_span_press"))))
        val tv = PNBridge.registry.get(32)!!.view as TextView
        assertTrue(tv.movementMethod is LinkMovementMethod)
        val spanned = tv.text as android.text.Spanned
        val pressable = spanned.getSpans(0, spanned.length, com.pythonnative.runtime.components.PNPressableSpan::class.java)
        assertEquals(1, pressable.size)
        assertEquals(1, pressable[0].index)
        assertEquals(9, spanned.getSpanStart(pressable[0]))
        // The wire carries wired events only in `_pn_events`, never as an `on_press` prop.
        applier.applyOp(Op.Create(33, "Text", JSONObject().put("text", "tap").put("_pn_events", events("on_press"))))
        val label = PNBridge.registry.get(33)!!.view as TextView
        assertTrue(label.isClickable)
        assertTrue(label.hasOnClickListeners())
        applier.applyOp(Op.Update(33, JSONObject().put("_pn_events", events())))
        assertFalse(label.isClickable)
        applier.applyOp(Op.Create(34, "Text", JSONObject().put("text", "select me").put("selectable", true).put("ellipsize_mode", "middle").put("max_lines", 1)))
        val selectable = PNBridge.registry.get(34)!!.view as TextView
        assertTrue(selectable.isTextSelectable)
        assertEquals(android.text.TextUtils.TruncateAt.MIDDLE, selectable.ellipsize)
    }

    @Test fun spanTapsAreBoundedByTheGlyphs() {
        val spans = JSONArray().put(JSONObject().put("text", "Read the ")).put(JSONObject().put("text", "terms").put("pressable", true))
        applier.applyOp(Op.Create(40, "Text", JSONObject().put("spans", spans).put("_pn_events", events("on_span_press"))))
        val tv = PNBridge.registry.get(40)!!.view as TextView
        val method = com.pythonnative.runtime.components.PNSpanMovementMethod
        assertTrue(tv.movementMethod === method)
        val spanned = tv.text as android.text.Spanned
        // "Read the " is 0..9 and "terms" is 9..14.
        assertNull(method.spanAtOffset(spanned, 3))
        assertEquals(1, method.spanAtOffset(spanned, 9)?.index)
        assertEquals(1, method.spanAtOffset(spanned, 12)?.index)
        assertEquals("right half of the last glyph", 1, method.spanAtOffset(spanned, 14)?.index)
        // Robolectric's legacy graphics lay text out with zero-width glyphs,
        // so any x past the line's right edge is past the text.
        tv.measure(
            View.MeasureSpec.makeMeasureSpec(1000, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(200, View.MeasureSpec.AT_MOST),
        )
        tv.layout(0, 0, 1000, tv.measuredHeight)
        val layout = tv.layout!!
        val y = (layout.getLineTop(0) + layout.getLineBottom(0)) / 2f + tv.totalPaddingTop
        val pastEnd = layout.getLineRight(0) + tv.totalPaddingLeft + 40f
        assertNull("stock LinkMovementMethod would fire the last span here", method.spanAt(tv, spanned, pastEnd, y))
    }

    @Test fun textInputSelectionIsControlledAndKeyboardTypesApply() {
        applier.applyOp(Op.Create(35, "TextInput", JSONObject().put("value", "hello world").put("selection", JSONObject().put("start", 1).put("end", 4)).put("keyboard_type", "web_search")))
        val et = PNBridge.registry.get(35)!!.view as EditText
        assertEquals(1, et.selectionStart)
        assertEquals(4, et.selectionEnd)
        assertEquals(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH, et.imeOptions and android.view.inputmethod.EditorInfo.IME_MASK_ACTION)
        assertTrue(et.inputType and android.text.InputType.TYPE_TEXT_VARIATION_WEB_EDIT_TEXT != 0)
        // The same selection again does not touch the user's cursor; a new one does.
        et.setSelection(6, 6)
        applier.applyOp(Op.Update(35, JSONObject().put("placeholder", "x")))
        assertEquals(6, et.selectionStart)
        applier.applyOp(Op.Update(35, JSONObject().put("selection", JSONObject().put("start", 0).put("end", 11))))
        assertEquals(0, et.selectionStart)
        assertEquals(11, et.selectionEnd)
        applier.applyOp(Op.Update(35, JSONObject().put("keyboard_type", "visible_password")))
        assertTrue(et.inputType and android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD != 0)
    }

    @Test fun pressableRippleForegroundAndBackgroundModes() {
        val ripple = JSONObject().put("color", "#33000000").put("borderless", false).put("foreground", true)
        applier.applyOp(Op.Create(36, "Pressable", JSONObject().put("android_ripple", ripple).put("disabled", true).put("delay_long_press", 400)))
        val view = PNBridge.registry.get(36)!!.view
        assertTrue(view.foreground is RippleDrawable)
        assertFalse(view.isEnabled)
        applier.applyOp(Op.Update(36, JSONObject().put("android_ripple", JSONObject().put("color", JSONObject().put("light", "#22000000").put("dark", "#22ffffff")).put("foreground", false)).put("background_color", "#ff0000").put("disabled", false)))
        assertNull(view.foreground)
        assertTrue(view.background is RippleDrawable)
        assertTrue(view.isEnabled)
        // A later border change re-bakes the background and keeps the ripple beneath the children.
        applier.applyOp(Op.Update(36, JSONObject().put("border_radius", 8)))
        assertTrue(view.background is RippleDrawable)
        applier.applyOp(Op.Update(36, JSONObject().put("android_ripple", JSONObject.NULL)))
        assertFalse(view.background is RippleDrawable)
        assertNull(view.foreground)
    }

    @Test fun modalBackAsksPythonInsteadOfDismissing() {
        applier.applyOp(Op.Create(37, "Modal", JSONObject().put("visible", true).put("_pn_events", events("on_request_close"))))
        val record = PNBridge.registry.get(37)!!
        val dialog = record.state["dialog"] as Dialog
        val down = android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_BACK)
        val up = android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_BACK)
        dialog.onKeyDown(android.view.KeyEvent.KEYCODE_BACK, down)
        dialog.onKeyUp(android.view.KeyEvent.KEYCODE_BACK, up)
        assertTrue(dialog.isShowing)
        assertSame(dialog, record.state["dialog"])
        applier.applyOp(Op.Update(37, JSONObject().put("visible", false)))
        assertNull(record.state["dialog"])
    }

    @Test fun modalKeepsItsChildrenAcrossPresentations() {
        applier.applyOp(Op.Create(39, "Modal", JSONObject().put("visible", false)))
        applier.applyOp(Op.Create(40, "View", JSONObject()))
        applier.applyOp(Op.Insert(39, 40, 0))
        val record = PNBridge.registry.get(39)!!
        val child = PNBridge.registry.get(40)!!.view
        applier.applyOp(Op.Update(39, JSONObject().put("visible", true)))
        assertSame(record.state["content_view"], child.parent)
        applier.applyOp(Op.Update(39, JSONObject().put("visible", false)))
        assertNull(record.state["dialog"])
        applier.applyOp(Op.Update(39, JSONObject().put("visible", true)))
        val content = record.state["content_view"] as android.widget.FrameLayout
        assertSame("a reopened modal shows its children again", content, child.parent)
        assertEquals(1, content.childCount)
        applier.applyOp(Op.Update(39, JSONObject().put("visible", false)))
        applier.applyOp(Op.Destroy(40))
        assertNull("a destroyed child leaves the last dialog too", child.parent)
    }

    @Test fun overlayBackdropTapsNeverCloseTheModalNatively() {
        applier.applyOp(Op.Create(41, "Modal", JSONObject().put("visible", true).put("presentation_style", "overlay")))
        applier.applyOp(Op.Create(42, "View", JSONObject()))
        applier.applyOp(Op.Insert(41, 42, 0))
        val record = PNBridge.registry.get(41)!!
        val dialog = record.state["dialog"] as Dialog
        val content = record.state["content_view"] as android.widget.FrameLayout
        val child = PNBridge.registry.get(42)!!.view
        child.layout(10, 20, 110, 220)
        val manager = record.manager as com.pythonnative.runtime.components.ModalManager
        assertTrue(manager.isOnChild(content, 50f, 100f))
        assertFalse(manager.isOnChild(content, 300f, 400f))
        // Without on_request_close a backdrop tap leaves the modal open.
        content.performClick()
        assertTrue(dialog.isShowing)
        assertSame(dialog, record.state["dialog"])
    }

    @Test fun virtualListScrollPayloadKeepsListWindowFields() {
        applier.applyOp(Op.Create(38, "VirtualList", JSONObject("""{"dataset":{"base":0,"revision":1,"changes":[["reset",[["a",1,44,false],["b",1,44,false]]]]}}""")))
        val list = PNBridge.registry.get(38)!!.view
        val method = list.javaClass.getDeclaredMethod("scrollPayload").apply { isAccessible = true }
        val payload = method.invoke(list) as JSONObject
        for (key in listOf("x", "y", "content_width", "content_height", "viewport_width", "viewport_height", "first", "last", "extent", "range")) {
            assertTrue("missing $key", payload.has(key))
        }
    }
}
