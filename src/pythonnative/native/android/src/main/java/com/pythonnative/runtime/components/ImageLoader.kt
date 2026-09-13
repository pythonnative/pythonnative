package com.pythonnative.runtime.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import android.util.Base64
import android.net.Uri
import java.io.ByteArrayOutputStream
import com.pythonnative.runtime.bridge.MainThread
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
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

    private class Request {
        val callbacks = LinkedHashMap<Long, Callback>()
        var future: Future<*>? = null
        @Volatile var connection: HttpURLConnection? = null
        val cancelled = AtomicBoolean(false)
    }
    private val inflight = HashMap<String, Request>()
    private val identifiers = AtomicLong()
    private const val DISK_LIMIT = 64L * 1024 * 1024

    private val memory: LruCache<String, Bitmap> by lazy {
        val maxKb = (Runtime.getRuntime().maxMemory() / 1024L).toInt()
        object : LruCache<String, Bitmap>(minOf(32 * 1024, max(4 * 1024, maxKb / 8))) {
            override fun sizeOf(key: String, value: Bitmap): Int = max(1, value.byteCount / 1024)
        }
    }

    /** Result callback: exactly one of `bitmap` or `error` is non-null. */
    fun interface Callback {
        fun onResult(bitmap: Bitmap?, error: String?)
    }

    /** Load `url` (http/https) into a bitmap sized for `targetW` x `targetH` pixels. */
    fun loadRemote(context: Context, url: String, targetW: Int, targetH: Int, callback: Callback): () -> Unit {
        val key = "$url@$targetW:$targetH"
        memory.get(key)?.let { callback.onResult(it, null); return {} }
        val id = identifiers.incrementAndGet()
        val request: Request
        synchronized(inflight) {
            val existing = inflight[key]
            if (existing != null) {
                request = existing
                request.callbacks[id] = callback
            } else {
                request = Request()
                request.callbacks[id] = callback
                inflight[key] = request
                val cacheDir = File(context.cacheDir, "pn_images")
                request.future = executor.submit {
                    var bitmap: Bitmap? = null
                    var error: String? = null
                    try {
                        val file = cachedFile(cacheDir, url)
                        if (!file.exists() || file.length() == 0L) download(url, file, request)
                        if (!request.cancelled.get()) {
                            bitmap = decodeDownsampled(file.absolutePath, targetW, targetH)
                            if (bitmap == null) { file.delete(); error = "decode failed" }
                            else memory.put(key, bitmap)
                            trimDisk(cacheDir)
                        }
                    } catch (failure: Exception) { error = failure.message ?: "load failed" }
                    val loaded = bitmap
                    val failed = error
                    MainThread.post {
                        val callbacks = synchronized(inflight) {
                            if (inflight[key] !== request) emptyList() else {
                                inflight.remove(key)
                                request.callbacks.values.toList().also { request.callbacks.clear() }
                            }
                        }
                        for (listener in callbacks) listener.onResult(loaded, failed)
                    }
                }
            }
        }
        return {
            synchronized(inflight) {
                request.callbacks.remove(id)
                if (request.callbacks.isEmpty() && inflight[key] === request) {
                    inflight.remove(key)
                    request.cancelled.set(true)
                    request.future?.cancel(true)
                    request.connection?.disconnect()
                }
            }
        }
    }

    /** Decode a local file on a background thread; cancellation suppresses delivery. */
    fun loadFile(path: String, targetW: Int, targetH: Int, callback: Callback): () -> Unit {
        val cancelled = AtomicBoolean(false)
        val future = executor.submit {
            val bitmap = runCatching { decodeDownsampled(path, targetW, targetH) }.getOrNull()
            MainThread.post { if (!cancelled.get()) callback.onResult(bitmap, if (bitmap == null) "decode failed" else null) }
        }
        return { cancelled.set(true); future.cancel(true); Unit }
    }

    /** Decode content URIs and base64 data off the UI thread, with bounded input. */
    fun loadData(context: Context, source: String, targetW: Int, targetH: Int, callback: Callback): () -> Unit {
        val cancelled = AtomicBoolean(false)
        val future = executor.submit {
            val result = runCatching {
                val bytes = if (source.startsWith("data:")) {
                    val payload = source.substringAfter(',', "")
                    require(payload.length <= DISK_LIMIT * 4 / 3 + 4) { "Image exceeds 64 MB" }
                    Base64.decode(payload, Base64.DEFAULT)
                } else {
                    context.contentResolver.openInputStream(Uri.parse(source)).use { input ->
                        requireNotNull(input) { "Image URI is unavailable" }
                        val output = ByteArrayOutputStream()
                        val buffer = ByteArray(8192)
                        while (true) {
                            check(!cancelled.get()) { "Image cancelled" }
                            val count = input.read(buffer)
                            if (count < 0) break
                            require(output.size().toLong() + count <= DISK_LIMIT) { "Image exceeds 64 MB" }
                            output.write(buffer, 0, count)
                        }
                        output.toByteArray()
                    }
                }
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                val options = BitmapFactory.Options().apply { inSampleSize = sampleSize(bounds, targetW, targetH) }
                requireNotNull(BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)) { "Image decode failed" }
            }
            MainThread.post { if (!cancelled.get()) callback.onResult(result.getOrNull(), result.exceptionOrNull()?.message) }
        }
        return { cancelled.set(true); future.cancel(true); Unit }
    }

    private fun trimDisk(directory: File) {
        val files = directory.listFiles()?.filter { !it.name.endsWith(".part") }?.sortedBy { it.lastModified() } ?: return
        var total = files.sumOf { it.length() }
        for (file in files) {
            if (total <= DISK_LIMIT) break
            val size = file.length()
            if (file.delete()) total -= size
        }
    }

    /** Decode `path` with `inSampleSize` chosen so the result still covers the target. */
    fun decodeDownsampled(path: String, targetW: Int, targetH: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(path, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        val opts = BitmapFactory.Options().apply { inSampleSize = sampleSize(bounds, targetW, targetH) }
        return BitmapFactory.decodeFile(path, opts)
    }

    private fun sampleSize(bounds: BitmapFactory.Options, targetW: Int, targetH: Int): Int {
        val width = bounds.outWidth
        val height = bounds.outHeight
        require(width > 0 && height > 0) { "Invalid image dimensions" }
        val tw = if (targetW > 0) targetW.coerceAtMost(4096) else 2048
        val th = if (targetH > 0) targetH.coerceAtMost(4096) else 2048
        var sample = 1
        while (width / (sample * 2) >= tw && height / (sample * 2) >= th) sample *= 2
        while (width / sample > 4096 || height / sample > 4096) sample *= 2
        return sample
    }

    private fun cachedFile(dir: File, url: String): File {
        if (!dir.exists()) dir.mkdirs()
        val digest = MessageDigest.getInstance("SHA-256").digest(url.toByteArray(Charsets.UTF_8))
        val hex = digest.joinToString("") { String.format("%02x", it) }
        val path = url.substringBefore('?').substringBefore('#')
        val ext = path.substringAfterLast('.', "").takeIf { it.length in 1..5 && it.all { c -> c.isLetterOrDigit() } }
        return File(dir, if (ext != null) "$hex.$ext" else hex)
    }

    private fun download(url: String, target: File, request: Request) {
        var current = url
        var redirects = 0
        while (true) {
            if (request.cancelled.get()) return
            val connection = URL(current).openConnection() as HttpURLConnection
            request.connection = connection
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
                val tmp = File.createTempFile(target.name, ".part", target.parentFile)
                try {
                    connection.inputStream.use { input ->
                        FileOutputStream(tmp).use { output ->
                            val buffer = ByteArray(8192)
                            var total = 0L
                            while (true) {
                                if (request.cancelled.get()) return
                                val length = input.read(buffer)
                                if (length < 0) break
                                total += length
                                require(total <= DISK_LIMIT) { "Image exceeds 64 MB" }
                                output.write(buffer, 0, length)
                            }
                        }
                    }
                    if (!tmp.renameTo(target)) tmp.copyTo(target, overwrite = true)
                } finally { tmp.delete() }
                return
            } finally {
                connection.disconnect()
            }
        }
    }

}
