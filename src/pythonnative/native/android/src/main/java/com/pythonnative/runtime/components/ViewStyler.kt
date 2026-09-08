package com.pythonnative.runtime.components

import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.TouchDelegate
import android.view.View
import android.view.ViewGroup
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.bridge.num
import com.pythonnative.runtime.bridge.obj
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.views.PNAccessibilityDelegate
import com.pythonnative.runtime.views.PNBorderDrawable
import com.pythonnative.runtime.views.PNFrameLayout
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.roundToInt

/**
 * Applies the visual props every element supports: background and
 * borders, opacity, overflow, display, z-order, pointer events, hit
 * slop, shadows, transforms, and accessibility.
 *
 * Border-related props are baked into a single background drawable,
 * so the styler keeps the merged "visual" subset per view and re-bakes
 * it whenever one of those keys changes.
 */
object ViewStyler {
    private val sideWidthKeys = listOf("border_left_width", "border_top_width", "border_right_width", "border_bottom_width")
    private val sideColorKeys = listOf("border_left_color", "border_top_color", "border_right_color", "border_bottom_color")
    // Order matches GradientDrawable.setCornerRadii: TL, TR, BR, BL.
    private val cornerKeys = listOf(
        "border_top_left_radius", "border_top_right_radius", "border_bottom_right_radius", "border_bottom_left_radius",
    )
    private val drawableKeys: List<String> =
        listOf("background_color", "border_radius", "border_width", "border_color") + cornerKeys + sideWidthKeys + sideColorKeys

    private fun density(): Float = PNBridge.density()
    private fun px(dp: Double): Float = (dp * density()).toFloat()
    private fun pxI(dp: Double): Int = (dp * density()).roundToInt()

    private fun record(view: View): ViewRecord? = PNBridge.registry.recordFor(view)

    /** Apply the common visual props present in `props` to `view`. */
    fun apply(view: View, props: JSONObject) {
        val record = record(view)
        if (drawableKeys.any { props.has(it) }) {
            val visual = visualProps(record)
            for (key in drawableKeys) {
                if (props.has(key)) visual.put(key, props.opt(key) ?: JSONObject.NULL)
            }
            applyBorder(view, visual)
        }
        if (props.has("overflow")) {
            val clip = props.str("overflow") == "hidden"
            if (view is ViewGroup) {
                view.clipChildren = clip
                view.clipToPadding = clip
            }
        }
        if (props.has("display")) {
            view.visibility = if (props.str("display") == "none") View.GONE else View.VISIBLE
        }
        props.num("opacity")?.let { view.alpha = it.toFloat() }
        if (props.has("z_index")) {
            val z = props.num("z_index")
            view.z = if (z != null) px(z) else 0f
        }
        if (props.has("pointer_events")) applyPointerEvents(view, props.str("pointer_events"))
        if (props.has("hit_slop")) updateHitSlop(view)
        applyShadow(view, props)
        applyTransform(view, props)
        applyAccessibility(view, props)
    }

    private fun visualProps(record: ViewRecord?): JSONObject {
        val existing = record?.state?.get("visual") as? JSONObject
        if (existing != null) return existing
        val fresh = JSONObject()
        record?.state?.put("visual", fresh)
        return fresh
    }

    // ------------------------------------------------------------------
    // Background and borders
    // ------------------------------------------------------------------

    /** Re-bake the background drawable from the merged visual props. */
    fun applyBorder(view: View, visual: JSONObject) {
        if (applySideBorder(view, visual)) return
        val hasBorder = listOf("border_radius", "border_width", "border_color").any { visual.has(it) } ||
            cornerKeys.any { visual.has(it) }
        val hasBg = visual.value("background_color") != null
        if (!hasBorder && !hasBg) {
            if (view.background is GradientDrawable || view.background is PNBorderDrawable) view.background = null
            return
        }
        val drawable = GradientDrawable()
        PNColor.parse(visual.value("background_color"))?.let { drawable.setColor(it) }
        if (cornerKeys.any { visual.value(it) != null }) {
            val base = visual.num("border_radius") ?: 0.0
            val radii = FloatArray(8)
            for ((i, key) in cornerKeys.withIndex()) {
                val r = px(visual.num(key) ?: base)
                radii[i * 2] = r
                radii[i * 2 + 1] = r
            }
            drawable.cornerRadii = radii
        } else {
            visual.num("border_radius")?.let { drawable.cornerRadius = px(it) }
        }
        if (visual.value("border_width") != null || visual.value("border_color") != null) {
            val width = visual.num("border_width") ?: 1.0
            val color = PNColor.parseOr(visual.value("border_color"), 0xFF000000.toInt())
            drawable.setStroke(pxI(width), color)
        }
        view.background = drawable
        view.invalidate()
    }

    private fun applySideBorder(view: View, visual: JSONObject): Boolean {
        if (sideWidthKeys.none { visual.value(it) != null }) return false
        val baseWidth = visual.num("border_width") ?: 0.0
        val baseColor = visual.value("border_color") ?: "#000000"
        val widths = FloatArray(4) { i -> px(visual.num(sideWidthKeys[i]) ?: baseWidth) }
        val colors = IntArray(4) { i -> PNColor.parseOr(visual.value(sideColorKeys[i]) ?: baseColor, 0xFF000000.toInt()) }
        val bg = PNColor.parse(visual.value("background_color"))
        val radius = px(visual.num("border_radius") ?: 0.0)
        view.background = PNBorderDrawable(bg != null, bg ?: 0, radius, widths, colors)
        view.invalidate()
        return true
    }

    /**
     * Apply one animated `background_color` frame without losing borders:
     * mutate the existing drawable's fill in place when possible.
     */
    fun setAnimatedBackground(view: View, value: Any?) {
        val color = PNColor.parse(value) ?: return
        val record = record(view)
        val visual = record?.state?.get("visual") as? JSONObject
        val hasBorder = visual != null && drawableKeys.any { it != "background_color" && visual.value(it) != null }
        if (hasBorder && visual != null) {
            visual.put("background_color", String.format("#%08X", color))
            when (val bg = view.background) {
                is GradientDrawable -> bg.setColor(color)
                is PNBorderDrawable -> bg.setFillColor(color)
                else -> applyBorder(view, visual)
            }
            return
        }
        view.setBackgroundColor(color)
    }

    // ------------------------------------------------------------------
    // Shadow / elevation
    // ------------------------------------------------------------------

    private fun applyShadow(view: View, props: JSONObject) {
        var elevation = props.num("elevation")
        if (elevation == null && props.has("shadow_radius")) elevation = props.num("shadow_radius")
        if (elevation == null && (props.value("shadow_color") != null || props.value("shadow_opacity") != null)) {
            // Shadow requested without an explicit size: Material card-like default.
            elevation = 4.0
        }
        if (elevation == null) return
        view.elevation = px(elevation)
        val color = props.value("shadow_color") ?: return
        if (Build.VERSION.SDK_INT < 28) return
        var argb = PNColor.parse(color) ?: return
        props.num("shadow_opacity")?.let { argb = PNColor.withAlpha(argb, it) }
        view.outlineAmbientShadowColor = argb
        view.outlineSpotShadowColor = argb
    }

    // ------------------------------------------------------------------
    // Transform
    // ------------------------------------------------------------------

    private fun applyTransform(view: View, props: JSONObject) {
        if (!props.has("transform")) return
        val spec = props.value("transform")
        if (spec == null) {
            view.rotation = 0f
            view.rotationX = 0f
            view.rotationY = 0f
            view.scaleX = 1f
            view.scaleY = 1f
            view.translationX = 0f
            view.translationY = 0f
            return
        }
        val entries: List<Any?> = when (spec) {
            is JSONArray -> JsonUtil.toList(spec)
            else -> listOf(spec)
        }
        for (entry in entries) {
            val e = entry as? JSONObject ?: continue
            try {
                if (e.has("rotate")) view.rotation = angleDegrees(e.value("rotate"))
                if (e.has("rotate_x")) view.rotationX = angleDegrees(e.value("rotate_x"))
                if (e.has("rotate_y")) view.rotationY = angleDegrees(e.value("rotate_y"))
                if (e.has("rotate_z")) view.rotation = angleDegrees(e.value("rotate_z"))
                e.num("scale")?.let { view.scaleX = it.toFloat(); view.scaleY = it.toFloat() }
                e.num("scale_x")?.let { view.scaleX = it.toFloat() }
                e.num("scale_y")?.let { view.scaleY = it.toFloat() }
                e.num("translate_x")?.let { view.translationX = px(it) }
                e.num("translate_y")?.let { view.translationY = px(it) }
                if (e.has("skew_x") || e.has("skew_y")) {
                    // Android views have no skew transform; approximate with rotation around the axis.
                    PNLog.once("skew", "transform skew_x/skew_y is not supported on Android and is ignored")
                }
            } catch (ex: Exception) {
                PNLog.swallowed("ViewStyler.applyTransform", ex)
            }
        }
    }

    /** Parse `"45deg"`, `"0.5rad"`, or a bare number (degrees) into degrees. */
    fun angleDegrees(value: Any?): Float {
        return when (value) {
            is Number -> value.toFloat()
            is String -> {
                val s = value.trim()
                when {
                    s.endsWith("deg") -> s.dropLast(3).toFloatOrNull() ?: 0f
                    s.endsWith("rad") -> Math.toDegrees((s.dropLast(3).toDoubleOrNull() ?: 0.0)).toFloat()
                    else -> s.toFloatOrNull() ?: 0f
                }
            }
            else -> 0f
        }
    }

    // ------------------------------------------------------------------
    // Accessibility
    // ------------------------------------------------------------------

    /** Apply accessibility props (label / accessible / state / live region / role / test_id). */
    fun applyAccessibility(view: View, props: JSONObject) {
        if (props.has("accessible")) {
            view.importantForAccessibility = if (JsonUtil.truthy(props.value("accessible"))) {
                View.IMPORTANT_FOR_ACCESSIBILITY_YES
            } else {
                View.IMPORTANT_FOR_ACCESSIBILITY_NO
            }
        }
        if (props.has("accessibility_label")) {
            view.contentDescription = props.str("accessibility_label")
        }
        if (props.has("accessibility_hint") && Build.VERSION.SDK_INT >= 28) {
            view.tooltipText = props.str("accessibility_hint")
        }
        if (props.has("accessibility_live_region")) {
            view.accessibilityLiveRegion = when (props.str("accessibility_live_region")?.lowercase()) {
                "polite" -> View.ACCESSIBILITY_LIVE_REGION_POLITE
                "assertive" -> View.ACCESSIBILITY_LIVE_REGION_ASSERTIVE
                else -> View.ACCESSIBILITY_LIVE_REGION_NONE
            }
        }
        val state = props.obj("accessibility_state")
        if (state != null && state.has("selected")) {
            view.isSelected = JsonUtil.truthy(state.value("selected"))
        }
        val testId = props.str("test_id")
        val role = props.str("accessibility_role")
        if (testId == null && state == null && role == null) return
        val record = record(view)
        var delegate = record?.state?.get("a11y_delegate") as? PNAccessibilityDelegate
        if (delegate == null) {
            delegate = PNAccessibilityDelegate()
            view.accessibilityDelegate = delegate
            record?.state?.put("a11y_delegate", delegate)
        }
        if (testId != null) {
            delegate.testId = testId
            view.tag = testId
        }
        if (role != null) delegate.role = role
        if (state != null) {
            delegate.stateDisabled = optBool(state, "disabled")
            delegate.stateSelected = optBool(state, "selected")
            delegate.stateChecked = optBool(state, "checked")
            delegate.stateBusy = optBool(state, "busy")
            delegate.stateExpanded = optBool(state, "expanded")
        }
    }

    private fun optBool(obj: JSONObject, key: String): Boolean? {
        val v = obj.value(key) ?: return null
        return JsonUtil.truthy(v)
    }

    // ------------------------------------------------------------------
    // Pointer events and hit slop
    // ------------------------------------------------------------------

    /** Whether `pointer_events` disables the view's own touch handling. */
    fun pointerEventsBlocked(view: View): Boolean {
        val mode = record(view)?.props?.str("pointer_events") ?: return false
        return mode == "none" || mode == "box_none"
    }

    private fun applyPointerEvents(view: View, value: String?) {
        val mode = value ?: "auto"
        val state = record(view)?.state
        (view as? PNFrameLayout)?.setPointerEventsMode(mode)
        when (mode) {
            "none", "box_none" -> {
                state?.let { if (!it.containsKey("pe_was_clickable")) it["pe_was_clickable"] = view.isClickable }
                view.isClickable = false
            }
            "box_only" -> {
                state?.let { if (!it.containsKey("pe_was_clickable")) it["pe_was_clickable"] = view.isClickable }
                view.isClickable = true
            }
            else -> {
                val was = state?.remove("pe_was_clickable") as? Boolean
                if (was != null) view.isClickable = was
            }
        }
    }

    private fun hitSlopInsets(value: Any?): DoubleArray? {
        return when (value) {
            null, JSONObject.NULL -> null
            is JSONObject -> doubleArrayOf(
                value.num("top") ?: 0.0, value.num("left") ?: 0.0, value.num("bottom") ?: 0.0, value.num("right") ?: 0.0,
            )
            else -> JsonUtil.toDoubleOrNull(value)?.let { doubleArrayOf(it, it, it, it) }
        }
    }

    /** Extend the view's touch target via a `TouchDelegate` on its parent (needs a frame). */
    fun updateHitSlop(view: View) {
        val record = record(view) ?: return
        val frame = record.frame ?: return
        val insets = hitSlopInsets(record.props.value("hit_slop"))
        val parent = view.parent as? ViewGroup ?: return
        if (insets == null) {
            if (record.state.remove("hit_slop_active") != null) parent.touchDelegate = null
            return
        }
        val (top, left, bottom, right) = insets
        val (x, y, w, h) = frame
        val rect = Rect(pxI(x - left), pxI(y - top), pxI(x + w + right), pxI(y + h + bottom))
        parent.touchDelegate = TouchDelegate(rect, view)
        record.state["hit_slop_active"] = true
    }
}
