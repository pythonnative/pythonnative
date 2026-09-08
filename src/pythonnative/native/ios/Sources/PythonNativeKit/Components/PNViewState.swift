import UIKit

/// Per-view state attached to every bridge-created `UIView`.
///
/// Managers are shared per element type, so anything a manager needs
/// to remember about one view (its merged props, style bookkeeping,
/// recognizers, suppress flags) lives here. The state is stored as an
/// associated object so it can be reached from any `UIView` reference.
public final class PNViewState {
    /// The reconciler tag of the view.
    public let tag: Int64
    /// Element type name.
    public let typeName: String
    /// Every prop the view has received so far (updates merge; `null` removes).
    public var props: [String: Any] = [:]
    /// Free-form storage for manager-specific values (suppress flags, delegates, ...).
    public var extras: [String: Any] = [:]
    /// Strong references the view's manager needs to keep alive (delegates, targets).
    public var retained: [AnyObject] = []
    /// Recognizers installed from the `gestures` prop.
    public var gestureRecognizers: [UIGestureRecognizer] = []

    // Style bookkeeping used by `PNViewStyler` at frame time.
    var requestedCornerRadius: CGFloat?
    var cornerRadii: [CGFloat]?
    var sideBorderWidths: [CGFloat]?
    var sideBorderColors: [UIColor]?
    var sideBorderLayers: [CALayer?] = [nil, nil, nil, nil]

    init(tag: Int64, typeName: String) {
        self.tag = tag
        self.typeName = typeName
    }

    /// Names of the events wired on the element this render (`_pn_events`).
    public var eventNames: Set<String> {
        guard let list = props["_pn_events"] as? [Any] else { return [] }
        return Set(list.compactMap { $0 as? String })
    }

    /// Whether the element wired a callback named `name`.
    public func hasEvent(_ name: String) -> Bool {
        eventNames.contains(name)
    }

    /// Typed access to `extras`.
    public func flag(_ key: String) -> Bool {
        (extras[key] as? Bool) ?? false
    }

    private static var key: UInt8 = 0

    /// Attach a fresh state object to `view`.
    @discardableResult
    static func attach(_ view: UIView, tag: Int64, typeName: String) -> PNViewState {
        let state = PNViewState(tag: tag, typeName: typeName)
        objc_setAssociatedObject(view, &key, state, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        return state
    }

    /// The state attached to `view`, if any.
    public static func existing(for view: UIView) -> PNViewState? {
        objc_getAssociatedObject(view, &key) as? PNViewState
    }

    static func detach(_ view: UIView) {
        objc_setAssociatedObject(view, &key, nil, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
    }
}

/// Event emission keyed by view.
public enum PNEvents {
    /// Emit `name` for `view` with positional `args`. Returns Python's
    /// JSON reply for request-style events, else `nil`.
    @discardableResult
    public static func emit(_ view: UIView, _ name: String, _ args: [Any?] = []) -> String? {
        guard let state = PNViewState.existing(for: view) else { return nil }
        return PNBridge.shared.emitEvent(tag: state.tag, name: name, args: args)
    }

    /// Emit only when the element wired a handler for `name`.
    @discardableResult
    public static func emitIfWired(_ view: UIView, _ name: String, _ args: [Any?] = []) -> String? {
        guard let state = PNViewState.existing(for: view), state.hasEvent(name) else { return nil }
        return PNBridge.shared.emitEvent(tag: state.tag, name: name, args: args)
    }
}
