import AVFoundation
import UIKit

/// Registers `Audio` and owns the `microphone` permission.
public enum AudioPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(AudioModuleAdapter<AudioModule>.self)
        PNPermissions.register("microphone", PNAudioMicrophonePermission())
    }
}

private func microphoneUsageDeclared() -> Bool {
    Bundle.main.object(forInfoDictionaryKey: "NSMicrophoneUsageDescription") != nil
}

private func audioError(_ code: String, _ message: String) -> NSError {
    NSError(domain: code, code: 1, userInfo: [NSLocalizedDescriptionKey: message])
}

private let missingUsageMessage = "Recording needs a microphone usage string. Add microphone = \"...\" under [permissions] in pythonnative.toml and rebuild."

private final class PNAudioMicrophonePermission: PNPermissionProvider {
    private func status(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized: return "granted"
        case .denied, .restricted: return "blocked"
        case .notDetermined: return "undetermined"
        @unknown default: return "undetermined"
        }
    }

    func check(_ done: @escaping (String) -> Void) {
        done(status(AVCaptureDevice.authorizationStatus(for: .audio)))
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        // Without the usage string, the system would end the process at the prompt.
        guard microphoneUsageDeclared() else {
            PNLog.modules.error("\(missingUsageMessage)")
            done("blocked")
            return nil
        }
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            DispatchQueue.main.async { done(granted ? "granted" : "blocked") }
        }
        return nil
    }
}

/// What `Sound` needs from a player, so `AudioModule` needn't care which one it holds.
private protocol PNSoundPlayer: AnyObject {
    var onEnd: (() -> Void)? { get set }
    var isPlaying: Bool { get }
    var position: Double { get }
    var duration: Double { get }
    func play()
    func pause()
    func seek(to seconds: Double)
    func setVolume(_ volume: Double)
    func setRate(_ rate: Double)
    func setLooping(_ looping: Bool)
    func unload()
}

/// A file on the device: `AVAudioPlayer`.
private final class PNLocalSound: NSObject, PNSoundPlayer, AVAudioPlayerDelegate {
    private let player: AVAudioPlayer
    var onEnd: (() -> Void)?

    init(url: URL) throws {
        player = try AVAudioPlayer(contentsOf: url)
        super.init()
        player.delegate = self
        player.enableRate = true
        player.prepareToPlay()
    }

    var isPlaying: Bool { player.isPlaying }
    var position: Double { player.currentTime }
    var duration: Double { player.duration }

    func play() { player.play() }
    func pause() { player.pause() }
    func seek(to seconds: Double) { player.currentTime = min(max(seconds, 0), player.duration) }
    func setVolume(_ volume: Double) { player.volume = Float(volume) }
    func setRate(_ rate: Double) { player.rate = Float(rate) }
    func setLooping(_ looping: Bool) { player.numberOfLoops = looping ? -1 : 0 }

    func unload() {
        player.stop()
        player.delegate = nil
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onEnd?()
    }
}

/// A network URL: `AVPlayer`, which streams where `AVAudioPlayer` can't.
private final class PNRemoteSound: PNSoundPlayer {
    private let player: AVPlayer
    private let item: AVPlayerItem
    private var rate: Float = 1
    private var looping = false
    private var statusObservation: NSKeyValueObservation?
    private var endObserver: NSObjectProtocol?
    private var settled: ((Result<Void, Error>) -> Void)?
    var onEnd: (() -> Void)?

    init(url: URL, settled: @escaping (Result<Void, Error>) -> Void) {
        item = AVPlayerItem(url: url)
        player = AVPlayer(playerItem: item)
        self.settled = settled
        statusObservation = item.observe(\.status, options: [.initial, .new]) { [weak self] item, _ in
            DispatchQueue.main.async { self?.statusChanged(item) }
        }
        endObserver = NotificationCenter.default.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { [weak self] _ in
            self?.reachedEnd()
        }
    }

    private func statusChanged(_ item: AVPlayerItem) {
        switch item.status {
        case .readyToPlay:
            settled?(.success(()))
            settled = nil
        case .failed:
            settled?(.failure(audioError("load_failed", item.error?.localizedDescription ?? "The sound couldn't load")))
            settled = nil
        default:
            break
        }
    }

    private func reachedEnd() {
        player.seek(to: .zero, toleranceBefore: .zero, toleranceAfter: .zero)
        if looping {
            player.rate = rate
        } else {
            player.pause()
            onEnd?()
        }
    }

    var isPlaying: Bool { player.rate != 0 }

    var position: Double {
        let seconds = player.currentTime().seconds
        return seconds.isFinite ? seconds : 0
    }

    var duration: Double {
        let seconds = item.duration.seconds
        return seconds.isFinite ? seconds : 0
    }

    func play() { player.rate = rate }
    func pause() { player.pause() }

    func seek(to seconds: Double) {
        player.seek(to: CMTime(seconds: max(seconds, 0), preferredTimescale: 600), toleranceBefore: .zero, toleranceAfter: .zero)
    }

    func setVolume(_ volume: Double) { player.volume = Float(volume) }

    func setRate(_ value: Double) {
        rate = Float(value)
        if player.rate != 0 { player.rate = rate }
    }

    func setLooping(_ value: Bool) { looping = value }

    func unload() {
        settled = nil
        statusObservation = nil
        if let observer = endObserver { NotificationCenter.default.removeObserver(observer) }
        endObserver = nil
        player.pause()
        player.replaceCurrentItem(with: nil)
    }
}

/// One `AVAudioRecorder`, and the session category to go back to when it's done.
private final class PNAudioRecording {
    private let recorder: AVAudioRecorder
    private let url: URL
    private let previous: (AVAudioSession.Category, AVAudioSession.Mode, AVAudioSession.CategoryOptions)

    init(path: String?, quality: PNAudioStartRecordingQuality) throws {
        url = try Self.fileURL(path)
        let session = AVAudioSession.sharedInstance()
        previous = (session.category, session.mode, session.categoryOptions)
        var settings: [String: Any] = [AVFormatIDKey: Int(kAudioFormatMPEG4AAC)]
        switch quality {
        case .low:
            settings[AVSampleRateKey] = 16_000
            settings[AVNumberOfChannelsKey] = 1
            settings[AVEncoderBitRateKey] = 32_000
        case .medium:
            settings[AVSampleRateKey] = 22_050
            settings[AVNumberOfChannelsKey] = 1
            settings[AVEncoderBitRateKey] = 64_000
        case .high:
            settings[AVSampleRateKey] = 44_100
            settings[AVNumberOfChannelsKey] = 1
            settings[AVEncoderBitRateKey] = 128_000
        }
        do {
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true)
            recorder = try AVAudioRecorder(url: url, settings: settings)
        } catch {
            try? session.setCategory(previous.0, mode: previous.1, options: previous.2)
            throw audioError("recording_failed", error.localizedDescription)
        }
        recorder.isMeteringEnabled = true
        guard recorder.record() else {
            try? session.setCategory(previous.0, mode: previous.1, options: previous.2)
            throw audioError("recording_failed", "The recorder wouldn't start")
        }
    }

    /// `nil` is a new file in Caches, and a relative path is under Caches.
    private static func fileURL(_ path: String?) throws -> URL {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let url: URL
        if let path = path, !path.isEmpty {
            if path.hasPrefix("file://"), let parsed = URL(string: path) {
                url = parsed
            } else if path.hasPrefix("/") {
                url = URL(fileURLWithPath: path)
            } else {
                url = caches.appendingPathComponent(path)
            }
        } else {
            url = caches.appendingPathComponent("pn-recordings/\(UUID().uuidString).m4a")
        }
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        } catch {
            throw audioError("recording_failed", error.localizedDescription)
        }
        return url
    }

    func pause() { recorder.pause() }

    func resume() {
        if !recorder.record() { PNLog.modules.error("recording wouldn't resume") }
    }

    var metering: Double {
        recorder.updateMeters()
        return Double(recorder.averagePower(forChannel: 0))
    }

    func stop() throws -> PNRecording {
        let elapsed = recorder.currentTime
        recorder.stop()
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(previous.0, mode: previous.1, options: previous.2)
        let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? NSNumber)?.intValue ?? 0
        guard size > 0 else { throw audioError("recording_failed", "No audio was captured") }
        // The finished file's own length is more exact than the recorder's clock.
        let measured = AVURLAsset(url: url).duration.seconds
        return PNRecording(duration: measured.isFinite && measured > 0 ? measured : elapsed, path: url.path)
    }

    func cancel() {
        recorder.stop()
        recorder.deleteRecording()
        try? AVAudioSession.sharedInstance().setCategory(previous.0, mode: previous.1, options: previous.2)
    }
}

/// `Audio`: `Sound` and `Recorder`, addressed by id, plus the session mode.
public final class AudioModule: AudioImplementation {
    private var sounds: [Int64: PNSoundPlayer] = [:]
    private var recordings: [Int64: PNAudioRecording] = [:]
    private var nextID: Int64 = 1
    private var backgroundObserver: NSObjectProtocol?
    private var isStartingRecording = false
    private let recordingQueue = DispatchQueue(label: "com.pythonnative.audio.recording")

    public init() {
        // An app that declared the `audio` background mode wants to keep playing.
        let modes = Bundle.main.object(forInfoDictionaryKey: "UIBackgroundModes") as? [String] ?? []
        if !modes.contains("audio") {
            backgroundObserver = NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
                self?.sounds.values.forEach { if $0.isPlaying { $0.pause() } }
            }
        }
    }

    private func sound(_ id: Int64) throws -> PNSoundPlayer {
        guard let sound = sounds[id] else { throw audioError("not_found", "No loaded sound \(id)") }
        return sound
    }

    private func recording(_ id: Int64) throws -> PNAudioRecording {
        guard let recording = recordings[id] else { throw audioError("not_found", "No active recording \(id)") }
        return recording
    }

    private func install(_ player: PNSoundPlayer, volume: Double, rate: Double, looping: Bool) -> Int64 {
        let id = nextID
        nextID += 1
        player.setVolume(volume)
        player.setRate(rate)
        player.setLooping(looping)
        player.onEnd = { PNModuleEvents.emit(module: "Audio", event: "sound_ended", payload: ["id": id]) }
        sounds[id] = player
        return id
    }

    /// A URL, a file path, an `asset://` URI, or a path under `app/assets/`.
    private func resolve(_ source: String) -> URL? {
        if source.hasPrefix("http://") || source.hasPrefix("https://") || source.hasPrefix("file://") {
            return URL(string: source)
        }
        if source.hasPrefix("/") { return URL(fileURLWithPath: source) }
        return PNAssets.shared.resolve(source)?.url
    }

    public func load_sound(looping: Bool, rate: Double, source: String, volume: Double, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        guard let url = resolve(source) else {
            completion(.failure(audioError("load_failed", "Can't find sound source: \(source)")))
            return nil
        }
        if url.isFileURL {
            var cancelled = false
            DispatchQueue.global(qos: .userInitiated).async {
                let loaded = Result { try PNLocalSound(url: url) }
                DispatchQueue.main.async {
                    if cancelled { return }
                    switch loaded {
                    case .success(let player):
                        completion(.success(self.install(player, volume: volume, rate: rate, looping: looping)))
                    case .failure(let error):
                        completion(.failure(audioError("load_failed", error.localizedDescription)))
                    }
                }
            }
            return { cancelled = true }
        }
        var pending: PNRemoteSound?
        let player = PNRemoteSound(url: url) { result in
            guard let player = pending else { return }
            pending = nil
            switch result {
            case .success: completion(.success(self.install(player, volume: volume, rate: rate, looping: looping)))
            case .failure(let error): completion(.failure(error))
            }
        }
        pending = player
        return {
            pending?.unload()
            pending = nil
        }
    }

    public func play_sound(id: Int64) throws { try sound(id).play() }
    public func pause_sound(id: Int64) throws { try sound(id).pause() }

    public func stop_sound(id: Int64) throws {
        let player = try sound(id)
        player.pause()
        player.seek(to: 0)
    }

    public func seek_sound(id: Int64, seconds: Double) throws { try sound(id).seek(to: seconds) }
    public func set_sound_volume(id: Int64, volume: Double) throws { try sound(id).setVolume(min(max(volume, 0), 1)) }
    public func set_sound_rate(id: Int64, rate: Double) throws { try sound(id).setRate(max(rate, 0)) }
    public func set_sound_looping(id: Int64, looping: Bool) throws { try sound(id).setLooping(looping) }
    public func sound_position(id: Int64) throws -> Double { try sound(id).position }
    public func sound_duration(id: Int64) throws -> Double { try sound(id).duration }
    public func unload_sound(id: Int64) throws { sounds.removeValue(forKey: id)?.unload() }

    public func start_recording(path: String?, quality: PNAudioStartRecordingQuality, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        guard microphoneUsageDeclared() else {
            completion(.failure(audioError("missing_usage_string", missingUsageMessage)))
            return nil
        }
        guard recordings.isEmpty, !isStartingRecording else {
            completion(.failure(audioError("recording_failed", "A recording is already running")))
            return nil
        }
        isStartingRecording = true
        var cancelled = false
        let begin = {
            var settled = false
            // Starting input waits on the audio server, which may never answer
            // (seen on the simulator), and a caller shouldn't wait forever.
            let timeout = DispatchWorkItem {
                settled = true
                if !cancelled { completion(.failure(audioError("recording_failed", "The audio input didn't start in time"))) }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 20, execute: timeout)
            // Activating the session can block, so it stays off the main thread.
            self.recordingQueue.async {
                let started = Result { try PNAudioRecording(path: path, quality: quality) }
                DispatchQueue.main.async {
                    self.isStartingRecording = false
                    timeout.cancel()
                    if cancelled || settled {
                        if case .success(let recording) = started {
                            self.recordingQueue.async { recording.cancel() }
                        }
                        return
                    }
                    settled = true
                    completion(started.map { recording in
                        let id = self.nextID
                        self.nextID += 1
                        self.recordings[id] = recording
                        return id
                    })
                }
            }
        }
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            begin()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    if granted {
                        begin()
                    } else {
                        self.isStartingRecording = false
                        if !cancelled { completion(.failure(audioError("permission_denied", "Microphone permission was denied"))) }
                    }
                }
            }
        default:
            isStartingRecording = false
            completion(.failure(audioError("permission_denied", "Microphone permission was denied")))
            return nil
        }
        return { cancelled = true }
    }

    public func pause_recording(id: Int64) throws { try recording(id).pause() }
    public func resume_recording(id: Int64) throws { try recording(id).resume() }
    public func recording_metering(id: Int64) throws -> Double { try recording(id).metering }

    public func stop_recording(id: Int64, completion: @escaping (Result<PNRecording, Error>) -> Void) -> (() -> Void)? {
        guard let active = recordings.removeValue(forKey: id) else {
            completion(.failure(audioError("not_found", "No active recording \(id)")))
            return nil
        }
        recordingQueue.async {
            let finished = Result { try active.stop() }
            DispatchQueue.main.async { completion(finished) }
        }
        return nil
    }

    public func set_mode(allow_bluetooth: Bool, category: PNAudioSetModeCategory, default_to_speaker: Bool, duck_others: Bool, mix_with_others: Bool) throws {
        let session: AVAudioSession.Category
        switch category {
        case .ambient: session = .ambient
        case .solo_ambient: session = .soloAmbient
        case .playback: session = .playback
        case .record: session = .record
        case .play_and_record: session = .playAndRecord
        case .multi_route: session = .multiRoute
        }
        var options: AVAudioSession.CategoryOptions = []
        if mix_with_others { options.insert(.mixWithOthers) }
        if duck_others { options.insert(.duckOthers) }
        if default_to_speaker { options.insert(.defaultToSpeaker) }
        if allow_bluetooth { options.insert(.allowBluetooth) }
        do {
            try AVAudioSession.sharedInstance().setCategory(session, options: options)
        } catch {
            throw audioError("invalid_mode", error.localizedDescription)
        }
    }
}
