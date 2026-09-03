import Foundation
import os

/// Loggers for every PythonNativeKit subsystem, plus a rate limiter for
/// messages that could otherwise fire at frame rate.
enum PNLog {
    static let bridge = Logger(subsystem: "com.pythonnative", category: "bridge")
    static let components = Logger(subsystem: "com.pythonnative", category: "components")
    static let gestures = Logger(subsystem: "com.pythonnative", category: "gestures")
    static let animation = Logger(subsystem: "com.pythonnative", category: "animation")
    static let modules = Logger(subsystem: "com.pythonnative", category: "modules")
    static let screens = Logger(subsystem: "com.pythonnative", category: "screens")

    private static var lastEmitted: [String: TimeInterval] = [:]
    private static var onceKeys: Set<String> = []

    /// Log `message` at most once per `interval` seconds for a given `key`.
    static func rateLimited(_ logger: Logger, key: String, interval: TimeInterval = 1.0, _ message: @autoclosure () -> String) {
        let now = Date().timeIntervalSinceReferenceDate
        if let last = lastEmitted[key], now - last < interval { return }
        lastEmitted[key] = now
        let text = message()
        logger.error("\(text, privacy: .public)")
    }

    /// Log `message` exactly once per process for a given `key`.
    static func once(_ logger: Logger, key: String, _ message: @autoclosure () -> String) {
        if onceKeys.contains(key) { return }
        onceKeys.insert(key)
        let text = message()
        logger.warning("\(text, privacy: .public)")
    }
}
