import UIKit

/// Color parsing shared by every manager.
///
/// Accepts `#RGB`, `#RGBA`, `#RRGGBB`, `#AARRGGBB` (the PythonNative
/// convention: alpha first), `rgb(r, g, b)`, `rgba(r, g, b, a)`, CSS
/// named colors, `"transparent"`, raw ARGB integers, and
/// `{"light": c, "dark": c}` dictionaries for dynamic colors.
public enum PNColor {
    /// Parse `value` into a `UIColor`, or `nil` when it isn't a color.
    public static func parse(_ value: Any?) -> UIColor? {
        switch value {
        case nil, is NSNull:
            return nil
        case let dict as [String: Any]:
            return dynamic(dict)
        case let number as NSNumber where !(value is Bool):
            return fromARGB(number.int64Value)
        case let int as Int:
            return fromARGB(Int64(int))
        case let string as String:
            return parse(string: string)
        default:
            return nil
        }
    }

    /// Parse a color string; see `parse(_:)` for the accepted grammar.
    public static func parse(string raw: String) -> UIColor? {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.isEmpty { return nil }
        let lower = text.lowercased()
        if lower == "transparent" || lower == "clear" || lower == "none" {
            return UIColor.clear
        }
        if text.hasPrefix("#") {
            return parseHex(String(text.dropFirst()))
        }
        if lower.hasPrefix("rgb") {
            return parseRGBFunction(lower)
        }
        if let named = PNNamedColors.table[lower] {
            return fromARGB(named)
        }
        if let hex = parseHex(text), text.count == 6 || text.count == 8 {
            return hex
        }
        return nil
    }

    /// Components (0...1) of `color` in the sRGB space.
    public static func components(_ color: UIColor) -> (r: CGFloat, g: CGFloat, b: CGFloat, a: CGFloat) {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        if color.getRed(&r, green: &g, blue: &b, alpha: &a) {
            return (r, g, b, a)
        }
        var white: CGFloat = 0
        if color.getWhite(&white, alpha: &a) {
            return (white, white, white, a)
        }
        return (0, 0, 0, 1)
    }

    /// `#AARRGGBB` string for `color`, matching the Python interpolation output.
    public static func hexString(_ color: UIColor) -> String {
        let c = components(color)
        func byte(_ v: CGFloat) -> Int { Int((max(0, min(1, v)) * 255).rounded()) }
        return String(format: "#%02X%02X%02X%02X", byte(c.a), byte(c.r), byte(c.g), byte(c.b))
    }

    /// Build a color from a 32-bit ARGB integer (signed or unsigned).
    public static func fromARGB(_ value: Int64) -> UIColor {
        var argb = value
        if argb < 0 { argb += 0x1_0000_0000 }
        let a = CGFloat((argb >> 24) & 0xFF) / 255
        let r = CGFloat((argb >> 16) & 0xFF) / 255
        let g = CGFloat((argb >> 8) & 0xFF) / 255
        let b = CGFloat(argb & 0xFF) / 255
        return UIColor(red: r, green: g, blue: b, alpha: a)
    }

    // MARK: - Private

    private static func parseHex(_ digits: String) -> UIColor? {
        var hex = digits
        switch hex.count {
        case 3:
            hex = "FF" + hex.map { "\($0)\($0)" }.joined()
        case 4:
            // #RGBA short form (CSS): expand then move alpha to the front.
            let expanded = hex.map { "\($0)\($0)" }
            hex = expanded[3] + expanded[0] + expanded[1] + expanded[2]
        case 6:
            hex = "FF" + hex
        case 8:
            break
        default:
            return nil
        }
        guard let value = Int64(hex, radix: 16) else { return nil }
        return fromARGB(value)
    }

    private static func parseRGBFunction(_ text: String) -> UIColor? {
        guard let open = text.firstIndex(of: "("), let close = text.lastIndex(of: ")"), open < close else { return nil }
        let inner = text[text.index(after: open)..<close]
        let parts = inner.split(whereSeparator: { $0 == "," || $0 == " " || $0 == "/" })
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        guard parts.count == 3 || parts.count == 4 else { return nil }
        func channel(_ s: String) -> CGFloat? {
            if s.hasSuffix("%"), let v = Double(s.dropLast()) { return CGFloat(v / 100) }
            guard let v = Double(s) else { return nil }
            return CGFloat(v / 255)
        }
        func alpha(_ s: String) -> CGFloat? {
            if s.hasSuffix("%"), let v = Double(s.dropLast()) { return CGFloat(v / 100) }
            guard let v = Double(s) else { return nil }
            return CGFloat(v)
        }
        guard let r = channel(parts[0]), let g = channel(parts[1]), let b = channel(parts[2]) else { return nil }
        let a = parts.count == 4 ? (alpha(parts[3]) ?? 1) : 1
        return UIColor(red: clamp(r), green: clamp(g), blue: clamp(b), alpha: clamp(a))
    }

    private static func dynamic(_ dict: [String: Any]) -> UIColor? {
        let light = parse(dict["light"] ?? dict["default"])
        let dark = parse(dict["dark"])
        guard light != nil || dark != nil else { return nil }
        return UIColor { traits in
            if traits.userInterfaceStyle == .dark {
                return dark ?? light ?? .clear
            }
            return light ?? dark ?? .clear
        }
    }

    private static func clamp(_ v: CGFloat) -> CGFloat { max(0, min(1, v)) }
}

/// CSS named colors as ARGB integers.
enum PNNamedColors {
    static let table: [String: Int64] = [
        "black": 0xFF00_0000, "white": 0xFFFF_FFFF, "red": 0xFFFF_0000, "green": 0xFF00_8000,
        "blue": 0xFF00_00FF, "yellow": 0xFFFF_FF00, "cyan": 0xFF00_FFFF, "aqua": 0xFF00_FFFF,
        "magenta": 0xFFFF_00FF, "fuchsia": 0xFFFF_00FF, "gray": 0xFF80_8080, "grey": 0xFF80_8080,
        "silver": 0xFFC0_C0C0, "maroon": 0xFF80_0000, "olive": 0xFF80_8000, "lime": 0xFF00_FF00,
        "teal": 0xFF00_8080, "navy": 0xFF00_0080, "purple": 0xFF80_0080, "orange": 0xFFFF_A500,
        "pink": 0xFFFF_C0CB, "brown": 0xFFA5_2A2A, "gold": 0xFFFF_D700, "indigo": 0xFF4B_0082,
        "violet": 0xFFEE_82EE, "tomato": 0xFFFF_6347, "coral": 0xFFFF_7F50, "salmon": 0xFFFA_8072,
        "crimson": 0xFFDC_143C, "khaki": 0xFFF0_E68C, "beige": 0xFFF5_F5DC, "ivory": 0xFFFF_FFF0,
        "lavender": 0xFFE6_E6FA, "plum": 0xFFDD_A0DD, "orchid": 0xFFDA_70D6, "turquoise": 0xFF40_E0D0,
        "tan": 0xFFD2_B48C, "chocolate": 0xFFD2_691E, "firebrick": 0xFFB2_2222, "darkred": 0xFF8B_0000,
        "darkgreen": 0xFF00_6400, "darkblue": 0xFF00_008B, "darkgray": 0xFFA9_A9A9, "darkgrey": 0xFFA9_A9A9,
        "dimgray": 0xFF69_6969, "dimgrey": 0xFF69_6969, "lightgray": 0xFFD3_D3D3, "lightgrey": 0xFFD3_D3D3,
        "lightblue": 0xFFAD_D8E6, "lightgreen": 0xFF90_EE90, "lightyellow": 0xFFFF_FFE0, "lightpink": 0xFFFF_B6C1,
        "skyblue": 0xFF87_CEEB, "steelblue": 0xFF46_82B4, "royalblue": 0xFF41_69E1, "dodgerblue": 0xFF1E_90FF,
        "deepskyblue": 0xFF00_BFFF, "slategray": 0xFF70_8090, "slategrey": 0xFF70_8090, "whitesmoke": 0xFFF5_F5F5,
        "gainsboro": 0xFFDC_DCDC, "snow": 0xFFFF_FAFA, "seagreen": 0xFF2E_8B57, "forestgreen": 0xFF22_8B22,
        "limegreen": 0xFF32_CD32, "springgreen": 0xFF00_FF7F, "mintcream": 0xFFF5_FFFA, "aquamarine": 0xFF7F_FFD4,
        "hotpink": 0xFFFF_69B4, "deeppink": 0xFFFF_1493, "orangered": 0xFFFF_4500, "darkorange": 0xFFFF_8C00,
        "goldenrod": 0xFFDA_A520, "sienna": 0xFFA0_522D, "peru": 0xFFCD_853F, "wheat": 0xFFF5_DEB3,
        "linen": 0xFFFA_F0E6, "azure": 0xFFF0_FFFF, "honeydew": 0xFFF0_FFF0, "midnightblue": 0xFF19_1970,
        "rebeccapurple": 0xFF66_3399, "mediumpurple": 0xFF93_70DB, "slateblue": 0xFF6A_5ACD, "cadetblue": 0xFF5F_9EA0,
        "cornflowerblue": 0xFF64_95ED, "darkcyan": 0xFF00_8B8B, "darkmagenta": 0xFF8B_008B, "darkviolet": 0xFF94_00D3,
        "darkslategray": 0xFF2F_4F4F, "darkslategrey": 0xFF2F_4F4F, "lightcoral": 0xFFF0_8080, "lightsalmon": 0xFFFF_A07A,
        "lightseagreen": 0xFF20_B2AA, "lightskyblue": 0xFF87_CEFA, "lightslategray": 0xFF77_8899, "lightslategrey": 0xFF77_8899,
        "lightsteelblue": 0xFFB0_C4DE, "mediumblue": 0xFF00_00CD, "mediumseagreen": 0xFF3C_B371, "mediumvioletred": 0xFFC7_1585,
        "olivedrab": 0xFF6B_8E23, "palegreen": 0xFF98_FB98, "paleturquoise": 0xFFAF_EEEE, "palevioletred": 0xFFDB_7093,
        "powderblue": 0xFFB0_E0E6, "rosybrown": 0xFFBC_8F8F, "saddlebrown": 0xFF8B_4513, "sandybrown": 0xFFF4_A460,
        "thistle": 0xFFD8_BFD8, "yellowgreen": 0xFF9A_CD32, "chartreuse": 0xFF7F_FF00, "greenyellow": 0xFFAD_FF2F,
    ]
}
