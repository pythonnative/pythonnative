import Foundation

/// JSON helpers shared by the bridge, event emitters, and modules.
///
/// Encoding tolerates values `JSONSerialization` rejects (non-finite
/// doubles, `Optional.none`, `CGFloat`, `URL`) by normalizing them
/// first; decoding turns the Python-side `"inf"` marker back into
/// `Double.infinity`.
public enum PNJSON {
    /// Decode a JSON document into Foundation containers.
    public static func decode(_ text: String) -> Any? {
        guard let data = text.data(using: .utf8) else { return nil }
        return try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    }

    /// Decode a JSON object, returning an empty dictionary for anything else.
    public static func decodeObject(_ text: String?) -> [String: Any] {
        guard let text = text, let value = decode(text) as? [String: Any] else { return [:] }
        return value
    }

    /// Encode any JSON-compatible value (a fragment is allowed).
    public static func encode(_ value: Any?) -> String {
        let normalized = normalize(value)
        guard JSONSerialization.isValidJSONObject([normalized]) else { return "null" }
        guard let data = try? JSONSerialization.data(withJSONObject: normalized, options: [.fragmentsAllowed]),
              let text = String(data: data, encoding: .utf8)
        else {
            return "null"
        }
        return text
    }

    /// Replace every `"inf"` string in a decoded prop tree with `Double.infinity`.
    public static func resolveInfinity(_ value: Any) -> Any {
        if let string = value as? String {
            return string == "inf" ? Double.infinity : string
        }
        if let dict = value as? [String: Any] {
            var out: [String: Any] = [:]
            out.reserveCapacity(dict.count)
            for (key, item) in dict {
                out[key] = resolveInfinity(item)
            }
            return out
        }
        if let array = value as? [Any] {
            return array.map { resolveInfinity($0) }
        }
        return value
    }

    /// Convert arbitrary values to something `JSONSerialization` accepts.
    static func normalize(_ value: Any?) -> Any {
        guard let value = value else { return NSNull() }
        switch value {
        case let optional as Optional<Any>:
            guard let unwrapped = optional else { return NSNull() }
            return normalizeConcrete(unwrapped)
        default:
            return normalizeConcrete(value)
        }
    }

    private static func normalizeConcrete(_ value: Any) -> Any {
        switch value {
        case is NSNull:
            return value
        case let bool as Bool:
            return bool
        case let double as Double:
            return double.isFinite ? double : NSNull()
        case let float as Float:
            return float.isFinite ? Double(float) : NSNull()
        case let cg as CGFloat:
            return cg.isFinite ? Double(cg) : NSNull()
        case let int as Int:
            return int
        case let int64 as Int64:
            return int64
        case let number as NSNumber:
            return number
        case let string as String:
            return string
        case let url as URL:
            return url.absoluteString
        case let dict as [String: Any]:
            var out: [String: Any] = [:]
            out.reserveCapacity(dict.count)
            for (key, item) in dict {
                out[key] = normalize(item)
            }
            return out
        case let array as [Any]:
            return array.map { normalize($0) }
        default:
            return String(describing: value)
        }
    }
}

/// Typed accessors for loosely typed prop dictionaries.
public enum PNProps {
    /// Coerce numbers, numeric strings, and the `"inf"` marker to `Double`.
    public static func double(_ value: Any?) -> Double? {
        switch value {
        case let d as Double: return d
        case let f as Float: return Double(f)
        case let cg as CGFloat: return Double(cg)
        case let i as Int: return Double(i)
        case let n as NSNumber: return n.doubleValue
        case let s as String:
            if s == "inf" { return Double.infinity }
            if s == "-inf" { return -Double.infinity }
            return Double(s)
        default: return nil
        }
    }

    /// Like `double(_:)` but non-finite values fall back to `fallback`.
    public static func finite(_ value: Any?, _ fallback: Double = 0) -> Double {
        guard let d = double(value), d.isFinite else { return fallback }
        return d
    }

    public static func int(_ value: Any?) -> Int? {
        switch value {
        case let i as Int: return i
        case let n as NSNumber: return n.intValue
        case let d as Double: return d.isFinite ? Int(d) : nil
        case let s as String: return Int(s) ?? Double(s).map { Int($0) }
        default: return nil
        }
    }

    public static func bool(_ value: Any?) -> Bool? {
        switch value {
        case let b as Bool: return b
        case let n as NSNumber: return n.boolValue
        case let s as String: return s.lowercased() == "true"
        default: return nil
        }
    }

    public static func string(_ value: Any?) -> String? {
        switch value {
        case nil: return nil
        case is NSNull: return nil
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        default: return String(describing: value as Any)
        }
    }

    public static func dict(_ value: Any?) -> [String: Any]? {
        value as? [String: Any]
    }

    public static func array(_ value: Any?) -> [Any]? {
        value as? [Any]
    }

    /// True when the key is present, even if its value is `null`.
    public static func has(_ props: [String: Any], _ key: String) -> Bool {
        props.index(forKey: key) != nil
    }

    /// The value for `key`, treating JSON `null` as absent.
    public static func value(_ props: [String: Any], _ key: String) -> Any? {
        guard let v = props[key], !(v is NSNull) else { return nil }
        return v
    }
}
