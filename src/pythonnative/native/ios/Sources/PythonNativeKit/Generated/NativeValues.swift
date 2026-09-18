import Foundation
import CoreFoundation

/// Presence of a nonrequired nullable record field, including explicit null.
public enum PNPresence<Value> {
    case absent
    case present(Value)
}

/// A JSON value, including explicit null. Arbitrary native objects can't cross.
public indirect enum PNJSONValue: Codable, Equatable {
    case null, bool(Bool), number(Double), string(String), array([PNJSONValue]), object([String: PNJSONValue])

    public init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer()
        if value.decodeNil() { self = .null }
        else if let item = try? value.decode(Bool.self) { self = .bool(item) }
        else if let item = try? value.decode(String.self) { self = .string(item) }
        else if let item = try? value.decode(Double.self), item.isFinite { self = .number(item) }
        else if let item = try? value.decode([PNJSONValue].self) { self = .array(item) }
        else { self = .object(try value.decode([String: PNJSONValue].self)) }
    }

    public func encode(to encoder: Encoder) throws {
        var value = encoder.singleValueContainer()
        switch self {
        case .null: try value.encodeNil()
        case .bool(let item): try value.encode(item)
        case .number(let item): try value.encode(item)
        case .string(let item): try value.encode(item)
        case .array(let item): try value.encode(item)
        case .object(let item): try value.encode(item)
        }
    }
}

/// Shared recursive codecs used by every generated component and module.
public enum PNValues {
    public static func decode<T: Decodable>(_ type: T.Type, _ value: Any?) throws -> T {
        let data = try JSONSerialization.data(withJSONObject: value ?? NSNull(), options: [.fragmentsAllowed, .sortedKeys])
        return try JSONDecoder().decode(type, from: data)
    }

    public static func encode<T: Encodable>(_ value: T) -> Any {
        do {
            return try checkedEncode(value)
        } catch {
            preconditionFailure("Generated native value isn't serializable: \(error)")
        }
    }

    public static func checkedEncode<T: Encodable>(_ value: T) throws -> Any {
        try JSONSerialization.jsonObject(with: JSONEncoder().encode(value), options: [.fragmentsAllowed])
    }

    public static func defaultValue(_ json: String) -> Any {
        try! JSONSerialization.jsonObject(with: Data(json.utf8), options: [.fragmentsAllowed])
    }
}

public enum NativeDecodeError: Error, LocalizedError {
    case invalid(String)
    public var errorDescription: String? {
        switch self { case .invalid(let message): return message }
    }
}

/// A generated normalized props decoder. Wire validation precedes mutation.
public protocol PNNativeProps {
    init(_ values: [String: Any], partial: Bool) throws
}

public enum PNViewWidth: Codable {
    case option0(Int64)
    case option1(Double)
    case option2(String)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Int64.self) { self = .option0(value); return }
        if let value = try? container.decode(Double.self) { self = .option1(value); return }
        if let value = try? container.decode(String.self) { self = .option2(value); return }
        throw NativeDecodeError.invalid("PNViewWidth")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        }
    }
}

public enum PNViewFlexDirection: String, Codable {
    case `row` = "row"
    case `column` = "column"
    case `row_reverse` = "row_reverse"
    case `column_reverse` = "column_reverse"
}

public enum PNViewFlexWrap: String, Codable {
    case `nowrap` = "nowrap"
    case `wrap` = "wrap"
    case `wrap_reverse` = "wrap_reverse"
}

public enum PNViewJustifyContent: String, Codable {
    case `flex_start` = "flex_start"
    case `center` = "center"
    case `flex_end` = "flex_end"
    case `space_between` = "space_between"
    case `space_around` = "space_around"
    case `space_evenly` = "space_evenly"
    case `start` = "start"
    case `leading` = "leading"
    case `top` = "top"
    case `end` = "end"
    case `trailing` = "trailing"
    case `bottom` = "bottom"
}

public enum PNViewAlignItems: String, Codable {
    case `stretch` = "stretch"
    case `flex_start` = "flex_start"
    case `center` = "center"
    case `flex_end` = "flex_end"
    case `baseline` = "baseline"
    case `auto` = "auto"
    case `start` = "start"
    case `leading` = "leading"
    case `top` = "top"
    case `end` = "end"
    case `trailing` = "trailing"
    case `bottom` = "bottom"
    case `fill` = "fill"
}

public enum PNViewAlignContent: String, Codable {
    case `flex_start` = "flex_start"
    case `center` = "center"
    case `flex_end` = "flex_end"
    case `stretch` = "stretch"
    case `space_between` = "space_between"
    case `space_around` = "space_around"
    case `space_evenly` = "space_evenly"
}

public enum PNViewDirection: String, Codable {
    case `ltr` = "ltr"
    case `rtl` = "rtl"
}

public enum PNViewDisplay: String, Codable {
    case `flex` = "flex"
    case `none` = "none"
}

public enum PNViewPosition: String, Codable {
    case `relative` = "relative"
    case `absolute` = "absolute"
}

public struct PNEdgeInsets: Codable {
    public let `top`: PNViewWidth?
    public let `right`: PNViewWidth?
    public let `bottom`: PNViewWidth?
    public let `left`: PNViewWidth?
    public let `horizontal`: PNViewWidth?
    public let `vertical`: PNViewWidth?
    public let `all`: PNViewWidth?
    public init(`top`: PNViewWidth?, `right`: PNViewWidth?, `bottom`: PNViewWidth?, `left`: PNViewWidth?, `horizontal`: PNViewWidth?, `vertical`: PNViewWidth?, `all`: PNViewWidth?) {
        self.`top` = `top`
        self.`right` = `right`
        self.`bottom` = `bottom`
        self.`left` = `left`
        self.`horizontal` = `horizontal`
        self.`vertical` = `vertical`
        self.`all` = `all`
    }
    private enum CodingKeys: String, CodingKey { case `top`; case `right`; case `bottom`; case `left`; case `horizontal`; case `vertical`; case `all` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`top` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`top`)
        self.`right` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`right`)
        self.`bottom` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`bottom`)
        self.`left` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`left`)
        self.`horizontal` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`horizontal`)
        self.`vertical` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`vertical`)
        self.`all` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`all`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`top`, forKey: .`top`)
        try container.encodeIfPresent(`right`, forKey: .`right`)
        try container.encodeIfPresent(`bottom`, forKey: .`bottom`)
        try container.encodeIfPresent(`left`, forKey: .`left`)
        try container.encodeIfPresent(`horizontal`, forKey: .`horizontal`)
        try container.encodeIfPresent(`vertical`, forKey: .`vertical`)
        try container.encodeIfPresent(`all`, forKey: .`all`)
    }
}

public enum PNViewPadding: Codable {
    case option0(Int64)
    case option1(Double)
    case option2(String)
    case option3(PNEdgeInsets)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Int64.self) { self = .option0(value); return }
        if let value = try? container.decode(Double.self) { self = .option1(value); return }
        if let value = try? container.decode(String.self) { self = .option2(value); return }
        if let value = try? container.decode(PNEdgeInsets.self) { self = .option3(value); return }
        throw NativeDecodeError.invalid("PNViewPadding")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        }
    }
}

public enum PNPNViewMargin3: String, Codable {
    case `auto` = "auto"
}

public enum PNViewMargin: Codable {
    case option0(Int64)
    case option1(Double)
    case option2(String)
    case option3(PNPNViewMargin3)
    case option4(PNEdgeInsets)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Int64.self) { self = .option0(value); return }
        if let value = try? container.decode(Double.self) { self = .option1(value); return }
        if let value = try? container.decode(String.self) { self = .option2(value); return }
        if let value = try? container.decode(PNPNViewMargin3.self) { self = .option3(value); return }
        if let value = try? container.decode(PNEdgeInsets.self) { self = .option4(value); return }
        throw NativeDecodeError.invalid("PNViewMargin")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        case .option4(let value): try container.encode(value)
        }
    }
}

public enum PNViewMarginTop: Codable {
    case option0(Int64)
    case option1(Double)
    case option2(String)
    case option3(PNPNViewMargin3)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Int64.self) { self = .option0(value); return }
        if let value = try? container.decode(Double.self) { self = .option1(value); return }
        if let value = try? container.decode(String.self) { self = .option2(value); return }
        if let value = try? container.decode(PNPNViewMargin3.self) { self = .option3(value); return }
        throw NativeDecodeError.invalid("PNViewMarginTop")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        }
    }
}

public enum PNViewOverflow: String, Codable {
    case `visible` = "visible"
    case `hidden` = "hidden"
    case `scroll` = "scroll"
}

public enum PNViewFontWeight: String, Codable {
    case `normal` = "normal"
    case `bold` = "bold"
    case `value_100` = "100"
    case `value_200` = "200"
    case `value_300` = "300"
    case `value_400` = "400"
    case `value_500` = "500"
    case `value_600` = "600"
    case `value_700` = "700"
    case `value_800` = "800"
    case `value_900` = "900"
}

public enum PNViewTextAlign: String, Codable {
    case `left` = "left"
    case `center` = "center"
    case `right` = "right"
    case `justify` = "justify"
    case `start` = "start"
    case `end` = "end"
}

public enum PNViewTextDecoration: String, Codable {
    case `none` = "none"
    case `underline` = "underline"
    case `line_through` = "line_through"
}

public enum PNViewTextTransform: String, Codable {
    case `none` = "none"
    case `uppercase` = "uppercase"
    case `lowercase` = "lowercase"
    case `capitalize` = "capitalize"
}

public struct PNShadowOffset: Codable {
    public let `width`: Double
    public let `height`: Double
    public init(`width`: Double, `height`: Double) {
        self.`width` = `width`
        self.`height` = `height`
    }
    private enum CodingKeys: String, CodingKey { case `width`; case `height` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`width` = try container.decode(Double.self, forKey: .`width`)
        self.`height` = try container.decode(Double.self, forKey: .`height`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`width`, forKey: .`width`)
        try container.encode(`height`, forKey: .`height`)
    }
}

public struct PNPNViewTextShadowOffset1: Codable {
    public let `item0`: Double
    public let `item1`: Double
    public init(`item0`: Double, `item1`: Double) {
        self.`item0` = `item0`
        self.`item1` = `item1`
    }
    public init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        `item0` = try container.decode(Double.self)
        `item1` = try container.decode(Double.self)
        if !container.isAtEnd { throw NativeDecodeError.invalid("Tuple length") }
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.unkeyedContainer()
        try container.encode(`item0`)
        try container.encode(`item1`)
    }
}

public enum PNViewTextShadowOffset: Codable {
    case option0(PNShadowOffset)
    case option1(PNPNViewTextShadowOffset1)
    case option2([Double])
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(PNShadowOffset.self) { self = .option0(value); return }
        if let value = try? container.decode(PNPNViewTextShadowOffset1.self) { self = .option1(value); return }
        if let value = try? container.decode([Double].self) { self = .option2(value); return }
        throw NativeDecodeError.invalid("PNViewTextShadowOffset")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        }
    }
}

public enum PNPNTransformRotateRotate: Codable {
    case option0(Double)
    case option1(String)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Double.self) { self = .option0(value); return }
        if let value = try? container.decode(String.self) { self = .option1(value); return }
        throw NativeDecodeError.invalid("PNPNTransformRotateRotate")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        }
    }
}

public struct PNTransformRotate: Codable {
    public let `rotate`: PNPNTransformRotateRotate
    public init(`rotate`: PNPNTransformRotateRotate) {
        self.`rotate` = `rotate`
    }
    private enum CodingKeys: String, CodingKey { case `rotate` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`rotate` = try container.decode(PNPNTransformRotateRotate.self, forKey: .`rotate`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`rotate`, forKey: .`rotate`)
    }
}

public struct PNTransformScale: Codable {
    public let `scale`: Double
    public init(`scale`: Double) {
        self.`scale` = `scale`
    }
    private enum CodingKeys: String, CodingKey { case `scale` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`scale` = try container.decode(Double.self, forKey: .`scale`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`scale`, forKey: .`scale`)
    }
}

public struct PNTransformScaleX: Codable {
    public let `scale_x`: Double
    public init(`scale_x`: Double) {
        self.`scale_x` = `scale_x`
    }
    private enum CodingKeys: String, CodingKey { case `scale_x` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`scale_x` = try container.decode(Double.self, forKey: .`scale_x`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`scale_x`, forKey: .`scale_x`)
    }
}

public struct PNTransformScaleY: Codable {
    public let `scale_y`: Double
    public init(`scale_y`: Double) {
        self.`scale_y` = `scale_y`
    }
    private enum CodingKeys: String, CodingKey { case `scale_y` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`scale_y` = try container.decode(Double.self, forKey: .`scale_y`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`scale_y`, forKey: .`scale_y`)
    }
}

public struct PNTransformTranslate: Codable {
    public let `translate_x`: Double?
    public let `translate_y`: Double?
    public init(`translate_x`: Double?, `translate_y`: Double?) {
        self.`translate_x` = `translate_x`
        self.`translate_y` = `translate_y`
    }
    private enum CodingKeys: String, CodingKey { case `translate_x`; case `translate_y` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`translate_x` = try container.decodeIfPresent(Double.self, forKey: .`translate_x`)
        self.`translate_y` = try container.decodeIfPresent(Double.self, forKey: .`translate_y`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`translate_x`, forKey: .`translate_x`)
        try container.encodeIfPresent(`translate_y`, forKey: .`translate_y`)
    }
}

public enum PNPNViewTransform6Item: Codable {
    case option0(PNTransformRotate)
    case option1(PNTransformScale)
    case option2(PNTransformScaleX)
    case option3(PNTransformScaleY)
    case option4(PNTransformTranslate)
    case option5([String: PNJSONValue])
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(PNTransformRotate.self) { self = .option0(value); return }
        if let value = try? container.decode(PNTransformScale.self) { self = .option1(value); return }
        if let value = try? container.decode(PNTransformScaleX.self) { self = .option2(value); return }
        if let value = try? container.decode(PNTransformScaleY.self) { self = .option3(value); return }
        if let value = try? container.decode(PNTransformTranslate.self) { self = .option4(value); return }
        if let value = try? container.decode([String: PNJSONValue].self) { self = .option5(value); return }
        throw NativeDecodeError.invalid("PNPNViewTransform6Item")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        case .option4(let value): try container.encode(value)
        case .option5(let value): try container.encode(value)
        }
    }
}

public enum PNViewTransform: Codable {
    case option0(PNTransformRotate)
    case option1(PNTransformScale)
    case option2(PNTransformScaleX)
    case option3(PNTransformScaleY)
    case option4(PNTransformTranslate)
    case option5([String: PNJSONValue])
    case option6([PNPNViewTransform6Item])
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(PNTransformRotate.self) { self = .option0(value); return }
        if let value = try? container.decode(PNTransformScale.self) { self = .option1(value); return }
        if let value = try? container.decode(PNTransformScaleX.self) { self = .option2(value); return }
        if let value = try? container.decode(PNTransformScaleY.self) { self = .option3(value); return }
        if let value = try? container.decode(PNTransformTranslate.self) { self = .option4(value); return }
        if let value = try? container.decode([String: PNJSONValue].self) { self = .option5(value); return }
        if let value = try? container.decode([PNPNViewTransform6Item].self) { self = .option6(value); return }
        throw NativeDecodeError.invalid("PNViewTransform")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        case .option4(let value): try container.encode(value)
        case .option5(let value): try container.encode(value)
        case .option6(let value): try container.encode(value)
        }
    }
}

public enum PNViewPointerEvents: String, Codable {
    case `auto` = "auto"
    case `none` = "none"
    case `box_none` = "box_none"
    case `box_only` = "box_only"
}

public enum PNViewHitSlop: Codable {
    case option0(Double)
    case option1([String: Double])
    case option2(PNJSONValue)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Double.self) { self = .option0(value); return }
        if let value = try? container.decode([String: Double].self) { self = .option1(value); return }
        if let value = try? container.decode(PNJSONValue.self) { self = .option2(value); return }
        throw NativeDecodeError.invalid("PNViewHitSlop")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        }
    }
}

public enum PNPNPNAccessibilityStateChecked1: String, Codable {
    case `mixed` = "mixed"
}

public enum PNPNAccessibilityStateChecked: Codable {
    case option0(Bool)
    case option1(PNPNPNAccessibilityStateChecked1)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Bool.self) { self = .option0(value); return }
        if let value = try? container.decode(PNPNPNAccessibilityStateChecked1.self) { self = .option1(value); return }
        throw NativeDecodeError.invalid("PNPNAccessibilityStateChecked")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        }
    }
}

public struct PNAccessibilityState: Codable {
    public let `disabled`: Bool?
    public let `selected`: Bool?
    public let `checked`: PNPNAccessibilityStateChecked?
    public let `busy`: Bool?
    public let `expanded`: Bool?
    public init(`disabled`: Bool?, `selected`: Bool?, `checked`: PNPNAccessibilityStateChecked?, `busy`: Bool?, `expanded`: Bool?) {
        self.`disabled` = `disabled`
        self.`selected` = `selected`
        self.`checked` = `checked`
        self.`busy` = `busy`
        self.`expanded` = `expanded`
    }
    private enum CodingKeys: String, CodingKey { case `disabled`; case `selected`; case `checked`; case `busy`; case `expanded` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`disabled` = try container.decodeIfPresent(Bool.self, forKey: .`disabled`)
        self.`selected` = try container.decodeIfPresent(Bool.self, forKey: .`selected`)
        self.`checked` = try container.decodeIfPresent(PNPNAccessibilityStateChecked.self, forKey: .`checked`)
        self.`busy` = try container.decodeIfPresent(Bool.self, forKey: .`busy`)
        self.`expanded` = try container.decodeIfPresent(Bool.self, forKey: .`expanded`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`disabled`, forKey: .`disabled`)
        try container.encodeIfPresent(`selected`, forKey: .`selected`)
        try container.encodeIfPresent(`checked`, forKey: .`checked`)
        try container.encodeIfPresent(`busy`, forKey: .`busy`)
        try container.encodeIfPresent(`expanded`, forKey: .`expanded`)
    }
}

public enum PNViewAccessibilityLiveRegion: String, Codable {
    case `none` = "none"
    case `polite` = "polite"
    case `assertive` = "assertive"
}

public enum PNViewPnHeaderSlot: String, Codable {
    case `left` = "left"
    case `right` = "right"
}

public enum PNActivityIndicatorSize: String, Codable {
    case `small` = "small"
    case `large` = "large"
}

public enum PNBlurViewBlurType: String, Codable {
    case `light` = "light"
    case `dark` = "dark"
    case `regular` = "regular"
    case `prominent` = "prominent"
    case `extra_light` = "extra_light"
    case `system_thin_material` = "system_thin_material"
    case `system_material` = "system_material"
    case `system_thick_material` = "system_thick_material"
    case `system_chrome_material` = "system_chrome_material"
}

public enum PNDatePickerMode: String, Codable {
    case `date` = "date"
    case `time` = "time"
    case `datetime` = "datetime"
}

public enum PNImageScaleType: String, Codable {
    case `cover` = "cover"
    case `contain` = "contain"
    case `stretch` = "stretch"
    case `center` = "center"
}

public struct PNImageLoadEvent: Codable {
    public let `width`: Double
    public let `height`: Double
    public init(`width`: Double, `height`: Double) {
        self.`width` = `width`
        self.`height` = `height`
    }
    private enum CodingKeys: String, CodingKey { case `width`; case `height` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`width` = try container.decode(Double.self, forKey: .`width`)
        self.`height` = try container.decode(Double.self, forKey: .`height`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`width`, forKey: .`width`)
        try container.encode(`height`, forKey: .`height`)
    }
}

public enum PNKeyboardAvoidingViewBehavior: String, Codable {
    case `padding` = "padding"
    case `position` = "position"
    case `height` = "height"
}

public enum PNModalAnimationType: String, Codable {
    case `slide` = "slide"
    case `fade` = "fade"
    case `none` = "none"
}

public enum PNModalPresentationStyle: String, Codable {
    case `page_sheet` = "page_sheet"
    case `form_sheet` = "form_sheet"
    case `full_screen` = "full_screen"
    case `overlay` = "overlay"
}

public enum PNSafeAreaViewEdgesItem: String, Codable {
    case `top` = "top"
    case `left` = "left"
    case `bottom` = "bottom"
    case `right` = "right"
}

public enum PNScreenPresentation: String, Codable {
    case `card` = "card"
    case `modal` = "modal"
}

public enum PNScreenAnimation: String, Codable {
    case `default` = "default"
    case `none` = "none"
    case `fade` = "fade"
    case `slide_from_right` = "slide_from_right"
    case `slide_from_bottom` = "slide_from_bottom"
}

public enum PNScreenTabBarBadge: Codable {
    case option0(String)
    case option1(Int64)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(String.self) { self = .option0(value); return }
        if let value = try? container.decode(Int64.self) { self = .option1(value); return }
        throw NativeDecodeError.invalid("PNScreenTabBarBadge")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        }
    }
}

public struct PNScrollViewRefreshControl: Codable {
    public let `width`: PNViewWidth?
    public let `height`: PNViewWidth?
    public let `min_width`: PNViewWidth?
    public let `max_width`: PNViewWidth?
    public let `min_height`: PNViewWidth?
    public let `max_height`: PNViewWidth?
    public let `aspect_ratio`: Double?
    public let `flex`: Double?
    public let `flex_grow`: Double?
    public let `flex_shrink`: Double?
    public let `flex_basis`: PNViewWidth?
    public let `flex_direction`: PNViewFlexDirection?
    public let `flex_wrap`: PNViewFlexWrap?
    public let `justify_content`: PNViewJustifyContent?
    public let `align_items`: PNViewAlignItems?
    public let `align_self`: PNViewAlignItems?
    public let `align_content`: PNViewAlignContent?
    public let `direction`: PNViewDirection?
    public let `display`: PNViewDisplay?
    public let `position`: PNViewPosition?
    public let `top`: PNViewWidth?
    public let `right`: PNViewWidth?
    public let `bottom`: PNViewWidth?
    public let `left`: PNViewWidth?
    public let `start`: PNViewWidth?
    public let `end`: PNViewWidth?
    public let `padding`: PNViewPadding?
    public let `padding_top`: PNViewWidth?
    public let `padding_bottom`: PNViewWidth?
    public let `padding_left`: PNViewWidth?
    public let `padding_right`: PNViewWidth?
    public let `padding_start`: PNViewWidth?
    public let `padding_end`: PNViewWidth?
    public let `padding_horizontal`: PNViewWidth?
    public let `padding_vertical`: PNViewWidth?
    public let `margin`: PNViewMargin?
    public let `margin_top`: PNViewMarginTop?
    public let `margin_bottom`: PNViewMarginTop?
    public let `margin_left`: PNViewMarginTop?
    public let `margin_right`: PNViewMarginTop?
    public let `margin_start`: PNViewMarginTop?
    public let `margin_end`: PNViewMarginTop?
    public let `margin_horizontal`: PNViewMarginTop?
    public let `margin_vertical`: PNViewMarginTop?
    public let `spacing`: Double?
    public let `gap`: Double?
    public let `row_gap`: Double?
    public let `column_gap`: Double?
    public let `overflow`: PNViewOverflow?
    public let `background_color`: String?
    public let `color`: String?
    public let `border_color`: String?
    public let `placeholder_color`: String?
    public let `tint_color`: PNPresence<String?>
    public let `border_width`: Double?
    public let `border_radius`: Double?
    public let `border_top_left_radius`: Double?
    public let `border_top_right_radius`: Double?
    public let `border_bottom_left_radius`: Double?
    public let `border_bottom_right_radius`: Double?
    public let `border_top_width`: Double?
    public let `border_right_width`: Double?
    public let `border_bottom_width`: Double?
    public let `border_left_width`: Double?
    public let `border_top_color`: String?
    public let `border_right_color`: String?
    public let `border_bottom_color`: String?
    public let `border_left_color`: String?
    public let `font_size`: Double?
    public let `font_family`: String?
    public let `font_weight`: PNViewFontWeight?
    public let `bold`: Bool?
    public let `italic`: Bool?
    public let `text_align`: PNViewTextAlign?
    public let `text_decoration`: PNViewTextDecoration?
    public let `text_transform`: PNViewTextTransform?
    public let `line_height`: Double?
    public let `letter_spacing`: Double?
    public let `max_lines`: Int64?
    public let `text_shadow_color`: String?
    public let `text_shadow_offset`: PNViewTextShadowOffset?
    public let `text_shadow_radius`: Double?
    public let `shadow_color`: String?
    public let `shadow_offset`: PNViewTextShadowOffset?
    public let `shadow_opacity`: Double?
    public let `shadow_radius`: Double?
    public let `elevation`: Double?
    public let `opacity`: Double?
    public let `transform`: PNViewTransform?
    public let `z_index`: Int64?
    public let `pointer_events`: PNViewPointerEvents?
    public let `refreshing`: Bool?
    public let `on_refresh`: PNPresence<Bool?>
    public let `accessibility_role`: String?
    public let `ref`: PNJSONValue?
    public let `on_layout`: Bool?
    public init(`width`: PNViewWidth?, `height`: PNViewWidth?, `min_width`: PNViewWidth?, `max_width`: PNViewWidth?, `min_height`: PNViewWidth?, `max_height`: PNViewWidth?, `aspect_ratio`: Double?, `flex`: Double?, `flex_grow`: Double?, `flex_shrink`: Double?, `flex_basis`: PNViewWidth?, `flex_direction`: PNViewFlexDirection?, `flex_wrap`: PNViewFlexWrap?, `justify_content`: PNViewJustifyContent?, `align_items`: PNViewAlignItems?, `align_self`: PNViewAlignItems?, `align_content`: PNViewAlignContent?, `direction`: PNViewDirection?, `display`: PNViewDisplay?, `position`: PNViewPosition?, `top`: PNViewWidth?, `right`: PNViewWidth?, `bottom`: PNViewWidth?, `left`: PNViewWidth?, `start`: PNViewWidth?, `end`: PNViewWidth?, `padding`: PNViewPadding?, `padding_top`: PNViewWidth?, `padding_bottom`: PNViewWidth?, `padding_left`: PNViewWidth?, `padding_right`: PNViewWidth?, `padding_start`: PNViewWidth?, `padding_end`: PNViewWidth?, `padding_horizontal`: PNViewWidth?, `padding_vertical`: PNViewWidth?, `margin`: PNViewMargin?, `margin_top`: PNViewMarginTop?, `margin_bottom`: PNViewMarginTop?, `margin_left`: PNViewMarginTop?, `margin_right`: PNViewMarginTop?, `margin_start`: PNViewMarginTop?, `margin_end`: PNViewMarginTop?, `margin_horizontal`: PNViewMarginTop?, `margin_vertical`: PNViewMarginTop?, `spacing`: Double?, `gap`: Double?, `row_gap`: Double?, `column_gap`: Double?, `overflow`: PNViewOverflow?, `background_color`: String?, `color`: String?, `border_color`: String?, `placeholder_color`: String?, `tint_color`: PNPresence<String?>, `border_width`: Double?, `border_radius`: Double?, `border_top_left_radius`: Double?, `border_top_right_radius`: Double?, `border_bottom_left_radius`: Double?, `border_bottom_right_radius`: Double?, `border_top_width`: Double?, `border_right_width`: Double?, `border_bottom_width`: Double?, `border_left_width`: Double?, `border_top_color`: String?, `border_right_color`: String?, `border_bottom_color`: String?, `border_left_color`: String?, `font_size`: Double?, `font_family`: String?, `font_weight`: PNViewFontWeight?, `bold`: Bool?, `italic`: Bool?, `text_align`: PNViewTextAlign?, `text_decoration`: PNViewTextDecoration?, `text_transform`: PNViewTextTransform?, `line_height`: Double?, `letter_spacing`: Double?, `max_lines`: Int64?, `text_shadow_color`: String?, `text_shadow_offset`: PNViewTextShadowOffset?, `text_shadow_radius`: Double?, `shadow_color`: String?, `shadow_offset`: PNViewTextShadowOffset?, `shadow_opacity`: Double?, `shadow_radius`: Double?, `elevation`: Double?, `opacity`: Double?, `transform`: PNViewTransform?, `z_index`: Int64?, `pointer_events`: PNViewPointerEvents?, `refreshing`: Bool?, `on_refresh`: PNPresence<Bool?>, `accessibility_role`: String?, `ref`: PNJSONValue?, `on_layout`: Bool?) {
        self.`width` = `width`
        self.`height` = `height`
        self.`min_width` = `min_width`
        self.`max_width` = `max_width`
        self.`min_height` = `min_height`
        self.`max_height` = `max_height`
        self.`aspect_ratio` = `aspect_ratio`
        self.`flex` = `flex`
        self.`flex_grow` = `flex_grow`
        self.`flex_shrink` = `flex_shrink`
        self.`flex_basis` = `flex_basis`
        self.`flex_direction` = `flex_direction`
        self.`flex_wrap` = `flex_wrap`
        self.`justify_content` = `justify_content`
        self.`align_items` = `align_items`
        self.`align_self` = `align_self`
        self.`align_content` = `align_content`
        self.`direction` = `direction`
        self.`display` = `display`
        self.`position` = `position`
        self.`top` = `top`
        self.`right` = `right`
        self.`bottom` = `bottom`
        self.`left` = `left`
        self.`start` = `start`
        self.`end` = `end`
        self.`padding` = `padding`
        self.`padding_top` = `padding_top`
        self.`padding_bottom` = `padding_bottom`
        self.`padding_left` = `padding_left`
        self.`padding_right` = `padding_right`
        self.`padding_start` = `padding_start`
        self.`padding_end` = `padding_end`
        self.`padding_horizontal` = `padding_horizontal`
        self.`padding_vertical` = `padding_vertical`
        self.`margin` = `margin`
        self.`margin_top` = `margin_top`
        self.`margin_bottom` = `margin_bottom`
        self.`margin_left` = `margin_left`
        self.`margin_right` = `margin_right`
        self.`margin_start` = `margin_start`
        self.`margin_end` = `margin_end`
        self.`margin_horizontal` = `margin_horizontal`
        self.`margin_vertical` = `margin_vertical`
        self.`spacing` = `spacing`
        self.`gap` = `gap`
        self.`row_gap` = `row_gap`
        self.`column_gap` = `column_gap`
        self.`overflow` = `overflow`
        self.`background_color` = `background_color`
        self.`color` = `color`
        self.`border_color` = `border_color`
        self.`placeholder_color` = `placeholder_color`
        self.`tint_color` = `tint_color`
        self.`border_width` = `border_width`
        self.`border_radius` = `border_radius`
        self.`border_top_left_radius` = `border_top_left_radius`
        self.`border_top_right_radius` = `border_top_right_radius`
        self.`border_bottom_left_radius` = `border_bottom_left_radius`
        self.`border_bottom_right_radius` = `border_bottom_right_radius`
        self.`border_top_width` = `border_top_width`
        self.`border_right_width` = `border_right_width`
        self.`border_bottom_width` = `border_bottom_width`
        self.`border_left_width` = `border_left_width`
        self.`border_top_color` = `border_top_color`
        self.`border_right_color` = `border_right_color`
        self.`border_bottom_color` = `border_bottom_color`
        self.`border_left_color` = `border_left_color`
        self.`font_size` = `font_size`
        self.`font_family` = `font_family`
        self.`font_weight` = `font_weight`
        self.`bold` = `bold`
        self.`italic` = `italic`
        self.`text_align` = `text_align`
        self.`text_decoration` = `text_decoration`
        self.`text_transform` = `text_transform`
        self.`line_height` = `line_height`
        self.`letter_spacing` = `letter_spacing`
        self.`max_lines` = `max_lines`
        self.`text_shadow_color` = `text_shadow_color`
        self.`text_shadow_offset` = `text_shadow_offset`
        self.`text_shadow_radius` = `text_shadow_radius`
        self.`shadow_color` = `shadow_color`
        self.`shadow_offset` = `shadow_offset`
        self.`shadow_opacity` = `shadow_opacity`
        self.`shadow_radius` = `shadow_radius`
        self.`elevation` = `elevation`
        self.`opacity` = `opacity`
        self.`transform` = `transform`
        self.`z_index` = `z_index`
        self.`pointer_events` = `pointer_events`
        self.`refreshing` = `refreshing`
        self.`on_refresh` = `on_refresh`
        self.`accessibility_role` = `accessibility_role`
        self.`ref` = `ref`
        self.`on_layout` = `on_layout`
    }
    private enum CodingKeys: String, CodingKey { case `width`; case `height`; case `min_width`; case `max_width`; case `min_height`; case `max_height`; case `aspect_ratio`; case `flex`; case `flex_grow`; case `flex_shrink`; case `flex_basis`; case `flex_direction`; case `flex_wrap`; case `justify_content`; case `align_items`; case `align_self`; case `align_content`; case `direction`; case `display`; case `position`; case `top`; case `right`; case `bottom`; case `left`; case `start`; case `end`; case `padding`; case `padding_top`; case `padding_bottom`; case `padding_left`; case `padding_right`; case `padding_start`; case `padding_end`; case `padding_horizontal`; case `padding_vertical`; case `margin`; case `margin_top`; case `margin_bottom`; case `margin_left`; case `margin_right`; case `margin_start`; case `margin_end`; case `margin_horizontal`; case `margin_vertical`; case `spacing`; case `gap`; case `row_gap`; case `column_gap`; case `overflow`; case `background_color`; case `color`; case `border_color`; case `placeholder_color`; case `tint_color`; case `border_width`; case `border_radius`; case `border_top_left_radius`; case `border_top_right_radius`; case `border_bottom_left_radius`; case `border_bottom_right_radius`; case `border_top_width`; case `border_right_width`; case `border_bottom_width`; case `border_left_width`; case `border_top_color`; case `border_right_color`; case `border_bottom_color`; case `border_left_color`; case `font_size`; case `font_family`; case `font_weight`; case `bold`; case `italic`; case `text_align`; case `text_decoration`; case `text_transform`; case `line_height`; case `letter_spacing`; case `max_lines`; case `text_shadow_color`; case `text_shadow_offset`; case `text_shadow_radius`; case `shadow_color`; case `shadow_offset`; case `shadow_opacity`; case `shadow_radius`; case `elevation`; case `opacity`; case `transform`; case `z_index`; case `pointer_events`; case `refreshing`; case `on_refresh`; case `accessibility_role`; case `ref`; case `on_layout` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`width`)
        self.`height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`height`)
        self.`min_width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`min_width`)
        self.`max_width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`max_width`)
        self.`min_height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`min_height`)
        self.`max_height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`max_height`)
        self.`aspect_ratio` = try container.decodeIfPresent(Double.self, forKey: .`aspect_ratio`)
        self.`flex` = try container.decodeIfPresent(Double.self, forKey: .`flex`)
        self.`flex_grow` = try container.decodeIfPresent(Double.self, forKey: .`flex_grow`)
        self.`flex_shrink` = try container.decodeIfPresent(Double.self, forKey: .`flex_shrink`)
        self.`flex_basis` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`flex_basis`)
        self.`flex_direction` = try container.decodeIfPresent(PNViewFlexDirection.self, forKey: .`flex_direction`)
        self.`flex_wrap` = try container.decodeIfPresent(PNViewFlexWrap.self, forKey: .`flex_wrap`)
        self.`justify_content` = try container.decodeIfPresent(PNViewJustifyContent.self, forKey: .`justify_content`)
        self.`align_items` = try container.decodeIfPresent(PNViewAlignItems.self, forKey: .`align_items`)
        self.`align_self` = try container.decodeIfPresent(PNViewAlignItems.self, forKey: .`align_self`)
        self.`align_content` = try container.decodeIfPresent(PNViewAlignContent.self, forKey: .`align_content`)
        self.`direction` = try container.decodeIfPresent(PNViewDirection.self, forKey: .`direction`)
        self.`display` = try container.decodeIfPresent(PNViewDisplay.self, forKey: .`display`)
        self.`position` = try container.decodeIfPresent(PNViewPosition.self, forKey: .`position`)
        self.`top` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`top`)
        self.`right` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`right`)
        self.`bottom` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`bottom`)
        self.`left` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`left`)
        self.`start` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`start`)
        self.`end` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`end`)
        self.`padding` = try container.decodeIfPresent(PNViewPadding.self, forKey: .`padding`)
        self.`padding_top` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_top`)
        self.`padding_bottom` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_bottom`)
        self.`padding_left` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_left`)
        self.`padding_right` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_right`)
        self.`padding_start` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_start`)
        self.`padding_end` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_end`)
        self.`padding_horizontal` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_horizontal`)
        self.`padding_vertical` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_vertical`)
        self.`margin` = try container.decodeIfPresent(PNViewMargin.self, forKey: .`margin`)
        self.`margin_top` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_top`)
        self.`margin_bottom` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_bottom`)
        self.`margin_left` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_left`)
        self.`margin_right` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_right`)
        self.`margin_start` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_start`)
        self.`margin_end` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_end`)
        self.`margin_horizontal` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_horizontal`)
        self.`margin_vertical` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_vertical`)
        self.`spacing` = try container.decodeIfPresent(Double.self, forKey: .`spacing`)
        self.`gap` = try container.decodeIfPresent(Double.self, forKey: .`gap`)
        self.`row_gap` = try container.decodeIfPresent(Double.self, forKey: .`row_gap`)
        self.`column_gap` = try container.decodeIfPresent(Double.self, forKey: .`column_gap`)
        self.`overflow` = try container.decodeIfPresent(PNViewOverflow.self, forKey: .`overflow`)
        self.`background_color` = try container.decodeIfPresent(String.self, forKey: .`background_color`)
        self.`color` = try container.decodeIfPresent(String.self, forKey: .`color`)
        self.`border_color` = try container.decodeIfPresent(String.self, forKey: .`border_color`)
        self.`placeholder_color` = try container.decodeIfPresent(String.self, forKey: .`placeholder_color`)
        self.`tint_color` = container.contains(.`tint_color`) ? .present(try container.decode(String?.self, forKey: .`tint_color`)) : .absent
        self.`border_width` = try container.decodeIfPresent(Double.self, forKey: .`border_width`)
        self.`border_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_radius`)
        self.`border_top_left_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_top_left_radius`)
        self.`border_top_right_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_top_right_radius`)
        self.`border_bottom_left_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_left_radius`)
        self.`border_bottom_right_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_right_radius`)
        self.`border_top_width` = try container.decodeIfPresent(Double.self, forKey: .`border_top_width`)
        self.`border_right_width` = try container.decodeIfPresent(Double.self, forKey: .`border_right_width`)
        self.`border_bottom_width` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_width`)
        self.`border_left_width` = try container.decodeIfPresent(Double.self, forKey: .`border_left_width`)
        self.`border_top_color` = try container.decodeIfPresent(String.self, forKey: .`border_top_color`)
        self.`border_right_color` = try container.decodeIfPresent(String.self, forKey: .`border_right_color`)
        self.`border_bottom_color` = try container.decodeIfPresent(String.self, forKey: .`border_bottom_color`)
        self.`border_left_color` = try container.decodeIfPresent(String.self, forKey: .`border_left_color`)
        self.`font_size` = try container.decodeIfPresent(Double.self, forKey: .`font_size`)
        self.`font_family` = try container.decodeIfPresent(String.self, forKey: .`font_family`)
        self.`font_weight` = try container.decodeIfPresent(PNViewFontWeight.self, forKey: .`font_weight`)
        self.`bold` = try container.decodeIfPresent(Bool.self, forKey: .`bold`)
        self.`italic` = try container.decodeIfPresent(Bool.self, forKey: .`italic`)
        self.`text_align` = try container.decodeIfPresent(PNViewTextAlign.self, forKey: .`text_align`)
        self.`text_decoration` = try container.decodeIfPresent(PNViewTextDecoration.self, forKey: .`text_decoration`)
        self.`text_transform` = try container.decodeIfPresent(PNViewTextTransform.self, forKey: .`text_transform`)
        self.`line_height` = try container.decodeIfPresent(Double.self, forKey: .`line_height`)
        self.`letter_spacing` = try container.decodeIfPresent(Double.self, forKey: .`letter_spacing`)
        self.`max_lines` = try container.decodeIfPresent(Int64.self, forKey: .`max_lines`)
        self.`text_shadow_color` = try container.decodeIfPresent(String.self, forKey: .`text_shadow_color`)
        self.`text_shadow_offset` = try container.decodeIfPresent(PNViewTextShadowOffset.self, forKey: .`text_shadow_offset`)
        self.`text_shadow_radius` = try container.decodeIfPresent(Double.self, forKey: .`text_shadow_radius`)
        self.`shadow_color` = try container.decodeIfPresent(String.self, forKey: .`shadow_color`)
        self.`shadow_offset` = try container.decodeIfPresent(PNViewTextShadowOffset.self, forKey: .`shadow_offset`)
        self.`shadow_opacity` = try container.decodeIfPresent(Double.self, forKey: .`shadow_opacity`)
        self.`shadow_radius` = try container.decodeIfPresent(Double.self, forKey: .`shadow_radius`)
        self.`elevation` = try container.decodeIfPresent(Double.self, forKey: .`elevation`)
        self.`opacity` = try container.decodeIfPresent(Double.self, forKey: .`opacity`)
        self.`transform` = try container.decodeIfPresent(PNViewTransform.self, forKey: .`transform`)
        self.`z_index` = try container.decodeIfPresent(Int64.self, forKey: .`z_index`)
        self.`pointer_events` = try container.decodeIfPresent(PNViewPointerEvents.self, forKey: .`pointer_events`)
        self.`refreshing` = try container.decodeIfPresent(Bool.self, forKey: .`refreshing`)
        self.`on_refresh` = container.contains(.`on_refresh`) ? .present(try container.decode(Bool?.self, forKey: .`on_refresh`)) : .absent
        self.`accessibility_role` = try container.decodeIfPresent(String.self, forKey: .`accessibility_role`)
        self.`ref` = try container.decodeIfPresent(PNJSONValue.self, forKey: .`ref`)
        self.`on_layout` = try container.decodeIfPresent(Bool.self, forKey: .`on_layout`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`width`, forKey: .`width`)
        try container.encodeIfPresent(`height`, forKey: .`height`)
        try container.encodeIfPresent(`min_width`, forKey: .`min_width`)
        try container.encodeIfPresent(`max_width`, forKey: .`max_width`)
        try container.encodeIfPresent(`min_height`, forKey: .`min_height`)
        try container.encodeIfPresent(`max_height`, forKey: .`max_height`)
        try container.encodeIfPresent(`aspect_ratio`, forKey: .`aspect_ratio`)
        try container.encodeIfPresent(`flex`, forKey: .`flex`)
        try container.encodeIfPresent(`flex_grow`, forKey: .`flex_grow`)
        try container.encodeIfPresent(`flex_shrink`, forKey: .`flex_shrink`)
        try container.encodeIfPresent(`flex_basis`, forKey: .`flex_basis`)
        try container.encodeIfPresent(`flex_direction`, forKey: .`flex_direction`)
        try container.encodeIfPresent(`flex_wrap`, forKey: .`flex_wrap`)
        try container.encodeIfPresent(`justify_content`, forKey: .`justify_content`)
        try container.encodeIfPresent(`align_items`, forKey: .`align_items`)
        try container.encodeIfPresent(`align_self`, forKey: .`align_self`)
        try container.encodeIfPresent(`align_content`, forKey: .`align_content`)
        try container.encodeIfPresent(`direction`, forKey: .`direction`)
        try container.encodeIfPresent(`display`, forKey: .`display`)
        try container.encodeIfPresent(`position`, forKey: .`position`)
        try container.encodeIfPresent(`top`, forKey: .`top`)
        try container.encodeIfPresent(`right`, forKey: .`right`)
        try container.encodeIfPresent(`bottom`, forKey: .`bottom`)
        try container.encodeIfPresent(`left`, forKey: .`left`)
        try container.encodeIfPresent(`start`, forKey: .`start`)
        try container.encodeIfPresent(`end`, forKey: .`end`)
        try container.encodeIfPresent(`padding`, forKey: .`padding`)
        try container.encodeIfPresent(`padding_top`, forKey: .`padding_top`)
        try container.encodeIfPresent(`padding_bottom`, forKey: .`padding_bottom`)
        try container.encodeIfPresent(`padding_left`, forKey: .`padding_left`)
        try container.encodeIfPresent(`padding_right`, forKey: .`padding_right`)
        try container.encodeIfPresent(`padding_start`, forKey: .`padding_start`)
        try container.encodeIfPresent(`padding_end`, forKey: .`padding_end`)
        try container.encodeIfPresent(`padding_horizontal`, forKey: .`padding_horizontal`)
        try container.encodeIfPresent(`padding_vertical`, forKey: .`padding_vertical`)
        try container.encodeIfPresent(`margin`, forKey: .`margin`)
        try container.encodeIfPresent(`margin_top`, forKey: .`margin_top`)
        try container.encodeIfPresent(`margin_bottom`, forKey: .`margin_bottom`)
        try container.encodeIfPresent(`margin_left`, forKey: .`margin_left`)
        try container.encodeIfPresent(`margin_right`, forKey: .`margin_right`)
        try container.encodeIfPresent(`margin_start`, forKey: .`margin_start`)
        try container.encodeIfPresent(`margin_end`, forKey: .`margin_end`)
        try container.encodeIfPresent(`margin_horizontal`, forKey: .`margin_horizontal`)
        try container.encodeIfPresent(`margin_vertical`, forKey: .`margin_vertical`)
        try container.encodeIfPresent(`spacing`, forKey: .`spacing`)
        try container.encodeIfPresent(`gap`, forKey: .`gap`)
        try container.encodeIfPresent(`row_gap`, forKey: .`row_gap`)
        try container.encodeIfPresent(`column_gap`, forKey: .`column_gap`)
        try container.encodeIfPresent(`overflow`, forKey: .`overflow`)
        try container.encodeIfPresent(`background_color`, forKey: .`background_color`)
        try container.encodeIfPresent(`color`, forKey: .`color`)
        try container.encodeIfPresent(`border_color`, forKey: .`border_color`)
        try container.encodeIfPresent(`placeholder_color`, forKey: .`placeholder_color`)
        if case .present(let value) = `tint_color` { try container.encode(value, forKey: .`tint_color`) }
        try container.encodeIfPresent(`border_width`, forKey: .`border_width`)
        try container.encodeIfPresent(`border_radius`, forKey: .`border_radius`)
        try container.encodeIfPresent(`border_top_left_radius`, forKey: .`border_top_left_radius`)
        try container.encodeIfPresent(`border_top_right_radius`, forKey: .`border_top_right_radius`)
        try container.encodeIfPresent(`border_bottom_left_radius`, forKey: .`border_bottom_left_radius`)
        try container.encodeIfPresent(`border_bottom_right_radius`, forKey: .`border_bottom_right_radius`)
        try container.encodeIfPresent(`border_top_width`, forKey: .`border_top_width`)
        try container.encodeIfPresent(`border_right_width`, forKey: .`border_right_width`)
        try container.encodeIfPresent(`border_bottom_width`, forKey: .`border_bottom_width`)
        try container.encodeIfPresent(`border_left_width`, forKey: .`border_left_width`)
        try container.encodeIfPresent(`border_top_color`, forKey: .`border_top_color`)
        try container.encodeIfPresent(`border_right_color`, forKey: .`border_right_color`)
        try container.encodeIfPresent(`border_bottom_color`, forKey: .`border_bottom_color`)
        try container.encodeIfPresent(`border_left_color`, forKey: .`border_left_color`)
        try container.encodeIfPresent(`font_size`, forKey: .`font_size`)
        try container.encodeIfPresent(`font_family`, forKey: .`font_family`)
        try container.encodeIfPresent(`font_weight`, forKey: .`font_weight`)
        try container.encodeIfPresent(`bold`, forKey: .`bold`)
        try container.encodeIfPresent(`italic`, forKey: .`italic`)
        try container.encodeIfPresent(`text_align`, forKey: .`text_align`)
        try container.encodeIfPresent(`text_decoration`, forKey: .`text_decoration`)
        try container.encodeIfPresent(`text_transform`, forKey: .`text_transform`)
        try container.encodeIfPresent(`line_height`, forKey: .`line_height`)
        try container.encodeIfPresent(`letter_spacing`, forKey: .`letter_spacing`)
        try container.encodeIfPresent(`max_lines`, forKey: .`max_lines`)
        try container.encodeIfPresent(`text_shadow_color`, forKey: .`text_shadow_color`)
        try container.encodeIfPresent(`text_shadow_offset`, forKey: .`text_shadow_offset`)
        try container.encodeIfPresent(`text_shadow_radius`, forKey: .`text_shadow_radius`)
        try container.encodeIfPresent(`shadow_color`, forKey: .`shadow_color`)
        try container.encodeIfPresent(`shadow_offset`, forKey: .`shadow_offset`)
        try container.encodeIfPresent(`shadow_opacity`, forKey: .`shadow_opacity`)
        try container.encodeIfPresent(`shadow_radius`, forKey: .`shadow_radius`)
        try container.encodeIfPresent(`elevation`, forKey: .`elevation`)
        try container.encodeIfPresent(`opacity`, forKey: .`opacity`)
        try container.encodeIfPresent(`transform`, forKey: .`transform`)
        try container.encodeIfPresent(`z_index`, forKey: .`z_index`)
        try container.encodeIfPresent(`pointer_events`, forKey: .`pointer_events`)
        try container.encodeIfPresent(`refreshing`, forKey: .`refreshing`)
        if case .present(let value) = `on_refresh` { try container.encode(value, forKey: .`on_refresh`) }
        try container.encodeIfPresent(`accessibility_role`, forKey: .`accessibility_role`)
        try container.encodeIfPresent(`ref`, forKey: .`ref`)
        try container.encodeIfPresent(`on_layout`, forKey: .`on_layout`)
    }
}

public enum PNScrollViewScrollAxis: String, Codable {
    case `vertical` = "vertical"
    case `horizontal` = "horizontal"
}

public struct PNStyle: Codable {
    public let `width`: PNViewWidth?
    public let `height`: PNViewWidth?
    public let `min_width`: PNViewWidth?
    public let `max_width`: PNViewWidth?
    public let `min_height`: PNViewWidth?
    public let `max_height`: PNViewWidth?
    public let `aspect_ratio`: Double?
    public let `flex`: Double?
    public let `flex_grow`: Double?
    public let `flex_shrink`: Double?
    public let `flex_basis`: PNViewWidth?
    public let `flex_direction`: PNViewFlexDirection?
    public let `flex_wrap`: PNViewFlexWrap?
    public let `justify_content`: PNViewJustifyContent?
    public let `align_items`: PNViewAlignItems?
    public let `align_self`: PNViewAlignItems?
    public let `align_content`: PNViewAlignContent?
    public let `direction`: PNViewDirection?
    public let `display`: PNViewDisplay?
    public let `position`: PNViewPosition?
    public let `top`: PNViewWidth?
    public let `right`: PNViewWidth?
    public let `bottom`: PNViewWidth?
    public let `left`: PNViewWidth?
    public let `start`: PNViewWidth?
    public let `end`: PNViewWidth?
    public let `padding`: PNViewPadding?
    public let `padding_top`: PNViewWidth?
    public let `padding_bottom`: PNViewWidth?
    public let `padding_left`: PNViewWidth?
    public let `padding_right`: PNViewWidth?
    public let `padding_start`: PNViewWidth?
    public let `padding_end`: PNViewWidth?
    public let `padding_horizontal`: PNViewWidth?
    public let `padding_vertical`: PNViewWidth?
    public let `margin`: PNViewMargin?
    public let `margin_top`: PNViewMarginTop?
    public let `margin_bottom`: PNViewMarginTop?
    public let `margin_left`: PNViewMarginTop?
    public let `margin_right`: PNViewMarginTop?
    public let `margin_start`: PNViewMarginTop?
    public let `margin_end`: PNViewMarginTop?
    public let `margin_horizontal`: PNViewMarginTop?
    public let `margin_vertical`: PNViewMarginTop?
    public let `spacing`: Double?
    public let `gap`: Double?
    public let `row_gap`: Double?
    public let `column_gap`: Double?
    public let `overflow`: PNViewOverflow?
    public let `background_color`: String?
    public let `color`: String?
    public let `border_color`: String?
    public let `placeholder_color`: String?
    public let `tint_color`: String?
    public let `border_width`: Double?
    public let `border_radius`: Double?
    public let `border_top_left_radius`: Double?
    public let `border_top_right_radius`: Double?
    public let `border_bottom_left_radius`: Double?
    public let `border_bottom_right_radius`: Double?
    public let `border_top_width`: Double?
    public let `border_right_width`: Double?
    public let `border_bottom_width`: Double?
    public let `border_left_width`: Double?
    public let `border_top_color`: String?
    public let `border_right_color`: String?
    public let `border_bottom_color`: String?
    public let `border_left_color`: String?
    public let `font_size`: Double?
    public let `font_family`: String?
    public let `font_weight`: PNViewFontWeight?
    public let `bold`: Bool?
    public let `italic`: Bool?
    public let `text_align`: PNViewTextAlign?
    public let `text_decoration`: PNViewTextDecoration?
    public let `text_transform`: PNViewTextTransform?
    public let `line_height`: Double?
    public let `letter_spacing`: Double?
    public let `max_lines`: Int64?
    public let `text_shadow_color`: String?
    public let `text_shadow_offset`: PNViewTextShadowOffset?
    public let `text_shadow_radius`: Double?
    public let `shadow_color`: String?
    public let `shadow_offset`: PNViewTextShadowOffset?
    public let `shadow_opacity`: Double?
    public let `shadow_radius`: Double?
    public let `elevation`: Double?
    public let `opacity`: Double?
    public let `transform`: PNViewTransform?
    public let `z_index`: Int64?
    public let `pointer_events`: PNViewPointerEvents?
    public init(`width`: PNViewWidth?, `height`: PNViewWidth?, `min_width`: PNViewWidth?, `max_width`: PNViewWidth?, `min_height`: PNViewWidth?, `max_height`: PNViewWidth?, `aspect_ratio`: Double?, `flex`: Double?, `flex_grow`: Double?, `flex_shrink`: Double?, `flex_basis`: PNViewWidth?, `flex_direction`: PNViewFlexDirection?, `flex_wrap`: PNViewFlexWrap?, `justify_content`: PNViewJustifyContent?, `align_items`: PNViewAlignItems?, `align_self`: PNViewAlignItems?, `align_content`: PNViewAlignContent?, `direction`: PNViewDirection?, `display`: PNViewDisplay?, `position`: PNViewPosition?, `top`: PNViewWidth?, `right`: PNViewWidth?, `bottom`: PNViewWidth?, `left`: PNViewWidth?, `start`: PNViewWidth?, `end`: PNViewWidth?, `padding`: PNViewPadding?, `padding_top`: PNViewWidth?, `padding_bottom`: PNViewWidth?, `padding_left`: PNViewWidth?, `padding_right`: PNViewWidth?, `padding_start`: PNViewWidth?, `padding_end`: PNViewWidth?, `padding_horizontal`: PNViewWidth?, `padding_vertical`: PNViewWidth?, `margin`: PNViewMargin?, `margin_top`: PNViewMarginTop?, `margin_bottom`: PNViewMarginTop?, `margin_left`: PNViewMarginTop?, `margin_right`: PNViewMarginTop?, `margin_start`: PNViewMarginTop?, `margin_end`: PNViewMarginTop?, `margin_horizontal`: PNViewMarginTop?, `margin_vertical`: PNViewMarginTop?, `spacing`: Double?, `gap`: Double?, `row_gap`: Double?, `column_gap`: Double?, `overflow`: PNViewOverflow?, `background_color`: String?, `color`: String?, `border_color`: String?, `placeholder_color`: String?, `tint_color`: String?, `border_width`: Double?, `border_radius`: Double?, `border_top_left_radius`: Double?, `border_top_right_radius`: Double?, `border_bottom_left_radius`: Double?, `border_bottom_right_radius`: Double?, `border_top_width`: Double?, `border_right_width`: Double?, `border_bottom_width`: Double?, `border_left_width`: Double?, `border_top_color`: String?, `border_right_color`: String?, `border_bottom_color`: String?, `border_left_color`: String?, `font_size`: Double?, `font_family`: String?, `font_weight`: PNViewFontWeight?, `bold`: Bool?, `italic`: Bool?, `text_align`: PNViewTextAlign?, `text_decoration`: PNViewTextDecoration?, `text_transform`: PNViewTextTransform?, `line_height`: Double?, `letter_spacing`: Double?, `max_lines`: Int64?, `text_shadow_color`: String?, `text_shadow_offset`: PNViewTextShadowOffset?, `text_shadow_radius`: Double?, `shadow_color`: String?, `shadow_offset`: PNViewTextShadowOffset?, `shadow_opacity`: Double?, `shadow_radius`: Double?, `elevation`: Double?, `opacity`: Double?, `transform`: PNViewTransform?, `z_index`: Int64?, `pointer_events`: PNViewPointerEvents?) {
        self.`width` = `width`
        self.`height` = `height`
        self.`min_width` = `min_width`
        self.`max_width` = `max_width`
        self.`min_height` = `min_height`
        self.`max_height` = `max_height`
        self.`aspect_ratio` = `aspect_ratio`
        self.`flex` = `flex`
        self.`flex_grow` = `flex_grow`
        self.`flex_shrink` = `flex_shrink`
        self.`flex_basis` = `flex_basis`
        self.`flex_direction` = `flex_direction`
        self.`flex_wrap` = `flex_wrap`
        self.`justify_content` = `justify_content`
        self.`align_items` = `align_items`
        self.`align_self` = `align_self`
        self.`align_content` = `align_content`
        self.`direction` = `direction`
        self.`display` = `display`
        self.`position` = `position`
        self.`top` = `top`
        self.`right` = `right`
        self.`bottom` = `bottom`
        self.`left` = `left`
        self.`start` = `start`
        self.`end` = `end`
        self.`padding` = `padding`
        self.`padding_top` = `padding_top`
        self.`padding_bottom` = `padding_bottom`
        self.`padding_left` = `padding_left`
        self.`padding_right` = `padding_right`
        self.`padding_start` = `padding_start`
        self.`padding_end` = `padding_end`
        self.`padding_horizontal` = `padding_horizontal`
        self.`padding_vertical` = `padding_vertical`
        self.`margin` = `margin`
        self.`margin_top` = `margin_top`
        self.`margin_bottom` = `margin_bottom`
        self.`margin_left` = `margin_left`
        self.`margin_right` = `margin_right`
        self.`margin_start` = `margin_start`
        self.`margin_end` = `margin_end`
        self.`margin_horizontal` = `margin_horizontal`
        self.`margin_vertical` = `margin_vertical`
        self.`spacing` = `spacing`
        self.`gap` = `gap`
        self.`row_gap` = `row_gap`
        self.`column_gap` = `column_gap`
        self.`overflow` = `overflow`
        self.`background_color` = `background_color`
        self.`color` = `color`
        self.`border_color` = `border_color`
        self.`placeholder_color` = `placeholder_color`
        self.`tint_color` = `tint_color`
        self.`border_width` = `border_width`
        self.`border_radius` = `border_radius`
        self.`border_top_left_radius` = `border_top_left_radius`
        self.`border_top_right_radius` = `border_top_right_radius`
        self.`border_bottom_left_radius` = `border_bottom_left_radius`
        self.`border_bottom_right_radius` = `border_bottom_right_radius`
        self.`border_top_width` = `border_top_width`
        self.`border_right_width` = `border_right_width`
        self.`border_bottom_width` = `border_bottom_width`
        self.`border_left_width` = `border_left_width`
        self.`border_top_color` = `border_top_color`
        self.`border_right_color` = `border_right_color`
        self.`border_bottom_color` = `border_bottom_color`
        self.`border_left_color` = `border_left_color`
        self.`font_size` = `font_size`
        self.`font_family` = `font_family`
        self.`font_weight` = `font_weight`
        self.`bold` = `bold`
        self.`italic` = `italic`
        self.`text_align` = `text_align`
        self.`text_decoration` = `text_decoration`
        self.`text_transform` = `text_transform`
        self.`line_height` = `line_height`
        self.`letter_spacing` = `letter_spacing`
        self.`max_lines` = `max_lines`
        self.`text_shadow_color` = `text_shadow_color`
        self.`text_shadow_offset` = `text_shadow_offset`
        self.`text_shadow_radius` = `text_shadow_radius`
        self.`shadow_color` = `shadow_color`
        self.`shadow_offset` = `shadow_offset`
        self.`shadow_opacity` = `shadow_opacity`
        self.`shadow_radius` = `shadow_radius`
        self.`elevation` = `elevation`
        self.`opacity` = `opacity`
        self.`transform` = `transform`
        self.`z_index` = `z_index`
        self.`pointer_events` = `pointer_events`
    }
    private enum CodingKeys: String, CodingKey { case `width`; case `height`; case `min_width`; case `max_width`; case `min_height`; case `max_height`; case `aspect_ratio`; case `flex`; case `flex_grow`; case `flex_shrink`; case `flex_basis`; case `flex_direction`; case `flex_wrap`; case `justify_content`; case `align_items`; case `align_self`; case `align_content`; case `direction`; case `display`; case `position`; case `top`; case `right`; case `bottom`; case `left`; case `start`; case `end`; case `padding`; case `padding_top`; case `padding_bottom`; case `padding_left`; case `padding_right`; case `padding_start`; case `padding_end`; case `padding_horizontal`; case `padding_vertical`; case `margin`; case `margin_top`; case `margin_bottom`; case `margin_left`; case `margin_right`; case `margin_start`; case `margin_end`; case `margin_horizontal`; case `margin_vertical`; case `spacing`; case `gap`; case `row_gap`; case `column_gap`; case `overflow`; case `background_color`; case `color`; case `border_color`; case `placeholder_color`; case `tint_color`; case `border_width`; case `border_radius`; case `border_top_left_radius`; case `border_top_right_radius`; case `border_bottom_left_radius`; case `border_bottom_right_radius`; case `border_top_width`; case `border_right_width`; case `border_bottom_width`; case `border_left_width`; case `border_top_color`; case `border_right_color`; case `border_bottom_color`; case `border_left_color`; case `font_size`; case `font_family`; case `font_weight`; case `bold`; case `italic`; case `text_align`; case `text_decoration`; case `text_transform`; case `line_height`; case `letter_spacing`; case `max_lines`; case `text_shadow_color`; case `text_shadow_offset`; case `text_shadow_radius`; case `shadow_color`; case `shadow_offset`; case `shadow_opacity`; case `shadow_radius`; case `elevation`; case `opacity`; case `transform`; case `z_index`; case `pointer_events` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`width`)
        self.`height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`height`)
        self.`min_width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`min_width`)
        self.`max_width` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`max_width`)
        self.`min_height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`min_height`)
        self.`max_height` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`max_height`)
        self.`aspect_ratio` = try container.decodeIfPresent(Double.self, forKey: .`aspect_ratio`)
        self.`flex` = try container.decodeIfPresent(Double.self, forKey: .`flex`)
        self.`flex_grow` = try container.decodeIfPresent(Double.self, forKey: .`flex_grow`)
        self.`flex_shrink` = try container.decodeIfPresent(Double.self, forKey: .`flex_shrink`)
        self.`flex_basis` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`flex_basis`)
        self.`flex_direction` = try container.decodeIfPresent(PNViewFlexDirection.self, forKey: .`flex_direction`)
        self.`flex_wrap` = try container.decodeIfPresent(PNViewFlexWrap.self, forKey: .`flex_wrap`)
        self.`justify_content` = try container.decodeIfPresent(PNViewJustifyContent.self, forKey: .`justify_content`)
        self.`align_items` = try container.decodeIfPresent(PNViewAlignItems.self, forKey: .`align_items`)
        self.`align_self` = try container.decodeIfPresent(PNViewAlignItems.self, forKey: .`align_self`)
        self.`align_content` = try container.decodeIfPresent(PNViewAlignContent.self, forKey: .`align_content`)
        self.`direction` = try container.decodeIfPresent(PNViewDirection.self, forKey: .`direction`)
        self.`display` = try container.decodeIfPresent(PNViewDisplay.self, forKey: .`display`)
        self.`position` = try container.decodeIfPresent(PNViewPosition.self, forKey: .`position`)
        self.`top` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`top`)
        self.`right` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`right`)
        self.`bottom` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`bottom`)
        self.`left` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`left`)
        self.`start` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`start`)
        self.`end` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`end`)
        self.`padding` = try container.decodeIfPresent(PNViewPadding.self, forKey: .`padding`)
        self.`padding_top` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_top`)
        self.`padding_bottom` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_bottom`)
        self.`padding_left` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_left`)
        self.`padding_right` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_right`)
        self.`padding_start` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_start`)
        self.`padding_end` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_end`)
        self.`padding_horizontal` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_horizontal`)
        self.`padding_vertical` = try container.decodeIfPresent(PNViewWidth.self, forKey: .`padding_vertical`)
        self.`margin` = try container.decodeIfPresent(PNViewMargin.self, forKey: .`margin`)
        self.`margin_top` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_top`)
        self.`margin_bottom` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_bottom`)
        self.`margin_left` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_left`)
        self.`margin_right` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_right`)
        self.`margin_start` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_start`)
        self.`margin_end` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_end`)
        self.`margin_horizontal` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_horizontal`)
        self.`margin_vertical` = try container.decodeIfPresent(PNViewMarginTop.self, forKey: .`margin_vertical`)
        self.`spacing` = try container.decodeIfPresent(Double.self, forKey: .`spacing`)
        self.`gap` = try container.decodeIfPresent(Double.self, forKey: .`gap`)
        self.`row_gap` = try container.decodeIfPresent(Double.self, forKey: .`row_gap`)
        self.`column_gap` = try container.decodeIfPresent(Double.self, forKey: .`column_gap`)
        self.`overflow` = try container.decodeIfPresent(PNViewOverflow.self, forKey: .`overflow`)
        self.`background_color` = try container.decodeIfPresent(String.self, forKey: .`background_color`)
        self.`color` = try container.decodeIfPresent(String.self, forKey: .`color`)
        self.`border_color` = try container.decodeIfPresent(String.self, forKey: .`border_color`)
        self.`placeholder_color` = try container.decodeIfPresent(String.self, forKey: .`placeholder_color`)
        self.`tint_color` = try container.decodeIfPresent(String.self, forKey: .`tint_color`)
        self.`border_width` = try container.decodeIfPresent(Double.self, forKey: .`border_width`)
        self.`border_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_radius`)
        self.`border_top_left_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_top_left_radius`)
        self.`border_top_right_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_top_right_radius`)
        self.`border_bottom_left_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_left_radius`)
        self.`border_bottom_right_radius` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_right_radius`)
        self.`border_top_width` = try container.decodeIfPresent(Double.self, forKey: .`border_top_width`)
        self.`border_right_width` = try container.decodeIfPresent(Double.self, forKey: .`border_right_width`)
        self.`border_bottom_width` = try container.decodeIfPresent(Double.self, forKey: .`border_bottom_width`)
        self.`border_left_width` = try container.decodeIfPresent(Double.self, forKey: .`border_left_width`)
        self.`border_top_color` = try container.decodeIfPresent(String.self, forKey: .`border_top_color`)
        self.`border_right_color` = try container.decodeIfPresent(String.self, forKey: .`border_right_color`)
        self.`border_bottom_color` = try container.decodeIfPresent(String.self, forKey: .`border_bottom_color`)
        self.`border_left_color` = try container.decodeIfPresent(String.self, forKey: .`border_left_color`)
        self.`font_size` = try container.decodeIfPresent(Double.self, forKey: .`font_size`)
        self.`font_family` = try container.decodeIfPresent(String.self, forKey: .`font_family`)
        self.`font_weight` = try container.decodeIfPresent(PNViewFontWeight.self, forKey: .`font_weight`)
        self.`bold` = try container.decodeIfPresent(Bool.self, forKey: .`bold`)
        self.`italic` = try container.decodeIfPresent(Bool.self, forKey: .`italic`)
        self.`text_align` = try container.decodeIfPresent(PNViewTextAlign.self, forKey: .`text_align`)
        self.`text_decoration` = try container.decodeIfPresent(PNViewTextDecoration.self, forKey: .`text_decoration`)
        self.`text_transform` = try container.decodeIfPresent(PNViewTextTransform.self, forKey: .`text_transform`)
        self.`line_height` = try container.decodeIfPresent(Double.self, forKey: .`line_height`)
        self.`letter_spacing` = try container.decodeIfPresent(Double.self, forKey: .`letter_spacing`)
        self.`max_lines` = try container.decodeIfPresent(Int64.self, forKey: .`max_lines`)
        self.`text_shadow_color` = try container.decodeIfPresent(String.self, forKey: .`text_shadow_color`)
        self.`text_shadow_offset` = try container.decodeIfPresent(PNViewTextShadowOffset.self, forKey: .`text_shadow_offset`)
        self.`text_shadow_radius` = try container.decodeIfPresent(Double.self, forKey: .`text_shadow_radius`)
        self.`shadow_color` = try container.decodeIfPresent(String.self, forKey: .`shadow_color`)
        self.`shadow_offset` = try container.decodeIfPresent(PNViewTextShadowOffset.self, forKey: .`shadow_offset`)
        self.`shadow_opacity` = try container.decodeIfPresent(Double.self, forKey: .`shadow_opacity`)
        self.`shadow_radius` = try container.decodeIfPresent(Double.self, forKey: .`shadow_radius`)
        self.`elevation` = try container.decodeIfPresent(Double.self, forKey: .`elevation`)
        self.`opacity` = try container.decodeIfPresent(Double.self, forKey: .`opacity`)
        self.`transform` = try container.decodeIfPresent(PNViewTransform.self, forKey: .`transform`)
        self.`z_index` = try container.decodeIfPresent(Int64.self, forKey: .`z_index`)
        self.`pointer_events` = try container.decodeIfPresent(PNViewPointerEvents.self, forKey: .`pointer_events`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`width`, forKey: .`width`)
        try container.encodeIfPresent(`height`, forKey: .`height`)
        try container.encodeIfPresent(`min_width`, forKey: .`min_width`)
        try container.encodeIfPresent(`max_width`, forKey: .`max_width`)
        try container.encodeIfPresent(`min_height`, forKey: .`min_height`)
        try container.encodeIfPresent(`max_height`, forKey: .`max_height`)
        try container.encodeIfPresent(`aspect_ratio`, forKey: .`aspect_ratio`)
        try container.encodeIfPresent(`flex`, forKey: .`flex`)
        try container.encodeIfPresent(`flex_grow`, forKey: .`flex_grow`)
        try container.encodeIfPresent(`flex_shrink`, forKey: .`flex_shrink`)
        try container.encodeIfPresent(`flex_basis`, forKey: .`flex_basis`)
        try container.encodeIfPresent(`flex_direction`, forKey: .`flex_direction`)
        try container.encodeIfPresent(`flex_wrap`, forKey: .`flex_wrap`)
        try container.encodeIfPresent(`justify_content`, forKey: .`justify_content`)
        try container.encodeIfPresent(`align_items`, forKey: .`align_items`)
        try container.encodeIfPresent(`align_self`, forKey: .`align_self`)
        try container.encodeIfPresent(`align_content`, forKey: .`align_content`)
        try container.encodeIfPresent(`direction`, forKey: .`direction`)
        try container.encodeIfPresent(`display`, forKey: .`display`)
        try container.encodeIfPresent(`position`, forKey: .`position`)
        try container.encodeIfPresent(`top`, forKey: .`top`)
        try container.encodeIfPresent(`right`, forKey: .`right`)
        try container.encodeIfPresent(`bottom`, forKey: .`bottom`)
        try container.encodeIfPresent(`left`, forKey: .`left`)
        try container.encodeIfPresent(`start`, forKey: .`start`)
        try container.encodeIfPresent(`end`, forKey: .`end`)
        try container.encodeIfPresent(`padding`, forKey: .`padding`)
        try container.encodeIfPresent(`padding_top`, forKey: .`padding_top`)
        try container.encodeIfPresent(`padding_bottom`, forKey: .`padding_bottom`)
        try container.encodeIfPresent(`padding_left`, forKey: .`padding_left`)
        try container.encodeIfPresent(`padding_right`, forKey: .`padding_right`)
        try container.encodeIfPresent(`padding_start`, forKey: .`padding_start`)
        try container.encodeIfPresent(`padding_end`, forKey: .`padding_end`)
        try container.encodeIfPresent(`padding_horizontal`, forKey: .`padding_horizontal`)
        try container.encodeIfPresent(`padding_vertical`, forKey: .`padding_vertical`)
        try container.encodeIfPresent(`margin`, forKey: .`margin`)
        try container.encodeIfPresent(`margin_top`, forKey: .`margin_top`)
        try container.encodeIfPresent(`margin_bottom`, forKey: .`margin_bottom`)
        try container.encodeIfPresent(`margin_left`, forKey: .`margin_left`)
        try container.encodeIfPresent(`margin_right`, forKey: .`margin_right`)
        try container.encodeIfPresent(`margin_start`, forKey: .`margin_start`)
        try container.encodeIfPresent(`margin_end`, forKey: .`margin_end`)
        try container.encodeIfPresent(`margin_horizontal`, forKey: .`margin_horizontal`)
        try container.encodeIfPresent(`margin_vertical`, forKey: .`margin_vertical`)
        try container.encodeIfPresent(`spacing`, forKey: .`spacing`)
        try container.encodeIfPresent(`gap`, forKey: .`gap`)
        try container.encodeIfPresent(`row_gap`, forKey: .`row_gap`)
        try container.encodeIfPresent(`column_gap`, forKey: .`column_gap`)
        try container.encodeIfPresent(`overflow`, forKey: .`overflow`)
        try container.encodeIfPresent(`background_color`, forKey: .`background_color`)
        try container.encodeIfPresent(`color`, forKey: .`color`)
        try container.encodeIfPresent(`border_color`, forKey: .`border_color`)
        try container.encodeIfPresent(`placeholder_color`, forKey: .`placeholder_color`)
        try container.encodeIfPresent(`tint_color`, forKey: .`tint_color`)
        try container.encodeIfPresent(`border_width`, forKey: .`border_width`)
        try container.encodeIfPresent(`border_radius`, forKey: .`border_radius`)
        try container.encodeIfPresent(`border_top_left_radius`, forKey: .`border_top_left_radius`)
        try container.encodeIfPresent(`border_top_right_radius`, forKey: .`border_top_right_radius`)
        try container.encodeIfPresent(`border_bottom_left_radius`, forKey: .`border_bottom_left_radius`)
        try container.encodeIfPresent(`border_bottom_right_radius`, forKey: .`border_bottom_right_radius`)
        try container.encodeIfPresent(`border_top_width`, forKey: .`border_top_width`)
        try container.encodeIfPresent(`border_right_width`, forKey: .`border_right_width`)
        try container.encodeIfPresent(`border_bottom_width`, forKey: .`border_bottom_width`)
        try container.encodeIfPresent(`border_left_width`, forKey: .`border_left_width`)
        try container.encodeIfPresent(`border_top_color`, forKey: .`border_top_color`)
        try container.encodeIfPresent(`border_right_color`, forKey: .`border_right_color`)
        try container.encodeIfPresent(`border_bottom_color`, forKey: .`border_bottom_color`)
        try container.encodeIfPresent(`border_left_color`, forKey: .`border_left_color`)
        try container.encodeIfPresent(`font_size`, forKey: .`font_size`)
        try container.encodeIfPresent(`font_family`, forKey: .`font_family`)
        try container.encodeIfPresent(`font_weight`, forKey: .`font_weight`)
        try container.encodeIfPresent(`bold`, forKey: .`bold`)
        try container.encodeIfPresent(`italic`, forKey: .`italic`)
        try container.encodeIfPresent(`text_align`, forKey: .`text_align`)
        try container.encodeIfPresent(`text_decoration`, forKey: .`text_decoration`)
        try container.encodeIfPresent(`text_transform`, forKey: .`text_transform`)
        try container.encodeIfPresent(`line_height`, forKey: .`line_height`)
        try container.encodeIfPresent(`letter_spacing`, forKey: .`letter_spacing`)
        try container.encodeIfPresent(`max_lines`, forKey: .`max_lines`)
        try container.encodeIfPresent(`text_shadow_color`, forKey: .`text_shadow_color`)
        try container.encodeIfPresent(`text_shadow_offset`, forKey: .`text_shadow_offset`)
        try container.encodeIfPresent(`text_shadow_radius`, forKey: .`text_shadow_radius`)
        try container.encodeIfPresent(`shadow_color`, forKey: .`shadow_color`)
        try container.encodeIfPresent(`shadow_offset`, forKey: .`shadow_offset`)
        try container.encodeIfPresent(`shadow_opacity`, forKey: .`shadow_opacity`)
        try container.encodeIfPresent(`shadow_radius`, forKey: .`shadow_radius`)
        try container.encodeIfPresent(`elevation`, forKey: .`elevation`)
        try container.encodeIfPresent(`opacity`, forKey: .`opacity`)
        try container.encodeIfPresent(`transform`, forKey: .`transform`)
        try container.encodeIfPresent(`z_index`, forKey: .`z_index`)
        try container.encodeIfPresent(`pointer_events`, forKey: .`pointer_events`)
    }
}

public enum PNPNScrollViewContentContainerStyle2Item: Codable {
    case option0(PNStyle)
    case option1([String: PNJSONValue])
    case option2(PNJSONValue)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(PNStyle.self) { self = .option0(value); return }
        if let value = try? container.decode([String: PNJSONValue].self) { self = .option1(value); return }
        if let value = try? container.decode(PNJSONValue.self) { self = .option2(value); return }
        throw NativeDecodeError.invalid("PNPNScrollViewContentContainerStyle2Item")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        }
    }
}

public enum PNScrollViewContentContainerStyle: Codable {
    case option0(PNStyle)
    case option1([String: PNJSONValue])
    case option2([PNPNScrollViewContentContainerStyle2Item])
    case option3(PNJSONValue)
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(PNStyle.self) { self = .option0(value); return }
        if let value = try? container.decode([String: PNJSONValue].self) { self = .option1(value); return }
        if let value = try? container.decode([PNPNScrollViewContentContainerStyle2Item].self) { self = .option2(value); return }
        if let value = try? container.decode(PNJSONValue.self) { self = .option3(value); return }
        throw NativeDecodeError.invalid("PNScrollViewContentContainerStyle")
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .option0(let value): try container.encode(value)
        case .option1(let value): try container.encode(value)
        case .option2(let value): try container.encode(value)
        case .option3(let value): try container.encode(value)
        }
    }
}

public enum PNScrollViewKeyboardDismissMode: String, Codable {
    case `none` = "none"
    case `on_drag` = "on_drag"
    case `interactive` = "interactive"
}

public enum PNStatusBarBarStyle: String, Codable {
    case `light` = "light"
    case `dark` = "dark"
    case `default` = "default"
}

public enum PNPNSvgShapeKind: String, Codable {
    case `path` = "path"
    case `circle` = "circle"
    case `ellipse` = "ellipse"
    case `rect` = "rect"
    case `line` = "line"
    case `polyline` = "polyline"
    case `polygon` = "polygon"
}

public enum PNPNSvgShapeFillRule: String, Codable {
    case `nonzero` = "nonzero"
    case `evenodd` = "evenodd"
}

public enum PNPNSvgShapeStrokeLinecap: String, Codable {
    case `butt` = "butt"
    case `round` = "round"
    case `square` = "square"
}

public enum PNPNSvgShapeStrokeLinejoin: String, Codable {
    case `miter` = "miter"
    case `round` = "round"
    case `bevel` = "bevel"
}

public struct PNSvgShape: Codable {
    public let `kind`: PNPNSvgShapeKind
    public let `d`: String?
    public let `cx`: Double?
    public let `cy`: Double?
    public let `r`: Double?
    public let `rx`: Double?
    public let `ry`: Double?
    public let `x`: Double?
    public let `y`: Double?
    public let `width`: Double?
    public let `height`: Double?
    public let `x1`: Double?
    public let `y1`: Double?
    public let `x2`: Double?
    public let `y2`: Double?
    public let `points`: String?
    public let `fill`: String?
    public let `fill_opacity`: Double?
    public let `fill_rule`: PNPNSvgShapeFillRule?
    public let `stroke`: String?
    public let `stroke_width`: Double?
    public let `stroke_opacity`: Double?
    public let `stroke_linecap`: PNPNSvgShapeStrokeLinecap?
    public let `stroke_linejoin`: PNPNSvgShapeStrokeLinejoin?
    public let `stroke_dasharray`: [Double]?
    public let `opacity`: Double?
    public let `transform`: String?
    public init(`kind`: PNPNSvgShapeKind, `d`: String?, `cx`: Double?, `cy`: Double?, `r`: Double?, `rx`: Double?, `ry`: Double?, `x`: Double?, `y`: Double?, `width`: Double?, `height`: Double?, `x1`: Double?, `y1`: Double?, `x2`: Double?, `y2`: Double?, `points`: String?, `fill`: String?, `fill_opacity`: Double?, `fill_rule`: PNPNSvgShapeFillRule?, `stroke`: String?, `stroke_width`: Double?, `stroke_opacity`: Double?, `stroke_linecap`: PNPNSvgShapeStrokeLinecap?, `stroke_linejoin`: PNPNSvgShapeStrokeLinejoin?, `stroke_dasharray`: [Double]?, `opacity`: Double?, `transform`: String?) {
        self.`kind` = `kind`
        self.`d` = `d`
        self.`cx` = `cx`
        self.`cy` = `cy`
        self.`r` = `r`
        self.`rx` = `rx`
        self.`ry` = `ry`
        self.`x` = `x`
        self.`y` = `y`
        self.`width` = `width`
        self.`height` = `height`
        self.`x1` = `x1`
        self.`y1` = `y1`
        self.`x2` = `x2`
        self.`y2` = `y2`
        self.`points` = `points`
        self.`fill` = `fill`
        self.`fill_opacity` = `fill_opacity`
        self.`fill_rule` = `fill_rule`
        self.`stroke` = `stroke`
        self.`stroke_width` = `stroke_width`
        self.`stroke_opacity` = `stroke_opacity`
        self.`stroke_linecap` = `stroke_linecap`
        self.`stroke_linejoin` = `stroke_linejoin`
        self.`stroke_dasharray` = `stroke_dasharray`
        self.`opacity` = `opacity`
        self.`transform` = `transform`
    }
    private enum CodingKeys: String, CodingKey { case `kind`; case `d`; case `cx`; case `cy`; case `r`; case `rx`; case `ry`; case `x`; case `y`; case `width`; case `height`; case `x1`; case `y1`; case `x2`; case `y2`; case `points`; case `fill`; case `fill_opacity`; case `fill_rule`; case `stroke`; case `stroke_width`; case `stroke_opacity`; case `stroke_linecap`; case `stroke_linejoin`; case `stroke_dasharray`; case `opacity`; case `transform` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`kind` = try container.decode(PNPNSvgShapeKind.self, forKey: .`kind`)
        self.`d` = container.contains(.`d`) ? (try container.decode(String?.self, forKey: .`d`)) : (try PNValues.decode(String?.self, PNValues.defaultValue("null")))
        self.`cx` = container.contains(.`cx`) ? (try container.decode(Double?.self, forKey: .`cx`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`cy` = container.contains(.`cy`) ? (try container.decode(Double?.self, forKey: .`cy`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`r` = container.contains(.`r`) ? (try container.decode(Double?.self, forKey: .`r`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`rx` = container.contains(.`rx`) ? (try container.decode(Double?.self, forKey: .`rx`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`ry` = container.contains(.`ry`) ? (try container.decode(Double?.self, forKey: .`ry`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`x` = container.contains(.`x`) ? (try container.decode(Double?.self, forKey: .`x`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`y` = container.contains(.`y`) ? (try container.decode(Double?.self, forKey: .`y`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`width` = container.contains(.`width`) ? (try container.decode(Double?.self, forKey: .`width`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`height` = container.contains(.`height`) ? (try container.decode(Double?.self, forKey: .`height`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`x1` = container.contains(.`x1`) ? (try container.decode(Double?.self, forKey: .`x1`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`y1` = container.contains(.`y1`) ? (try container.decode(Double?.self, forKey: .`y1`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`x2` = container.contains(.`x2`) ? (try container.decode(Double?.self, forKey: .`x2`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`y2` = container.contains(.`y2`) ? (try container.decode(Double?.self, forKey: .`y2`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`points` = container.contains(.`points`) ? (try container.decode(String?.self, forKey: .`points`)) : (try PNValues.decode(String?.self, PNValues.defaultValue("null")))
        self.`fill` = container.contains(.`fill`) ? (try container.decode(String?.self, forKey: .`fill`)) : (try PNValues.decode(String?.self, PNValues.defaultValue("null")))
        self.`fill_opacity` = container.contains(.`fill_opacity`) ? (try container.decode(Double?.self, forKey: .`fill_opacity`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`fill_rule` = container.contains(.`fill_rule`) ? (try container.decode(PNPNSvgShapeFillRule?.self, forKey: .`fill_rule`)) : (try PNValues.decode(PNPNSvgShapeFillRule?.self, PNValues.defaultValue("null")))
        self.`stroke` = container.contains(.`stroke`) ? (try container.decode(String?.self, forKey: .`stroke`)) : (try PNValues.decode(String?.self, PNValues.defaultValue("null")))
        self.`stroke_width` = container.contains(.`stroke_width`) ? (try container.decode(Double?.self, forKey: .`stroke_width`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`stroke_opacity` = container.contains(.`stroke_opacity`) ? (try container.decode(Double?.self, forKey: .`stroke_opacity`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`stroke_linecap` = container.contains(.`stroke_linecap`) ? (try container.decode(PNPNSvgShapeStrokeLinecap?.self, forKey: .`stroke_linecap`)) : (try PNValues.decode(PNPNSvgShapeStrokeLinecap?.self, PNValues.defaultValue("null")))
        self.`stroke_linejoin` = container.contains(.`stroke_linejoin`) ? (try container.decode(PNPNSvgShapeStrokeLinejoin?.self, forKey: .`stroke_linejoin`)) : (try PNValues.decode(PNPNSvgShapeStrokeLinejoin?.self, PNValues.defaultValue("null")))
        self.`stroke_dasharray` = container.contains(.`stroke_dasharray`) ? (try container.decode([Double]?.self, forKey: .`stroke_dasharray`)) : (try PNValues.decode([Double]?.self, PNValues.defaultValue("null")))
        self.`opacity` = container.contains(.`opacity`) ? (try container.decode(Double?.self, forKey: .`opacity`)) : (try PNValues.decode(Double?.self, PNValues.defaultValue("null")))
        self.`transform` = container.contains(.`transform`) ? (try container.decode(String?.self, forKey: .`transform`)) : (try PNValues.decode(String?.self, PNValues.defaultValue("null")))
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`kind`, forKey: .`kind`)
        try container.encode(`d`, forKey: .`d`)
        try container.encode(`cx`, forKey: .`cx`)
        try container.encode(`cy`, forKey: .`cy`)
        try container.encode(`r`, forKey: .`r`)
        try container.encode(`rx`, forKey: .`rx`)
        try container.encode(`ry`, forKey: .`ry`)
        try container.encode(`x`, forKey: .`x`)
        try container.encode(`y`, forKey: .`y`)
        try container.encode(`width`, forKey: .`width`)
        try container.encode(`height`, forKey: .`height`)
        try container.encode(`x1`, forKey: .`x1`)
        try container.encode(`y1`, forKey: .`y1`)
        try container.encode(`x2`, forKey: .`x2`)
        try container.encode(`y2`, forKey: .`y2`)
        try container.encode(`points`, forKey: .`points`)
        try container.encode(`fill`, forKey: .`fill`)
        try container.encode(`fill_opacity`, forKey: .`fill_opacity`)
        try container.encode(`fill_rule`, forKey: .`fill_rule`)
        try container.encode(`stroke`, forKey: .`stroke`)
        try container.encode(`stroke_width`, forKey: .`stroke_width`)
        try container.encode(`stroke_opacity`, forKey: .`stroke_opacity`)
        try container.encode(`stroke_linecap`, forKey: .`stroke_linecap`)
        try container.encode(`stroke_linejoin`, forKey: .`stroke_linejoin`)
        try container.encode(`stroke_dasharray`, forKey: .`stroke_dasharray`)
        try container.encode(`opacity`, forKey: .`opacity`)
        try container.encode(`transform`, forKey: .`transform`)
    }
}

public enum PNSvgPreserveAspectRatio: String, Codable {
    case `meet` = "meet"
    case `slice` = "slice"
    case `none` = "none"
}

public struct PNPNTabBarItemsItemIcon: Codable {
    public let `shapes`: [PNSvgShape]?
    public let `view_box`: String?
    public let `uri`: String?
    public init(`shapes`: [PNSvgShape]?, `view_box`: String?, `uri`: String?) {
        self.`shapes` = `shapes`
        self.`view_box` = `view_box`
        self.`uri` = `uri`
    }
    private enum CodingKeys: String, CodingKey { case `shapes`; case `view_box`; case `uri` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`shapes` = try container.decodeIfPresent([PNSvgShape].self, forKey: .`shapes`)
        self.`view_box` = try container.decodeIfPresent(String.self, forKey: .`view_box`)
        self.`uri` = try container.decodeIfPresent(String.self, forKey: .`uri`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encodeIfPresent(`shapes`, forKey: .`shapes`)
        try container.encodeIfPresent(`view_box`, forKey: .`view_box`)
        try container.encodeIfPresent(`uri`, forKey: .`uri`)
    }
}

public struct PNTabBarItemsItem: Codable {
    public let `name`: String
    public let `title`: String
    public let `icon`: PNPNTabBarItemsItemIcon?
    public let `badge`: String?
    public init(`name`: String, `title`: String, `icon`: PNPNTabBarItemsItemIcon?, `badge`: String?) {
        self.`name` = `name`
        self.`title` = `title`
        self.`icon` = `icon`
        self.`badge` = `badge`
    }
    private enum CodingKeys: String, CodingKey { case `name`; case `title`; case `icon`; case `badge` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`name` = try container.decode(String.self, forKey: .`name`)
        self.`title` = try container.decode(String.self, forKey: .`title`)
        self.`icon` = try container.decodeIfPresent(PNPNTabBarItemsItemIcon.self, forKey: .`icon`)
        self.`badge` = try container.decodeIfPresent(String.self, forKey: .`badge`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`name`, forKey: .`name`)
        try container.encode(`title`, forKey: .`title`)
        try container.encodeIfPresent(`icon`, forKey: .`icon`)
        try container.encodeIfPresent(`badge`, forKey: .`badge`)
    }
}

public enum PNTextInputKeyboardType: String, Codable {
    case `default` = "default"
    case `email_address` = "email_address"
    case `number_pad` = "number_pad"
    case `decimal_pad` = "decimal_pad"
    case `phone_pad` = "phone_pad"
    case `url` = "url"
}

public enum PNTextInputAutoCapitalize: String, Codable {
    case `none` = "none"
    case `sentences` = "sentences"
    case `words` = "words"
    case `characters` = "characters"
}

public enum PNTextInputReturnKeyType: String, Codable {
    case `default` = "default"
    case `done` = "done"
    case `go` = "go"
    case `next` = "next"
    case `send` = "send"
    case `search` = "search"
}

public struct PNWebNavigationEvent: Codable {
    public let `url`: String
    public let `loading`: Bool
    public let `can_go_back`: Bool
    public let `can_go_forward`: Bool
    public let `title`: String
    public init(`url`: String, `loading`: Bool, `can_go_back`: Bool, `can_go_forward`: Bool, `title`: String) {
        self.`url` = `url`
        self.`loading` = `loading`
        self.`can_go_back` = `can_go_back`
        self.`can_go_forward` = `can_go_forward`
        self.`title` = `title`
    }
    private enum CodingKeys: String, CodingKey { case `url`; case `loading`; case `can_go_back`; case `can_go_forward`; case `title` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`url` = try container.decode(String.self, forKey: .`url`)
        self.`loading` = try container.decode(Bool.self, forKey: .`loading`)
        self.`can_go_back` = try container.decode(Bool.self, forKey: .`can_go_back`)
        self.`can_go_forward` = try container.decode(Bool.self, forKey: .`can_go_forward`)
        self.`title` = container.contains(.`title`) ? (try container.decode(String.self, forKey: .`title`)) : (try PNValues.decode(String.self, PNValues.defaultValue("\"\"")))
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`url`, forKey: .`url`)
        try container.encode(`loading`, forKey: .`loading`)
        try container.encode(`can_go_back`, forKey: .`can_go_back`)
        try container.encode(`can_go_forward`, forKey: .`can_go_forward`)
        try container.encode(`title`, forKey: .`title`)
    }
}

public struct PNFontFace: Codable {
    public let `family`: String
    public let `weight`: Int64
    public let `italic`: Bool
    public let `postscript_name`: String
    public let `path`: String
    public init(`family`: String, `weight`: Int64, `italic`: Bool, `postscript_name`: String, `path`: String) {
        self.`family` = `family`
        self.`weight` = `weight`
        self.`italic` = `italic`
        self.`postscript_name` = `postscript_name`
        self.`path` = `path`
    }
    private enum CodingKeys: String, CodingKey { case `family`; case `weight`; case `italic`; case `postscript_name`; case `path` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`family` = try container.decode(String.self, forKey: .`family`)
        self.`weight` = try container.decode(Int64.self, forKey: .`weight`)
        self.`italic` = try container.decode(Bool.self, forKey: .`italic`)
        self.`postscript_name` = try container.decode(String.self, forKey: .`postscript_name`)
        self.`path` = try container.decode(String.self, forKey: .`path`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`family`, forKey: .`family`)
        try container.encode(`weight`, forKey: .`weight`)
        try container.encode(`italic`, forKey: .`italic`)
        try container.encode(`postscript_name`, forKey: .`postscript_name`)
        try container.encode(`path`, forKey: .`path`)
    }
}

public struct PNAssetManifest: Codable {
    public let `files`: [String]
    public let `variants`: [String: [String: String]]
    public let `fonts`: [PNFontFace]
    public init(`files`: [String], `variants`: [String: [String: String]], `fonts`: [PNFontFace]) {
        self.`files` = `files`
        self.`variants` = `variants`
        self.`fonts` = `fonts`
    }
    private enum CodingKeys: String, CodingKey { case `files`; case `variants`; case `fonts` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`files` = container.contains(.`files`) ? (try container.decode([String].self, forKey: .`files`)) : (try PNValues.decode([String].self, PNValues.defaultValue("[]")))
        self.`variants` = container.contains(.`variants`) ? (try container.decode([String: [String: String]].self, forKey: .`variants`)) : (try PNValues.decode([String: [String: String]].self, PNValues.defaultValue("{}")))
        self.`fonts` = container.contains(.`fonts`) ? (try container.decode([PNFontFace].self, forKey: .`fonts`)) : (try PNValues.decode([PNFontFace].self, PNValues.defaultValue("[]")))
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`files`, forKey: .`files`)
        try container.encode(`variants`, forKey: .`variants`)
        try container.encode(`fonts`, forKey: .`fonts`)
    }
}

public struct PNImageSize: Codable {
    public let `width`: Double
    public let `height`: Double
    public init(`width`: Double, `height`: Double) {
        self.`width` = `width`
        self.`height` = `height`
    }
    private enum CodingKeys: String, CodingKey { case `width`; case `height` }
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.`width` = try container.decode(Double.self, forKey: .`width`)
        self.`height` = try container.decode(Double.self, forKey: .`height`)
    }
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(`width`, forKey: .`width`)
        try container.encode(`height`, forKey: .`height`)
    }
}

public enum PNLocationGetCurrentAccuracy: String, Codable {
    case `balanced` = "balanced"
    case `high` = "high"
}
