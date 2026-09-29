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
        // Common scalar props need no JSON round trip. Complex records still
        // use their generated Codable implementations once per prop wrapper.
        if type == String.self, let scalar = value as? String { return scalar as! T }
        if type == Bool.self, let scalar = value as? NSNumber, CFGetTypeID(scalar) == CFBooleanGetTypeID() { return scalar.boolValue as! T }
        if let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(), number.doubleValue.isFinite {
            if type == Double.self { return number.doubleValue as! T }
            if type == Int64.self, abs(number.doubleValue) <= 9_007_199_254_740_991, number.doubleValue.rounded() == number.doubleValue { return number.int64Value as! T }
        }
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
        let encoder = PNValueEncoder()
        try encoder.encode(value)
        return encoder.storage.value()
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
    init(_ values: [String: Any], partial: Bool, validated: Bool) throws
}

/// Encode generated Codable values directly into bridge values. This avoids a
/// JSON round trip and preserves embedded NULs on every supported Foundation.
private final class PNEncodedValue {
    var scalar: Any?
    var object: [String: PNEncodedValue]?
    var array: [PNEncodedValue]?
    func value() -> Any {
        if let object = object { return object.mapValues { $0.value() } }
        if let array = array { return array.map { $0.value() } }
        return scalar ?? NSNull()
    }
}

private final class PNValueEncoder: Encoder {
    let storage: PNEncodedValue
    let codingPath: [CodingKey]
    var userInfo: [CodingUserInfoKey: Any] { [:] }
    init(_ storage: PNEncodedValue = PNEncodedValue(), path: [CodingKey] = []) {
        self.storage = storage; codingPath = path
    }
    func container<Key: CodingKey>(keyedBy: Key.Type) -> KeyedEncodingContainer<Key> {
        if storage.object == nil { storage.object = [:] }
        return KeyedEncodingContainer(PNKeyedValues<Key>(encoder: self))
    }
    func unkeyedContainer() -> UnkeyedEncodingContainer {
        if storage.array == nil { storage.array = [] }
        return PNArrayValues(encoder: self)
    }
    func singleValueContainer() -> SingleValueEncodingContainer { PNScalarValue(encoder: self) }
    func encode<T: Encodable>(_ value: T) throws { try value.encode(to: self) }
    func child(_ key: CodingKey) -> PNValueEncoder { PNValueEncoder(path: codingPath + [key]) }
}

private struct PNValueKey: CodingKey {
    let stringValue: String
    let intValue: Int?
    init(stringValue: String) { self.stringValue = stringValue; intValue = nil }
    init(intValue: Int) { self.intValue = intValue; stringValue = String(intValue) }
}

private struct PNKeyedValues<Key: CodingKey>: KeyedEncodingContainerProtocol {
    let encoder: PNValueEncoder
    var codingPath: [CodingKey] { encoder.codingPath }
    func put(_ key: Key) -> PNValueEncoder {
        let child = encoder.child(key); encoder.storage.object![key.stringValue] = child.storage; return child
    }
    mutating func encodeNil(forKey key: Key) throws { put(key).storage.scalar = NSNull() }
    mutating func encode<T: Encodable>(_ value: T, forKey key: Key) throws { try put(key).encode(value) }
    mutating func nestedContainer<NestedKey: CodingKey>(keyedBy: NestedKey.Type, forKey key: Key) -> KeyedEncodingContainer<NestedKey> {
        put(key).container(keyedBy: keyedBy)
    }
    mutating func nestedUnkeyedContainer(forKey key: Key) -> UnkeyedEncodingContainer { put(key).unkeyedContainer() }
    mutating func superEncoder() -> Encoder {
        let key = PNValueKey(stringValue: "super"), child = encoder.child(PNValueKey(stringValue: "super"))
        encoder.storage.object![key.stringValue] = child.storage; return child
    }
    mutating func superEncoder(forKey key: Key) -> Encoder { put(key) }
}

private struct PNArrayValues: UnkeyedEncodingContainer {
    let encoder: PNValueEncoder
    var codingPath: [CodingKey] { encoder.codingPath }
    var count: Int { encoder.storage.array!.count }
    func next() -> PNValueEncoder {
        let child = encoder.child(PNValueKey(intValue: count)); encoder.storage.array!.append(child.storage); return child
    }
    mutating func encodeNil() throws { next().storage.scalar = NSNull() }
    mutating func encode<T: Encodable>(_ value: T) throws { try next().encode(value) }
    mutating func nestedContainer<NestedKey: CodingKey>(keyedBy: NestedKey.Type) -> KeyedEncodingContainer<NestedKey> {
        next().container(keyedBy: keyedBy)
    }
    mutating func nestedUnkeyedContainer() -> UnkeyedEncodingContainer { next().unkeyedContainer() }
    mutating func superEncoder() -> Encoder { next() }
}

private struct PNScalarValue: SingleValueEncodingContainer {
    let encoder: PNValueEncoder
    var codingPath: [CodingKey] { encoder.codingPath }
    mutating func encodeNil() throws { encoder.storage.scalar = NSNull() }
    mutating func encode(_ value: Bool) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: String) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: Double) throws {
        guard value.isFinite else { throw EncodingError.invalidValue(value, .init(codingPath: codingPath, debugDescription: "Nonfinite bridge number")) }
        encoder.storage.scalar = value
    }
    mutating func encode(_ value: Float) throws { try encode(Double(value)) }
    mutating func encode(_ value: Int) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: Int8) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: Int16) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: Int32) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: Int64) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: UInt) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: UInt8) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: UInt16) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: UInt32) throws { encoder.storage.scalar = value }
    mutating func encode(_ value: UInt64) throws { encoder.storage.scalar = value }
    mutating func encode<T: Encodable>(_ value: T) throws { try encoder.encode(value) }
}
