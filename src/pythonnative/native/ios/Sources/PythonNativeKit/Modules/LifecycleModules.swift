import Network
import UIKit

/// `AppState`: foreground / background transitions.
///
/// The scene delegate calls `AppStateModule.dispatch(_:)`; the module
/// emits `change` with the state string (`"active"`, `"inactive"`,
/// `"background"`) as the payload, which is what the Python facade reads.
public final class AppStateModule: AppStateImplementation {
    public static let name = "AppState"
    public private(set) static var current = "active"

    public init() {}

    public func current_state() -> String { Self.current }

    /// Record and publish a lifecycle transition.
    public static func dispatch(_ state: String) {
        guard ["active", "inactive", "background"].contains(state), state != current else { return }
        current = state
        PNBridge.shared.whenCallbackRegistered {
            AppStateEvents.change(state)
        }
    }
}

/// `Battery`: level / state getters plus `change` events while monitoring.
public final class BatteryModule: BatteryImplementation {
    public static let name = "Battery"
    private static var observers: [NSObjectProtocol] = []

    public init() {
        BatteryModule.startMonitoring()
    }

    public func get_level() -> Double { Double(UIDevice.current.batteryLevel) }
    public func get_state() -> String { Self.stateName() }

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
        PNModuleEvents.emitTyped(BatteryEvents.change, [
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
public final class NetInfoModule: NetInfoImplementation {
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
                PNModuleEvents.emitTyped(NetInfoEvents.change, snapshot)
            }
        }
        monitor.start(queue: DispatchQueue(label: "com.pythonnative.netinfo"))
    }

    deinit {
        monitor.cancel()
    }

    public func fetch() throws -> [String: PNJSONValue]? {
        let current = Self.snapshot(monitor.currentPath)
        last = current
        return try current.mapValues { try PNValues.decode(PNJSONValue.self, $0) }
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
public final class LinkingModule: LinkingImplementation {
    public static let name = "Linking"

    public init() {}

    public func open_url(url: String) -> Bool {
        guard let parsed = URL(string: url), UIApplication.shared.canOpenURL(parsed) || parsed.scheme?.hasPrefix("http") == true else { return false }
        UIApplication.shared.open(parsed, options: [:]) { _ in }
        return true
    }
    public func can_open_url(url: String) -> Bool {
        URL(string: url).map { UIApplication.shared.canOpenURL($0) } ?? false
    }
    public func open_settings() -> Bool { open_url(url: UIApplication.openSettingsURLString) }

    /// Forward an inbound URL as a `url` event (payload: the URL string).
    public static func deliver(url: String) {
        PNBridge.shared.whenCallbackRegistered {
            PNMain.run {
                LinkingEvents.url(url)
            }
        }
    }
}
