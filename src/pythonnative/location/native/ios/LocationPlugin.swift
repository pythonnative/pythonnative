import CoreLocation
import UIKit

/// Registers `Location` and owns the `location_when_in_use` permission.
public enum LocationPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(LocationModuleAdapter<LocationModule>.self)
        PNPermissions.register("location_when_in_use", PNLocationPermission())
    }
}

extension CLLocationManager {
    /// `authorizationStatus` (instance, iOS 14+) with the class-method
    /// fallback used on iOS 13.
    var pnAuthorizationStatus: CLAuthorizationStatus {
        if #available(iOS 14.0, *) {
            return authorizationStatus
        }
        return CLLocationManager.authorizationStatus()
    }
}

private func permissionStatus(_ status: CLAuthorizationStatus) -> String {
    switch status {
    case .authorizedAlways, .authorizedWhenInUse: return "granted"
    case .denied, .restricted: return "blocked"
    case .notDetermined: return "undetermined"
    @unknown default: return "undetermined"
    }
}

private final class PNLocationPermission: PNPermissionProvider {
    private var requesters: [UUID: PNLocationPermissionRequester] = [:]

    func check(_ done: @escaping (String) -> Void) {
        done(permissionStatus(CLLocationManager().pnAuthorizationStatus))
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        let id = UUID()
        let requester = PNLocationPermissionRequester { [weak self] status in
            self?.requesters.removeValue(forKey: id)
            done(status)
        }
        requesters[id] = requester
        requester.start()
        return { [weak self] in self?.requesters.removeValue(forKey: id)?.cancel() }
    }
}

/// One-shot when-in-use authorization request.
private final class PNLocationPermissionRequester: NSObject, CLLocationManagerDelegate {
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
            finish(permissionStatus(current))
            return
        }
        manager.requestWhenInUseAuthorization()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.pnAuthorizationStatus
        if status != .notDetermined {
            finish(permissionStatus(status))
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

/// `Location`: one-shot `get_current` fix via `CLLocationManager`.
public final class LocationModule: LocationImplementation {
    private var sessions: [UUID: PNLocationSession] = [:]
    private var watchers: [Int64: PNLocationWatcher] = [:]
    private var nextWatcher: Int64 = 1
    public init() {}

    public func start_watching(accuracy: PNLocationGetCurrentAccuracy, distance: Double, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        let id = nextWatcher
        nextWatcher += 1
        let watcher = PNLocationWatcher(id: id, accuracy: accuracy.rawValue, distance: distance) { [weak self] outcome in
            switch outcome {
            case .started: completion(.success(id))
            case .denied:
                self?.watchers.removeValue(forKey: id)
                completion(.failure(NSError(domain: "permission_denied", code: 1, userInfo: [NSLocalizedDescriptionKey: "Location permission was denied"])))
            }
        }
        watchers[id] = watcher
        watcher.start()
        return { [weak self] in self?.watchers.removeValue(forKey: id)?.stop() }
    }

    public func stop_watching(id: Int64) {
        watchers.removeValue(forKey: id)?.stop()
    }

    public func get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: @escaping (Result<[String: Double]?, Error>) -> Void) -> (() -> Void)? {
        let id = UUID()
        let session = PNLocationSession(accuracy: accuracy.rawValue, timeout: timeout) { [weak self] fix in
            self?.sessions.removeValue(forKey: id)
            completion(.success(fix))
        }
        sessions[id] = session
        session.start()
        return { [weak self] in self?.sessions.removeValue(forKey: id)?.cancel() }
    }
}

/// One location request: authorization, a single fix, and a timeout.
final class PNLocationSession: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let done: ([String: Double]?) -> Void
    private let timeout: TimeInterval
    private var finished = false
    private var timer: Timer?

    init(accuracy: String?, timeout: TimeInterval, done: @escaping ([String: Double]?) -> Void) {
        self.done = done
        self.timeout = max(1, timeout)
        super.init()
        manager.delegate = self
        switch accuracy {
        case "high": manager.desiredAccuracy = kCLLocationAccuracyBest
        default: manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        }
    }

    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in
            self?.finish(nil)
        }
        switch manager.pnAuthorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            finish(nil)
        default:
            manager.requestLocation()
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.pnAuthorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            manager.requestLocation()
        case .denied, .restricted:
            finish(nil)
        default:
            break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        var fix: [String: Double] = [
            "latitude": location.coordinate.latitude,
            "longitude": location.coordinate.longitude,
            "accuracy": location.horizontalAccuracy,
            "altitude": location.altitude,
            "timestamp": location.timestamp.timeIntervalSince1970,
        ]
        if location.speed >= 0 { fix["speed"] = location.speed }
        if location.course >= 0 { fix["heading"] = location.course }
        finish(fix)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        PNLog.modules.error("location failed: \(error.localizedDescription)")
        finish(nil)
    }

    func cancel() {
        finished = true
        timer?.invalidate()
        timer = nil
        manager.stopUpdatingLocation()
        manager.delegate = nil
    }

    private func finish(_ fix: [String: Double]?) {
        if finished { return }
        cancel()
        done(fix)
    }
}

/// A continuous subscription: authorization, then `position` events until stopped.
final class PNLocationWatcher: NSObject, CLLocationManagerDelegate {
    enum Outcome { case started, denied }

    private let manager = CLLocationManager()
    private let id: Int64
    private let settled: (Outcome) -> Void
    private var didSettle = false

    init(id: Int64, accuracy: String?, distance: Double, settled: @escaping (Outcome) -> Void) {
        self.id = id
        self.settled = settled
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = accuracy == "high" ? kCLLocationAccuracyBest : kCLLocationAccuracyHundredMeters
        manager.distanceFilter = distance > 0 ? distance : kCLDistanceFilterNone
    }

    func start() {
        switch manager.pnAuthorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .denied, .restricted: settle(.denied)
        default: begin()
        }
    }

    private func begin() {
        settle(.started)
        manager.startUpdatingLocation()
    }

    private func settle(_ outcome: Outcome) {
        if didSettle { return }
        didSettle = true
        settled(outcome)
    }

    func stop() {
        manager.stopUpdatingLocation()
        manager.delegate = nil
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.pnAuthorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse: if !didSettle { begin() }
        case .denied, .restricted: settle(.denied)
        default: break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        for location in locations {
            var fix: [String: Any] = [
                "latitude": location.coordinate.latitude,
                "longitude": location.coordinate.longitude,
                "accuracy": location.horizontalAccuracy,
                "timestamp": location.timestamp.timeIntervalSince1970,
            ]
            if location.verticalAccuracy >= 0 { fix["altitude"] = location.altitude }
            if location.speed >= 0 { fix["speed"] = location.speed }
            if location.course >= 0 { fix["heading"] = location.course }
            PNModuleEvents.emit(module: "Location", event: "position", payload: ["id": id, "value": fix])
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        PNLog.modules.error("location updates failed: \(error.localizedDescription)")
    }
}
