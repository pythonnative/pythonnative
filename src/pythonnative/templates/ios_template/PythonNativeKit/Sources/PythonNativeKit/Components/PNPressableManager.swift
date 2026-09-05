import UIKit

/// `Pressable`: a touchable container with press feedback.
///
/// A zero-duration long-press recognizer tracks the raw touch for
/// `on_press_in` / `on_press_out` and the pressed-opacity feedback; a tap
/// recognizer fires `on_press` and a standard long press fires
/// `on_long_press`. Hit slop and pointer events come from
/// `PNContainerView`, so hit testing is entirely UIKit's.
public final class PNPressableManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let view = PNContainerView(frame: .zero)
        view.isUserInteractionEnabled = true
        return view
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        let handler = PNPressHandler(view: view)
        PNViewState.existing(for: view)?.retained.append(handler)
        handler.install()
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        PNViewStyler.applyCommon(view, props)
        if PNProps.has(props, "enabled") {
            view.isUserInteractionEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true
        }
        if PNProps.has(props, "disabled") {
            view.isUserInteractionEnabled = !(PNProps.bool(PNProps.value(props, "disabled")) ?? false)
        }
        if let delay = PNProps.double(PNProps.value(props, "delay_long_press")),
           let handler = PNViewState.existing(for: view)?.retained.compactMap({ $0 as? PNPressHandler }).first
        {
            handler.longPress.minimumPressDuration = max(0.05, delay / 1000)
        }
    }
}

/// Owns the three press recognizers of one Pressable.
final class PNPressHandler: NSObject, UIGestureRecognizerDelegate {
    private weak var view: UIView?
    let tap = UITapGestureRecognizer()
    let longPress = UILongPressGestureRecognizer()
    let touch = UILongPressGestureRecognizer()

    init(view: UIView) {
        self.view = view
        super.init()
    }

    func install() {
        guard let view = view else { return }
        touch.minimumPressDuration = 0
        tap.addTarget(self, action: #selector(onTap(_:)))
        longPress.addTarget(self, action: #selector(onLongPress(_:)))
        touch.addTarget(self, action: #selector(onTouch(_:)))
        for recognizer in [tap, longPress, touch] {
            recognizer.cancelsTouchesInView = false
            recognizer.delegate = self
            view.addGestureRecognizer(recognizer)
        }
    }

    private var merged: [String: Any] {
        view.flatMap { PNViewState.existing(for: $0)?.props } ?? [:]
    }

    @objc private func onTap(_ recognizer: UITapGestureRecognizer) {
        guard let view = view, recognizer.state == .ended else { return }
        PNEvents.emit(view, "on_press")
    }

    @objc private func onLongPress(_ recognizer: UILongPressGestureRecognizer) {
        guard let view = view, recognizer.state == .began else { return }
        PNEvents.emit(view, "on_long_press")
    }

    @objc private func onTouch(_ recognizer: UILongPressGestureRecognizer) {
        guard let view = view else { return }
        switch recognizer.state {
        case .began:
            feedback(pressed: true)
            PNEvents.emit(view, "on_press_in")
        case .ended, .cancelled, .failed:
            feedback(pressed: false)
            PNEvents.emit(view, "on_press_out")
        default:
            break
        }
    }

    private func feedback(pressed: Bool) {
        guard let view = view else { return }
        let props = merged
        let target: CGFloat
        let duration: TimeInterval
        if pressed {
            target = CGFloat(PNProps.double(PNProps.value(props, "pressed_opacity")) ?? 0.6)
            duration = 0.05
        } else {
            target = CGFloat(PNProps.double(PNProps.value(props, "opacity")) ?? 1)
            duration = 0.1
        }
        UIView.animate(withDuration: duration) { view.alpha = target }
    }

    // Press recognizers recognize alongside everything, including the
    // declarative `gestures` recognizers and a parent scroll view's pan.
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        true
    }
}
