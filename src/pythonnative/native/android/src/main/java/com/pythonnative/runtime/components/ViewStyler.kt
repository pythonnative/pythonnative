package com.pythonnative.runtime.components

import android.graphics.Matrix
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
import kotlin.math.sqrt
import kotlin.math.tan

/**
 * Applies the visual props every element supports: background and
 * borders, opacity, overflow, display, z-order, pointer events, hit
 * slop, shadows, transforms, and accessibility.
 *
 * Border-related props are baked into a single background drawable,
 * so the styler keeps the merged "visual" subset per view and re-bakes
 * it whenever one of those keys changes. `border_style` `dashed` and
 * `dotted` use a `DashPathEffect` (uniform borders through
 * `GradientDrawable`, per-side borders through `PNBorderDrawable`).
 *
 * Transforms map onto the view's transform properties (`rotate*`,
 * `scale*`, `translate*`, `perspective` as camera distance); `skew_x` /
 * `skew_y` are applied through `View.setAnimationMatrix` on API 29+ and
 * ignored below it, where the view pipeline cannot express a skew.
 *
 * Accessibility follows React Native's Android mapping:
 * `accessibility_hint` is appended to the content description,
 * `accessibility_value` becomes range info or a state description,
 * `accessibility_actions` become node actions that fire
 * `on_accessibility_action(name)`, and `important_for_accessibility`
 * maps onto `View.importantForAccessibility`.
 */
object ViewStyler {
    private val sideWidthKeys = listOf("border_left_width", "border_top_width", "border_right_width", "border_bottom_width")
    private val sideColorKeys = listOf("border_left_color", "border_top_color", "border_right_color", "border_bottom_color")
    // Order matches GradientDrawable.setCornerRadii: TL, TR, BR, BL.
    private val cornerKeys = listOf(
        "border_top_left_radius", "border_top_right_radius", "border_bottom_right_radius", "border_bottom_left_radius",
    )
    private val drawableKeys: List<String> =
        listOf("background_color", "border_radius", "border_width", "border_color", "border_style") + cornerKeys + sideWidthKeys + sideColorKeys

    /** React Native's camera-distance normalization for `perspective`. */
    private val CAMERA_DISTANCE_NORMALIZATION_MULTIPLIER = sqrt(5.0).toFloat()

    private fun density(): Float = PNBridge.density()
    private fun px(dp: Double): Float = (dp * density()).toFloat()
    private fun pxI(dp: Double): Int = (dp * density()).roundToInt()

    private fun record(view: View): ViewRecord? = PNBridge.registry.recordFor(view)

    /** Whether `props` changes any key baked into the background drawable. */
    fun touchesBackground(props: JSONObject): Boolean = drawableKeys.any { props.has(it) }

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
        if (props.has("opacity")) view.alpha = (props.num("opacity") ?: 1.0).toFloat()
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
            val style = borderStyle(visual)
            if (style == "solid") {
                drawable.setStroke(pxI(width), color)
            } else {
                val (dash, gap) = PNBorderDrawable.dashIntervals(style, px(width))
                drawable.setStroke(pxI(width), color, dash, gap)
            }
        }
        view.background = drawable
        view.invalidate()
    }

    /** `border_style` normalized to `solid`, `dashed`, or `dotted` (the typed enum, `solid` for anything else). */
    fun borderStyle(visual: JSONObject): String =
        runCatching { com.pythonnative.generated.PNViewProps(visual).border_style?.rawValue }.getOrNull() ?: "solid"

    private fun applySideBorder(view: View, visual: JSONObject): Boolean {
        if (sideWidthKeys.none { visual.value(it) != null }) return false
        val baseWidth = visual.num("border_width") ?: 0.0
        val baseColor = visual.value("border_color") ?: "#000000"
        val widths = FloatArray(4) { i -> px(visual.num(sideWidthKeys[i]) ?: baseWidth) }
        val colors = IntArray(4) { i -> PNColor.parseOr(visual.value(sideColorKeys[i]) ?: baseColor, 0xFF000000.toInt()) }
        val bg = PNColor.parse(visual.value("background_color"))
        val radius = px(visual.num("border_radius") ?: 0.0)
        view.background = PNBorderDrawable(bg != null, bg ?: 0, radius, widths, colors, borderStyle(visual))
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
        val keys = listOf("elevation", "shadow_radius", "shadow_color", "shadow_opacity", "shadow_offset")
        if (keys.none { props.has(it) }) return
        val merged = record(view)?.props ?: props
        val elevation = merged.num("elevation") ?: merged.num("shadow_radius")
            ?: if (keys.any { merged.value(it) != null }) 4.0 else 0.0
        view.elevation = px(elevation)
        if (Build.VERSION.SDK_INT < 28) return
        var argb = PNColor.parse(merged.value("shadow_color")) ?: android.graphics.Color.BLACK
        merged.num("shadow_opacity")?.let { argb = PNColor.withAlpha(argb, it) }
        view.outlineAmbientShadowColor = argb
        view.outlineSpotShadowColor = argb
    }

    // ------------------------------------------------------------------
    // Transform
    // ------------------------------------------------------------------

    private fun applyTransform(view: View, props: JSONObject) {
        if (!props.has("transform")) return
        val spec = props.value("transform")
        val state = record(view)?.state
        if (spec == null) {
            view.rotation = 0f
            view.rotationX = 0f
            view.rotationY = 0f
            view.scaleX = 1f
            view.scaleY = 1f
            view.translationX = 0f
            view.translationY = 0f
            if (state?.remove("perspective") != null) view.cameraDistance = 1280f * density()
            if (state?.remove("skew") != null) setSkew(view, null)
            return
        }
        val entries: List<Any?> = when (spec) {
            is JSONArray -> JsonUtil.toList(spec)
            else -> listOf(spec)
        }
        var skew: FloatArray? = null
        var perspective: Double? = null
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
                e.num("perspective")?.let { perspective = it }
                if (e.has("skew_x") || e.has("skew_y")) {
                    val current = skew ?: floatArrayOf(0f, 0f)
                    if (e.has("skew_x")) current[0] = angleDegrees(e.value("skew_x"))
                    if (e.has("skew_y")) current[1] = angleDegrees(e.value("skew_y"))
                    skew = current
                }
            } catch (ex: Exception) {
                PNLog.swallowed("ViewStyler.applyTransform", ex)
            }
        }
        val depth = perspective
        if (depth != null && depth > 0.0) {
            // React Native: camera distance = perspective * density * sqrt(5).
            view.cameraDistance = px(depth) * CAMERA_DISTANCE_NORMALIZATION_MULTIPLIER
            state?.put("perspective", depth)
        } else if (state?.remove("perspective") != null) {
            view.cameraDistance = 1280f * density()
        }
        if (skew != null) {
            state?.put("skew", skew)
            setSkew(view, skew)
        } else if (state?.remove("skew") != null) {
            setSkew(view, null)
        }
    }

    /**
     * Apply (or clear) a skew in degrees about the view's center. Uses
     * `View.setAnimationMatrix` (API 29+), which composes with the regular
     * transform properties; earlier releases log once and ignore it, as
     * React Native for Android also lacks skew. Re-run from `setFrame`
     * because the pivot follows the view's size.
     */
    fun setSkew(view: View, degrees: FloatArray?) {
        if (Build.VERSION.SDK_INT < 29) {
            if (degrees != null) PNLog.once("skew", "transform skew_x/skew_y needs Android 10+ (View.setAnimationMatrix); ignored")
            return
        }
        if (degrees == null || (degrees[0] == 0f && degrees[1] == 0f)) {
            view.animationMatrix = null
            return
        }
        val matrix = Matrix()
        val px = view.width / 2f
        val py = view.height / 2f
        matrix.setSkew(tan(Math.toRadians(degrees[0].toDouble())).toFloat(), tan(Math.toRadians(degrees[1].toDouble())).toFloat(), px, py)
        view.animationMatrix = matrix
    }

    /** Re-apply a stored skew after the view's frame changed (the pivot moved). */
    fun updateSkew(view: View) {
        val skew = record(view)?.state?.get("skew") as? FloatArray ?: return
        setSkew(view, skew)
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

    /**
     * Apply accessibility props: `accessible`, `important_for_accessibility`,
     * `accessibility_label` + `accessibility_hint` (composed into the content
     * description), `accessibility_live_region`, `accessibility_state`,
     * `accessibility_role`, `accessibility_value`, `accessibility_actions`,
     * and `test_id`.
     */
    fun applyAccessibility(view: View, props: JSONObject) {
        val record = record(view)
        val merged = record?.props ?: props
        val typed = com.pythonnative.generated.PNViewProps(props)
        if (typed.has_accessible) {
            view.importantForAccessibility = if (JsonUtil.truthy(props.value("accessible"))) {
                View.IMPORTANT_FOR_ACCESSIBILITY_YES
            } else {
                View.IMPORTANT_FOR_ACCESSIBILITY_NO
            }
        }
        if (typed.has_important_for_accessibility) {
            view.importantForAccessibility = importantForAccessibility(runCatching { typed.important_for_accessibility?.rawValue }.getOrNull())
        }
        if (typed.has_accessibility_label || typed.has_accessibility_hint) {
            view.contentDescription = contentDescription(merged.str("accessibility_label"), merged.str("accessibility_hint"))
        }
        if (typed.has_accessibility_live_region) {
            view.accessibilityLiveRegion = when (runCatching { typed.accessibility_live_region?.rawValue }.getOrNull()) {
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
        val hasValue = typed.has_accessibility_value
        val hasActions = typed.has_accessibility_actions
        if (testId == null && state == null && role == null && !hasValue && !hasActions) return
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
        if (hasValue) {
            val value = runCatching { typed.accessibility_value }.getOrNull()
            val recordValue = (value as? com.pythonnative.generated.PNViewAccessibilityValue.Option1)?.value
            delegate.valueMin = recordValue?.min
            delegate.valueMax = recordValue?.max
            delegate.valueNow = recordValue?.now
            delegate.valueText = when (value) {
                is com.pythonnative.generated.PNViewAccessibilityValue.Option0 -> value.value
                is com.pythonnative.generated.PNViewAccessibilityValue.Option1 -> recordValue?.text
                else -> JsonUtil.stringOrNull(props.value("accessibility_value"))
            }
        }
        if (hasActions) delegate.actions = accessibilityActions(props.value("accessibility_actions"))
    }

    /**
     * The content description for a label and hint: React Native for
     * Android appends the hint to the label (`"label, hint"`), or announces
     * the hint alone when there is no label.
     */
    fun contentDescription(label: String?, hint: String?): String? {
        val l = label?.takeIf { it.isNotEmpty() }
        val h = hint?.takeIf { it.isNotEmpty() }
        return when {
            l != null && h != null -> "$l, $h"
            l != null -> l
            else -> h
        }
    }

    /** `important_for_accessibility` value to the `View.IMPORTANT_FOR_ACCESSIBILITY_*` constant. */
    fun importantForAccessibility(value: String?): Int = when (value) {
        "yes" -> View.IMPORTANT_FOR_ACCESSIBILITY_YES
        "no" -> View.IMPORTANT_FOR_ACCESSIBILITY_NO
        "no_hide_descendants", "no-hide-descendants" -> View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        else -> View.IMPORTANT_FOR_ACCESSIBILITY_AUTO
    }

    /** Decode `accessibility_actions` (`[{name, label?}]` per the typed contract, or bare name strings) into actions. */
    fun accessibilityActions(value: Any?): List<PNAccessibilityDelegate.Action> {
        if (value is JSONArray) {
            runCatching { com.pythonnative.generated.PNValues.array(value).map { com.pythonnative.generated.PNAccessibilityAction.decode(it) } }
                .getOrNull()?.let { typed -> return typed.map { PNAccessibilityDelegate.Action(it.name, it.label) } }
        }
        val items = when (value) {
            is JSONArray -> JsonUtil.toList(value)
            is List<*> -> value
            else -> return emptyList()
        }
        return items.mapNotNull { item ->
            when (item) {
                is JSONObject -> item.str("name")?.takeIf { it.isNotEmpty() }?.let { PNAccessibilityDelegate.Action(it, item.str("label")) }
                is String -> item.takeIf { it.isNotEmpty() }?.let { PNAccessibilityDelegate.Action(it, null) }
                else -> null
            }
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
