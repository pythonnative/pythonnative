import CoreMotion
import Foundation

/// Registers `Sensors` and owns the `motion` permission.
public enum SensorsPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(SensorsModuleAdapter<SensorsModule>.self)
        PNPermissions.register("motion", PNMotionPermission())
    }
}

private func permissionStatus(_ status: CMAuthorizationStatus) -> String {
    switch status {
    case .authorized: return "granted"
    case .denied, .restricted: return "blocked"
    case .notDetermined: return "undetermined"
    @unknown default: return "undetermined"
    }
}

/// Motion and Fitness access, which `CMAltimeter` is the only reader here to need.
private final class PNMotionPermission: PNPermissionProvider {
    private var altimeter: CMAltimeter?

    func check(_ done: @escaping (String) -> Void) {
        done(permissionStatus(CMAltimeter.authorizationStatus()))
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        guard CMAltimeter.authorizationStatus() == .notDetermined, CMAltimeter.isRelativeAltitudeAvailable() else {
            check(done)
            return nil
        }
        // There's no request API: starting updates is what prompts.
        let altimeter = CMAltimeter()
        self.altimeter = altimeter
        altimeter.startRelativeAltitudeUpdates(to: .main) { [weak self] _, _ in
            guard let self = self, let running = self.altimeter else { return }
            running.stopRelativeAltitudeUpdates()
            self.altimeter = nil
            self.check(done)
        }
        return { [weak self] in
            self?.altimeter?.stopRelativeAltitudeUpdates()
            self?.altimeter = nil
        }
    }
}

/// `Sensors`: CoreMotion's readings, in the units and signs the Python facade promises.
public final class SensorsModule: SensorsImplementation {
    public init() {}

    public func is_available(sensor: PNSensorsIsAvailableSensor) throws -> Bool {
        PNMotionHub.shared.isAvailable(sensor)
    }

    public func start(hz: Double, sensor: PNSensorsIsAvailableSensor, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        guard PNMotionHub.shared.isAvailable(sensor) else {
            completion(.failure(NSError(domain: "unavailable", code: 1, userInfo: [NSLocalizedDescriptionKey: "This device has no \(sensor.rawValue)"])))
            return nil
        }
        return PNMotionHub.shared.subscribe(sensor, hz: hz, completion: completion)
    }

    public func stop(id: Int64) throws {
        PNMotionHub.shared.unsubscribe(id)
    }
}

/// Apple asks for one `CMMotionManager` per app, and each sensor on it takes
/// one handler, so every subscription shares this one and thins to its own rate.
private final class PNMotionHub {
    static let shared = PNMotionHub()

    private struct Subscriber {
        let sensor: PNSensorsIsAvailableSensor
        let hz: Double
        var last: TimeInterval = 0
        var settle: ((Result<Int64, Error>) -> Void)?
    }

    /// CoreMotion reports multiples of g with gravity pointing down, so a device
    /// flat on a table reads z = -1. The facade promises Android's convention, +9.81.
    private static let accelerationScale = -9.80665
    /// `CMAltitudeData.pressure` is in kilopascals.
    private static let hectopascalsPerKilopascal = 10.0

    private let motion = CMMotionManager()
    private var altimeter: CMAltimeter?
    private var subscribers: [Int64: Subscriber] = [:]
    private var running: Set<String> = []
    private var nextId: Int64 = 1
    /// Sensor timestamps count from boot; this turns them into Unix seconds.
    private let bootTime = Date().timeIntervalSince1970 - ProcessInfo.processInfo.systemUptime

    func isAvailable(_ sensor: PNSensorsIsAvailableSensor) -> Bool {
        switch sensor {
        case .accelerometer: return motion.isAccelerometerAvailable
        case .gyroscope: return motion.isGyroAvailable
        case .magnetometer: return motion.isMagnetometerAvailable
        case .barometer: return CMAltimeter.isRelativeAltitudeAvailable()
        }
    }

    func subscribe(_ sensor: PNSensorsIsAvailableSensor, hz: Double, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)? {
        let id = nextId
        nextId += 1
        subscribers[id] = Subscriber(sensor: sensor, hz: hz)
        if sensor == .barometer {
            // Whether the user allowed it is known only once the altimeter
            // answers, so the first reading or error settles the call.
            let status = CMAltimeter.authorizationStatus()
            if status == .denied || status == .restricted {
                subscribers.removeValue(forKey: id)
                completion(.failure(Self.deniedError()))
                return nil
            }
            subscribers[id]?.settle = completion
            startBarometer()
            return { [weak self] in self?.unsubscribe(id) }
        }
        refresh(sensor)
        completion(.success(id))
        return nil
    }

    func unsubscribe(_ id: Int64) {
        guard let removed = subscribers.removeValue(forKey: id) else { return }
        if removed.sensor == .barometer {
            if !subscribers.values.contains(where: { $0.sensor == .barometer }) {
                altimeter?.stopRelativeAltitudeUpdates()
                altimeter = nil
            }
        } else {
            refresh(removed.sensor)
        }
    }

    private static func deniedError() -> NSError {
        NSError(domain: "permission_denied", code: 1, userInfo: [NSLocalizedDescriptionKey: "Motion and Fitness permission was denied"])
    }

    /// Start, stop, or retime a CoreMotion sensor to suit its current subscribers.
    private func refresh(_ sensor: PNSensorsIsAvailableSensor) {
        let rates = subscribers.values.filter { $0.sensor == sensor }.map { $0.hz }
        guard let fastest = rates.max() else {
            switch sensor {
            case .accelerometer: motion.stopAccelerometerUpdates()
            case .gyroscope: motion.stopGyroUpdates()
            case .magnetometer: motion.stopMagnetometerUpdates()
            case .barometer: break
            }
            running.remove(sensor.rawValue)
            return
        }
        let interval = 1.0 / fastest
        let isRunning = running.contains(sensor.rawValue)
        switch sensor {
        case .accelerometer:
            motion.accelerometerUpdateInterval = interval
            if !isRunning {
                motion.startAccelerometerUpdates(to: .main) { [weak self] data, _ in
                    guard let self = self, let data = data else { return }
                    let scale = Self.accelerationScale
                    self.deliver(.accelerometer, at: data.timestamp, [
                        "x": data.acceleration.x * scale, "y": data.acceleration.y * scale, "z": data.acceleration.z * scale,
                    ])
                }
            }
        case .gyroscope:
            motion.gyroUpdateInterval = interval
            if !isRunning {
                motion.startGyroUpdates(to: .main) { [weak self] data, _ in
                    guard let self = self, let data = data else { return }
                    self.deliver(.gyroscope, at: data.timestamp, ["x": data.rotationRate.x, "y": data.rotationRate.y, "z": data.rotationRate.z])
                }
            }
        case .magnetometer:
            motion.magnetometerUpdateInterval = interval
            if !isRunning {
                motion.startMagnetometerUpdates(to: .main) { [weak self] data, _ in
                    guard let self = self, let data = data else { return }
                    self.deliver(.magnetometer, at: data.timestamp, ["x": data.magneticField.x, "y": data.magneticField.y, "z": data.magneticField.z])
                }
            }
        case .barometer:
            return
        }
        running.insert(sensor.rawValue)
    }

    private func startBarometer() {
        if altimeter != nil { return }
        let altimeter = CMAltimeter()
        self.altimeter = altimeter
        altimeter.startRelativeAltitudeUpdates(to: .main) { [weak self] data, error in
            guard let self = self else { return }
            if let error = error {
                self.failBarometer(error)
            } else if let data = data {
                self.settleBarometer()
                self.deliver(.barometer, at: data.timestamp, ["hpa": data.pressure.doubleValue * Self.hectopascalsPerKilopascal])
            }
        }
    }

    private func settleBarometer() {
        for (id, subscriber) in subscribers where subscriber.settle != nil {
            subscribers[id]?.settle = nil
            subscriber.settle?(.success(id))
        }
    }

    private func failBarometer(_ error: Error) {
        let nsError = error as NSError
        let denied = nsError.domain == CMErrorDomain && nsError.code == Int(CMErrorMotionActivityNotAuthorized.rawValue)
        let failure: Error = denied ? Self.deniedError() : error
        for (id, subscriber) in subscribers where subscriber.sensor == .barometer {
            subscribers.removeValue(forKey: id)
            subscriber.settle?(.failure(failure))
        }
        altimeter?.stopRelativeAltitudeUpdates()
        altimeter = nil
        PNLog.modules.error("altimeter failed: \(error.localizedDescription)")
    }

    private func deliver(_ sensor: PNSensorsIsAvailableSensor, at timestamp: TimeInterval, _ reading: [String: Double]) {
        var value = reading
        value["timestamp"] = bootTime + timestamp
        for (id, subscriber) in subscribers where subscriber.sensor == sensor {
            // A little slack, so a jittery sample doesn't halve a matching rate.
            if timestamp - subscriber.last < 0.8 / subscriber.hz { continue }
            subscribers[id]?.last = timestamp
            PNModuleEvents.emit(module: "Sensors", event: "reading", payload: ["id": id, "value": value])
        }
    }
}
