import UIKit

/// The development error screen, a host-owned view that remains usable when
/// the rendered surface fails.
///
/// It renders the report `Host.show_error` sends (the shape of
/// `pythonnative.errors.ErrorReport.to_dict` plus `screen`): the error type
/// and message, the phase, the component stack, and the frames. Application
/// frames show their source excerpt, and each run of framework frames
/// collapses into one row that expands. Tapping an application frame's title
/// sends the `open_in_editor` host event; Reload sends `reload`.
final class PNErrorOverlay: UIView {
    private(set) static var visible: PNErrorOverlay?

    private var screen: Int64 = 0
    private var text = ""
    private var appFrames: [(file: String, line: Int)] = []
    private var frameworkGroups: [UIStackView] = []
    private weak var copyButton: UIButton?

    private static let background = UIColor(red: 0.11, green: 0.11, blue: 0.12, alpha: 1)
    private static let secondary = UIColor(white: 0.62, alpha: 1)
    private static let messageColor = UIColor(red: 1, green: 0.65, blue: 0.7, alpha: 1)
    private static let linkColor = UIColor(red: 0.45, green: 0.7, blue: 1, alpha: 1)
    private static let failingLine = UIColor(red: 1, green: 0.3, blue: 0.35, alpha: 0.28)

    /// Show `report`, replacing any error screen already showing.
    static func show(_ report: [String: Any]) {
        dismiss()
        let screen = Int64(PNProps.int(report["screen"]) ?? 0)
        let controller = PNScreenRegistry.shared.controller(for: screen)
        guard let container = controller?.view.window ?? controller?.view ?? PNWindow.keyWindow() else { return }
        let overlay = PNErrorOverlay(frame: container.bounds)
        overlay.screen = screen
        overlay.text = PNProps.string(report["text"]) ?? ""
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        overlay.backgroundColor = background
        overlay.accessibilityViewIsModal = true
        let heading = overlay.build(report)
        container.addSubview(overlay)
        visible = overlay
        UIAccessibility.post(notification: .screenChanged, argument: heading)
    }

    static func dismiss() {
        visible?.removeFromSuperview()
        visible = nil
    }

    // MARK: - Building

    /// Lay out the report; returns the heading for VoiceOver focus.
    private func build(_ report: [String: Any]) -> UIView {
        let content = UIStackView()
        content.axis = .vertical
        content.spacing = 6
        content.alignment = .fill

        let level = PNProps.string(report["level"]) ?? "error"
        let typeName = PNProps.string(report["type"]) ?? ""
        let heading = Self.label(typeName.isEmpty ? (PNProps.string(report["title"]) ?? "Python error") : typeName,
                                 font: Self.bold(.title2), color: .white)
        heading.accessibilityTraits = .header
        content.addArrangedSubview(heading)
        if let message = PNProps.string(report["message"]), !message.isEmpty {
            content.addArrangedSubview(Self.label(message, font: .preferredFont(forTextStyle: .body), color: Self.messageColor))
        }
        if let phase = PNProps.string(report["phase"]), !phase.isEmpty {
            let kind = level == "warning" ? "Warning" : "Error"
            content.addArrangedSubview(Self.label("\(kind) during \(phase)", font: .preferredFont(forTextStyle: .footnote), color: Self.secondary))
        }

        let components = (report["component_stack"] as? [Any] ?? []).compactMap { $0 as? [String: Any] }
        if !components.isEmpty {
            content.addArrangedSubview(Self.section("Component stack"))
            let lines = components.map { component -> String in
                let name = "<\(PNProps.string(component["name"]) ?? "?")>"
                guard let file = PNProps.string(component["file"]), !file.isEmpty,
                      let line = PNProps.int(component["line"]), line > 0 else { return name }
                return "\(name) (\(file):\(line))"
            }
            content.addArrangedSubview(Self.label(lines.joined(separator: "\n"), font: Self.mono(12), color: .white))
        }

        let frames = (report["frames"] as? [Any] ?? []).compactMap { $0 as? [String: Any] }
        if !frames.isEmpty {
            content.addArrangedSubview(Self.section("Call stack"))
            var run: [[String: Any]] = []
            for frame in frames {
                if PNProps.bool(frame["framework"]) ?? false {
                    run.append(frame)
                    continue
                }
                if !run.isEmpty { content.addArrangedSubview(frameworkGroup(run)); run = [] }
                content.addArrangedSubview(appFrame(frame))
            }
            if !run.isEmpty { content.addArrangedSubview(frameworkGroup(run)) }
        } else if !text.isEmpty {
            content.addArrangedSubview(Self.section("Traceback"))
            content.addArrangedSubview(Self.label(text, font: Self.mono(12), color: Self.messageColor))
        }

        let scroll = UIScrollView()
        scroll.accessibilityIdentifier = "pn-error-trace"
        scroll.alwaysBounceVertical = true
        scroll.addSubview(content)

        let reload = Self.button("Reload", identifier: "pn-error-reload", target: self, action: #selector(reloadPressed))
        let copy = Self.button("Copy", identifier: "pn-error-copy", target: self, action: #selector(copyPressed))
        let close = Self.button("Dismiss", identifier: "pn-error-dismiss", target: self, action: #selector(dismissPressed))
        copyButton = copy
        let actions = UIStackView(arrangedSubviews: [close, copy, reload])
        actions.distribution = .fillEqually

        let stack = UIStackView(arrangedSubviews: [scroll, actions])
        stack.axis = .vertical
        stack.spacing = 12
        addSubview(stack)
        for view in [stack, content] as [UIView] { view.translatesAutoresizingMaskIntoConstraints = false }
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: safeAreaLayoutGuide.topAnchor, constant: 16),
            stack.bottomAnchor.constraint(equalTo: safeAreaLayoutGuide.bottomAnchor, constant: -8),
            stack.leadingAnchor.constraint(equalTo: safeAreaLayoutGuide.leadingAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: safeAreaLayoutGuide.trailingAnchor, constant: -16),
            actions.heightAnchor.constraint(greaterThanOrEqualToConstant: 44),
            content.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor),
            content.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor),
            content.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor),
            content.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor),
        ])
        return heading
    }

    /// An application frame: its tappable title and its source excerpt.
    private func appFrame(_ frame: [String: Any]) -> UIView {
        let file = PNProps.string(frame["file"]) ?? ""
        let line = PNProps.int(frame["line"]) ?? 0
        let title = PNProps.string(frame["title"]) ?? "\(file):\(line)"
        let button = UIButton(type: .system)
        button.setTitle(title, for: .normal)
        button.setTitleColor(Self.linkColor, for: .normal)
        button.titleLabel?.font = Self.mono(13, weight: .semibold)
        button.titleLabel?.numberOfLines = 0
        button.contentHorizontalAlignment = .leading
        button.accessibilityHint = "Opens this line in your editor"
        button.tag = appFrames.count
        appFrames.append((file, line))
        button.addTarget(self, action: #selector(framePressed(_:)), for: .touchUpInside)
        let views: [UIView]
        if let excerpt = PNProps.string(frame["excerpt"]), !excerpt.isEmpty {
            let source = UILabel()
            source.numberOfLines = 0
            source.attributedText = Self.excerpt(excerpt)
            views = [button, source]
        } else {
            views = [button]
        }
        let stack = UIStackView(arrangedSubviews: views)
        stack.axis = .vertical
        stack.spacing = 2
        stack.layoutMargins = UIEdgeInsets(top: 6, left: 0, bottom: 6, right: 0)
        stack.isLayoutMarginsRelativeArrangement = true
        return stack
    }

    /// One row for a run of framework frames that expands to their titles.
    private func frameworkGroup(_ frames: [[String: Any]]) -> UIView {
        let toggle = UIButton(type: .system)
        toggle.setTitle("\(frames.count) framework frame\(frames.count == 1 ? "" : "s")", for: .normal)
        toggle.setTitleColor(Self.secondary, for: .normal)
        toggle.titleLabel?.font = .preferredFont(forTextStyle: .footnote)
        toggle.contentHorizontalAlignment = .leading
        toggle.accessibilityIdentifier = "pn-error-framework-frames"
        toggle.tag = frameworkGroups.count
        toggle.addTarget(self, action: #selector(togglePressed(_:)), for: .touchUpInside)
        let titles = frames.map { PNProps.string($0["title"]) ?? "" }.joined(separator: "\n")
        let detail = UIStackView(arrangedSubviews: [Self.label(titles, font: Self.mono(11), color: Self.secondary)])
        detail.isHidden = true
        frameworkGroups.append(detail)
        let stack = UIStackView(arrangedSubviews: [toggle, detail])
        stack.axis = .vertical
        stack.spacing = 2
        return stack
    }

    // MARK: - Actions

    @objc private func dismissPressed() { Self.dismiss() }

    @objc private func reloadPressed() {
        PNBridge.shared.callPython(kind: "host", tag: screen, name: "reload", payload: "{}")
    }

    @objc private func copyPressed() {
        UIPasteboard.general.string = text
        copyButton?.setTitle("Copied", for: .normal)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.copyButton?.setTitle("Copy", for: .normal)
        }
    }

    @objc private func framePressed(_ sender: UIButton) {
        guard appFrames.indices.contains(sender.tag) else { return }
        let frame = appFrames[sender.tag]
        PNBridge.shared.callPython(kind: "host", tag: screen, name: "open_in_editor", payload: PNJSON.encode(["file": frame.file, "line": frame.line]))
    }

    @objc private func togglePressed(_ sender: UIButton) {
        guard frameworkGroups.indices.contains(sender.tag) else { return }
        frameworkGroups[sender.tag].isHidden.toggle()
    }

    // MARK: - Styling

    private static func mono(_ size: CGFloat, weight: UIFont.Weight = .regular) -> UIFont {
        UIFontMetrics(forTextStyle: .body).scaledFont(for: .monospacedSystemFont(ofSize: size, weight: weight))
    }

    private static func bold(_ style: UIFont.TextStyle) -> UIFont {
        let base = UIFont.preferredFont(forTextStyle: style)
        return UIFont(descriptor: base.fontDescriptor.withSymbolicTraits(.traitBold) ?? base.fontDescriptor, size: 0)
    }

    private static func label(_ text: String, font: UIFont, color: UIColor) -> UILabel {
        let label = UILabel()
        label.text = text
        label.font = font
        label.textColor = color
        label.numberOfLines = 0
        label.adjustsFontForContentSizeCategory = true
        return label
    }

    private static func section(_ title: String) -> UIView {
        let label = label(title.uppercased(), font: bold(.caption1), color: secondary)
        label.accessibilityTraits = .header
        let wrapper = UIStackView(arrangedSubviews: [label])
        wrapper.layoutMargins = UIEdgeInsets(top: 12, left: 0, bottom: 0, right: 0)
        wrapper.isLayoutMarginsRelativeArrangement = true
        return wrapper
    }

    private static func button(_ title: String, identifier: String, target: Any, action: Selector) -> UIButton {
        let button = UIButton(type: .system)
        button.setTitle(title, for: .normal)
        button.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.accessibilityIdentifier = identifier
        button.addTarget(target, action: action, for: .touchUpInside)
        return button
    }

    /// The excerpt with its failing line (the one starting with `>`) highlighted.
    static func excerpt(_ excerpt: String) -> NSAttributedString {
        let result = NSMutableAttributedString()
        let lines = excerpt.components(separatedBy: "\n")
        for (index, line) in lines.enumerated() {
            let failing = line.hasPrefix(">")
            var attributes: [NSAttributedString.Key: Any] = [
                .font: mono(12, weight: failing ? .bold : .regular),
                .foregroundColor: failing ? UIColor.white : secondary,
            ]
            if failing { attributes[.backgroundColor] = failingLine }
            result.append(NSAttributedString(string: line + (index < lines.count - 1 ? "\n" : ""), attributes: attributes))
        }
        return result
    }
}
