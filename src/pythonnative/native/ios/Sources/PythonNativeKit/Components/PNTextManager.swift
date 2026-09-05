import UIKit

/// `Text`: a `UILabel` with rich spans, text transforms, shadows, and the
/// full font prop set.
public final class PNTextManager: PNComponentManager {
    static let textShadowKeys = ["text_shadow_color", "text_shadow_offset", "text_shadow_radius"]
    static let attributedKeys = ["letter_spacing", "line_height", "text_decoration"] + textShadowKeys
    static let fontKeys = ["font_size", "font_weight", "font_family", "italic", "bold", "font_style"]
    static let spanRebuildKeys = ["spans", "text", "text_transform", "color"] + fontKeys + attributedKeys

    public override func makeView(props: [String: Any]) -> UIView {
        let label = UILabel(frame: .zero)
        label.numberOfLines = 0
        label.translatesAutoresizingMaskIntoConstraints = true
        return label
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let label = view as? UILabel else { return }
        let merged = mergedProps(label)
        let hasSpans = !((PNProps.value(merged, "spans") as? [Any]) ?? []).isEmpty
        let textChanged = PNProps.has(props, "text") || PNProps.has(props, "text_transform")
        if textChanged, !hasSpans {
            label.text = PNTextManager.transform(PNProps.string(PNProps.value(merged, "text")), mode: PNProps.string(PNProps.value(merged, "text_transform")))
        }
        if PNTextManager.fontKeys.contains(where: { PNProps.has(props, $0) }) {
            label.font = PNTextManager.font(from: merged, base: label.font)
        }
        if let color = PNColor.parse(PNProps.value(props, "color")) {
            label.textColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            label.backgroundColor = color
        }
        if PNProps.has(props, "max_lines") || PNProps.has(props, "number_of_lines") {
            let lines = PNProps.int(PNProps.value(props, "max_lines")) ?? PNProps.int(PNProps.value(props, "number_of_lines")) ?? 0
            label.numberOfLines = max(0, lines)
        }
        if PNProps.has(props, "text_align") {
            label.textAlignment = PNTextManager.alignment(PNProps.string(PNProps.value(props, "text_align")))
        }
        if PNProps.has(props, "selectable") {
            label.isUserInteractionEnabled = PNProps.bool(PNProps.value(props, "selectable")) ?? false
        }
        if hasSpans {
            if PNTextManager.spanRebuildKeys.contains(where: { PNProps.has(props, $0) }) {
                applySpans(label, merged)
            }
        } else if PNProps.has(props, "spans") {
            label.text = PNTextManager.transform(PNProps.string(PNProps.value(merged, "text")), mode: PNProps.string(PNProps.value(merged, "text_transform")))
        } else if PNTextManager.attributedKeys.contains(where: { PNProps.has(props, $0) })
            || (textChanged && PNTextManager.attributedKeys.contains { PNProps.value(merged, $0) != nil })
        {
            applyAttributed(label, merged)
        }
        PNViewStyler.applyDecoration(label, props)
    }

    // MARK: - Fonts

    /// Resolve a `UIFont` from the element's font props.
    static func font(from props: [String: Any], base: UIFont?) -> UIFont {
        let currentSize = base?.pointSize ?? 17
        let size = CGFloat(PNProps.double(PNProps.value(props, "font_size")) ?? Double(currentSize))
        var weight: Any? = PNProps.value(props, "font_weight")
        if weight == nil, PNProps.bool(PNProps.value(props, "bold")) == true { weight = "bold" }
        let italic = PNProps.bool(PNProps.value(props, "italic")) == true
            || PNProps.string(PNProps.value(props, "font_style")) == "italic"
        return font(size: size, weight: weight, family: PNProps.string(PNProps.value(props, "font_family")), italic: italic)
    }

    static func font(size: CGFloat, weight: Any?, family: String?, italic: Bool) -> UIFont {
        if let family = family, !family.isEmpty, let named = UIFont(name: family, size: size) {
            return italic ? italicized(named, size: size) : named
        }
        let font = UIFont.systemFont(ofSize: size, weight: fontWeight(weight))
        return italic ? italicized(font, size: size) : font
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
        let baseSize = label.font?.pointSize ?? 17
        var location = 0
        for (span, text) in zip(spans, texts) {
            let length = (text as NSString).length
            let range = NSRange(location: location, length: length)
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
    }
}
