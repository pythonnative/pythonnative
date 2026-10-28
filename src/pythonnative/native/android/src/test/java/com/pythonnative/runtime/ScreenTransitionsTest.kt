package com.pythonnative.runtime

import com.pythonnative.runtime.R
import com.pythonnative.runtime.components.ScreenTransitions
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenTransitionsTest {
    @Test
    fun defaultAnimationDependsOnPresentation() {
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation("default", "card"))
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation(null, null))
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation("", "card"))
        for (presentation in listOf("modal", "full_screen_modal", "form_sheet", "transparent_modal")) {
            assertEquals(presentation, "slide_from_bottom", ScreenTransitions.effectiveAnimation("default", presentation))
        }
        // An explicit animation wins over the presentation's default.
        assertEquals("fade", ScreenTransitions.effectiveAnimation("fade", "modal"))
        assertEquals("none", ScreenTransitions.effectiveAnimation("none", "form_sheet"))
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation("slide_from_right", "modal"))
        // Unknown names degrade to the stack default.
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation("wobble", "card"))
    }

    @Test
    fun readsRawScreenProps() {
        assertEquals("slide_from_bottom", ScreenTransitions.effectiveAnimation(JSONObject().put("presentation", "modal")))
        assertEquals("fade", ScreenTransitions.effectiveAnimation(JSONObject().put("animation", "fade")))
        assertEquals("slide_from_right", ScreenTransitions.effectiveAnimation(null))
        assertTrue(ScreenTransitions.isTransparent(JSONObject().put("presentation", "transparent_modal")))
        assertFalse(ScreenTransitions.isTransparent(JSONObject().put("presentation", "modal")))
        assertFalse(ScreenTransitions.isTransparent(null))
    }

    @Test
    fun pushAndPopAreReverses() {
        val push = ScreenTransitions.push("slide_from_right")
        assertEquals(R.anim.pn_slide_in_right, push.enter)
        assertEquals(R.anim.pn_slide_out_left, push.exit)
        val pop = ScreenTransitions.pop("slide_from_right")
        assertEquals(R.anim.pn_slide_in_left, pop.enter)
        assertEquals(R.anim.pn_slide_out_right, pop.exit)

        val sheetPush = ScreenTransitions.push("slide_from_bottom")
        assertEquals(R.anim.pn_slide_in_bottom, sheetPush.enter)
        assertEquals(R.anim.pn_hold, sheetPush.exit)
        val sheetPop = ScreenTransitions.pop("slide_from_bottom")
        assertEquals(R.anim.pn_hold, sheetPop.enter)
        assertEquals(R.anim.pn_slide_out_bottom, sheetPop.exit)

        assertEquals(ScreenTransitions.Transition(R.anim.pn_fade_in, R.anim.pn_fade_out), ScreenTransitions.push("fade"))
        assertEquals(ScreenTransitions.Transition(R.anim.pn_fade_in, R.anim.pn_fade_out), ScreenTransitions.pop("fade"))
        assertTrue(ScreenTransitions.push("none").isNone)
        assertTrue(ScreenTransitions.pop("none").isNone)
        assertFalse(push.isNone)
    }

    @Test
    fun transparentModalsKeepTheScreenBeneathVisible() {
        // [card, card] -> only the top is visible.
        assertEquals(1, ScreenTransitions.firstVisibleIndex(2) { false })
        // [card, transparent] -> both visible.
        assertEquals(0, ScreenTransitions.firstVisibleIndex(2) { it == 1 })
        // [card, card, transparent, transparent] -> the run of transparents plus the card beneath.
        assertEquals(1, ScreenTransitions.firstVisibleIndex(4) { it >= 2 })
        // A transparent modal at the root still shows itself.
        assertEquals(0, ScreenTransitions.firstVisibleIndex(1) { true })
        assertEquals(-1, ScreenTransitions.firstVisibleIndex(0) { true })
    }
}
