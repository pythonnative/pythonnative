package com.pythonnative.runtime.screens

import android.content.Context
import android.content.res.Configuration
import android.graphics.Point
import android.os.Build
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.pythonnative.runtime.PNBridge
import org.json.JSONObject
import kotlin.math.max

/**
 * Integer ids for live [PNScreenFragment]s. Python addresses screens
 * by these ids in `Host` module calls and receives them as the `tag`
 * of `host` callbacks.
 */
object ScreenRegistry {
    private val screens = LinkedHashMap<Int, PNScreenFragment>()
    private var nextId = 1
    private var activeId = 0

    /** Assign an id to `fragment`. */
    fun register(fragment: PNScreenFragment): Int {
        val id = nextId++
        screens[id] = fragment
        return id
    }

    fun unregister(id: Int) {
        screens.remove(id)
        if (activeId == id) activeId = screens.keys.lastOrNull() ?: 0
    }

    fun get(id: Int): PNScreenFragment? = screens[id]

    /** Mark `id` as the screen the user currently sees (called on resume). */
    fun setActive(id: Int) {
        activeId = id
    }

    /** The visible screen's id, or `0`. */
    fun activeId(): Int = activeId

    /** The fragment container of the visible screen (overlay host for `Portal`). */
    fun activeContainer(): ViewGroup? = screens[activeId]?.container ?: screens.values.lastOrNull()?.container
}

/** Builds the viewport payload shared by `layout`, `resume`, and `Host.viewport`. */
object Viewport {
    /**
     * `{width, height, insets{top,left,bottom,right}, color_scheme,
     * keyboard_height, scale, font_scale, screen_width, screen_height}`
     * in dp, measured from `view` (falling back to display metrics when
     * the view has not been laid out yet). `scale` is the display
     * density, `font_scale` the user's text scaling, and
     * `screen_width`/`screen_height` the physical display size in dp
     * (`Dimensions.get("screen")`), as opposed to the window the view
     * occupies.
     */
    fun describe(view: View): JSONObject {
        val density = PNBridge.density()
        val metrics = view.resources.displayMetrics
        val screen = screenSize(view.context)
        val w = if (view.width > 0) view.width else metrics.widthPixels
        val h = if (view.height > 0) view.height else metrics.heightPixels
        val insets = ViewCompat.getRootWindowInsets(view)
        val bars = insets?.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
        val ime = insets?.getInsets(WindowInsetsCompat.Type.ime())
        val bottomBar = bars?.bottom ?: 0
        val keyboard = max(0, (ime?.bottom ?: 0) - bottomBar) / density
        val night = view.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK
        return JSONObject()
            .put("width", w / density.toDouble())
            .put("height", h / density.toDouble())
            .put(
                "insets",
                JSONObject()
                    .put("top", (bars?.top ?: 0) / density.toDouble())
                    .put("left", (bars?.left ?: 0) / density.toDouble())
                    .put("bottom", bottomBar / density.toDouble())
                    .put("right", (bars?.right ?: 0) / density.toDouble()),
            )
            .put("color_scheme", if (night == Configuration.UI_MODE_NIGHT_YES) "dark" else "light")
            .put("keyboard_height", keyboard.toDouble())
            .put("scale", density.toDouble())
            .put("font_scale", view.resources.configuration.fontScale.toDouble())
            .put("screen_width", screen.x / density.toDouble())
            .put("screen_height", screen.y / density.toDouble())
    }

    /** The full display size in pixels (including system bars). */
    fun screenSize(context: Context): Point {
        val fallback = context.resources.displayMetrics.let { Point(it.widthPixels, it.heightPixels) }
        val manager = context.getSystemService(Context.WINDOW_SERVICE) as? WindowManager ?: return fallback
        return try {
            if (Build.VERSION.SDK_INT >= 30) {
                val bounds = manager.maximumWindowMetrics.bounds
                if (bounds.width() > 0 && bounds.height() > 0) Point(bounds.width(), bounds.height()) else fallback
            } else {
                val point = Point()
                @Suppress("DEPRECATION")
                manager.defaultDisplay.getRealSize(point)
                if (point.x > 0 && point.y > 0) point else fallback
            }
        } catch (_: Exception) {
            fallback
        }
    }
}
