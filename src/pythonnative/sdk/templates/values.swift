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
