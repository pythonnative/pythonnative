package com.pythonnative.runtime

import android.text.InputType
import com.pythonnative.runtime.components.ScrollMath
import com.pythonnative.runtime.components.TextInputManager
import com.pythonnative.runtime.modules.AccessibilityInfoModule
import com.pythonnative.runtime.modules.KeyboardModule
import com.pythonnative.runtime.modules.LocalizationModule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

class RoundTwoLogicTest {
    @Test
    fun snapTargetsHonorAlignmentAndRange() {
        // Pages of 300 in a 300 viewport, content 900: plain paging.
        assertEquals(300.0, ScrollMath.snapTarget(160.0, 300.0, 300.0, "start", 900.0), 0.0)
        assertEquals(0.0, ScrollMath.snapTarget(140.0, 300.0, 300.0, "start", 900.0), 0.0)
        assertEquals(600.0, ScrollMath.snapTarget(1000.0, 300.0, 300.0, "start", 900.0), 0.0)
        // Items of 100 in a 300 viewport: center alignment offsets by (300 - 100) / 2.
        assertEquals(100.0, ScrollMath.snapTarget(120.0, 100.0, 300.0, "center", 1000.0), 0.0)
        assertEquals(0.0, ScrollMath.snapTarget(20.0, 100.0, 300.0, "center", 1000.0), 0.0)
        // End alignment: an item's trailing edge meets the viewport's end.
        assertEquals(200.0, ScrollMath.snapTarget(230.0, 100.0, 300.0, "end", 1000.0), 0.0)
        // Never past the scrollable range or below zero.
        assertEquals(700.0, ScrollMath.snapTarget(5000.0, 100.0, 300.0, "start", 1000.0), 0.0)
        assertEquals(0.0, ScrollMath.snapTarget(-40.0, 100.0, 300.0, "start", 1000.0), 0.0)
    }

    @Test
    fun flingScaleShortensFastDeceleration() {
        assertEquals(1f, ScrollMath.flingScale("normal"), 0f)
        assertEquals(1f, ScrollMath.flingScale(null), 0f)
        assertEquals(1f, ScrollMath.flingScale(0.998), 1e-6f)
        val fast = ScrollMath.flingScale("fast")
        assertTrue(fast < 1f && fast > 0.3f)
        assertEquals(fast, ScrollMath.flingScale(0.99), 1e-6f)
        // Slower than normal is clamped to the platform fling, and garbage leaves it alone.
        assertEquals(1f, ScrollMath.flingScale(0.999), 0f)
        assertEquals(1f, ScrollMath.flingScale(1.0), 0f)
        assertEquals(1f, ScrollMath.flingScale("bogus"), 0f)
    }

    @Test
    fun keyPressDiffs() {
        assertEquals("a", TextInputManager.keyFor("a", 0, 0, 1))
        assertEquals("!", TextInputManager.keyFor("hi!", 2, 0, 1))
        assertEquals("Enter", TextInputManager.keyFor("hi\n", 2, 0, 1))
        assertEquals("Backspace", TextInputManager.keyFor("h", 1, 1, 0))
        assertNull(TextInputManager.keyFor("pasted", 0, 0, 6))
        assertNull(TextInputManager.keyFor("x", 0, 1, 1))
        assertNull(TextInputManager.keyFor("", 0, 3, 0))
    }

    @Test
    fun keyboardTypesMapToInputTypes() {
        val manager = TextInputManager()
        assertEquals(InputType.TYPE_CLASS_TEXT, manager.inputTypeFor("default"))
        assertEquals(InputType.TYPE_CLASS_TEXT, manager.inputTypeFor("ascii"))
        assertEquals(InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_SIGNED or InputType.TYPE_NUMBER_FLAG_DECIMAL, manager.inputTypeFor("numbers_and_punctuation"))
        assertEquals(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_WEB_EDIT_TEXT, manager.inputTypeFor("web_search"))
        assertEquals(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD, manager.inputTypeFor("visible_password"))
        assertEquals(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS, manager.inputTypeFor("email_address"))
        assertEquals(InputType.TYPE_CLASS_PHONE, manager.inputTypeFor("phone_pad"))
    }

    @Test
    fun modulePayloadsMatchTheContracts() {
        val keyboard = KeyboardModule.payload(216.5, true, 250L).mapValues { it.value.value }
        assertEquals(mapOf("height" to 216.5, "visible" to true, "duration_ms" to 250.0), keyboard)
        val a11y = AccessibilityInfoModule.payload(screenReader = true, reduceMotion = false).mapValues { it.value.value }
        assertEquals(mapOf("screen_reader" to true, "reduce_motion" to false), a11y)
        val en = LocalizationModule.describe(Locale.forLanguageTag("en-US")).mapValues { it.value.value }
        assertEquals(mapOf("language_tag" to "en-US", "language_code" to "en", "region_code" to "US", "is_rtl" to false), en)
        val ar = LocalizationModule.describe(Locale.forLanguageTag("ar-EG")).mapValues { it.value.value }
        assertEquals("ar", ar["language_code"])
        assertEquals(true, ar["is_rtl"])
        val bare = LocalizationModule.describe(Locale("fr")).mapValues { it.value.value }
        assertEquals("", bare["region_code"])
        assertFalse(LocalizationModule.isRtl(Locale.JAPAN))
        assertTrue(LocalizationModule.isRtl(Locale("he")))
    }
}
