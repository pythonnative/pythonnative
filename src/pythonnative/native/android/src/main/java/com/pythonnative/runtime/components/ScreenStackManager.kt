package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Typeface
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.content.res.AppCompatResources
import androidx.appcompat.widget.Toolbar
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.fragment.app.FragmentContainerView
import androidx.fragment.app.FragmentManager
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.R
import com.pythonnative.runtime.layout.NativeLayout
import org.json.JSONObject

/**
 * `Screen`: one route of a native stack. Its view is the fragment
 * content; header slots (`_pn_header_slot` children) are lifted into
 * the parent stack's toolbar. Screens other than `transparent_modal`
 * presentations get the theme's window background when no
 * `background_color` is set, so slide transitions never reveal the
 * screen beneath. `guarded` (a `before_remove` listener exists) is
 * accepted and unused: Android pops only after Python confirms through
 * `on_native_back`, so there is no native gesture to veto.
 */
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
        val merged = propsOf(view)
        if (initial || props.has("background_color") || props.has("presentation")) applyBackground(view, merged)
        val tag = PNBridge.registry.tagOf(view)
        val parent = tag?.let { NativeLayout.parent(it) }?.let { PNBridge.registry.get(it) }
        (parent?.manager as? ScreenStackManager)?.let { stack ->
            stack.noteScreen(parent.view, tag, merged)
            stack.refresh(parent.view)
        }
    }
    private fun applyBackground(view: View, merged: JSONObject) {
        if (ScreenTransitions.isTransparent(merged)) return
        if (PNColor.parse(merged.opt("background_color")) != null) return
        view.setBackgroundColor(PNTheme.background(view.context))
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

/**
 * One fragment stack whose Python providers and state remain
 * application-owned.
 *
 * The stack owns a header (a `Toolbar` plus an optional large-title
 * row) and a `FragmentContainerView`. Each `Screen` child becomes a
 * [LogicalScreenFragment]; pushes and pops run the transitions chosen
 * by [ScreenTransitions] from the screen's `animation` and
 * `presentation` props. The header applies the status-bar inset itself
 * so it sits below the bar in edge-to-edge windows, renders
 * `header_large_title` as a 96dp expanded toolbar, and draws a vector
 * back chevron tinted by `header_tint_color`.
 *
 * On Activity recreation the fragment manager restores the
 * `pn-screen-<tag>` fragments; [Stack.schedule] adopts them by tag
 * instead of adding duplicates and removes any whose screen is gone.
 *
 * Predictive back: the app manifest enables
 * `enableOnBackInvokedCallback`, and `PNScreenFragment` registers a
 * callback whose progress hooks are no-ops. The system only plays its
 * back-to-home preview when no enabled callback exists; the callback
 * stays enabled by default (Python owns the back decision and does not
 * yet call `Host.set_back_enabled`), so today the gesture commits
 * without a preview and Python pops or finishes. Cross-screen predictive
 * previews (peeking at the previous screen while dragging) are not
 * implemented: the stack is Python-driven and pops only after the
 * gesture commits.
 */
class ScreenStackManager : ComponentManager() {
    /** Base toolbar height, in dp. */
    private val toolbarDp = 56
    /** Extra height of the large-title row, in dp (`56 + 40 = 96`). */
    private val largeTitleRowDp = 40

    private inner class Stack(context: Context) : LinearLayout(context), DefaultLifecycleObserver {
        val header = LinearLayout(context).apply { orientation = VERTICAL }
        val toolbar = Toolbar(context)
        val largeTitle = TextView(context).apply {
            visibility = View.GONE
            gravity = Gravity.START or Gravity.BOTTOM
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            setPadding((16 * PNBridge.density()).toInt(), 0, (16 * PNBridge.density()).toInt(), (8 * PNBridge.density()).toInt())
        }
        val container = FragmentContainerView(context).apply { id = View.generateViewId() }
        val screens = ArrayList<Long>()
        val fragments = HashMap<Long, LogicalScreenFragment>()
        /** Effective animation and transparency per screen tag, kept past the record's destruction for pops. */
        val animations = HashMap<Long, String>()
        val transparent = HashSet<Long>()
        var lastTop: Long? = null
        var scheduled = false
        var owner: FragmentManager? = null
        var statusInset = 0
        private val headerViews = ArrayList<View>()
        private val defaultTitleColor = PNTheme.textPrimary(context)
        init {
            orientation = VERTICAL
            header.addView(toolbar, LayoutParams(LayoutParams.MATCH_PARENT, (toolbarDp * PNBridge.density()).toInt()))
            header.addView(largeTitle, LayoutParams(LayoutParams.MATCH_PARENT, (largeTitleRowDp * PNBridge.density()).toInt()))
            addView(header, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            addView(container, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))
            toolbar.setNavigationOnClickListener { fire(this, "on_native_back", 1) }
            ViewCompat.setOnApplyWindowInsetsListener(this) { _, insets ->
                val top = insets.getInsets(WindowInsetsCompat.Type.statusBars() or WindowInsetsCompat.Type.displayCutout()).top
                if (top != statusInset) {
                    statusInset = top
                    header.setPadding(0, if (header.visibility == View.VISIBLE) top else 0, 0, 0)
                }
                insets
            }
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
                commit(manager)
                applyHeader()
                NativeLayout.containerDidLayout()
            }
        }

        private fun transition(): ScreenTransitions.Transition {
            val previous = lastTop
            val top = screens.lastOrNull()
            if (fragments.isEmpty() || previous == null || top == null || previous == top) return ScreenTransitions.NONE
            val topIsNew = fragments[top] == null
            // A pop reveals an existing screen; a replace (old top gone, new top added) animates as a push.
            val pop = !topIsNew && (previous !in screens || screens.indexOf(top) < screens.indexOf(previous))
            return if (pop) ScreenTransitions.pop(animations[previous] ?: "slide_from_right")
            else ScreenTransitions.push(animations[top] ?: "slide_from_right")
        }

        private fun commit(manager: FragmentManager) {
            val transaction = manager.beginTransaction().setReorderingAllowed(true)
            val transition = transition()
            if (!transition.isNone) transaction.setCustomAnimations(transition.enter, transition.exit)
            // Fragments for screens that left the stack, including ones a
            // recreated Activity restored for screens that no longer exist.
            for ((tag, fragment) in fragments.toMap()) if (tag !in screens) {
                transaction.remove(fragment)
                fragments.remove(tag)
                animations.remove(tag)
                transparent.remove(tag)
            }
            for (fragment in manager.fragments) {
                val tag = fragment.tag?.removePrefix(FRAGMENT_TAG_PREFIX)?.toLongOrNull() ?: continue
                if (fragment.tag?.startsWith(FRAGMENT_TAG_PREFIX) == true && tag !in screens && fragments[tag] !== fragment) transaction.remove(fragment)
            }
            val firstVisible = ScreenTransitions.firstVisibleIndex(screens.size) { screens[it] in transparent }
            for ((index, tag) in screens.withIndex()) {
                var fragment = fragments[tag]
                if (fragment == null) {
                    val restored = manager.findFragmentByTag(FRAGMENT_TAG_PREFIX + tag) as? LogicalScreenFragment
                    fragment = restored ?: LogicalScreenFragment().apply { arguments = Bundle().apply { putLong("tag", tag) } }
                    fragments[tag] = fragment
                    if (restored == null) transaction.add(container.id, fragment, FRAGMENT_TAG_PREFIX + tag)
                }
                when {
                    index == screens.size - 1 ->
                        transaction.show(fragment).setMaxLifecycle(fragment, Lifecycle.State.RESUMED).setPrimaryNavigationFragment(fragment)
                    index >= firstVisible -> transaction.show(fragment).setMaxLifecycle(fragment, Lifecycle.State.STARTED)
                    else -> transaction.hide(fragment).setMaxLifecycle(fragment, Lifecycle.State.STARTED)
                }
            }
            transaction.commitNow()
            lastTop = screens.lastOrNull()
        }

        private fun applyHeader() {
            val current = screens.lastOrNull()?.let { PNBridge.registry.get(it) }
            val props = current?.props ?: JSONObject()
            val shown = props.optBoolean("header_shown", true)
            header.visibility = if (shown) View.VISIBLE else View.GONE
            header.setPadding(0, if (shown) statusInset else 0, 0, 0)
            val large = props.optBoolean("header_large_title", false)
            val titleStyle = props.optJSONObject("header_title_style") ?: JSONObject()
            val titleColor = PNColor.parse(titleStyle.opt("color")) ?: defaultTitleColor
            val bold = titleStyle.optBoolean("bold", large)
            val title = props.optString("title", "")
            header.setBackgroundColor(PNColor.parse(props.optJSONObject("header_style")?.opt("background_color")) ?: android.graphics.Color.TRANSPARENT)
            if (large) {
                toolbar.title = ""
                largeTitle.visibility = View.VISIBLE
                largeTitle.text = title
                largeTitle.setTextColor(titleColor)
                largeTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, titleStyle.optDouble("font_size", LARGE_TITLE_SP).toFloat())
                largeTitle.setTypeface(Typeface.DEFAULT, if (bold) Typeface.BOLD else Typeface.NORMAL)
            } else {
                largeTitle.visibility = View.GONE
                toolbar.title = title
                toolbar.setTitleTextColor(titleColor)
                for (index in 0 until toolbar.childCount) {
                    (toolbar.getChildAt(index) as? TextView)?.let { label ->
                        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, titleStyle.optDouble("font_size", TITLE_SP).toFloat())
                        label.setTypeface(Typeface.DEFAULT, if (bold) Typeface.BOLD else Typeface.NORMAL)
                    }
                }
            }
            for (view in headerViews) toolbar.removeView(view)
            headerViews.clear()
            @Suppress("UNCHECKED_CAST")
            val slots = current?.state?.get("header_slots") as? Map<String, View> ?: emptyMap()
            for ((side, view) in slots) {
                (view.parent as? ViewGroup)?.removeView(view)
                val gravity = if (side == "left") Gravity.START else Gravity.END
                toolbar.addView(view, Toolbar.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, (44 * PNBridge.density()).toInt(), gravity or Gravity.CENTER_VERTICAL))
                headerViews.add(view)
            }
            val tint = PNColor.parse(props.opt("header_tint_color")) ?: if (titleStyle.has("color")) titleColor else PNTheme.controlNormal(context)
            toolbar.navigationIcon = if (screens.size > 1 && props.optBoolean("header_back_visible", true) && "left" !in slots) {
                AppCompatResources.getDrawable(context, R.drawable.pn_ic_arrow_back)?.mutate()?.apply { setTint(tint) }
            } else null
            toolbar.navigationContentDescription = "Back"
        }
    }

    fun refresh(view: View) { (view as Stack).schedule() }

    /** Remember a screen's transition choices so a pop can replay them after the screen's record is gone. */
    fun noteScreen(view: View, tag: Long, props: JSONObject) {
        val stack = view as Stack
        stack.animations[tag] = ScreenTransitions.effectiveAnimation(props)
        if (ScreenTransitions.isTransparent(props)) stack.transparent.add(tag) else stack.transparent.remove(tag)
    }

    override fun createView(context: Context, tag: Long, props: JSONObject): View = Stack(context)
    override fun insertChild(parent: View, child: View, index: Int) {
        val stack = parent as Stack
        val record = PNBridge.registry.recordFor(child) ?: return
        val tag = record.tag
        noteScreen(stack, tag, record.props)
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
        stack.animations.clear()
        stack.transparent.clear()
    }

    companion object {
        /** Fragment tag prefix; the suffix is the screen's reconciler tag. */
        const val FRAGMENT_TAG_PREFIX = "pn-screen-"
        /** Default toolbar title size (sp). */
        const val TITLE_SP = 20.0
        /** Default large title size (sp). */
        const val LARGE_TITLE_SP = 28.0
    }
}
