package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import com.pythonnative.runtime.screens.ScreenRegistry
import org.json.JSONObject

/**
 * `Portal` element: floats its children over the screen in a full-size,
 * non-clickable overlay added directly to the screen's fragment
 * container (the same parent as the screen root, so portal coordinates
 * equal viewport coordinates). The overlay attaches lazily on the first
 * child insert and re-homes itself if the container changed.
 */
class PortalManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val overlay = FrameLayout(context)
        overlay.isClickable = false
        return overlay
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        ViewStyler.apply(view, props)
        if (!initial) ensureAttached(view)
    }

    private fun ensureAttached(overlay: View) {
        val container = ScreenRegistry.activeContainer() ?: return
        val parent = overlay.parent as? ViewGroup
        if (parent === container) {
            overlay.bringToFront()
            return
        }
        parent?.removeView(overlay)
        container.addView(
            overlay,
            ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT),
        )
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        ensureAttached(parent)
        ViewChildren.insert(parent as ViewGroup, child, index)
    }

    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {
        // The overlay fills its container; the engine frames only the portal's children.
    }

    override fun teardown(view: View) {
        (view.parent as? ViewGroup)?.removeView(view)
    }
}
