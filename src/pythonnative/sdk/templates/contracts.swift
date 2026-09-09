import Foundation
import CoreFoundation

/// Generated contract metadata; validation is shared by built-ins and plugins.
public enum PNContracts {
    public static let fingerprint = "{{fingerprint}}"
    private static let specification = """
{{specification}}
"""
    private static let document = try! JSONSerialization.jsonObject(with: Data(specification.utf8)) as! [String: Any]
    private static let components = document["components"] as! [String: [String: Any]]
    private static let modules = document["modules"] as! [String: [String: Any]]

    public static func validate(_ name: String, _ props: [String: Any], partial: Bool = false) -> Bool {
        guard let schema = components[name], let fields = schema["props"] as? [String: [String: Any]] else { return false }
        if !partial {
            for key in schema["required"] as? [String] ?? [] where props[key] == nil { return false }
        }
        for (key, value) in props {
            guard let field = fields[key] else { return false }
            if let platforms = (field["native"] as? [String: Any])?["platforms"] as? [String], !platforms.contains("ios") { return false }
            if value is NSNull && partial {
                if (schema["required"] as? [String] ?? []).contains(key) { return false }
                continue
            }
            if !matches(value, field) { return false }
        }
        return true
    }

    public static func invalidatesLayout(_ name: String, _ changed: [String: Any]) -> Bool {
        guard let fields = components[name]?["props"] as? [String: [String: Any]] else { return true }
        return changed.keys.contains { ((fields[$0]?["native"] as? [String: Any])?["invalidates_layout"] as? Bool) ?? true }
    }

    public static func requiresRecreation(_ name: String, _ changed: [String: Any]) -> Bool {
        let fields = components[name]?["props"] as? [String: [String: Any]] ?? [:]
        let defaults = components[name]?["defaults"] as? [String: Any] ?? [:]
        return changed.contains { key, value in
            ((fields[key]?["native"] as? [String: Any])?["recreate"] as? Bool ?? false)
                || (value is NSNull && (defaults[key] == nil || defaults[key] is NSNull))
        }
    }

    public static func normalize(_ name: String, _ changed: [String: Any]) -> [String: Any] {
        let defaults = components[name]?["defaults"] as? [String: Any] ?? [:]
        return changed.reduce(into: [:]) { result, item in result[item.key] = item.value is NSNull ? (defaults[item.key] ?? NSNull()) : item.value }
    }

    public static func validateCommand(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        guard let commands = components[name]?["commands"] as? [String: [String: Any]], let command = commands[method] else { return false }
        return validateArguments(command, args)
    }

    public static func validateModule(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        // Host, Layout, and Runtime are renderer control channels.
        guard let module = modules[name] else { return ["Host", "Layout", "Runtime"].contains(name) }
        guard let methods = module["methods"] as? [String: [String: Any]], let command = methods[method] else { return false }
        return validateArguments(command, args)
    }

    private static func validateArguments(_ command: [String: Any], _ args: [String: Any]) -> Bool {
        let fields = command["arguments"] as? [String: Any] ?? [:]
        return matches(args, ["type": "object", "properties": fields, "required": command["required"] ?? Array(fields.keys), "additionalProperties": false])
    }

    public static func matches(_ value: Any, _ schema: [String: Any]) -> Bool {
        if let alternatives = schema["anyOf"] as? [[String: Any]] { return alternatives.contains { matches(value, $0) } }
        if let values = schema["enum"] as? [Any] {
            return values.contains { candidate in
                if let a = candidate as? NSNumber, let b = value as? NSNumber {
                    return (CFGetTypeID(a) == CFBooleanGetTypeID()) == (CFGetTypeID(b) == CFBooleanGetTypeID()) && a == b
                }
                if let a = candidate as? String, let b = value as? String { return a == b }
                return candidate is NSNull && value is NSNull
            }
        }
        switch schema["type"] as? String {
        case "null": return value is NSNull
        case "string": return value is String
        case "boolean": return (value as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false
        case "integer": return (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite && abs($0.doubleValue) <= 9_007_199_254_740_991 && $0.doubleValue.rounded() == $0.doubleValue } ?? false
        case "number": return (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite } ?? false
        case "array":
            guard let array = value as? [Any] else { return false }
            return array.allSatisfy { matches($0, schema["items"] as? [String: Any] ?? [:]) }
        case "object":
            guard let object = value as? [String: Any] else { return false }
            let fields = schema["properties"] as? [String: [String: Any]] ?? [:]
            for key in schema["required"] as? [String] ?? [] where object[key] == nil { return false }
            for (key, item) in object {
                if let field = fields[key] { if !matches(item, field) { return false } }
                else if let additional = schema["additionalProperties"] as? [String: Any] { if !matches(item, additional) { return false } }
                else if schema["additionalProperties"] as? Bool == false { return false }
            }
            return true
        case "event": return (value as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false
        default: return true
        }
    }
}
