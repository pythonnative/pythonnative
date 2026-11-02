import AVFoundation
import AVKit
import UIKit

/// Registers the `Video` component.
public enum VideoPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("Video") { PNVideoManager() }
    }
}

/// `Video`: props go to one `PNVideoView`, which owns the player.
final class PNVideoManager: PNTypedComponentManager<VideoProps> {
    init() { super.init(VideoProps.self) }

    override func makeView(props: [String: Any]) -> UIView {
        PNVideoView(frame: .zero)
    }

    override func applyTyped(view: UIView, props: VideoProps, initial: Bool) {
        PNViewStyler.applyCommon(view, props.values)
        guard let video = view as? PNVideoView else { return }
        if initial || props.has_resize_mode { video.setResizeMode(props.resize_mode ?? .contain) }
        if initial || props.has_controls { video.setControls(props.controls ?? false) }
        if initial || props.has_autoplay { video.autoplay = props.autoplay ?? false }
        if initial || props.has_loop { video.loops = props.loop ?? false }
        if initial || props.has_muted { video.setMuted(props.muted ?? false) }
        if initial || props.has_volume { video.setVolume(props.volume ?? 1) }
        if initial || props.has_rate { video.setRate(props.rate ?? 1) }
        if initial || props.has_progress_interval { video.setProgressInterval(props.progress_interval ?? 0.25) }
        if initial || props.has_poster { video.setPoster(props.poster) }
        if initial || props.has_source { video.setSource(props.source) }
    }

    override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let video = view as? PNVideoView else { return nil }
        switch name {
        case "play": video.play()
        case "pause": video.pause()
        case "seek": video.seek(to: PNProps.double(args["seconds"]) ?? 0)
        case "position": return video.position
        default: return super.command(view: view, name: name, args: args)
        }
        return nil
    }

    override func teardown(view: UIView) {
        (view as? PNVideoView)?.releasePlayer()
    }
}

/// An `AVPlayer` shown through this view's own `AVPlayerLayer`, or through an
/// `AVPlayerViewController` when native controls are on, which is the only
/// way UIKit offers them.
final class PNVideoView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
    private var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }

    var autoplay = false
    var loops = false

    private let player = AVPlayer()
    private var controller: AVPlayerViewController?
    private let posterView = UIImageView()
    private var cancelPoster: (() -> Void)?
    private var gravity: AVLayerVideoGravity = .resizeAspect
    private var rate: Float = 1
    private var progressInterval = 0.25
    private var timeObserver: Any?
    private var statusObservation: NSKeyValueObservation?
    private var waitingObservation: NSKeyValueObservation?
    private var itemObservers: [NSObjectProtocol] = []
    private var appObservers: [NSObjectProtocol] = []
    private var pendingSeek: Double?
    private var isItemReady = false
    private var isBuffering = false
    private var didEnd = false
    private var resumeOnForeground = false
    private var released = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        clipsToBounds = true
        playerLayer.player = player
        playerLayer.videoGravity = gravity
        posterView.isHidden = true
        posterView.clipsToBounds = true
        addSubview(posterView)
        observeTimeControl()
        observeApp()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    deinit { releasePlayer() }

    override func layoutSubviews() {
        super.layoutSubviews()
        controller?.view.frame = bounds
        posterView.frame = bounds
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        guard let controller = controller else { return }
        if window == nil {
            controller.willMove(toParent: nil)
            controller.removeFromParent()
        } else if controller.parent == nil, let parent = owningViewController() {
            parent.addChild(controller)
            controller.didMove(toParent: parent)
        }
    }

    private func owningViewController() -> UIViewController? {
        var responder: UIResponder? = next
        while let current = responder {
            if let viewController = current as? UIViewController { return viewController }
            responder = current.next
        }
        return nil
    }

    // MARK: - Props

    func setControls(_ enabled: Bool) {
        if enabled == (controller != nil) { return }
        if enabled {
            let controller = AVPlayerViewController()
            controller.player = player
            controller.videoGravity = gravity
            controller.view.frame = bounds
            controller.view.backgroundColor = .clear
            playerLayer.player = nil
            insertSubview(controller.view, belowSubview: posterView)
            self.controller = controller
            if window != nil, let parent = owningViewController() {
                parent.addChild(controller)
                controller.didMove(toParent: parent)
            }
        } else if let controller = controller {
            detach(controller)
            self.controller = nil
            playerLayer.player = player
        }
    }

    private func detach(_ controller: AVPlayerViewController) {
        controller.willMove(toParent: nil)
        controller.view.removeFromSuperview()
        controller.removeFromParent()
        controller.player = nil
    }

    func setResizeMode(_ mode: PNVideoResizeMode) {
        switch mode {
        case .contain:
            gravity = .resizeAspect
            posterView.contentMode = .scaleAspectFit
        case .cover:
            gravity = .resizeAspectFill
            posterView.contentMode = .scaleAspectFill
        case .stretch:
            gravity = .resize
            posterView.contentMode = .scaleToFill
        }
        playerLayer.videoGravity = gravity
        controller?.videoGravity = gravity
    }

    func setMuted(_ muted: Bool) {
        player.isMuted = muted
        preparePlaybackCategory()
    }

    func setVolume(_ volume: Double) {
        player.volume = Float(min(max(volume, 0), 1))
    }

    func setRate(_ value: Double) {
        rate = Float(max(value, 0))
        if player.rate != 0 { player.rate = rate }
    }

    func setProgressInterval(_ seconds: Double) {
        progressInterval = max(seconds, 0.016)
        if timeObserver != nil || player.currentItem != nil { observeProgress() }
    }

    func setSource(_ source: String?) {
        clearItem()
        guard let source = source, !source.isEmpty else {
            player.replaceCurrentItem(with: nil)
            return
        }
        guard let url = Self.url(for: source) else {
            player.replaceCurrentItem(with: nil)
            let message = "Can't find video source: \(source)"
            // The view may not be registered yet during its initial props.
            DispatchQueue.main.async { [weak self] in
                if let self = self { PNComponentEvents.Video.on_error(self, message) }
            }
            return
        }
        posterView.isHidden = posterView.image == nil
        preparePlaybackCategory()
        let item = AVPlayerItem(url: url)
        observe(item)
        player.replaceCurrentItem(with: item)
        observeProgress()
        DispatchQueue.main.async { [weak self] in self?.setBuffering(true) }
    }

    func setPoster(_ source: String?) {
        cancelPoster?()
        cancelPoster = nil
        posterView.image = nil
        posterView.isHidden = true
        guard let source = source, !source.isEmpty else { return }
        let size = bounds.size
        let show: (UIImage?) -> Void = { [weak self] image in
            guard let self = self, let image = image else { return }
            self.posterView.image = image
            self.posterView.isHidden = self.player.rate != 0 || self.didEnd
        }
        if PNImageManager.isRemote(source) {
            cancelPoster = PNImageLoader.shared.fetch(source) { result in
                DispatchQueue.global(qos: .userInitiated).async {
                    let image = (try? result.get()).flatMap { PNImageManager.decode($0, targetSize: size) }
                    DispatchQueue.main.async { show(image) }
                }
            }
        } else {
            DispatchQueue.global(qos: .userInitiated).async {
                let image = PNImageManager.loadLocal(source, targetSize: size)
                DispatchQueue.main.async { show(image) }
            }
        }
    }

    /// A URL, a file path, an `asset://` URI, or a path under `app/assets/`.
    private static func url(for source: String) -> URL? {
        if source.hasPrefix("http://") || source.hasPrefix("https://") || source.hasPrefix("file://") {
            return URL(string: source)
        }
        if source.hasPrefix("/") { return URL(fileURLWithPath: source) }
        return PNAssets.shared.resolve(source)?.url
    }

    /// iOS's default session obeys the silent switch, which isn't what anyone
    /// expects of a video with sound. A category the app chose stays as it is.
    private func preparePlaybackCategory() {
        guard !player.isMuted, player.currentItem != nil || controller != nil else { return }
        let session = AVAudioSession.sharedInstance()
        if session.category == .soloAmbient {
            do {
                try session.setCategory(.playback)
            } catch {
                PNLog.modules.error("video audio session failed: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Commands

    func play() {
        if didEnd {
            didEnd = false
            player.seek(to: .zero, toleranceBefore: .zero, toleranceAfter: .zero)
        }
        posterView.isHidden = true
        player.rate = rate
    }

    func pause() {
        player.pause()
    }

    func seek(to seconds: Double) {
        guard isItemReady else {
            pendingSeek = seconds
            return
        }
        didEnd = false
        posterView.isHidden = true
        player.seek(to: CMTime(seconds: max(seconds, 0), preferredTimescale: 600), toleranceBefore: .zero, toleranceAfter: .zero)
    }

    var position: Double {
        let seconds = player.currentTime().seconds
        return seconds.isFinite ? seconds : 0
    }

    // MARK: - Observation

    private func observeTimeControl() {
        waitingObservation = player.observe(\.timeControlStatus, options: [.new]) { [weak self] player, _ in
            DispatchQueue.main.async { self?.timeControlChanged(player) }
        }
    }

    private func timeControlChanged(_ player: AVPlayer) {
        switch player.timeControlStatus {
        case .playing:
            posterView.isHidden = true
            setBuffering(false)
        case .waitingToPlayAtSpecifiedRate:
            if player.currentItem != nil && player.reasonForWaitingToPlay != .noItemToPlay { setBuffering(true) }
        case .paused:
            if isItemReady { setBuffering(false) }
        @unknown default:
            break
        }
    }

    private func observe(_ item: AVPlayerItem) {
        statusObservation = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            DispatchQueue.main.async { self?.statusChanged(item) }
        }
        let center = NotificationCenter.default
        itemObservers = [
            center.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main) { [weak self] _ in
                self?.reachedEnd()
            },
            center.addObserver(forName: .AVPlayerItemFailedToPlayToEndTime, object: item, queue: .main) { [weak self] note in
                guard let self = self else { return }
                let error = note.userInfo?[AVPlayerItemFailedToPlayToEndTimeErrorKey] as? Error
                self.setBuffering(false)
                PNComponentEvents.Video.on_error(self, error?.localizedDescription ?? "Playback failed")
            },
        ]
    }

    private func statusChanged(_ item: AVPlayerItem) {
        guard item === player.currentItem else { return }
        switch item.status {
        case .readyToPlay:
            if isItemReady { return }
            isItemReady = true
            setBuffering(false)
            let size = item.presentationSize
            PNComponentEvents.Video.on_ready(self, PNVideoInfo(duration: Self.seconds(item.duration), height: Double(size.height), width: Double(size.width)))
            if let seconds = pendingSeek {
                pendingSeek = nil
                seek(to: seconds)
            }
            if autoplay { play() }
        case .failed:
            setBuffering(false)
            PNComponentEvents.Video.on_error(self, item.error?.localizedDescription ?? "The video couldn't load")
        default:
            break
        }
    }

    private func reachedEnd() {
        if loops {
            player.seek(to: .zero, toleranceBefore: .zero, toleranceAfter: .zero)
            player.rate = rate
            return
        }
        didEnd = true
        PNComponentEvents.Video.on_end(self)
    }

    private func observeProgress() {
        if let observer = timeObserver { player.removeTimeObserver(observer) }
        let interval = CMTime(seconds: progressInterval, preferredTimescale: 600)
        timeObserver = player.addPeriodicTimeObserver(forInterval: interval, queue: .main) { [weak self] time in
            guard let self = self, let item = self.player.currentItem, self.isItemReady, time.seconds.isFinite else { return }
            PNComponentEvents.Video.on_progress(self, time.seconds, Self.seconds(item.duration))
        }
    }

    private func setBuffering(_ buffering: Bool) {
        if buffering == isBuffering { return }
        isBuffering = buffering
        PNComponentEvents.Video.on_buffering(self, buffering)
    }

    private static func seconds(_ time: CMTime) -> Double {
        let seconds = time.seconds
        return seconds.isFinite ? seconds : 0
    }

    private func observeApp() {
        let center = NotificationCenter.default
        appObservers = [
            center.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
                guard let self = self else { return }
                self.resumeOnForeground = self.player.rate != 0
                self.player.pause()
            },
            center.addObserver(forName: UIApplication.willEnterForegroundNotification, object: nil, queue: .main) { [weak self] _ in
                guard let self = self, self.resumeOnForeground else { return }
                self.resumeOnForeground = false
                self.player.rate = self.rate
            },
        ]
    }

    // MARK: - Cleanup

    private func clearItem() {
        statusObservation = nil
        for observer in itemObservers { NotificationCenter.default.removeObserver(observer) }
        itemObservers = []
        pendingSeek = nil
        isItemReady = false
        didEnd = false
    }

    /// Stop for good: the view is unmounting.
    func releasePlayer() {
        if released { return }
        released = true
        cancelPoster?()
        cancelPoster = nil
        clearItem()
        waitingObservation = nil
        for observer in appObservers { NotificationCenter.default.removeObserver(observer) }
        appObservers = []
        if let observer = timeObserver { player.removeTimeObserver(observer) }
        timeObserver = nil
        player.pause()
        player.replaceCurrentItem(with: nil)
        if let controller = controller { detach(controller) }
        controller = nil
        playerLayer.player = nil
    }
}
