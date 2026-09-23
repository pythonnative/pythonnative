import UIKit

/// A host-owned error view that remains usable when the rendered surface fails.
final class PNErrorOverlay: UIView {
    private static var visible: PNErrorOverlay?
    private var screen: Int64 = 0
    static func show(screen: Int64, title: String, trace: String) {
        dismiss()
        guard let controller = PNScreenRegistry.shared.controller(for: screen),
              let container = controller.view.window ?? controller.view else { return }
        let overlay = PNErrorOverlay(frame: container.bounds)
        overlay.screen = screen
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        overlay.backgroundColor = UIColor(red: 0.11, green: 0.11, blue: 0.12, alpha: 1)
        overlay.accessibilityViewIsModal = true
        let heading = UILabel()
        heading.text = title; heading.textColor = .white; heading.numberOfLines = 0
        heading.font = .preferredFont(forTextStyle: .headline)
        heading.adjustsFontForContentSizeCategory = true
        let detail = UITextView()
        detail.text = trace; detail.isEditable = false; detail.isSelectable = true
        detail.backgroundColor = .clear; detail.textColor = UIColor(red: 1, green: 0.65, blue: 0.7, alpha: 1)
        detail.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
        detail.accessibilityIdentifier = "pn-error-trace"
        let reload = UIButton(type: .system); reload.setTitle("Reload", for: .normal)
        reload.accessibilityIdentifier = "pn-error-reload"
        reload.addTarget(overlay, action: #selector(reloadPressed), for: .touchUpInside)
        let close = UIButton(type: .system); close.setTitle("Dismiss", for: .normal)
        close.accessibilityIdentifier = "pn-error-dismiss"
        close.addTarget(overlay, action: #selector(dismissPressed), for: .touchUpInside)
        let actions = UIStackView(arrangedSubviews: [reload, close]); actions.distribution = .fillEqually
        let stack = UIStackView(arrangedSubviews: [heading, detail, actions]); stack.axis = .vertical; stack.spacing = 12
        overlay.addSubview(stack); stack.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: overlay.safeAreaLayoutGuide.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: overlay.safeAreaLayoutGuide.bottomAnchor, constant: -16),
            stack.leadingAnchor.constraint(equalTo: overlay.leadingAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: overlay.trailingAnchor, constant: -16),
            actions.heightAnchor.constraint(greaterThanOrEqualToConstant: 44),
        ])
        container.addSubview(overlay); visible = overlay
        UIAccessibility.post(notification: .screenChanged, argument: heading)
    }
    static func dismiss() { visible?.removeFromSuperview(); visible = nil }
    @objc private func dismissPressed() { Self.dismiss() }
    @objc private func reloadPressed() { PNBridge.shared.callPython(kind: "host", tag: screen, name: "reload", payload: "{}") }
}
