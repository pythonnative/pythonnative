package com.pythonnative.android_template

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class PageFragment : Fragment() {
    private val TAG = javaClass.simpleName
    private var page: PyObject? = null
    private val hotReloadHandler = Handler(Looper.getMainLooper())
    private val hotReloadRunnable = object : Runnable {
        override fun run() {
            try {
                page?.callAttr("hot_reload_tick")
            } catch (e: Exception) {
                Log.w(TAG, "hot_reload_tick failed", e)
            } finally {
                hotReloadHandler.postDelayed(this, 500)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) {
            context?.let { Python.start(AndroidPlatform(it)) }
        }
        try {
            val py = Python.getInstance()
            // Default to "app.main": PythonNative imports the module
            // and looks up its top-level `App` attribute. Override
            // via fragment arguments / nav graph to load a different
            // module or a specific dotted-attribute path (e.g.
            // "app.main.RootScreen").
            val pagePath = arguments?.getString("page_path") ?: "app.main"
            val argsJson = arguments?.getString("args_json")
            val filesRoot = requireContext().filesDir.absolutePath
            val devRoot = "$filesRoot/pythonnative_dev"
            val hotReload = py.getModule("pythonnative.hot_reload")
            hotReload.callAttr("configure_dev_environment", filesRoot)
            val pnPage = py.getModule("pythonnative.page")
            page = pnPage.callAttr("create_page", pagePath, requireActivity(), argsJson)
            page?.callAttr("enable_hot_reload", "$devRoot/reload.json", devRoot)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to instantiate page", e)
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        // Create a simple container which Python-native views can be attached to.
        val frame = FrameLayout(requireContext())
        frame.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        return frame
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        // Python side will call set_root_view to attach a native view to Activity.
        // In fragment-based architecture, the Activity will set contentView once,
        // so we ensure the fragment's container is available for Python to target.
        // Expose the fragment container to Python so Page.set_root_view can attach into it
        try {
            val py = Python.getInstance()
            val utils = py.getModule("pythonnative.utils")
            utils.callAttr("set_android_fragment_container", view)
            // Now that container exists, invoke on_create so Python can attach its root view
            page?.callAttr("on_create")
            hotReloadHandler.removeCallbacks(hotReloadRunnable)
            hotReloadHandler.postDelayed(hotReloadRunnable, 500)
        } catch (e: Exception) {
            Log.e(TAG, "on_create failed", e)
        }
    }

    override fun onStart() {
        super.onStart()
        try { page?.callAttr("on_start") } catch (e: Exception) { Log.w(TAG, "on_start failed", e) }
    }

    override fun onResume() {
        super.onResume()
        try { page?.callAttr("on_resume") } catch (e: Exception) { Log.w(TAG, "on_resume failed", e) }
    }

    override fun onPause() {
        super.onPause()
        try { page?.callAttr("on_pause") } catch (e: Exception) { Log.w(TAG, "on_pause failed", e) }
    }

    override fun onStop() {
        super.onStop()
        try { page?.callAttr("on_stop") } catch (e: Exception) { Log.w(TAG, "on_stop failed", e) }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        hotReloadHandler.removeCallbacks(hotReloadRunnable)
    }

    override fun onDestroy() {
        super.onDestroy()
        hotReloadHandler.removeCallbacks(hotReloadRunnable)
        try { page?.callAttr("on_destroy") } catch (e: Exception) { Log.w(TAG, "on_destroy failed", e) }
    }

    companion object {
        fun newInstance(pagePath: String, argsJson: String?): PageFragment {
            val f = PageFragment()
            f.arguments = bundleOf(
                "page_path" to pagePath,
                "args_json" to argsJson
            )
            return f
        }
    }
}
