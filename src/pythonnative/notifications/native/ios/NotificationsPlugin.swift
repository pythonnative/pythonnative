import UIKit
import UserNotifications

/// Registers `Notifications`, installs the notification center delegate from
/// a lifecycle hook, and owns the `notifications` permission.
public enum NotificationsPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(NotificationsModuleAdapter<NotificationsModule>.self)
        registry.registerLifecycleHook(PNNotificationsHook())
        PNPermissions.register("notifications", PNNotificationPermission())
    }
}

/// The delegate has to be set before `didFinishLaunching` returns, or the tap
/// that launched the app is lost.
private final class PNNotificationsHook: PNAppLifecycleHook {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {
        PNNotificationCenter.shared.install()
    }
}

private final class PNNotificationPermission: PNPermissionProvider {
    func check(_ done: @escaping (String) -> Void) {
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
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
            DispatchQueue.main.async { done(granted ? "granted" : "blocked") }
        }
        return nil
    }
}

/// One module event, held back until Python subscribes. The bridge's mailbox
/// only waits for Python to start, and an app subscribes later than that, from
/// a screen's effect. Touched only on the main thread.
final class PNBufferedEvent {
    private static let limit = 64

    private let module: String
    private let event: String
    private var pending: [Any] = []
    private(set) var isListening = false

    init(module: String, event: String) {
        self.module = module
        self.event = event
    }

    func send(_ payload: Any) {
        if isListening {
            PNModuleEvents.emit(module: module, event: event, payload: payload)
            return
        }
        if pending.count == Self.limit { pending.removeFirst() }
        pending.append(payload)
    }

    func setListening(_ listening: Bool) {
        isListening = listening
        guard listening else { return }
        let replay = pending
        pending = []
        for payload in replay { PNModuleEvents.emit(module: module, event: event, payload: payload) }
    }

    func dropOldest() {
        if !pending.isEmpty { pending.removeFirst() }
    }
}

/// The `UNUserNotificationCenter` delegate: presents notifications in the
/// foreground and turns arrivals and taps into module events.
final class PNNotificationCenter: NSObject, UNUserNotificationCenterDelegate {
    static let shared = PNNotificationCenter()
    static let dataKey = "pn_data"

    let received = PNBufferedEvent(module: "Notifications", event: "received")
    let responses = PNBufferedEvent(module: "Notifications", event: "response")

    /// `Push` hears about foreground pushes through this, as a process has
    /// only one delegate.
    var onForegroundPush: (([AnyHashable: Any]) -> Void)?

    private(set) var launchResponse: [String: PNJSONValue]?
    private var launchBuffered = false
    private var launching = true
    private var activation: NSObjectProtocol?

    func install() {
        UNUserNotificationCenter.current().delegate = self
        // A launching tap can arrive on either side of the first activation,
        // depending on the iOS version, so it stays "launching" a moment past it.
        activation = NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self = self, let activation = self.activation else { return }
            NotificationCenter.default.removeObserver(activation)
            self.activation = nil
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.launching = false }
        }
    }

    /// Reading the launching tap claims it, so it isn't replayed to `on_response` too.
    func readLaunchResponse() -> [String: PNJSONValue]? {
        if launchBuffered {
            responses.dropOldest()
            launchBuffered = false
        }
        return launchResponse
    }

    func setListening(_ event: PNNotificationsSetListeningEvent, _ listening: Bool) {
        switch event {
        case .received: received.setListening(listening)
        case .response:
            if listening { launchBuffered = false }
            responses.setListening(listening)
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        PNMain.run { [self] in
            received.send(PNValues.encode(Self.payload(notification)))
            if notification.request.trigger is UNPushNotificationTrigger {
                onForegroundPush?(notification.request.content.userInfo)
            }
        }
        if #available(iOS 14.0, *) {
            completionHandler([.banner, .list, .sound, .badge])
        } else {
            completionHandler([.alert, .sound, .badge])
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        PNMain.run { [self] in
            var payload = Self.payload(response.notification)
            payload["action"] = .string(Self.action(response.actionIdentifier))
            if launching && launchResponse == nil {
                launchResponse = payload
                launchBuffered = !responses.isListening
            }
            responses.send(PNValues.encode(payload))
        }
        completionHandler()
    }

    private static func action(_ identifier: String) -> String {
        switch identifier {
        case UNNotificationDefaultActionIdentifier: return "default"
        case UNNotificationDismissActionIdentifier: return "dismiss"
        default: return identifier
        }
    }

    private static func payload(_ notification: UNNotification) -> [String: PNJSONValue] {
        let content = notification.request.content
        return [
            "identifier": .string(notification.request.identifier),
            "title": .string(content.title),
            "body": .string(content.body),
            "data": .object(data(content.userInfo)),
        ]
    }

    /// A local notification's `data`, or a push's keys other than `aps`.
    static func data(_ userInfo: [AnyHashable: Any]) -> [String: PNJSONValue] {
        var fields: [String: Any] = [:]
        if let encoded = userInfo[dataKey] as? String {
            fields = PNJSON.decodeObject(encoded)
        } else {
            for case let (key as String, value) in userInfo where key != "aps" { fields[key] = value }
        }
        return (try? PNValues.decode([String: PNJSONValue].self, fields)) ?? [:]
    }
}

/// `Notifications`: local notifications through `UNUserNotificationCenter`.
public final class NotificationsModule: NotificationsImplementation {
    public init() {}

    public func request_permission(completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            DispatchQueue.main.async {
                if let error = error { completion(.failure(error)) } else { completion(.success(granted)) }
            }
        }
        return nil
    }

    public func schedule(badge: Int64?, body: String, data: [String: PNJSONValue]?, delay_seconds: Double, identifier: String, sound: Bool, title: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        let center = UNUserNotificationCenter.current()
        // The center accepts a request without permission and silently drops it.
        center.getNotificationSettings { settings in
            switch settings.authorizationStatus {
            case .denied, .notDetermined:
                DispatchQueue.main.async { completion(.success(false)) }
                return
            default:
                break
            }
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = sound ? .default : nil
            content.badge = badge.map { NSNumber(value: $0) }
            if let data = data, let encoded = try? JSONEncoder().encode(data) {
                // JSON, because `userInfo` can't hold every JSON value (a null, for one).
                content.userInfo = [PNNotificationCenter.dataKey: String(decoding: encoded, as: UTF8.self)]
            }
            let trigger = delay_seconds > 0 ? UNTimeIntervalNotificationTrigger(timeInterval: delay_seconds, repeats: false) : nil
            center.add(UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)) { error in
                DispatchQueue.main.async {
                    if let error = error { completion(.failure(error)) } else { completion(.success(true)) }
                }
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

    public func cancel_all(completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)? {
        let center = UNUserNotificationCenter.current()
        center.removeAllPendingNotificationRequests()
        center.removeAllDeliveredNotifications()
        completion(.success(()))
        return nil
    }

    public func set_badge(count: Int64, completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)? {
        if #available(iOS 16.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(Int(count)) { error in
                DispatchQueue.main.async {
                    if let error = error { completion(.failure(error)) } else { completion(.success(())) }
                }
            }
        } else {
            UIApplication.shared.applicationIconBadgeNumber = Int(count)
            completion(.success(()))
        }
        return nil
    }

    public func last_response() throws -> [String: PNJSONValue]? {
        PNNotificationCenter.shared.readLaunchResponse()
    }

    public func set_listening(event: PNNotificationsSetListeningEvent, listening: Bool) throws {
        PNNotificationCenter.shared.setListening(event, listening)
    }
}
