import UIKit

/// `DevSupport`: the device-side development UI the devtools agent drives.
///
/// A non-contract module like `Host`: Python enables it only in
/// development mode, and until then menu triggers do nothing. Events go to
/// Python as module events: `menu` (shake, Cmd+D), `reload` (Cmd+R),
/// `inspect` (`{"tag", "x", "y"}` for a tap while inspecting), and
/// `inspect_done` (the inspector banner's Done button).
///
/// Overlays are subviews of the key window, brought to the front whenever
/// they change, and are removed from the hierarchy when hidden.
public final class DevSupportModule: PNNativeModule {
    public static let name = "DevSupport"

    /// Whether Python has enabled development support.
    public private(set) static var isEnabled = false

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "enable":
            Self.isEnabled = true
            promise.resolve(nil)
        case "highlight":
            let tag = PNProps.int(args["tag"]).map(Int64.init)
            promise.resolve(Self.highlight(tag: tag, label: PNProps.string(args["label"]) ?? ""))
        case "set_inspecting":
            Self.setInspecting(PNProps.bool(args["enabled"]) ?? false)
            promise.resolve(nil)
        case "set_perf_monitor":
            let lines = (args["lines"] as? [Any] ?? []).compactMap { $0 as? String }
            Self.setPerfMonitor(visible: PNProps.bool(args["visible"]) ?? false, lines: lines)
            promise.resolve(nil)
        case "frame_stats":
            promise.resolve(PNFrameCounter.shared.stats())
        default:
            promise.reject("DevSupport has no method '\(method)'", code: "unknown_method")
        }
    }

    /// Send `event` (`"menu"`, `"reload"`) to Python if development support
    /// is enabled. Returns whether it was sent.
    @discardableResult
    public static func trigger(_ event: String) -> Bool {
        guard isEnabled else { return false }
        PNModuleEvents.emit(module: name, event: event, payload: [String: Any]())
        return true
    }

    /// Forget all state and remove every overlay. Intended for tests.
    static func reset() {
        isEnabled = false
        highlightView?.removeFromSuperview(); highlightView = nil
        inspector?.removeFromSuperview(); inspector = nil
        perfMonitor?.removeFromSuperview(); perfMonitor = nil
    }

    // MARK: - Highlight

    static var highlightView: PNHighlightView?

    /// Outline the view for `tag` with a label chip, or clear the outline
    /// when `tag` is nil. Returns whether an outline is showing.
    static func highlight(tag: Int64?, label: String) -> Bool {
        guard let tag = tag, let target = PNViewRegistry.shared.view(for: tag),
              let window = target.window ?? PNWindow.keyWindow() else {
            highlightView?.removeFromSuperview()
            highlightView = nil
            return false
        }
        let outline = highlightView ?? PNHighlightView()
        highlightView = outline
        outline.show(frame: target.convert(target.bounds, to: window), label: label, in: window)
        raiseOverlays(in: window)
        return true
    }

    // MARK: - Inspector

    static var inspector: PNInspectorOverlay?

    /// Intercept taps and report the tapped view as an `inspect` event.
    static func setInspecting(_ enabled: Bool) {
        guard enabled else {
            inspector?.removeFromSuperview()
            inspector = nil
            return
        }
        guard inspector == nil, let window = PNWindow.keyWindow() else { return }
        let overlay = PNInspectorOverlay(frame: window.bounds)
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        overlay.onTap = { point in
            guard let tag = inspect(at: point, in: window) else { return }
            PNModuleEvents.emit(module: name, event: "inspect", payload: ["tag": tag, "x": Double(point.x), "y": Double(point.y)])
        }
        overlay.onDone = {
            setInspecting(false)
            PNModuleEvents.emit(module: name, event: "inspect_done", payload: [String: Any]())
        }
        window.addSubview(overlay)
        inspector = overlay
        raiseOverlays(in: window)
        UIAccessibility.post(notification: .screenChanged, argument: overlay.banner)
    }

    /// The tag of the deepest registered view under `point` (window
    /// coordinates), ignoring the development overlays.
    ///
    /// Unlike `hitTest`, views that don't take touches (labels, images)
    /// count, so tapping a `Text` selects the `Text`.
    static func inspect(at point: CGPoint, in window: UIWindow) -> Int64? {
        let overlays: [UIView?] = [inspector, highlightView, perfMonitor, PNErrorOverlay.visible]
        let excluded = Set(overlays.compactMap { $0.map(ObjectIdentifier.init) })
        return deepestRegistered(in: window, at: point, excluding: excluded)
    }

    private static func deepestRegistered(in view: UIView, at point: CGPoint, excluding excluded: Set<ObjectIdentifier>) -> Int64? {
        guard !view.isHidden, view.alpha > 0.01, !excluded.contains(ObjectIdentifier(view)),
              view.point(inside: point, with: nil) else { return nil }
        for subview in view.subviews.reversed() {
            if let tag = deepestRegistered(in: subview, at: view.convert(point, to: subview), excluding: excluded) {
                return tag
            }
        }
        if let state = PNViewState.existing(for: view), PNViewRegistry.shared.view(for: state.tag) === view {
            return state.tag
        }
        return nil
    }

    // MARK: - Performance monitor

    static var perfMonitor: PNPerfMonitorView?

    /// Show the floating monitor with the native frame rate and `lines`, or hide it.
    static func setPerfMonitor(visible: Bool, lines: [String]) {
        guard visible else {
            perfMonitor?.removeFromSuperview()
            perfMonitor = nil
            PNFrameCounter.shared.onSecond = nil
            return
        }
        guard let window = PNWindow.keyWindow() else { return }
        let monitor = perfMonitor ?? PNPerfMonitorView()
        perfMonitor = monitor
        monitor.lines = lines
        if monitor.superview !== window {
            monitor.removeFromSuperview()
            window.addSubview(monitor)
            monitor.pin(to: window)
        }
        PNFrameCounter.shared.start()
        PNFrameCounter.shared.onSecond = { [weak monitor] in monitor?.refresh() }
        monitor.refresh()
        raiseOverlays(in: window)
    }

    /// Keep the overlays above the app's content, the inspector topmost.
    private static func raiseOverlays(in window: UIWindow) {
        for overlay in [highlightView, perfMonitor, inspector] as [UIView?] {
            if let overlay = overlay, overlay.superview === window { window.bringSubviewToFront(overlay) }
        }
    }
}

// MARK: - Frame counter

/// Counts the UI thread's frames with a `CADisplayLink`, started on first use.
final class PNFrameCounter {
    static let shared = PNFrameCounter()

    /// Called on the main thread each time a one-second window closes.
    var onSecond: (() -> Void)?

    private var link: CADisplayLink?
    private var windowStart: CFTimeInterval = 0
    private var windowFrames = 0
    private var lastTimestamp: CFTimeInterval = 0
    private var dropped = 0
    private(set) var fps: Double = 0

    /// `{"fps": frames per second over the last second, "dropped": frames
    /// dropped since the previous call}`.
    func stats() -> [String: Any] {
        start()
        let result: [String: Any] = ["fps": (fps * 10).rounded() / 10, "dropped": dropped]
        dropped = 0
        return result
    }

    func start() {
        guard link == nil else { return }
        let link = CADisplayLink(target: PNFrameTarget(self), selector: #selector(PNFrameTarget.tick(_:)))
        link.add(to: .main, forMode: .common)
        self.link = link
    }

    fileprivate func tick(_ link: CADisplayLink) {
        let now = link.timestamp
        let interval = link.duration > 0 ? link.duration : 1.0 / 60
        if lastTimestamp > 0 {
            let missed = Int(((now - lastTimestamp) / interval).rounded()) - 1
            if missed > 0 { dropped += missed }
        } else {
            windowStart = now
        }
        lastTimestamp = now
        windowFrames += 1
        let elapsed = now - windowStart
        if elapsed >= 1 {
            fps = Double(windowFrames) / elapsed
            windowFrames = 0
            windowStart = now
            onSecond?()
        }
    }
}

/// Breaks the display link's strong reference to its target.
private final class PNFrameTarget: NSObject {
    weak var counter: PNFrameCounter?
    init(_ counter: PNFrameCounter) { self.counter = counter }
    @objc func tick(_ link: CADisplayLink) { counter?.tick(link) }
}

// MARK: - Overlay views

private let accent = UIColor.systemBlue

/// The inspector's outline and label chip. It never takes touches.
final class PNHighlightView: UIView {
    private let outline = UIView()
    private let chip = UILabel()

    init() {
        super.init(frame: .zero)
        isUserInteractionEnabled = false
        isAccessibilityElement = false
        accessibilityElementsHidden = true
        outline.layer.borderColor = accent.cgColor
        outline.layer.borderWidth = 2
        outline.backgroundColor = accent.withAlphaComponent(0.15)
        chip.font = .monospacedSystemFont(ofSize: 11, weight: .semibold)
        chip.textColor = .white
        chip.backgroundColor = accent
        chip.layer.cornerRadius = 4
        chip.layer.masksToBounds = true
        chip.textAlignment = .center
        addSubview(outline)
        addSubview(chip)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func show(frame target: CGRect, label: String, in window: UIWindow) {
        if superview !== window {
            removeFromSuperview()
            window.addSubview(self)
        }
        frame = window.bounds
        outline.frame = target
        chip.text = label
        chip.isHidden = label.isEmpty
        let size = chip.sizeThatFits(CGSize(width: window.bounds.width - 16, height: 20))
        let width = min(size.width + 12, window.bounds.width - 8)
        let height: CGFloat = 20
        // Above the outline when there's room, otherwise just inside its top.
        let top = target.minY - height - 2 >= window.safeAreaInsets.top ? target.minY - height - 2 : max(target.minY + 2, window.safeAreaInsets.top)
        let left = min(max(target.minX, 4), window.bounds.width - width - 4)
        chip.frame = CGRect(x: left, y: top, width: width, height: height)
    }
}

/// A transparent, window-sized view that takes every tap while inspecting,
/// with a banner explaining it and a Done button.
final class PNInspectorOverlay: UIView, UIGestureRecognizerDelegate {
    var onTap: ((CGPoint) -> Void)?
    var onDone: (() -> Void)?
    let banner = UIView()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        accessibilityIdentifier = "pn-dev-inspector"
        banner.backgroundColor = UIColor(white: 0.1, alpha: 0.9)
        banner.layer.cornerRadius = 12
        banner.accessibilityIdentifier = "pn-dev-inspector-banner"
        let label = UILabel()
        label.text = "Tap an element to inspect it"
        label.textColor = .white
        label.font = .preferredFont(forTextStyle: .subheadline)
        label.adjustsFontForContentSizeCategory = true
        label.numberOfLines = 0
        let done = UIButton(type: .system)
        done.setTitle("Done", for: .normal)
        done.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        done.tintColor = UIColor(red: 0.45, green: 0.7, blue: 1, alpha: 1)
        done.accessibilityIdentifier = "pn-dev-inspector-done"
        done.addTarget(self, action: #selector(donePressed), for: .touchUpInside)
        done.setContentHuggingPriority(.required, for: .horizontal)
        let row = UIStackView(arrangedSubviews: [label, done])
        row.spacing = 12
        row.alignment = .center
        banner.addSubview(row)
        addSubview(banner)
        row.translatesAutoresizingMaskIntoConstraints = false
        banner.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            row.topAnchor.constraint(equalTo: banner.topAnchor, constant: 8),
            row.bottomAnchor.constraint(equalTo: banner.bottomAnchor, constant: -8),
            row.leadingAnchor.constraint(equalTo: banner.leadingAnchor, constant: 16),
            row.trailingAnchor.constraint(equalTo: banner.trailingAnchor, constant: -12),
            banner.bottomAnchor.constraint(equalTo: safeAreaLayoutGuide.bottomAnchor, constant: -12),
            banner.centerXAnchor.constraint(equalTo: centerXAnchor),
            banner.leadingAnchor.constraint(greaterThanOrEqualTo: leadingAnchor, constant: 16),
            banner.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor, constant: -16),
        ])
        let tap = UITapGestureRecognizer(target: self, action: #selector(tapped(_:)))
        tap.delegate = self
        addGestureRecognizer(tap)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        !(touch.view?.isDescendant(of: banner) ?? false)
    }

    @objc private func tapped(_ recognizer: UITapGestureRecognizer) {
        guard let window = window else { return }
        onTap?(recognizer.location(in: window))
    }

    @objc private func donePressed() { onDone?() }
}

/// The floating performance monitor: the native frame rate, then Python's lines.
final class PNPerfMonitorView: UIView {
    var lines: [String] = []
    private let label = UILabel()

    init() {
        super.init(frame: .zero)
        isUserInteractionEnabled = false
        accessibilityIdentifier = "pn-dev-perf-monitor"
        backgroundColor = UIColor(white: 0, alpha: 0.7)
        layer.cornerRadius = 8
        label.numberOfLines = 0
        label.textColor = .white
        label.font = .monospacedDigitSystemFont(ofSize: 11, weight: .medium)
        addSubview(label)
        label.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            label.topAnchor.constraint(equalTo: topAnchor, constant: 6),
            label.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -6),
            label.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 8),
            label.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -8),
        ])
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    var text: String { label.text ?? "" }

    func pin(to window: UIWindow) {
        translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            topAnchor.constraint(equalTo: window.safeAreaLayoutGuide.topAnchor, constant: 8),
            trailingAnchor.constraint(equalTo: window.safeAreaLayoutGuide.trailingAnchor, constant: -8),
            widthAnchor.constraint(lessThanOrEqualTo: window.widthAnchor, multiplier: 0.6),
        ])
    }

    func refresh() {
        let fps = Int(PNFrameCounter.shared.fps.rounded())
        label.text = (["UI \(fps) fps"] + lines).joined(separator: "\n")
        accessibilityLabel = label.text
    }
}
