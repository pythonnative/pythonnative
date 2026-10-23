import UIKit

/// A `Text` element's content and line settings, built from its props on
/// any thread (RFC 0007).
///
/// The core measures text on its workers through this type, and
/// `PNTextManager` gives its label the same attributed string, line count,
/// and truncation, so the size the core lays out and what the label draws
/// come from one description. Fonts are scaled for the content size
/// category captured on the main thread, never by consulting UIKit state
/// from a worker.
public struct PNTextLayout {
    public let attributed: NSAttributedString
    public let numberOfLines: Int
    public let lineBreakMode: NSLineBreakMode
    public let alignment: NSTextAlignment
    /// UTF-16 ranges of each span, and whether it's pressable.
    public let spanRanges: [NSRange]
    public let spanPressable: [Bool]
    /// The first line's ascender, the text's baseline from its top.
    public let ascender: CGFloat

    static let textShadowKeys = ["text_shadow_color", "text_shadow_offset", "text_shadow_radius"]
    static let fontKeys = ["font_size", "font_weight", "font_family", "italic", "bold", "font_style"]

    public init(_ props: [String: Any]) {
        let mode = PNProps.string(PNProps.value(props, "text_transform"))
        let font = PNTextLayout.font(from: props)
        alignment = PNTextLayout.alignment(PNProps.string(PNProps.value(props, "text_align")))
        numberOfLines = max(0, PNProps.int(PNProps.value(props, "max_lines")) ?? 0)
        lineBreakMode = PNTextLayout.lineBreakMode(PNProps.string(PNProps.value(props, "ellipsize_mode")))
        let base = PNTextLayout.attributes(props, font: font, alignment: alignment)
        let spans = ((PNProps.value(props, "spans") as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
        if spans.isEmpty {
            attributed = NSAttributedString(string: PNTextLayout.transform(PNProps.string(PNProps.value(props, "text")), mode: mode), attributes: base)
            spanRanges = []
            spanPressable = []
        } else {
            let texts = spans.map { PNTextLayout.transform(PNProps.string($0["text"]), mode: mode) }
            let full = NSMutableAttributedString(string: texts.joined(), attributes: base)
            let baseSize = CGFloat(PNProps.double(PNProps.value(props, "font_size")) ?? 17)
            var location = 0
            var ranges: [NSRange] = []
            for (span, text) in zip(spans, texts) {
                let range = NSRange(location: location, length: (text as NSString).length)
                ranges.append(range)
                location += range.length
                if range.length == 0 { continue }
                if PNTextLayout.fontKeys.contains(where: { PNProps.value(span, $0) != nil }) {
                    var weight: Any? = PNProps.value(span, "font_weight")
                    if weight == nil, PNProps.bool(PNProps.value(span, "bold")) == true { weight = "bold" }
                    let spanFont = PNTextLayout.font(
                        size: CGFloat(PNProps.double(PNProps.value(span, "font_size")) ?? Double(baseSize)), weight: weight,
                        family: PNProps.string(PNProps.value(span, "font_family")),
                        italic: PNProps.bool(PNProps.value(span, "italic")) == true
                    )
                    full.addAttribute(.font, value: spanFont, range: range)
                }
                if let color = PNColor.parse(PNProps.value(span, "color")) { full.addAttribute(.foregroundColor, value: color, range: range) }
                if let color = PNColor.parse(PNProps.value(span, "background_color")) { full.addAttribute(.backgroundColor, value: color, range: range) }
                if let kern = PNProps.double(PNProps.value(span, "letter_spacing")) { full.addAttribute(.kern, value: kern, range: range) }
                switch PNProps.string(PNProps.value(span, "text_decoration")) {
                case "underline": full.addAttribute(.underlineStyle, value: NSUnderlineStyle.single.rawValue, range: range)
                case "line_through": full.addAttribute(.strikethroughStyle, value: NSUnderlineStyle.single.rawValue, range: range)
                default: break
                }
            }
            attributed = full
            spanRanges = ranges
            spanPressable = spans.map { PNProps.bool($0["pressable"]) == true }
        }
        var first = font
        if attributed.length > 0, let spanFont = attributed.attribute(.font, at: 0, effectiveRange: nil) as? UIFont { first = spanFont }
        ascender = first.ascender
    }

    // MARK: - Measurement

    /// The size the text occupies within `maxWidth` (and `maxHeight` when finite), rounded up to device pixels.
    public func measure(maxWidth: CGFloat, maxHeight: CGFloat = .infinity) -> CGSize {
        guard attributed.length > 0 else { return .zero }
        let width = maxWidth.isFinite && maxWidth > 0 ? maxWidth : CGFloat.greatestFiniteMagnitude
        let storage = NSTextStorage(attributedString: attributed)
        let layout = NSLayoutManager()
        let container = NSTextContainer(size: CGSize(width: width, height: CGFloat.greatestFiniteMagnitude))
        container.lineFragmentPadding = 0
        container.maximumNumberOfLines = numberOfLines
        container.lineBreakMode = lineBreakMode
        layout.addTextContainer(container)
        storage.addLayoutManager(layout)
        layout.ensureLayout(for: container)
        let used = layout.usedRect(for: container)
        let scale = PNTextLayout.environment().scale
        var size = CGSize(width: ceil(used.width * scale) / scale, height: ceil(used.height * scale) / scale)
        if maxWidth.isFinite { size.width = min(size.width, maxWidth) }
        if maxHeight.isFinite, maxHeight > 0 { size.height = min(size.height, maxHeight) }
        return size
    }

    /// The span a point (in a text box of `size`, centered vertically as a label draws) landed on.
    public func spanIndex(at point: CGPoint, in size: CGSize) -> Int? {
        guard attributed.length > 0, !spanRanges.isEmpty else { return nil }
        let storage = NSTextStorage(attributedString: attributed)
        let layout = NSLayoutManager()
        let container = NSTextContainer(size: size)
        container.lineFragmentPadding = 0
        container.maximumNumberOfLines = numberOfLines
        container.lineBreakMode = lineBreakMode
        layout.addTextContainer(container)
        storage.addLayoutManager(layout)
        let used = layout.usedRect(for: container)
        let offset = CGPoint(x: 0, y: max(0, (size.height - used.height) / 2))
        let local = CGPoint(x: point.x - offset.x, y: point.y - offset.y)
        guard used.insetBy(dx: -4, dy: -4).contains(local) else { return nil }
        let index = layout.characterIndex(for: local, in: container, fractionOfDistanceBetweenInsertionPoints: nil)
        return spanRanges.firstIndex { NSLocationInRange(index, $0) }
    }

    // MARK: - Environment

    private struct Environment {
        var category: UIContentSizeCategory = .large
        var scale: CGFloat = 3
    }

    private static let environmentLock = NSLock()
    private static var current = Environment()

    private static func environment() -> Environment {
        environmentLock.lock()
        defer { environmentLock.unlock() }
        return current
    }

    /// Record the content size category and screen scale; call on the main thread when they change.
    static func captureEnvironment() {
        let capture = {
            let value = Environment(category: UIApplication.shared.preferredContentSizeCategory, scale: UIScreen.main.scale)
            environmentLock.lock()
            current = value
            environmentLock.unlock()
        }
        if Thread.isMainThread { capture() } else { DispatchQueue.main.async(execute: capture) }
    }

    // MARK: - Fonts

    /// The element's font, scaled for the captured content size category.
    public static func font(from props: [String: Any]) -> UIFont {
        let size = CGFloat(PNProps.double(PNProps.value(props, "font_size")) ?? 17)
        var weight: Any? = PNProps.value(props, "font_weight")
        if weight == nil, PNProps.bool(PNProps.value(props, "bold")) == true { weight = "bold" }
        let italic = PNProps.bool(PNProps.value(props, "italic")) == true
            || PNProps.string(PNProps.value(props, "font_style")) == "italic"
        return font(size: size, weight: weight, family: PNProps.string(PNProps.value(props, "font_family")), italic: italic)
    }

    public static func font(size: CGFloat, weight: Any?, family: String?, italic: Bool) -> UIFont {
        let traits = UITraitCollection(preferredContentSizeCategory: environment().category)
        let metrics = UIFontMetrics(forTextStyle: .body)
        if let family = family, !family.isEmpty {
            // Bundled fonts (app/assets/fonts) are matched by family, weight,
            // and style from the manifest; the face already carries the
            // weight and slant, so no synthetic bold or italic is applied.
            if let name = PNAssets.shared.fontName(family: family, weight: numericWeight(weight), italic: italic),
               let bundled = UIFont(name: name, size: size) {
                return metrics.scaledFont(for: bundled, compatibleWith: traits)
            }
            if let named = UIFont(name: family, size: size) {
                return metrics.scaledFont(for: italic ? italicized(named, size: size) : named, compatibleWith: traits)
            }
        }
        let font = UIFont.systemFont(ofSize: size, weight: fontWeight(weight))
        return metrics.scaledFont(for: italic ? italicized(font, size: size) : font, compatibleWith: traits)
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
        switch max(100, min(900, numeric)) {
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

    // MARK: - Attributes

    /// `ellipsize_mode` -> `NSLineBreakMode`. Head and middle truncation
    /// apply to the last visible line; `clip` cuts without an ellipsis.
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

    static func attributes(_ props: [String: Any], font: UIFont, alignment: NSTextAlignment) -> [NSAttributedString.Key: Any] {
        var attrs: [NSAttributedString.Key: Any] = [.font: font]
        attrs[.foregroundColor] = PNColor.parse(PNProps.value(props, "color")) ?? UIColor.label
        if let kern = PNProps.double(PNProps.value(props, "letter_spacing")) { attrs[.kern] = kern }
        let style = NSMutableParagraphStyle()
        style.alignment = alignment
        if let lineHeight = PNProps.double(PNProps.value(props, "line_height")) {
            style.minimumLineHeight = CGFloat(lineHeight)
            style.maximumLineHeight = CGFloat(lineHeight)
        }
        attrs[.paragraphStyle] = style
        switch PNProps.string(PNProps.value(props, "text_decoration")) {
        case "underline": attrs[.underlineStyle] = NSUnderlineStyle.single.rawValue
        case "line_through": attrs[.strikethroughStyle] = NSUnderlineStyle.single.rawValue
        default: break
        }
        if textShadowKeys.contains(where: { PNProps.value(props, $0) != nil }) {
            let shadow = NSShadow()
            shadow.shadowColor = PNColor.parse(PNProps.value(props, "text_shadow_color")) ?? UIColor.black
            let (dx, dy) = PNViewStyler.shadowOffset(PNProps.value(props, "text_shadow_offset"))
            shadow.shadowOffset = CGSize(width: dx, height: dy)
            shadow.shadowBlurRadius = CGFloat(PNProps.double(PNProps.value(props, "text_shadow_radius")) ?? 0)
            attrs[.shadow] = shadow
        }
        return attrs
    }
}
