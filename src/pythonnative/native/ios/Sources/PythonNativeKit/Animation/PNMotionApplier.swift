import UIKit

/// Applies the paint props the renderer core's motion runtime writes (RFC 0009).
///
/// A `prop` write lands exactly as if a commit had changed just that key:
/// the value is merged into the view's props and goes through the
/// manager's `apply`, so every paint prop a static update supports
/// (`background_color`, border colors and radii, shadows, `tint_color`,
/// text colors and shadows, `z_index`, ...) animates the same way. `null`
/// restores the prop's default; the core sends the committed static value
/// explicitly when there is one. A write wins over the static value until
/// the core writes the key again, and `transform` replaces the static list
/// while set (there is no per-channel composition).
///
/// `opacity` and `transform` take a fast path, since they're written every
/// frame by most animations.
public enum PNMotionApplier {
    /// Apply one written value of `prop` to `view` through `manager`.
    public static func apply(view: UIView, manager: PNComponentManager, prop: String, value: Any?) {
        let value: Any = value ?? NSNull()
        if let state = PNViewState.existing(for: view) {
            if value is NSNull {
                state.props.removeValue(forKey: prop)
            } else {
                state.props[prop] = value
            }
        }
        switch prop {
        case "opacity":
            let opacity = PNProps.double(value) ?? 1
            view.alpha = CGFloat(opacity.isFinite ? opacity : 1)
        case "transform":
            PNTransform.apply(view, spec: value is NSNull ? nil : value)
        default:
            _ = PNValues.takeDecodeFailure()
            manager.apply(view: view, props: [prop: value], initial: false)
            if let failure = PNValues.takeDecodeFailure() {
                PNLog.rateLimited(PNLog.animation, key: "write:\(prop)", "[motion] \(prop): \(failure)")
            }
        }
    }
}

/// The timing of a native animation described by a motion descriptor: a
/// layout preset (`item_entering`, ...) or a `shared_transition`.
///
/// `spring` wins (`duration` with `damping_ratio`, or the physical
/// `damping`, `stiffness`, and `mass`), then `duration` (milliseconds) with
/// `easing` (a name or four bezier control points), then the fallback.
struct PNMotionTiming {
    enum Curve: Equatable {
        case bezier(CGPoint, CGPoint)
        case spring(dampingRatio: CGFloat)
        case physical(mass: CGFloat, stiffness: CGFloat, damping: CGFloat)
    }

    var duration: TimeInterval
    var delay: TimeInterval
    var curve: Curve

    /// UIKit's push: about 0.35 s, ease in and out.
    static let push = PNMotionTiming(duration: 0.35, delay: 0, curve: .bezier(CGPoint(x: 0.42, y: 0), CGPoint(x: 0.58, y: 1)))

    init(duration: TimeInterval, delay: TimeInterval, curve: Curve) {
        self.duration = duration
        self.delay = delay
        self.curve = curve
    }

    /// Read `spec`, falling back to `fallback` for whatever it leaves out.
    init(_ spec: [String: Any]?, fallback: PNMotionTiming = .push) {
        self = fallback
        guard let spec = spec else { return }
        if let ms = PNProps.double(spec["delay"]), ms.isFinite { delay = max(0, ms / 1000) }
        if let spring = spec["spring"] as? [String: Any] {
            let ms = PNProps.double(spring["duration"]) ?? PNProps.double(spec["duration"])
            if let ratio = PNProps.double(spring["damping_ratio"]), ratio.isFinite {
                curve = .spring(dampingRatio: CGFloat(max(0.01, ratio)))
                if let ms = ms, ms.isFinite, ms > 0 { duration = ms / 1000 }
            } else {
                let mass = max(0.01, PNProps.double(spring["mass"]) ?? 1)
                let stiffness = max(0.01, PNProps.double(spring["stiffness"]) ?? 100)
                let damping = max(0, PNProps.double(spring["damping"]) ?? 10)
                curve = .physical(mass: CGFloat(mass), stiffness: CGFloat(stiffness), damping: CGFloat(damping))
                if let ms = ms, ms.isFinite, ms > 0 {
                    duration = ms / 1000
                } else {
                    duration = PNMotionTiming.settleTime(mass: mass, stiffness: stiffness, damping: damping)
                }
            }
            return
        }
        if let ms = PNProps.double(spec["duration"]), ms.isFinite { duration = max(0, ms / 1000) }
        if let easing = PNMotionTiming.bezier(spec["easing"]) { curve = easing }
    }

    /// A named curve or `[x1, y1, x2, y2]`; `nil` keeps the fallback.
    static func bezier(_ easing: Any?) -> Curve? {
        if let points = easing as? [Any], points.count == 4 {
            let p = points.map { CGFloat(PNProps.double($0) ?? 0) }
            return .bezier(CGPoint(x: min(1, max(0, p[0])), y: p[1]), CGPoint(x: min(1, max(0, p[2])), y: p[3]))
        }
        guard let name = easing as? String else { return nil }
        let points: (CGFloat, CGFloat, CGFloat, CGFloat)
        switch name {
        case "linear": points = (0, 0, 1, 1)
        case "ease", "ease_in": points = (0.42, 0, 1, 1)
        // A bounce isn't a cubic bezier, so UIKit's animators get ease-out.
        case "ease_out", "bounce": points = (0, 0, 0.58, 1)
        // The core's exact beziers for t² and t³.
        case "quad": points = (1.0 / 3.0, 0, 2.0 / 3.0, 1.0 / 3.0)
        case "cubic": points = (1.0 / 3.0, 0, 2.0 / 3.0, 0)
        default: points = (0.42, 0, 0.58, 1)
        }
        return .bezier(CGPoint(x: points.0, y: points.1), CGPoint(x: points.2, y: points.3))
    }

    /// Roughly when a physical spring comes within 0.1% of rest.
    static func settleTime(mass: Double, stiffness: Double, damping: Double) -> TimeInterval {
        let omega = (stiffness / mass).squareRoot()
        let zeta = damping / (2 * (stiffness * mass).squareRoot())
        guard omega > 0, zeta > 0 else { return 1 }
        return min(2, max(0.1, 6.9 / (min(zeta, 1) * omega)))
    }

    var timingParameters: UITimingCurveProvider {
        switch curve {
        case let .bezier(first, second):
            return UICubicTimingParameters(controlPoint1: first, controlPoint2: second)
        case let .spring(ratio):
            return UISpringTimingParameters(dampingRatio: ratio)
        case let .physical(mass, stiffness, damping):
            return UISpringTimingParameters(mass: mass, stiffness: stiffness, damping: damping, initialVelocity: .zero)
        }
    }

    /// A paused animator with this timing (the delay is the caller's).
    func makeAnimator() -> UIViewPropertyAnimator {
        UIViewPropertyAnimator(duration: duration, timingParameters: timingParameters)
    }

    /// Run `animations` now (their model values change immediately) with
    /// this timing, including the delay.
    func run(_ animations: @escaping () -> Void, completion: (() -> Void)? = nil) {
        guard delay > 0 else {
            let animator = makeAnimator()
            animator.addAnimations(animations)
            animator.addCompletion { _ in completion?() }
            animator.startAnimation()
            return
        }
        // UIView's block API runs the block at once and delays the animation.
        switch curve {
        case let .bezier(first, second):
            let option: UIView.AnimationOptions
            if first == .zero && second == CGPoint(x: 1, y: 1) {
                option = .curveLinear
            } else if first.x < 0.1 {
                option = .curveEaseOut
            } else if second.x > 0.9 {
                option = .curveEaseIn
            } else {
                option = .curveEaseInOut
            }
            UIView.animate(withDuration: duration, delay: delay, options: [option, .beginFromCurrentState], animations: animations) { _ in
                completion?()
            }
        case let .spring(ratio):
            UIView.animate(withDuration: duration, delay: delay, usingSpringWithDamping: ratio, initialSpringVelocity: 0,
                           options: [.beginFromCurrentState], animations: animations) { _ in completion?() }
        case let .physical(mass, stiffness, damping):
            let ratio = max(0.01, damping / (2 * (stiffness * mass).squareRoot()))
            UIView.animate(withDuration: duration, delay: delay, usingSpringWithDamping: min(1, ratio), initialSpringVelocity: 0,
                           options: [.beginFromCurrentState], animations: animations) { _ in completion?() }
        }
    }
}
