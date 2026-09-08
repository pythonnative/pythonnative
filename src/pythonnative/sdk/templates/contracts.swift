import Foundation
import CoreFoundation

/// Generated contract metadata; validation is shared by built-ins and plugins.
public enum PNContracts {
    public static let fingerprint = "{{fingerprint}}"
    private static let specification = """
{{specification}}
"""
    private static let components = (try! JSONSerialization.jsonObject(with: Data(specification.utf8)) as! [String: Any])["components"] as! [String: [String: Any]]

    public static func validate(_ name: String, _ props: [String: Any], partial: Bool = false) -> Bool {
        guard let schema = components[name], let fields = schema["props"] as? [String: [String: Any]] else { return true }
        if !partial {
            for key in schema["required"] as? [String] ?? [] where props[key] == nil { return false }
        }
        for (key, value) in props {
            if value is NSNull && partial { continue }
            if let field = fields[key], !matches(value, field) { return false }
        }
        return true
    }

    public static func invalidatesLayout(_ name: String, _ changed: [String: Any]) -> Bool {
        guard let fields = components[name]?["props"] as? [String: [String: Any]] else { return true }
        return changed.keys.contains { ((fields[$0]?["native"] as? [String: Any])?["invalidates_layout"] as? Bool) ?? true }
    }

    private static func matches(_ value: Any, _ schema: [String: Any]) -> Bool {
        if let alternatives = schema["anyOf"] as? [[String: Any]] { return alternatives.contains { matches(value, $0) } }
        if let values = schema["enum"] as? [Any] { return values.contains { String(describing: $0) == String(describing: value) } }
        switch schema["type"] as? String {
        case "null": return value is NSNull
        case "string": return value is String
        case "boolean": return (value as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false
        case "integer": return (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.rounded() == $0.doubleValue } ?? false
        case "number": return (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite } ?? false
        case "array":
            guard let array = value as? [Any] else { return false }
            return array.allSatisfy { matches($0, schema["items"] as? [String: Any] ?? [:]) }
        case "object": return value is [String: Any]
        case "event": return value is Bool || value is NSNull
        default: return true
        }
    }
}
