package com.pythonnative.runtime.components

import android.annotation.SuppressLint
import android.content.Context
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.HorizontalScrollView
import androidx.core.widget.NestedScrollView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.obj
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * `ScrollView` element: a `NestedScrollView` (vertical, always wrapped in
 * a `SwipeRefreshLayout` that is enabled only while `refresh_control`
 * is set) or a `HorizontalScrollView`.
 *
 * `on_scroll` carries `{x, y, extent, range}` in dp. Commands:
 * `scroll_to_offset`, `scroll_to_end`, `get_scroll_offset`,
 * `flash_scroll_indicators`.
 */
class ScrollViewManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val horizontal = props.str("scroll_axis") == "horizontal" || JsonUtil.truthy(props.value("horizontal"))
        return if (horizontal) {
            val sv = HorizontalScrollView(context)
            bindScrollListener(sv, sv, true)
            bindTouch(sv, sv, true)
            sv
        } else {
            val sv = NestedScrollView(context)
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
        val sv = inner(view)
        ViewStyler.apply(sv, props)
        if (props.has("shows_scroll_indicator")) {
            val show = props.value("shows_scroll_indicator") != false
            sv.isVerticalScrollBarEnabled = show
            sv.isHorizontalScrollBarEnabled = show
        }
        if (props.has("bounces")) {
            sv.overScrollMode = if (props.value("bounces") == false) View.OVER_SCROLL_NEVER else View.OVER_SCROLL_IF_CONTENT_SCROLLS
        }
        if (props.has("scroll_enabled")) stateOf(view)["scroll_enabled"] = props.value("scroll_enabled") != false
        if (props.has("refresh_control") && view is SwipeRefreshLayout) applyRefresh(view, props.obj("refresh_control"))
        // paging_enabled and keyboard_dismiss_mode are read from merged props at touch time.
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

    private fun bindScrollListener(outer: View, sv: View, horizontal: Boolean) {
        sv.setOnScrollChangeListener { v, scrollX, scrollY, _, _ ->
            if (!hasEvent(outer, "on_scroll")) return@setOnScrollChangeListener
            fire(outer, "on_scroll", scrollPayload(v as ViewGroup, horizontal, scrollX, scrollY))
        }
    }

    private fun scrollPayload(sv: ViewGroup, horizontal: Boolean, scrollX: Int, scrollY: Int): Map<String, Any?> {
        val content = if (sv.childCount > 0) sv.getChildAt(0) else null
        val extent = if (horizontal) sv.width else sv.height
        val range = if (content == null) extent else if (horizontal) content.width else content.height
        return mapOf(
            "x" to dp(scrollX),
            "y" to dp(scrollY),
            "extent" to dp(extent),
            "range" to dp(max(range, extent)),
            "content_width" to dp(content?.width ?: sv.width),
            "content_height" to dp(content?.height ?: sv.height),
        )
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun bindTouch(outer: View, sv: ViewGroup, horizontal: Boolean) {
        sv.setOnTouchListener { v, event ->
            val merged = propsOf(outer)
            if (stateOf(outer)["scroll_enabled"] == false) return@setOnTouchListener true
            when (event.actionMasked) {
                MotionEvent.ACTION_MOVE -> {
                    val mode = merged.str("keyboard_dismiss_mode")
                    if (mode == "on_drag" || mode == "interactive") dismissKeyboard(v)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    if (JsonUtil.truthy(merged.value("paging_enabled"))) scheduleSnap(sv, horizontal)
                }
            }
            false
        }
    }

    private fun dismissKeyboard(view: View) {
        val focused = view.rootView.findFocus() ?: return
        focused.clearFocus()
        (view.context.getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager)
            ?.hideSoftInputFromWindow(view.windowToken, 0)
    }

    /** Wait for the fling to settle (two identical samples), then snap to the nearest page. */
    private fun scheduleSnap(sv: ViewGroup, horizontal: Boolean) {
        val state = stateOf(sv.parent as? View ?: sv)
        val token = ((state["snap_token"] as? Int) ?: 0) + 1
        state["snap_token"] = token
        var last = -1
        val poll = object : Runnable {
            override fun run() {
                if (state["snap_token"] != token) return
                val current = if (horizontal) sv.scrollX else sv.scrollY
                if (current == last) {
                    val page = if (horizontal) sv.width else sv.height
                    if (page > 0) {
                        val target = (current.toDouble() / page).roundToInt() * page
                        if (target != current) {
                            when (sv) {
                                is NestedScrollView -> sv.smoothScrollTo(0, target)
                                is HorizontalScrollView -> sv.smoothScrollTo(target, 0)
                            }
                        }
                    }
                    return
                }
                last = current
                MainThread.postDelayed(this, 50)
            }
        }
        MainThread.postDelayed(poll, 50)
    }

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
