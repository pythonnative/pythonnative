import UIKit

/// Base class for every element type's native implementation.
///
/// One manager instance serves every view of its type; per-view state
/// is kept in `PNViewState`. Subclasses usually override `makeView` and
/// `apply`, and opt into `measure`, `command`, and the child hooks when
/// the stock behavior isn't right.
open class PNComponentManager {
    public init() {}

    // MARK: - Creation and props

    /// Create the native view and apply its initial props.
    open func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = makeView(props: props)
        view.translatesAutoresizingMaskIntoConstraints = true
        let state = PNViewState.attach(view, tag: tag, typeName: String(describing: type(of: self)))
        state.props = PNComponentManager.stripNulls(props)
        apply(view: view, props: props, initial: true)
        if let gestures = PNProps.value(props, "gestures") {
            PNGestureCoordinator.shared.wire(view: view, specs: gestures)
        }
        return view
    }

    /// Hook run after the view is registered in `PNViewRegistry`.
    open func didCreate(view: UIView, tag: Int64, props: [String: Any]) {}

    /// Construct the bare native view. Subclasses override this.
    open func makeView(props: [String: Any]) -> UIView {
        PNContainerView(frame: .zero)
    }

    /// Merge `changed` into the view's props and apply them.
    open func update(view: UIView, changed: [String: Any]) {
        if let state = PNViewState.existing(for: view) {
            for (key, value) in changed {
                if value is NSNull {
                    state.props.removeValue(forKey: key)
                } else {
                    state.props[key] = value
                }
            }
        }
        apply(view: view, props: changed, initial: false)
        if PNProps.has(changed, "gestures") {
            PNGestureCoordinator.shared.wire(view: view, specs: PNProps.value(changed, "gestures"))
        }
    }

    /// Apply `props` (initial or changed) to the view. The default
    /// applies every shared visual prop; leaf managers override.
    open func apply(view: UIView, props: [String: Any], initial: Bool) {
        PNViewStyler.applyCommon(view, props)
    }

    // MARK: - Children

    /// Ensure `child` sits at `index` under `parent` (move-aware, clamped).
    open func insertChild(parent: UIView, child: UIView, index: Int) {
        child.translatesAutoresizingMaskIntoConstraints = true
        let container = childContainer(for: parent)
        let siblings = container.subviews
        if child.superview === container, let current = siblings.firstIndex(where: { $0 === child }) {
            let target = max(0, min(index, siblings.count - 1))
            if current == target { return }
            container.insertSubview(child, at: target)
            return
        }
        let target = max(0, min(index, siblings.count))
        container.insertSubview(child, at: target)
    }

    /// Detach `child` from `parent`.
    open func removeChild(parent: UIView, child: UIView) {
        if child.superview != nil {
            child.removeFromSuperview()
        }
    }

    /// The view children are inserted into (the view itself by default).
    open func childContainer(for view: UIView) -> UIView {
        view
    }

    // MARK: - Lifecycle

    /// Release the view's resources and detach it from the hierarchy.
    open func destroy(view: UIView) {
        teardown(view: view)
        PNGestureCoordinator.shared.unwire(view: view)
        PNAnimator.shared.forget(view: view)
        view.layer.removeAllAnimations()
        if view.superview != nil {
            view.removeFromSuperview()
        }
    }

    /// Subclass hook for extra cleanup before the view is released.
    open func teardown(view: UIView) {}

    // MARK: - Layout

    /// Apply a frame from the layout engine (transform-safe, non-finite values clamped).
    open func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {
        let fx = CGFloat(PNProps.finite(x))
        let fy = CGFloat(PNProps.finite(y))
        let fw = CGFloat(max(0, PNProps.finite(w)))
        let fh = CGFloat(max(0, PNProps.finite(h)))
        if !(x.isFinite && y.isFinite && w.isFinite && h.isFinite) {
            PNLog.rateLimited(PNLog.components, key: "set_frame:nan", "[set_frame:nan] (\(x), \(y), \(w), \(h)) clamped")
        }
        view.translatesAutoresizingMaskIntoConstraints = true
        // Setting `bounds.size` + `center` (instead of `frame`) keeps the
        // frame meaningful under a non-identity transform and preserves
        // a scroll view's content offset (its `bounds.origin`).
        var bounds = view.bounds
        bounds.size = CGSize(width: fw, height: fh)
        view.bounds = bounds
        let anchor = view.layer.anchorPoint
        view.center = CGPoint(x: fx + fw * anchor.x, y: fy + fh * anchor.y)
        PNViewStyler.syncFrameDependentStyles(view, size: CGSize(width: fw, height: fh))
        if let scroll = view.superview as? UIScrollView, !(scroll is UITableView) {
            let visible = scroll.bounds.size
            let contentW = max(visible.width, fx + fw)
            let contentH = max(visible.height, fy + fh)
            if scroll.contentSize != CGSize(width: contentW, height: contentH) {
                scroll.contentSize = CGSize(width: contentW, height: contentH)
            }
        }
    }

    /// Natural size under the constraints (either may be `1e6` / infinite).
    open func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let mw = PNComponentManager.clampConstraint(maxW)
        let mh = PNComponentManager.clampConstraint(maxH)
        var size = view.sizeThatFits(CGSize(width: mw, height: mh))
        if maxW.isFinite { size.width = min(size.width, maxW) }
        if !size.width.isFinite { size.width = 0 }
        if !size.height.isFinite { size.height = 0 }
        return size
    }

    // MARK: - Commands and animation

    /// Run an imperative command. Unknown commands return `nil`.
    open func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        nil
    }

    /// Apply one Python-driven animation frame immediately.
    open func setAnimatedProperty(view: UIView, prop: String, value: Any?) {
        PNAnimator.shared.applyValue(view: view, prop: prop, value: value)
    }

    /// Start a natively driven animation. Returns `false` to fall back to Python.
    open func startAnimation(view: UIView, id: Int64, prop: String, spec: [String: Any]) -> Bool {
        PNAnimator.shared.start(view: view, id: id, prop: prop, spec: spec)
    }

    /// Cancel a native animation, returning the presentation value when known.
    open func cancelAnimation(view: UIView, id: Int64) -> Any? {
        PNAnimator.shared.cancel(id: id)
    }

    // MARK: - Helpers

    /// The merged props recorded for `view` (empty when unmanaged).
    public func mergedProps(_ view: UIView) -> [String: Any] {
        PNViewState.existing(for: view)?.props ?? [:]
    }

    /// Clamp an infinite or oversized layout constraint for UIKit.
    public static func clampConstraint(_ value: CGFloat, fallback: CGFloat = 10_000) -> CGFloat {
        guard value.isFinite else { return fallback }
        return max(0, min(value, fallback))
    }

    static func stripNulls(_ props: [String: Any]) -> [String: Any] {
        props.filter { !($0.value is NSNull) }
    }
}
