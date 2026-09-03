package com.pythonnative.runtime.bridge

import android.os.Handler
import android.os.Looper

/** Main-looper helpers shared by the bridge, modules, and managers. */
object MainThread {
    private val handler: Handler by lazy { Handler(Looper.getMainLooper()) }

    /** Whether the current thread is the main thread. */
    fun isMain(): Boolean = Looper.myLooper() == Looper.getMainLooper()

    /** Post `runnable` to the main looper. */
    fun post(runnable: Runnable) {
        handler.post(runnable)
    }

    /** Post `runnable` to the main looper after `delayMs`. */
    fun postDelayed(runnable: Runnable, delayMs: Long) {
        handler.postDelayed(runnable, delayMs)
    }

    /** Remove a pending `runnable`. */
    fun remove(runnable: Runnable) {
        handler.removeCallbacks(runnable)
    }

    /** Run `runnable` inline when already on the main thread, otherwise post it. */
    fun runOnMain(runnable: Runnable) {
        if (isMain()) runnable.run() else post(runnable)
    }
}
