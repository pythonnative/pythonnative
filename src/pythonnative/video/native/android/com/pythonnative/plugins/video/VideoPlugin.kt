package com.pythonnative.plugins.video

import android.app.Activity
import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.pythonnative.generated.PNComponentEvents
import com.pythonnative.generated.PNVideoInfo
import com.pythonnative.generated.PNVideoResizeMode
import com.pythonnative.generated.VideoProps
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.components.ImageLoader
import com.pythonnative.runtime.components.TypedComponentManager
import com.pythonnative.runtime.modules.PNLifecycleHook
import org.json.JSONObject
import java.io.File
import java.util.Collections
import java.util.WeakHashMap

/** Registers the `Video` component and frees decoders while the app is in the background. */
object VideoPlugin : PNPlugin {
    private val views: MutableSet<PNVideoView> = Collections.newSetFromMap(WeakHashMap())

    override fun register(registry: PNRegistry) {
        registry.registerComponent("Video") { PNVideoManager() }
        registry.registerLifecycleHook(object : PNLifecycleHook {
            override fun onActivityStopped(activity: Activity) {
                if (!activity.isChangingConfigurations) views.toList().forEach { it.suspendPlayer() }
            }

            override fun onActivityResumed(activity: Activity) {
                views.toList().forEach { it.resumePlayer() }
            }
        })
    }

    internal fun track(view: PNVideoView) {
        views.add(view)
    }

    internal fun untrack(view: PNVideoView) {
        views.remove(view)
    }
}

/** `Video`: props go to one [PNVideoView], which owns the player. */
class PNVideoManager : TypedComponentManager<VideoProps>({ values, partial -> VideoProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View =
        PNVideoView(context).also { VideoPlugin.track(it) }

    override fun applyTyped(view: View, props: VideoProps, initial: Boolean) {
        super.applyTyped(view, props, initial)
        val video = view as? PNVideoView ?: return
        if (initial || props.has_resize_mode) video.setResizeMode(props.`resize_mode` ?: PNVideoResizeMode.`contain`)
        if (initial || props.has_controls) video.setControls(props.`controls` ?: false)
        if (initial || props.has_autoplay) video.autoplay = props.`autoplay` ?: false
        if (initial || props.has_loop) video.setLooping(props.`loop` ?: false)
        if (initial || props.has_muted) video.setMuted(props.`muted` ?: false)
        if (initial || props.has_volume) video.setVolume(props.`volume` ?: 1.0)
        if (initial || props.has_rate) video.setRate(props.`rate` ?: 1.0)
        if (initial || props.has_progress_interval) video.progressInterval = props.`progress_interval` ?: 0.25
        if (initial || props.has_poster) video.setPoster(props.`poster`)
        if (initial || props.has_source) video.setSource(props.`source`)
    }

    override fun command(view: View, name: String, args: JSONObject): Any? {
        val video = view as? PNVideoView ?: return null
        return when (name) {
            "play" -> { video.play(); null }
            "pause" -> { video.pause(); null }
            "seek" -> { video.seek(args.optDouble("seconds", 0.0)); null }
            "position" -> video.position()
            else -> super.command(view, name, args)
        }
    }

    override fun teardown(view: View) {
        val video = view as? PNVideoView ?: return
        VideoPlugin.untrack(video)
        video.releasePlayer()
    }
}

/**
 * A Media3 `ExoPlayer` shown through a `PlayerView`. The player is released,
 * not just paused, when the activity stops, since a device has few hardware
 * decoders; [resumePlayer] rebuilds it where it left off.
 */
@OptIn(UnstableApi::class)
class PNVideoView(context: Context) : FrameLayout(context) {
    var autoplay = false
    var progressInterval = 0.25

    private val playerView = PlayerView(context)
    private val posterView = ImageView(context)
    private val handler = Handler(Looper.getMainLooper())
    private var player: ExoPlayer? = null
    private var item: MediaItem? = null
    private var looping = false
    private var muted = false
    private var volume = 1f
    private var rate = 1f
    private var isBuffering = false
    private var didReportReady = false
    private var cancelPoster: (() -> Unit)? = null
    private var resumeAt: Long? = null
    private var resumePlaying = false
    private var released = false

    private val progressTick = object : Runnable {
        override fun run() {
            val active = player ?: return
            if (!active.isPlaying) return
            reportProgress()
            handler.postDelayed(this, (progressInterval * 1000).toLong().coerceAtLeast(16L))
        }
    }

    private val listener = object : Player.Listener {
        override fun onPlaybackStateChanged(state: Int) {
            val active = player ?: return
            setBuffering(state == Player.STATE_BUFFERING)
            if (state == Player.STATE_READY && !didReportReady) {
                didReportReady = true
                PNComponentEvents.Video.`on_ready`(this@PNVideoView, info(active))
            }
            if (state == Player.STATE_ENDED) {
                reportProgress()
                PNComponentEvents.Video.`on_end`(this@PNVideoView)
            }
        }

        override fun onIsPlayingChanged(isPlaying: Boolean) {
            handler.removeCallbacks(progressTick)
            if (isPlaying) {
                posterView.visibility = View.GONE
                progressTick.run()
            }
        }

        override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
            if (reason == Player.DISCONTINUITY_REASON_SEEK) reportProgress()
        }

        override fun onPlayerError(error: PlaybackException) {
            setBuffering(false)
            PNComponentEvents.Video.`on_error`(this@PNVideoView, error.message ?: error.errorCodeName)
        }
    }

    init {
        addView(playerView, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        addView(posterView, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        posterView.visibility = View.GONE
        playerView.useController = false
        playerView.setShutterBackgroundColor(android.graphics.Color.TRANSPARENT)
        clipChildren = true
    }

    private fun info(active: ExoPlayer): PNVideoInfo {
        val format = active.videoFormat
        var width = format?.width ?: 0
        var height = format?.height ?: 0
        if (format != null && format.rotationDegrees % 180 != 0) {
            val swap = width
            width = height
            height = swap
        }
        return PNVideoInfo(duration = seconds(active.duration), width = width.coerceAtLeast(0).toDouble(), height = height.coerceAtLeast(0).toDouble())
    }

    private fun reportProgress() {
        val active = player ?: return
        PNComponentEvents.Video.`on_progress`(this, active.currentPosition / 1000.0, seconds(active.duration))
    }

    private fun seconds(millis: Long): Double = if (millis == C.TIME_UNSET) 0.0 else millis / 1000.0

    private fun setBuffering(buffering: Boolean) {
        if (buffering == isBuffering) return
        isBuffering = buffering
        PNComponentEvents.Video.`on_buffering`(this, buffering)
    }

    private fun ensurePlayer(): ExoPlayer = player ?: ExoPlayer.Builder(context).build().also { built ->
        built.setAudioAttributes(
            AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(),
            !muted,
        )
        built.repeatMode = if (looping) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
        built.volume = if (muted) 0f else volume
        built.playbackParameters = PlaybackParameters(rate)
        built.addListener(listener)
        playerView.player = built
        player = built
    }

    fun setControls(enabled: Boolean) {
        playerView.useController = enabled
    }

    fun setResizeMode(mode: PNVideoResizeMode) {
        when (mode) {
            PNVideoResizeMode.`contain` -> {
                playerView.resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                posterView.scaleType = ImageView.ScaleType.FIT_CENTER
            }
            PNVideoResizeMode.`cover` -> {
                playerView.resizeMode = AspectRatioFrameLayout.RESIZE_MODE_ZOOM
                posterView.scaleType = ImageView.ScaleType.CENTER_CROP
            }
            PNVideoResizeMode.`stretch` -> {
                playerView.resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FILL
                posterView.scaleType = ImageView.ScaleType.FIT_XY
            }
        }
    }

    fun setLooping(enabled: Boolean) {
        looping = enabled
        player?.repeatMode = if (enabled) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
    }

    fun setMuted(enabled: Boolean) {
        muted = enabled
        player?.volume = if (enabled) 0f else volume
    }

    fun setVolume(value: Double) {
        volume = value.coerceIn(0.0, 1.0).toFloat()
        if (!muted) player?.volume = volume
    }

    fun setRate(value: Double) {
        rate = value.coerceAtLeast(0.01).toFloat()
        player?.playbackParameters = PlaybackParameters(rate)
    }

    fun setSource(source: String?) {
        didReportReady = false
        resumeAt = null
        if (source.isNullOrEmpty()) {
            item = null
            player?.clearMediaItems()
            return
        }
        val uri = uriFor(source)
        if (uri == null) {
            item = null
            player?.clearMediaItems()
            // The view may not be registered yet during its initial props.
            post { PNComponentEvents.Video.`on_error`(this, "Can't find video source: $source") }
            return
        }
        posterView.visibility = if (posterView.drawable != null) View.VISIBLE else View.GONE
        val next = MediaItem.fromUri(uri)
        item = next
        val active = ensurePlayer()
        active.setMediaItem(next)
        active.playWhenReady = autoplay
        active.prepare()
    }

    fun setPoster(source: String?) {
        cancelPoster?.invoke()
        cancelPoster = null
        posterView.setImageDrawable(null)
        posterView.visibility = View.GONE
        if (source.isNullOrEmpty()) return
        val metrics = resources.displayMetrics
        val callback = ImageLoader.Callback { bitmap: Bitmap?, error: String? ->
            if (bitmap != null) {
                posterView.setImageBitmap(bitmap)
                if (player?.isPlaying != true) posterView.visibility = View.VISIBLE
            } else if (error != null) {
                PNLog.swallowed("Video.poster", RuntimeException(error))
            }
        }
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        cancelPoster = when {
            source.startsWith("http://") || source.startsWith("https://") -> ImageLoader.loadRemote(context, source, width, height, callback)
            source.startsWith("/") || source.startsWith("file://") -> ImageLoader.loadFile(source.removePrefix("file://"), width, height, callback)
            else -> PNAssets.resolve(source)?.let { ImageLoader.loadAsset(it, width, height, callback) }
        }
    }

    /** A URL, a file path, an `asset://` URI, or a path under `app/assets/`. */
    private fun uriFor(source: String): Uri? {
        if (source.startsWith("http://") || source.startsWith("https://") || source.startsWith("file://") || source.startsWith("content://")) {
            return Uri.parse(source)
        }
        if (source.startsWith("/")) return Uri.fromFile(File(source))
        val resolved = PNAssets.resolve(source) ?: return null
        return resolved.file?.let { Uri.fromFile(it) } ?: Uri.parse("asset:///${PNAssets.BUNDLE_ROOT}/${resolved.path}")
    }

    fun play() {
        val active = player ?: return
        if (active.playbackState == Player.STATE_ENDED) active.seekTo(0)
        posterView.visibility = View.GONE
        active.play()
    }

    fun pause() {
        player?.pause()
    }

    fun seek(seconds: Double) {
        posterView.visibility = View.GONE
        player?.seekTo((seconds.coerceAtLeast(0.0) * 1000).toLong())
    }

    fun position(): Double = (player?.currentPosition ?: resumeAt ?: 0L) / 1000.0

    fun suspendPlayer() {
        val active = player ?: return
        if (item != null) {
            resumeAt = active.currentPosition
            resumePlaying = active.playWhenReady
        }
        handler.removeCallbacks(progressTick)
        playerView.player = null
        active.removeListener(listener)
        active.release()
        player = null
    }

    fun resumePlayer() {
        val at = resumeAt ?: return
        val media = item ?: return
        if (released || player != null) return
        resumeAt = null
        val active = ensurePlayer()
        active.setMediaItem(media, at)
        active.playWhenReady = resumePlaying
        active.prepare()
    }

    /** Stop for good: the view is unmounting. */
    fun releasePlayer() {
        released = true
        cancelPoster?.invoke()
        cancelPoster = null
        item = null
        resumeAt = null
        handler.removeCallbacks(progressTick)
        playerView.player = null
        player?.removeListener(listener)
        player?.release()
        player = null
    }
}
