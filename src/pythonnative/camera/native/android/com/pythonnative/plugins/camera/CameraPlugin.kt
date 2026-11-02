package com.pythonnative.plugins.camera

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.provider.MediaStore
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.annotation.OptIn
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.core.UseCase
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.Observer
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.pythonnative.generated.CameraImplementation
import com.pythonnative.generated.CameraModuleAdapter
import com.pythonnative.generated.CameraViewProps
import com.pythonnative.generated.PNBarcode
import com.pythonnative.generated.PNCameraError
import com.pythonnative.generated.PNCameraViewBarcodeTypesItem
import com.pythonnative.generated.PNCameraViewFacing
import com.pythonnative.generated.PNCameraViewFlash
import com.pythonnative.generated.PNComponentEvents
import com.pythonnative.generated.PNPhoto
import com.pythonnative.generated.PNVideoRecording
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.TypedComponentManager
import com.pythonnative.runtime.components.ViewStyler
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.PNLifecycleHook
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions
import com.pythonnative.runtime.modules.RequestCodes
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max
import kotlin.math.min

private const val CAMERA = "android.permission.CAMERA"
private const val RECORD_AUDIO = "android.permission.RECORD_AUDIO"

/** Registers `Camera` and `CameraView`, and owns the `camera` and `microphone` permissions. */
object CameraPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { CameraModuleAdapter(CameraModule) }
        registry.registerComponent("CameraView") { CameraViewManager() }
        registry.registerLifecycleHook(CameraModule)
        PNPermissions.register("camera", CAMERA)
        PNPermissions.register("microphone", RECORD_AUDIO)
    }
}

/** Decoding and re-encoding can take long enough to stall the UI, so captures finish here. */
private val captureExecutor: ExecutorService by lazy { Executors.newSingleThreadExecutor() }

private fun newCaptureFile(ctx: Context, suffix: String): File {
    val dir = File(ctx.cacheDir, "pn-camera").apply { mkdirs() }
    return File.createTempFile("pn-camera-", suffix, dir)
}

private fun exifRotation(file: File): Int = try {
    when (ExifInterface(file.absolutePath).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
        ExifInterface.ORIENTATION_ROTATE_90 -> 90
        ExifInterface.ORIENTATION_ROTATE_180 -> 180
        ExifInterface.ORIENTATION_ROTATE_270 -> 270
        else -> 0
    }
} catch (error: Exception) {
    PNLog.swallowed("Camera.exif", error)
    0
}

/**
 * Re-encode at [quality] unless it's 100, and return the resulting file.
 * Decoding drops the EXIF orientation that writing the JPEG wouldn't restore,
 * so the pixels are rotated to match. A failure leaves the original, which is
 * still a valid answer.
 */
private fun finishCapture(ctx: Context, file: File, quality: Int): File {
    if (quality >= 100) return file
    return try {
        val bitmap = BitmapFactory.decodeFile(file.absolutePath) ?: return file
        val rotation = exifRotation(file)
        val upright = if (rotation == 0) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
        val target = newCaptureFile(ctx, ".jpg")
        FileOutputStream(target).use { check(upright.compress(Bitmap.CompressFormat.JPEG, quality.coerceIn(1, 100), it)) }
        if (upright !== bitmap) upright.recycle()
        bitmap.recycle()
        file.delete()
        target
    } catch (error: Throwable) {
        PNLog.swallowed("Camera.recompress", error)
        file
    }
}

/** The file's size as it displays, which swaps the sides of a rotated JPEG. */
private fun photoRecord(file: File): PNPhoto {
    val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.absolutePath, options)
    val sideways = exifRotation(file) % 180 != 0
    val width = if (sideways) options.outHeight else options.outWidth
    val height = if (sideways) options.outWidth else options.outHeight
    return PNPhoto(height = height.toLong(), path = file.absolutePath, width = width.toLong())
}

/**
 * `Camera`: the system capture screen, and the answering half of
 * `CameraViewHandle`, which addresses a view by its tag.
 *
 * `take_photo` launches `ACTION_IMAGE_CAPTURE` with `EXTRA_OUTPUT` set to a
 * `FileProvider` URI so the camera writes the full-resolution capture instead
 * of returning a thumbnail. The system refuses that intent to an app that
 * declares the `CAMERA` permission without holding it, and this plugin always
 * declares it, so the permission comes first.
 */
object CameraModule : CameraImplementation, PNLifecycleHook {
    private class Pending(val quality: Int, val output: File, val uri: Uri, val done: (Result<String?>) -> Unit)

    private const val URI_GRANTS = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
    private val pending = HashMap<Int, Pending>()

    override fun take_photo(allow_editing: Boolean, quality: Double, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        if (allow_editing) PNLog.once("camera-editing", "Camera: allow_editing is not supported on Android and is ignored")
        val activity = PNBridge.activity() ?: run { completion(Result.success(null)); return null }
        if (pending.isNotEmpty()) {
            completion(Result.failure(PNModuleError("The camera screen is already open", "busy")))
            return null
        }
        var cancelled = false
        var cancelLaunch: (() -> Unit)? = null
        val cancelRequest = BuiltinModules.permissions.requestManifest(arrayOf(CAMERA)) { results ->
            if (cancelled) return@requestManifest
            if (results.any { it == PackageManager.PERMISSION_GRANTED }) {
                cancelLaunch = launch(activity, quality, completion)
            } else {
                completion(Result.success(null))
            }
        }
        return {
            cancelled = true
            cancelRequest?.invoke()
            cancelLaunch?.invoke()
        }
    }

    private fun launch(activity: Activity, quality: Double, completion: (Result<String?>) -> Unit): (() -> Unit)? {
        val output: File
        val uri: Uri
        try {
            output = newCaptureFile(activity, ".jpg")
            uri = FileProvider.getUriForFile(activity, activity.packageName + ".pythonnative.fileprovider", output)
        } catch (error: Exception) {
            completion(Result.failure(error))
            return null
        }
        val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT, uri).addFlags(URI_GRANTS)
        // Some camera apps read EXTRA_OUTPUT from a ClipData; grant every resolver explicitly too.
        intent.clipData = ClipData.newRawUri("output", uri)
        try {
            for (info in activity.packageManager.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY)) {
                activity.grantUriPermission(info.activityInfo.packageName, uri, URI_GRANTS)
            }
        } catch (error: Exception) {
            PNLog.swallowed("Camera.grant", error)
        }
        val code = RequestCodes.next()
        pending[code] = Pending((quality.coerceIn(0.0, 1.0) * 100).toInt(), output, uri, completion)
        try {
            @Suppress("DEPRECATION")
            activity.startActivityForResult(intent, code)
        } catch (error: Exception) {
            pending.remove(code)
            revoke(activity, uri)
            output.delete()
            completion(Result.failure(error))
            return null
        }
        return {
            pending.remove(code)?.let { revoke(activity, it.uri); it.output.delete() }
            @Suppress("DEPRECATION")
            activity.finishActivity(code)
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean {
        val request = pending.remove(requestCode) ?: return false
        revoke(PNBridge.activity(), request.uri)
        val captured = request.output
        if (resultCode != Activity.RESULT_OK || !captured.exists() || captured.length() == 0L) {
            captured.delete()
            request.done(Result.success(null))
            return true
        }
        val ctx = PNBridge.context()
        captureExecutor.execute { request.done(Result.success(finishCapture(ctx, captured, request.quality).absolutePath)) }
        return true
    }

    private fun revoke(activity: Activity?, uri: Uri) {
        try { activity?.revokeUriPermission(uri, URI_GRANTS) } catch (_: Exception) {}
    }

    private fun view(tag: Long): PNCameraView =
        PNBridge.registry.get(tag)?.view as? PNCameraView ?: throw PNModuleError("No CameraView with tag $tag is mounted", "not_ready")

    /** Run [work] against the view, reporting anything CameraX throws with a code Python can read. */
    private fun <T> withView(tag: Long, completion: (Result<T>) -> Unit, work: PNCameraView.() -> Unit): (() -> Unit)? {
        try {
            view(tag).work()
        } catch (error: PNModuleError) {
            completion(Result.failure(error))
        } catch (error: Exception) {
            completion(Result.failure(PNModuleError(error.message ?: error.javaClass.simpleName, "capture_failed")))
        }
        return null
    }

    override fun take_picture(quality: Double, tag: Long, completion: (Result<PNPhoto>) -> Unit): (() -> Unit)? =
        withView(tag, completion) { takePicture((quality.coerceIn(0.0, 1.0) * 100).toInt(), completion) }

    override fun start_recording(audio: Boolean, tag: Long, completion: (Result<Unit>) -> Unit): (() -> Unit)? =
        withView(tag, completion) { startRecording(audio, completion) }

    override fun stop_recording(tag: Long, completion: (Result<PNVideoRecording>) -> Unit): (() -> Unit)? =
        withView(tag, completion) { stopRecording(completion) }
}

private class CameraViewManager : TypedComponentManager<CameraViewProps>({ values, partial -> CameraViewProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = PNCameraView(context)

    override fun applyTyped(view: View, props: CameraViewProps, initial: Boolean) {
        ViewStyler.apply(view, props.values)
        val camera = view as PNCameraView
        if (initial || props.has_facing) camera.setFacing(props.facing ?: PNCameraViewFacing.`back`)
        if (initial || props.has_flash) camera.setFlash(props.flash ?: PNCameraViewFlash.`off`)
        if (initial || props.has_zoom) camera.setZoom(props.zoom ?: 1.0)
        if (initial || props.has_barcode_types) camera.setBarcodeTypes(props.barcode_types ?: emptyList())
    }

    override fun insertChild(parent: View, child: View, index: Int) {
        super.insertChild((parent as PNCameraView).overlay, child, index)
    }

    override fun removeChild(parent: View, child: View) {
        super.removeChild((parent as PNCameraView).overlay, child)
    }

    override fun teardown(view: View) {
        (view as PNCameraView).shutDown()
    }
}

/**
 * A live preview on CameraX, bound to the activity's lifecycle so that it
 * stops and resumes with the app.
 *
 * The video use case binds only while recording, because many devices can't
 * run every use case at once. Barcode scanning (and, where it doesn't fit,
 * pictures) sit out until the recording ends.
 */
private class PNCameraView(context: Context) : FrameLayout(context) {
    val overlay = FrameLayout(context)
    private val preview = PreviewView(context).apply {
        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        scaleType = PreviewView.ScaleType.FILL_CENTER
    }
    private val placeholder = TextView(context).apply {
        setTextColor(Color.WHITE)
        gravity = Gravity.CENTER
        visibility = View.GONE
    }
    private val previewCase = Preview.Builder().build()
    private val imageCapture = ImageCapture.Builder()
        .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
        .setJpegQuality(100)
        .build()
    private val analysisExecutor: ExecutorService by lazy { Executors.newSingleThreadExecutor() }
    private var provider: ProcessCameraProvider? = null
    private var camera: Camera? = null
    private var bound: List<UseCase> = emptyList()
    private var analysis: ImageAnalysis? = null
    private var scanner: BarcodeScanner? = null
    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var recordingFile: File? = null
    private var onStopped: ((Result<PNVideoRecording>) -> Unit)? = null
    private var facing = PNCameraViewFacing.`back`
    private var flash = PNCameraViewFlash.`off`
    private var zoom = 1.0
    private var barcodeTypes: List<PNCameraViewBarcodeTypesItem> = emptyList()
    private val seenBarcodes = HashMap<String, Long>()
    private var ready = false
    private var videoWanted = false
    private var shutDown = false
    private val stateObserver = Observer<CameraState> { state -> cameraStateChanged(state) }

    init {
        setBackgroundColor(Color.BLACK)
        val fill = { LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT) }
        addView(preview, fill())
        addView(placeholder, fill())
        addView(overlay, fill())
        previewCase.setSurfaceProvider(preview.surfaceProvider)
    }

    fun setFacing(value: PNCameraViewFacing) {
        if (value == facing) return
        facing = value
        ready = false
        rebind()
    }

    fun setFlash(value: PNCameraViewFlash) {
        flash = value
        applyCameraSettings()
    }

    fun setZoom(value: Double) {
        zoom = value
        applyCameraSettings()
    }

    fun setBarcodeTypes(value: List<PNCameraViewBarcodeTypesItem>) {
        if (value == barcodeTypes) return
        barcodeTypes = value
        seenBarcodes.clear()
        rebuildAnalysis()
        rebind()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        start()
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        stop()
    }

    private fun start() {
        if (shutDown || !isAttachedToWindow) return
        val permissions = BuiltinModules.permissions
        if (permissions.isGranted(CAMERA)) {
            startProvider()
            return
        }
        permissions.requestManifest(arrayOf(CAMERA)) { results ->
            if (results.any { it == PackageManager.PERMISSION_GRANTED }) {
                startProvider()
            } else {
                fail("permission_denied", "The user refused the camera permission.", "Camera permission denied")
            }
        }
    }

    private fun startProvider() {
        if (shutDown || !isAttachedToWindow) return
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            try {
                provider = future.get()
                rebind()
            } catch (error: Exception) {
                fail("capture_failed", error.message ?: "CameraX couldn't start", "Camera unavailable")
            }
        }, ContextCompat.getMainExecutor(context))
    }

    private fun stop() {
        recording?.stop()
        unbind()
        ready = false
    }

    fun shutDown() {
        shutDown = true
        stop()
        scanner?.close()
        scanner = null
        analysis?.clearAnalyzer()
        analysis = null
        previewCase.setSurfaceProvider(null)
    }

    private fun selector(): CameraSelector =
        if (facing == PNCameraViewFacing.`front`) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA

    private fun unbind() {
        camera?.cameraInfo?.cameraState?.removeObserver(stateObserver)
        camera = null
        if (bound.isNotEmpty()) provider?.unbind(*bound.toTypedArray())
        bound = emptyList()
    }

    /**
     * Bind the widest set of use cases the device accepts. `bindToLifecycle`
     * rejects a combination the hardware can't run with `IllegalArgumentException`.
     */
    private fun rebind() {
        val provider = provider ?: return
        val owner = PNBridge.activity() as? LifecycleOwner
        if (shutDown || !isAttachedToWindow || owner == null) return
        val selector = selector()
        if (!hasCamera(provider, selector)) {
            unbind()
            val side = if (facing == PNCameraViewFacing.`front`) "front" else "back"
            fail("unavailable", "This device has no $side camera.", "Camera unavailable")
            return
        }
        unbind()
        val video = if (videoWanted) videoCapture else null
        val scan = analysis
        // Scanning pauses while recording: few devices can run all four, and the
        // ones that can't don't always fail cleanly.
        val combinations = if (video != null) {
            listOf(listOf(previewCase, imageCapture, video), listOf(previewCase, video))
        } else {
            listOfNotNull(listOfNotNull(previewCase, imageCapture, scan), if (scan != null) listOf(previewCase, imageCapture) else null)
        }
        for (cases in combinations) {
            try {
                camera = provider.bindToLifecycle(owner, selector, *cases.toTypedArray())
                bound = cases
                placeholder.visibility = View.GONE
                camera?.cameraInfo?.cameraState?.observe(owner, stateObserver)
                applyCameraSettings()
                return
            } catch (error: IllegalArgumentException) {
                PNLog.swallowed("CameraView.bind", error)
            }
        }
        fail("capture_failed", "This device can't run the camera with these settings.", "Camera unavailable")
    }

    private fun hasCamera(provider: ProcessCameraProvider, selector: CameraSelector): Boolean = try {
        provider.hasCamera(selector)
    } catch (_: Exception) {
        false
    }

    private fun cameraStateChanged(state: CameraState) {
        state.error?.let { error ->
            if (error.type == CameraState.ErrorType.CRITICAL) {
                fail("capture_failed", "The camera stopped with error ${error.code}.", "Camera unavailable")
                return
            }
        }
        if (state.type == CameraState.Type.OPEN) {
            applyCameraSettings()
            if (!ready) {
                ready = true
                PNComponentEvents.CameraView.on_ready(this)
            }
        }
    }

    private fun fail(code: String, message: String, label: String) {
        placeholder.text = label
        placeholder.visibility = View.VISIBLE
        PNComponentEvents.CameraView.on_error(this, PNCameraError(code = code, message = message))
    }

    private fun applyCameraSettings() {
        val camera = camera ?: return
        imageCapture.flashMode = when (flash) {
            PNCameraViewFlash.`on` -> ImageCapture.FLASH_MODE_ON
            PNCameraViewFlash.`auto` -> ImageCapture.FLASH_MODE_AUTO
            else -> ImageCapture.FLASH_MODE_OFF
        }
        if (camera.cameraInfo.hasFlashUnit()) camera.cameraControl.enableTorch(flash == PNCameraViewFlash.`torch`)
        // Before the camera opens there's no range to clamp to. Opening applies these again.
        val range = camera.cameraInfo.zoomState.value ?: return
        camera.cameraControl.setZoomRatio(max(range.minZoomRatio, min(zoom.toFloat(), range.maxZoomRatio)))
    }

    // Pictures

    fun takePicture(quality: Int, completion: (Result<PNPhoto>) -> Unit) {
        if (camera == null || imageCapture !in bound) {
            completion(Result.failure(PNModuleError("The camera isn't running", "not_ready")))
            return
        }
        val file = newCaptureFile(context, ".jpg")
        preview.display?.let { imageCapture.targetRotation = it.rotation }
        // A camera HAL that dies mid-capture leaves CameraX waiting until the
        // camera next closes, and the API 31 emulator's back camera does just that.
        val settled = AtomicBoolean(false)
        val timeout = Runnable {
            if (settled.compareAndSet(false, true)) {
                file.delete()
                completion(Result.failure(PNModuleError("The camera didn't deliver the picture in time", "capture_failed")))
            }
        }
        MainThread.postDelayed(timeout, CAPTURE_TIMEOUT_MS)
        imageCapture.takePicture(
            ImageCapture.OutputFileOptions.Builder(file).build(),
            captureExecutor,
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(results: ImageCapture.OutputFileResults) {
                    MainThread.remove(timeout)
                    if (!settled.compareAndSet(false, true)) {
                        file.delete()
                        return
                    }
                    completion(Result.success(photoRecord(finishCapture(context, file, quality))))
                }
                override fun onError(error: ImageCaptureException) {
                    MainThread.remove(timeout)
                    file.delete()
                    if (settled.compareAndSet(false, true)) {
                        completion(Result.failure(PNModuleError(error.message ?: "The picture failed", "capture_failed")))
                    }
                }
            },
        )
    }

    // Video

    fun startRecording(audio: Boolean, completion: (Result<Unit>) -> Unit) {
        if (camera == null) {
            completion(Result.failure(PNModuleError("The camera isn't running", "not_ready")))
            return
        }
        if (recording != null) {
            completion(Result.failure(PNModuleError("This CameraView is already recording", "busy")))
            return
        }
        if (!audio) {
            beginRecording(false, completion)
            return
        }
        BuiltinModules.permissions.requestManifest(arrayOf(RECORD_AUDIO)) { results ->
            if (results.any { it == PackageManager.PERMISSION_GRANTED }) {
                beginRecording(true, completion)
            } else {
                completion(Result.failure(PNModuleError("Microphone permission was denied. Declare microphone under [permissions], or pass audio=False", "permission_denied")))
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun beginRecording(audio: Boolean, completion: (Result<Unit>) -> Unit) {
        val capture = videoCapture ?: VideoCapture.withOutput(
            Recorder.Builder()
                .setQualitySelector(QualitySelector.fromOrderedList(listOf(Quality.FHD, Quality.HD, Quality.SD), FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)))
                .build(),
        ).also { videoCapture = it }
        videoWanted = true
        if (capture !in bound) rebind()
        if (capture !in bound) {
            videoWanted = false
            completion(Result.failure(PNModuleError("This device can't record with these settings", "capture_failed")))
            return
        }
        val file = newCaptureFile(context, ".mp4")
        preview.display?.let { capture.targetRotation = it.rotation }
        var pending = capture.output.prepareRecording(context, FileOutputOptions.Builder(file).build())
        if (audio) pending = pending.withAudioEnabled()
        var started: ((Result<Unit>) -> Unit)? = completion
        recordingFile = file
        recording = pending.start(ContextCompat.getMainExecutor(context)) { event ->
            when (event) {
                is VideoRecordEvent.Start -> {
                    started?.invoke(Result.success(Unit))
                    started = null
                }
                is VideoRecordEvent.Finalize -> {
                    started?.invoke(Result.failure(PNModuleError(event.cause?.message ?: "Recording didn't start", "capture_failed")))
                    started = null
                    recordingFinished(event)
                }
            }
        }
    }

    private fun recordingFinished(event: VideoRecordEvent.Finalize) {
        val file = recordingFile
        val done = onStopped
        recording = null
        recordingFile = null
        onStopped = null
        val saved = file != null && file.length() > 0L && (!event.hasError() || event.error == VideoRecordEvent.Finalize.ERROR_SOURCE_INACTIVE)
        if (saved) {
            done?.invoke(Result.success(PNVideoRecording(duration = event.recordingStats.recordedDurationNanos / 1e9, path = file!!.absolutePath)))
        } else {
            file?.delete()
            done?.invoke(Result.failure(PNModuleError(event.cause?.message ?: "No video was saved (error ${event.error})", "capture_failed")))
        }
        videoWanted = false
        if (!shutDown && isAttachedToWindow) rebind()
    }

    fun stopRecording(completion: (Result<PNVideoRecording>) -> Unit) {
        val active = recording
        if (active == null) {
            completion(Result.failure(PNModuleError("This CameraView isn't recording", "not_recording")))
            return
        }
        onStopped = completion
        active.stop()
    }

    // Barcodes

    private fun rebuildAnalysis() {
        analysis?.clearAnalyzer()
        scanner?.close()
        analysis = null
        scanner = null
        val formats = barcodeTypes.map(::mlkitFormat)
        if (formats.isEmpty()) return
        val options = BarcodeScannerOptions.Builder().setBarcodeFormats(formats.first(), *formats.drop(1).toIntArray()).build()
        val client = BarcodeScanning.getClient(options)
        scanner = client
        analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .also { it.setAnalyzer(analysisExecutor) { image -> scan(client, image) } }
    }

    @OptIn(ExperimentalGetImage::class)
    private fun scan(client: BarcodeScanner, frame: androidx.camera.core.ImageProxy) {
        val image = frame.image
        if (image == null) {
            frame.close()
            return
        }
        client.process(InputImage.fromMediaImage(image, frame.imageInfo.rotationDegrees))
            .addOnSuccessListener { found -> barcodesFound(found) }
            .addOnFailureListener { error -> PNLog.swallowed("CameraView.scan", Exception(error)) }
            .addOnCompleteListener { frame.close() }
    }

    private fun barcodesFound(found: List<Barcode>) {
        val now = android.os.SystemClock.elapsedRealtime()
        for (barcode in found) {
            val type = appFormat(barcode.format) ?: continue
            val text = barcode.rawValue ?: continue
            val key = "${type.rawValue}:$text"
            val last = seenBarcodes[key]
            seenBarcodes[key] = now
            if (last == null || now - last >= BARCODE_REPEAT_MS) {
                PNComponentEvents.CameraView.on_barcode(this, PNBarcode(data = text, type = type))
            }
        }
    }

    private companion object {
        /** How long a barcode must stay out of view before it's reported again. */
        const val BARCODE_REPEAT_MS = 1500L

        const val CAPTURE_TIMEOUT_MS = 30_000L

        fun mlkitFormat(type: PNCameraViewBarcodeTypesItem): Int = when (type) {
            PNCameraViewBarcodeTypesItem.`aztec` -> Barcode.FORMAT_AZTEC
            PNCameraViewBarcodeTypesItem.`codabar` -> Barcode.FORMAT_CODABAR
            PNCameraViewBarcodeTypesItem.`code128` -> Barcode.FORMAT_CODE_128
            PNCameraViewBarcodeTypesItem.`code39` -> Barcode.FORMAT_CODE_39
            PNCameraViewBarcodeTypesItem.`code93` -> Barcode.FORMAT_CODE_93
            PNCameraViewBarcodeTypesItem.`data_matrix` -> Barcode.FORMAT_DATA_MATRIX
            PNCameraViewBarcodeTypesItem.`ean13` -> Barcode.FORMAT_EAN_13
            PNCameraViewBarcodeTypesItem.`ean8` -> Barcode.FORMAT_EAN_8
            PNCameraViewBarcodeTypesItem.`itf14` -> Barcode.FORMAT_ITF
            PNCameraViewBarcodeTypesItem.`pdf417` -> Barcode.FORMAT_PDF417
            PNCameraViewBarcodeTypesItem.`qr` -> Barcode.FORMAT_QR_CODE
            PNCameraViewBarcodeTypesItem.`upc_a` -> Barcode.FORMAT_UPC_A
            PNCameraViewBarcodeTypesItem.`upc_e` -> Barcode.FORMAT_UPC_E
        }

        fun appFormat(format: Int): PNCameraViewBarcodeTypesItem? =
            PNCameraViewBarcodeTypesItem.entries.firstOrNull { mlkitFormat(it) == format }
    }
}
