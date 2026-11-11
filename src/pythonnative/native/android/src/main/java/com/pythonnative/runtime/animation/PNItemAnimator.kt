package com.pythonnative.runtime.animation

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.view.View
import androidx.recyclerview.widget.RecyclerView
import androidx.recyclerview.widget.SimpleItemAnimator
import org.json.JSONObject

/**
 * A `VirtualList`'s row animations (RFC 0009): `item_entering`,
 * `item_exiting`, and `item_layout` presets, each
 * `{"type", "duration", "delay", "easing", "spring", "edge"}`.
 *
 * RecyclerView asks an item animator only about dataset changes
 * (`notifyItemInserted`, `notifyItemRemoved`, `notifyItemMoved`), never
 * about recycling or scrolling, so only those animate. Entering types are
 * `fade_in`, `slide_in` (from beyond the list's `edge`), and `zoom_in`;
 * exiting types are `fade_out`, `slide_out`, and `zoom_out`; layout types
 * are `linear` (move from the old position) and `fading` (fade out at the
 * old position, then in at the new one). A change without a preset for it
 * happens at once. The animator only touches the row containers' alpha,
 * scale, and translation, which the list owns, and resets them when a row
 * settles.
 */
class PNItemAnimator : SimpleItemAnimator() {
    var entering: JSONObject? = null
    var exiting: JSONObject? = null
    var layout: JSONObject? = null

    /** Whether any preset is set (the list installs the animator only then). */
    val active: Boolean get() = entering != null || exiting != null || layout != null

    private enum class Kind { ADD, REMOVE, MOVE }

    private inner class Entry(val holder: RecyclerView.ViewHolder, val kind: Kind, val spec: JSONObject, val dx: Float = 0f, val dy: Float = 0f) {
        var animator: ValueAnimator? = null
        var done = false

        fun start() {
            val timing = MotionTiming.of(spec)
            val animation = ValueAnimator.ofFloat(0f, 1f)
            animation.duration = timing.durationMs
            animation.startDelay = timing.delayMs
            animation.interpolator = timing.interpolator
            animation.addUpdateListener { apply(it.animatedValue as Float) }
            animation.addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationStart(animator: Animator) {
                    when (kind) {
                        Kind.ADD -> dispatchAddStarting(holder)
                        Kind.REMOVE -> dispatchRemoveStarting(holder)
                        Kind.MOVE -> dispatchMoveStarting(holder)
                    }
                }
                override fun onAnimationEnd(animator: Animator) = finish()
            })
            animator = animation
            apply(0f)
            animation.start()
        }

        /** Set the row container's state at progress `fraction` (a spring may overshoot 1). */
        fun apply(fraction: Float) {
            val view = holder.itemView
            when (kind) {
                Kind.ADD -> when (spec.optString("type")) {
                    "zoom_in" -> { view.scaleX = fraction; view.scaleY = fraction }
                    "slide_in" -> slide(view, 1 - fraction)
                    else -> view.alpha = fraction.coerceIn(0f, 1f)
                }
                Kind.REMOVE -> when (spec.optString("type")) {
                    "zoom_out" -> { view.scaleX = 1 - fraction; view.scaleY = 1 - fraction }
                    "slide_out" -> slide(view, fraction)
                    else -> view.alpha = (1 - fraction).coerceIn(0f, 1f)
                }
                Kind.MOVE -> if (spec.optString("type") == "fading") {
                    if (fraction < 0.5f) {
                        view.translationX = -dx
                        view.translationY = -dy
                        view.alpha = (1 - fraction * 2).coerceIn(0f, 1f)
                    } else {
                        view.translationX = 0f
                        view.translationY = 0f
                        view.alpha = (fraction * 2 - 1).coerceIn(0f, 1f)
                    }
                } else {
                    view.translationX = -dx * (1 - fraction)
                    view.translationY = -dy * (1 - fraction)
                }
            }
        }

        /** Offset the row toward its edge: 0 is in place, 1 just past the list's edge. */
        private fun slide(view: View, amount: Float) {
            val list = view.parent as? View
            val width = (list?.width ?: view.width).toFloat()
            val height = (list?.height ?: view.height).toFloat()
            when (spec.optString("edge", "right")) {
                "left" -> view.translationX = -(view.right.toFloat()) * amount
                "top" -> view.translationY = -(view.bottom.toFloat()) * amount
                "bottom" -> view.translationY = (height - view.top) * amount
                else -> view.translationX = (width - view.left) * amount
            }
        }

        fun finish() {
            if (done) return
            done = true
            reset(holder.itemView)
            pending.remove(this)
            running.remove(holder)
            when (kind) {
                Kind.ADD -> dispatchAddFinished(holder)
                Kind.REMOVE -> dispatchRemoveFinished(holder)
                Kind.MOVE -> dispatchMoveFinished(holder)
            }
            if (!isRunning) dispatchAnimationsFinished()
        }
    }

    private val pending = ArrayList<Entry>()
    private val running = HashMap<RecyclerView.ViewHolder, Entry>()

    init {
        supportsChangeAnimations = false
    }

    private fun reset(view: View) {
        view.alpha = 1f
        view.scaleX = 1f
        view.scaleY = 1f
        view.translationX = 0f
        view.translationY = 0f
    }

    override fun animateAdd(holder: RecyclerView.ViewHolder): Boolean {
        endAnimation(holder)
        val spec = entering ?: run { dispatchAddFinished(holder); return false }
        val entry = Entry(holder, Kind.ADD, spec)
        entry.apply(0f)
        pending.add(entry)
        return true
    }

    override fun animateRemove(holder: RecyclerView.ViewHolder): Boolean {
        endAnimation(holder)
        val spec = exiting ?: run { dispatchRemoveFinished(holder); return false }
        pending.add(Entry(holder, Kind.REMOVE, spec))
        return true
    }

    override fun animateMove(holder: RecyclerView.ViewHolder, fromX: Int, fromY: Int, toX: Int, toY: Int): Boolean {
        val view = holder.itemView
        val startX = fromX + view.translationX
        val startY = fromY + view.translationY
        endAnimation(holder)
        val dx = toX - startX
        val dy = toY - startY
        val spec = layout
        if (spec == null || (dx == 0f && dy == 0f)) {
            dispatchMoveFinished(holder)
            return false
        }
        val entry = Entry(holder, Kind.MOVE, spec, dx, dy)
        entry.apply(0f)
        pending.add(entry)
        return true
    }

    override fun animateChange(
        oldHolder: RecyclerView.ViewHolder, newHolder: RecyclerView.ViewHolder,
        fromLeft: Int, fromTop: Int, toLeft: Int, toTop: Int,
    ): Boolean {
        if (oldHolder === newHolder) return animateMove(oldHolder, fromLeft, fromTop, toLeft, toTop)
        dispatchChangeFinished(oldHolder, true)
        dispatchChangeFinished(newHolder, false)
        return false
    }

    override fun runPendingAnimations() {
        val starting = ArrayList(pending)
        pending.clear()
        for (entry in starting) {
            running[entry.holder] = entry
            entry.start()
        }
    }

    override fun endAnimation(item: RecyclerView.ViewHolder) {
        pending.firstOrNull { it.holder === item }?.let { entry ->
            pending.remove(entry)
            entry.finish()
        }
        running[item]?.let { entry ->
            entry.animator?.cancel()
            entry.finish()
        }
    }

    override fun isRunning(): Boolean = pending.isNotEmpty() || running.isNotEmpty()

    override fun endAnimations() {
        for (entry in ArrayList(pending)) entry.finish()
        pending.clear()
        for (entry in ArrayList(running.values)) {
            entry.animator?.cancel()
            entry.finish()
        }
        running.clear()
    }
}
