import UIKit

/// Presents `UIAlertController`s from the top view controller.
public enum PNAlertPresenter {
    /// Show an alert or action sheet. `buttons` are
    /// `{"label", "style": "default"|"cancel"|"destructive"}` dicts;
    /// `completion` receives the tapped index, or `-1` on dismissal.
    public static func present(
        title: String?, message: String?, buttons: [[String: Any]], style: String,
        completion: @escaping (Int) -> Void
    ) {
        guard let top = PNWindow.topViewController() else {
            completion(-1)
            return
        }
        let preferred: UIAlertController.Style = style == "action_sheet" ? .actionSheet : .alert
        let alert = UIAlertController(title: title, message: message, preferredStyle: preferred)
        var settled = false
        let finish: (Int) -> Void = { index in
            if settled { return }
            settled = true
            completion(index)
        }
        let list = buttons.isEmpty ? [["label": "OK"]] : buttons
        for (index, button) in list.enumerated() {
            let label = PNProps.string(button["label"]) ?? PNProps.string(button["title"]) ?? "OK"
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

    func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
        onDismiss()
        PNAlertDismissWatcher.watchers.removeValue(forKey: ObjectIdentifier(presentationController.presentedViewController))
    }
}

/// `Alert`: `present` (async, resolves the tapped index) and `show` (fire-and-forget).
public final class AlertModule: PNNativeModule {
    public static let name = "Alert"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "present", "show":
            let buttons = ((args["buttons"] as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
            let fireAndForget = method == "show"
            if fireAndForget { promise.resolve(nil) }
            PNAlertPresenter.present(
                title: PNProps.string(args["title"]),
                message: PNProps.string(args["message"]),
                buttons: buttons,
                style: PNProps.string(args["style"]) ?? "alert"
            ) { index in
                if !fireAndForget { promise.resolve(index) }
            }
        default:
            promise.reject("Alert has no method '\(method)'", code: "unknown_method")
        }
    }
}
