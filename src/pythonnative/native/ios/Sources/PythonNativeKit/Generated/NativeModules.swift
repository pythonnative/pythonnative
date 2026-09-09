import Foundation

public protocol AlertImplementation {
    init()
    func present(title: String, message: String?, buttons: Any, style: String, completion: @escaping (Result<Int, Error>) -> Void)
    func show(title: String, message: String?, buttons: Any, style: String) throws -> Void
}

public final class AlertModuleAdapter<Implementation: AlertImplementation>: PNNativeModule {
    public static var name: String { "Alert" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "present":
                guard let title = args["title"] as? String else { promise.reject("Invalid title"); return }
                let message = args["message"] as? String
                guard let buttons = args["buttons"] as? Any else { promise.reject("Invalid buttons"); return }
                guard let style = args["style"] as? String else { promise.reject("Invalid style"); return }
                implementation.present(title: title, message: message, buttons: buttons, style: style) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            case "show":
                guard let title = args["title"] as? String else { promise.reject("Invalid title"); return }
                let message = args["message"] as? String
                guard let buttons = args["buttons"] as? Any else { promise.reject("Invalid buttons"); return }
                guard let style = args["style"] as? String else { promise.reject("Invalid style"); return }
                try implementation.show(title: title, message: message, buttons: buttons, style: style); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol AppStateImplementation {
    init()
    func current_state() throws -> String
}

public final class AppStateModuleAdapter<Implementation: AppStateImplementation>: PNNativeModule {
    public static var name: String { "AppState" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "current_state":
                promise.resolve(try implementation.current_state())
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol BatteryImplementation {
    init()
    func get_level() throws -> Double
    func get_state() throws -> String
}

public final class BatteryModuleAdapter<Implementation: BatteryImplementation>: PNNativeModule {
    public static var name: String { "Battery" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "get_level":
                promise.resolve(try implementation.get_level())
            case "get_state":
                promise.resolve(try implementation.get_state())
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol BiometricsImplementation {
    init()
    func authenticate(reason: String, completion: @escaping (Result<Bool, Error>) -> Void)
    func is_available() throws -> Bool
}

public final class BiometricsModuleAdapter<Implementation: BiometricsImplementation>: PNNativeModule {
    public static var name: String { "Biometrics" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "authenticate":
                guard let reason = args["reason"] as? String else { promise.reject("Invalid reason"); return }
                implementation.authenticate(reason: reason) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            case "is_available":
                promise.resolve(try implementation.is_available())
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol CameraImplementation {
    init()
    func pick_from_gallery(quality: Double, allow_editing: Bool, completion: @escaping (Result<String?, Error>) -> Void)
    func take_photo(quality: Double, allow_editing: Bool, completion: @escaping (Result<String?, Error>) -> Void)
}

public final class CameraModuleAdapter<Implementation: CameraImplementation>: PNNativeModule {
    public static var name: String { "Camera" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "pick_from_gallery":
                guard let quality = args["quality"] as? Double else { promise.reject("Invalid quality"); return }
                guard let allow_editing = args["allow_editing"] as? Bool else { promise.reject("Invalid allow_editing"); return }
                implementation.pick_from_gallery(quality: quality, allow_editing: allow_editing) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            case "take_photo":
                guard let quality = args["quality"] as? Double else { promise.reject("Invalid quality"); return }
                guard let allow_editing = args["allow_editing"] as? Bool else { promise.reject("Invalid allow_editing"); return }
                implementation.take_photo(quality: quality, allow_editing: allow_editing) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol ClipboardImplementation {
    init()
    func get_string() throws -> String
    func set_string(text: String) throws -> Void
}

public final class ClipboardModuleAdapter<Implementation: ClipboardImplementation>: PNNativeModule {
    public static var name: String { "Clipboard" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "get_string":
                promise.resolve(try implementation.get_string())
            case "set_string":
                guard let text = args["text"] as? String else { promise.reject("Invalid text"); return }
                try implementation.set_string(text: text); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol DeviceImplementation {
    init()
    func info() throws -> Any
}

public final class DeviceModuleAdapter<Implementation: DeviceImplementation>: PNNativeModule {
    public static var name: String { "Device" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "info":
                promise.resolve(try implementation.info())
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol HapticsImplementation {
    init()
    func cancel() throws -> Void
    func impact(style: String) throws -> Void
    func notification(type: String) throws -> Void
    func selection() throws -> Void
    func vibrate(duration_ms: Int) throws -> Void
}

public final class HapticsModuleAdapter<Implementation: HapticsImplementation>: PNNativeModule {
    public static var name: String { "Haptics" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "cancel":
                try implementation.cancel(); promise.resolve(nil)
            case "impact":
                guard let style = args["style"] as? String else { promise.reject("Invalid style"); return }
                try implementation.impact(style: style); promise.resolve(nil)
            case "notification":
                guard let type = args["type"] as? String else { promise.reject("Invalid type"); return }
                try implementation.notification(type: type); promise.resolve(nil)
            case "selection":
                try implementation.selection(); promise.resolve(nil)
            case "vibrate":
                guard let duration_ms = args["duration_ms"] as? Int else { promise.reject("Invalid duration_ms"); return }
                try implementation.vibrate(duration_ms: duration_ms); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol LinkingImplementation {
    init()
    func can_open_url(url: String) throws -> Bool
    func open_settings() throws -> Bool
    func open_url(url: String) throws -> Bool
}

public final class LinkingModuleAdapter<Implementation: LinkingImplementation>: PNNativeModule {
    public static var name: String { "Linking" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "can_open_url":
                guard let url = args["url"] as? String else { promise.reject("Invalid url"); return }
                promise.resolve(try implementation.can_open_url(url: url))
            case "open_settings":
                promise.resolve(try implementation.open_settings())
            case "open_url":
                guard let url = args["url"] as? String else { promise.reject("Invalid url"); return }
                promise.resolve(try implementation.open_url(url: url))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol LocationImplementation {
    init()
    func get_current(accuracy: Any, timeout: Double, completion: @escaping (Result<Any?, Error>) -> Void)
}

public final class LocationModuleAdapter<Implementation: LocationImplementation>: PNNativeModule {
    public static var name: String { "Location" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "get_current":
                guard let accuracy = args["accuracy"] as? Any else { promise.reject("Invalid accuracy"); return }
                guard let timeout = args["timeout"] as? Double else { promise.reject("Invalid timeout"); return }
                implementation.get_current(accuracy: accuracy, timeout: timeout) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol NetInfoImplementation {
    init()
    func fetch() throws -> Any?
}

public final class NetInfoModuleAdapter<Implementation: NetInfoImplementation>: PNNativeModule {
    public static var name: String { "NetInfo" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "fetch":
                promise.resolve(try implementation.fetch())
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol NotificationsImplementation {
    init()
    func cancel(identifier: String, completion: @escaping (Result<Void, Error>) -> Void)
    func get_device_token(completion: @escaping (Result<String?, Error>) -> Void)
    func request_permission(completion: @escaping (Result<Bool, Error>) -> Void)
    func schedule(title: String, body: String, delay_seconds: Double, identifier: String, completion: @escaping (Result<Bool, Error>) -> Void)
}

public final class NotificationsModuleAdapter<Implementation: NotificationsImplementation>: PNNativeModule {
    public static var name: String { "Notifications" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "cancel":
                guard let identifier = args["identifier"] as? String else { promise.reject("Invalid identifier"); return }
                implementation.cancel(identifier: identifier) { result in
                    switch result { case .success(let value): promise.resolve(nil); case .failure(let error): promise.reject(error) }
                }
            case "get_device_token":
                implementation.get_device_token() { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            case "request_permission":
                implementation.request_permission() { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            case "schedule":
                guard let title = args["title"] as? String else { promise.reject("Invalid title"); return }
                guard let body = args["body"] as? String else { promise.reject("Invalid body"); return }
                guard let delay_seconds = args["delay_seconds"] as? Double else { promise.reject("Invalid delay_seconds"); return }
                guard let identifier = args["identifier"] as? String else { promise.reject("Invalid identifier"); return }
                implementation.schedule(title: title, body: body, delay_seconds: delay_seconds, identifier: identifier) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol PermissionsImplementation {
    init()
    func check(permission: String) throws -> String
    func request(permission: String, completion: @escaping (Result<String, Error>) -> Void)
}

public final class PermissionsModuleAdapter<Implementation: PermissionsImplementation>: PNNativeModule {
    public static var name: String { "Permissions" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "check":
                guard let permission = args["permission"] as? String else { promise.reject("Invalid permission"); return }
                promise.resolve(try implementation.check(permission: permission))
            case "request":
                guard let permission = args["permission"] as? String else { promise.reject("Invalid permission"); return }
                implementation.request(permission: permission) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol SecureStoreImplementation {
    init()
    func clear() throws -> Void
    func delete_item(key: String) throws -> Bool
    func get_item(key: String) throws -> String?
    func set_item(key: String, value: String) throws -> Bool
}

public final class SecureStoreModuleAdapter<Implementation: SecureStoreImplementation>: PNNativeModule {
    public static var name: String { "SecureStore" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "clear":
                try implementation.clear(); promise.resolve(nil)
            case "delete_item":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                promise.resolve(try implementation.delete_item(key: key))
            case "get_item":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                promise.resolve(try implementation.get_item(key: key))
            case "set_item":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                guard let value = args["value"] as? String else { promise.reject("Invalid value"); return }
                promise.resolve(try implementation.set_item(key: key, value: value))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol ShareImplementation {
    init()
    func share(message: String?, url: String?, title: String?, completion: @escaping (Result<Bool, Error>) -> Void)
}

public final class ShareModuleAdapter<Implementation: ShareImplementation>: PNNativeModule {
    public static var name: String { "Share" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "share":
                let message = args["message"] as? String
                let url = args["url"] as? String
                let title = args["title"] as? String
                implementation.share(message: message, url: url, title: title) { result in
                    switch result { case .success(let value): promise.resolve(value); case .failure(let error): promise.reject(error) }
                }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol StorageImplementation {
    init()
    func all_keys() throws -> Any
    func clear() throws -> Void
    func delete(key: String) throws -> Void
    func get(key: String) throws -> String?
    func set(key: String, value: String) throws -> Void
}

public final class StorageModuleAdapter<Implementation: StorageImplementation>: PNNativeModule {
    public static var name: String { "Storage" }
    let implementation: Implementation
    public init() { implementation = Implementation() }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            switch method {
            case "all_keys":
                promise.resolve(try implementation.all_keys())
            case "clear":
                try implementation.clear(); promise.resolve(nil)
            case "delete":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                try implementation.delete(key: key); promise.resolve(nil)
            case "get":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                promise.resolve(try implementation.get(key: key))
            case "set":
                guard let key = args["key"] as? String else { promise.reject("Invalid key"); return }
                guard let value = args["value"] as? String else { promise.reject("Invalid value"); return }
                try implementation.set(key: key, value: value); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}
