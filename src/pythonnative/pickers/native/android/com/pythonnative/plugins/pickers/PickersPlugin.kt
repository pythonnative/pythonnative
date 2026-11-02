package com.pythonnative.plugins.pickers

import android.app.Activity
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.os.Build
import android.os.ext.SdkExtensions
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import com.pythonnative.generated.PNPickedFile
import com.pythonnative.generated.PickersImplementation
import com.pythonnative.generated.PickersModuleAdapter
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.PNLifecycleHook
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions
import com.pythonnative.runtime.modules.RequestCodes
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.Executors

private const val READ_MEDIA_IMAGES = "android.permission.READ_MEDIA_IMAGES"
private const val READ_MEDIA_VIDEO = "android.permission.READ_MEDIA_VIDEO"
private const val READ_EXTERNAL_STORAGE = "android.permission.READ_EXTERNAL_STORAGE"

/** Registers `Pickers` and owns the `photo_library` permission. */
object PickersPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { PickersModuleAdapter(PickersModule) }
        registry.registerLifecycleHook(PickersModule)
        PNPermissions.register(
            "photo_library",
            READ_MEDIA_IMAGES,
            arrayOf(READ_MEDIA_IMAGES, READ_MEDIA_VIDEO),
            minSdk = 33,
            legacy = READ_EXTERNAL_STORAGE,
        )
    }
}

/**
 * `Pickers`: the system photo picker through `ACTION_PICK_IMAGES` where it
 * exists, `ACTION_GET_CONTENT` where it doesn't, and `ACTION_OPEN_DOCUMENT`.
 *
 * A granted URI lasts only as long as the activity, and a provider can be slow
 * or remote, so each file is copied to the cache on a background thread before
 * Python sees it.
 */
object PickersModule : PickersImplementation, PNLifecycleHook {
    /**
     * @property limit How many results to keep; the document picker can't enforce a number.
     * @property quality JPEG quality from 0 to 100 to re-encode at, or `null` to keep the bytes.
     */
    private class Pending(val limit: Int, val quality: Int?, val done: (Result<List<PNPickedFile>>) -> Unit)

    private val pending = HashMap<Int, Pending>()
    private val executor by lazy { Executors.newSingleThreadExecutor() }

    /** `ACTION_PICK_IMAGES` is on API 33, and on API 30 to 32 through an SDK extension. */
    private fun hasPhotoPicker(): Boolean =
        Build.VERSION.SDK_INT >= 33 || (Build.VERSION.SDK_INT >= 30 && SdkExtensions.getExtensionVersion(Build.VERSION_CODES.R) >= 2)

    private fun mediaIntent(mime: String, limit: Int): Intent {
        val multiple = limit != 1
        if (hasPhotoPicker()) {
            val intent = Intent(MediaStore.ACTION_PICK_IMAGES).setType(mime)
            if (multiple) {
                // The extra rejects 1 and anything over the platform's maximum.
                val maximum = MediaStore.getPickImagesMaxLimit()
                intent.putExtra(MediaStore.EXTRA_PICK_IMAGES_MAX, if (limit == 0) maximum else limit.coerceAtMost(maximum))
            }
            return intent
        }
        return Intent(Intent.ACTION_GET_CONTENT).setType(mime).addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
    }

    override fun pick_images(limit: Long, quality: Double, completion: (Result<List<PNPickedFile>>) -> Unit): (() -> Unit)? =
        launch(mediaIntent("image/*", limit.toInt()), limit.toInt(), (quality.coerceIn(0.0, 1.0) * 100).toInt(), completion)

    override fun pick_videos(limit: Long, completion: (Result<List<PNPickedFile>>) -> Unit): (() -> Unit)? =
        launch(mediaIntent("video/*", limit.toInt()), limit.toInt(), null, completion)

    override fun pick_documents(multiple: Boolean, types: List<String>?, completion: (Result<List<PNPickedFile>>) -> Unit): (() -> Unit)? {
        val wanted = types?.takeIf { it.isNotEmpty() } ?: listOf("*/*")
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType(if (wanted.size == 1) wanted[0] else "*/*")
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
        if (wanted.size > 1) intent.putExtra(Intent.EXTRA_MIME_TYPES, wanted.toTypedArray())
        return launch(intent, if (multiple) 0 else 1, null, completion)
    }

    private fun launch(intent: Intent, limit: Int, quality: Int?, completion: (Result<List<PNPickedFile>>) -> Unit): (() -> Unit)? {
        val activity = PNBridge.activity() ?: run { completion(Result.success(emptyList())); return null }
        if (pending.isNotEmpty()) {
            completion(Result.failure(PNModuleError("A picker is already open", "busy")))
            return null
        }
        val code = RequestCodes.next()
        pending[code] = Pending(limit, quality, completion)
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(intent, code)
        } catch (error: Exception) {
            pending.remove(code)
            completion(Result.failure(PNModuleError(error.message ?: "The picker couldn't open", "unavailable")))
            return null
        }
        return {
            if (pending.remove(code) != null) {
                @Suppress("DEPRECATION")
                activity.finishActivity(code)
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        val request = pending.remove(requestCode) ?: return false
        val uris = if (resultCode == Activity.RESULT_OK) resultUris(data) else emptyList()
        val kept = if (request.limit > 0) uris.take(request.limit) else uris
        if (kept.isEmpty()) {
            request.done(Result.success(emptyList()))
            return true
        }
        val ctx = PNBridge.context()
        executor.execute {
            val result = runCatching { kept.map { importFile(ctx, it, request.quality) } }
            MainThread.post { request.done(result.recoverCatching { throw PNModuleError(it.message ?: "The file couldn't be read", "pick_failed") }) }
        }
        return true
    }

    private fun resultUris(data: Intent?): List<Uri> {
        val clip = data?.clipData
        if (clip != null && clip.itemCount > 0) return (0 until clip.itemCount).mapNotNull { clip.getItemAt(it).uri }
        return listOfNotNull(data?.data)
    }

    private fun importFile(ctx: Context, uri: Uri, quality: Int?): PNPickedFile {
        val resolver = ctx.contentResolver
        val name = displayName(resolver, uri)
        val mime = resolver.getType(uri) ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase()) ?: "application/octet-stream"
        val target = File(newDirectory(ctx), safeName(name))
        resolver.openInputStream(uri)?.use { input -> FileOutputStream(target).use { input.copyTo(it) } }
            ?: throw PNModuleError("The provider returned no data for $name", "pick_failed")
        // PNG and GIF keep their bytes for transparency and animation.
        if (quality != null && quality < 100 && mime != "image/png" && mime != "image/gif") {
            reencode(ctx, target, quality)?.let { return PNPickedFile(mime_type = "image/jpeg", name = it.name, path = it.absolutePath, size = it.length()) }
        }
        return PNPickedFile(mime_type = mime, name = target.name, path = target.absolutePath, size = target.length())
    }

    /** Write `source` as a JPEG with its EXIF rotation applied, or `null` when it can't be decoded. */
    private fun reencode(ctx: Context, source: File, quality: Int): File? = try {
        BitmapFactory.decodeFile(source.absolutePath)?.let { bitmap ->
            val rotation = exifRotation(source)
            val upright = if (rotation == 0) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
            val target = File(newDirectory(ctx), source.nameWithoutExtension + ".jpg")
            FileOutputStream(target).use { check(upright.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(1, 100), it)) }
            if (upright !== bitmap) upright.recycle()
            bitmap.recycle()
            source.delete()
            source.parentFile?.delete()
            target
        }
    } catch (error: Throwable) {
        // Out of memory or a decoder failure: the original file is still a valid answer.
        PNLog.swallowed("Pickers.reencode", error)
        null
    }

    private fun exifRotation(file: File): Int = try {
        when (ExifInterface(file.absolutePath).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90
            ExifInterface.ORIENTATION_ROTATE_180 -> 180
            ExifInterface.ORIENTATION_ROTATE_270 -> 270
            else -> 0
        }
    } catch (_: Exception) {
        0
    }

    private fun displayName(resolver: ContentResolver, uri: Uri): String {
        try {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) cursor.getString(index)?.takeIf { it.isNotEmpty() }?.let { return it }
                }
            }
        } catch (error: Exception) {
            PNLog.swallowed("Pickers.displayName", error)
        }
        return uri.lastPathSegment?.substringAfterLast('/')?.takeIf { it.isNotEmpty() } ?: "file"
    }

    /** A provider chooses the name, so it can't be trusted not to climb out of the directory. */
    private fun safeName(name: String): String = name.substringAfterLast('/').substringAfterLast('\\').takeIf { it.isNotEmpty() && it != "." && it != ".." } ?: "file"

    /** A fresh directory, so that two files with one name can't collide. */
    private fun newDirectory(ctx: Context): File = File(File(ctx.cacheDir, "pn-pickers"), UUID.randomUUID().toString()).apply { mkdirs() }
}
