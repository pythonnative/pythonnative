package com.pythonnative.runtime.components

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.appcompat.widget.Toolbar
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.fragment.app.FragmentContainerView
import androidx.fragment.app.FragmentManager
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.pythonnative.runtime.PNBridge
import org.json.JSONObject
import android.widget.FrameLayout
import com.pythonnative.runtime.layout.NativeLayout

class ScreenManager : ViewManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View =
        super.createView(context, tag, props).apply {
            layoutParams = FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            addOnLayoutChangeListener { _, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom ->
                if (right - left != oldRight - oldLeft || bottom - top != oldBottom - oldTop) NativeLayout.containerDidLayout()
            }
        }
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        super.applyProps(view, props, initial)
        PNBridge.registry.tagOf(view)?.let { tag -> NativeLayout.parent(tag)?.let { PNBridge.registry.get(it) } }?.let { parent ->
            (parent.manager as? ScreenStackManager)?.refresh(parent.view)
        }
    }
    @Suppress("UNCHECKED_CAST")
    private fun headers(view: View): MutableMap<String, View> =
        stateOf(view).getOrPut("header_slots") { mutableMapOf<String, View>() } as MutableMap<String, View>
    override fun insertChild(parent: View, child: View, index: Int) {
        val side = propsOf(child).optString("_pn_header_slot", "")
        if (side.isNotEmpty()) headers(parent)[side] = child else super.insertChild(parent, child, index)
        refreshParent(parent)
    }
    override fun removeChild(parent: View, child: View) {
        headers(parent).entries.removeAll { it.value === child }
        super.removeChild(parent, child)
        refreshParent(parent)
    }
    private fun refreshParent(view: View) {
        PNBridge.registry.tagOf(view)?.let { NativeLayout.parent(it) }?.let { PNBridge.registry.get(it) }?.let {
            (it.manager as? ScreenStackManager)?.refresh(it.view)
        }
    }
    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {}
}

/** A native fragment displays an existing logical screen's view. */
class LogicalScreenFragment : Fragment() {
    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        val view = PNBridge.registry.get(requireArguments().getLong("tag"))?.view ?: View(requireContext())
        (view.parent as? ViewGroup)?.removeView(view)
        return view
    }
}

/** One fragment stack whose Python providers and state remain application-owned. */
class ScreenStackManager : ComponentManager() {
    private inner class Stack(context: Context) : LinearLayout(context), DefaultLifecycleObserver {
        val toolbar = Toolbar(context)
        val container = FragmentContainerView(context).apply { id = View.generateViewId() }
        val screens = ArrayList<Long>()
        val fragments = HashMap<Long, LogicalScreenFragment>()
        var scheduled = false
        var owner: FragmentManager? = null
        private val headerViews = ArrayList<View>()
        private val defaultTitleColor = android.widget.TextView(context).currentTextColor
        init {
            orientation = VERTICAL
            addView(toolbar, LayoutParams(LayoutParams.MATCH_PARENT, (56 * PNBridge.density()).toInt()))
            addView(container, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))
            toolbar.setNavigationOnClickListener { fire(this, "on_native_back", 1) }
        }
        override fun onAttachedToWindow() { super.onAttachedToWindow(); (context as? LifecycleOwner)?.lifecycle?.addObserver(this); schedule() }
        override fun onDetachedFromWindow() { (context as? LifecycleOwner)?.lifecycle?.removeObserver(this); super.onDetachedFromWindow() }
        override fun onResume(owner: LifecycleOwner) { schedule() }
        fun schedule() {
            if (scheduled) return
            scheduled = true
            post {
                scheduled = false
                if (!isAttachedToWindow) return@post
                val manager = owner ?: runCatching { FragmentManager.findFragment<Fragment>(this).childFragmentManager }.getOrNull()
                    ?: (context as? FragmentActivity)?.supportFragmentManager ?: return@post
                owner = manager
                if (manager.isStateSaved) return@post
                val transaction = manager.beginTransaction().setReorderingAllowed(true)
                if (fragments.isNotEmpty() && screens.lastOrNull()?.let { PNBridge.registry.get(it)?.props?.optString("animation") } != "none") transaction.setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
                for ((tag, fragment) in fragments.toMap()) if (tag !in screens) {
                    transaction.remove(fragment)
                    fragments.remove(tag)
                }
                for (tag in screens) {
                    var fragment = fragments[tag]
                    if (fragment == null) {
                        fragment = LogicalScreenFragment().apply { arguments = Bundle().apply { putLong("tag", tag) } }
                        fragments[tag] = fragment
                        transaction.add(container.id, fragment, "pn-screen-$tag")
                    }
                    if (tag == screens.lastOrNull()) {
                        transaction.show(fragment).setMaxLifecycle(fragment, Lifecycle.State.RESUMED).setPrimaryNavigationFragment(fragment)
                    } else transaction.hide(fragment).setMaxLifecycle(fragment, Lifecycle.State.STARTED)
                }
                transaction.commitNow()
                val current = screens.lastOrNull()?.let { PNBridge.registry.get(it) }
                val props = current?.props ?: JSONObject()
                toolbar.title = props.optString("title", "")
                toolbar.visibility = if (props.optBoolean("header_shown", true)) View.VISIBLE else View.GONE
                toolbar.setBackgroundColor(PNColor.parse(props.optJSONObject("header_style")?.opt("background_color")) ?: android.graphics.Color.TRANSPARENT)
                val titleStyle = props.optJSONObject("header_title_style") ?: JSONObject()
                toolbar.setTitleTextColor(PNColor.parse(titleStyle.opt("color")) ?: defaultTitleColor)
                for (index in 0 until toolbar.childCount) {
                    (toolbar.getChildAt(index) as? android.widget.TextView)?.let { title ->
                        title.textSize = titleStyle.optDouble("font_size", 20.0).toFloat()
                        title.setTypeface(android.graphics.Typeface.DEFAULT, if (titleStyle.optBoolean("bold", false)) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
                    }
                }
                for (view in headerViews) toolbar.removeView(view)
                headerViews.clear()
                @Suppress("UNCHECKED_CAST")
                val slots = current?.state?.get("header_slots") as? Map<String, View> ?: emptyMap()
                for ((side, view) in slots) {
                    (view.parent as? ViewGroup)?.removeView(view)
                    val gravity = if (side == "left") android.view.Gravity.START else android.view.Gravity.END
                    toolbar.addView(view, Toolbar.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, (44 * PNBridge.density()).toInt(), gravity or android.view.Gravity.CENTER_VERTICAL))
                    headerViews.add(view)
                }
                toolbar.navigationIcon = if (screens.size > 1 && props.optBoolean("header_back_visible", true) && "left" !in slots) context.getDrawable(android.R.drawable.ic_media_previous)?.mutate() else null
                PNColor.parse(props.opt("header_tint_color"))?.let { toolbar.navigationIcon?.setTint(it) }
                toolbar.navigationContentDescription = "Back"
                NativeLayout.containerDidLayout()
            }
        }
    }
    fun refresh(view: View) { (view as Stack).schedule() }
    override fun createView(context: Context, tag: Long, props: JSONObject): View = Stack(context)
    override fun insertChild(parent: View, child: View, index: Int) {
        val stack = parent as Stack
        val tag = PNBridge.registry.recordFor(child)?.tag ?: return
        stack.screens.remove(tag)
        stack.screens.add(index.coerceAtMost(stack.screens.size), tag)
        stack.schedule()
    }
    override fun removeChild(parent: View, child: View) {
        val stack = parent as Stack
        PNBridge.registry.recordFor(child)?.let { stack.screens.remove(it.tag) }
        stack.schedule()
    }
    override fun command(view: View, name: String, args: JSONObject): Any? {
        if (name == "restore_stack") (view as Stack).schedule()
        return null
    }
    override fun teardown(view: View) {
        val stack = view as Stack
        val manager = stack.owner
        if (manager != null && !manager.isDestroyed) {
            val transaction = manager.beginTransaction()
            for (fragment in stack.fragments.values) transaction.remove(fragment)
            transaction.commitAllowingStateLoss()
        }
        stack.screens.clear()
        stack.fragments.clear()
    }
}
