import UIKit

/// Applies the animated values the renderer core's animator writes
/// (`opacity`, `background_color`, `color`, `translate_x`, `translate_y`,
/// `scale`, `scale_x`, `scale_y`, `rotate`, `rotate_x`, `rotate_y`).
///
/// The core evaluates graphs and runs every timing, spring, and decay
/// driver on the display link (RFC 0007); this type only puts values on
/// views. Transform channels are stored per view in
/// `PNViewState.animatedTransform` and composed with the static
/// `transform` prop by `PNTransform`, so binding `translate_x` and
/// `translate_y` together (or on top of a static `rotate`) works.
public final class PNAnimator {
    public static let shared = PNAnimator()

    /// Prop names the animator can write.
    public static let animatableProps: Set<String> = [
        "opacity", "background_color", "color",
        "translate_x", "translate_y", "scale", "scale_x", "scale_y", "rotate", "rotate_x", "rotate_y",
    ]

    /// Transform channels routed through `PNTransform.compose`.
    static let transformProps: Set<String> = Set(PNTransform.animatedChannels)

    private init() {}

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
}
