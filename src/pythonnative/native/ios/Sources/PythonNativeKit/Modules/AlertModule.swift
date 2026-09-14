import UIKit

/// Presents `UIAlertController`s from the top view controller.
public enum PNAlertPresenter {
    /// Show an alert or action sheet. `buttons` are
    /// `{"label", "style": "default"|"cancel"|"destructive"}` dicts;
    /// `completion` receives the tapped index, or `-1` on dismissal.
    @discardableResult
    public static func present(
        title: String?, message: String?, buttons: [[String: Any]], style: String,
        completion: @escaping (Int) -> Void
    ) -> (() -> Void)? {
        guard let top = PNWindow.topViewController() else {
            completion(-1)
            return nil
        }
        let preferred: UIAlertController.Style = style == "action_sheet" ? .actionSheet : .alert
        let alert = UIAlertController(title: title, message: message, preferredStyle: preferred)
        var settled = false
        let finish: (Int) -> Void = { [weak alert] index in
            if settled { return }
            settled = true
            if let alert = alert { PNAlertDismissWatcher.forget(alert) }
            completion(index)
        }
        let list = buttons.isEmpty ? [["label": "OK"]] : buttons
        for (index, button) in list.enumerated() {
            let label = PNProps.string(button["label"]) ?? "OK"
            let actionStyle: UIAlertAction.Style
            switch PNProps.string(button["style"]) {
            case "cancel": actionStyle = .cancel
            case "destructive": actionStyle = .destructive
            default: actionStyle = .default
            }
            alert.addAction(UIAlertAction(title: label, style: actionStyle) { _ in finish(index) })
        }
        if preferred == .actionSheet, let popover = alert.popoverPresentationController {
            popover.sourceView = top.view
            popover.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.maxY - 1, width: 1, height: 1)
            popover.permittedArrowDirections = []
        }
        top.present(alert, animated: true)
        // A sheet dismissed by tapping outside (iPad popover) never runs
        // an action; report -1 once it disappears.
        PNAlertDismissWatcher.watch(alert) { finish(-1) }
        return {
            settled = true
            PNAlertDismissWatcher.forget(alert)
            alert.dismiss(animated: true)
        }
    }
}

/// Observes an alert's disappearance to report an outside-tap dismissal.
final class PNAlertDismissWatcher: NSObject, UIPopoverPresentationControllerDelegate {
    private let onDismiss: () -> Void
    private static var watchers: [ObjectIdentifier: PNAlertDismissWatcher] = [:]

    private init(onDismiss: @escaping () -> Void) {
        self.onDismiss = onDismiss
    }

    static func watch(_ alert: UIAlertController, onDismiss: @escaping () -> Void) {
        let watcher = PNAlertDismissWatcher(onDismiss: onDismiss)
        watchers[ObjectIdentifier(alert)] = watcher
        alert.popoverPresentationController?.delegate = watcher
    }

    static func forget(_ alert: UIAlertController) { watchers.removeValue(forKey: ObjectIdentifier(alert)) }

    func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
        onDismiss()
        PNAlertDismissWatcher.watchers.removeValue(forKey: ObjectIdentifier(presentationController.presentedViewController))
    }
}

/// `Alert`: `present` (async, resolves the tapped index) and `show` (fire-and-forget).
public final class AlertModule: AlertImplementation {
    public init() {}

    public func show(title: String, message: String?, buttons: [[String: PNJSONValue]], style: String) {
        PNAlertPresenter.present(title: title, message: message, buttons: buttons.map { $0.mapValues { PNValues.encode($0) } }, style: style) { _ in }
    }

    public func present(title: String, message: String?, buttons: [[String: PNJSONValue]], style: String, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        PNAlertPresenter.present(title: title, message: message, buttons: buttons.map { $0.mapValues { PNValues.encode($0) } }, style: style) { completion(.success(Int64($0))) }
    }
}
