package com.pythonnative.runtime.screens

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
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

    /** Screen path when the arguments carry none (apps return the entry module). */
    protected open fun defaultPath(): String? = null

    /** The path this fragment shows. */
    fun screenPath(): String? = arguments?.getString(ARG_PATH) ?: defaultPath()

    private fun argsJson(): String? = arguments?.getString(ARG_ARGS)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        screenId = ScreenRegistry.register(this)
        pendingRestore = savedInstanceState?.getString(STATE_KEY)
        requireActivity().onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    val consumed = created && host("back_pressed", "{}") == "true"
                    if (!consumed) {
                        isEnabled = false
                        requireActivity().onBackPressedDispatcher.onBackPressed()
                        isEnabled = true
                    }
                }
            },
        )
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
        publishLayout(view, force = true)
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

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (!created) return
        host("save_state", "{}")?.let { outState.putString(STATE_KEY, it) }
    }

    override fun onDestroyView() {
        super.onDestroyView()
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
