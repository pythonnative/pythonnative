package com.pythonnative.runtime.components

import android.content.Context
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.views.PNFrameLayout
import org.json.JSONObject
import kotlin.math.max

/**
 * Flex container (shared by `View`, `Column`, and `Row`): a bare
 * [PNFrameLayout]. All flex semantics are computed by the Python layout
 * engine and applied through `setFrame`; the container is just a
 * positioning surface with `pointer_events` interception.
 */
open class ViewManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = PNFrameLayout(context)
}

/** Empty layout placeholder used as a flexible gap. */
class SpacerManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = View(context)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        // Spacers carry no visual props of their own.
    }
}

/** Safe-area container: a flex container with `fitsSystemWindows`. */
class SafeAreaViewManager : ViewManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val view = PNFrameLayout(context)
        view.fitsSystemWindows = true
        return view
    }
}

/**
 * Vanilla container that publishes the keyboard height (from window
 * insets) as a `Host` module `keyboard` event so the Python-side
 * component can compute its offset.
 */
class KeyboardAvoidingViewManager : ViewManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val view = PNFrameLayout(context)
        ViewCompat.setOnApplyWindowInsetsListener(view) { v, insets ->
            publishKeyboard(v, insets)
            insets
        }
        view.addOnLayoutChangeListener { v, _, _, _, _, _, _, _, _ ->
            ViewCompat.getRootWindowInsets(v)?.let { publishKeyboard(v, it) }
        }
        return view
    }

    private fun publishKeyboard(view: View, insets: WindowInsetsCompat) {
        val density = PNBridge.density()
        val ime = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
        val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom
        val height = max(0, ime - bars) / density
        val last = stateOf(view)["keyboard_height"] as? Double
        if (last != null && last == height.toDouble()) return
        stateOf(view)["keyboard_height"] = height.toDouble()
        ModuleEvents.emit("Host", "keyboard", JSONObject().put("height", height.toDouble()))
    }
}
