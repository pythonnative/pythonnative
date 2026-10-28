package com.pythonnative.runtime

import android.view.View
import com.pythonnative.runtime.components.ViewStyler
import com.pythonnative.runtime.modules.CameraModule
import com.pythonnative.runtime.modules.DeviceModule
import com.pythonnative.runtime.views.PNAccessibilityDelegate
import com.pythonnative.runtime.views.PNBorderDrawable
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StyleAccessibilityDeviceTest {
    @Test
    fun hintIsAppendedToTheContentDescription() {
        assertEquals("Save, Saves the draft", ViewStyler.contentDescription("Save", "Saves the draft"))
        assertEquals("Save", ViewStyler.contentDescription("Save", null))
        assertEquals("Save", ViewStyler.contentDescription("Save", ""))
        assertEquals("Saves the draft", ViewStyler.contentDescription(null, "Saves the draft"))
        assertNull(ViewStyler.contentDescription(null, null))
    }

    @Test
    fun importantForAccessibilityMapsEveryValue() {
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO, ViewStyler.importantForAccessibility("auto"))
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_YES, ViewStyler.importantForAccessibility("yes"))
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO, ViewStyler.importantForAccessibility("no"))
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS, ViewStyler.importantForAccessibility("no_hide_descendants"))
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO, ViewStyler.importantForAccessibility(null))
    }

    @Test
    fun accessibilityActionsDecodeAndTakeIds() {
        val actions = ViewStyler.accessibilityActions(
            JSONArray("""[{"name": "activate"}, {"name": "archive", "label": "Archive thread"}, "snooze", {"label": "no name"}, ""]"""),
        )
        assertEquals(
            listOf(
                PNAccessibilityDelegate.Action("activate", null),
                PNAccessibilityDelegate.Action("archive", "Archive thread"),
                PNAccessibilityDelegate.Action("snooze", null),
            ),
            actions,
        )
        assertTrue(ViewStyler.accessibilityActions("nope").isEmpty())
        val ids = PNAccessibilityDelegate.assignIds(actions, intArrayOf(1001, 1002))
        assertEquals("activate", ids[PNAccessibilityDelegate.STANDARD_ACTIONS.getValue("activate")])
        assertEquals("archive", ids[1001])
        assertEquals("snooze", ids[1002])
        // The pool is finite; extra custom actions are dropped, standard ones never are.
        val many = (0 until 5).map { PNAccessibilityDelegate.Action("custom$it", null) } + PNAccessibilityDelegate.Action("longpress", null)
        val limited = PNAccessibilityDelegate.assignIds(many, intArrayOf(7, 8))
        assertEquals(setOf("custom0", "custom1", "longpress"), limited.values.toSet())
        assertEquals(16, PNAccessibilityDelegate.CUSTOM_ACTION_IDS.size)
        assertEquals(16, PNAccessibilityDelegate.CUSTOM_ACTION_IDS.toSet().size)
    }

    @Test
    fun borderStyleNormalizesAndDashIntervalsScaleWithWidth() {
        assertEquals("dashed", ViewStyler.borderStyle(JSONObject().put("border_style", "dashed")))
        assertEquals("dotted", ViewStyler.borderStyle(JSONObject().put("border_style", "dotted")))
        assertEquals("solid", ViewStyler.borderStyle(JSONObject().put("border_style", "solid")))
        assertEquals("solid", ViewStyler.borderStyle(JSONObject().put("border_style", "wavy")))
        assertEquals("solid", ViewStyler.borderStyle(JSONObject()))
        assertEquals(2f to 2f, PNBorderDrawable.dashIntervals("dotted", 2f))
        assertEquals(6f to 4f, PNBorderDrawable.dashIntervals("dashed", 2f))
        assertEquals(1f to 0f, PNBorderDrawable.dashIntervals("solid", 1f))
        // Sub-pixel widths still produce a visible pattern.
        assertEquals(1f to 1f, PNBorderDrawable.dashIntervals("dotted", 0.4f))
    }

    @Test
    fun deviceHelpers() {
        assertTrue(DeviceModule.isTablet(600))
        assertTrue(DeviceModule.isTablet(720))
        assertFalse(DeviceModule.isTablet(599))
        assertFalse(DeviceModule.isTablet(411))
        assertTrue(DeviceModule.isEmulator(fingerprint = "google/sdk_gphone64_arm64/emu64a:14/UE1A/1:user", model = "sdk_gphone64_arm64", product = "sdk_gphone64_arm64", hardware = "ranchu", brand = "google", device = "emu64a", manufacturer = "Google"))
        assertTrue(DeviceModule.isEmulator(fingerprint = "generic/x86", model = "x", product = "x", hardware = "x", brand = "x", device = "x", manufacturer = "x"))
        assertFalse(DeviceModule.isEmulator(fingerprint = "google/panther/panther:14/UQ1A/1:user/release-keys", model = "Pixel 7", product = "panther", hardware = "panther", brand = "google", device = "panther", manufacturer = "Google"))
        assertEquals(".pythonnative.fileprovider", CameraModule.AUTHORITY_SUFFIX)
    }
}
