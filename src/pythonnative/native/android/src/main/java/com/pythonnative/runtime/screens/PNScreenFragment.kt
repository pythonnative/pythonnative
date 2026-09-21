package com.pythonnative.runtime.screens

import android.content.res.Configuration
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.activity.BackEventCompat
import androidx.activity.OnBackPressedCallback
import androidx.core.os.bundleOf
import androidx.core.view.ViewCompat
import androidx.fragment.app.Fragment
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import org.json.JSONObject

/**
 * The Fragment hosting one PythonNative screen.
 *
 * On view creation it asks Python to create the screen
 * (`callback("host", screenId, "create", {...})`) and afterwards
 * forwards lifecycle and layout: `start`, `layout`, `resume`, `pause`,
 * `stop`, `destroy`, `back_pressed`, `save_state`, and
 * `restore_state`. Python attaches the screen's root view through the
 * `Host.attach_root` module call, which lands in [attachRoot].
 *
 * Apps subclass this (the nav graph names the subclass) and override
 * [defaultPath] to supply the entry module when the fragment arguments
 * don't carry one. Fast Refresh needs nothing from the fragment: the
 * Python dev client reloads modules and refreshes mounted screens.
 *
 * Back handling: an [OnBackPressedCallback] forwards `back_pressed` to
 * Python, which pops its own stack or calls `Host.finish`. Its
 * predictive-back hooks (`handleOnBackStarted` / `Progressed` /
 * `Cancelled`) are no-ops. With `enableOnBackInvokedCallback` on in the
 * manifest, Android 13+ plays the system back-to-home preview only while
 * no callback is enabled. The callback is enabled by default and stays
 * so until Python toggles [backEnabled] through `Host.set_back_enabled`
 * (not called yet), so the preview does not appear today. There is no
 * cross-screen predictive preview: the stack is Python-driven and pops
 * only after the gesture commits.
 *
 * Viewport: `layout` is re-published on view size changes, window inset
 * changes (which include the keyboard through [PNKeyboard]), and
 * configuration changes such as font scale or rotation.
 */
open class PNScreenFragment : Fragment() {
    /** The screen id assigned by [ScreenRegistry]. */
    var screenId: Int = 0
        private set

    /** The container the root view is attached into (valid between `onCreateView` and `onDestroyView`). */
    var container: FrameLayout? = null
        private set

    private var created = false
    private var pendingRestore: String? = null
    private var lastLayout: String? = null
    private var backCallback: OnBackPressedCallback? = null
    private var removeKeyboardListener: (() -> Unit)? = null

    /**
     * Whether the screen intercepts the system back gesture. `true` by
     * default so Python decides; set `false` (through `Host.set_back_enabled`)
     * when Python has nothing to pop, which lets the system's predictive
     * back-to-home animation play.
     */
    var backEnabled: Boolean
        get() = backCallback?.isEnabled ?: true
        set(value) { backCallback?.isEnabled = value }

    /** Screen path when the arguments carry none (apps return the entry module). */
    protected open fun defaultPath(): String? = null

    /** The path this fragment shows. */
    fun screenPath(): String? = arguments?.getString(ARG_PATH) ?: defaultPath()

    private fun argsJson(): String? = arguments?.getString(ARG_ARGS)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        screenId = ScreenRegistry.register(this)
        pendingRestore = savedInstanceState?.getString(STATE_KEY)
        val callback = object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (created) host("back_pressed", "{}")
                else requireActivity().finish()
            }
            // Predictive back: no in-app preview to drive, so progress is ignored.
            override fun handleOnBackStarted(backEvent: BackEventCompat) {}
            override fun handleOnBackProgressed(backEvent: BackEventCompat) {}
            override fun handleOnBackCancelled() {}
        }
        backCallback = callback
        requireActivity().onBackPressedDispatcher.addCallback(this, callback)
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        val frame = FrameLayout(requireContext())
        frame.layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        this.container = frame
        return frame
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        arguments?.getString(ARG_TITLE)?.let { activity?.title = it }
        val payload = JSONObject()
            .put("path", screenPath() ?: JSONObject.NULL)
            .put("args", argsJson() ?: JSONObject.NULL)
        host("create", payload.toString())
        created = true
        pendingRestore?.let {
            host("restore_state", JSONObject().put("state", it).toString())
            pendingRestore = null
        }
        view.addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ -> publishLayout(v) }
        ViewCompat.setOnApplyWindowInsetsListener(view) { v, insets ->
            publishLayout(v, force = true)
            insets
        }
        removeKeyboardListener?.invoke()
        removeKeyboardListener = PNKeyboard.addListener { _, _, _ -> container?.let { publishLayout(it, force = true) } }
        publishLayout(view, force = true)
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // Font scale, orientation, and UI mode changes handled in-place.
        container?.let { publishLayout(it, force = true) }
    }

    private fun publishLayout(view: View, force: Boolean = false) {
        if (!created) return
        val payload = Viewport.describe(view).toString()
        if (!force && payload == lastLayout) return
        lastLayout = payload
        host("layout", payload)
    }

    /** Current viewport payload for this screen. */
    fun viewport(): JSONObject {
        val v = container ?: view
        return if (v != null) Viewport.describe(v) else JSONObject()
    }

    /** Attach `root` (MATCH_PARENT) into the fragment container, replacing any previous root. */
    fun attachRoot(root: View) {
        val target = container ?: return
        target.removeAllViews()
        (root.parent as? ViewGroup)?.removeView(root)
        target.addView(root, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        publishLayout(target, force = true)
    }

    /** Detach `root` from wherever it is parented (never clears the shared container). */
    fun detachRoot(root: View) {
        (root.parent as? ViewGroup)?.removeView(root)
    }

    override fun onStart() {
        super.onStart()
        host("start", "{}")
    }

    override fun onResume() {
        super.onResume()
        ScreenRegistry.setActive(screenId)
        host("resume", viewport().toString())
    }

    override fun onPause() {
        super.onPause()
        host("pause", "{}")
    }

    override fun onStop() {
        super.onStop()
        host("stop", "{}")
    }

    var cachedStateJSON: String? = null

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (!created) return
        host("save_state", "{}")
        cachedStateJSON?.let { outState.putString(STATE_KEY, it) }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        removeKeyboardListener?.invoke()
        removeKeyboardListener = null
        container = null
    }

    override fun onDestroy() {
        super.onDestroy()
        if (created) host("destroy", "{}")
        created = false
        ScreenRegistry.unregister(screenId)
    }

    private fun host(name: String, payloadJson: String): String? {
        return try {
            PNBridge.callPython("host", screenId.toLong(), name, payloadJson)
        } catch (e: Exception) {
            PNLog.rateLimited("host:$name", "host callback '$name' failed", e)
            null
        }
    }

    companion object {
        const val ARG_PATH = "screen_path"
        const val ARG_ARGS = "args_json"
        const val ARG_TITLE = "title"
        private const val STATE_KEY = "pn_screen_state"

        /** Build a fragment for `path` with optional JSON `args`. */
        @JvmStatic
        fun newInstance(path: String, argsJson: String?): PNScreenFragment {
            val f = PNScreenFragment()
            f.arguments = bundleOf(ARG_PATH to path, ARG_ARGS to argsJson)
            return f
        }
    }
}
