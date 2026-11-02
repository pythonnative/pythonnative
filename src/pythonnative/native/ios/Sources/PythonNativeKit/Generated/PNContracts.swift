import Foundation
import PNCore

/// The contract this library was generated from. The renderer core compiles
/// the same contracts and validates every commit, command, and module call;
/// nothing on the Swift side interprets them.
public enum PNContracts {
    public static let fingerprint = "4f3c6c610fd0f6b21949e7ed16e03fd100dd347c3e29be0dedd509b0fdb386dc"
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
