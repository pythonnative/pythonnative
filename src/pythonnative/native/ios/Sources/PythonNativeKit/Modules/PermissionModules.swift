import AVFoundation
import Contacts
import CoreLocation
import LocalAuthentication
import Photos
import UIKit
import UserNotifications

/// `Permissions`: `check` and `request` (async).
///
/// Permission names are the `[permissions]` keys from pythonnative.toml
/// (`camera`, `microphone`, `photo_library`, `location_when_in_use`,
/// `contacts`, `notifications`). The Python facade validates them before
/// the call reaches this module, so an unknown name here is a bug rather
/// than user input, and is rejected rather than answered.
public final class PermissionsModule: PermissionsImplementation {

    /// Every accepted permission name, in the `[permissions]` vocabulary.
    public static let names: Set<String> = [
        "camera", "microphone", "photo_library", "location_when_in_use", "contacts", "notifications",
    ]

    private var locationRequesters: [UUID: PNLocationPermissionRequester] = [:]

    public init() {}

    public func check(permission: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)? {
        guard Self.names.contains(permission) else {
            completion(.failure(NativeDecodeError.invalid("Unknown permission: " + permission))); return nil
        }
        var cancelled = false
        check(permission) { if !cancelled { completion(.success($0)) } }
        return { cancelled = true }
    }

    public func request(permission: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)? {
        guard Self.names.contains(permission) else {
            completion(.failure(NativeDecodeError.invalid("Unknown permission: " + permission))); return nil
        }
        var cancelled = false
        let cancel = request(permission) { if !cancelled { completion(.success($0)) } }
        // System permission prompts can't be dismissed by an app. Detach the waiter.
        return { cancelled = true; cancel?() }
    }

    // MARK: - Check

    private func check(_ permission: String, _ done: @escaping (String) -> Void) {
        switch permission {
        case "camera":
            done(PermissionsModule.status(AVCaptureDevice.authorizationStatus(for: .video)))
        case "microphone":
            done(PermissionsModule.status(AVCaptureDevice.authorizationStatus(for: .audio)))
        case "photo_library":
            done(PermissionsModule.status(PHPhotoLibrary.pnReadWriteAuthorizationStatus()))
        case "contacts":
            done(PermissionsModule.status(CNContactStore.authorizationStatus(for: .contacts)))
        case "location_when_in_use":
            done(PermissionsModule.status(CLLocationManager().pnAuthorizationStatus))
        case "notifications":
            UNUserNotificationCenter.current().getNotificationSettings { settings in
                let status: String
                switch settings.authorizationStatus {
                case .authorized, .provisional, .ephemeral: status = "granted"
                case .denied: status = "blocked"
                case .notDetermined: status = "undetermined"
                @unknown default: status = "undetermined"
                }
                DispatchQueue.main.async { done(status) }
            }
        default:
            done("undetermined")
        }
    }

    // MARK: - Request

    private func request(_ permission: String, _ done: @escaping (String) -> Void) -> (() -> Void)? {
        let finish: (String) -> Void = { status in DispatchQueue.main.async { done(status) } }
        switch permission {
        case "camera":
            AVCaptureDevice.requestAccess(for: .video) { finish($0 ? "granted" : "blocked") }
        case "microphone":
            AVCaptureDevice.requestAccess(for: .audio) { finish($0 ? "granted" : "blocked") }
        case "photo_library":
            PHPhotoLibrary.pnRequestReadWriteAuthorization { finish(PermissionsModule.status($0)) }
        case "contacts":
            CNContactStore().requestAccess(for: .contacts) { granted, _ in finish(granted ? "granted" : "blocked") }
        case "notifications":
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
                finish(granted ? "granted" : "blocked")
            }
        case "location_when_in_use":
            let id = UUID()
            let requester = PNLocationPermissionRequester { [weak self] status in
                self?.locationRequesters.removeValue(forKey: id)
                finish(status)
            }
            locationRequesters[id] = requester
            requester.start()
            return { [weak self] in self?.locationRequesters.removeValue(forKey: id)?.cancel() }
        default:
            done("undetermined")
        }
        return nil
    }

    // MARK: - Status mapping

    static func status(_ s: AVAuthorizationStatus) -> String {
        switch s {
        case .authorized: return "granted"
        case .denied: return "blocked"
        case .restricted: return "blocked"
        case .notDetermined: return "undetermined"
        @unknown default: return "undetermined"
        }
    }

    static func status(_ s: PHAuthorizationStatus) -> String {
        switch s {
        case .authorized, .limited: return "granted"
        case .denied, .restricted: return "blocked"
        case .notDetermined: return "undetermined"
        @unknown default: return "undetermined"
        }
    }

    static func status(_ s: CNAuthorizationStatus) -> String {
        switch s {
        case .authorized: return "granted"
        case .denied, .restricted: return "blocked"
        case .notDetermined: return "undetermined"
        // `.limited` (iOS 18) and future cases still permit access.
        default: return "granted"
        }
    }

    static func status(_ s: CLAuthorizationStatus) -> String {
        switch s {
        case .authorizedAlways, .authorizedWhenInUse: return "granted"
        case .denied, .restricted: return "blocked"
        case .notDetermined: return "undetermined"
        @unknown default: return "undetermined"
        }
    }
}

/// One-shot when-in-use authorization request.
final class PNLocationPermissionRequester: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let done: (String) -> Void
    private var finished = false

    init(done: @escaping (String) -> Void) {
        self.done = done
        super.init()
        manager.delegate = self
    }

    func start() {
        let current = manager.pnAuthorizationStatus
        if current != .notDetermined {
            finish(PermissionsModule.status(current))
            return
        }
        manager.requestWhenInUseAuthorization()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.pnAuthorizationStatus
        if status != .notDetermined {
            finish(PermissionsModule.status(status))
        }
    }

    private func finish(_ status: String) {
        if finished { return }
        cancel()
        done(status)
    }

    func cancel() {
        finished = true
        manager.delegate = nil
    }
}

/// `Notifications`: local notifications plus APNs registration.
public final class NotificationsModule: NotificationsImplementation {
    private static var tokenWaiters: [UUID: (Result<String?, Error>) -> Void] = [:]
    public init() {}

    public func request_permission(completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            DispatchQueue.main.async {
                if let error = error { completion(.failure(error)) } else { completion(.success(granted)) }
            }
        }
        return nil
    }

    public func schedule(title: String, body: String, delay_seconds: Double, identifier: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        guard delay_seconds >= 0 else {
            completion(.failure(NativeDecodeError.invalid("delay_seconds must be nonnegative"))); return nil
        }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(0.1, delay_seconds), repeats: false)
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)) { error in
            DispatchQueue.main.async {
                if let error = error { completion(.failure(error)) } else { completion(.success(true)) }
            }
        }
        return nil
    }

    public func cancel(identifier: String, completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)? {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [identifier])
        center.removeDeliveredNotifications(withIdentifiers: [identifier])
        completion(.success(()))
        return nil
    }

    public func get_device_token(completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        let id = UUID()
        Self.tokenWaiters[id] = completion
        UIApplication.shared.registerForRemoteNotifications()
        return { Self.tokenWaiters.removeValue(forKey: id) }
    }

    public static func deliverToken(_ token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        let waiters = tokenWaiters; tokenWaiters = [:]
        for waiter in waiters.values { waiter(.success(hex)) }
    }

    public static func deliverError(_ error: Error) {
        let waiters = tokenWaiters; tokenWaiters = [:]
        for waiter in waiters.values { waiter(.failure(error)) }
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
