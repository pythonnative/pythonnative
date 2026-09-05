import AVFoundation
import Contacts
import CoreLocation
import LocalAuthentication
import Photos
import UIKit
import UserNotifications

/// `Permissions`: `check` (sync) and `request` (async).
///
/// Permission names are the `[permissions]` keys from pythonnative.toml
/// (`camera`, `microphone`, `photo_library`, `location_when_in_use`,
/// `contacts`, `notifications`). The Python facade validates them before
/// the call reaches this module, so an unknown name here is a bug rather
/// than user input, and is rejected rather than answered.
public final class PermissionsModule: PNNativeModule {
    public static let name = "Permissions"

    /// Every accepted permission name, in the `[permissions]` vocabulary.
    public static let names: Set<String> = [
        "camera", "microphone", "photo_library", "location_when_in_use", "contacts", "notifications",
    ]

    private var locationRequester: PNLocationPermissionRequester?

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        let permission = PNProps.string(args["permission"]) ?? ""
        switch method {
        case "check", "request":
            guard PermissionsModule.names.contains(permission) else {
                return promise.reject("unknown permission '\(permission)'", code: "bad_args")
            }
            if method == "check" {
                check(permission) { promise.resolve($0) }
            } else {
                request(permission) { promise.resolve($0) }
            }
        default:
            promise.reject("Permissions has no method '\(method)'", code: "unknown_method")
        }
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

    private func request(_ permission: String, _ done: @escaping (String) -> Void) {
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
            let requester = PNLocationPermissionRequester { [weak self] status in
                self?.locationRequester = nil
                finish(status)
            }
            locationRequester = requester
            requester.start()
        default:
            done("undetermined")
        }
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
        finished = true
        done(status)
    }
}

/// `Notifications`: local notifications plus APNs registration.
public final class NotificationsModule: PNNativeModule {
    public static let name = "Notifications"

    private static var tokenWaiters: [PNPromise] = []

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        let center = UNUserNotificationCenter.current()
        switch method {
        case "request_permission":
            center.requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
                DispatchQueue.main.async { promise.resolve(granted) }
            }
        case "schedule":
            let content = UNMutableNotificationContent()
            content.title = PNProps.string(args["title"]) ?? ""
            content.body = PNProps.string(args["body"]) ?? ""
            if PNProps.bool(args["sound"]) != false { content.sound = .default }
            if let badge = PNProps.int(args["badge"]) { content.badge = NSNumber(value: badge) }
            let delay = max(0.1, PNProps.double(args["delay_seconds"]) ?? 0)
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: delay, repeats: false)
            let identifier = PNProps.string(args["identifier"]) ?? "default"
            center.add(UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)) { error in
                DispatchQueue.main.async {
                    if let error = error {
                        PNLog.modules.error("schedule failed: \(error.localizedDescription)")
                    }
                    promise.resolve(error == nil)
                }
            }
        case "cancel":
            let identifier = PNProps.string(args["identifier"]) ?? "default"
            center.removePendingNotificationRequests(withIdentifiers: [identifier])
            center.removeDeliveredNotifications(withIdentifiers: [identifier])
            promise.resolve(nil)
        case "get_device_token":
            NotificationsModule.tokenWaiters.append(promise)
            UIApplication.shared.registerForRemoteNotifications()
        default:
            promise.reject("Notifications has no method '\(method)'", code: "unknown_method")
        }
    }

    /// Called by the app delegate with the APNs token.
    public static func deliverToken(_ token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        let waiters = tokenWaiters
        tokenWaiters = []
        for waiter in waiters { waiter.resolve(hex) }
    }

    /// Called by the app delegate when APNs registration fails.
    public static func deliverError(_ error: Error) {
        let waiters = tokenWaiters
        tokenWaiters = []
        for waiter in waiters { waiter.reject(String(describing: error), code: "apns") }
    }
}

/// `Biometrics`: `LAContext` availability and authentication.
public final class BiometricsModule: PNNativeModule {
    public static let name = "Biometrics"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "is_available":
            let context = LAContext()
            var error: NSError?
            promise.resolve(context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error))
        case "authenticate":
            let context = LAContext()
            let reason = PNProps.string(args["reason"]) ?? "Authenticate"
            var error: NSError?
            let policy: LAPolicy = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
                ? .deviceOwnerAuthenticationWithBiometrics : .deviceOwnerAuthentication
            context.evaluatePolicy(policy, localizedReason: reason) { success, _ in
                DispatchQueue.main.async { promise.resolve(success) }
            }
        default:
            promise.reject("Biometrics has no method '\(method)'", code: "unknown_method")
        }
    }
}
