package com.pythonnative.runtime

import android.app.Dialog
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.view.animation.Interpolator
import android.widget.FrameLayout
import android.widget.TextView
import androidx.fragment.app.FragmentActivity
import androidx.recyclerview.widget.RecyclerView
import com.pythonnative.runtime.animation.MotionTiming
import com.pythonnative.runtime.animation.PNItemAnimator
import com.pythonnative.runtime.components.SharedElementFlight
import com.pythonnative.runtime.mount.MotionWrite
import com.pythonnative.runtime.mount.MountOp
import com.pythonnative.runtime.mount.Mounter
import com.pythonnative.runtime.views.PNFrameLayout
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** RFC 0009 on Android: motion writes, exits, shared-element flights, and list item animations. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MotionRobolectricTest {
    private lateinit var activity: FragmentActivity
    private lateinit var applier: Mounter
    private val finished = ArrayList<Long>()

    @Before fun start() {
        activity = Robolectric.buildActivity(FragmentActivity::class.java).setup().get()
        PNBridge.setContext(activity)
        applier = Mounter(PNBridge.registry) { finished.add(it) }
    }

    @After fun stop() {
        for (record in PNBridge.registry.all()) applier.applyOp(MountOp.Delete(record.tag))
        PNBridge.clearContext(activity)
        activity.finish()
    }

    private fun idle() = shadowOf(Looper.getMainLooper()).idle()

    private fun view(tag: Long): View = PNBridge.registry.get(tag)!!.view

    /** A root View attached to the activity with `children` inserted in order. */
    private fun tree(root: Long, vararg children: Long): ViewGroup {
        applier.applyOp(MountOp.Create(root, "View", JSONObject()))
        for ((index, child) in children.withIndex()) {
            applier.applyOp(MountOp.Create(child, "View", JSONObject().put("background_color", "#ff0000")))
            applier.applyOp(MountOp.Insert(root, child, index))
        }
        val group = view(root) as ViewGroup
        activity.setContentView(group)
        return group
    }

    // -- writes -------------------------------------------------------------

    @Test fun propWritesGoThroughTheStaticPathAndNullResets() {
        applier.applyOp(MountOp.Create(1, "View", JSONObject().put("opacity", 0.5).put("background_color", "#ff0000")))
        applier.applyOp(MountOp.Create(2, "Text", JSONObject().put("text", "hi").put("color", "#000000")))
        applier.applyWrites(listOf(
            MotionWrite.Prop(1, "opacity", 0.25),
            MotionWrite.Prop(1, "background_color", "#FF00FF00"),
            MotionWrite.Prop(2, "color", "#FF0000FF"),
        ))
        assertEquals(0.25f, view(1).alpha, 0f)
        val drawable = view(1).background as android.graphics.drawable.GradientDrawable
        assertEquals(0xFF00FF00.toInt(), drawable.color!!.defaultColor)
        assertEquals(0xFF0000FF.toInt(), (view(2) as TextView).currentTextColor)
        // The static props stay recorded; a motion value only overrides them on the view.
        assertEquals("#ff0000", PNBridge.registry.get(1)!!.props.getString("background_color"))
        applier.applyWrites(listOf(MotionWrite.Prop(1, "opacity", null)))
        assertEquals(1f, view(1).alpha, 0f)
        // Writes to unknown tags are ignored.
        applier.applyWrites(listOf(MotionWrite.Prop(99, "opacity", 0.1)))
    }

    @Test fun transformWritesReplaceTheStaticTransform() {
        val static = JSONArray().put(JSONObject().put("translate_x", 10)).put(JSONObject().put("rotate", "45deg"))
        applier.applyOp(MountOp.Create(1, "View", JSONObject().put("transform", static)))
        val v = view(1)
        assertEquals(10 * PNBridge.density(), v.translationX, 0.01f)
        assertEquals(45f, v.rotation, 0f)
        applier.applyWrites(listOf(MotionWrite.Prop(1, "transform", JSONArray().put(JSONObject().put("scale", 2)))))
        assertEquals("unnamed channels return to identity", 0f, v.translationX, 0f)
        assertEquals(0f, v.rotation, 0f)
        assertEquals(2f, v.scaleX, 0f)
        applier.applyWrites(listOf(MotionWrite.Prop(1, "transform", static)))
        assertEquals(10 * PNBridge.density(), v.translationX, 0.01f)
        assertEquals(1f, v.scaleX, 0f)
        applier.applyWrites(listOf(MotionWrite.Prop(1, "transform", null)))
        assertEquals(0f, v.translationX, 0f)
        assertEquals(0f, v.rotation, 0f)
    }

    @Test fun frameWritesUseTheFramePath() {
        tree(1, 2)
        applier.applyWrites(listOf(MotionWrite.Frame(2, 5.0, 6.0, 70.0, 80.0)))
        val params = view(2).layoutParams as ViewGroup.MarginLayoutParams
        val density = PNBridge.density()
        assertEquals(Math.round(5 * density), params.leftMargin)
        assertEquals(Math.round(80 * density), params.height)
        assertEquals(listOf(5.0, 6.0, 70.0, 80.0), PNBridge.registry.get(2)!!.frame!!.toList())
    }

    // -- exits ----------------------------------------------------------------

    @Test fun coreOwnedExitsStayInPlaceWithoutTouchesUntilRemoved() {
        val root = tree(1, 2, 3)
        applier.applyOp(MountOp.Create(4, "View", JSONObject().put("background_color", "#00ff00")))
        applier.applyOp(MountOp.Insert(2, 4, 0))
        val exiting = view(2)
        applier.applyOp(MountOp.Exit(2, 0))
        assertTrue(applier.isExiting(2))
        assertSame(root, exiting.parent)
        assertEquals(0, root.indexOfChild(exiting))
        assertEquals("none", (exiting as PNFrameLayout).getPointerEventsMode())
        assertNotNull("the subtree stays mounted", PNBridge.registry.get(4))
        // The core's index 0 counts only children that aren't exiting, so it lands after view 2.
        applier.applyOp(MountOp.Create(5, "View", JSONObject().put("background_color", "#0000ff")))
        applier.applyOp(MountOp.Insert(1, 5, 0))
        assertEquals(listOf(2L, 5L, 3L), PNBridge.registry.get(1)!!.children)
        assertEquals(listOf(exiting, view(5), view(3)), (0 until root.childCount).map { root.getChildAt(it) })
        // Index 2 (past every live child) appends.
        applier.applyOp(MountOp.Create(6, "View", JSONObject().put("background_color", "#0000ff")))
        applier.applyOp(MountOp.Insert(1, 6, 2))
        assertEquals(listOf(2L, 5L, 3L, 6L), PNBridge.registry.get(1)!!.children)
        // The core keeps animating the exiting view.
        applier.applyWrites(listOf(MotionWrite.Prop(2, "opacity", 0.3)))
        assertEquals(0.3f, exiting.alpha, 0f)
        applier.applyWrites(listOf(MotionWrite.Remove(listOf(4, 2, 77))))
        assertNull(PNBridge.registry.get(4))
        assertNull(PNBridge.registry.get(2))
        assertNull(exiting.parent)
        assertEquals(listOf(5L, 3L, 6L), PNBridge.registry.get(1)!!.children)
        assertTrue(finished.isEmpty())
    }

    @Test fun modalExitsDismissBeforeTheirChildrenAreDestroyed() {
        tree(1)
        applier.applyOp(MountOp.Create(2, "Modal", JSONObject().put("visible", true)))
        applier.applyOp(MountOp.Insert(1, 2, 0))
        applier.applyOp(MountOp.Create(3, "Text", JSONObject().put("text", "inside")))
        applier.applyOp(MountOp.Insert(2, 3, 0))
        val record = PNBridge.registry.get(2)!!
        val dialog = record.state["dialog"] as Dialog
        val content = record.state["content_view"] as FrameLayout
        applier.applyOp(MountOp.Exit(2, 1))
        assertFalse(dialog.isShowing)
        assertSame("the content stays through the dismissal", content, view(3).parent)
        assertNotNull(PNBridge.registry.get(3))
        assertTrue(PNBridge.registry.get(1)!!.children.isEmpty())
        assertTrue(finished.isEmpty())
        idle()
        assertEquals(listOf(2L), finished)
        applier.applyWrites(listOf(MotionWrite.Remove(listOf(3, 2))))
        assertNull(PNBridge.registry.get(3))
        assertNull(PNBridge.registry.get(2))
    }

    @Test fun hostOwnedExitOfAnUnknownViewStillFinishes() {
        applier.applyOp(MountOp.Exit(42, 1))
        idle()
        assertEquals(listOf(42L), finished)
    }

    private fun stackWithTwoScreens(animation: String): ViewGroup {
        applier.applyOp(MountOp.Create(10, "ScreenStack", JSONObject()))
        for ((index, screen) in listOf(11L, 12L).withIndex()) {
            applier.applyOp(MountOp.Create(screen, "Screen", JSONObject().put("animation", animation)))
            applier.applyOp(MountOp.Insert(10, screen, index))
            applier.applyOp(MountOp.Create(screen * 10, "Text", JSONObject().put("text", "screen $screen")))
            applier.applyOp(MountOp.Insert(screen, screen * 10, 0))
        }
        val stack = view(10) as ViewGroup
        activity.setContentView(stack)
        idle()
        return stack
    }

    @Test fun poppedScreensKeepTheirContentUntilTheFragmentIsGone() {
        stackWithTwoScreens("none")
        val screen = view(12) as ViewGroup
        assertNotNull("the top screen is shown", screen.parent)
        applier.applyOp(MountOp.Exit(12, 1))
        assertSame("the screen keeps its content", view(120), screen.getChildAt(0))
        assertTrue(finished.isEmpty())
        idle()
        assertEquals(listOf(12L), finished)
        assertNull("the fragment's view left the container", screen.parent)
        assertNotNull(PNBridge.registry.get(120))
        applier.applyWrites(listOf(MotionWrite.Remove(listOf(120, 12))))
        assertNull(PNBridge.registry.get(12))
        assertNotNull(view(11).parent)
    }

    @Test fun animatedPopsFinishAfterTheExitAnimation() {
        stackWithTwoScreens("slide_from_right")
        val screen = view(12) as ViewGroup
        applier.applyOp(MountOp.Exit(12, 1))
        shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(1000))
        assertEquals(listOf(12L), finished)
        assertSame(view(120), screen.getChildAt(0))
    }

    // -- shared elements ------------------------------------------------------

    @Test fun flightsLiftTheTargetIntoTheOverlayAndPutItBack() {
        val root = tree(1, 2, 3)
        applier.applyOp(MountOp.Frame(2, 0.0, 0.0, 40.0, 40.0))
        applier.applyOp(MountOp.Frame(3, 50.0, 100.0, 200.0, 120.0))
        idle()
        val source = view(2)
        val target = view(3)
        val host = FrameLayout(activity)
        (root.parent as ViewGroup).addView(host, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        idle()
        val pair = JSONObject().put("name", "photo").put("source", 2).put("target", 3).put("transition", JSONObject.NULL)
            .put("source_style", JSONObject().put("opacity", 0.5)).put("target_style", JSONObject())
        val flight = SharedElementFlight(host, pair, MotionTiming(300, 0, Interpolator { it }))
        assertTrue(flight.start())
        assertEquals(0f, source.alpha, 0f)
        assertNotSame("the target flies outside its parent", root, target.parent)
        assertEquals(source.width, target.width)
        assertEquals(0.5f, target.alpha, 0f)
        flight.end()
        assertSame(root, target.parent)
        assertEquals(1, root.indexOfChild(target))
        assertEquals(1f, source.alpha, 0f)
        assertEquals(1f, target.alpha, 0f)
    }

    @Test fun flightBlendsNumbersAndColors() {
        val radius = SharedElementFlight.blend("border_radius", 8, null)!!
        assertEquals(4.0, radius(0.5f) as Double, 1e-9)
        val opacity = SharedElementFlight.blend("opacity", null, 0.0)!!
        assertEquals(1.0, opacity(0f) as Double, 1e-9)
        val color = SharedElementFlight.blend("background_color", "#FF000000", "#FFFFFFFF")!!
        assertEquals("#FF7F7F7F", color(0.5f))
        assertNull(SharedElementFlight.blend("background_color", null, JSONObject.NULL))
    }

    // -- timing and lists -----------------------------------------------------

    @Test fun timingReadsEasingsAndSprings() {
        val linear = MotionTiming.of(JSONObject().put("duration", 120).put("delay", 30).put("easing", "linear"))
        assertEquals(120L, linear.durationMs)
        assertEquals(30L, linear.delayMs)
        assertEquals(0.25f, linear.interpolator.getInterpolation(0.25f), 1e-6f)
        val bezier = MotionTiming.easing(JSONArray().put(0.42).put(0).put(0.58).put(1))
        assertEquals(0.5f, bezier.getInterpolation(0.5f), 1e-3f)
        assertTrue(bezier.getInterpolation(0.2f) < 0.2f)
        assertEquals(300L, MotionTiming.of(null).durationMs)
        val spring = MotionTiming.of(JSONObject().put("spring", JSONObject().put("duration", 450).put("damping_ratio", 0.5)))
        assertTrue(spring.durationMs in 445L..455L)
        assertEquals(1f, spring.interpolator.getInterpolation(1f), 0f)
        assertTrue("an underdamped spring overshoots", (0..100).any { spring.interpolator.getInterpolation(it / 100f) > 1f })
        val physical = MotionTiming.of(JSONObject().put("spring", JSONObject().put("stiffness", 100).put("damping", 20).put("mass", 1)))
        assertTrue(physical.durationMs in 300L..3000L)
    }

    @Test fun itemAnimatorRunsPresetsAndSettlesRows() {
        val animator = PNItemAnimator()
        val holder = object : RecyclerView.ViewHolder(FrameLayout(activity)) {}
        assertFalse("without a preset a row appears at once", animator.animateAdd(holder))
        animator.entering = JSONObject().put("type", "fade_in").put("duration", 200)
        assertTrue(animator.animateAdd(holder))
        assertEquals(0f, holder.itemView.alpha, 0f)
        assertTrue(animator.isRunning)
        animator.runPendingAnimations()
        animator.endAnimations()
        assertFalse(animator.isRunning)
        assertEquals(1f, holder.itemView.alpha, 0f)
        animator.layout = JSONObject().put("type", "linear")
        assertTrue(animator.animateMove(holder, 0, 0, 0, 50))
        assertEquals(-50f, holder.itemView.translationY, 0f)
        animator.endAnimation(holder)
        assertEquals(0f, holder.itemView.translationY, 0f)
        assertFalse("a row that doesn't move doesn't animate", animator.animateMove(holder, 0, 50, 0, 50))
    }

    @Test fun virtualListInstallsTheItemAnimatorOnlyWithPresets() {
        applier.applyOp(MountOp.Create(30, "VirtualList", JSONObject()))
        val list = view(30)
        val recycler = (list.javaClass.getDeclaredField("recycler").apply { isAccessible = true }.get(list)) as RecyclerView
        assertNull(recycler.itemAnimator)
        applier.applyOp(MountOp.Update(30, JSONObject().put("item_entering", JSONObject().put("type", "fade_in"))))
        assertTrue(recycler.itemAnimator is PNItemAnimator)
        applier.applyOp(MountOp.Update(30, JSONObject().put("item_entering", JSONObject.NULL)))
        assertNull(recycler.itemAnimator)
    }
}
