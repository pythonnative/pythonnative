import UIKit
import UserNotifications

/// Registers `Push` and the lifecycle hook that hears from APNs.
public enum PushPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(PushModuleAdapter<PushModule>.self)
        registry.registerLifecycleHook(PNPushHub.shared)
    }
}

/// APNs registration and delivery. Touched only on the main thread.
final class PNPushHub: PNAppLifecycleHook {
    static let shared = PNPushHub()

    /// How long APNs gets to answer: it never calls back with no network.
    private static let registrationTimeout: TimeInterval = 30
    /// How long a background wake stays open, so Python's handlers can run
    /// (a cold wake starts Python first). iOS allows 30 seconds.
    private static let backgroundWindow: TimeInterval = 5
    private static let duplicateWindow: TimeInterval = 5

    let tokens = PNBufferedEvent(module: "Push", event: "token")
    let messages = PNBufferedEvent(module: "Push", event: "message")
    private(set) var token: String?
    private var waiters: [UUID: (Result<String?, Error>) -> Void] = [:]
    private var unmatched: [(presented: Bool, key: Data, time: Date)] = []

    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {
        PNNotificationCenter.shared.onForegroundPush = { [weak self] userInfo in self?.arrive(userInfo, presented: true) }
    }

    func register(_ waiter: @escaping (Result<String?, Error>) -> Void) -> (() -> Void) {
        let id = UUID()
        waiters[id] = waiter
        UIApplication.shared.registerForRemoteNotifications()
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.registrationTimeout) { [weak self] in
            self?.waiters.removeValue(forKey: id)?(.failure(Self.error("APNs didn't answer the registration request")))
        }
        return { [weak self] in self?.waiters.removeValue(forKey: id) }
    }

    func didRegisterForRemoteNotifications(deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02x", $0) }.joined()
        if hex != token {
            token = hex
            tokens.send(hex)
        }
        settle(.success(hex))
    }

    func didFailToRegisterForRemoteNotifications(error: Error) {
        PNLog.modules.error("APNs registration failed: \(error.localizedDescription)")
        settle(.failure(Self.error(error.localizedDescription)))
    }

    func didReceiveRemoteNotification(_ userInfo: [AnyHashable: Any], completion: @escaping (UIBackgroundFetchResult) -> Void) -> Bool {
        arrive(userInfo, presented: false)
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.backgroundWindow) { completion(.newData) }
        return true
    }

    /// A foreground push with `content-available` comes through both the
    /// notification center and `didReceiveRemoteNotification`, in either order
    /// and with nothing to identify it, so a copy from one path cancels a recent
    /// identical copy from the other.
    private func arrive(_ userInfo: [AnyHashable: Any], presented: Bool) {
        let key = (try? JSONSerialization.data(withJSONObject: userInfo, options: [.sortedKeys])) ?? Data()
        let now = Date()
        unmatched.removeAll { now.timeIntervalSince($0.time) > Self.duplicateWindow }
        if let match = unmatched.firstIndex(where: { $0.presented != presented && $0.key == key }) {
            unmatched.remove(at: match)
            return
        }
        unmatched.append((presented, key, now))
        deliver(userInfo)
    }

    private func deliver(_ userInfo: [AnyHashable: Any]) {
        var payload: [String: PNJSONValue] = ["data": .object(PNNotificationCenter.data(userInfo))]
        let alert = (userInfo["aps"] as? [String: Any])?["alert"]
        if let body = alert as? String {
            payload["body"] = .string(body)
        } else if let alert = alert as? [String: Any] {
            if let title = alert["title"] as? String { payload["title"] = .string(title) }
            if let body = alert["body"] as? String { payload["body"] = .string(body) }
        }
        messages.send(PNValues.encode(payload))
    }

    private func settle(_ result: Result<String?, Error>) {
        let pending = waiters
        waiters = [:]
        for waiter in pending.values { waiter(result) }
    }

    private static func error(_ message: String) -> Error {
        NSError(domain: "apns", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}

/// `Push`: the APNs device token and remote messages.
public final class PushModule: PushImplementation {
    public init() {}

    public func get_device_token(completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        if let token = PNPushHub.shared.token {
            completion(.success(token))
            return nil
        }
        return PNPushHub.shared.register(completion)
    }

    public func set_listening(event: PNPushSetListeningEvent, listening: Bool) throws {
        switch event {
        case .token:
            PNPushHub.shared.tokens.setListening(listening)
            // APNs reports a rotated token only in answer to registering.
            if listening { UIApplication.shared.registerForRemoteNotifications() }
        case .message:
            PNPushHub.shared.messages.setListening(listening)
        }
    }
}
