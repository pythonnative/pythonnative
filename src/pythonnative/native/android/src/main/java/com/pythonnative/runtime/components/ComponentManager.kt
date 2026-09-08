package com.pythonnative.runtime.components

import android.content.Context
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.animation.PNAnimator
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.ViewRecord
import com.pythonnative.runtime.bridge.present
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Base class for one element type's native implementation.
 *
 * Subclasses implement [createView] (construct the widget) and
 * [applyProps] (apply visual props); the base class owns frame
 * application, intrinsic measurement, child management, and the
 * animation hooks. All geometry crossing this API is in dp.
 */
abstract class ComponentManager {
    /** Construct the widget for `tag`; `props` may be consulted for creation-time choices. */
    abstract fun createView(context: Context, tag: Long, props: JSONObject): View

    /**
     * Apply `props` to `view`. `initial` is `true` for the create op;
     * on updates `props` holds only the changed keys (JSON null means
     * removed). The merged props are always available via [propsOf].
     */
    open fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewStyler.apply(view, props)
    }

    /** Apply changed props (the `u` op). */
    fun update(view: View, changed: JSONObject) = applyProps(view, changed, false)

    /** Ensure `child` sits at `index` under `parent` (move-aware, clamped). */
    open fun insertChild(parent: View, child: View, index: Int) {
        val group = parent as? ViewGroup ?: return
        ViewChildren.insert(group, child, index)
    }

    /** Detach `child` from `parent` without destroying it. */
    open fun removeChild(parent: View, child: View) {
        (parent as? ViewGroup)?.removeView(child)
    }

    /** Release resources and detach from the parent. */
    open fun destroy(view: View) {
        try {
            teardown(view)
        } catch (e: Exception) {
            Log.d(PNBridge.TAG, "teardown failed for ${view.javaClass.simpleName}", e)
        }
        (view.parent as? ViewGroup)?.removeView(view)
    }

    /** Subclass hook for extra cleanup before the view is released. */
    protected open fun teardown(view: View) {}

    /**
     * Position `view` inside its parent's `FrameLayout` via margin layout
     * params. Non-finite values are clamped; sizes are never negative.
     */
    open fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {
        val pxX = px(finite(x))
        val pxY = px(finite(y))
        val pxW = max(0, px(finite(width)))
        val pxH = max(0, px(finite(height)))
        val lp = view.layoutParams
        val params: ViewGroup.LayoutParams = if (lp == null) {
            FrameLayout.LayoutParams(pxW, pxH)
        } else {
            lp.width = pxW
            lp.height = pxH
            lp
        }
        if (params is ViewGroup.MarginLayoutParams) {
            params.leftMargin = pxX
            params.topMargin = pxY
            params.rightMargin = 0
            params.bottomMargin = 0
        }
        view.layoutParams = params
        val record = recordOf(view)
        if (record != null) {
            record.frame = doubleArrayOf(x, y, width, height)
            if (record.props.present("hit_slop") || record.state["hit_slop_active"] == true) {
                ViewStyler.updateHitSlop(view)
            }
        }
    }

    /**
     * Natural size of `view` under the constraints, in dp. Either
     * constraint may be `1e6` or infinite meaning unconstrained.
     */
    open fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray {
        val density = PNBridge.density()
        val wSpec = measureSpec(maxWidth, density)
        val hSpec = measureSpec(maxHeight, density)
        view.measure(wSpec, hSpec)
        return floatArrayOf(view.measuredWidth / density, view.measuredHeight / density)
    }

    /** Run an imperative command; unknown names return `null`. */
    open fun command(view: View, name: String, args: JSONObject): Any? = null

    /** Apply one Python-driven animation frame immediately. */
    open fun setAnimatedProperty(view: View, prop: String, value: Any?) {
        PNAnimator.setProperty(view, prop, value)
    }

    /** Start a natively driven animation; `false` asks Python to tick it instead. */
    open fun startAnimation(view: View, id: Long, prop: String, spec: JSONObject): Boolean =
        PNAnimator.start(view, id, prop, spec)

    /** Cancel a native animation and return the presentation value, if readable. */
    open fun cancelAnimation(view: View, id: Long): Any? = PNAnimator.cancel(id)

    // ------------------------------------------------------------------
    // Helpers for subclasses
    // ------------------------------------------------------------------

    /** The registry record for `view`, or `null` for foreign views. */
    protected fun recordOf(view: View): ViewRecord? = PNBridge.registry.recordFor(view)

    /** Merged props for `view` (empty for foreign views). */
    protected fun propsOf(view: View): JSONObject = recordOf(view)?.props ?: JSONObject()

    /** Manager-private state map for `view`. */
    protected fun stateOf(view: View): MutableMap<String, Any?> = recordOf(view)?.state ?: HashMap()

    /** Dispatch event `name` with positional `args` for `view`'s tag. */
    protected fun fire(view: View, name: String, vararg args: Any?): Boolean = PNEvents.fire(view, name, *args)

    /** Dispatch event `name` and return Python's (JSON) reply. */
    protected fun fireForResult(view: View, name: String, vararg args: Any?): String? =
        PNEvents.fireForResult(view, name, *args)

    /** Whether the element wired a callback named `name`. */
    protected fun hasEvent(view: View, name: String): Boolean = recordOf(view)?.hasEvent(name) ?: false

    /** dp to whole pixels. */
    protected fun px(dp: Double): Int = (dp * PNBridge.density()).roundToInt()

    /** dp to pixels as a float. */
    protected fun pxF(dp: Double): Float = (dp * PNBridge.density()).toFloat()

    /** pixels to dp. */
    protected fun dp(px: Number): Double = px.toDouble() / PNBridge.density()

    private fun finite(v: Double): Double = if (v.isNaN() || v.isInfinite()) 0.0 else v

    private fun measureSpec(limit: Double, density: Float): Int {
        if (limit.isNaN() || limit.isInfinite() || limit >= 1e6) {
            return View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        }
        val px = min((max(0.0, limit) * density).toInt(), (1 shl 29))
        return View.MeasureSpec.makeMeasureSpec(px, View.MeasureSpec.AT_MOST)
    }
}

/** Move-aware indexed insertion into any `ViewGroup`. */
object ViewChildren {
    fun insert(parent: ViewGroup, child: View, index: Int) {
        val current = child.parent as? ViewGroup
        if (current === parent) {
            val currentIndex = parent.indexOfChild(child)
            val target = max(0, min(index, parent.childCount - 1))
            if (currentIndex == target) return
            parent.removeView(child)
            parent.addView(child, max(0, min(target, parent.childCount)))
            return
        }
        current?.removeView(child)
        if (child.layoutParams == null) {
            child.layoutParams = FrameLayout.LayoutParams(0, 0)
        }
        parent.addView(child, max(0, min(index, parent.childCount)))
    }
}

/** Event dispatch keyed by view identity. */
object PNEvents {
    /** Dispatch `name` for `view` with positional `args`; `false` when the view is unknown. */
    fun fire(view: View, name: String, vararg args: Any?): Boolean {
        val tag = PNBridge.registry.tagOf(view) ?: return false
        fireTag(tag, name, JsonUtil.args(*args))
        return true
    }

    /** Dispatch `name` for `view` and return Python's JSON reply. */
    fun fireForResult(view: View, name: String, vararg args: Any?): String? {
        val tag = PNBridge.registry.tagOf(view) ?: return null
        return fireTag(tag, name, JsonUtil.args(*args))
    }

    /** Dispatch `name` for `tag` with an already built argument array. */
    fun fireTag(tag: Long, name: String, args: JSONArray): String? =
        PNBridge.callPython("event", tag, name, args.toString())
}

/** Fallback for unknown element types: an empty container that hosts children. */
class PlaceholderManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = FrameLayout(context)
}
