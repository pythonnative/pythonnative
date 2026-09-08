import AudioToolbox
import Security
import UIKit

/// `Device`: static device and app-path information.
public final class DeviceModule: PNNativeModule {
    public static let name = "Device"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "info":
            promise.resolve(DeviceModule.info())
        default:
            promise.reject("Device has no method '\(method)'", code: "unknown_method")
        }
    }

    /// The `Device.info()` payload.
    public static func info() -> [String: Any] {
        let paths = FileManager.default
        let documents = paths.urls(for: .documentDirectory, in: .userDomainMask).first?.path ?? NSHomeDirectory() + "/Documents"
        let caches = paths.urls(for: .cachesDirectory, in: .userDomainMask).first?.path ?? NSTemporaryDirectory()
        return [
            "os": "ios",
            "os_version": UIDevice.current.systemVersion,
            "model": UIDevice.current.model,
            "name": UIDevice.current.name,
            "app_dir": documents,
            "cache_dir": caches,
            "locale": Locale.current.identifier,
            "scale": Double(PNWindow.screenScale()),
            "is_simulator": DeviceModule.isSimulator,
        ]
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
public final class StorageModule: PNNativeModule {
    public static let name = "Storage"
    static let suiteName = "pn_async_storage"

    private let defaults: UserDefaults

    public init() {
        defaults = UserDefaults(suiteName: StorageModule.suiteName) ?? .standard
    }

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "get":
            guard let key = PNProps.string(args["key"]) else { return promise.reject("missing key", code: "bad_args") }
            promise.resolve(defaults.string(forKey: key))
        case "set":
            guard let key = PNProps.string(args["key"]) else { return promise.reject("missing key", code: "bad_args") }
            defaults.set(PNProps.string(args["value"]) ?? "", forKey: key)
            promise.resolve(nil)
        case "delete":
            guard let key = PNProps.string(args["key"]) else { return promise.reject("missing key", code: "bad_args") }
            defaults.removeObject(forKey: key)
            promise.resolve(nil)
        case "all_keys":
            let keys: [String] = defaults.persistentDomain(forName: StorageModule.suiteName)?.keys.map { $0 } ?? []
            promise.resolve(keys.sorted())
        case "clear":
            defaults.removePersistentDomain(forName: StorageModule.suiteName)
            promise.resolve(nil)
        default:
            promise.reject("Storage has no method '\(method)'", code: "unknown_method")
        }
    }
}

/// `SecureStore`: Keychain generic passwords under one service.
public final class SecureStoreModule: PNNativeModule {
    public static let name = "SecureStore"
    static let service = "com.pythonnative.securestore"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        guard let key = PNProps.string(args["key"]) else {
            promise.reject("missing key", code: "bad_args")
            return
        }
        switch method {
        case "set_item":
            promise.resolve(SecureStoreModule.set(key, PNProps.string(args["value"]) ?? ""))
        case "get_item":
            promise.resolve(SecureStoreModule.get(key))
        case "delete_item":
            promise.resolve(SecureStoreModule.delete(key))
        default:
            promise.reject("SecureStore has no method '\(method)'", code: "unknown_method")
        }
    }

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
        SecItemDelete(query(key) as CFDictionary) == errSecSuccess
    }
}

/// `Clipboard`: the general pasteboard.
public final class ClipboardModule: PNNativeModule {
    public static let name = "Clipboard"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "set_string":
            UIPasteboard.general.string = PNProps.string(args["text"]) ?? ""
            promise.resolve(nil)
        case "get_string":
            promise.resolve(UIPasteboard.general.string ?? "")
        default:
            promise.reject("Clipboard has no method '\(method)'", code: "unknown_method")
        }
    }
}

/// `Share`: `UIActivityViewController`, resolving whether a share completed.
public final class ShareModule: PNNativeModule {
    public static let name = "Share"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        guard method == "share" else {
            promise.reject("Share has no method '\(method)'", code: "unknown_method")
            return
        }
        var items: [Any] = []
        if let message = PNProps.string(args["message"]), !message.isEmpty { items.append(message) }
        if let url = PNProps.string(args["url"]).flatMap({ URL(string: $0) }) { items.append(url) }
        guard !items.isEmpty, let top = PNWindow.topViewController() else {
            promise.resolve(false)
            return
        }
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        if let title = PNProps.string(args["title"]) {
            controller.setValue(title, forKey: "subject")
        }
        controller.completionWithItemsHandler = { _, completed, _, _ in
            promise.resolve(completed)
        }
        if let popover = controller.popoverPresentationController {
            popover.sourceView = top.view
            popover.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.midY, width: 1, height: 1)
            popover.permittedArrowDirections = []
        }
        top.present(controller, animated: true)
    }
}

/// `Haptics`: feedback generators plus the legacy vibration sound.
public final class HapticsModule: PNNativeModule {
    public static let name = "Haptics"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "impact":
            let generator = UIImpactFeedbackGenerator(style: HapticsModule.impactStyle(PNProps.string(args["style"])))
            generator.prepare()
            generator.impactOccurred()
            promise.resolve(nil)
        case "notification":
            let generator = UINotificationFeedbackGenerator()
            generator.prepare()
            generator.notificationOccurred(HapticsModule.notificationType(PNProps.string(args["type"])))
            promise.resolve(nil)
        case "selection":
            let generator = UISelectionFeedbackGenerator()
            generator.prepare()
            generator.selectionChanged()
            promise.resolve(nil)
        case "vibrate":
            let duration = PNProps.int(args["duration_ms"]) ?? 400
            if duration <= 100 {
                let generator = UIImpactFeedbackGenerator(style: .heavy)
                generator.prepare()
                generator.impactOccurred()
            } else {
                AudioServicesPlaySystemSound(kSystemSoundID_Vibrate)
            }
            promise.resolve(nil)
        case "cancel":
            promise.resolve(nil)
        default:
            promise.reject("Haptics has no method '\(method)'", code: "unknown_method")
        }
    }

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
