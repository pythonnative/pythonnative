package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.HorizontalScrollView
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.obj
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.views.PNHorizontalScrollView
import com.pythonnative.runtime.views.PNNestedScrollView
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * `ScrollView` element: a `NestedScrollView` (vertical, always wrapped in
 * a `SwipeRefreshLayout` that is enabled only while `refresh_control`
 * is set) or a `HorizontalScrollView`; `horizontal` picks at creation
 * (the contract recreates the view when it changes).
 *
 * Every scroll event (`on_scroll`, `on_scroll_begin_drag`,
 * `on_scroll_end_drag`, `on_momentum_scroll_end`) carries a
 * `ScrollEvent` `{x, y, content_width, content_height, viewport_width,
 * viewport_height}` in dp and fires only when the app wired it.
 * `scroll_event_throttle` (ms) rate-limits `on_scroll` with a trailing
 * emit so the resting offset always lands. Drag events come from the
 * touch stream (first move / release); momentum end is detected by
 * polling the offset until it stops moving, after which
 * `snap_to_interval` / `paging_enabled` snap the offset (with
 * `snap_to_alignment`) and momentum end fires once settled.
 *
 * `content_inset` becomes padding with `clipToPadding=false`.
 * `deceleration_rate` scales fling velocity (see [ScrollMath.flingScale])
 * because the platform scrollers hide their friction.
 * `keyboard_should_persist_taps="never"` (the default) hides the IME
 * when a touch lands on the scroll view outside an input;
 * `keyboard_dismiss_mode="on_drag"` hides it as the user drags.
 * Commands: `scroll_to_offset`, `scroll_to_end`, `get_scroll_offset`,
 * `flash_scroll_indicators`.
 */
class ScrollViewManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val horizontal = JsonUtil.truthy(props.value("horizontal"))
        return if (horizontal) {
            val sv = PNHorizontalScrollView(context)
            sv.clipToPadding = false
            bindScrollListener(sv, sv, true)
            bindTouch(sv, sv, true)
            sv
        } else {
            val sv = PNNestedScrollView(context)
            sv.clipToPadding = false
            val wrapper = SwipeRefreshLayout(context)
            wrapper.addView(sv, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            wrapper.isEnabled = false
            wrapper.setOnRefreshListener { fire(wrapper, "on_refresh") }
            bindScrollListener(wrapper, sv, false)
            bindTouch(wrapper, sv, false)
            wrapper
        }
    }

    private fun inner(outer: View): ViewGroup = when (outer) {
        is SwipeRefreshLayout -> outer.getChildAt(0) as ViewGroup
        else -> outer as ViewGroup
    }

    private fun isHorizontal(outer: View): Boolean = outer is HorizontalScrollView

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = ScrollViewProps(props, validated = true)
        val sv = inner(view)
        ViewStyler.apply(sv, props)
        if (typed.has_shows_scroll_indicator) {
            val show = typed.shows_scroll_indicator != false
            sv.isVerticalScrollBarEnabled = show
            sv.isHorizontalScrollBarEnabled = show
        }
        if (typed.has_bounces) {
            sv.overScrollMode = if (typed.bounces == false) View.OVER_SCROLL_NEVER else View.OVER_SCROLL_IF_CONTENT_SCROLLS
        }
        if (typed.has_scroll_enabled) stateOf(view)["scroll_enabled"] = typed.scroll_enabled != false
        if (typed.has_scroll_event_throttle) stateOf(view)["throttle_ms"] = typed.scroll_event_throttle ?: 0.0
        if (typed.has_content_inset) applyContentInset(sv, typed.content_inset)
        if (typed.has_deceleration_rate) {
            val scale = ScrollMath.flingScale(typed.deceleration_rate?.let { PNValues.encode(it) })
            when (sv) {
                is PNNestedScrollView -> sv.flingScale = scale
                is PNHorizontalScrollView -> sv.flingScale = scale
            }
        }
        if (typed.has_refresh_control && view is SwipeRefreshLayout) applyRefresh(view, props.obj("refresh_control"))
        // paging_enabled, snap_to_*, keyboard_* are read from merged props at touch time.
    }

    private fun applyContentInset(sv: ViewGroup, inset: PNEdgeInsets?) {
        if (inset == null) {
            sv.setPadding(0, 0, 0, 0)
            return
        }
        // Typed by the shared interface: the generated union's name follows
        // whichever component first declares it, which a plugin can change.
        fun side(value: PNNativeValue?, fallback: Double): Double = value?.let { JsonUtil.toDoubleOrNull(PNValues.encode(it)) } ?: fallback
        val all = side(inset.all, 0.0)
        val horizontal = side(inset.horizontal, all)
        val vertical = side(inset.vertical, all)
        sv.setPadding(px(side(inset.left, horizontal)), px(side(inset.top, vertical)), px(side(inset.right, horizontal)), px(side(inset.bottom, vertical)))
    }

    private fun applyRefresh(srl: SwipeRefreshLayout, spec: JSONObject?) {
        if (spec == null) {
            srl.isEnabled = false
            srl.isRefreshing = false
            return
        }
        srl.isEnabled = true
        PNColor.parse(spec.value("tint_color"))?.let { srl.setColorSchemeColors(it) }
        PNColor.parse(spec.value("background_color"))?.let { srl.setProgressBackgroundColorSchemeColor(it) }
        srl.isRefreshing = JsonUtil.truthy(spec.value("refreshing"))
    }

    override fun insertChild(parent: View, child: View, index: Int) = ViewChildren.insert(inner(parent), child, index)

    override fun removeChild(parent: View, child: View) {
        inner(parent).removeView(child)
    }

    // ------------------------------------------------------------------
    // Events
    // ------------------------------------------------------------------

    /** The `ScrollEvent` payload for the scroll view's current offset. */
    fun scrollEvent(sv: ViewGroup): PNScrollEvent {
        val content = if (sv.childCount > 0) sv.getChildAt(0) else null
        return PNScrollEvent(
            x = dp(sv.scrollX),
            y = dp(sv.scrollY),
            content_width = dp(content?.width ?: sv.width),
            content_height = dp(content?.height ?: sv.height),
            viewport_width = dp(sv.width),
            viewport_height = dp(sv.height),
        )
    }

    private fun bindScrollListener(outer: View, sv: ViewGroup, horizontal: Boolean) {
        sv.setOnScrollChangeListener { _, _, _, _, _ -> emitScroll(outer, sv) }
    }

    /** Emit `on_scroll`, honoring `scroll_event_throttle` with a trailing emit. */
    private fun emitScroll(outer: View, sv: ViewGroup) {
        if (!hasEvent(outer, "on_scroll")) return
        val state = stateOf(outer)
        val throttle = (state["throttle_ms"] as? Double) ?: 0.0
        val now = SystemClock.uptimeMillis()
        val last = (state["last_scroll_emit"] as? Long) ?: 0L
        if (throttle > 0 && now - last < throttle) {
            if (state["trailing_scroll"] != true) {
                state["trailing_scroll"] = true
                MainThread.postDelayed({
                    state["trailing_scroll"] = false
                    if (recordOf(outer) != null && hasEvent(outer, "on_scroll")) {
                        state["last_scroll_emit"] = SystemClock.uptimeMillis()
                        PNComponentEvents.ScrollView.on_scroll(outer, scrollEvent(sv))
                    }
                }, (throttle - (now - last)).toLong().coerceAtLeast(1L))
            }
            return
        }
        state["last_scroll_emit"] = now
        PNComponentEvents.ScrollView.on_scroll(outer, scrollEvent(sv))
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun bindTouch(outer: View, sv: ViewGroup, horizontal: Boolean) {
        sv.setOnTouchListener { v, event ->
            val merged = propsOf(outer)
            val state = stateOf(outer)
            if (state["scroll_enabled"] == false) return@setOnTouchListener true
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    state["settle_token"] = ((state["settle_token"] as? Int) ?: 0) + 1
                    state["dragging"] = false
                    if ((merged.str("keyboard_should_persist_taps") ?: "never") == "never") dismissKeyboardForTap(v)
                }
                MotionEvent.ACTION_MOVE -> {
                    if (state["dragging"] != true) {
                        state["dragging"] = true
                        if (hasEvent(outer, "on_scroll_begin_drag")) PNComponentEvents.ScrollView.on_scroll_begin_drag(outer, scrollEvent(sv))
                    }
                    val mode = merged.str("keyboard_dismiss_mode")
                    if (mode == "on_drag" || mode == "interactive") dismissKeyboard(v)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    if (state["dragging"] == true) {
                        state["dragging"] = false
                        if (hasEvent(outer, "on_scroll_end_drag")) PNComponentEvents.ScrollView.on_scroll_end_drag(outer, scrollEvent(sv))
                        settle(outer, sv, horizontal, snapped = false)
                    }
                }
            }
            false
        }
    }

    /** Hide the IME when a tap lands on the scroll view itself rather than on an input. */
    private fun dismissKeyboardForTap(view: View) {
        val focused = view.rootView.findFocus() as? EditText ?: return
        dismissKeyboard(view)
        focused.clearFocus()
    }

    private fun dismissKeyboard(view: View) {
        val focused = view.rootView.findFocus() ?: return
        focused.clearFocus()
        (view.context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager)
            ?.hideSoftInputFromWindow(view.windowToken, 0)
    }

    /**
     * Wait for the offset to stop moving (two identical 50 ms samples).
     * Then snap to the configured interval if needed (and settle again),
     * otherwise report `on_momentum_scroll_end`.
     */
    private fun settle(outer: View, sv: ViewGroup, horizontal: Boolean, snapped: Boolean) {
        val state = stateOf(outer)
        val token = ((state["settle_token"] as? Int) ?: 0) + 1
        state["settle_token"] = token
        var last = -1
        val poll = object : Runnable {
            override fun run() {
                if (state["settle_token"] != token || recordOf(outer) == null) return
                val current = if (horizontal) sv.scrollX else sv.scrollY
                if (current != last) {
                    last = current
                    MainThread.postDelayed(this, 50)
                    return
                }
                val target = if (snapped) null else snapTarget(outer, sv, horizontal, current)
                if (target != null && target != current) {
                    when (sv) {
                        is NestedScrollView -> sv.smoothScrollTo(0, target)
                        is HorizontalScrollView -> sv.smoothScrollTo(target, 0)
                    }
                    settle(outer, sv, horizontal, snapped = true)
                    return
                }
                if (hasEvent(outer, "on_momentum_scroll_end")) PNComponentEvents.ScrollView.on_momentum_scroll_end(outer, scrollEvent(sv))
            }
        }
        MainThread.postDelayed(poll, 50)
    }

    /** The snapped offset for `current`, or `null` when no snapping is configured. */
    private fun snapTarget(outer: View, sv: ViewGroup, horizontal: Boolean, current: Int): Int? {
        val merged = propsOf(outer)
        val viewport = if (horizontal) sv.width else sv.height
        if (viewport <= 0) return null
        val content = if (sv.childCount > 0) sv.getChildAt(0) else null
        val contentSize = (if (horizontal) content?.width else content?.height) ?: viewport
        val interval: Double = when {
            merged.value("snap_to_interval") != null -> pxF(JsonUtil.toDouble(merged.value("snap_to_interval"))).toDouble()
            JsonUtil.truthy(merged.value("paging_enabled")) -> viewport.toDouble()
            else -> return null
        }
        if (interval <= 0.0) return null
        return ScrollMath.snapTarget(current.toDouble(), interval, viewport.toDouble(), merged.str("snap_to_alignment") ?: "start", contentSize.toDouble()).roundToInt()
    }

    // ------------------------------------------------------------------
    // Commands
    // ------------------------------------------------------------------

    override fun command(view: View, name: String, args: JSONObject): Any? {
        val sv = inner(view)
        val horizontal = isHorizontal(view)
        when (name) {
            "scroll_to_offset" -> {
                val x = px(JsonUtil.toDouble(args.opt("x")))
                val y = px(JsonUtil.toDouble(args.opt("y")))
                val animated = args.value("animated") != false
                when (sv) {
                    is NestedScrollView -> if (animated) sv.smoothScrollTo(x, y) else sv.scrollTo(x, y)
                    is HorizontalScrollView -> if (animated) sv.smoothScrollTo(x, y) else sv.scrollTo(x, y)
                }
            }
            "scroll_to_end" -> {
                val child = if (sv.childCount > 0) sv.getChildAt(0) else return null
                val animated = args.value("animated") != false
                if (horizontal) {
                    val target = max(0, child.width - sv.width)
                    if (animated) (sv as HorizontalScrollView).smoothScrollTo(target, 0) else sv.scrollTo(target, 0)
                } else {
                    val target = max(0, child.height - sv.height)
                    if (animated) (sv as NestedScrollView).smoothScrollTo(0, target) else sv.scrollTo(0, target)
                }
            }
            "get_scroll_offset" -> return mapOf("x" to dp(sv.scrollX), "y" to dp(sv.scrollY))
            "flash_scroll_indicators" -> sv.awakenScrollBarsCompat()
        }
        return null
    }

    private fun View.awakenScrollBarsCompat() {
        // awakenScrollBars is protected; toggling the fade re-shows the bars briefly.
        isScrollbarFadingEnabled = false
        MainThread.postDelayed({ isScrollbarFadingEnabled = true }, 600)
    }

    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {
        super.setFrame(view, x, y, width, height)
        // The inner scroll view fills its refresh wrapper.
        if (view is SwipeRefreshLayout) {
            val sv = view.getChildAt(0)
            val lp = sv.layoutParams
            lp.width = ViewGroup.LayoutParams.MATCH_PARENT
            lp.height = ViewGroup.LayoutParams.MATCH_PARENT
            sv.layoutParams = lp
        }
    }
}

/** Pure scroll arithmetic shared by `ScrollView` and its tests. */
object ScrollMath {
    /** React Native's `deceleration_rate` values. */
    const val NORMAL_RATE = 0.998
    const val FAST_RATE = 0.99

    /**
     * Velocity multiplier standing in for a scroller friction. React
     * Native's fling travels `v / (1 - rate)`, so the distance ratio
     * between `rate` and the normal `0.998` is `(1 - 0.998) / (1 - rate)`;
     * Android's `OverScroller` fling distance grows roughly with the
     * square of the velocity, hence the square root. `"normal"` (or an
     * unknown value) leaves the fling untouched, `"fast"` shortens it.
     */
    fun flingScale(rate: Any?): Float {
        val value = when (rate) {
            "fast" -> FAST_RATE
            is Number -> rate.toDouble()
            else -> NORMAL_RATE
        }
        if (!value.isFinite() || value >= 1.0 || value <= 0.0) return 1f
        return sqrt((1.0 - NORMAL_RATE) / (1.0 - value)).toFloat().coerceIn(0.05f, 1f)
    }

    /**
     * Snap `current` to the nearest multiple of `interval` (px), aligned
     * so a snapped item sits at the viewport's start, center, or end,
     * clamped to the scrollable range.
     */
    fun snapTarget(current: Double, interval: Double, viewport: Double, alignment: String, contentSize: Double): Double {
        val offset = when (alignment) {
            "center" -> (viewport - interval) / 2.0
            "end" -> viewport - interval
            else -> 0.0
        }
        val snapped = Math.round((current + offset) / interval) * interval - offset
        val maxOffset = max(0.0, contentSize - viewport)
        return snapped.coerceIn(0.0, maxOffset)
    }
}
