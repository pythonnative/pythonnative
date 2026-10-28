import UIKit

/// `Text`: a `UILabel` showing a `PNTextLayout`: rich spans, text
/// transforms, shadows, and the full font prop set.
///
/// The renderer core measures text on its workers with the same
/// `PNTextLayout` (see `PNMeasurement`), so the label and the measured size
/// come from one attributed string, line count, and truncation mode.
public final class PNTextManager: PNTypedComponentManager<TextProps> {
    public init() { super.init(TextProps.self) }
    static let fontKeys = PNTextLayout.fontKeys
    /// Props that change the label's content or line settings.
    static let layoutKeys = ["text", "spans", "text_transform", "color", "letter_spacing", "line_height",
                             "text_decoration", "text_align", "max_lines", "ellipsize_mode"]
        + fontKeys + PNTextLayout.textShadowKeys

    public override func makeView(props: [String: Any]) -> UIView {
        let label = PNLabel(frame: .zero)
        label.numberOfLines = 0
        label.adjustsFontForContentSizeCategory = true
        label.translatesAutoresizingMaskIntoConstraints = true
        return label
    }

    public override func applyTyped(view: UIView, props: TextProps, raw: [String: Any], initial: Bool) {
        let changed = raw
        guard let label = view as? UILabel else { return }
        let merged = mergedProps(label)
        let contentChanged = initial || PNTextManager.layoutKeys.contains(where: { PNProps.has(changed, $0) })
        if contentChanged {
            let layout = PNTextLayout(merged)
            label.font = PNTextLayout.font(from: merged)
            // An attributed string resets the label's line settings from its
            // paragraph style, so they're applied after it.
            label.attributedText = layout.attributed
            label.textAlignment = layout.alignment
            label.numberOfLines = layout.numberOfLines
            label.lineBreakMode = layout.lineBreakMode
            let state = PNViewState.existing(for: label)
            state?.extras["span_ranges"] = layout.spanRanges
            state?.extras["span_pressable"] = layout.spanPressable
        }
        if props.has_background_color { label.backgroundColor = PNColor.parse(PNProps.value(changed, "background_color")) }
        if props.has_selectable, let selectable = label as? PNLabel {
            selectable.isSelectable = props.selectable ?? false
        }
        if props.has_allow_font_scaling {
            label.adjustsFontForContentSizeCategory = props.allow_font_scaling ?? true
        }
        if props.has_spans || initial || PNProps.has(changed, "_pn_events"), let pressable = label as? PNLabel {
            let state = PNViewState.existing(for: label)
            let spanPressable = (state?.extras["span_pressable"] as? [Bool])?.contains(true) ?? false
            pressable.isPressable = (state?.hasEvent("on_press") ?? false) || spanPressable
        }
        PNViewStyler.applyDecoration(label, changed)
        if contentChanged, !initial {
            PNTextManager.announceIfLive(label, merged)
        }
    }

    /// `accessibility_live_region`: `assertive` announces the new text,
    /// `polite` reports a layout change VoiceOver reads when idle.
    static func announceIfLive(_ label: UILabel, _ merged: [String: Any]) {
        switch PNProps.string(PNProps.value(merged, "accessibility_live_region")) {
        case "assertive":
            UIAccessibility.post(notification: .announcement, argument: label.attributedText?.string ?? label.text ?? "")
        case "polite":
            UIAccessibility.post(notification: .layoutChanged, argument: label)
        default:
            break
        }
    }

    // MARK: - Press handling

    /// Resolve a tap at `point` (label coordinates) to the span it landed
    /// on, or `nil` when it missed every span.
    static func spanIndex(at point: CGPoint, in label: UILabel) -> Int? {
        guard let state = PNViewState.existing(for: label), state.extras["span_ranges"] as? [NSRange] != nil else { return nil }
        return PNTextLayout(state.props).spanIndex(at: point, in: label.bounds.size)
    }

    // MARK: - Shared helpers

    /// Resolve a `UIFont` from font props (headers, buttons, inputs).
    static func font(from props: [String: Any], base: UIFont?) -> UIFont {
        PNTextLayout.font(from: props)
    }

    public static func lineBreakMode(_ value: String?) -> NSLineBreakMode {
        PNTextLayout.lineBreakMode(value)
    }

    public static func transform(_ text: String?, mode: String?) -> String {
        PNTextLayout.transform(text, mode: mode)
    }
}

/// The `Text` label. `selectable` is implemented as a long-press "Copy"
/// edit menu (`UIEditMenuInteraction` on iOS 16, `UIMenuController`
/// before) that copies the whole label text; the label stays a `UILabel`
/// so spans and Dynamic Type behave natively and no drag-selection
/// handles appear.
public final class PNLabel: UILabel {
    private var longPress: UILongPressGestureRecognizer?
    private var menuInteraction: NSObject?
    private var tap: UITapGestureRecognizer?

    /// Whether the label listens for taps (`on_press` wired or a span is `pressable`).
    public var isPressable: Bool = false {
        didSet {
            guard isPressable != oldValue else { return }
            if isPressable {
                isUserInteractionEnabled = true
                let recognizer = UITapGestureRecognizer(target: self, action: #selector(handleTap(_:)))
                recognizer.cancelsTouchesInView = false
                addGestureRecognizer(recognizer)
                tap = recognizer
            } else if let recognizer = tap {
                removeGestureRecognizer(recognizer)
                tap = nil
            }
        }
    }

    /// Route a tap at `point`: a pressable span reports `on_span_press(index)`,
    /// anything else reports the label's own `on_press`.
    @discardableResult
    public func press(at point: CGPoint) -> Bool {
        if let index = PNTextManager.spanIndex(at: point, in: self),
           let flags = PNViewState.existing(for: self)?.extras["span_pressable"] as? [Bool],
           flags.indices.contains(index), flags[index] {
            PNComponentEvents.Text.on_span_press(self, Int64(index))
            return true
        }
        guard PNViewState.existing(for: self)?.hasEvent("on_press") == true else { return false }
        PNComponentEvents.Text.on_press(self)
        return true
    }

    @objc private func handleTap(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended else { return }
        press(at: recognizer.location(in: self))
    }

    /// Whether a long press offers to copy the text.
    public var isSelectable: Bool = false {
        didSet {
            guard isSelectable != oldValue else { return }
            if isSelectable { installSelection() } else { removeSelection() }
        }
    }

    public override var canBecomeFirstResponder: Bool { isSelectable }

    public override func canPerformAction(_ action: Selector, withSender sender: Any?) -> Bool {
        isSelectable && action == #selector(copy(_:))
    }

    public override func copy(_ sender: Any?) {
        UIPasteboard.general.string = attributedText?.string ?? text ?? ""
    }

    private func installSelection() {
        isUserInteractionEnabled = true
        let press = UILongPressGestureRecognizer(target: self, action: #selector(showCopyMenu(_:)))
        press.cancelsTouchesInView = false
        addGestureRecognizer(press)
        longPress = press
        if #available(iOS 16.0, *) {
            let interaction = UIEditMenuInteraction(delegate: nil)
            addInteraction(interaction)
            menuInteraction = interaction
        }
    }

    private func removeSelection() {
        if let press = longPress { removeGestureRecognizer(press) }
        longPress = nil
        if #available(iOS 16.0, *), let interaction = menuInteraction as? UIEditMenuInteraction {
            removeInteraction(interaction)
        }
        menuInteraction = nil
    }

    @objc private func showCopyMenu(_ recognizer: UILongPressGestureRecognizer) {
        guard recognizer.state == .began, isSelectable, window != nil else { return }
        becomeFirstResponder()
        let point = recognizer.location(in: self)
        if #available(iOS 16.0, *), let interaction = menuInteraction as? UIEditMenuInteraction {
            interaction.presentEditMenu(with: UIEditMenuConfiguration(identifier: nil, sourcePoint: point))
        } else {
            let controller = UIMenuController.shared
            controller.showMenu(from: self, rect: CGRect(origin: point, size: .zero))
        }
    }
}
