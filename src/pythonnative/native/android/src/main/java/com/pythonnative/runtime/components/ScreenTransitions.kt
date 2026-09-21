package com.pythonnative.runtime.components

import com.pythonnative.runtime.R
import org.json.JSONObject

/**
 * Pure mapping from a `Screen`'s `animation` and `presentation` props to
 * the fragment transition resources the native stack runs.
 *
 * Animation values follow React Navigation's native stack: `default`
 * and `slide_from_right` slide the pushed screen in from the trailing
 * edge (the covered screen parks a third of the way off-screen) and
 * reverse on pop; `slide_from_bottom` slides up over a held screen and
 * slides back down on pop; `fade` cross-fades; `none` skips the
 * transition. Every modal presentation (`modal`, `full_screen_modal`,
 * `form_sheet`, `transparent_modal`) is a full-screen screen presented
 * with the bottom slide when `animation` is `default`, which is what
 * React Navigation does on Android; `transparent_modal` additionally
 * keeps the screen beneath it visible.
 */
object ScreenTransitions {
    /** Enter/exit animation resources; `0` means no animation. */
    data class Transition(val enter: Int, val exit: Int) {
        val isNone: Boolean get() = enter == 0 && exit == 0
    }

    /** Presentation values presented as bottom-sliding full-screen screens. */
    val MODAL_PRESENTATIONS: Set<String> = setOf("modal", "full_screen_modal", "form_sheet", "transparent_modal")

    /** The animation names the stack understands after `default` is resolved. */
    val ANIMATIONS: Set<String> = setOf("slide_from_right", "slide_from_bottom", "fade", "none")

    val NONE = Transition(0, 0)

    /**
     * The concrete animation for a screen: `default` resolves to
     * `slide_from_bottom` for modal presentations and `slide_from_right`
     * otherwise; unknown names fall back to `slide_from_right`.
     */
    fun effectiveAnimation(animation: String?, presentation: String?): String {
        val name = animation?.takeIf { it.isNotEmpty() } ?: "default"
        if (name == "default") return if (presentation in MODAL_PRESENTATIONS) "slide_from_bottom" else "slide_from_right"
        return if (name in ANIMATIONS) name else "slide_from_right"
    }

    /** [effectiveAnimation] read from raw `Screen` props. */
    fun effectiveAnimation(props: JSONObject?): String =
        effectiveAnimation(props?.optString("animation", "default"), props?.optString("presentation", "card"))

    /** Whether the screen keeps the one beneath it visible. */
    fun isTransparent(props: JSONObject?): Boolean = props?.optString("presentation", "card") == "transparent_modal"

    /** Transition for pushing a screen whose effective animation is `animation`. */
    fun push(animation: String): Transition = when (animation) {
        "none" -> NONE
        "fade" -> Transition(R.anim.pn_fade_in, R.anim.pn_fade_out)
        "slide_from_bottom" -> Transition(R.anim.pn_slide_in_bottom, R.anim.pn_hold)
        else -> Transition(R.anim.pn_slide_in_right, R.anim.pn_slide_out_left)
    }

    /** Transition for popping a screen whose effective animation is `animation` (the reverse of [push]). */
    fun pop(animation: String): Transition = when (animation) {
        "none" -> NONE
        "fade" -> Transition(R.anim.pn_fade_in, R.anim.pn_fade_out)
        "slide_from_bottom" -> Transition(R.anim.pn_hold, R.anim.pn_slide_out_bottom)
        else -> Transition(R.anim.pn_slide_in_left, R.anim.pn_slide_out_right)
    }

    /**
     * Which screens of `screens` (bottom to top) stay visible: the top
     * screen, plus every screen a run of transparent modals sits over.
     * `transparent` reports whether the screen at an index is a
     * `transparent_modal`. Returns the lowest visible index (or `-1`).
     */
    fun firstVisibleIndex(count: Int, transparent: (Int) -> Boolean): Int {
        if (count == 0) return -1
        var index = count - 1
        while (index > 0 && transparent(index)) index--
        return index
    }
}
