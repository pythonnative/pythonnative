package com.pythonnative.plugins.audio

import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaMetadataRetriever
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.pythonnative.generated.AudioImplementation
import com.pythonnative.generated.AudioModuleAdapter
import com.pythonnative.generated.PNAudioSetModeCategory
import com.pythonnative.generated.PNAudioStartRecordingQuality
import com.pythonnative.generated.PNRecording
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.assets.PNAssets
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.BuiltinModules
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNLifecycleHook
import com.pythonnative.runtime.modules.PNModuleError
import com.pythonnative.runtime.modules.PNPermissions
import java.io.File
import java.util.UUID
import kotlin.math.log10

private const val RECORD_AUDIO = "android.permission.RECORD_AUDIO"

/** Registers `Audio` and owns the `microphone` permission. */
object AudioPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        val module = AudioModule()
        registry.registerModule { AudioModuleAdapter(module) }
        registry.registerLifecycleHook(object : PNLifecycleHook {
            override fun onActivityStopped(activity: Activity) {
                if (!activity.isChangingConfigurations) module.pauseSounds()
            }
        })
        PNPermissions.register("microphone", RECORD_AUDIO)
    }
}

/** One `Sound`: an `ExoPlayer`, reporting when it first can play and when it ends. */
private class PNSound(
    context: Context,
    uri: Uri,
    attributes: AudioAttributes,
    handleFocus: Boolean,
    private val onLoaded: (Throwable?) -> Unit,
    private val onEnded: () -> Unit,
) : Player.Listener {
    private val player: ExoPlayer = ExoPlayer.Builder(context).build()
    private var loaded = false

    init {
        player.setAudioAttributes(attributes, handleFocus)
        player.addListener(this)
        player.setMediaItem(MediaItem.fromUri(uri))
        player.prepare()
    }

    val position: Double get() = player.currentPosition / 1000.0
    val duration: Double get() = if (player.duration == C.TIME_UNSET) 0.0 else player.duration / 1000.0

    override fun onPlaybackStateChanged(state: Int) {
        if (state == Player.STATE_READY && !loaded) {
            loaded = true
            onLoaded(null)
        }
        if (state == Player.STATE_ENDED) {
            // Rewinds so `play()` plays it again, as `AVAudioPlayer` does.
            player.playWhenReady = false
            player.seekTo(0)
            onEnded()
        }
    }

    override fun onPlayerError(error: PlaybackException) {
        if (!loaded) {
            loaded = true
            onLoaded(PNModuleError(error.message ?: error.errorCodeName, "load_failed"))
        } else {
            PNLog.swallowed("Sound", error)
        }
    }

    fun play() = player.play()
    fun pause() = player.pause()
    fun seek(seconds: Double) = player.seekTo((seconds.coerceAtLeast(0.0) * 1000).toLong())

    fun setVolume(volume: Double) {
        player.volume = volume.coerceIn(0.0, 1.0).toFloat()
    }

    fun setRate(rate: Double) {
        player.playbackParameters = PlaybackParameters(rate.coerceAtLeast(0.01).toFloat())
    }

    fun setLooping(looping: Boolean) {
        player.repeatMode = if (looping) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
    }

    fun setFocus(attributes: AudioAttributes, handleFocus: Boolean) = player.setAudioAttributes(attributes, handleFocus)

    fun release() {
        player.removeListener(this)
        player.release()
    }
}

/** One `MediaRecorder`, with its own clock since the recorder doesn't expose one. */
private class PNAudioRecording(context: Context, path: String?, quality: PNAudioStartRecordingQuality) {
    private val file = fileFor(context, path)
    private val recorder: MediaRecorder = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
    private var elapsedMs = 0L
    private var resumedAt = 0L

    init {
        val (sampleRate, bitRate) = when (quality) {
            PNAudioStartRecordingQuality.`low` -> 16_000 to 32_000
            PNAudioStartRecordingQuality.`medium` -> 22_050 to 64_000
            PNAudioStartRecordingQuality.`high` -> 44_100 to 128_000
        }
        try {
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            recorder.setAudioChannels(1)
            recorder.setAudioSamplingRate(sampleRate)
            recorder.setAudioEncodingBitRate(bitRate)
            recorder.setOutputFile(file.path)
            recorder.prepare()
            recorder.start()
            resumedAt = SystemClock.elapsedRealtime()
        } catch (error: Exception) {
            recorder.release()
            throw PNModuleError(error.message ?: "The recorder wouldn't start", "recording_failed")
        }
    }

    fun pause() {
        if (resumedAt == 0L) return
        recorder.pause()
        elapsedMs += SystemClock.elapsedRealtime() - resumedAt
        resumedAt = 0L
    }

    fun resume() {
        if (resumedAt != 0L) return
        recorder.resume()
        resumedAt = SystemClock.elapsedRealtime()
    }

    /** The peak since the last call, as decibels relative to full scale. */
    fun metering(): Double {
        val amplitude = recorder.maxAmplitude
        return if (amplitude <= 0) -160.0 else (20 * log10(amplitude / 32767.0)).coerceAtLeast(-160.0)
    }

    fun stop(): PNRecording {
        if (resumedAt != 0L) elapsedMs += SystemClock.elapsedRealtime() - resumedAt
        try {
            recorder.stop()
        } catch (error: RuntimeException) {
            // `stop` throws when no audio arrived, and the file is then unusable.
            file.delete()
            throw PNModuleError("No audio was captured", "recording_failed")
        } finally {
            recorder.release()
        }
        if (file.length() == 0L) throw PNModuleError("No audio was captured", "recording_failed")
        return PNRecording(path = file.path, duration = measured() ?: (elapsedMs / 1000.0))
    }

    /** The finished file's own length is more exact than the clock. */
    private fun measured(): Double? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(file.path)
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()?.let { it / 1000.0 }
        } catch (error: Exception) {
            PNLog.swallowed("Recorder.duration", error)
            null
        } finally {
            retriever.release()
        }
    }

    private companion object {
        /** `null` is a new file in the cache directory, and a relative path is under it. */
        fun fileFor(context: Context, path: String?): File {
            val file = when {
                path.isNullOrEmpty() -> File(context.cacheDir, "pn-recordings/${UUID.randomUUID()}.m4a")
                path.startsWith("file://") -> File(path.removePrefix("file://"))
                path.startsWith("/") -> File(path)
                else -> File(context.cacheDir, path)
            }
            file.parentFile?.mkdirs()
            return file
        }
    }
}

/** `Audio`: `Sound` and `Recorder`, addressed by id, plus how sounds take audio focus. */
class AudioModule : AudioImplementation {
    private val sounds = HashMap<Long, PNSound>()
    private val recordings = HashMap<Long, PNAudioRecording>()
    private var nextId = 1L
    private var attributes = attributes(duck = false)
    private var handleFocus = true

    private fun attributes(duck: Boolean): AudioAttributes =
        // ExoPlayer maps the sonification usage to a focus request that lets others keep playing, lowered.
        AudioAttributes.Builder()
            .setUsage(if (duck) C.USAGE_ASSISTANCE_SONIFICATION else C.USAGE_MEDIA)
            .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
            .build()

    internal fun pauseSounds() = sounds.values.forEach { it.pause() }

    private fun sound(id: Long): PNSound = sounds[id] ?: throw PNModuleError("No loaded sound $id", "not_found")

    private fun recording(id: Long): PNAudioRecording =
        recordings[id] ?: throw PNModuleError("No active recording $id", "not_found")

    /** A URL, a file path, an `asset://` URI, or a path under `app/assets/`. */
    private fun uriFor(source: String): Uri? {
        if (source.startsWith("http://") || source.startsWith("https://") || source.startsWith("file://") || source.startsWith("content://")) {
            return Uri.parse(source)
        }
        if (source.startsWith("/")) return Uri.fromFile(File(source))
        val resolved = PNAssets.resolve(source) ?: return null
        return resolved.file?.let { Uri.fromFile(it) } ?: Uri.parse("asset:///${PNAssets.BUNDLE_ROOT}/${resolved.path}")
    }

    override fun load_sound(looping: Boolean, rate: Double, source: String, volume: Double, completion: (Result<Long>) -> Unit): (() -> Unit)? {
        val uri = uriFor(source)
        if (uri == null) {
            completion(Result.failure(PNModuleError("Can't find sound source: $source", "load_failed")))
            return null
        }
        val id = nextId++
        var sound: PNSound? = null
        sound = PNSound(
            PNBridge.context(),
            uri,
            attributes,
            handleFocus,
            onLoaded = { error ->
                if (error == null) {
                    sounds[id] = sound!!
                    completion(Result.success(id))
                } else {
                    sound?.release()
                    completion(Result.failure(error))
                }
            },
            onEnded = { ModuleEvents.emit("Audio", "sound_ended", mapOf("id" to id)) },
        )
        sound.setVolume(volume)
        sound.setRate(rate)
        sound.setLooping(looping)
        return { sound.release() }
    }

    override fun play_sound(id: Long) = sound(id).play()
    override fun pause_sound(id: Long) = sound(id).pause()

    override fun stop_sound(id: Long) {
        val active = sound(id)
        active.pause()
        active.seek(0.0)
    }

    override fun seek_sound(id: Long, seconds: Double) = sound(id).seek(seconds)
    override fun set_sound_volume(id: Long, volume: Double) = sound(id).setVolume(volume)
    override fun set_sound_rate(id: Long, rate: Double) = sound(id).setRate(rate)
    override fun set_sound_looping(id: Long, looping: Boolean) = sound(id).setLooping(looping)
    override fun sound_position(id: Long): Double = sound(id).position
    override fun sound_duration(id: Long): Double = sound(id).duration

    override fun unload_sound(id: Long) {
        sounds.remove(id)?.release()
    }

    private fun manifestDeclaresMicrophone(context: Context): Boolean {
        @Suppress("DEPRECATION")
        val info = context.packageManager.getPackageInfo(context.packageName, PackageManager.GET_PERMISSIONS)
        return info.requestedPermissions?.contains(RECORD_AUDIO) == true
    }

    override fun start_recording(path: String?, quality: PNAudioStartRecordingQuality, completion: (Result<Long>) -> Unit): (() -> Unit)? {
        val context = PNBridge.context()
        if (!manifestDeclaresMicrophone(context)) {
            completion(Result.failure(PNModuleError("Recording needs a microphone usage string. Add microphone = \"...\" under [permissions] in pythonnative.toml and rebuild.", "missing_usage_string")))
            return null
        }
        if (recordings.isNotEmpty()) {
            completion(Result.failure(PNModuleError("A recording is already running", "recording_failed")))
            return null
        }
        val begin = {
            completion(runCatching {
                val id = nextId++
                recordings[id] = PNAudioRecording(context, path, quality)
                id
            })
        }
        val permissions = BuiltinModules.permissions
        if (permissions.isGranted(RECORD_AUDIO)) {
            begin()
            return null
        }
        return permissions.requestManifest(arrayOf(RECORD_AUDIO)) { results ->
            if (results.any { it == PackageManager.PERMISSION_GRANTED }) begin()
            else completion(Result.failure(PNModuleError("Microphone permission was denied", "permission_denied")))
        }
    }

    override fun pause_recording(id: Long) = recording(id).pause()
    override fun resume_recording(id: Long) = recording(id).resume()
    override fun recording_metering(id: Long): Double = recording(id).metering()

    override fun stop_recording(id: Long, completion: (Result<PNRecording>) -> Unit): (() -> Unit)? {
        completion(runCatching {
            val active = recording(id)
            recordings.remove(id)
            active.stop()
        })
        return null
    }

    override fun set_mode(allow_bluetooth: Boolean, category: PNAudioSetModeCategory, default_to_speaker: Boolean, duck_others: Boolean, mix_with_others: Boolean) {
        attributes = attributes(duck_others)
        handleFocus = !mix_with_others
        sounds.values.forEach { it.setFocus(attributes, handleFocus) }
    }
}
