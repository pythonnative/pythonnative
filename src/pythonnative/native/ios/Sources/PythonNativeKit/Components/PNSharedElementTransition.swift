import UIKit
import PNCore

/// Two mounted views with the same `shared_tag` on the screens of one
/// push or pop, as `pn_core_shared_elements` pairs them (RFC 0009).
struct PNSharedElementPair {
    let name: String
    /// The view on the screen being left.
    let source: Int64
    /// The view on the screen being shown; it's the one that flies.
    let target: Int64
    let transition: [String: Any]?
    let sourceStyle: [String: Any]
    let targetStyle: [String: Any]
}

enum PNSharedElements {
    /// The shared elements between two screens of the surface.
    static func pairs(from: Int64, to: Int64) -> [PNSharedElementPair] {
        guard let raw = pn_core_shared_elements(PNCore.handle, PNCore.surface, from, to) else { return [] }
        defer { pn_core_free(raw) }
        return parse(String(cString: raw))
    }

    static func parse(_ json: String) -> [PNSharedElementPair] {
        guard let data = json.data(using: .utf8),
              let list = (try? JSONSerialization.jsonObject(with: data)) as? [Any] else { return [] }
        return list.compactMap { item in
            guard let pair = item as? [String: Any],
                  let source = (pair["source"] as? NSNumber)?.int64Value,
                  let target = (pair["target"] as? NSNumber)?.int64Value else { return nil }
            return PNSharedElementPair(
                name: pair["name"] as? String ?? "", source: source, target: target,
                transition: pair["transition"] as? [String: Any],
                sourceStyle: pair["source_style"] as? [String: Any] ?? [:],
                targetStyle: pair["target_style"] as? [String: Any] ?? [:]
            )
        }
    }
}

/// A stack push or pop that flies shared elements between the screens.
///
/// It recreates the stack's own transition in the context's container view
/// (UIKit's slide for `default` and `slide_from_right`, a cross-dissolve
/// for `fade`, a cover for `slide_from_bottom`) and, with the same timing,
/// lifts each pair's destination view out of its screen, flies it from the
/// source's rect to its own, and blends `border_radius`,
/// `background_color`, and `opacity` (or the pair's `props`) from the
/// source's style to its own. The source is hidden meanwhile. When the
/// transition ends, the view goes back to its parent, index, and frame.
///
/// Timing comes from the first pair's `shared_transition` (a spring, or a
/// duration and easing), else UIKit's push. The animator is interruptible,
/// so an edge pan drives an interactive pop through
/// `UIPercentDrivenInteractiveTransition`; canceling flies the elements back.
final class PNSharedElementTransition: NSObject, UIViewControllerAnimatedTransitioning {
    let operation: UINavigationController.Operation
    let animation: String
    let pairs: [PNSharedElementPair]
    let timing: PNMotionTiming
    private var animator: UIViewPropertyAnimator?

    /// A destination view in flight and what it lands back on.
    final class Flight {
        let tag: Int64
        let view: UIView
        let source: UIView
        let superview: UIView?
        let index: Int
        let bounds: CGRect
        let center: CGPoint
        let transform: CATransform3D
        let alpha: CGFloat
        let cornerRadius: CGFloat
        let masksToBounds: Bool
        let backgroundColor: UIColor?
        let sourceAlpha: CGFloat
        /// A frame the core set while the view flew, applied when it lands.
        var pendingFrame: (x: Double, y: Double, width: Double, height: Double)?

        init(tag: Int64, view: UIView, source: UIView) {
            self.tag = tag
            self.view = view
            self.source = source
            superview = view.superview
            index = view.superview?.subviews.firstIndex(of: view) ?? 0
            bounds = view.bounds
            center = view.center
            transform = view.layer.transform
            alpha = view.alpha
            cornerRadius = view.layer.cornerRadius
            masksToBounds = view.layer.masksToBounds
            backgroundColor = view.backgroundColor
            sourceAlpha = source.alpha
        }
    }

    private static var flights: [ObjectIdentifier: Flight] = [:]

    /// Hold a frame the core set on a view that's flying; it lands with it.
    static func deferFrame(of view: UIView, x: Double, y: Double, width: Double, height: Double) -> Bool {
        guard !flights.isEmpty, let flight = flights[ObjectIdentifier(view)] else { return false }
        flight.pendingFrame = (x, y, width, height)
        return true
    }

    /// Whether `view` is flying between screens right now.
    static func isFlying(_ view: UIView) -> Bool { flights[ObjectIdentifier(view)] != nil }

    init(operation: UINavigationController.Operation, animation: String, pairs: [PNSharedElementPair]) {
        self.operation = operation
        self.animation = animation
        self.pairs = pairs
        var timing = PNMotionTiming(pairs.lazy.compactMap { $0.transition }.first, fallback: .push)
        timing.delay = 0
        self.timing = timing
    }

    func transitionDuration(using context: UIViewControllerContextTransitioning?) -> TimeInterval {
        timing.duration
    }

    func animateTransition(using context: UIViewControllerContextTransitioning) {
        interruptibleAnimator(using: context).startAnimation()
    }

    func interruptibleAnimator(using context: UIViewControllerContextTransitioning) -> UIViewImplicitlyAnimating {
        if let animator = animator { return animator }
        let animator = makeAnimator(context)
        self.animator = animator
        return animator
    }

    private func makeAnimator(_ context: UIViewControllerContextTransitioning) -> UIViewPropertyAnimator {
        let animator = timing.makeAnimator()
        let container = context.containerView
        let fromController = context.viewController(forKey: .from)
        let toController = context.viewController(forKey: .to)
        guard let fromView = context.view(forKey: .from) ?? fromController?.view,
              let toView = context.view(forKey: .to) ?? toController?.view,
              let toController = toController else {
            animator.addCompletion { _ in context.completeTransition(!context.transitionWasCancelled) }
            return animator
        }
        toView.frame = context.finalFrame(for: toController)
        // Stack screens are transparent over the stack's background. Two of them
        // overlapping mid-slide would show through each other, so each borrows
        // the nearest opaque background behind it until the transition ends.
        let backdrop = PNSharedElementTransition.opaqueBackground(behind: fromController?.navigationController?.view ?? container)
        let fromBackground = fromView.backgroundColor, toBackground = toView.backgroundColor
        if let backdrop = backdrop {
            if fromView.backgroundColor == nil || fromView.backgroundColor == .clear { fromView.backgroundColor = backdrop }
            if toView.backgroundColor == nil || toView.backgroundColor == .clear { toView.backgroundColor = backdrop }
        }
        if operation == .pop {
            container.insertSubview(toView, belowSubview: fromView)
        } else {
            container.addSubview(toView)
        }
        toView.setNeedsLayout()
        toView.layoutIfNeeded()

        // Measure every pair before the screens move.
        let registry = PNViewRegistry.shared
        var flights: [(Flight, CGRect, Blend)] = []
        for pair in pairs {
            guard let source = registry.view(for: pair.source), let target = registry.view(for: pair.target),
                  source.isDescendant(of: fromView), target.isDescendant(of: toView),
                  PNSharedElementTransition.flights[ObjectIdentifier(target)] == nil else { continue }
            let sourceRect = source.convert(source.bounds, to: container)
            let targetRect = target.convert(target.bounds, to: container)
            guard sourceRect.width.isFinite, targetRect.width.isFinite else { continue }
            flights.append((Flight(tag: pair.target, view: target, source: source), targetRect, Blend(pair, source: source, target: target)))
            // Lift the destination into the container at the source's rect.
            target.layer.transform = CATransform3DIdentity
            container.addSubview(target)
            target.bounds = CGRect(origin: target.bounds.origin, size: sourceRect.size)
            target.center = CGPoint(x: sourceRect.midX, y: sourceRect.midY)
            flights.last?.2.applyStart(to: target)
            source.alpha = 0
        }
        for (flight, _, _) in flights { PNSharedElementTransition.flights[ObjectIdentifier(flight.view)] = flight }

        let width = container.bounds.width, height = container.bounds.height
        var fromEnd = CGAffineTransform.identity
        var fromAlpha: CGFloat = 1, toAlpha: CGFloat = 1
        switch (animation, operation) {
        case ("fade", .pop):
            fromAlpha = 0
        case ("fade", _):
            toView.alpha = 0
        case ("slide_from_bottom", .pop):
            fromEnd = CGAffineTransform(translationX: 0, y: height)
        case ("slide_from_bottom", _):
            toView.transform = CGAffineTransform(translationX: 0, y: height)
        case (_, .pop):
            toView.transform = CGAffineTransform(translationX: -width * 0.3, y: 0)
            fromEnd = CGAffineTransform(translationX: width, y: 0)
        default:
            toView.transform = CGAffineTransform(translationX: width, y: 0)
            fromEnd = CGAffineTransform(translationX: -width * 0.3, y: 0)
        }

        animator.addAnimations {
            fromView.transform = fromEnd
            fromView.alpha = fromAlpha
            toView.transform = .identity
            toView.alpha = toAlpha
            for (flight, rect, blend) in flights {
                flight.view.bounds = CGRect(origin: flight.view.bounds.origin, size: rect.size)
                flight.view.center = CGPoint(x: rect.midX, y: rect.midY)
                blend.applyEnd(to: flight.view)
            }
        }
        animator.addCompletion { [weak self] _ in
            fromView.backgroundColor = fromBackground
            toView.backgroundColor = toBackground
            fromView.transform = .identity
            toView.transform = .identity
            fromView.alpha = 1
            toView.alpha = 1
            for (flight, _, _) in flights { PNSharedElementTransition.land(flight) }
            self?.animator = nil
            context.completeTransition(!context.transitionWasCancelled)
        }
        return animator
    }

    /// Put a flown view back where it came from and unhide its source.
    /// The first opaque background color at or behind `view`, walking up its superviews.
    static func opaqueBackground(behind view: UIView?) -> UIColor? {
        var current = view
        while let candidate = current {
            if let color = candidate.backgroundColor, color.cgColor.alpha > 0.99 { return color }
            current = candidate.superview
        }
        return view?.window?.backgroundColor ?? .systemBackground
    }

    static func land(_ flight: Flight) {
        flights.removeValue(forKey: ObjectIdentifier(flight.view))
        let view = flight.view
        view.removeFromSuperview()
        if let superview = flight.superview {
            superview.insertSubview(view, at: min(flight.index, superview.subviews.count))
        }
        view.layer.transform = CATransform3DIdentity
        view.bounds = flight.bounds
        view.center = flight.center
        view.layer.transform = flight.transform
        view.alpha = flight.alpha
        view.layer.cornerRadius = flight.cornerRadius
        view.layer.masksToBounds = flight.masksToBounds
        view.backgroundColor = flight.backgroundColor
        flight.source.alpha = flight.sourceAlpha
        if let frame = flight.pendingFrame, let record = PNViewRegistry.shared.resolve(flight.tag), record.view === view {
            record.manager.setFrame(view: view, x: frame.x, y: frame.y, w: frame.width, h: frame.height)
        }
    }

    /// The paint props a flight blends, from the source's style to the destination's.
    struct Blend {
        var radius: (CGFloat, CGFloat)?
        var color: (UIColor?, UIColor?)?
        var alpha: (CGFloat, CGFloat)?

        init(_ pair: PNSharedElementPair, source: UIView, target: UIView) {
            let props = Set((pair.transition?["props"] as? [Any])?.compactMap { $0 as? String }
                ?? ["border_radius", "background_color", "opacity"])
            if props.contains("border_radius") {
                let from = PNProps.double(pair.sourceStyle["border_radius"]).map { CGFloat($0) } ?? source.layer.cornerRadius
                let to = PNProps.double(pair.targetStyle["border_radius"]).map { CGFloat($0) } ?? target.layer.cornerRadius
                if from != to { radius = (max(0, from), max(0, to)) }
            }
            if props.contains("background_color") {
                let from = PNColor.parse(pair.sourceStyle["background_color"]) ?? source.backgroundColor
                let to = target.backgroundColor ?? PNColor.parse(pair.targetStyle["background_color"])
                if from != to { color = (from ?? to?.withAlphaComponent(0), to ?? from?.withAlphaComponent(0)) }
            }
            if props.contains("opacity") {
                let from = PNProps.double(pair.sourceStyle["opacity"]).map { CGFloat($0) } ?? source.alpha
                if from != target.alpha { alpha = (from, target.alpha) }
            }
        }

        func applyStart(to view: UIView) {
            if let radius = radius {
                view.layer.cornerRadius = radius.0
                view.layer.masksToBounds = true
            }
            if let color = color { view.backgroundColor = color.0 }
            if let alpha = alpha { view.alpha = alpha.0 }
        }

        func applyEnd(to view: UIView) {
            if let radius = radius { view.layer.cornerRadius = radius.1 }
            if let color = color { view.backgroundColor = color.1 }
            if let alpha = alpha { view.alpha = alpha.1 }
        }
    }
}
