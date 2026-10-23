package com.pythonnative.runtime.animation

import android.view.Choreographer
import com.pythonnative.runtime.core.PNCore

/**
 * Display frames for the core's animator. The core asks for frames
 * (`request_frames`) when a driver starts; the clock then ticks on every
 * `Choreographer` frame until no driver is left.
 */
object FrameClock : Choreographer.FrameCallback {
    private var running = false

    /** Start ticking; call on the main thread. */
    fun start() {
        if (running || !PNCore.loaded) return
        running = true
        Choreographer.getInstance().postFrameCallback(this)
    }

    override fun doFrame(frameTimeNanos: Long) {
        if (PNCore.animationFrame(frameTimeNanos / 1_000_000.0)) Choreographer.getInstance().postFrameCallback(this)
        else running = false
    }
}
