package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import com.pythonnative.runtime.bridge.MainThread
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import kotlin.math.max

/**
 * Image fetching and decoding for the `Image` manager.
 *
 * Remote images are downloaded on a small background pool into a disk
 * cache under `cacheDir/pn_images` (keyed by the SHA-256 of the URL),
 * decoded with `inSampleSize` downsampling to the target size, and kept
 * in a memory `LruCache`. Callbacks run on the main thread.
 */
object ImageLoader {
    private val executor = Executors.newFixedThreadPool(3) { runnable ->
        Thread(runnable, "pn-image").apply { isDaemon = true }
    }

    private val memory: LruCache<String, Bitmap> by lazy {
        val maxKb = (Runtime.getRuntime().maxMemory() / 1024L).toInt()
        object : LruCache<String, Bitmap>(max(4 * 1024, maxKb / 8)) {
            override fun sizeOf(key: String, value: Bitmap): Int = max(1, value.byteCount / 1024)
        }
    }

    /** Result callback: exactly one of `bitmap` or `error` is non-null. */
    fun interface Callback {
        fun onResult(bitmap: Bitmap?, error: String?)
    }

    /** Load `url` (http/https) into a bitmap sized for `targetW` x `targetH` pixels. */
    fun loadRemote(context: Context, url: String, targetW: Int, targetH: Int, callback: Callback) {
        val key = "$url@$targetW"
        memory.get(key)?.let {
            callback.onResult(it, null)
            return
        }
        val cacheDir = File(context.cacheDir, "pn_images")
        executor.execute {
            try {
                val file = cachedFile(cacheDir, url)
                if (!file.exists() || file.length() == 0L) download(url, file)
                val bitmap = decodeDownsampled(file.absolutePath, targetW, targetH)
                if (bitmap == null) {
                    file.delete()
                    deliver(callback, null, "decode failed")
                } else {
                    memory.put(key, bitmap)
                    deliver(callback, bitmap, null)
                }
            } catch (e: Exception) {
                deliver(callback, null, e.message ?: e.javaClass.simpleName)
            }
        }
    }

    /** Decode a local file on a background thread. */
    fun loadFile(path: String, targetW: Int, targetH: Int, callback: Callback) {
        executor.execute {
            val bitmap = try {
                decodeDownsampled(path, targetW, targetH)
            } catch (e: Exception) {
                null
            }
            deliver(callback, bitmap, if (bitmap == null) "decode failed" else null)
        }
    }

    /** Decode `path` with `inSampleSize` chosen so the result still covers the target. */
    fun decodeDownsampled(path: String, targetW: Int, targetH: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(path, bounds)
        val srcW = bounds.outWidth
        val srcH = bounds.outHeight
        if (srcW <= 0 || srcH <= 0) return null
        var tw = if (targetW > 0) targetW else srcW
        var th = if (targetH > 0) targetH else tw
        if (tw <= 0) tw = srcW
        if (th <= 0) th = srcH
        var sample = 1
        while (srcW / (sample * 2) >= tw && srcH / (sample * 2) >= th) sample *= 2
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeFile(path, opts)
    }

    private fun cachedFile(dir: File, url: String): File {
        if (!dir.exists()) dir.mkdirs()
        val digest = MessageDigest.getInstance("SHA-256").digest(url.toByteArray(Charsets.UTF_8))
        val hex = digest.joinToString("") { String.format("%02x", it) }
        val path = url.substringBefore('?').substringBefore('#')
        val ext = path.substringAfterLast('.', "").takeIf { it.length in 1..5 && it.all { c -> c.isLetterOrDigit() } }
        return File(dir, if (ext != null) "$hex.$ext" else hex)
    }

    private fun download(url: String, target: File) {
        var current = url
        var redirects = 0
        while (true) {
            val connection = URL(current).openConnection() as HttpURLConnection
            connection.connectTimeout = 15_000
            connection.readTimeout = 30_000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "PythonNative/Android")
            try {
                val code = connection.responseCode
                if (code in 300..399 && redirects < 5) {
                    val location = connection.getHeaderField("Location") ?: throw IllegalStateException("redirect without Location")
                    current = URL(URL(current), location).toString()
                    redirects++
                    continue
                }
                if (code !in 200..299) throw IllegalStateException("HTTP $code")
                val tmp = File(target.parentFile, target.name + ".part")
                connection.inputStream.use { input ->
                    FileOutputStream(tmp).use { output -> input.copyTo(output) }
                }
                if (!tmp.renameTo(target)) {
                    tmp.copyTo(target, overwrite = true)
                    tmp.delete()
                }
                return
            } finally {
                connection.disconnect()
            }
        }
    }

    private fun deliver(callback: Callback, bitmap: Bitmap?, error: String?) {
        MainThread.post { callback.onResult(bitmap, error) }
    }
}
