package com.pythonnative.runtime.assets

import android.content.Context
import android.content.res.AssetManager
import android.graphics.Typeface
import com.pythonnative.generated.PNAssetManifest
import com.pythonnative.generated.PNFontFace
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNLog
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileNotFoundException
import java.io.InputStream
import kotlin.math.abs

/**
 * Resolves `asset://` URIs against the bundled `app/assets/` folder of
 * the APK and, while connected to `pn start`, the dev overlay that
 * shadows it.
 *
 * `pn build` writes a `pn_assets.json` manifest next to the staged
 * assets listing every file, the density variants of each base name
 * (`logo@2x.png`), and the parsed font faces. The overlay manifest
 * arrives through the `Assets` module. Resolution looks in the overlay
 * first, then the bundle, and picks the variant closest to the screen
 * density (preferring the next denser one so images are downsampled,
 * not upsampled).
 */
object PNAssets {
    /** The URI scheme Python emits for bundled files. */
    const val SCHEME = "asset://"
    /** Where the builder stages `app/assets/` inside the APK's assets. */
    const val BUNDLE_ROOT = "app/assets"

    /** One resolved file: how to open it and the density it was drawn for. */
    class Resolved(
        val path: String,
        val scale: Float,
        /** Overlay files live on disk; bundled ones only inside the APK. */
        val file: File?,
        private val opener: () -> InputStream,
    ) {
        fun open(): InputStream = opener()
    }

    private class Root(val manifest: PNAssetManifest?, val directory: File?, val assets: AssetManager?) {
        fun exists(path: String): Boolean {
            if (directory != null) return File(directory, path).isFile
            val manager = assets ?: return false
            return try { manager.open("$BUNDLE_ROOT/$path").close(); true } catch (_: Exception) { false }
        }
        fun open(path: String): InputStream {
            if (directory != null) return FileInputStream(File(directory, path))
            return assets?.open("$BUNDLE_ROOT/$path") ?: throw FileNotFoundException(path)
        }
        fun resolved(path: String): Resolved =
            Resolved(path, scaleOf(path), directory?.let { File(it, path) }) { open(path) }
    }

    private val lock = Any()
    private var overlay: Root? = null
    private var bundled: Root? = null
    private var bundledContext: Context? = null
    private val typefaces = HashMap<String, Typeface?>()
    private var faces: List<Pair<PNFontFace, Root>> = emptyList()
    private val listeners = ArrayList<() -> Unit>()
    @Volatile var generation = 0
        private set

    /** Attach the app context so bundled assets can be opened; idempotent. */
    fun attach(context: Context) {
        synchronized(lock) {
            if (bundledContext === context.applicationContext && bundled != null) return
            bundledContext = context.applicationContext
            val assets = context.applicationContext.assets
            bundled = Root(readManifest { assets.open("$BUNDLE_ROOT/pn_assets.json") }, null, assets)
            typefaces.clear()
            rebuildFaces()
        }
    }

    /** Point the resolver at a dev overlay (or clear it with `null`) and notify listeners. */
    fun configure(overlay: String?, manifest: PNAssetManifest?) {
        synchronized(lock) {
            this.overlay = if (overlay.isNullOrEmpty()) null else Root(manifest, File(overlay), null)
            typefaces.clear()
            rebuildFaces()
            generation++
        }
        val snapshot = synchronized(lock) { listeners.toList() }
        MainThread.runOnMain { for (listener in snapshot) listener() }
    }

    /** Register a callback for overlay changes; returns the unsubscribe action. */
    fun addListener(listener: () -> Unit): () -> Unit {
        synchronized(lock) { listeners.add(listener) }
        return { synchronized(lock) { listeners.remove(listener) } }
    }

    /** Whether `value` is an `asset://` URI. */
    fun isAssetUri(value: String?): Boolean = value?.startsWith(SCHEME) == true

    /** The asset path named by a URI (`asset://images/a.png` -> `images/a.png`). */
    fun pathOf(uri: String): String = uri.removePrefix(SCHEME).trimStart('/')

    /** Resolve a path or URI, preferring the overlay and the best density variant. */
    fun resolve(pathOrUri: String, scale: Float = deviceScale()): Resolved? {
        val path = pathOf(pathOrUri)
        for (root in roots()) {
            val manifest = root.manifest
            if (manifest != null) {
                val variant = variant(manifest, path, scale)
                if (variant != null && root.exists(variant)) return root.resolved(variant)
            }
            if (root.exists(path)) return root.resolved(path)
        }
        return null
    }

    /** Whether some copy of `pathOrUri` exists. */
    fun exists(pathOrUri: String): Boolean = resolve(pathOrUri) != null

    /** Read the bytes of an asset (the base file, not a density variant). */
    fun read(pathOrUri: String): ByteArray {
        val path = pathOf(pathOrUri)
        for (root in roots()) {
            if (root.exists(path)) return root.open(path).use { it.readBytes() }
        }
        throw FileNotFoundException("asset not found: $path")
    }

    /** Pick the manifest variant of `path` for `scale`, or null when the manifest has no entry. */
    fun variant(manifest: PNAssetManifest, path: String, scale: Float): String? {
        val base = baseName(path)
        val group = manifest.variants[base]
        if (!group.isNullOrEmpty()) {
            val options = group.mapNotNull { (key, value) -> key.toFloatOrNull()?.let { it to value } }
            options.firstOrNull { abs(it.first - scale) < 0.001f }?.let { return it.second }
            options.filter { it.first > scale }.minByOrNull { it.first }?.let { return it.second }
            return options.maxByOrNull { it.first }?.second
        }
        return if (manifest.files.contains(base)) base else null
    }

    /** `images/logo@2x.png` -> `images/logo.png`. */
    fun baseName(path: String): String {
        val slash = path.lastIndexOf('/')
        val directory = if (slash >= 0) path.substring(0, slash + 1) else ""
        val name = path.substring(slash + 1)
        val dot = name.lastIndexOf('.')
        val stem = if (dot > 0) name.substring(0, dot) else name
        val ext = if (dot > 0) name.substring(dot) else ""
        val at = stem.lastIndexOf('@')
        if (at >= 0 && stem.endsWith("x") && stem.substring(at + 1, stem.length - 1).toFloatOrNull() != null) {
            return directory + stem.substring(0, at) + ext
        }
        return path
    }

    /** The density encoded in a variant name (`@2x` -> 2), or 1. */
    fun scaleOf(path: String): Float {
        val name = path.substringAfterLast('/')
        val stem = name.substringBeforeLast('.', name)
        val at = stem.lastIndexOf('@')
        if (at < 0 || !stem.endsWith("x")) return 1f
        return stem.substring(at + 1, stem.length - 1).toFloatOrNull() ?: 1f
    }

    /** The screen density as an iOS-style scale (`xxhdpi` -> 3). */
    fun deviceScale(): Float {
        val context = bundledContext ?: return 1f
        val density = context.resources.displayMetrics.density
        return if (density > 0f) density else 1f
    }

    // ------------------------------------------------------------------
    // Fonts
    // ------------------------------------------------------------------

    /** Every bundled font face (overlay faces shadow bundle faces of the same family/weight/style). */
    fun fontFaces(): List<PNFontFace> = synchronized(lock) { faces.map { it.first } }

    /** The best face for `family`, or null when the family isn't bundled. */
    fun fontFace(family: String, weight: Int, italic: Boolean): PNFontFace? {
        val wanted = family.trim().lowercase()
        val candidates = synchronized(lock) { faces.filter { it.first.family.lowercase() == wanted } }
        if (candidates.isEmpty()) return null
        return candidates.minByOrNull { (face, _) ->
            (if (face.italic == italic) 0 else 1000) + abs(face.weight.toInt() - weight)
        }?.first
    }

    /**
     * A `Typeface` for the bundled face closest to `family`/`weight`/`italic`,
     * or null when the family isn't bundled (callers fall back to system fonts).
     */
    fun typeface(family: String, weight: Int, italic: Boolean): Typeface? {
        val face = fontFace(family, weight, italic) ?: return null
        val key = "${face.family.lowercase()}|${face.weight}|${face.italic}"
        synchronized(lock) {
            if (typefaces.containsKey(key)) return typefaces[key]
        }
        val root = synchronized(lock) { faces.firstOrNull { it.first === face }?.second }
        val loaded = try {
            when {
                root == null -> null
                root.directory != null -> Typeface.createFromFile(File(root.directory, face.path))
                root.assets != null -> Typeface.createFromAsset(root.assets, "$BUNDLE_ROOT/${face.path}")
                else -> null
            }
        } catch (error: Exception) {
            PNLog.rateLimited("font:${face.path}", "[assets] could not load ${face.path}", error)
            null
        }
        synchronized(lock) { typefaces[key] = loaded }
        return loaded
    }

    private fun rebuildFaces() {
        val merged = ArrayList<Pair<PNFontFace, Root>>()
        val seen = HashSet<String>()
        for (root in listOfNotNull(overlay, bundled)) {
            for (face in root.manifest?.fonts ?: emptyList()) {
                val key = "${face.family.lowercase()}|${face.weight}|${face.italic}"
                if (!seen.add(key)) continue
                merged.add(face to root)
            }
        }
        faces = merged
    }

    // ------------------------------------------------------------------
    // Internals
    // ------------------------------------------------------------------

    private fun roots(): List<Root> = synchronized(lock) { listOfNotNull(overlay, bundled) }

    private fun readManifest(open: () -> InputStream): PNAssetManifest? = try {
        val text = open().use { it.readBytes().toString(Charsets.UTF_8) }
        PNAssetManifest.decode(JSONObject(text))
    } catch (_: Exception) {
        null
    }

    /** Testing hook: install a directory as the bundle root instead of the APK assets. */
    internal fun installBundleForTesting(directory: File?, manifest: PNAssetManifest?) {
        synchronized(lock) {
            bundled = if (directory == null) null else Root(manifest, directory, null)
            overlay = null
            typefaces.clear()
            rebuildFaces()
        }
    }
}
