package com.pythonnative.runtime.core

import android.animation.ValueAnimator
import android.content.Context
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.View
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.animation.FrameClock
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.layout.Measurement
import com.pythonnative.runtime.mount.MountDecoder
import com.pythonnative.runtime.mount.Mounter
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The renderer core (`include/pn_core.h`), loaded from `libpncore.so`.
 *
 * Python commits to the same library through ctypes; Kotlin is the
 * platform half. It installs the core's platform callbacks, drains mount
 * transactions on the main thread, runs the core's deferred work on a
 * background thread, drives animation frames from the `Choreographer`,
 * and feeds events, pointers, and container sizes back. The main thread
 * never waits on another thread for any of this.
 *
 * JVM unit tests run without the library; every entry point then degrades
 * to a no-op (and events go straight to the Python mailbox).
 */
object PNCore {
    /** The surface every host mounts into. */
    const val SURFACE = 1L

    /** Whether `libpncore.so` loaded. */
    @JvmStatic
    val loaded: Boolean = try {
        System.loadLibrary("pncore")
        true
    } catch (error: Throwable) {
        Log.w(PNBridge.TAG, "libpncore.so unavailable: ${error.message}")
        false
    }

    private var installed = false
    private val mountScheduled = AtomicBoolean(false)
    private val workScheduled = AtomicBoolean(false)
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "PythonNative-core").apply { isDaemon = true }
    }

    /** Applies mount transactions to the platform views. */
    val mounter by lazy { Mounter(PNBridge.registry) }

    /**
     * Install the platform callbacks and tell Python where the library is.
     * Runs once, before Python starts.
     */
    fun install(context: Context) {
        if (installed || !loaded) return
        installed = true
        nativeInstall()
        // ctypes opens the image the app already loaded: by path when the
        // library was extracted, otherwise by its soname.
        val extracted = File(context.applicationInfo.nativeLibraryDir ?: "", "libpncore.so")
        val path = if (extracted.exists()) extracted.absolutePath else "libpncore.so"
        try {
            android.system.Os.setenv("PN_CORE_LIBRARY", path, true)
        } catch (error: Exception) {
            Log.e(PNBridge.TAG, "could not export PN_CORE_LIBRARY", error)
        }
        updateReduceMotion(context)
    }

    /** Re-read the system's animation setting (reduce motion). */
    fun updateReduceMotion(context: Context) {
        if (!loaded) return
        val disabled = if (Build.VERSION.SDK_INT >= 26) !ValueAnimator.areAnimatorsEnabled()
        else Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        nativeSetReduceMotion(disabled)
    }

    // ------------------------------------------------------------------
    // Platform callbacks (called from C++ on any thread)
    // ------------------------------------------------------------------

    @JvmStatic
    fun scheduleMount() {
        if (mountScheduled.compareAndSet(false, true)) MainThread.post(Runnable { drainMounts() })
    }

    @JvmStatic
    fun scheduleWork() {
        if (workScheduled.compareAndSet(false, true)) worker.execute {
            workScheduled.set(false)
            nativeWork()
        }
    }

    @JvmStatic
    fun requestFrames() {
        MainThread.runOnMain(Runnable { FrameClock.start() })
    }

    @JvmStatic
    fun measure(
        surface: Long, tag: Long, component: String, mode: Int, props: ByteBuffer,
        width: Float, widthMode: Int, height: Float, heightMode: Int,
    ): FloatArray = Measurement.measure(tag, component, mode, props, width, widthMode, height, heightMode)

    @JvmStatic
    fun baseline(surface: Long, tag: Long, width: Float, height: Float): Float = Measurement.baseline(tag, height)

    @JvmStatic
    fun emit(kind: String, surface: Long, tag: Long, name: String, payload: ByteArray) {
        PNBridge.callPython(kind, tag, name, String(payload, Charsets.UTF_8))
    }

    // ------------------------------------------------------------------
    // The main thread's side
    // ------------------------------------------------------------------

    /**
     * Apply every queued mount transaction now. Module calls run this first,
     * so a module (`Host.attach_root`) always sees the views Python committed.
     */
    fun drainMounts() {
        mountScheduled.set(false)
        if (!loaded) return
        while (true) {
            val transaction = nativeMountNext() ?: break
            mounter.mount(transaction)
        }
    }

    /** Report a mount transaction applied (`error` null) or failed. */
    fun mountFinished(id: Long, error: String?) {
        if (loaded) nativeMountFinished(id, error?.toByteArray(Charsets.UTF_8))
    }

    /** Apply the animated prop writes the core produced. */
    fun applyWrites() {
        if (!loaded) return
        val buffer = nativeTakeWrites() ?: return
        for (write in MountDecoder.decodeWrites(buffer)) {
            val record = PNBridge.registry.get(write.tag) ?: continue
            try {
                record.manager.setAnimatedProperty(record.view, write.prop, write.value)
            } catch (error: Exception) {
                Log.d(PNBridge.TAG, "animated write ${write.prop} failed", error)
            }
        }
    }

    /** Stamp and deliver a view event to Python. */
    fun event(tag: Long, name: String, args: JSONArray, editRevision: Long = 0) {
        if (!loaded) {
            PNBridge.callPython("event", tag, name, JSONObject().put("args", args).put("edit_revision", editRevision).toString())
            return
        }
        nativeEvent(SURFACE, tag, name, args.toString().toByteArray(Charsets.UTF_8), editRevision)
        applyWrites()
    }

    fun reportContainer(tag: Long, x: Float, y: Float, width: Float, height: Float) {
        if (loaded && width > 0 && height > 0) nativeReportContainer(SURFACE, tag, x, y, width, height)
    }

    /** Report `view`'s size and window origin as the container `tag` lays out in, now and whenever its size changes. */
    fun observeContainer(view: View, tag: Long) {
        view.addOnLayoutChangeListener { v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom ->
            if (right - left != oldRight - oldLeft || bottom - top != oldBottom - oldTop) reportContainer(v, tag)
        }
        if (view.width > 0) reportContainer(view, tag)
    }

    private fun reportContainer(view: View, tag: Long) {
        val density = PNBridge.density()
        val origin = IntArray(2)
        view.getLocationInWindow(origin)
        reportContainer(tag, origin[0] / density, origin[1] / density, view.width / density, view.height / density)
    }

    fun reportIntrinsic(tag: Long, width: Float, height: Float) {
        if (loaded) nativeReportIntrinsic(SURFACE, tag, width, height)
    }

    fun invalidate(tag: Long) {
        if (loaded) nativeInvalidate(SURFACE, tag)
    }

    fun invalidateMeasurements() {
        if (loaded) nativeInvalidateMeasurements()
    }

    fun protocolVersion(): Int = if (loaded) nativeProtocolVersion() else com.pythonnative.generated.PNContracts.protocolVersion

    @JvmStatic
    fun validateModule(module: String, method: String, arguments: String): Boolean =
        !loaded || nativeValidateModule(module, method, arguments.toByteArray(Charsets.UTF_8))

    // -- gestures ---------------------------------------------------------

    fun hasGestures(tag: Long): Boolean = loaded && nativeHasGestures(SURFACE, tag)

    /** Feed packed `(phase, pointer, x, y, windowX, windowY, seconds)` events; returns whether a pan is active. */
    fun pointer(tag: Long, events: DoubleArray, count: Int): Boolean {
        if (!loaded || count == 0) return false
        val active = nativePointer(SURFACE, tag, events, count) != 0
        applyWrites()
        return active
    }

    fun gestureDeadline(tag: Long): Double = if (loaded) nativeGestureDeadline(SURFACE, tag) else -1.0

    fun gesturePoll(tag: Long, time: Double) {
        if (!loaded) return
        nativeGesturePoll(SURFACE, tag, time)
        applyWrites()
    }

    /** Seconds on the clock gesture timestamps use. */
    fun now(): Double = SystemClock.uptimeMillis() / 1000.0

    // -- lists ------------------------------------------------------------

    /** Publish a list's next dataset patch; returns its edits. */
    fun listApply(tag: Long): JSONObject? = if (loaded) nativeListApply(SURFACE, tag)?.let { JSONObject(it) } else null

    fun listCount(tag: Long): Int = if (loaded) nativeListCount(SURFACE, tag).toInt() else 0
    fun listRevision(tag: Long): Long = if (loaded) nativeListRevision(SURFACE, tag) else 0L

    fun listKey(tag: Long, index: Int): String? =
        if (loaded) nativeListKey(SURFACE, tag, index.toLong())?.let { String(it, Charsets.UTF_8) } else null

    fun listIndex(tag: Long, key: String): Int =
        if (loaded) nativeListIndex(SURFACE, tag, key.toByteArray(Charsets.UTF_8)).toInt() else -1

    fun listExtent(tag: Long, index: Int): Double = if (loaded) nativeListExtent(SURFACE, tag, index.toLong()) else 0.0

    fun listSticky(tag: Long, index: Int): Boolean = loaded && nativeListSticky(SURFACE, tag, index.toLong())

    fun listStickyAt(tag: Long, index: Int): Int = if (loaded) nativeListStickyAt(SURFACE, tag, index.toLong()).toInt() else -1

    /** The first sticky row after `index`, or -1 (a binary search over [listStickyAt]). */
    fun listNextSticky(tag: Long, index: Int): Int {
        val count = listCount(tag)
        var low = index + 1
        var high = count - 1
        if (low > high || listStickyAt(tag, high) <= index) return -1
        while (low < high) {
            val mid = (low + high) / 2
            if (listStickyAt(tag, mid) > index) high = mid else low = mid + 1
        }
        return low
    }

    /** Advance the core's animation drivers to `timestampMs`; returns whether any still run. */
    fun animationFrame(timestampMs: Double): Boolean {
        if (!loaded) return false
        val more = nativeAnimationFrame(timestampMs)
        applyWrites()
        return more
    }

    // ------------------------------------------------------------------
    // JNI
    // ------------------------------------------------------------------

    @JvmStatic private external fun nativeInstall()
    @JvmStatic private external fun nativeProtocolVersion(): Int
    @JvmStatic private external fun nativeValidateModule(module: String, method: String, arguments: ByteArray): Boolean
    @JvmStatic private external fun nativeWork()
    @JvmStatic private external fun nativeMountNext(): ByteBuffer?
    @JvmStatic private external fun nativeMountFinished(id: Long, error: ByteArray?)
    @JvmStatic private external fun nativeReportContainer(surface: Long, tag: Long, x: Float, y: Float, width: Float, height: Float)
    @JvmStatic private external fun nativeReportIntrinsic(surface: Long, tag: Long, width: Float, height: Float)
    @JvmStatic private external fun nativeInvalidate(surface: Long, tag: Long)
    @JvmStatic private external fun nativeInvalidateMeasurements()
    @JvmStatic private external fun nativeEvent(surface: Long, tag: Long, name: String, arguments: ByteArray, editRevision: Long)
    @JvmStatic private external fun nativeAnimationFrame(timestampMs: Double): Boolean
    @JvmStatic private external fun nativeTakeWrites(): ByteBuffer?
    @JvmStatic private external fun nativeSetReduceMotion(enabled: Boolean)
    @JvmStatic private external fun nativePointer(surface: Long, tag: Long, events: DoubleArray, count: Int): Int
    @JvmStatic private external fun nativeGestureDeadline(surface: Long, tag: Long): Double
    @JvmStatic private external fun nativeGesturePoll(surface: Long, tag: Long, time: Double)
    @JvmStatic private external fun nativeHasGestures(surface: Long, tag: Long): Boolean
    @JvmStatic private external fun nativeListApply(surface: Long, tag: Long): String?
    @JvmStatic private external fun nativeListCount(surface: Long, tag: Long): Long
    @JvmStatic private external fun nativeListRevision(surface: Long, tag: Long): Long
    @JvmStatic private external fun nativeListKey(surface: Long, tag: Long, index: Long): ByteArray?
    @JvmStatic private external fun nativeListIndex(surface: Long, tag: Long, key: ByteArray): Long
    @JvmStatic private external fun nativeListExtent(surface: Long, tag: Long, index: Long): Double
    @JvmStatic private external fun nativeListSticky(surface: Long, tag: Long, index: Long): Boolean
    @JvmStatic private external fun nativeListStickyAt(surface: Long, tag: Long, index: Long): Long
}
