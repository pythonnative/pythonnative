package com.pythonnative.runtime.components

import android.app.Dialog
import android.content.Context
import android.graphics.drawable.ColorDrawable
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject

/**
 * `Modal` element: real modal presentation backed by a `Dialog`.
 *
 * The on-tree placeholder is a hidden `View`. When `visible` flips to
 * `true`, a `Dialog` hosting a `FrameLayout` is shown and the
 * reconciler's child inserts are forwarded into that content view.
 */
class ModalManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val placeholder = View(context)
        placeholder.visibility = View.GONE
        return placeholder
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val state = stateOf(view)
        // Only react when `visible` itself changed; a re-render while the
        // dialog is open must not tear it down.
        if (props.has("visible")) {
            val visible = JsonUtil.truthy(props.value("visible"))
            if (visible && state["dialog"] == null) present(view)
            else if (!visible && state["dialog"] != null) dismiss(view, fromUser = false)
        }
        val dialog = state["dialog"] as? Dialog
        if (dialog != null && props.has("dismiss_on_backdrop")) {
            dialog.setCanceledOnTouchOutside(props.value("dismiss_on_backdrop") != false)
        }
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        val state = stateOf(parent)
        val content = state["content_view"] as? FrameLayout
        if (content != null) {
            ViewChildren.insert(content, child, index)
        } else {
            @Suppress("UNCHECKED_CAST")
            val pending = state.getOrPut("pending") { ArrayList<View>() } as ArrayList<View>
            pending.remove(child)
            pending.add(index.coerceIn(0, pending.size), child)
        }
    }

    override fun removeChild(parent: View, child: View) {
        val state = stateOf(parent)
        val content = state["content_view"] as? FrameLayout
        if (content != null) {
            content.removeView(child)
        } else {
            @Suppress("UNCHECKED_CAST")
            (state["pending"] as? ArrayList<View>)?.remove(child)
        }
    }

    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {
        // The dialog owns its own window; the layout engine frames only the children.
    }

    override fun teardown(view: View) {
        if (stateOf(view)["dialog"] != null) dismiss(view, fromUser = false)
    }

    private fun present(placeholder: View) {
        val state = stateOf(placeholder)
        val props = propsOf(placeholder)
        val ctx = placeholder.context
        val dialog = Dialog(ctx)
        val content = FrameLayout(ctx)
        val presentation = props.str("presentation_style") ?: "page_sheet"
        val isOverlay = presentation == "overlay" || JsonUtil.truthy(props.value("transparent"))
        content.setBackgroundColor(if (isOverlay) 0x00FFFFFF else 0xFFFFFFFF.toInt())
        dialog.setContentView(content, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        dialog.window?.let { window ->
            if (isOverlay) {
                window.setBackgroundDrawable(ColorDrawable(0x00000000))
                window.setDimAmount(0.5f)
                window.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT)
            } else {
                window.setLayout(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT)
            }
            val animation = props.str("animation_type") ?: props.str("animation")
            when (animation) {
                "none" -> window.setWindowAnimations(0)
                "fade" -> window.setWindowAnimations(android.R.style.Animation_Toast)
                "slide" -> window.setWindowAnimations(android.R.style.Animation_InputMethod)
            }
            PNColor.parse(props.value("status_bar_color"))?.let { window.statusBarColor = it }
        }
        dialog.setCanceledOnTouchOutside(props.value("dismiss_on_backdrop") != false)
        dialog.setCancelable(props.value("dismissable") != false)
        state["dialog"] = dialog
        state["content_view"] = content
        @Suppress("UNCHECKED_CAST")
        val pending = state.remove("pending") as? ArrayList<View>
        pending?.forEach { child ->
            (child.parent as? ViewGroup)?.removeView(child)
            content.addView(child)
        }
        dialog.setOnShowListener { fire(placeholder, "on_show") }
        dialog.setOnDismissListener {
            // Programmatic dismiss (visible=false) also lands here; the
            // Python side expects on_dismiss only for user-driven closes,
            // but android.py fired it unconditionally, so keep that.
            if (stateOf(placeholder)["dialog"] === dialog) {
                stateOf(placeholder).remove("dialog")
                stateOf(placeholder).remove("content_view")
            }
            fire(placeholder, "on_dismiss")
            if (hasEvent(placeholder, "on_request_close")) fire(placeholder, "on_request_close")
        }
        dialog.show()
    }

    private fun dismiss(placeholder: View, fromUser: Boolean) {
        val state = stateOf(placeholder)
        val dialog = state.remove("dialog") as? Dialog
        state.remove("content_view")
        if (!fromUser) dialog?.setOnDismissListener(null)
        dialog?.dismiss()
    }
}
