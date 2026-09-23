import Foundation
import CoreFoundation

/// Executable generated contracts. No schema JSON is interpreted on the mount path.
public enum PNContracts {
    public static let fingerprint = "{{fingerprint}}"
    private struct Field {
        let matches: (Any) -> Bool
        let allowed: Bool
        let layout: Bool
        let recreate: Bool
        let required: Bool
        let defaultValue: Any
        init(_ matches: @escaping (Any) -> Bool, _ allowed: Bool, _ layout: Bool, _ recreate: Bool, _ required: Bool, _ defaultValue: Any) {
            self.matches = matches; self.allowed = allowed; self.layout = layout
            self.recreate = recreate; self.required = required; self.defaultValue = defaultValue
        }
    }
    public struct ChangeMask: OptionSet {
        public let rawValue: Int
        public init(rawValue: Int) { self.rawValue = rawValue }
        public static let layout = ChangeMask(rawValue: 1)
        public static let recreate = ChangeMask(rawValue: 2)
    }
{{predicates}}
{{fields}}
    private static let components: [String: [String: Field]] = [
{{components}}
    ]
    private static let commands: [String: (Any) -> Bool] = [
{{commands}}
    ]
    private static let modules: [String: (Any) -> Bool] = [
{{modules}}
    ]
    private static func isBoolean(_ value: Any) -> Bool {
        (value as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false
    }
    private static func isNumber(_ value: Any) -> Bool {
        (value as? NSNumber).map { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite } ?? false
    }
    private static func isInteger(_ value: Any) -> Bool {
        guard isNumber(value), let number = value as? NSNumber else { return false }
        return abs(number.doubleValue) <= 9_007_199_254_740_991 && number.doubleValue.rounded() == number.doubleValue
    }
    public static func validate(_ name: String, _ props: [String: Any], partial: Bool = false) -> Bool {
        guard let fields = components[name] else { return false }
        if !partial && fields.contains(where: { $0.value.required && props[$0.key] == nil }) { return false }
        return props.allSatisfy { key, value in fields[key].map { $0.allowed && $0.matches(value) } ?? false }
    }
    public static func changes(_ name: String, _ keys: Set<String>) -> ChangeMask {
        guard let fields = components[name] else { return [.layout, .recreate] }
        var mask: ChangeMask = []
        for key in keys {
            if fields[key]?.layout ?? true { mask.insert(.layout) }
            if fields[key]?.recreate ?? false { mask.insert(.recreate) }
        }
        return mask
    }
    public static func invalidatesLayout(_ name: String, _ changed: [String: Any]) -> Bool {
        changes(name, Set(changed.keys)).contains(.layout)
    }
    public static func validateRemoval(_ name: String, _ changed: [String: Any], _ removed: [String]) -> Bool {
        guard let fields = components[name] else { return false }
        return Set(removed).count == removed.count && removed.allSatisfy { key in
            fields[key].map { !$0.required && $0.allowed && changed[key] == nil } ?? false
        }
    }
    public static func requiresRecreation(_ name: String, _ changed: [String: Any], removed: [String] = []) -> Bool {
        changes(name, Set(changed.keys).union(removed)).contains(.recreate)
    }
    public static func normalize(_ name: String, _ changed: [String: Any], removed: [String] = []) -> [String: Any] {
        var result = changed
        for key in removed { result[key] = components[name]?[key]?.defaultValue ?? NSNull() }
        return result
    }
    public static func validateCommand(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        commands[name + "." + method]?(args) ?? false
    }
    public static func validateModule(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        if ["Host", "Layout", "Runtime"].contains(name) { return true }
        return modules[name + "." + method]?(args) ?? false
    }
}
