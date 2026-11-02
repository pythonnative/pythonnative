import Foundation

/// A plugin's answer for one `[permissions]` name. The kit itself imports no
/// privacy-sensitive framework: a name works only when a plugin that uses it
/// is in the build, so an app never references an API it doesn't call.
public protocol PNPermissionProvider: AnyObject {
    /// Report `granted`, `denied`, `blocked`, or `undetermined` on the main thread.
    func check(_ done: @escaping (String) -> Void)
    /// Prompt if needed and report the result on the main thread. Returns a
    /// cancellation for prompts the app can withdraw.
    func request(_ done: @escaping (String) -> Void) -> (() -> Void)?
}

/// The permission names plugins have registered.
public enum PNPermissions {
    private static var providers: [String: PNPermissionProvider] = [:]

    /// Register (or replace) the provider for permission `name`.
    public static func register(_ name: String, _ provider: PNPermissionProvider) {
        providers[name] = provider
    }

    static func provider(_ name: String) -> PNPermissionProvider? {
        PNRegistry.shared.ensureBuiltins()
        return providers[name]
    }
}

/// `Permissions`: `check` and `request` (async), answered by the providers
/// plugins register. The Python facade validates the name's format; a name no
/// plugin in this build owns is rejected with a code it can explain.
public final class PermissionsModule: PermissionsImplementation {
    public init() {}

    private func provider(_ permission: String, completion: (Result<String, Error>) -> Void) -> PNPermissionProvider? {
        if let provider = PNPermissions.provider(permission) { return provider }
        completion(.failure(NSError(domain: "plugin_not_enabled", code: 1, userInfo: [NSLocalizedDescriptionKey: "No plugin in this build provides the \(permission) permission"])))
        return nil
    }

    public func check(permission: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)? {
        guard let provider = provider(permission, completion: completion) else { return nil }
        var cancelled = false
        provider.check { if !cancelled { completion(.success($0)) } }
        return { cancelled = true }
    }

    public func request(permission: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)? {
        guard let provider = provider(permission, completion: completion) else { return nil }
        var cancelled = false
        let cancel = provider.request { if !cancelled { completion(.success($0)) } }
        // System permission prompts can't be dismissed by an app. Detach the waiter.
        return { cancelled = true; cancel?() }
    }
}
