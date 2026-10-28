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

/// The shared keyboard observer.
///
/// Tracks the keyboard's height, visibility, and the animation duration
/// of its last frame change, emits the `Keyboard` module's `change`
/// event `{"height", "visible", "duration_ms"}`, re-emits every live
/// screen's viewport (`keyboard_height` is part of it), and notifies
/// Swift listeners. `KeyboardModule` is a thin adapter over it.
public final class PNKeyboardObserver {
    public static let shared = PNKeyboardObserver()

    /// One keyboard state, as the `Keyboard` module reports it.
    public struct Snapshot: Equatable {
        public let height: Double
        public let visible: Bool
        public let durationMs: Double
        /// `{"height", "visible", "duration_ms"}`.
        public var payload: [String: Any] { ["height": height, "visible": visible, "duration_ms": durationMs] }
    }

    private var started = false
    private var listeners: [UUID: (Snapshot) -> Void] = [:]
    private(set) public var height: CGFloat = 0
    private(set) public var isVisible = false
    private(set) public var lastDurationMs: Double = 0
    /// The keyboard's end frame in screen coordinates (`.zero` when hidden).
    private(set) public var frame: CGRect = .zero

    private init() {}

    /// The current state.
    public var snapshot: Snapshot { Snapshot(height: Double(height), visible: isVisible, durationMs: lastDurationMs) }

    /// Begin observing keyboard notifications (idempotent).
    public func start() {
        if started { return }
        started = true
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(willShow(_:)), name: UIResponder.keyboardWillShowNotification, object: nil)
        center.addObserver(self, selector: #selector(willChange(_:)), name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        center.addObserver(self, selector: #selector(willHide(_:)), name: UIResponder.keyboardWillHideNotification, object: nil)
    }

    /// Observe state changes from Swift; the returned closure unsubscribes.
    @discardableResult
    public func addListener(_ listener: @escaping (Snapshot) -> Void) -> () -> Void {
        start()
        let token = UUID()
        listeners[token] = listener
        return { [weak self] in self?.listeners.removeValue(forKey: token) }
    }

    /// Resign the first responder anywhere in the app (`Keyboard.dismiss`).
    public func dismiss() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        PNWindow.keyWindow()?.endEditing(true)
    }

    @objc private func willShow(_ note: Notification) {
        apply(note, hiding: false)
    }

    @objc private func willChange(_ note: Notification) {
        apply(note, hiding: false)
    }

    @objc private func willHide(_ note: Notification) {
        apply(note, hiding: true)
    }

    private func apply(_ note: Notification, hiding: Bool) {
        let duration = ((note.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? NSNumber)?.doubleValue ?? 0.25) * 1000
        let end = (note.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue ?? .zero
        let value = hiding ? 0 : Self.keyboardHeight(from: note)
        publish(value, frame: value > 0 ? end : .zero, durationMs: duration)
    }

    /// Record a keyboard state and publish it when it changed. Exposed so
    /// tests (and hosts without a keyboard session) can drive it.
    public func publish(_ value: CGFloat, frame: CGRect = .zero, durationMs: Double = 0) {
        let clamped = max(0, value)
        let visible = clamped > 0
        if clamped == height && visible == isVisible { return }
        height = clamped
        isVisible = visible
        lastDurationMs = durationMs
        self.frame = frame
        let current = snapshot
        PNModuleEvents.emitTyped(KeyboardEvents.change, current.payload)
        for id in PNScreenRegistry.shared.screenIds {
            PNScreenRegistry.shared.controller(for: id)?.keyboardDidChange()
        }
        for listener in listeners.values { listener(current) }
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
