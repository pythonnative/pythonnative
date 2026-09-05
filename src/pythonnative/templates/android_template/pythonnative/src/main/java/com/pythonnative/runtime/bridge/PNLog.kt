package com.pythonnative.runtime.bridge

import android.util.Log

/** Rate-limited logging so a hot failing op cannot flood logcat. */
object PNLog {
    const val TAG = "PythonNative"

    private const val BURST = 5
    private const val EVERY = 100
    private val counts = HashMap<String, Int>()
    private val once = HashSet<String>()

    /** Log `message` for `key`, letting the first few through and then every 100th. */
    fun rateLimited(key: String, message: String, error: Throwable? = null) {
        val n = (counts[key] ?: 0) + 1
        counts[key] = n
        if (n <= BURST || n % EVERY == 0) {
            val suffix = if (n > BURST) " (x$n)" else ""
            if (error != null) Log.e(TAG, message + suffix, error) else Log.e(TAG, message + suffix)
        }
    }

    /** Log `message` at most once per `key`. */
    fun once(key: String, message: String) {
        if (once.add(key)) Log.w(TAG, message)
    }

    /** Log a swallowed exception at debug level. */
    fun swallowed(where: String, error: Throwable) {
        Log.d(TAG, "$where: ${error.javaClass.simpleName}: ${error.message}")
    }
}
