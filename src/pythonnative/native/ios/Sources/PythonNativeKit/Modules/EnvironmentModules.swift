import UIKit

/// `Keyboard`: dismissal and visibility over `PNKeyboardObserver`, which
/// emits `change` `{"height", "visible", "duration_ms"}` on every show,
/// hide, and frame change.
public final class KeyboardModule: KeyboardImplementation {
    public static let name = "Keyboard"

    public init() {
        PNKeyboardObserver.shared.start()
    }

    public func dismiss() throws {
        PNKeyboardObserver.shared.dismiss()
    }

    public func is_visible() throws -> Bool {
        PNKeyboardObserver.shared.isVisible
    }
}

/// `AccessibilityInfo`: VoiceOver and Reduce Motion state, announcements,
/// and focus. Emits `change` `{"screen_reader", "reduce_motion"}` when
/// either setting flips.
public final class AccessibilityInfoModule: AccessibilityInfoImplementation {
    public static let name = "AccessibilityInfo"
    private static var observers: [NSObjectProtocol] = []

    public init() {
        AccessibilityInfoModule.startObserving()
    }

    public func is_screen_reader_enabled() throws -> Bool {
        UIAccessibility.isVoiceOverRunning
    }

    public func is_reduce_motion_enabled() throws -> Bool {
        UIAccessibility.isReduceMotionEnabled
    }

    public func announce(message: String) throws {
        UIAccessibility.post(notification: .announcement, argument: message)
    }

    public func set_accessibility_focus(tag: Int64) throws {
        guard let view = PNViewRegistry.shared.view(for: tag) else {
            throw NSError(domain: "AccessibilityInfo", code: 1, userInfo: [NSLocalizedDescriptionKey: "no view with tag \(tag)"])
        }
        UIAccessibility.post(notification: .layoutChanged, argument: view)
    }

    /// The `change` payload.
    public static func snapshot() -> [String: Any] {
        ["screen_reader": UIAccessibility.isVoiceOverRunning, "reduce_motion": UIAccessibility.isReduceMotionEnabled]
    }

    static func startObserving() {
        guard observers.isEmpty else { return }
        let center = NotificationCenter.default
        for name in [UIAccessibility.voiceOverStatusDidChangeNotification, UIAccessibility.reduceMotionStatusDidChangeNotification] {
            observers.append(center.addObserver(forName: name, object: nil, queue: .main) { _ in
                AccessibilityInfoModule.dispatch()
            })
        }
    }

    /// Emit the current state as a `change` event.
    public static func dispatch() {
        PNModuleEvents.emitTyped(AccessibilityInfoEvents.change, snapshot())
    }
}

/// `Localization`: the user's preferred locales and time zone. Emits
/// `change` `{"locales", "timezone"}` when either changes.
public final class LocalizationModule: LocalizationImplementation {
    public static let name = "Localization"
    private static var observers: [NSObjectProtocol] = []

    public init() {
        LocalizationModule.startObserving()
    }

    public func get_locales() throws -> [[String: PNJSONValue]] {
        try LocalizationModule.locales().map { try PNValues.decode([String: PNJSONValue].self, $0) }
    }

    public func get_timezone() throws -> String {
        TimeZone.current.identifier
    }

    /// One `{"language_tag", "language_code", "region_code", "is_rtl"}`
    /// record per entry of `Locale.preferredLanguages` (BCP 47 tags).
    public static func locales(_ preferred: [String] = Locale.preferredLanguages) -> [[String: Any]] {
        let tags = preferred.isEmpty ? [DeviceModule.languageTag(Locale.current)] : preferred
        return tags.map { tag in
            let locale = Locale(identifier: tag)
            let language = locale.languageCode ?? String(tag.split(separator: "-").first ?? Substring(tag))
            let region = locale.regionCode ?? ""
            return [
                "language_tag": DeviceModule.languageTag(locale),
                "language_code": language,
                "region_code": region,
                "is_rtl": Locale.characterDirection(forLanguage: language) == .rightToLeft,
            ]
        }
    }

    /// The `change` payload.
    public static func snapshot() -> [String: Any] {
        ["locales": locales(), "timezone": TimeZone.current.identifier]
    }

    static func startObserving() {
        guard observers.isEmpty else { return }
        let center = NotificationCenter.default
        for name in [NSLocale.currentLocaleDidChangeNotification, Notification.Name.NSSystemTimeZoneDidChange] {
            observers.append(center.addObserver(forName: name, object: nil, queue: .main) { _ in
                LocalizationModule.dispatch()
            })
        }
    }

    /// Emit the current locales and time zone as a `change` event.
    public static func dispatch() {
        PNModuleEvents.emitTyped(LocalizationEvents.change, snapshot())
    }
}

extension PNModuleEvents {
    /// Route a `[String: Any]` payload through a generated typed emitter.
    static func emitTyped(_ emitter: ([String: PNJSONValue]) -> Void, _ payload: [String: Any]) {
        guard let typed = try? PNValues.decode([String: PNJSONValue].self, payload) else {
            PNLog.rateLimited(PNLog.modules, key: "typed-event", "module event payload isn't JSON: \(payload)")
            return
        }
        emitter(typed)
    }
}
