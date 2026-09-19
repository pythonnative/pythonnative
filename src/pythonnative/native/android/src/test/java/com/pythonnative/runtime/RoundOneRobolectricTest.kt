package com.pythonnative.runtime

import android.app.Activity
import android.app.Dialog
import android.graphics.drawable.ColorDrawable
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import androidx.core.graphics.Insets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.pythonnative.runtime.bridge.Op
import com.pythonnative.runtime.bridge.TransactionApplier
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.PNTheme
import com.pythonnative.runtime.components.TextManager
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.CameraModule
import com.pythonnative.runtime.screens.PNKeyboard
import com.pythonnative.runtime.screens.Viewport
import com.pythonnative.runtime.views.PNAccessibilityDelegate
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RoundOneRobolectricTest {
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

    @Test fun viewportCarriesScaleFontScaleAndScreenSize() {
        val payload = Viewport.describe(activity.window.decorView)
        for (key in listOf("width", "height", "insets", "color_scheme", "keyboard_height", "scale", "font_scale", "screen_width", "screen_height")) {
            assertTrue("missing $key", payload.has(key))
        }
        assertEquals(activity.resources.displayMetrics.density.toDouble(), payload.getDouble("scale"), 1e-9)
        assertEquals(activity.resources.configuration.fontScale.toDouble(), payload.getDouble("font_scale"), 1e-9)
        assertTrue(payload.getDouble("screen_width") > 0.0)
        assertTrue(payload.getDouble("screen_height") > 0.0)
        assertEquals("light", payload.getString("color_scheme"))
    }

    @Test fun deviceInfoReturnsTheDeviceInfoKeys() {
        val info = BuiltinModules.device.info().mapValues { it.value.value }
        val expected = setOf(
            "platform", "os_version", "model", "manufacturer", "is_simulator", "is_tablet", "app_name", "app_version",
            "build_number", "bundle_id", "scale", "font_scale", "locale", "app_dir",
        )
        assertEquals(expected, info.keys)
        assertEquals("android", info["platform"])
        assertEquals(activity.packageName, info["bundle_id"])
        assertTrue(info["is_tablet"] is Boolean)
        assertTrue(info["is_simulator"] is Boolean)
        assertTrue((info["build_number"] as String).toLong() >= 0L)
        assertEquals(activity.resources.displayMetrics.density.toDouble(), info["scale"] as Double, 1e-9)
        assertTrue((info["locale"] as String).isNotEmpty())
        assertEquals(activity.filesDir.absolutePath, info["app_dir"])
    }

    @Test fun keyboardObserverSeesInsetsBeforeTheWindowConsumesThem() {
        // Under adjustResize the window pads the content for the IME and
        // consumes the inset on the way down, as this parent does here.
        val density = activity.resources.displayMetrics.density
        val content = activity.findViewById<View>(android.R.id.content)
        val parent = content.parent as View
        var contentSawInsets = false
        ViewCompat.setOnApplyWindowInsetsListener(parent) { _, _ -> WindowInsetsCompat.CONSUMED }
        ViewCompat.setOnApplyWindowInsetsListener(content) { _, insets ->
            contentSawInsets = true
            insets
        }
        try {
            PNKeyboard.attach(activity)
            val shown = WindowInsetsCompat.Builder()
                .setInsets(WindowInsetsCompat.Type.ime(), Insets.of(0, 0, 0, (300 * density).toInt()))
                .setVisible(WindowInsetsCompat.Type.ime(), true)
                .build()
            activity.window.decorView.dispatchApplyWindowInsets(shown.toWindowInsets())
            assertFalse("the parent consumed the insets", contentSawInsets)
            assertTrue(PNKeyboard.isVisible)
            assertEquals(300.0, PNKeyboard.heightDp, 0.5)
        } finally {
            ViewCompat.setOnApplyWindowInsetsListener(parent, null)
            ViewCompat.setOnApplyWindowInsetsListener(content, null)
            PNKeyboard.update(
                WindowInsetsCompat.Builder()
                    .setInsets(WindowInsetsCompat.Type.ime(), Insets.of(0, 0, 0, 0))
                    .setVisible(WindowInsetsCompat.Type.ime(), false)
                    .build(),
            )
        }
    }

    @Test fun keyboardObserverReportsHeightAboveTheNavigationBar() {
        val density = activity.resources.displayMetrics.density
        val events = ArrayList<Triple<Double, Boolean, Long>>()
        val remove = PNKeyboard.addListener { height, visible, duration -> events.add(Triple(height, visible, duration)) }
        try {
            val shown = WindowInsetsCompat.Builder()
                .setInsets(WindowInsetsCompat.Type.systemBars(), Insets.of(0, (24 * density).toInt(), 0, (48 * density).toInt()))
                .setInsets(WindowInsetsCompat.Type.ime(), Insets.of(0, 0, 0, (348 * density).toInt()))
                .setVisible(WindowInsetsCompat.Type.ime(), true)
                .build()
            PNKeyboard.update(shown)
            assertEquals(300.0, PNKeyboard.heightDp, 0.5)
            assertTrue(PNKeyboard.isVisible)
            assertEquals(1, events.size)
            // The same insets again are not re-announced.
            PNKeyboard.update(shown)
            assertEquals(1, events.size)
            val hidden = WindowInsetsCompat.Builder()
                .setInsets(WindowInsetsCompat.Type.systemBars(), Insets.of(0, (24 * density).toInt(), 0, (48 * density).toInt()))
                .setInsets(WindowInsetsCompat.Type.ime(), Insets.of(0, 0, 0, 0))
                .setVisible(WindowInsetsCompat.Type.ime(), false)
                .build()
            PNKeyboard.update(hidden)
            assertEquals(0.0, PNKeyboard.heightDp, 0.0)
            assertFalse(PNKeyboard.isVisible)
            assertEquals(2, events.size)
            assertEquals(false, events[1].second)
        } finally {
            remove()
        }
    }

    @Test fun hintJoinsTheLabelInTheContentDescription() {
        applier.applyOp(Op.Create(20, "View", JSONObject().put("accessibility_label", "Save").put("accessibility_hint", "Saves the draft")))
        val view = PNBridge.registry.get(20)!!.view
        assertEquals("Save, Saves the draft", view.contentDescription.toString())
        assertNull(if (android.os.Build.VERSION.SDK_INT >= 26) view.tooltipText else null)
        applier.applyOp(Op.Update(20, JSONObject().put("accessibility_hint", JSONObject.NULL)))
        assertEquals("Save", view.contentDescription.toString())
    }

    @Test fun accessibilityActionsAndImportanceReachTheView() {
        val props = JSONObject()
            .put("important_for_accessibility", "no_hide_descendants")
            .put("accessibility_actions", JSONArray("""[{"name": "activate"}, {"name": "archive", "label": "Archive"}]"""))
            .put("accessibility_value", JSONObject().put("min", 0).put("max", 10).put("now", 4).put("text", "4 of 10"))
        applier.applyOp(Op.Create(21, "View", props))
        val view = PNBridge.registry.get(21)!!.view
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS, view.importantForAccessibility)
        val delegate = PNBridge.registry.get(21)!!.state["a11y_delegate"] as PNAccessibilityDelegate
        assertEquals(listOf("activate", "archive"), delegate.actions.map { it.name })
        assertEquals(4.0, delegate.valueNow!!, 0.0)
        assertEquals("4 of 10", delegate.valueText)
        // A mapped action is consumed by the delegate (and fires on_accessibility_action).
        assertTrue(delegate.performAccessibilityAction(view, PNAccessibilityDelegate.STANDARD_ACTIONS.getValue("activate"), null))
        assertTrue(delegate.performAccessibilityAction(view, PNAccessibilityDelegate.CUSTOM_ACTION_IDS[0], null))
        val info = android.view.accessibility.AccessibilityNodeInfo.obtain(view)
        delegate.onInitializeAccessibilityNodeInfo(view, info)
        assertNotNull(info.rangeInfo)
        assertEquals(4f, info.rangeInfo.current, 0f)
        assertTrue(info.actionList.any { it.id == PNAccessibilityDelegate.CUSTOM_ACTION_IDS[0] && it.label == "Archive" })
    }

    @Test fun clipEllipsizeModeDisablesTheEllipsis() {
        val manager = TextManager()
        assertNull(manager.ellipsizeMode("clip"))
        assertEquals(android.text.TextUtils.TruncateAt.START, manager.ellipsizeMode("head"))
        assertEquals(android.text.TextUtils.TruncateAt.MIDDLE, manager.ellipsizeMode("middle"))
        assertEquals(android.text.TextUtils.TruncateAt.END, manager.ellipsizeMode("tail"))
        assertEquals(android.text.TextUtils.TruncateAt.END, manager.ellipsizeMode(null))
        applier.applyOp(Op.Create(22, "Text", JSONObject().put("text", "hello").put("max_lines", 2)))
        val tv = PNBridge.registry.get(22)!!.view as TextView
        assertEquals(2, tv.maxLines)
        assertEquals(android.text.TextUtils.TruncateAt.END, tv.ellipsize)
        applier.applyOp(Op.Update(22, JSONObject().put("max_lines", JSONObject.NULL)))
        assertEquals(Int.MAX_VALUE, tv.maxLines)
        assertNull(tv.ellipsize)
    }

    @Test fun tabBarAndModalUseThemeColorsInsteadOfWhite() {
        // BottomNavigationView insists on a Material/AppCompat theme, as the app template provides.
        activity.setTheme(com.google.android.material.R.style.Theme_MaterialComponents_DayNight_NoActionBar)
        applier.applyOp(Op.Create(23, "TabBar", JSONObject().put("items", JSONArray("""[{"name": "a", "title": "A"}]""")).put("active_tab", "a")))
        val bar = PNBridge.registry.get(23)!!.view as BottomNavigationView
        assertEquals(PNTheme.surface(activity), (bar.background as ColorDrawable).color)
        applier.applyOp(Op.Update(23, JSONObject().put("background_color", "#123456")))
        assertEquals(0xFF123456.toInt(), (bar.background as ColorDrawable).color)

        applier.applyOp(Op.Create(24, "Modal", JSONObject().put("visible", true)))
        val record = PNBridge.registry.get(24)!!
        val content = record.state["content_view"] as FrameLayout
        assertEquals(PNTheme.background(activity), (content.background as ColorDrawable).color)
        (record.state["dialog"] as Dialog).dismiss()
    }

    @Test fun cameraCaptureFilesLiveInTheCacheDirectory() {
        val file = CameraModule.newCaptureFile(activity)
        assertTrue(file.absolutePath.startsWith(activity.cacheDir.absolutePath))
        assertTrue(file.name.endsWith(".jpg"))
        assertEquals(activity.packageName + ".pythonnative.fileprovider", CameraModule.authority(activity))
        file.delete()
    }

    @Test fun screensPaintTheThemeBackgroundUnlessTransparent() {
        applier.applyOp(Op.Create(25, "Screen", JSONObject().put("route_key", "a").put("title", "A")))
        val screen = PNBridge.registry.get(25)!!.view
        assertEquals(PNTheme.background(activity), (screen.background as ColorDrawable).color)
        applier.applyOp(Op.Create(26, "Screen", JSONObject().put("route_key", "b").put("background_color", "#ff0000")))
        assertNotEquals(PNTheme.background(activity), (PNBridge.registry.get(26)!!.view.background as? ColorDrawable)?.color)
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "night")
class RoundOneNightModeTest {
    @Test fun dynamicColorsFollowTheActivityUiMode() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        PNBridge.setContext(activity)
        try {
            assertTrue(PNTheme.isDark(activity))
            assertTrue(PNColor.isDarkMode())
            assertEquals(0xFF000000.toInt(), PNColor.parse(JSONObject("""{"light": "#ffffff", "dark": "#000000"}""")))
            val payload = Viewport.describe(activity.window.decorView)
            assertEquals("dark", payload.getString("color_scheme"))
        } finally {
            PNBridge.clearContext(activity)
            activity.finish()
        }
    }
}
