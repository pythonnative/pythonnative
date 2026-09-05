import UIKit

/// Hit-test-aware container used by View, Row, Column, Pressable,
/// SafeAreaView, and KeyboardAvoidingView.
///
/// Implements `pointer_events` (`"none"`, `"box_none"`, `"box_only"`,
/// anything else = auto) and `hit_slop` by overriding the two UIKit
/// hit-testing entry points. With neither prop set the behavior is
/// exactly stock `UIView`.
open class PNContainerView: UIView {
    /// `nil` or `"auto"` means stock hit testing.
    public var pointerEvents: String?
    /// Extra touchable margin as (top, left, bottom, right).
    public var hitSlop: UIEdgeInsets = .zero

    public override init(frame: CGRect) {
        super.init(frame: frame)
        translatesAutoresizingMaskIntoConstraints = true
    }

    public required init?(coder: NSCoder) {
        super.init(coder: coder)
        translatesAutoresizingMaskIntoConstraints = true
    }

    open override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        if pointerEvents == "none" { return false }
        let expanded = bounds.inset(by: UIEdgeInsets(
            top: -hitSlop.top, left: -hitSlop.left, bottom: -hitSlop.bottom, right: -hitSlop.right
        ))
        return expanded.contains(point)
    }

    open override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        if pointerEvents == "none" { return nil }
        let result = super.hitTest(point, with: event)
        switch pointerEvents {
        case "box_none":
            return result === self ? nil : result
        case "box_only":
            return result == nil ? nil : self
        default:
            return result
        }
    }
}

/// Manager used for element types nobody registered. Creates a plain
/// `UIView` so the tree stays consistent.
final class PNPlaceholderManager: PNComponentManager {
    override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = PNContainerView(frame: .zero)
        view.backgroundColor = .clear
        return view
    }
}
