import LocalAuthentication
import UIKit

/// Registers `Biometrics`. Face ID has no prompt of its own to manage: iOS shows
/// it on the first `authenticate`, using the app's `NSFaceIDUsageDescription`.
public enum BiometricsPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(BiometricsModuleAdapter<BiometricsModule>.self)
    }
}

/// `Biometrics`: `LAContext` availability and authentication.
public final class BiometricsModule: BiometricsImplementation {
    public init() {}

    public func is_available() -> Bool {
        var error: NSError?
        return LAContext().canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }

    public func authenticate(reason: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        let context = LAContext()
        var error: NSError?
        let policy: LAPolicy = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
            ? .deviceOwnerAuthenticationWithBiometrics : .deviceOwnerAuthentication
        context.evaluatePolicy(policy, localizedReason: reason) { success, _ in
            DispatchQueue.main.async { completion(.success(success)) }
        }
        return { context.invalidate() }
    }
}
