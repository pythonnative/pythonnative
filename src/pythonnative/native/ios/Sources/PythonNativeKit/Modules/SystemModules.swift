import AudioToolbox
import Security
import UIKit

/// `Device`: static device and app-path information.
public final class DeviceModule: DeviceImplementation {
    public static let name = "Device"

    public init() {}

    public func info() throws -> [String: PNJSONValue] {
        try Self.snapshot().mapValues { try PNValues.decode(PNJSONValue.self, $0) }
    }

    /// The `Device.info()` payload: `platform`, `os_version`, `model`,
    /// `manufacturer`, `is_simulator`, `is_tablet`, `app_name`, `app_version`,
    /// `build_number`, `bundle_id`, `scale`, `font_scale`, `locale` (BCP 47),
    /// plus `app_dir` (the Documents directory) for file storage.
    public static func snapshot() -> [String: Any] {
        let paths = FileManager.default
        let documents = paths.urls(for: .documentDirectory, in: .userDomainMask).first?.path ?? NSHomeDirectory() + "/Documents"
        let info = Bundle.main.infoDictionary ?? [:]
        let appName = (info["CFBundleDisplayName"] as? String) ?? (info["CFBundleName"] as? String) ?? ""
        return [
            "platform": "ios",
            "os_version": UIDevice.current.systemVersion,
            "model": UIDevice.current.model,
            "manufacturer": "Apple",
            "is_simulator": DeviceModule.isSimulator,
            "is_tablet": UIDevice.current.userInterfaceIdiom == .pad,
            "app_name": appName,
            "app_version": (info["CFBundleShortVersionString"] as? String) ?? "",
            "build_number": (info["CFBundleVersion"] as? String) ?? "",
            "bundle_id": Bundle.main.bundleIdentifier ?? "",
            "scale": Double(PNWindow.screenScale()),
            "font_scale": PNWindow.fontScale(),
            "locale": DeviceModule.languageTag(Locale.current),
            "app_dir": documents,
        ]
    }

    /// The locale as a BCP 47 language tag (`en-US`), not a POSIX identifier.
    public static func languageTag(_ locale: Locale) -> String {
        if #available(iOS 16.0, *) {
            return locale.identifier(.bcp47)
        }
        return locale.identifier.replacingOccurrences(of: "_", with: "-")
    }

    static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }
}

/// `Storage`: `AsyncStorage` over the `pn_async_storage` defaults suite.
public final class StorageModule: StorageImplementation {
    static let suiteName = "pn_async_storage"
    private let defaults: UserDefaults
    public init() { defaults = UserDefaults(suiteName: Self.suiteName) ?? .standard }
    public func get(key: String) -> String? { defaults.string(forKey: key) }
    public func set(key: String, value: String) { defaults.set(value, forKey: key) }
    public func delete(key: String) { defaults.removeObject(forKey: key) }
    public func all_keys() -> [String] { (defaults.persistentDomain(forName: Self.suiteName)?.keys.map { $0 } ?? []).sorted() }
    public func clear() { defaults.removePersistentDomain(forName: Self.suiteName) }
}

/// `SecureStore`: Keychain generic passwords under one service.
public final class SecureStoreModule: SecureStoreImplementation {
    public static let name = "SecureStore"
    static let service = "com.pythonnative.securestore"

    public init() {}

    public func clear() throws {
        let status = SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: Self.service] as CFDictionary)
        if status != errSecSuccess && status != errSecItemNotFound { throw NSError(domain: NSOSStatusErrorDomain, code: Int(status)) }
    }
    public func set_item(key: String, value: String) -> Bool { Self.set(key, value) }
    public func get_item(key: String) -> String? { Self.get(key) }
    public func delete_item(key: String) -> Bool { Self.delete(key) }

    private static func query(_ key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }

    static func set(_ key: String, _ value: String) -> Bool {
        let data = Data(value.utf8)
        var q = query(key)
        let status = SecItemCopyMatching(q as CFDictionary, nil)
        if status == errSecSuccess {
            return SecItemUpdate(q as CFDictionary, [kSecValueData as String: data] as CFDictionary) == errSecSuccess
        }
        q[kSecValueData as String] = data
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    static func get(_ key: String) -> String? {
        var q = query(key)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) -> Bool {
        let status = SecItemDelete(query(key) as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

/// `Clipboard`: the general pasteboard.
public final class ClipboardModule: ClipboardImplementation {
    public init() {}
    public func set_string(text: String) { UIPasteboard.general.string = text }
    public func get_string() -> String { UIPasteboard.general.string ?? "" }
}

/// `Share`: `UIActivityViewController`, resolving whether a share completed.
public final class ShareModule: ShareImplementation {
    public static let name = "Share"

    public init() {}

    public func share(message: String?, url: String?, title: String?, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        var items: [Any] = []
        if let message = message, !message.isEmpty { items.append(message) }
        if let url = url.flatMap({ URL(string: $0) }) { items.append(url) }
        guard !items.isEmpty, let top = PNWindow.topViewController() else { completion(.success(false)); return nil }
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        if let title = title { controller.setValue(title, forKey: "subject") }
        controller.completionWithItemsHandler = { _, completed, _, error in
            if let error = error { completion(.failure(error)) } else { completion(.success(completed)) }
        }
        if let popover = controller.popoverPresentationController {
            popover.sourceView = top.view
            popover.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.midY, width: 1, height: 1)
            popover.permittedArrowDirections = []
        }
        top.present(controller, animated: true)
        return { [weak controller] in
            PNMain.run {
                controller?.completionWithItemsHandler = nil
                controller?.dismiss(animated: true)
            }
        }
    }
}

/// `Haptics`: feedback generators plus the legacy vibration sound.
public final class HapticsModule: HapticsImplementation {
    public static let name = "Haptics"

    public init() {}

    public func impact(style: String) {
        let generator = UIImpactFeedbackGenerator(style: Self.impactStyle(style))
        generator.prepare()
        generator.impactOccurred()
    }
    public func notification(type: String) {
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(Self.notificationType(type))
    }
    public func selection() {
        let generator = UISelectionFeedbackGenerator()
        generator.prepare()
        generator.selectionChanged()
    }
    public func vibrate(duration_ms: Int64) {
        guard duration_ms > 0 else { return }
        if duration_ms <= 100 { impact(style: "heavy") }
        else { AudioServicesPlaySystemSound(kSystemSoundID_Vibrate) }
    }
    public func cancel() {}

    static func impactStyle(_ name: String?) -> UIImpactFeedbackGenerator.FeedbackStyle {
        switch name {
        case "light": return .light
        case "heavy": return .heavy
        case "soft": return .soft
        case "rigid": return .rigid
        default: return .medium
        }
    }

    static func notificationType(_ name: String?) -> UINotificationFeedbackGenerator.FeedbackType {
        switch name {
        case "warning": return .warning
        case "error": return .error
        default: return .success
        }
    }
}
