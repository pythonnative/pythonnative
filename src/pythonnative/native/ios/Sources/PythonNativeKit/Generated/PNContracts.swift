import Foundation
import PNCore

/// The contract this library was generated from. The renderer core compiles
/// the same contracts and validates every commit, command, and module call;
/// nothing on the Swift side interprets them.
public enum PNContracts {
    public static let fingerprint = "b89b466f083ea2df7473d29e351ce99257f66792a17955c6ce3c2c0f238ae5c3"
    public static let protocolVersion = 7
    public static let yogaVersion = "3.2.1"

    /// Whether a native module call's arguments satisfy its contract.
    public static func validateModule(_ name: String, _ method: String, _ args: [String: Any]) -> Bool {
        if ["DevSupport", "Host", "Runtime"].contains(name) { return true }
        guard JSONSerialization.isValidJSONObject(args),
              let data = try? JSONSerialization.data(withJSONObject: args),
              let json = String(data: data, encoding: .utf8) else { return false }
        return pn_core_validate_module(pn_core_shared(), name, method, json) != 0
    }
}
