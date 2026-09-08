import Network
import UIKit

/// `AppState`: foreground / background transitions.
///
/// The scene delegate calls `AppStateModule.dispatch(_:)`; the module
/// emits `change` with the state string (`"active"`, `"inactive"`,
/// `"background"`) as the payload, which is what the Python facade reads.
public final class AppStateModule: PNNativeModule {
    public static let name = "AppState"
    public private(set) static var current = "active"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "current_state":
            promise.resolve(AppStateModule.current)
        default:
            promise.reject("AppState has no method '\(method)'", code: "unknown_method")
        }
    }

    /// Record and publish a lifecycle transition.
    public static func dispatch(_ state: String) {
        guard ["active", "inactive", "background"].contains(state), state != current else { return }
        current = state
        PNBridge.shared.whenCallbackRegistered {
            PNBridge.shared.callPython(kind: "module", tag: 0, name: name, payload: PNJSON.encode(["event": "change", "payload": state]))
        }
    }
}

/// `Battery`: level / state getters plus `change` events while monitoring.
public final class BatteryModule: PNNativeModule {
    public static let name = "Battery"
    private static var observers: [NSObjectProtocol] = []

    public init() {
        BatteryModule.startMonitoring()
    }

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "get_level":
            promise.resolve(Double(UIDevice.current.batteryLevel))
        case "get_state":
            promise.resolve(BatteryModule.stateName())
        default:
            promise.reject("Battery has no method '\(method)'", code: "unknown_method")
        }
    }

    /// Enable battery monitoring and forward UIDevice notifications.
    public static func startMonitoring() {
        guard observers.isEmpty else { return }
        UIDevice.current.isBatteryMonitoringEnabled = true
        let center = NotificationCenter.default
        for notification in [UIDevice.batteryLevelDidChangeNotification, UIDevice.batteryStateDidChangeNotification] {
            observers.append(center.addObserver(forName: notification, object: nil, queue: .main) { _ in
                BatteryModule.dispatch()
            })
        }
    }

    /// Emit the current `{"level", "state"}` snapshot.
    public static func dispatch() {
        PNModuleEvents.emit(module: name, event: "change", payload: [
            "level": Double(UIDevice.current.batteryLevel),
            "state": stateName(),
        ])
    }

    static func stateName() -> String {
        switch UIDevice.current.batteryState {
        case .unplugged: return "unplugged"
        case .charging: return "charging"
        case .full: return "full"
        default: return "unknown"
        }
    }
}

/// `NetInfo`: connectivity snapshots from `NWPathMonitor`.
public final class NetInfoModule: PNNativeModule {
    public static let name = "NetInfo"

    private let monitor = NWPathMonitor()
    private var last: [String: Any]?

    public init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let snapshot = NetInfoModule.snapshot(path)
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let last = self.last, NSDictionary(dictionary: last).isEqual(to: snapshot) { return }
                self.last = snapshot
                PNModuleEvents.emit(module: NetInfoModule.name, event: "change", payload: snapshot)
            }
        }
        monitor.start(queue: DispatchQueue(label: "com.pythonnative.netinfo"))
    }

    deinit {
        monitor.cancel()
    }

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "fetch":
            let snapshot = NetInfoModule.snapshot(monitor.currentPath)
            last = snapshot
            promise.resolve(snapshot)
        default:
            promise.reject("NetInfo has no method '\(method)'", code: "unknown_method")
        }
    }

    static func snapshot(_ path: NWPath) -> [String: Any] {
        let connected = path.status == .satisfied
        let type: String
        if !connected {
            type = "none"
        } else if path.usesInterfaceType(.wifi) {
            type = "wifi"
        } else if path.usesInterfaceType(.cellular) {
            type = "cellular"
        } else if path.usesInterfaceType(.wiredEthernet) {
            type = "ethernet"
        } else {
            type = "unknown"
        }
        return ["is_connected": connected, "type": type, "is_internet_reachable": connected]
    }
}

/// `Linking`: open URLs and deliver inbound deep links.
///
/// `deliver(url:)` buffers until Python's callback is registered so a
/// cold-start deep link reaches `Linking.get_initial_url()`.
public final class LinkingModule: PNNativeModule {
    public static let name = "Linking"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "open_url":
            guard let url = PNProps.string(args["url"]).flatMap({ URL(string: $0) }) else { return promise.resolve(false) }
            let app = UIApplication.shared
            guard app.canOpenURL(url) || url.scheme?.hasPrefix("http") == true else { return promise.resolve(false) }
            app.open(url, options: [:]) { _ in }
            promise.resolve(true)
        case "can_open_url":
            guard let url = PNProps.string(args["url"]).flatMap({ URL(string: $0) }) else { return promise.resolve(false) }
            promise.resolve(UIApplication.shared.canOpenURL(url))
        case "open_settings":
            guard let url = URL(string: UIApplication.openSettingsURLString) else { return promise.resolve(false) }
            UIApplication.shared.open(url, options: [:]) { _ in }
            promise.resolve(true)
        default:
            promise.reject("Linking has no method '\(method)'", code: "unknown_method")
        }
    }

    /// Forward an inbound URL as a `url` event (payload: the URL string).
    public static func deliver(url: String) {
        PNBridge.shared.whenCallbackRegistered {
            PNMain.run {
                PNBridge.shared.callPython(kind: "module", tag: 0, name: name, payload: PNJSON.encode(["event": "url", "payload": url]))
            }
        }
    }
}
