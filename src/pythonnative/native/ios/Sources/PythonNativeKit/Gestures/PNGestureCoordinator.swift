import UIKit

/// Installs `UIGestureRecognizer`s from the `gestures` prop and emits
/// `gesture:<index>` events with the payload dict Python's
/// `GestureEvent` expects.
///
/// Spec fields:
/// - `kind`: `tap`, `long_press`, `pan`, `swipe`, `fling`, `pinch`, `rotation`
/// - `enabled`: `false` keeps the spec's index but installs no recognizer
/// - per-kind config (`n_taps`, `max_distance`, `min_duration_ms`,
///   `min_distance`, `min_pointers`, `max_pointers`, `active_offset_x/y`,
///   `fail_offset_x/y`, `min_velocity`, `direction`, `n_pointers`)
/// - `simultaneous`: indices allowed to recognize together
/// - `wait_for`: indices that must fail before this one may begin
///
/// Every payload carries the view-local `x`/`y` and the window-space
/// `absolute_x`/`absolute_y`; `direction` is a swipe direction or `null`.
public final class PNGestureCoordinator: NSObject, UIGestureRecognizerDelegate {
    public static let shared = PNGestureCoordinator()

    /// Bookkeeping for one installed recognizer.
    final class Entry {
        let index: Int
        let kind: String
        var simultaneous: Set<Int>
        var minVelocity: CGFloat
        var direction: String
        var lastLocation: CGPoint = .zero

        init(index: Int, kind: String, simultaneous: Set<Int>, minVelocity: CGFloat, direction: String) {
            self.index = index
            self.kind = kind
            self.simultaneous = simultaneous
            self.minVelocity = minVelocity
            self.direction = direction
        }
    }

    private var entries: [ObjectIdentifier: Entry] = [:]

    private override init() {
        super.init()
    }

    // MARK: - Wiring

    /// Replace the recognizers on `view` with the ones described by `specs`.
    public func wire(view: UIView, specs: Any?) {
        unwire(view: view)
        guard let state = PNViewState.existing(for: view) else { return }
        let list = ((specs as? [Any]) ?? []).map { ($0 as? [String: Any]) ?? [:] }
        guard !list.isEmpty else { return }
        // A spec may own several recognizers (an any-direction swipe is
        // one `UISwipeGestureRecognizer` per direction), so relationships
        // are wired spec-to-spec across every recognizer on each side.
        var built: [Int: [UIGestureRecognizer]] = [:]
        for (index, spec) in list.enumerated() {
            if PNProps.bool(spec["enabled"]) == false { continue }
            let recognizers = makeRecognizers(spec)
            if recognizers.isEmpty {
                PNLog.once(PNLog.gestures, key: "kind:\(PNProps.string(spec["kind"]) ?? "")", "unsupported gesture kind '\(PNProps.string(spec["kind"]) ?? "")'")
                continue
            }
            for (recognizer, direction) in recognizers {
                let entry = Entry(
                    index: index,
                    kind: PNProps.string(spec["kind"]) ?? "",
                    simultaneous: Set(((spec["simultaneous"] as? [Any]) ?? []).compactMap { PNProps.int($0) }),
                    minVelocity: CGFloat(PNProps.double(spec["min_velocity"]) ?? 300),
                    direction: direction ?? PNProps.string(spec["direction"]) ?? "any"
                )
                entries[ObjectIdentifier(recognizer)] = entry
                recognizer.delegate = self
                recognizer.cancelsTouchesInView = false
                recognizer.addTarget(self, action: #selector(handle(_:)))
                view.addGestureRecognizer(recognizer)
                state.gestureRecognizers.append(recognizer)
                built[index, default: []].append(recognizer)
            }
        }
        for (index, spec) in list.enumerated() {
            guard let recognizers = built[index] else { continue }
            for wait in ((spec["wait_for"] as? [Any]) ?? []).compactMap({ PNProps.int($0) }) {
                guard wait != index, let others = built[wait] else { continue }
                for recognizer in recognizers {
                    for other in others {
                        recognizer.require(toFail: other)
                    }
                }
            }
        }
        view.isUserInteractionEnabled = true
    }

    /// Remove every recognizer previously installed on `view`.
    public func unwire(view: UIView) {
        guard let state = PNViewState.existing(for: view) else { return }
        for recognizer in state.gestureRecognizers {
            recognizer.removeTarget(self, action: nil)
            view.removeGestureRecognizer(recognizer)
            entries.removeValue(forKey: ObjectIdentifier(recognizer))
        }
        state.gestureRecognizers = []
    }

    // MARK: - Recognizer construction

    /// Build the recognizer(s) for one spec as `(recognizer, direction)`
    /// pairs. `direction` is set only for swipe / fling recognizers: a
    /// `UISwipeGestureRecognizer` reports its configured mask rather than
    /// the direction it resolved, so `direction = "any"` installs one
    /// recognizer per direction and tags each with its own name.
    func makeRecognizers(_ spec: [String: Any]) -> [(UIGestureRecognizer, String?)] {
        switch PNProps.string(spec["kind"]) ?? "" {
        case "tap":
            let tap = UITapGestureRecognizer()
            tap.numberOfTapsRequired = max(1, PNProps.int(spec["n_taps"]) ?? 1)
            return [(tap, nil)]
        case "long_press":
            let press = UILongPressGestureRecognizer()
            press.minimumPressDuration = max(0.01, (PNProps.double(spec["min_duration_ms"]) ?? 500) / 1000)
            press.allowableMovement = CGFloat(PNProps.double(spec["max_distance"]) ?? 12)
            return [(press, nil)]
        case "pan":
            return [(PNPanGestureRecognizer(config: PNPanConfig(spec)), nil)]
        case "swipe", "fling":
            let requested = PNProps.string(spec["direction"]) ?? "any"
            let directions = PNGestureCoordinator.swipeDirectionNames.contains(requested)
                ? [requested]
                : PNGestureCoordinator.swipeDirectionNames
            let touches = max(1, PNProps.int(spec["n_pointers"]) ?? 1)
            return directions.map { name in
                let swipe = UISwipeGestureRecognizer()
                swipe.direction = PNGestureCoordinator.swipeDirection(name)
                swipe.numberOfTouchesRequired = touches
                return (swipe, name)
            }
        case "pinch":
            return [(UIPinchGestureRecognizer(), nil)]
        case "rotation":
            return [(UIRotationGestureRecognizer(), nil)]
        default:
            return []
        }
    }

    /// The single-direction names a swipe spec may request.
    public static let swipeDirectionNames = ["left", "right", "up", "down"]

    /// Map a Python direction name to `UISwipeGestureRecognizer.Direction`.
    public static func swipeDirection(_ name: String) -> UISwipeGestureRecognizer.Direction {
        switch name {
        case "left": return .left
        case "right": return .right
        case "up": return .up
        case "down": return .down
        default: return [.left, .right, .up, .down]
        }
    }

    // MARK: - Relationship lookups (exposed for tests)

    /// The spec index recorded for `recognizer`, if it was installed by the coordinator.
    public func index(of recognizer: UIGestureRecognizer) -> Int? {
        entries[ObjectIdentifier(recognizer)]?.index
    }

    /// Whether the two recognizers are allowed to recognize together.
    public func allowsSimultaneous(_ a: UIGestureRecognizer, _ b: UIGestureRecognizer) -> Bool {
        guard let ea = entries[ObjectIdentifier(a)], let eb = entries[ObjectIdentifier(b)] else {
            // One side isn't ours (Pressable, scroll view): don't block it.
            return true
        }
        if a.view !== b.view { return true }
        return ea.simultaneous.contains(eb.index) || eb.simultaneous.contains(ea.index)
    }

    // MARK: - UIGestureRecognizerDelegate

    public func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        allowsSimultaneous(gestureRecognizer, other)
    }

    // MARK: - Emission

    @objc private func handle(_ recognizer: UIGestureRecognizer) {
        emit(recognizer, state: recognizer.state)
    }

    /// Emit the payload for `recognizer` as if it were in `state` (tests).
    func emitForTesting(_ recognizer: UIGestureRecognizer, state: UIGestureRecognizer.State) {
        emit(recognizer, state: state)
    }

    private func emit(_ recognizer: UIGestureRecognizer, state recognizerState: UIGestureRecognizer.State) {
        guard let view = recognizer.view, let entry = entries[ObjectIdentifier(recognizer)] else { return }
        let location = recognizer.location(in: view)
        let absolute = recognizer.location(in: nil)
        var payload: [String: Any] = [
            "kind": entry.kind,
            "x": Double(location.x),
            "y": Double(location.y),
            "absolute_x": Double(absolute.x),
            "absolute_y": Double(absolute.y),
            "translation_x": 0.0,
            "translation_y": 0.0,
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "scale": 1.0,
            "rotation": 0.0,
            "pointer_count": recognizer.numberOfTouches,
            "direction": NSNull(),
        ]
        var state = PNGestureCoordinator.stateName(recognizerState)
        switch recognizer {
        case let pan as UIPanGestureRecognizer:
            let translation = pan.translation(in: view)
            let velocity = pan.velocity(in: view)
            payload["translation_x"] = Double(translation.x)
            payload["translation_y"] = Double(translation.y)
            payload["velocity_x"] = Double(velocity.x)
            payload["velocity_y"] = Double(velocity.y)
        case let pinch as UIPinchGestureRecognizer:
            payload["scale"] = Double(pinch.scale)
            payload["velocity_x"] = Double(pinch.velocity)
        case let rotation as UIRotationGestureRecognizer:
            payload["rotation"] = Double(rotation.rotation)
            payload["velocity_x"] = Double(rotation.velocity)
        case let swipe as UISwipeGestureRecognizer:
            // UIKit reports swipes as a single `.ended`; Python expects `ended`.
            guard recognizerState == .ended || recognizerState == .recognized else { return }
            state = "ended"
            payload["direction"] = entry.direction
            payload["pointer_count"] = max(1, swipe.numberOfTouchesRequired)
        case is UITapGestureRecognizer:
            guard recognizerState == .ended || recognizerState == .recognized else { return }
            state = "ended"
        default:
            break
        }
        guard state != "possible" else { return }
        payload["state"] = state
        PNEvents.emit(view, "gesture:\(entry.index)", [payload])
    }

    static func stateName(_ state: UIGestureRecognizer.State) -> String {
        switch state {
        case .began: return "began"
        case .changed: return "changed"
        case .ended: return "ended"
        case .cancelled: return "cancelled"
        case .failed: return "failed"
        default: return "possible"
        }
    }

    /// The direction name recorded for a swipe / fling recognizer (exposed for tests).
    public func direction(of recognizer: UIGestureRecognizer) -> String? {
        guard let entry = entries[ObjectIdentifier(recognizer)], entry.kind == "swipe" || entry.kind == "fling" else {
            return nil
        }
        return entry.direction
    }
}

/// The activation rules of a `pan` spec (React Native Gesture Handler's).
public struct PNPanConfig: Equatable {
    /// `[negative | nil, positive | nil]`; crossing either bound is strict.
    public struct Offset: Equatable {
        public var negative: Double?
        public var positive: Double?
        /// Whether `value` lies outside the bounds.
        public func crossed(by value: Double) -> Bool {
            (negative.map { value < $0 } ?? false) || (positive.map { value > $0 } ?? false)
        }
        init?(_ raw: Any?) {
            guard let list = raw as? [Any], list.count == 2 else { return nil }
            negative = PNProps.double(list[0]).flatMap { $0.isFinite ? $0 : nil }
            positive = PNProps.double(list[1]).flatMap { $0.isFinite ? $0 : nil }
            if negative == nil && positive == nil { return nil }
        }
    }

    public var minDistance: Double?
    public var minPointers: Int
    public var maxPointers: Int?
    public var activeX: Offset?
    public var activeY: Offset?
    public var failX: Offset?
    public var failY: Offset?
    /// Points per second.
    public var minVelocity: Double?

    public init(_ spec: [String: Any]) {
        minDistance = PNProps.double(spec["min_distance"]).flatMap { $0.isFinite ? max(0, $0) : nil }
        minPointers = max(1, PNProps.int(spec["min_pointers"]) ?? 1)
        maxPointers = PNProps.int(spec["max_pointers"]).map { max(minPointers, $0) }
        activeX = Offset(spec["active_offset_x"])
        activeY = Offset(spec["active_offset_y"])
        failX = Offset(spec["fail_offset_x"])
        failY = Offset(spec["fail_offset_y"])
        minVelocity = PNProps.double(spec["min_velocity"]).flatMap { $0.isFinite ? max(0, $0) : nil }
    }

    /// Whether travel `(dx, dy)` fails the interaction.
    public func fails(dx: Double, dy: Double) -> Bool {
        (failX?.crossed(by: dx) ?? false) || (failY?.crossed(by: dy) ?? false)
    }

    /// Whether travel `(dx, dy)` at `speed` points/second activates the pan.
    public func activates(dx: Double, dy: Double, speed: Double) -> Bool {
        if activeX?.crossed(by: dx) ?? false { return true }
        if activeY?.crossed(by: dy) ?? false { return true }
        if let distance = minDistance, hypot(dx, dy) >= distance { return true }
        if let velocity = minVelocity, speed >= velocity { return true }
        // Nothing to wait for: any movement activates.
        return activeX == nil && activeY == nil && minDistance == nil && minVelocity == nil
    }
}

/// A pan recognizer that applies `PNPanConfig` before UIKit may begin.
///
/// Travel is measured from the first touch in window space. A crossed
/// fail offset fails the recognizer for the rest of the interaction; once
/// an activation criterion holds the recognizer begins with its
/// translation reset, so `translation_x`/`translation_y` count from the
/// activation point. Extra touches beyond `max_pointers` fail an inactive
/// pan and cancel an active one.
final class PNPanGestureRecognizer: UIPanGestureRecognizer {
    let config: PNPanConfig
    private var origin: CGPoint?
    private var lastSample: (CGPoint, TimeInterval)?
    private(set) var speed: Double = 0
    private(set) var activationSatisfied = false
    private var failedForInteraction = false

    /// Back-compatible accessor for the plain distance threshold.
    var minDistance: CGFloat { CGFloat(config.minDistance ?? 0) }

    init(config: PNPanConfig) {
        self.config = config
        super.init(target: nil, action: nil)
        minimumNumberOfTouches = config.minPointers
        if let maximum = config.maxPointers { maximumNumberOfTouches = maximum }
    }

    /// Only the activation rules begin the pan (see `touchesMoved`).
    /// UIKit's own pan announces `.began` once, after about ten points of
    /// travel, which can come before an offset rule is met; while the pan
    /// is possible those announcements are ignored, and after it began
    /// they're treated as changes so the action never sees two begins.
    override var state: UIGestureRecognizer.State {
        get { super.state }
        set {
            if newValue == .began || newValue == .changed {
                if super.state == .possible { return }
                super.state = .changed
                return
            }
            super.state = newValue
        }
    }

    override func reset() {
        super.reset()
        origin = nil
        lastSample = nil
        speed = 0
        activationSatisfied = false
        failedForInteraction = false
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesBegan(touches, with: event)
        if origin == nil, let touch = touches.first {
            origin = touch.location(in: nil)
            lastSample = (touch.location(in: nil), touch.timestamp)
        }
        if let maximum = config.maxPointers, event.allTouches?.filter({ $0.phase != .ended && $0.phase != .cancelled }).count ?? 0 > maximum {
            if super.state == .possible {
                failedForInteraction = true
                super.state = .failed
            } else if super.state == .began || super.state == .changed {
                super.state = .cancelled
            }
        }
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent) {
        if super.state == .possible, !failedForInteraction, let origin = origin, let touch = touches.first {
            let point = touch.location(in: nil)
            if let (last, time) = lastSample, touch.timestamp > time {
                speed = Double(hypot(point.x - last.x, point.y - last.y)) / (touch.timestamp - time)
            }
            lastSample = (point, touch.timestamp)
            let dx = Double(point.x - origin.x), dy = Double(point.y - origin.y)
            if config.fails(dx: dx, dy: dy) {
                failedForInteraction = true
                super.state = .failed
                return
            }
            if !activationSatisfied, config.activates(dx: dx, dy: dy, speed: speed) {
                activationSatisfied = true
                // Translation is measured from the activation point.
                if let view = view { setTranslation(.zero, in: view) }
                super.state = .began
            }
        }
        super.touchesMoved(touches, with: event)
    }

    /// Feed one synthetic move (window coordinates) to the activation rules; exposed for tests.
    func evaluate(dx: Double, dy: Double, speed: Double) -> UIGestureRecognizer.State {
        if failedForInteraction { return .failed }
        if config.fails(dx: dx, dy: dy) { failedForInteraction = true; return .failed }
        if config.activates(dx: dx, dy: dy, speed: speed) { activationSatisfied = true; return .began }
        return .possible
    }
}
