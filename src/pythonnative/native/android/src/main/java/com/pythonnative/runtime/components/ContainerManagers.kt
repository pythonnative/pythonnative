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
 * Vanilla container for `KeyboardAvoidingView`. The offset is computed in
 * Python from the `Keyboard` module's `change` events (fed by
 * `PNKeyboard`), so the view itself carries no keyboard logic.
 */
class KeyboardAvoidingViewManager : ViewManager()
