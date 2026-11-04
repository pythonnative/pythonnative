import Foundation
import PNCore

/// The contract this library was generated from. The renderer core compiles
/// the same contracts and validates every commit, command, and module call;
/// nothing on the Swift side interprets them.
public enum PNContracts {
    public static let fingerprint = "d0f4503111acbb6117870bb5bdd997964a29ec05d3190445e2c12ce446b18c4d"
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
