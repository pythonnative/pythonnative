package com.pythonnative.runtime.components

import android.app.Activity
import android.content.Context
import android.view.View
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONObject

/** `StatusBar` element: applies bar color, style, and visibility to the host window. */
class StatusBarManager : ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val v = View(context)
        v.visibility = View.GONE
        return v
    }

    override fun setFrame(view: View, x: Double, y: Double, width: Double, height: Double) {}

    override fun measure(view: View, maxWidth: Double, maxHeight: Double): FloatArray = floatArrayOf(0f, 0f)

    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val activity = PNBridge.activity() ?: (view.context as? Activity) ?: return
        val window = activity.window ?: return
        try {
            PNColor.parse(props.value("background_color"))?.let { window.statusBarColor = it }
            val controller: WindowInsetsControllerCompat = WindowCompat.getInsetsController(window, window.decorView)
            props.str("bar_style")?.let { style ->
                // "dark" / "default" mean dark icons (light backgrounds); "light" means light icons.
                controller.isAppearanceLightStatusBars = style == "dark" || style == "default" || style == "dark_content"
            }
            if (props.has("hidden")) {
                if (JsonUtil.truthy(props.value("hidden"))) {
                    controller.hide(WindowInsetsCompat.Type.statusBars())
                } else {
                    controller.show(WindowInsetsCompat.Type.statusBars())
                }
            }
            if (props.has("translucent")) {
                WindowCompat.setDecorFitsSystemWindows(window, !JsonUtil.truthy(props.value("translucent")))
            }
        } catch (e: Exception) {
            PNLog.once("statusbar", "StatusBar: could not apply props on Android: $e")
        }
    }
}
