import UIKit

/// Drives the `animate(tag, request)` protocol for animatable props
/// (`opacity`, `background_color`, `color`, `translate_x`, `translate_y`,
/// `scale`, `scale_x`, `scale_y`, `rotate`, `rotate_x`, `rotate_y`).
///
/// - `set` applies one Python-driven frame immediately.
/// - `start` runs `timing` / `spring` with `UIViewPropertyAnimator` and
///   `decay` with a display-link integrator; completion posts
///   `callback("animation", 0, "", {"id": n, "finished": bool})`.
/// - `cancel` stops the animation and returns the presentation value.
///
/// Transform channels are stored per view in
/// `PNViewState.animatedTransform` and composed with the static
/// `transform` prop by `PNTransform`, so binding `translate_x` and
/// `translate_y` together (or on top of a static `rotate`) works.
public final class PNAnimator {
    public static let shared = PNAnimator()

    /// Prop names accepted by `set` and `start`.
    public static let animatableProps: Set<String> = [
        "opacity", "background_color", "color",
        "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate", "rotate_x", "rotate_y",
    ]

    /// Transform channels routed through `PNTransform.compose`.
    static let transformProps: Set<String> = Set(PNTransform.animatedChannels)

    final class Running {
        weak var view: UIView?
        let prop: String
        var animator: UIViewPropertyAnimator?
        var decay: PNDecayDriver?
        var sampled: PNSampledDriver?
        init(view: UIView, prop: String) {
            self.view = view
            self.prop = prop
        }
    }

    private var running: [Int64: Running] = [:]

    private init() {}

    // MARK: - Request routing

    /// Handle one decoded `animate` request for the view with `tag`.
    public func handle(tag: Int64, request: [String: Any]) -> Any? {
        let op = PNProps.string(request["op"]) ?? ""
        switch op {
        case "graph":
            PNAnimationGraph.install(request["graph"] as? [String: Any] ?? [:])
            return nil
        case "set":
            guard let record = PNViewRegistry.shared.resolve(tag), let prop = PNProps.string(request["prop"]) else { return nil }
            record.manager.setAnimatedProperty(view: record.view, prop: prop, value: request["value"])
            return nil
        case "start":
            guard let record = PNViewRegistry.shared.resolve(tag), let prop = PNProps.string(request["prop"]),
                  let id = PNProps.int(request["id"])
            else { return ["ok": false] }
            let spec = PNProps.dict(request["spec"]) ?? [:]
            if prop.hasPrefix("_pn_graph:"), let node = Int64(prop.dropFirst(10)) {
                return ["ok": PNAnimationGraph.start(Int64(id), node: node, spec: spec)]
            }
            let ok = record.manager.startAnimation(view: record.view, id: Int64(id), prop: prop, spec: spec)
            return ["ok": ok]
        case "cancel":
            guard let id = PNProps.int(request["id"]) else { return nil }
            if let value = PNAnimationGraph.cancel(Int64(id)) { return ["value": value] }
            let value: Any?
            if let record = PNViewRegistry.shared.resolve(tag) {
                value = record.manager.cancelAnimation(view: record.view, id: Int64(id))
            } else {
                value = cancel(id: Int64(id))
            }
            guard let value = value else { return nil }
            return ["value": value]
        default:
            PNLog.rateLimited(PNLog.animation, key: "op:\(op)", "unknown animate op '\(op)'")
            return nil
        }
    }

    // MARK: - Frame application

    /// Apply one value of `prop` to `view` immediately.
    public func applyValue(view: UIView, prop: String, value: Any?) {
        if prop.hasPrefix("_pn_graph:"), let node = Int64(prop.dropFirst(10)), let value = PNProps.double(value) {
            PNAnimationGraph.set(node, value)
            return
        }
        switch prop {
        case "opacity":
            if let v = PNProps.double(value) { view.alpha = CGFloat(v) }
        case "background_color":
            if let color = PNColor.parse(value) { view.backgroundColor = color }
        case "color":
            guard let color = PNColor.parse(value) else { return }
            if let label = view as? UILabel {
                label.textColor = color
            } else if let field = view as? UITextField {
                field.textColor = color
            } else if let textView = view as? UITextView {
                textView.textColor = color
            } else if let button = view as? UIButton {
                button.setTitleColor(color, for: .normal)
            }
        case _ where PNAnimator.transformProps.contains(prop):
            guard let v = PNProps.double(value), v.isFinite else { return }
            setTransformChannel(view: view, channel: prop, value: v)
        default:
            PNLog.once(PNLog.animation, key: "prop:\(prop)", "ignoring unknown animated prop '\(prop)'")
        }
    }

    /// Record one animated transform channel and recompose the layer transform.
    func setTransformChannel(view: UIView, channel: String, value: Double) {
        guard let state = PNViewState.existing(for: view) else {
            view.layer.transform = PNTransform.compose(base: nil, animated: [channel: value])
            return
        }
        state.animatedTransform[channel] = value
        PNTransform.refresh(view)
    }

    /// Read the value of `prop` currently on screen (presentation layer when animating).
    public func presentationValue(view: UIView, prop: String) -> Any? {
        let layer = view.layer.presentation() ?? view.layer
        switch prop {
        case "opacity":
            return Double(layer.opacity)
        case "background_color":
            return layer.backgroundColor.map { PNColor.hexString(UIColor(cgColor: $0)) }
        case "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate":
            guard let overlay = PNTransform.presentedOverlay(view) else {
                return PNViewState.existing(for: view)?.animatedTransform[prop]
            }
            let parts = PNTransform.decompose(overlay)
            switch prop {
            case "translate_x": return Double(parts.translateX)
            case "translate_y": return Double(parts.translateY)
            case "scale", "scale_x": return Double(parts.scaleX)
            case "scale_y": return Double(parts.scaleY)
            default: return Double(parts.rotateDegrees)
            }
        case _ where PNAnimator.transformProps.contains(prop):
            return PNViewState.existing(for: view)?.animatedTransform[prop]
        default:
            return nil
        }
    }

    // MARK: - Start / cancel

    /// Start a native animation. Returns `false` when the spec must be
    /// ticked by Python instead.
    public func start(view: UIView, id: Int64, prop: String, spec: [String: Any]) -> Bool {
        guard PNAnimator.animatableProps.contains(prop), Thread.isMainThread else { return false }
        let kind = PNProps.string(spec["kind"] ?? spec["type"]) ?? ""
        let entry = Running(view: view, prop: prop)
        switch kind {
        case "timing", "spring":
            guard spec["to"] != nil else { return false }
            if kind == "timing", PNEasing.needsSampling(spec["easing"]) {
                // Curves UIKit can't express (bounce) are sampled on a display link.
                guard let from = PNProps.double(spec["from"] ?? presentationValue(view: view, prop: prop)), let to = PNProps.double(spec["to"]),
                      let function = PNEasing.function(spec["easing"]) else { return false }
                let driver = PNSampledDriver(
                    from: from, to: to, durationMs: PNProps.double(spec["duration_ms"]) ?? 300,
                    delayMs: PNProps.double(spec["delay_ms"]) ?? 0, easing: function
                ) { [weak self, weak view] value in
                    guard let self = self, let view = view else { return }
                    self.applyValue(view: view, prop: prop, value: value)
                } completion: { [weak self] in
                    guard let self = self, self.running[id] != nil else { return }
                    self.running.removeValue(forKey: id)
                    PNAnimator.reportCompletion(id: id, finished: true)
                }
                entry.sampled = driver
                running[id] = entry
                driver.start()
                return true
            }
            guard let timing = PNAnimator.timingParameters(kind: kind, spec: spec) else { return false }
            if let from = spec["from"] { applyValue(view: view, prop: prop, value: from) }
            let animator = UIViewPropertyAnimator(duration: timing.duration, timingParameters: timing.parameters)
            animator.isUserInteractionEnabled = true
            animator.addAnimations { [weak self, weak view] in
                guard let self = self, let view = view else { return }
                self.applyValue(view: view, prop: prop, value: spec["to"])
            }
            animator.addCompletion { [weak self] position in
                guard let self = self, self.running[id] != nil else { return }
                self.running.removeValue(forKey: id)
                PNAnimator.reportCompletion(id: id, finished: position == .end)
            }
            entry.animator = animator
            running[id] = entry
            let delay = max(0, (PNProps.double(spec["delay_ms"]) ?? 0) / 1000)
            animator.startAnimation(afterDelay: delay)
            return true
        case "decay":
            guard let velocity = PNProps.double(spec["velocity"]) else { return false }
            let from = PNProps.double(spec["from"]) ?? PNProps.double(presentationValue(view: view, prop: prop)) ?? 0
            let deceleration = PNProps.double(spec["deceleration"]) ?? PNDecayDriver.defaultDeceleration
            let driver = PNDecayDriver(from: from, velocity: velocity, deceleration: deceleration) { [weak self, weak view] value in
                guard let self = self, let view = view else { return }
                self.applyValue(view: view, prop: prop, value: value)
            } completion: { [weak self] in
                guard let self = self, self.running[id] != nil else { return }
                self.running.removeValue(forKey: id)
                PNAnimator.reportCompletion(id: id, finished: true)
            }
            entry.decay = driver
            running[id] = entry
            driver.start()
            return true
        default:
            return false
        }
    }

    /// Stop animation `id`, leaving the view at its presentation value.
    /// Returns that value (or `nil` when the animation isn't running).
    public func cancel(id: Int64) -> Any? {
        guard let entry = running.removeValue(forKey: id) else { return nil }
        var value: Any?
        if let view = entry.view {
            value = presentationValue(view: view, prop: entry.prop)
        }
        if let animator = entry.animator {
            animator.stopAnimation(true)
        }
        if let decay = entry.decay {
            value = decay.currentValue
            decay.stop()
        }
        if let sampled = entry.sampled {
            value = sampled.currentValue
            sampled.stop()
        }
        if let view = entry.view, let value = value {
            view.layer.removeAllAnimations()
            applyValue(view: view, prop: entry.prop, value: value)
        }
        return value
    }

    /// Drop bookkeeping for animations targeting `view` (on destroy).
    public func forget(view: UIView) {
        for (id, entry) in running where entry.view === view || entry.view == nil {
            entry.animator?.stopAnimation(true)
            entry.decay?.stop()
            entry.sampled?.stop()
            running.removeValue(forKey: id)
        }
    }

    // MARK: - Helpers

    static func reportCompletion(id: Int64, finished: Bool) {
        PNBridge.shared.callPython(kind: "animation", tag: 0, name: "", payload: PNJSON.encode(["id": id, "finished": finished]))
    }

    /// Resolve `timing` / `spring` specs to UIKit timing parameters, or
    /// `nil` when the easing isn't one UIKit can run (Python validates
    /// names; nothing falls back silently).
    static func timingParameters(kind: String, spec: [String: Any]) -> (duration: TimeInterval, parameters: UITimingCurveProvider)? {
        if kind == "spring" {
            let stiffness = max(1e-3, PNProps.double(spec["stiffness"]) ?? 100)
            let damping = max(1e-3, PNProps.double(spec["damping"]) ?? 10)
            let mass = max(1e-3, PNProps.double(spec["mass"]) ?? 1)
            let omega0 = sqrt(stiffness / mass)
            let zeta = damping / (2 * sqrt(stiffness * mass))
            let duration = zeta < 1 ? min(10, max(0.15, 4 / max(0.05, zeta * omega0))) : min(10, max(0.15, 4 / omega0))
            let distance = abs((PNProps.double(spec["to"]) ?? 0) - (PNProps.double(spec["from"]) ?? 0))
            let v0 = PNProps.double(spec["initial_velocity"]) ?? 0
            let normalized = distance > 1e-9 ? v0 / distance : 0
            let parameters = UISpringTimingParameters(
                mass: CGFloat(mass), stiffness: CGFloat(stiffness), damping: CGFloat(damping),
                initialVelocity: CGVector(dx: normalized, dy: normalized)
            )
            return (duration, parameters)
        }
        let duration = max(0, (PNProps.double(spec["duration_ms"]) ?? 300) / 1000)
        guard let curve = curve(for: spec["easing"]) else { return nil }
        return (duration, curve)
    }

    /// Map a wire easing (a name or `[x1, y1, x2, y2]`) to a UIKit curve;
    /// `nil` for `bounce` (sampled instead) and for unknown names.
    static func curve(for easing: Any?) -> UITimingCurveProvider? {
        guard let points = PNEasing.controlPoints(easing) else { return nil }
        return UICubicTimingParameters(controlPoint1: CGPoint(x: points.0, y: points.1), controlPoint2: CGPoint(x: points.2, y: points.3))
    }
}

/// The wire easing vocabulary shared with Python's `Easing`:
/// `linear`, `ease` (an alias of `ease_in`), `ease_in`, `ease_out`,
/// `ease_in_out`, `quad` (`t^2`), `cubic` (`t^3`), `bounce` (Penner
/// bounce-out), or a bare `[x1, y1, x2, y2]` cubic bezier.
public enum PNEasing {
    /// Cubic bezier control points for every curve that has them. `quad`
    /// and `cubic` are exact: with `x1 = 1/3, x2 = 2/3` the bezier's x is
    /// linear in `u`, and `y1 = 0, y2 = 1/3` (or `0`) makes y `u^2` (`u^3`).
    public static let named: [String: (Double, Double, Double, Double)] = [
        "linear": (0, 0, 1, 1),
        "ease": (0.42, 0, 1, 1),
        "ease_in": (0.42, 0, 1, 1),
        "ease_out": (0, 0, 0.58, 1),
        "ease_in_out": (0.42, 0, 0.58, 1),
        "quad": (1.0 / 3.0, 0, 2.0 / 3.0, 1.0 / 3.0),
        "cubic": (1.0 / 3.0, 0, 2.0 / 3.0, 0),
    ]

    /// Control points for `easing`, or `nil` when it has none (`bounce`,
    /// unknown names, malformed arrays). A missing easing is `ease_in_out`.
    public static func controlPoints(_ easing: Any?) -> (Double, Double, Double, Double)? {
        switch easing {
        case nil, is NSNull:
            return named["ease_in_out"]
        case let points as [Any]:
            let values = points.compactMap { PNProps.double($0) }
            guard values.count == 4, values.allSatisfy({ $0.isFinite }) else { return nil }
            return (values[0], values[1], values[2], values[3])
        case let name as String:
            return named[name]
        default:
            return nil
        }
    }

    /// Whether `easing` is a curve this platform can run at all.
    public static func isValid(_ easing: Any?) -> Bool {
        controlPoints(easing) != nil || (easing as? String) == "bounce"
    }

    /// Whether the curve has no bezier form and must be sampled per frame.
    public static func needsSampling(_ easing: Any?) -> Bool {
        (easing as? String) == "bounce"
    }

    /// `progress -> eased` for `easing`, or `nil` when unknown.
    public static func function(_ easing: Any?) -> ((Double) -> Double)? {
        if needsSampling(easing) { return bounce }
        guard let points = controlPoints(easing) else { return nil }
        return { t in PNGraphDriver.bezier(t, CGPoint(x: points.0, y: points.1), CGPoint(x: points.2, y: points.3)) }
    }

    /// Robert Penner's bounce-out, as React Native's `Easing.bounce`.
    public static func bounce(_ t: Double) -> Double {
        if t < 1 / 2.75 { return 7.5625 * t * t }
        if t < 2 / 2.75 { let u = t - 1.5 / 2.75; return 7.5625 * u * u + 0.75 }
        if t < 2.5 / 2.75 { let u = t - 2.25 / 2.75; return 7.5625 * u * u + 0.9375 }
        let u = t - 2.625 / 2.75
        return 7.5625 * u * u + 0.984375
    }
}

/// Runs a `timing` animation whose curve UIKit can't express (bounce) by
/// sampling the easing function on a display link.
public final class PNSampledDriver {
    private(set) var currentValue: Double
    let from: Double, to: Double, durationMs: Double, delayMs: Double
    private let easing: (Double) -> Double
    private let frame: (Double) -> Void
    private let completion: () -> Void
    private var link: CADisplayLink?
    private var startTime: CFTimeInterval = 0

    init(from: Double, to: Double, durationMs: Double, delayMs: Double, easing: @escaping (Double) -> Double,
         frame: @escaping (Double) -> Void, completion: @escaping () -> Void) {
        self.from = from; self.to = to
        self.durationMs = max(0, durationMs); self.delayMs = max(0, delayMs)
        self.easing = easing; self.frame = frame; self.completion = completion
        currentValue = from
    }

    func start() {
        startTime = CACurrentMediaTime()
        let link = CADisplayLink(target: self, selector: #selector(tick(_:)))
        link.add(to: .main, forMode: .common)
        self.link = link
    }

    func stop() {
        link?.invalidate()
        link = nil
    }

    /// Advance to `elapsedMs` since start; returns `true` when finished.
    @discardableResult
    func advance(elapsedMs: Double) -> Bool {
        let active = elapsedMs - delayMs
        guard active >= 0 else { return false }
        let progress = durationMs <= 0 ? 1 : min(1, active / durationMs)
        let done = progress >= 1 || UIAccessibility.isReduceMotionEnabled
        currentValue = done ? to : from + (to - from) * easing(progress)
        frame(currentValue)
        return done
    }

    @objc private func tick(_ link: CADisplayLink) {
        if advance(elapsedMs: max(0, link.targetTimestamp - startTime) * 1000) {
            stop()
            completion()
        }
    }
}

/// Integrates React Native's `decay` model on a `CADisplayLink`.
///
/// Velocity is in points per millisecond and decays as
/// `v(t) = v0 * d^t` (`t` in milliseconds, `d` defaulting to `0.998`),
/// so the closed-form position is `x(t) = x0 + v0 * (1 - d^t) / (1 - d)`
/// and the projected rest point is `x0 + v0 / (1 - d)`. The driver stops
/// once `|v| < 0.001` pt/ms or the value is within `0.1` of the rest point.
public final class PNDecayDriver {
    public static let defaultDeceleration = 0.998
    public static let restVelocity = 0.001
    public static let restDistance = 0.1

    private(set) var currentValue: Double
    let from: Double
    let velocity0: Double
    let deceleration: Double
    private let frame: (Double) -> Void
    private let completion: () -> Void
    private var link: CADisplayLink?
    private var startTime: CFTimeInterval = 0

    init(from: Double, velocity: Double, deceleration: Double, frame: @escaping (Double) -> Void, completion: @escaping () -> Void) {
        self.from = from
        currentValue = from
        velocity0 = velocity
        self.deceleration = PNDecayDriver.clamp(deceleration)
        self.frame = frame
        self.completion = completion
    }

    /// Keep `d` strictly inside `(0, 1)` so the closed form stays finite.
    static func clamp(_ deceleration: Double) -> Double {
        guard deceleration.isFinite else { return defaultDeceleration }
        return min(0.999_999, max(0.000_001, deceleration))
    }

    /// `v0 * d^t` for `t` in milliseconds.
    public static func velocity(velocity v0: Double, deceleration d: Double, elapsedMs t: Double) -> Double {
        v0 * pow(clamp(d), max(0, t))
    }

    /// `x0 + v0 * (1 - d^t) / (1 - d)` for `t` in milliseconds.
    public static func position(from x0: Double, velocity v0: Double, deceleration d: Double, elapsedMs t: Double) -> Double {
        let d = clamp(d)
        return x0 + v0 * (1 - pow(d, max(0, t))) / (1 - d)
    }

    /// `x0 + v0 / (1 - d)`: where the value comes to rest.
    public static func finalValue(from x0: Double, velocity v0: Double, deceleration d: Double) -> Double {
        let d = clamp(d)
        return x0 + v0 / (1 - d)
    }

    /// Whether the animation is finished at `t` milliseconds.
    public static func isAtRest(from x0: Double, velocity v0: Double, deceleration d: Double, elapsedMs t: Double) -> Bool {
        abs(velocity(velocity: v0, deceleration: d, elapsedMs: t)) < restVelocity
            || abs(position(from: x0, velocity: v0, deceleration: d, elapsedMs: t) - finalValue(from: x0, velocity: v0, deceleration: d)) < restDistance
    }

    /// The rest point of this driver.
    public var finalValue: Double { PNDecayDriver.finalValue(from: from, velocity: velocity0, deceleration: deceleration) }

    func start() {
        startTime = CACurrentMediaTime()
        if abs(velocity0) < PNDecayDriver.restVelocity {
            completion()
            return
        }
        let link = CADisplayLink(target: self, selector: #selector(tick(_:)))
        link.add(to: .main, forMode: .common)
        self.link = link
    }

    func stop() {
        link?.invalidate()
        link = nil
    }

    /// Advance to `elapsedMs` since start; returns `true` when finished.
    @discardableResult
    func advance(elapsedMs: Double) -> Bool {
        let done = PNDecayDriver.isAtRest(from: from, velocity: velocity0, deceleration: deceleration, elapsedMs: elapsedMs)
        currentValue = done ? finalValue : PNDecayDriver.position(from: from, velocity: velocity0, deceleration: deceleration, elapsedMs: elapsedMs)
        frame(currentValue)
        return done
    }

    @objc private func tick(_ link: CADisplayLink) {
        let elapsed = max(0, link.targetTimestamp - startTime) * 1000
        if advance(elapsedMs: elapsed) {
            stop()
            completion()
        }
    }
}
