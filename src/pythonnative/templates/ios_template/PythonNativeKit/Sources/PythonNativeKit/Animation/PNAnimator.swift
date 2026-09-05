import UIKit

/// Drives the `animate(tag, request)` protocol for animatable props
/// (`opacity`, `background_color`, `color`, `translate_x`, `translate_y`,
/// `scale`, `scale_x`, `scale_y`, `rotate`).
///
/// - `set` applies one Python-driven frame immediately.
/// - `start` runs `timing` / `spring` with `UIViewPropertyAnimator` and
///   `decay` with a display-link integrator; completion posts
///   `callback("animation", 0, "", {"id": n, "finished": bool})`.
/// - `cancel` stops the animation and returns the presentation value.
public final class PNAnimator {
    public static let shared = PNAnimator()

    /// Prop names accepted by `set` and `start`.
    public static let animatableProps: Set<String> = [
        "opacity", "background_color", "color", "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate",
    ]

    final class Running {
        weak var view: UIView?
        let prop: String
        var animator: UIViewPropertyAnimator?
        var decay: PNDecayDriver?
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
        case "set":
            guard let record = PNViewRegistry.shared.resolve(tag), let prop = PNProps.string(request["prop"]) else { return nil }
            record.manager.setAnimatedProperty(view: record.view, prop: prop, value: request["value"])
            return nil
        case "start":
            guard let record = PNViewRegistry.shared.resolve(tag), let prop = PNProps.string(request["prop"]),
                  let id = PNProps.int(request["id"])
            else { return ["ok": false] }
            let spec = PNProps.dict(request["spec"]) ?? [:]
            let ok = record.manager.startAnimation(view: record.view, id: Int64(id), prop: prop, spec: spec)
            return ["ok": ok]
        case "cancel":
            guard let id = PNProps.int(request["id"]) else { return nil }
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
        case "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate":
            guard let v = PNProps.double(value), v.isFinite else { return }
            PNTransform.apply(view, spec: [[prop: v]])
        default:
            PNLog.once(PNLog.animation, key: "prop:\(prop)", "ignoring unknown animated prop '\(prop)'")
        }
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
            let t = layer.affineTransform()
            let parts = PNTransform.decompose(t)
            switch prop {
            case "translate_x": return Double(parts.translateX)
            case "translate_y": return Double(parts.translateY)
            case "scale", "scale_x": return Double(parts.scaleX)
            case "scale_y": return Double(parts.scaleY)
            default: return Double(parts.rotateDegrees)
            }
        default:
            return nil
        }
    }

    // MARK: - Start / cancel

    /// Start a native animation. Returns `false` when the spec must be
    /// ticked by Python instead.
    public func start(view: UIView, id: Int64, prop: String, spec: [String: Any]) -> Bool {
        guard PNAnimator.animatableProps.contains(prop), Thread.isMainThread else { return false }
        let kind = PNProps.string(spec["kind"]) ?? ""
        let entry = Running(view: view, prop: prop)
        switch kind {
        case "timing", "spring":
            guard spec["to"] != nil else { return false }
            if let from = spec["from"] { applyValue(view: view, prop: prop, value: from) }
            let timing = PNAnimator.timingParameters(kind: kind, spec: spec)
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
            guard let from = PNProps.double(spec["from"]), let velocity = PNProps.double(spec["velocity"]) else { return false }
            let deceleration = max(1e-6, PNProps.double(spec["deceleration"]) ?? 0.997)
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
            running.removeValue(forKey: id)
        }
    }

    // MARK: - Helpers

    static func reportCompletion(id: Int64, finished: Bool) {
        PNBridge.shared.callPython(kind: "animation", tag: 0, name: "", payload: PNJSON.encode(["id": id, "finished": finished]))
    }

    /// Resolve `timing` / `spring` specs to UIKit timing parameters.
    static func timingParameters(kind: String, spec: [String: Any]) -> (duration: TimeInterval, parameters: UITimingCurveProvider) {
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
        return (duration, curve(for: spec["easing"]))
    }

    /// Map an easing name (or `[x1, y1, x2, y2]` control points) to a timing curve.
    static func curve(for easing: Any?) -> UITimingCurveProvider {
        if let points = easing as? [Any], points.count == 4 {
            let values = points.compactMap { PNProps.double($0) }
            if values.count == 4 {
                return UICubicTimingParameters(
                    controlPoint1: CGPoint(x: values[0], y: values[1]), controlPoint2: CGPoint(x: values[2], y: values[3])
                )
            }
        }
        switch PNProps.string(easing) ?? "ease_in_out" {
        case "linear": return UICubicTimingParameters(animationCurve: .linear)
        case "ease_in", "ease_in_quad": return UICubicTimingParameters(animationCurve: .easeIn)
        case "ease_out", "ease_out_quad": return UICubicTimingParameters(animationCurve: .easeOut)
        case "ease", "ease_in_out": return UICubicTimingParameters(animationCurve: .easeInOut)
        case "bounce":
            // No CoreAnimation equivalent; approximate with an overshoot curve.
            return UICubicTimingParameters(controlPoint1: CGPoint(x: 0.34, y: 1.56), controlPoint2: CGPoint(x: 0.64, y: 1))
        default: return UICubicTimingParameters(animationCurve: .easeInOut)
        }
    }
}

/// Integrates the `decay` model on a `CADisplayLink`, mirroring the
/// Python ticker: `v(t) = v0 * e^(-k * 1000 * t)` with `t` in seconds and
/// `v0` in units per second, so the closed-form position is
/// `from + v0 / (k * 1000) * (1 - e^(-k * 1000 * t))`.
final class PNDecayDriver {
    private(set) var currentValue: Double
    private let from: Double
    private let velocity0: Double
    private let k: Double
    private let frame: (Double) -> Void
    private let completion: () -> Void
    private var link: CADisplayLink?
    private var startTime: CFTimeInterval = 0
    private let restVelocity = 0.001

    init(from: Double, velocity: Double, deceleration: Double, frame: @escaping (Double) -> Void, completion: @escaping () -> Void) {
        self.from = from
        currentValue = from
        velocity0 = velocity
        k = deceleration
        self.frame = frame
        self.completion = completion
    }

    func start() {
        startTime = CACurrentMediaTime()
        if abs(velocity0) < restVelocity {
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

    @objc private func tick(_ link: CADisplayLink) {
        let elapsed = max(0, link.targetTimestamp - startTime)
        let decayFactor = exp(-k * 1000 * elapsed)
        let velocity = velocity0 * decayFactor
        currentValue = from + velocity0 / (k * 1000) * (1 - decayFactor)
        frame(currentValue)
        if abs(velocity) < restVelocity {
            stop()
            completion()
        }
    }
}
