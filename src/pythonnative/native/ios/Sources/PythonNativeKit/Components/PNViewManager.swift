import UIKit

/// `View`, `Row`, and `Column`: a hit-test-aware flex container. All
/// layout semantics live in the Python layout engine; the manager only
/// applies visual props and frames.
public final class PNViewManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        PNContainerView(frame: .zero)
    }
}

/// `Spacer`: an empty layout placeholder.
public final class PNSpacerManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UIView(frame: .zero)
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        // Sizing is entirely the layout engine's; nothing visual to apply.
    }
}

/// `SafeAreaView`: a plain container; insets are applied by the layout engine.
public final class PNSafeAreaViewManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        PNContainerView(frame: .zero)
    }
}

/// `KeyboardAvoidingView`: a container that keeps the keyboard observer
/// installed so Python receives keyboard height updates.
public final class PNKeyboardAvoidingViewManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        PNKeyboardObserver.shared.start()
        return PNContainerView(frame: .zero)
    }
}

/// Publishes the keyboard height through
/// `callback("module", 0, "Host", {"event": "keyboard", "payload": {"height": h}})`.
public final class PNKeyboardObserver {
    public static let shared = PNKeyboardObserver()

    private var started = false
    private(set) public var height: CGFloat = 0

    private init() {}

    /// Begin observing keyboard notifications (idempotent).
    public func start() {
        if started { return }
        started = true
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(willShow(_:)), name: UIResponder.keyboardWillShowNotification, object: nil)
        center.addObserver(self, selector: #selector(willChange(_:)), name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        center.addObserver(self, selector: #selector(willHide(_:)), name: UIResponder.keyboardWillHideNotification, object: nil)
    }

    @objc private func willShow(_ note: Notification) {
        publish(Self.keyboardHeight(from: note))
    }

    @objc private func willChange(_ note: Notification) {
        publish(Self.keyboardHeight(from: note))
    }

    @objc private func willHide(_ note: Notification) {
        publish(0)
    }

    private func publish(_ value: CGFloat) {
        let clamped = max(0, value)
        if clamped == height { return }
        height = clamped
        PNModuleEvents.emit(module: "Host", event: "keyboard", payload: ["height": Double(clamped)])
    }

    static func keyboardHeight(from note: Notification) -> CGFloat {
        guard let frame = (note.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue else {
            return 0
        }
        let screen = PNWindow.screenBounds()
        if screen.height > 0, frame.origin.y >= screen.height { return 0 }
        return frame.height
    }
}
