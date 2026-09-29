package com.pythonnative.runtime.modules

import android.util.Base64
import com.pythonnative.generated.AssetsImplementation
import com.pythonnative.generated.ImagesImplementation
import com.pythonnative.generated.PNAssetManifest
import com.pythonnative.generated.PNImageSize
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.components.ImageLoader
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileNotFoundException
import java.io.InputStream
import java.util.concurrent.Executors

/** `Assets`: the bridge face of [PNAssets] (overlay configuration and raw reads). */
class AssetsModule : AssetsImplementation {
    override fun configure(overlay: String?, manifest: PNAssetManifest) {
        PNAssets.configure(overlay, manifest)
    }

    override fun exists(path: String): Boolean = PNAssets.exists(path)

    override fun read(path: String): String? = Base64.encodeToString(PNAssets.read(path), Base64.NO_WRAP)
}

/**
 * `Images`: size lookups, prefetching, and cache control for the shared
 * image pipeline. `get_size` reads only the header of local sources and
 * downloads remote ones into the disk cache first.
 */
class ImagesModule : ImagesImplementation {
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "pn-images").apply { isDaemon = true }
    }

    override fun clear_cache() {
        ImageLoader.clearCache(PNBridge.context())
    }

    override fun get_size(uri: String, completion: (Result<PNImageSize>) -> Unit): (() -> Unit)? {
        if (uri.startsWith("http://") || uri.startsWith("https://")) {
            val context = PNBridge.context()
            return ImageLoader.prefetch(context, uri) { error ->
                val file = ImageLoader.cached(context, uri)
                if (error != null || file == null) {
                    completion(Result.failure(IllegalStateException(error ?: "download failed")))
                } else {
                    executor.submit { completion(measure({ FileInputStream(file) }, 1f)) }
                }
            }
        }
        val future = executor.submit {
            completion(runCatching {
                val (open, scale) = opener(uri)
                measure(open, scale).getOrThrow()
            })
        }
        return { future.cancel(true) }
    }

    override fun prefetch(uri: String, completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        if (uri.startsWith("http://") || uri.startsWith("https://")) {
            return ImageLoader.prefetch(PNBridge.context(), uri) { error ->
                if (error != null) completion(Result.failure(IllegalStateException(error))) else completion(Result.success(true))
            }
        }
        // Local sources are already on the device; report whether they exist.
        completion(runCatching { opener(uri).first().close(); true })
        return null
    }

    private fun measure(open: () -> InputStream, scale: Float): Result<PNImageSize> = runCatching {
        val (width, height) = ImageLoader.pixelSize(open) ?: throw IllegalArgumentException("Could not read image dimensions")
        PNImageSize(width / scale.toDouble(), height / scale.toDouble())
    }

    /** How to open `uri` plus the density scale its pixels were drawn for. */
    private fun opener(uri: String): Pair<() -> InputStream, Float> = when {
        PNAssets.isAssetUri(uri) -> {
            val resolved = PNAssets.resolve(uri) ?: throw FileNotFoundException("asset not found: ${PNAssets.pathOf(uri)}")
            Pair({ resolved.open() }, resolved.scale)
        }
        uri.startsWith("data:") -> {
            val bytes = Base64.decode(uri.substringAfter(',', ""), Base64.DEFAULT)
            Pair({ ByteArrayInputStream(bytes) }, 1f)
        }
        uri.startsWith("content://") -> Pair({
            PNBridge.context().contentResolver.openInputStream(android.net.Uri.parse(uri)) ?: throw FileNotFoundException(uri)
        }, 1f)
        else -> {
            val file = File(uri.removePrefix("file://"))
            if (!file.isFile) throw FileNotFoundException(uri)
            Pair({ FileInputStream(file) }, 1f)
        }
    }
}
