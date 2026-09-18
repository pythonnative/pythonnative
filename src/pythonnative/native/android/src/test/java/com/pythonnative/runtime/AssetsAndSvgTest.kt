package com.pythonnative.runtime

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.RectF
import com.pythonnative.generated.PNAssetManifest
import com.pythonnative.generated.PNFontFace
import com.pythonnative.generated.PNSvgShape
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.components.BoxBlur
import com.pythonnative.runtime.components.SvgPaint
import com.pythonnative.runtime.components.SvgRenderer
import com.pythonnative.runtime.components.SvgView
import com.pythonnative.runtime.components.TabBarManager
import com.pythonnative.runtime.components.TextStyle
import com.pythonnative.runtime.graphics.SvgPath
import com.pythonnative.runtime.graphics.SvgTransform
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.io.FileOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AssetsAndSvgTest {
    private lateinit var activity: Activity
    private lateinit var root: File

    @Before fun start() {
        activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        PNBridge.setContext(activity)
        root = File.createTempFile("pn-assets", "").apply { delete(); mkdirs() }
    }

    @After fun stop() {
        PNAssets.installBundleForTesting(null, null)
        root.deleteRecursively()
        PNBridge.clearContext(activity)
        activity.finish()
    }

    private fun write(path: String, text: String = "x") {
        val file = File(root, path)
        file.parentFile?.mkdirs()
        file.writeText(text)
    }

    private fun manifest(files: List<String>, variants: Map<String, Map<String, String>> = emptyMap(), fonts: List<PNFontFace> = emptyList()) =
        PNAssetManifest(files, variants, fonts)

    @Test fun uriHelpers() {
        assertTrue(PNAssets.isAssetUri("asset://images/a.png"))
        assertFalse(PNAssets.isAssetUri("https://example.com/a.png"))
        assertFalse(PNAssets.isAssetUri(null))
        assertEquals("images/a.png", PNAssets.pathOf("asset:///images/a.png"))
        assertEquals("images/logo.png", PNAssets.baseName("images/logo@2x.png"))
        assertEquals("images/logo.png", PNAssets.baseName("images/logo@1.5x.png"))
        assertEquals("logo.png", PNAssets.baseName("logo.png"))
        assertEquals("email@work.png", PNAssets.baseName("email@work.png"))
        assertEquals(3f, PNAssets.scaleOf("images/logo@3x.png"))
        assertEquals(1f, PNAssets.scaleOf("images/logo.png"))
    }

    @Test fun resolvesDensityVariantsFromManifest() {
        write("images/logo.png"); write("images/logo@2x.png"); write("images/logo@3x.png")
        PNAssets.installBundleForTesting(root, manifest(listOf("images/logo.png"), mapOf(
            "images/logo.png" to mapOf("1" to "images/logo.png", "2" to "images/logo@2x.png", "3" to "images/logo@3x.png"),
        )))
        assertEquals("images/logo@2x.png", PNAssets.resolve("asset://images/logo.png", 2f)?.path)
        assertEquals(2f, PNAssets.resolve("asset://images/logo.png", 2f)?.scale)
        // No exact match: prefer the next denser variant so we downsample.
        assertEquals("images/logo@3x.png", PNAssets.resolve("images/logo.png", 2.5f)?.path)
        assertEquals("images/logo@3x.png", PNAssets.resolve("images/logo.png", 4f)?.path)
        assertEquals("images/logo.png", PNAssets.resolve("images/logo.png", 1f)?.path)
        assertNull(PNAssets.resolve("images/missing.png"))
        assertTrue(PNAssets.exists("asset://images/logo.png"))
        assertEquals("x", String(PNAssets.read("images/logo.png")))
        assertThrows(java.io.FileNotFoundException::class.java) { PNAssets.read("nope.txt") }
    }

    @Test fun overlayShadowsBundleAndNotifiesListeners() {
        write("data/config.json", "bundle")
        PNAssets.installBundleForTesting(root, null)
        assertEquals("data/config.json", PNAssets.resolve("asset://data/config.json")?.path)

        val overlay = File.createTempFile("pn-overlay", "").apply { delete(); mkdirs() }
        try {
            File(overlay, "data").mkdirs()
            File(overlay, "data/config.json").writeText("overlay")
            File(overlay, "data/extra.json").writeText("new")
            var notified = 0
            val unsubscribe = PNAssets.addListener { notified++ }
            val before = PNAssets.generation
            PNAssets.configure(overlay.path, manifest(listOf("data/config.json", "data/extra.json")))
            org.robolectric.shadows.ShadowLooper.idleMainLooper()
            assertEquals(before + 1, PNAssets.generation)
            assertEquals(1, notified)
            assertEquals("overlay", String(PNAssets.read("data/config.json")))
            assertTrue(PNAssets.exists("data/extra.json"))
            assertNotNull(PNAssets.resolve("data/extra.json")?.file)

            PNAssets.configure(null, null)
            org.robolectric.shadows.ShadowLooper.idleMainLooper()
            assertEquals(2, notified)
            assertEquals("bundle", String(PNAssets.read("data/config.json")))
            assertFalse(PNAssets.exists("data/extra.json"))
            unsubscribe()
            PNAssets.configure(null, null)
            org.robolectric.shadows.ShadowLooper.idleMainLooper()
            assertEquals(2, notified)
        } finally {
            overlay.deleteRecursively()
        }
    }

    @Test fun fontLookupPrefersMatchingStyleThenClosestWeight() {
        assertNull(PNAssets.fontFace("Inter", 400, false))
        val faces = listOf(
            PNFontFace("Inter", 400, false, "Inter-Regular", "fonts/a.ttf"),
            PNFontFace("Inter", 700, false, "Inter-Bold", "fonts/b.ttf"),
            PNFontFace("Inter", 400, true, "Inter-Italic", "fonts/c.ttf"),
        )
        PNAssets.installBundleForTesting(root, manifest(emptyList(), fonts = faces))
        assertEquals("Inter-Regular", PNAssets.fontFace("inter", 400, false)?.postscript_name)
        assertEquals("Inter-Bold", PNAssets.fontFace("Inter", 600, false)?.postscript_name)
        assertEquals("Inter-Italic", PNAssets.fontFace("Inter", 900, true)?.postscript_name)
        assertNull(PNAssets.fontFace("Roboto", 400, false))
        assertEquals(3, PNAssets.fontFaces().size)
        // Bundled families resolve to a typeface (Robolectric fakes the file load); unknown ones fall back.
        assertNotNull(TextStyle.typeface("Inter", "bold", false))
        assertNotNull(TextStyle.typeface("Roboto", null, true))
        assertNotNull(TextStyle.typeface(null, "bold", false))
        assertEquals(700, TextStyle.numericWeight("bold"))
        assertEquals(600, TextStyle.numericWeight("semibold"))
        assertEquals(300, TextStyle.numericWeight(300))
        assertEquals(400, TextStyle.numericWeight(null))
    }

    // ------------------------------------------------------------------
    // SVG
    // ------------------------------------------------------------------

    private fun shape(json: String): PNSvgShape = PNSvgShape.decode(JSONObject(json))

    private fun bounds(path: android.graphics.Path): RectF = RectF().also { path.computeBounds(it, true) }

    @Test fun viewBoxParsing() {
        assertEquals(RectF(0f, 0f, 24f, 24f), SvgView.parseViewBox("0 0 24 24"))
        assertEquals(RectF(-5f, -5f, 5f, 5f), SvgView.parseViewBox("-5,-5, 10 10"))
        assertNull(SvgView.parseViewBox("0 0 24"))
        assertNull(SvgView.parseViewBox("0 0 0 24"))
        assertNull(SvgView.parseViewBox(null))
    }

    @Test fun pathParserHandlesCommandsRelativeMovesAndPackedArcFlags() {
        val box = bounds(SvgPath.parse("M0 0h10v10H0z")!!)
        assertEquals(RectF(0f, 0f, 10f, 10f), box)

        val poly = bounds(SvgPath.parse("m1,1 2 0 0 2 -2 0z l1e1 0")!!)
        assertEquals(1f, poly.left, 0.001f)
        assertEquals(11f, poly.right, 0.001f)

        assertNotNull(SvgPath.parse("M0 0 C 1 1, 2 1, 3 0 S 5 -1, 6 0 Q 7 1 8 0 T 10 0"))

        val packed = bounds(SvgPath.parse("M5 0A5 5 0 10 5 5")!!)
        val spaced = bounds(SvgPath.parse("M5 0A5 5 0 1 0 5 5")!!)
        assertEquals(spaced.width(), packed.width(), 0.01f)
        assertEquals(spaced.height(), packed.height(), 0.01f)
        // Chord of 5 on a radius-5 circle: the large arc spans 5*cos(30) + 5.
        assertEquals(9.33f, packed.width(), 0.05f)
        val lucide = bounds(SvgPath.parse("M21 12a9 9 0 11-6.219-8.56")!!)
        assertTrue(lucide.width() > 10f)

        assertNull(SvgPath.parse(""))
        assertNull(SvgPath.parse("garbage"))
    }

    @Test fun transformParsing() {
        val values = FloatArray(9)
        SvgTransform.parse("translate(10, 20)")!!.getValues(values)
        assertEquals(10f, values[2]); assertEquals(20f, values[5])
        SvgTransform.parse("scale(2)")!!.getValues(values)
        assertEquals(2f, values[0]); assertEquals(2f, values[4])
        val rotated = floatArrayOf(1f, 0f)
        SvgTransform.parse("rotate(90)")!!.mapPoints(rotated)
        assertEquals(0f, rotated[0], 0.0001f); assertEquals(1f, rotated[1], 0.0001f)
        val composed = floatArrayOf(0f, 0f)
        SvgTransform.parse("translate(5 5) rotate(180 1 1)")!!.mapPoints(composed)
        assertEquals(7f, composed[0], 0.0001f); assertEquals(7f, composed[1], 0.0001f)
        SvgTransform.parse("matrix(1 0 0 1 3 4)")!!.getValues(values)
        assertEquals(3f, values[2]); assertEquals(4f, values[5])
        assertNull(SvgTransform.parse("spin(3)"))
    }

    @Test fun geometryForPrimitives() {
        assertEquals(RectF(1f, 2f, 4f, 6f), bounds(SvgRenderer.geometry(shape("""{"kind":"rect","x":1,"y":2,"width":3,"height":4}"""))!!))
        assertEquals(RectF(0f, 0f, 10f, 10f), bounds(SvgRenderer.geometry(shape("""{"kind":"circle","cx":5,"cy":5,"r":5}"""))!!))
        assertEquals(RectF(0f, 0f, 4f, 4f), bounds(SvgRenderer.geometry(shape("""{"kind":"polygon","points":"0,0 4,0 4,4"}"""))!!))
        assertNull(SvgRenderer.geometry(shape("""{"kind":"path","d":""}""")))
        assertNull(SvgRenderer.resolve("none", Color.RED))
        assertEquals(Color.RED, SvgRenderer.resolve("currentColor", Color.RED))
        assertEquals(Color.BLUE, SvgRenderer.resolve("#0000ff", Color.RED))
    }

    @Test fun viewBoxTransformModes() {
        val values = FloatArray(9)
        val box = RectF(0f, 0f, 10f, 10f)
        val bounds = RectF(0f, 0f, 40f, 20f)
        SvgRenderer.viewBoxTransform(box, bounds, "meet").getValues(values)
        assertEquals(2f, values[0]); assertEquals(10f, values[2])
        SvgRenderer.viewBoxTransform(box, bounds, "slice").getValues(values)
        assertEquals(4f, values[0])
        SvgRenderer.viewBoxTransform(box, bounds, "none").getValues(values)
        assertEquals(4f, values[0]); assertEquals(2f, values[4])
    }

    @Test fun rasterizesShapesAndTabIcons() {
        val shapes = listOf(shape("""{"kind":"rect","x":0,"y":0,"width":24,"height":24,"fill":"currentColor"}"""))
        val bitmap = SvgRenderer.bitmap(shapes, RectF(0f, 0f, 24f, 24f), 24f, SvgPaint(), Color.RED, 2f)
        // 24dp at 2x, tagged with the density so it lays out at 24dp.
        assertEquals(48, bitmap.width)
        assertEquals(320, bitmap.density)

        val spec = JSONObject().put("shapes", JSONArray().put(JSONObject("""{"kind":"path","d":"M0 0h24v24H0z"}"""))).put("view_box", "0 0 24 24")
        assertNotNull(TabBarManager.icon(activity, spec))
        assertNull(TabBarManager.icon(activity, null))
        assertNull(TabBarManager.icon(activity, "house"))
        assertNull(TabBarManager.icon(activity, JSONObject().put("uri", "asset://missing.png")))
    }

    @Test fun boxBlurAveragesNeighborsAndReportsChanges() {
        val bitmap = Bitmap.createBitmap(4, 1, Bitmap.Config.ARGB_8888)
        bitmap.setPixel(0, 0, Color.WHITE)
        val first = BoxBlur.apply(bitmap, 1)
        // The white pixel bleeds into its neighbor.
        assertTrue(Color.red(bitmap.getPixel(1, 0)) > 0)
        assertTrue(Color.red(bitmap.getPixel(3, 0)) == 0)
        val second = BoxBlur.apply(bitmap, 1)
        assertNotEquals(first, second)
        assertEquals(second, BoxBlur.apply(bitmap, 0))
    }

    @Test fun decodedBitmapsCarryLogicalDensity() {
        val file = File(root, "big.png")
        val source = Bitmap.createBitmap(200, 100, Bitmap.Config.ARGB_8888)
        FileOutputStream(file).use { source.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val decoded = com.pythonnative.runtime.components.ImageLoader.decodeStream({ file.inputStream() }, 50, 25, 2f)!!
        // Downsampled to cover 50x25 (a 100x50 bitmap) but reported as a 100x50 logical image at 2x.
        assertTrue(decoded.width <= 100)
        val logicalWidth = decoded.width * 160f / decoded.density
        assertEquals(100f, logicalWidth, 1f)
    }
}
