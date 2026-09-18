package com.pythonnative.runtime.components

import com.pythonnative.generated.*

import android.app.Dialog
import android.content.Context
import android.graphics.drawable.ColorDrawable
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import androidx.core.view.WindowCompat
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject

/**
 * `Modal` element: real modal presentation backed by a `Dialog`.
 *
 * The on-tree placeholder is a hidden `View`. When `visible` flips to
 * `true`, a `Dialog` hosting a `FrameLayout` is shown and the modal's
 * children move into that content view. The children stay mounted while
 * the modal is hidden (Python keeps them in the tree), so the manager
 * keeps their order and every presentation gets all of them. The
 * content background is the theme's `android:colorBackground` (light or
 * dark) unless `background_color` is set; overlays are transparent.
 *
 * Closing follows React Native: the system back button (and a backdrop
 * tap on an overlay with `dismiss_on_backdrop`) fires `on_request_close`
 * when it is wired and Python decides by flipping `visible`; the modal
 * never closes itself. `on_dismiss` fires once the dialog is gone.
 * `status_bar_translucent` lets the dialog window draw under the status
 * bar.
 */
class ModalManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val placeholder = View(context)
        placeholder.visibility = View.GONE
        return placeholder
    }

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val typed = ModalProps(props)

        val state = stateOf(view)
        // Only react when `visible` itself changed; a re-render while the
        // dialog is open must not tear it down.
        if (typed.has_visible) {
            val visible = (typed.visible ?: false)
            if (visible && state["dialog"] == null) present(view)
            else if (!visible && state["dialog"] != null) dismiss(view, emit = true)
        }
        val dialog = state["dialog"] as? Dialog
        if (dialog != null && typed.has_status_bar_translucent) applyStatusBar(dialog, typed.status_bar_translucent == true)
    }

    private fun applyStatusBar(dialog: Dialog, translucent: Boolean) {
        val window = dialog.window ?: return
        WindowCompat.setDecorFitsSystemWindows(window, !translucent)
        if (translucent) {
            window.addFlags(WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_INSET_DECOR)
            window.statusBarColor = 0x00000000
        }
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        val state = stateOf(parent)
        val children = childrenOf(state)
        children.remove(child)
        children.add(index.coerceIn(0, children.size), child)
        (state["content_view"] as? FrameLayout)?.let { ViewChildren.insert(it, child, index) }
    }

    override fun removeChild(parent: View, child: View) {
        childrenOf(stateOf(parent)).remove(child)
        // A hidden modal's children still sit in the last dialog's content view.
        (child.parent as? ViewGroup)?.removeView(child)
    }

    /** The modal's children in order, kept across presentations. */
    @Suppress("UNCHECKED_CAST")
    private fun childrenOf(state: MutableMap<String, Any?>): ArrayList<View> =
        state.getOrPut("children") { ArrayList<View>() } as ArrayList<View>

    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {
        // The dialog owns its own window; the layout engine frames only the children.
    }

    override fun teardown(view: View) {
        if (stateOf(view)["dialog"] != null) dismiss(view, emit = false)
    }

    private fun present(placeholder: View) {
        val state = stateOf(placeholder)
        val props = propsOf(placeholder)
        val ctx = placeholder.context
        val dialog = Dialog(ctx)
        val content = FrameLayout(ctx)
        val presentation = props.str("presentation_style") ?: "page_sheet"
        val isOverlay = presentation == "overlay" || JsonUtil.truthy(props.value("transparent"))
        // Opaque presentations take the theme's window background (dark
        // mode aware) unless `background_color` is set; overlays stay clear.
        content.setBackgroundColor(
            if (isOverlay) 0x00000000 else PNColor.parse(props.value("background_color")) ?: PNTheme.background(ctx),
        )
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
        applyStatusBar(dialog, ModalProps(props).status_bar_translucent == true)
        // Back and backdrop taps ask Python (`on_request_close`) instead of dismissing.
        dialog.setCanceledOnTouchOutside(false)
        dialog.setCancelable(false)
        dialog.setOnKeyListener { _, keyCode, event ->
            if (keyCode != KeyEvent.KEYCODE_BACK) return@setOnKeyListener false
            if (event.action == KeyEvent.ACTION_UP && hasEvent(placeholder, "on_request_close")) PNComponentEvents.Modal.on_request_close(placeholder)
            true
        }
        if (isOverlay && props.value("dismiss_on_backdrop") != false) {
            // A tap on the dimmed backdrop, outside every child, asks to close.
            var downX = 0f
            var downY = 0f
            content.setOnTouchListener { _, event ->
                if (event.actionMasked == MotionEvent.ACTION_DOWN) {
                    downX = event.x
                    downY = event.y
                }
                false
            }
            content.setOnClickListener {
                if (!isOnChild(content, downX, downY) && hasEvent(placeholder, "on_request_close")) {
                    PNComponentEvents.Modal.on_request_close(placeholder)
                }
            }
        }
        state["dialog"] = dialog
        state["content_view"] = content
        // Each presentation builds a new dialog; move every child into it,
        // including children the previous dialog showed.
        for (child in childrenOf(state)) ViewChildren.insert(content, child, content.childCount)
        dialog.setOnShowListener { fire(placeholder, "on_show") }
        dialog.setOnDismissListener {
            // Only a close the runtime didn't ask for (the activity going
            // away) lands here: `dismiss` detaches this listener first.
            if (stateOf(placeholder)["dialog"] === dialog) {
                stateOf(placeholder).remove("dialog")
                stateOf(placeholder).remove("content_view")
            }
            if (hasEvent(placeholder, "on_dismiss")) fire(placeholder, "on_dismiss")
        }
        dialog.show()
    }

    /** Whether content-local point (`x`, `y`) lands on one of the modal's visible children. */
    internal fun isOnChild(content: ViewGroup, x: Float, y: Float): Boolean =
        (0 until content.childCount).any { index ->
            val child = content.getChildAt(index)
            child.visibility == View.VISIBLE && x >= child.left && x < child.right && y >= child.top && y < child.bottom
        }

    /** Close the dialog because `visible` went false (`emit`) or the modal unmounted. */
    private fun dismiss(placeholder: View, emit: Boolean) {
        val state = stateOf(placeholder)
        val dialog = state.remove("dialog") as? Dialog
        state.remove("content_view")
        dialog?.setOnDismissListener(null)
        dialog?.dismiss()
        if (emit && dialog != null && hasEvent(placeholder, "on_dismiss")) fire(placeholder, "on_dismiss")
    }
}
