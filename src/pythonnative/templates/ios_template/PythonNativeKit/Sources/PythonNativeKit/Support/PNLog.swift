import Foundation
import os.log

/// A thin `os_log` wrapper with the subset of the `Logger` API the kit
/// uses. `Logger` itself is iOS 14+, and apps may set a deployment target
/// as low as iOS 13, so this keeps the kit buildable at the app's minimum.
struct PNLogger {
    let log: OSLog

    init(category: String) {
        log = OSLog(subsystem: "com.pythonnative", category: category)
    }

    func error(_ message: String) { os_log("%{public}@", log: log, type: .error, message) }
    func warning(_ message: String) { os_log("%{public}@", log: log, type: .default, message) }
    func info(_ message: String) { os_log("%{public}@", log: log, type: .info, message) }
    func debug(_ message: String) { os_log("%{public}@", log: log, type: .debug, message) }
}

/// Loggers for every PythonNativeKit subsystem, plus a rate limiter for
/// messages that could otherwise fire at frame rate.
enum PNLog {
    static let bridge = PNLogger(category: "bridge")
    static let components = PNLogger(category: "components")
    static let gestures = PNLogger(category: "gestures")
    static let animation = PNLogger(category: "animation")
    static let modules = PNLogger(category: "modules")
    static let screens = PNLogger(category: "screens")

    private static var lastEmitted: [String: TimeInterval] = [:]
    private static var onceKeys: Set<String> = []

    /// Log `message` at most once per `interval` seconds for a given `key`.
    static func rateLimited(_ logger: PNLogger, key: String, interval: TimeInterval = 1.0, _ message: @autoclosure () -> String) {
        let now = Date().timeIntervalSinceReferenceDate
        if let last = lastEmitted[key], now - last < interval { return }
        lastEmitted[key] = now
        logger.error(message())
    }

    /// Log `message` exactly once per process for a given `key`.
    static func once(_ logger: PNLogger, key: String, _ message: @autoclosure () -> String) {
        if onceKeys.contains(key) { return }
        onceKeys.insert(key)
        logger.warning(message())
    }
}
