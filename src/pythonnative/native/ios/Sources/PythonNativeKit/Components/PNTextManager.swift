import UIKit

/// `Text`: a `UILabel` with rich spans, text transforms, shadows, and the
/// full font prop set.
public final class PNTextManager: PNTypedComponentManager<TextProps> {
    public init() { super.init(TextProps.self) }
    static let textShadowKeys = ["text_shadow_color", "text_shadow_offset", "text_shadow_radius"]
    static let attributedKeys = ["letter_spacing", "line_height", "text_decoration"] + textShadowKeys
    static let fontKeys = ["font_size", "font_weight", "font_family", "italic", "bold", "font_style"]
    static let spanRebuildKeys = ["spans", "text", "text_transform", "color"] + fontKeys + attributedKeys

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
        let hasSpans = !((PNProps.value(merged, "spans") as? [Any]) ?? []).isEmpty
        let textChanged = props.has_text || PNProps.has(changed, "text_transform")
        if textChanged, !hasSpans {
            label.text = PNTextManager.transform(PNProps.string(PNProps.value(merged, "text")), mode: PNProps.string(PNProps.value(merged, "text_transform")))
        }
        if initial || PNTextManager.fontKeys.contains(where: { PNProps.has(changed, $0) }) {
            label.font = PNTextManager.font(from: merged, base: label.font)
        }
        if props.has_color { label.textColor = PNColor.parse(PNProps.value(changed, "color")) ?? .label }
        if props.has_background_color { label.backgroundColor = PNColor.parse(PNProps.value(changed, "background_color")) }
        if props.has_max_lines {
            let lines = props.max_lines.map(Int.init) ?? 0
            label.numberOfLines = max(0, lines)
        }
        if PNProps.has(changed, "text_align") {
            label.textAlignment = PNTextManager.alignment(props.text_align?.rawValue)
        }
        if props.has_ellipsize_mode {
            label.lineBreakMode = PNTextManager.lineBreakMode(props.ellipsize_mode?.rawValue)
        }
        if props.has_selectable, let selectable = label as? PNLabel {
            selectable.isSelectable = props.selectable ?? false
        }
        if props.has_allow_font_scaling {
            label.adjustsFontForContentSizeCategory = props.allow_font_scaling ?? true
        }
        var contentChanged = textChanged
        if hasSpans {
            if PNTextManager.spanRebuildKeys.contains(where: { PNProps.has(changed, $0) }) {
                applySpans(label, merged)
                contentChanged = true
            }
        } else if props.has_spans {
            label.text = PNTextManager.transform(PNProps.string(PNProps.value(merged, "text")), mode: PNProps.string(PNProps.value(merged, "text_transform")))
            PNViewState.existing(for: label)?.extras.removeValue(forKey: "span_ranges")
            contentChanged = true
        } else if PNTextManager.attributedKeys.contains(where: { PNProps.has(changed, $0) })
            || (textChanged && PNTextManager.attributedKeys.contains { PNProps.value(merged, $0) != nil })
        {
            applyAttributed(label, merged)
        }
        if props.has_spans || initial || PNProps.has(changed, "_pn_events"), let pressable = label as? PNLabel {
            let state = PNViewState.existing(for: label)
            let spanPressable = (PNProps.value(merged, "spans") as? [Any])?.contains {
                PNProps.bool(($0 as? [String: Any])?["pressable"]) == true
            } ?? false
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
        guard let attributed = label.attributedText, attributed.length > 0,
              let ranges = PNViewState.existing(for: label)?.extras["span_ranges"] as? [NSRange] else { return nil }
        let storage = NSTextStorage(attributedString: attributed)
        let layout = NSLayoutManager()
        let container = NSTextContainer(size: label.bounds.size)
        container.lineFragmentPadding = 0
        container.maximumNumberOfLines = label.numberOfLines
        container.lineBreakMode = label.lineBreakMode
        layout.addTextContainer(container)
        storage.addLayoutManager(layout)
        let used = layout.usedRect(for: container)
        // UILabel centers its text vertically; align the layout the same way.
        let offset = CGPoint(x: 0, y: max(0, (label.bounds.height - used.height) / 2))
        let local = CGPoint(x: point.x - offset.x, y: point.y - offset.y)
        guard used.contains(local) || used.insetBy(dx: -4, dy: -4).contains(local) else { return nil }
        let index = layout.characterIndex(for: local, in: container, fractionOfDistanceBetweenInsertionPoints: nil)
        return ranges.firstIndex { NSLocationInRange(index, $0) }
    }

    // MARK: - Fonts

    /// Resolve a `UIFont` from the element's font props.
    static func font(from props: [String: Any], base: UIFont?) -> UIFont {
        let currentSize: CGFloat = 17
        let size = CGFloat(PNProps.double(PNProps.value(props, "font_size")) ?? Double(currentSize))
        var weight: Any? = PNProps.value(props, "font_weight")
        if weight == nil, PNProps.bool(PNProps.value(props, "bold")) == true { weight = "bold" }
        let italic = PNProps.bool(PNProps.value(props, "italic")) == true
            || PNProps.string(PNProps.value(props, "font_style")) == "italic"
        return font(size: size, weight: weight, family: PNProps.string(PNProps.value(props, "font_family")), italic: italic)
    }

    static func font(size: CGFloat, weight: Any?, family: String?, italic: Bool) -> UIFont {
        if let family = family, !family.isEmpty {
            // Bundled fonts (app/assets/fonts) are matched by family, weight,
            // and style from the manifest; the face already carries the
            // weight and slant, so no synthetic bold or italic is applied.
            if let name = PNAssets.shared.fontName(family: family, weight: numericWeight(weight), italic: italic),
               let bundled = UIFont(name: name, size: size) {
                return UIFontMetrics(forTextStyle: .body).scaledFont(for: bundled)
            }
            if let named = UIFont(name: family, size: size) {
                return UIFontMetrics(forTextStyle: .body).scaledFont(for: italic ? italicized(named, size: size) : named)
            }
        }
        let font = UIFont.systemFont(ofSize: size, weight: fontWeight(weight))
        return UIFontMetrics(forTextStyle: .body).scaledFont(for: italic ? italicized(font, size: size) : font)
    }

    /// A CSS-style weight (100 to 900) from a `font_weight` value.
    static func numericWeight(_ value: Any?) -> Int {
        if let name = value as? String {
            switch name.lowercased() {
            case "ultralight", "thin": return name.lowercased() == "thin" ? 200 : 100
            case "light": return 300
            case "normal", "regular": return 400
            case "medium": return 500
            case "semibold": return 600
            case "bold": return 700
            case "heavy": return 800
            case "black": return 900
            default: return Int(Double(name) ?? 400)
            }
        }
        return Int(PNProps.double(value) ?? 400)
    }

    static func italicized(_ font: UIFont, size: CGFloat) -> UIFont {
        var traits = font.fontDescriptor.symbolicTraits
        traits.insert(.traitItalic)
        guard let descriptor = font.fontDescriptor.withSymbolicTraits(traits) else { return font }
        return UIFont(descriptor: descriptor, size: size)
    }

    static func fontWeight(_ value: Any?) -> UIFont.Weight {
        if let name = value as? String {
            switch name.lowercased() {
            case "ultralight": return .ultraLight
            case "thin": return .thin
            case "light": return .light
            case "medium": return .medium
            case "semibold": return .semibold
            case "bold": return .bold
            case "heavy": return .heavy
            case "black": return .black
            default:
                if let numeric = Double(name) { return fontWeight(numeric) }
                return .regular
            }
        }
        guard let numeric = PNProps.double(value) else { return .regular }
        let n = max(100, min(900, numeric))
        switch n {
        case ...100: return .ultraLight
        case ...200: return .thin
        case ...300: return .light
        case ...400: return .regular
        case ...500: return .medium
        case ...600: return .semibold
        case ...700: return .bold
        case ...800: return .heavy
        default: return .black
        }
    }

    /// `ellipsize_mode` -> `NSLineBreakMode`. UIKit applies head and
    /// middle truncation to the last visible line of a multi-line label;
    /// `clip` cuts without an ellipsis.
    public static func lineBreakMode(_ value: String?) -> NSLineBreakMode {
        switch value {
        case "head": return .byTruncatingHead
        case "middle": return .byTruncatingMiddle
        case "clip": return .byClipping
        default: return .byTruncatingTail
        }
    }

    static func alignment(_ value: String?) -> NSTextAlignment {
        switch value {
        case "center": return .center
        case "right": return .right
        case "justify": return .justified
        case "natural": return .natural
        default: return .left
        }
    }

    // MARK: - Transforms

    /// Apply a `text_transform` mode (`uppercase`, `lowercase`, `capitalize`).
    public static func transform(_ text: String?, mode: String?) -> String {
        let s = text ?? ""
        switch mode {
        case "uppercase": return s.uppercased()
        case "lowercase": return s.lowercased()
        case "capitalize":
            var out = ""
            var atWordStart = true
            for ch in s {
                if ch.isWhitespace {
                    atWordStart = true
                    out.append(ch)
                } else if atWordStart {
                    out.append(contentsOf: String(ch).uppercased())
                    atWordStart = false
                } else {
                    out.append(ch)
                }
            }
            return out
        default: return s
        }
    }

    // MARK: - Attributed rendering

    static func baseAttributes(_ props: [String: Any], font: UIFont?) -> [NSAttributedString.Key: Any] {
        var attrs: [NSAttributedString.Key: Any] = [:]
        if let font = font { attrs[.font] = font }
        if let kern = PNProps.double(PNProps.value(props, "letter_spacing")) { attrs[.kern] = kern }
        if let lineHeight = PNProps.double(PNProps.value(props, "line_height")) {
            let style = NSMutableParagraphStyle()
            style.minimumLineHeight = CGFloat(lineHeight)
            style.maximumLineHeight = CGFloat(lineHeight)
            attrs[.paragraphStyle] = style
        }
        switch PNProps.string(PNProps.value(props, "text_decoration")) {
        case "underline": attrs[.underlineStyle] = NSUnderlineStyle.single.rawValue
        case "line_through": attrs[.strikethroughStyle] = NSUnderlineStyle.single.rawValue
        default: break
        }
        if let shadow = textShadow(props) { attrs[.shadow] = shadow }
        return attrs
    }

    static func textShadow(_ props: [String: Any]) -> NSShadow? {
        guard textShadowKeys.contains(where: { PNProps.value(props, $0) != nil }) else { return nil }
        let shadow = NSShadow()
        shadow.shadowColor = PNColor.parse(PNProps.value(props, "text_shadow_color")) ?? UIColor.black
        let (dx, dy) = PNViewStyler.shadowOffset(PNProps.value(props, "text_shadow_offset"))
        shadow.shadowOffset = CGSize(width: dx, height: dy)
        shadow.shadowBlurRadius = CGFloat(PNProps.double(PNProps.value(props, "text_shadow_radius")) ?? 0)
        return shadow
    }

    func applyAttributed(_ label: UILabel, _ props: [String: Any]) {
        guard let text = label.text, !text.isEmpty else { return }
        label.attributedText = NSAttributedString(string: text, attributes: PNTextManager.baseAttributes(props, font: label.font))
    }

    func applySpans(_ label: UILabel, _ merged: [String: Any]) {
        let mode = PNProps.string(PNProps.value(merged, "text_transform"))
        let spans = ((PNProps.value(merged, "spans") as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
        let texts = spans.map { PNTextManager.transform(PNProps.string($0["text"]), mode: mode) }
        let full = NSMutableAttributedString(string: texts.joined(), attributes: PNTextManager.baseAttributes(merged, font: label.font))
        let baseSize = CGFloat(PNProps.double(merged["font_size"]) ?? 17)
        var location = 0
        var ranges: [NSRange] = []
        for (span, text) in zip(spans, texts) {
            let length = (text as NSString).length
            let range = NSRange(location: location, length: length)
            ranges.append(range)
            location += length
            if length == 0 { continue }
            if PNTextManager.fontKeys.contains(where: { PNProps.value(span, $0) != nil }) {
                let size = CGFloat(PNProps.double(PNProps.value(span, "font_size")) ?? Double(baseSize))
                var weight: Any? = PNProps.value(span, "font_weight")
                if weight == nil, PNProps.bool(PNProps.value(span, "bold")) == true { weight = "bold" }
                let font = PNTextManager.font(
                    size: size, weight: weight, family: PNProps.string(PNProps.value(span, "font_family")),
                    italic: PNProps.bool(PNProps.value(span, "italic")) == true
                )
                full.addAttribute(.font, value: font, range: range)
            }
            if let color = PNColor.parse(PNProps.value(span, "color")) {
                full.addAttribute(.foregroundColor, value: color, range: range)
            }
            if let color = PNColor.parse(PNProps.value(span, "background_color")) {
                full.addAttribute(.backgroundColor, value: color, range: range)
            }
            if let kern = PNProps.double(PNProps.value(span, "letter_spacing")) {
                full.addAttribute(.kern, value: kern, range: range)
            }
            switch PNProps.string(PNProps.value(span, "text_decoration")) {
            case "underline": full.addAttribute(.underlineStyle, value: NSUnderlineStyle.single.rawValue, range: range)
            case "line_through": full.addAttribute(.strikethroughStyle, value: NSUnderlineStyle.single.rawValue, range: range)
            default: break
            }
        }
        label.attributedText = full
        PNViewState.existing(for: label)?.extras["span_ranges"] = ranges
        PNViewState.existing(for: label)?.extras["span_pressable"] = spans.map { PNProps.bool($0["pressable"]) == true }
    }
}

/// The `Text` label. `selectable` is implemented as a long-press "Copy"
/// edit menu (`UIEditMenuInteraction` on iOS 16, `UIMenuController`
/// before) that copies the whole label text; the label stays a `UILabel`
/// so measurement, spans, and Dynamic Type are unchanged and no
/// drag-selection handles appear.
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
