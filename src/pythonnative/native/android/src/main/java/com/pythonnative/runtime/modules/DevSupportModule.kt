package com.pythonnative.runtime.modules

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.view.Choreographer
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import org.json.JSONObject
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * `DevSupport`: the device-side development UI the devtools agent drives.
 *
 * A non-contract module like `Host`: Python enables it only in development
 * mode, and until then menu triggers do nothing. Events go to Python as
 * module events: `menu` (a shake, or the menu key the emulator sends for
 * Cmd+M), `inspect` (`{"tag", "x", "y"}` in dp for a tap while
 * inspecting), and `inspect_done` (the inspector banner's Done button).
 *
 * Overlays are children of the activity's decor view, above the app's
 * content, and are removed when hidden. The inspector and the monitor come
 * back when the activity is recreated.
 */
class DevSupportModule : NativeModule {
    override val name = "DevSupport"

    /** Whether Python has enabled development support. */
    var isEnabled = false
        private set

    private var inspecting = false
    private var monitorVisible = false
    private var monitorLines: List<String> = emptyList()

    internal var highlightView: FrameLayout? = null
        private set
    internal var inspectorView: FrameLayout? = null
        private set
    internal var monitorView: TextView? = null
        private set

    internal val frames = FrameCounter()
    private val shake = ShakeDetector { trigger("menu") }

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "enable" -> {
                isEnabled = true
                PNBridge.activity()?.let { shake.start(it) }
                promise.resolve(null)
            }
            "highlight" -> {
                val tag = if (args.isNull("tag")) null else JsonUtil.toLong(args.opt("tag"))
                promise.resolve(highlight(tag, args.optString("label")))
            }
            "set_inspecting" -> {
                setInspecting(args.optBoolean("enabled"))
                promise.resolve(null)
            }
            "set_perf_monitor" -> {
                val lines = args.optJSONArray("lines")
                monitorLines = if (lines == null) emptyList() else (0 until lines.length()).map { lines.optString(it) }
                setPerfMonitor(args.optBoolean("visible"))
                promise.resolve(null)
            }
            "frame_stats" -> promise.resolve(frames.stats())
            else -> promise.rejectUnknownMethod(method)
        }
    }

    /** Send `event` to Python if development support is enabled; returns whether it was sent. */
    fun trigger(event: String): Boolean {
        if (!isEnabled) return false
        ModuleEvents.emit(name, event, JSONObject())
        return true
    }

    /** The activity's menu key (Cmd+M in the emulator): opens the dev menu. */
    fun onMenuKey(): Boolean = trigger("menu")

    /** Restore the inspector and the monitor in a new activity. */
    fun attach(activity: Activity) {
        if (inspecting) showInspector(activity)
        if (monitorVisible) showMonitor(activity)
    }

    fun resume(activity: Activity) { if (isEnabled) shake.start(activity) }
    fun pause() = shake.stop()

    /** Drop the views that belong to `activity`'s window. */
    fun detach(activity: Activity) {
        shake.stop()
        val decor = activity.window?.decorView as? ViewGroup ?: return
        for (view in listOfNotNull(highlightView, inspectorView, monitorView)) if (view.parent === decor) decor.removeView(view)
        if (highlightView?.parent == null) highlightView = null
        if (inspectorView?.parent == null) inspectorView = null
        if (monitorView?.parent == null) monitorView = null
    }

    private fun decor(): ViewGroup? = PNBridge.activity()?.window?.decorView as? ViewGroup

    private fun density(): Float = PNBridge.activity()?.resources?.displayMetrics?.density ?: 1f

    // ------------------------------------------------------------------
    // Highlight
    // ------------------------------------------------------------------

    /** Outline the view for `tag` with a label chip, or clear it when `tag` is null. */
    internal fun highlight(tag: Long?, label: String): Boolean {
        val decor = decor()
        val target = tag?.let { PNBridge.registry.get(it)?.view }
        if (decor == null || target == null || !target.isAttachedToWindow) {
            highlightView?.let { (it.parent as? ViewGroup)?.removeView(it) }
            highlightView = null
            return false
        }
        val density = density()
        val container = highlightView ?: FrameLayout(decor.context).apply {
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
            addView(View(context).apply {
                background = GradientDrawable().apply {
                    setColor(Color.argb(38, 10, 132, 255))
                    setStroke((2 * density).roundToInt(), ACCENT)
                }
            })
            addView(TextView(context).apply {
                setTextColor(Color.WHITE)
                textSize = 11f
                typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
                setPadding((6 * density).roundToInt(), (2 * density).roundToInt(), (6 * density).roundToInt(), (2 * density).roundToInt())
                background = GradientDrawable().apply { setColor(ACCENT); cornerRadius = 4 * density }
                maxLines = 1
            })
        }
        highlightView = container
        if (container.parent !== decor) {
            (container.parent as? ViewGroup)?.removeView(container)
            decor.addView(container, FrameLayout.LayoutParams(-1, -1))
        }
        val origin = IntArray(2).also { decor.getLocationInWindow(it) }
        val position = IntArray(2).also { target.getLocationInWindow(it) }
        val left = position[0] - origin[0]
        val top = position[1] - origin[1]
        val outline = container.getChildAt(0)
        outline.layoutParams = FrameLayout.LayoutParams(target.width, target.height).apply { leftMargin = left; topMargin = top }
        val chip = container.getChildAt(1) as TextView
        chip.text = label
        chip.visibility = if (label.isEmpty()) View.GONE else View.VISIBLE
        chip.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED)
        val chipHeight = chip.measuredHeight
        val insetTop = systemBars(decor).top
        // Above the outline when there's room, otherwise just inside its top.
        val chipTop = if (top - chipHeight - 2 >= insetTop) top - chipHeight - 2 else maxOf(top + 2, insetTop)
        val chipLeft = left.coerceIn(0, maxOf(0, decor.width - chip.measuredWidth))
        chip.layoutParams = FrameLayout.LayoutParams(-2, -2).apply { leftMargin = chipLeft; topMargin = chipTop }
        raiseOverlays(decor)
        return true
    }

    // ------------------------------------------------------------------
    // Inspector
    // ------------------------------------------------------------------

    /** Intercept taps and report the tapped view as an `inspect` event. */
    internal fun setInspecting(enabled: Boolean) {
        inspecting = enabled
        if (!enabled) {
            inspectorView?.let { (it.parent as? ViewGroup)?.removeView(it) }
            inspectorView = null
            return
        }
        PNBridge.activity()?.let { showInspector(it) }
    }

    private fun showInspector(activity: Activity) {
        val decor = activity.window?.decorView as? ViewGroup ?: return
        if (inspectorView?.parent === decor) return
        inspectorView?.let { (it.parent as? ViewGroup)?.removeView(it) }
        val density = activity.resources.displayMetrics.density
        fun dp(value: Int) = (value * density).roundToInt()
        val overlay = InspectorOverlay(activity) { x, y -> onInspectTap(decor, x, y) }
        overlay.contentDescription = "pn-dev-inspector"
        val banner = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            isClickable = true
            setPadding(dp(16), dp(4), dp(8), dp(4))
            background = GradientDrawable().apply { setColor(Color.argb(230, 26, 26, 26)); cornerRadius = dp(12).toFloat() }
            addView(TextView(activity).apply {
                text = "Tap an element to inspect it"
                setTextColor(Color.WHITE)
                textSize = 14f
            })
            addView(Button(activity).apply {
                text = "Done"
                contentDescription = "pn-dev-inspector-done"
                setTextColor(Color.rgb(115, 179, 255))
                setBackgroundColor(Color.TRANSPARENT)
                setOnClickListener {
                    setInspecting(false)
                    ModuleEvents.emit(name, "inspect_done", JSONObject())
                }
            })
        }
        overlay.addView(banner, FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL).apply {
            bottomMargin = systemBars(decor).bottom + dp(12)
        })
        decor.addView(overlay, FrameLayout.LayoutParams(-1, -1))
        inspectorView = overlay
        raiseOverlays(decor)
    }

    private fun onInspectTap(decor: ViewGroup, x: Int, y: Int) {
        val tag = inspect(decor, x, y) ?: return
        val density = density()
        ModuleEvents.emit(name, "inspect", JSONObject().put("tag", tag).put("x", x / density.toDouble()).put("y", y / density.toDouble()))
    }

    /**
     * The tag of the deepest registered view under (`x`, `y`) in `decor`'s
     * pixels, ignoring the development overlays. Views that don't take
     * touches count, so tapping a `Text` selects the `Text`.
     */
    internal fun inspect(decor: ViewGroup, x: Int, y: Int): Long? {
        val origin = IntArray(2).also { decor.getLocationInWindow(it) }
        val excluded = setOfNotNull<View>(highlightView, inspectorView, monitorView)
        return deepestRegistered(decor, x + origin[0], y + origin[1], excluded, IntArray(2))
    }

    private fun deepestRegistered(view: View, x: Int, y: Int, excluded: Set<View>, location: IntArray): Long? {
        if (view.visibility != View.VISIBLE || view.alpha < 0.01f || view in excluded) return null
        view.getLocationInWindow(location)
        if (x < location[0] || y < location[1] || x >= location[0] + view.width || y >= location[1] + view.height) return null
        if (view is ViewGroup) {
            for (index in view.childCount - 1 downTo 0) {
                deepestRegistered(view.getChildAt(index), x, y, excluded, location)?.let { return it }
            }
        }
        return PNBridge.registry.tagOf(view)
    }

    // ------------------------------------------------------------------
    // Performance monitor
    // ------------------------------------------------------------------

    /** Show the floating monitor with the native frame rate and Python's lines, or hide it. */
    internal fun setPerfMonitor(visible: Boolean) {
        monitorVisible = visible
        if (!visible) {
            monitorView?.let { (it.parent as? ViewGroup)?.removeView(it) }
            monitorView = null
            frames.onSecond = null
            return
        }
        PNBridge.activity()?.let { showMonitor(it) }
    }

    private fun showMonitor(activity: Activity) {
        val decor = activity.window?.decorView as? ViewGroup ?: return
        val density = activity.resources.displayMetrics.density
        fun dp(value: Int) = (value * density).roundToInt()
        val monitor = monitorView ?: TextView(activity).apply {
            contentDescription = "pn-dev-perf-monitor"
            setTextColor(Color.WHITE)
            textSize = 11f
            typeface = Typeface.MONOSPACE
            setPadding(dp(8), dp(6), dp(8), dp(6))
            background = GradientDrawable().apply { setColor(Color.argb(178, 0, 0, 0)); cornerRadius = dp(8).toFloat() }
        }
        monitorView = monitor
        if (monitor.parent !== decor) {
            (monitor.parent as? ViewGroup)?.removeView(monitor)
            decor.addView(monitor, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.END).apply {
                topMargin = systemBars(decor).top + dp(8)
                marginEnd = dp(8)
            })
        }
        frames.start()
        frames.onSecond = { refreshMonitor() }
        refreshMonitor()
        raiseOverlays(decor)
    }

    private fun refreshMonitor() {
        monitorView?.text = (listOf("UI ${frames.fps.roundToInt()} fps") + monitorLines).joinToString("\n")
    }

    /** Keep the overlays above the app's content, the inspector topmost. */
    private fun raiseOverlays(decor: ViewGroup) {
        for (view in listOfNotNull(highlightView, monitorView, inspectorView)) if (view.parent === decor) view.bringToFront()
    }

    private fun systemBars(view: View) =
        ViewCompat.getRootWindowInsets(view)?.getInsets(WindowInsetsCompat.Type.systemBars()) ?: androidx.core.graphics.Insets.NONE

    private companion object {
        val ACCENT = Color.rgb(10, 132, 255)
    }
}

/** A window-sized view that takes every touch while inspecting and reports taps. */
private class InspectorOverlay(context: Context, private val onTap: (Int, Int) -> Unit) : FrameLayout(context) {
    private val slop = ViewConfiguration.get(context).scaledTouchSlop
    private var downX = 0f
    private var downY = 0f

    init { isClickable = true }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> { downX = event.x; downY = event.y }
            MotionEvent.ACTION_UP -> {
                if (kotlin.math.abs(event.x - downX) <= slop && kotlin.math.abs(event.y - downY) <= slop) {
                    performClick()
                    onTap(event.x.roundToInt(), event.y.roundToInt())
                }
            }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()
}

/** Counts the UI thread's frames with `Choreographer`, started on first use. */
class FrameCounter : Choreographer.FrameCallback {
    /** Called on the main thread each time a one-second window closes. */
    var onSecond: (() -> Unit)? = null

    /** Frames per second over the last full second. */
    var fps = 0.0
        private set

    private var running = false
    private var windowStart = 0L
    private var windowFrames = 0
    private var last = 0L
    private var dropped = 0

    /** `{"fps", "dropped"}`: the frame rate and the frames dropped since the previous call. */
    fun stats(): JSONObject {
        start()
        val result = JSONObject().put("fps", (fps * 10).roundToInt() / 10.0).put("dropped", dropped)
        dropped = 0
        return result
    }

    fun start() {
        if (running) return
        running = true
        Choreographer.getInstance().postFrameCallback(this)
    }

    override fun doFrame(frameTimeNanos: Long) {
        val interval = (1_000_000_000L / refreshRate()).coerceAtLeast(1L)
        if (last > 0) {
            val missed = ((frameTimeNanos - last).toDouble() / interval).roundToInt() - 1
            if (missed > 0) dropped += missed
        } else {
            windowStart = frameTimeNanos
        }
        last = frameTimeNanos
        windowFrames += 1
        val elapsed = frameTimeNanos - windowStart
        if (elapsed >= 1_000_000_000L) {
            fps = windowFrames * 1_000_000_000.0 / elapsed
            windowFrames = 0
            windowStart = frameTimeNanos
            onSecond?.invoke()
        }
        Choreographer.getInstance().postFrameCallback(this)
    }

    private fun refreshRate(): Long {
        @Suppress("DEPRECATION")
        val rate = PNBridge.activity()?.windowManager?.defaultDisplay?.refreshRate ?: 60f
        return if (rate >= 1f) rate.roundToInt().toLong() else 60L
    }
}

/** Calls `onShake` when the device is shaken (accelerometer). */
private class ShakeDetector(private val onShake: () -> Unit) : SensorEventListener {
    private var manager: SensorManager? = null
    private var lastShake = 0L

    fun start(context: Context) {
        if (manager != null) return
        val sensors = context.applicationContext.getSystemService(Context.SENSOR_SERVICE) as? SensorManager ?: return
        val accelerometer = sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) ?: return
        sensors.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_UI)
        manager = sensors
    }

    fun stop() {
        manager?.unregisterListener(this)
        manager = null
    }

    override fun onSensorChanged(event: SensorEvent) {
        val (x, y, z) = Triple(event.values[0], event.values[1], event.values[2])
        val force = sqrt(x * x + y * y + z * z) / SensorManager.GRAVITY_EARTH
        val now = System.currentTimeMillis()
        if (force > 2.7f && now - lastShake > 1000) {
            lastShake = now
            onShake()
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
}
