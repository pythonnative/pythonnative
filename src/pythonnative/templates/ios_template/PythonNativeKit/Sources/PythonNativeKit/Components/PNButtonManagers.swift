import UIKit

/// A closure-backed `UIControl` target with the duplicate-send filter the
/// simulator's event injection needs (one `UIEvent`, two action sends).
public final class PNActionTarget: NSObject {
    private let handler: () -> Void
    private var lastTimestamp: TimeInterval?

    public init(_ handler: @escaping () -> Void) {
        self.handler = handler
    }

    /// Attach `handler` to `control` for `events`, retained by the view's state.
    @discardableResult
    public static func attach(_ control: UIControl, events: UIControl.Event, _ handler: @escaping () -> Void) -> PNActionTarget {
        let target = PNActionTarget(handler)
        control.addTarget(target, action: #selector(fire(_:forEvent:)), for: events)
        PNViewState.existing(for: control)?.retained.append(target)
        return target
    }

    @objc func fire(_ sender: Any?, forEvent event: UIEvent?) {
        if let timestamp = event?.timestamp {
            if lastTimestamp == timestamp {
                PNLog.once(PNLog.components, key: "control-dedupe", "dropped a duplicated control action (one UIEvent, two sends)")
                return
            }
            lastTimestamp = timestamp
        }
        handler()
    }
}

/// `Button`: a system `UIButton` emitting `on_press`.
public final class PNButtonManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UIButton(type: .system)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let button = view as? UIButton {
            PNActionTarget.attach(button, events: .touchUpInside) { [weak button] in
                guard let button = button else { return }
                PNEvents.emit(button, "on_press")
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let button = view as? UIButton else { return }
        if PNProps.has(props, "title") {
            button.setTitle(PNProps.string(PNProps.value(props, "title")) ?? "", for: .normal)
        }
        if let size = PNProps.double(PNProps.value(props, "font_size")) {
            button.titleLabel?.font = UIFont.systemFont(ofSize: CGFloat(size))
        }
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            button.backgroundColor = color
            if !PNProps.has(props, "color") {
                button.setTitleColor(.white, for: .normal)
            }
        }
        if let color = PNColor.parse(PNProps.value(props, "color")) {
            button.setTitleColor(color, for: .normal)
        }
        if PNProps.has(props, "enabled") {
            button.isEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true
        }
        PNViewStyler.applyDecoration(button, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let intrinsic = view.intrinsicContentSize
        var w = intrinsic.width + 24
        var h = intrinsic.height + 12
        if maxW.isFinite { w = min(w, maxW) }
        if maxH.isFinite { h = min(h, maxH) }
        return CGSize(width: max(w, 44), height: max(h, 32))
    }
}

/// `Checkbox`: an SF Symbol button toggling checked / unchecked.
public final class PNCheckboxManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UIButton(type: .custom)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let button = view as? UIButton {
            PNActionTarget.attach(button, events: .touchUpInside) { [weak self, weak button] in
                guard let self = self, let button = button else { return }
                self.toggle(button)
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let button = view as? UIButton, let state = PNViewState.existing(for: button) else { return }
        if initial {
            let ink = PNColor.parse("#111111") ?? .label
            button.setTitleColor(ink, for: .normal)
            button.tintColor = ink
        }
        if PNProps.has(props, "value") {
            state.extras["value"] = PNProps.bool(PNProps.value(props, "value")) ?? false
        }
        if PNProps.has(props, "label") {
            let label = PNProps.string(PNProps.value(props, "label")) ?? ""
            button.setTitle(label, for: .normal)
            button.accessibilityLabel = label
        }
        if PNProps.has(props, "disabled") {
            button.isEnabled = !(PNProps.bool(PNProps.value(props, "disabled")) ?? false)
        }
        updateImage(button)
        PNViewStyler.applyAccessibility(button, props)
    }

    private func toggle(_ button: UIButton) {
        guard let state = PNViewState.existing(for: button) else { return }
        if PNProps.bool(PNProps.value(state.props, "disabled")) == true { return }
        let newValue = !state.flag("value")
        // Optimistic flip so the box feels instant; the `value` prop re-syncs it.
        state.extras["value"] = newValue
        updateImage(button)
        PNEvents.emit(button, "on_change", [newValue])
    }

    private func updateImage(_ button: UIButton) {
        guard let state = PNViewState.existing(for: button) else { return }
        let checked = state.flag("value")
        guard var image = UIImage(systemName: checked ? "checkmark.square.fill" : "square") else { return }
        if checked, let color = PNColor.parse(PNProps.value(state.props, "color")) {
            image = image.withTintColor(color, renderingMode: .alwaysOriginal)
        }
        button.setImage(image, for: .normal)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let size = view.sizeThatFits(CGSize(width: PNComponentManager.clampConstraint(maxW), height: PNComponentManager.clampConstraint(maxH)))
        var w = max(size.width + 8, 28)
        if maxW.isFinite { w = min(w, maxW) }
        return CGSize(width: w, height: max(size.height, 28))
    }
}

/// `Picker`: a button that presents an action sheet listing the options.
public final class PNPickerManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UIButton(type: .system)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let button = view as? UIButton {
            PNActionTarget.attach(button, events: .touchUpInside) { [weak self, weak button] in
                guard let self = self, let button = button else { return }
                self.presentSheet(button)
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let button = view as? UIButton else { return }
        button.setTitle(PNPickerManager.title(for: mergedProps(button)), for: .normal)
        PNViewStyler.applyAccessibility(button, props)
    }

    static func items(_ props: [String: Any]) -> [[String: Any]] {
        ((PNProps.value(props, "items") as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
    }

    static func title(for props: [String: Any]) -> String {
        let selected = PNProps.value(props, "value")
        for item in items(props) {
            if let value = PNProps.value(item, "value"), PNJSON.encode(value) == PNJSON.encode(selected) {
                return PNProps.string(item["label"]) ?? PNProps.string(item["value"]) ?? ""
            }
        }
        return PNProps.string(PNProps.value(props, "placeholder")) ?? "Select…"
    }

    private func presentSheet(_ button: UIButton) {
        let merged = mergedProps(button)
        let items = PNPickerManager.items(merged)
        var buttons: [[String: Any]] = items.map { ["label": PNProps.string($0["label"]) ?? PNProps.string($0["value"]) ?? ""] }
        buttons.append(["label": "Cancel", "style": "cancel"])
        PNAlertPresenter.present(
            title: PNProps.string(PNProps.value(merged, "placeholder")) ?? "Select…",
            message: nil, buttons: buttons, style: "action_sheet"
        ) { index in
            guard index >= 0, index < items.count else { return }
            PNEvents.emit(button, "on_change", [PNProps.value(items[index], "value")])
        }
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let size = view.sizeThatFits(CGSize(width: PNComponentManager.clampConstraint(maxW), height: PNComponentManager.clampConstraint(maxH)))
        return CGSize(width: size.width + 16, height: size.height + 8)
    }
}
