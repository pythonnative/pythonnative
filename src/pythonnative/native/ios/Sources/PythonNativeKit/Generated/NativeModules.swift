import Foundation

public protocol AccessibilityInfoImplementation {
    init()
    func `announce`(`message`: String) throws -> Void
    func `is_reduce_motion_enabled`() throws -> Bool
    func `is_screen_reader_enabled`() throws -> Bool
    func `set_accessibility_focus`(`tag`: Int64) throws -> Void
}

public final class AccessibilityInfoModuleAdapter<Implementation: AccessibilityInfoImplementation>: PNNativeModule {
    public static var name: String { "AccessibilityInfo" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("AccessibilityInfo", method, args) else { throw NativeDecodeError.invalid("AccessibilityInfo.\(method)") }
            switch method {
            case "announce":
                let `message` = try PNValues.decode(String.self, args["message"])
                try implementation.`announce`(`message`: `message`); promise.resolve(nil)
            case "is_reduce_motion_enabled":
                promise.resolve(try PNValues.checkedEncode(implementation.`is_reduce_motion_enabled`()))
            case "is_screen_reader_enabled":
                promise.resolve(try PNValues.checkedEncode(implementation.`is_screen_reader_enabled`()))
            case "set_accessibility_focus":
                let `tag` = try PNValues.decode(Int64.self, args["tag"])
                try implementation.`set_accessibility_focus`(`tag`: `tag`); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum AccessibilityInfoEvents {
    public static func `change`(_ payload: [String: PNJSONValue]) { PNModuleEvents.emit(module: "AccessibilityInfo", event: "change", payload: PNValues.encode(payload)) }
}

public protocol AlertImplementation {
    init()
    func `present`(`title`: String, `message`: String?, `buttons`: [[String: PNJSONValue]], `style`: String, completion: @escaping (Result<Int64, Error>) -> Void) -> (() -> Void)?
    func `show`(`title`: String, `message`: String?, `buttons`: [[String: PNJSONValue]], `style`: String) throws -> Void
}

public final class AlertModuleAdapter<Implementation: AlertImplementation>: PNNativeModule {
    public static var name: String { "Alert" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Alert", method, args) else { throw NativeDecodeError.invalid("Alert.\(method)") }
            switch method {
            case "present":
                let `title` = try PNValues.decode(String.self, args["title"])
                let `message` = try PNValues.decode(String?.self, args["message"])
                let `buttons` = try PNValues.decode([[String: PNJSONValue]].self, args["buttons"])
                let `style` = try PNValues.decode(String.self, args["style"])
                let cancellation = implementation.`present`(`title`: `title`, `message`: `message`, `buttons`: `buttons`, `style`: `style`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "show":
                let `title` = try PNValues.decode(String.self, args["title"])
                let `message` = try PNValues.decode(String?.self, args["message"])
                let `buttons` = try PNValues.decode([[String: PNJSONValue]].self, args["buttons"])
                let `style` = try PNValues.decode(String.self, args["style"])
                try implementation.`show`(`title`: `title`, `message`: `message`, `buttons`: `buttons`, `style`: `style`); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol AppStateImplementation {
    init()
    func `current_state`() throws -> String
}

public final class AppStateModuleAdapter<Implementation: AppStateImplementation>: PNNativeModule {
    public static var name: String { "AppState" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("AppState", method, args) else { throw NativeDecodeError.invalid("AppState.\(method)") }
            switch method {
            case "current_state":
                promise.resolve(try PNValues.checkedEncode(implementation.`current_state`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum AppStateEvents {
    public static func `change`(_ payload: String) { PNModuleEvents.emit(module: "AppState", event: "change", payload: PNValues.encode(payload)) }
}

public protocol AssetsImplementation {
    init()
    func `configure`(`overlay`: String?, `manifest`: PNAssetManifest) throws -> Void
    func `exists`(`path`: String) throws -> Bool
    func `read`(`path`: String) throws -> String?
}

public final class AssetsModuleAdapter<Implementation: AssetsImplementation>: PNNativeModule {
    public static var name: String { "Assets" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Assets", method, args) else { throw NativeDecodeError.invalid("Assets.\(method)") }
            switch method {
            case "configure":
                let `overlay` = try PNValues.decode(String?.self, args["overlay"])
                let `manifest` = try PNValues.decode(PNAssetManifest.self, args["manifest"])
                try implementation.`configure`(`overlay`: `overlay`, `manifest`: `manifest`); promise.resolve(nil)
            case "exists":
                let `path` = try PNValues.decode(String.self, args["path"])
                promise.resolve(try PNValues.checkedEncode(implementation.`exists`(`path`: `path`)))
            case "read":
                let `path` = try PNValues.decode(String.self, args["path"])
                promise.resolve(try PNValues.checkedEncode(implementation.`read`(`path`: `path`)))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol BatteryImplementation {
    init()
    func `get_level`() throws -> Double
    func `get_state`() throws -> String
}

public final class BatteryModuleAdapter<Implementation: BatteryImplementation>: PNNativeModule {
    public static var name: String { "Battery" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Battery", method, args) else { throw NativeDecodeError.invalid("Battery.\(method)") }
            switch method {
            case "get_level":
                promise.resolve(try PNValues.checkedEncode(implementation.`get_level`()))
            case "get_state":
                promise.resolve(try PNValues.checkedEncode(implementation.`get_state`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum BatteryEvents {
    public static func `change`(_ payload: [String: PNJSONValue]) { PNModuleEvents.emit(module: "Battery", event: "change", payload: PNValues.encode(payload)) }
}

public protocol BiometricsImplementation {
    init()
    func `authenticate`(`reason`: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)?
    func `is_available`() throws -> Bool
}

public final class BiometricsModuleAdapter<Implementation: BiometricsImplementation>: PNNativeModule {
    public static var name: String { "Biometrics" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Biometrics", method, args) else { throw NativeDecodeError.invalid("Biometrics.\(method)") }
            switch method {
            case "authenticate":
                let `reason` = try PNValues.decode(String.self, args["reason"] ?? PNValues.defaultValue("\"Authenticate\""))
                let cancellation = implementation.`authenticate`(`reason`: `reason`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "is_available":
                promise.resolve(try PNValues.checkedEncode(implementation.`is_available`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol CameraImplementation {
    init()
    func `pick_from_gallery`(`quality`: Double, `allow_editing`: Bool, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)?
    func `take_photo`(`quality`: Double, `allow_editing`: Bool, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)?
}

public final class CameraModuleAdapter<Implementation: CameraImplementation>: PNNativeModule {
    public static var name: String { "Camera" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Camera", method, args) else { throw NativeDecodeError.invalid("Camera.\(method)") }
            switch method {
            case "pick_from_gallery":
                let `quality` = try PNValues.decode(Double.self, args["quality"] ?? PNValues.defaultValue("0.9"))
                let `allow_editing` = try PNValues.decode(Bool.self, args["allow_editing"] ?? PNValues.defaultValue("false"))
                let cancellation = implementation.`pick_from_gallery`(`quality`: `quality`, `allow_editing`: `allow_editing`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "take_photo":
                let `quality` = try PNValues.decode(Double.self, args["quality"] ?? PNValues.defaultValue("0.9"))
                let `allow_editing` = try PNValues.decode(Bool.self, args["allow_editing"] ?? PNValues.defaultValue("false"))
                let cancellation = implementation.`take_photo`(`quality`: `quality`, `allow_editing`: `allow_editing`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol ClipboardImplementation {
    init()
    func `get_string`() throws -> String
    func `set_string`(`text`: String) throws -> Void
}

public final class ClipboardModuleAdapter<Implementation: ClipboardImplementation>: PNNativeModule {
    public static var name: String { "Clipboard" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Clipboard", method, args) else { throw NativeDecodeError.invalid("Clipboard.\(method)") }
            switch method {
            case "get_string":
                promise.resolve(try PNValues.checkedEncode(implementation.`get_string`()))
            case "set_string":
                let `text` = try PNValues.decode(String.self, args["text"])
                try implementation.`set_string`(`text`: `text`); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol DeviceImplementation {
    init()
    func `info`() throws -> [String: PNJSONValue]
}

public final class DeviceModuleAdapter<Implementation: DeviceImplementation>: PNNativeModule {
    public static var name: String { "Device" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Device", method, args) else { throw NativeDecodeError.invalid("Device.\(method)") }
            switch method {
            case "info":
                promise.resolve(try PNValues.checkedEncode(implementation.`info`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol HapticsImplementation {
    init()
    func `cancel`() throws -> Void
    func `impact`(`style`: String) throws -> Void
    func `notification`(`type`: String) throws -> Void
    func `selection`() throws -> Void
    func `vibrate`(`duration_ms`: Int64) throws -> Void
}

public final class HapticsModuleAdapter<Implementation: HapticsImplementation>: PNNativeModule {
    public static var name: String { "Haptics" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Haptics", method, args) else { throw NativeDecodeError.invalid("Haptics.\(method)") }
            switch method {
            case "cancel":
                try implementation.`cancel`(); promise.resolve(nil)
            case "impact":
                let `style` = try PNValues.decode(String.self, args["style"] ?? PNValues.defaultValue("\"medium\""))
                try implementation.`impact`(`style`: `style`); promise.resolve(nil)
            case "notification":
                let `type` = try PNValues.decode(String.self, args["type"] ?? PNValues.defaultValue("\"success\""))
                try implementation.`notification`(`type`: `type`); promise.resolve(nil)
            case "selection":
                try implementation.`selection`(); promise.resolve(nil)
            case "vibrate":
                let `duration_ms` = try PNValues.decode(Int64.self, args["duration_ms"] ?? PNValues.defaultValue("400"))
                try implementation.`vibrate`(`duration_ms`: `duration_ms`); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol ImagesImplementation {
    init()
    func `clear_cache`() throws -> Void
    func `get_size`(`uri`: String, completion: @escaping (Result<PNImageSize, Error>) -> Void) -> (() -> Void)?
    func `prefetch`(`uri`: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)?
}

public final class ImagesModuleAdapter<Implementation: ImagesImplementation>: PNNativeModule {
    public static var name: String { "Images" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Images", method, args) else { throw NativeDecodeError.invalid("Images.\(method)") }
            switch method {
            case "clear_cache":
                try implementation.`clear_cache`(); promise.resolve(nil)
            case "get_size":
                let `uri` = try PNValues.decode(String.self, args["uri"])
                let cancellation = implementation.`get_size`(`uri`: `uri`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "prefetch":
                let `uri` = try PNValues.decode(String.self, args["uri"])
                let cancellation = implementation.`prefetch`(`uri`: `uri`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol KeyboardImplementation {
    init()
    func `dismiss`() throws -> Void
    func `is_visible`() throws -> Bool
}

public final class KeyboardModuleAdapter<Implementation: KeyboardImplementation>: PNNativeModule {
    public static var name: String { "Keyboard" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Keyboard", method, args) else { throw NativeDecodeError.invalid("Keyboard.\(method)") }
            switch method {
            case "dismiss":
                try implementation.`dismiss`(); promise.resolve(nil)
            case "is_visible":
                promise.resolve(try PNValues.checkedEncode(implementation.`is_visible`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum KeyboardEvents {
    public static func `change`(_ payload: [String: PNJSONValue]) { PNModuleEvents.emit(module: "Keyboard", event: "change", payload: PNValues.encode(payload)) }
}

public protocol LinkingImplementation {
    init()
    func `can_open_url`(`url`: String) throws -> Bool
    func `open_settings`() throws -> Bool
    func `open_url`(`url`: String) throws -> Bool
}

public final class LinkingModuleAdapter<Implementation: LinkingImplementation>: PNNativeModule {
    public static var name: String { "Linking" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Linking", method, args) else { throw NativeDecodeError.invalid("Linking.\(method)") }
            switch method {
            case "can_open_url":
                let `url` = try PNValues.decode(String.self, args["url"])
                promise.resolve(try PNValues.checkedEncode(implementation.`can_open_url`(`url`: `url`)))
            case "open_settings":
                promise.resolve(try PNValues.checkedEncode(implementation.`open_settings`()))
            case "open_url":
                let `url` = try PNValues.decode(String.self, args["url"])
                promise.resolve(try PNValues.checkedEncode(implementation.`open_url`(`url`: `url`)))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum LinkingEvents {
    public static func `url`(_ payload: String) { PNModuleEvents.emit(module: "Linking", event: "url", payload: PNValues.encode(payload)) }
}

public protocol LocalizationImplementation {
    init()
    func `get_locales`() throws -> [[String: PNJSONValue]]
    func `get_timezone`() throws -> String
}

public final class LocalizationModuleAdapter<Implementation: LocalizationImplementation>: PNNativeModule {
    public static var name: String { "Localization" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Localization", method, args) else { throw NativeDecodeError.invalid("Localization.\(method)") }
            switch method {
            case "get_locales":
                promise.resolve(try PNValues.checkedEncode(implementation.`get_locales`()))
            case "get_timezone":
                promise.resolve(try PNValues.checkedEncode(implementation.`get_timezone`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum LocalizationEvents {
    public static func `change`(_ payload: [String: PNJSONValue]) { PNModuleEvents.emit(module: "Localization", event: "change", payload: PNValues.encode(payload)) }
}

public protocol LocationImplementation {
    init()
    func `get_current`(`accuracy`: PNLocationGetCurrentAccuracy, `timeout`: Double, completion: @escaping (Result<[String: Double]?, Error>) -> Void) -> (() -> Void)?
}

public final class LocationModuleAdapter<Implementation: LocationImplementation>: PNNativeModule {
    public static var name: String { "Location" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Location", method, args) else { throw NativeDecodeError.invalid("Location.\(method)") }
            switch method {
            case "get_current":
                let `accuracy` = try PNValues.decode(PNLocationGetCurrentAccuracy.self, args["accuracy"] ?? PNValues.defaultValue("\"balanced\""))
                let `timeout` = try PNValues.decode(Double.self, args["timeout"] ?? PNValues.defaultValue("10.0"))
                let cancellation = implementation.`get_current`(`accuracy`: `accuracy`, `timeout`: `timeout`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol NetInfoImplementation {
    init()
    func `fetch`() throws -> [String: PNJSONValue]?
}

public final class NetInfoModuleAdapter<Implementation: NetInfoImplementation>: PNNativeModule {
    public static var name: String { "NetInfo" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("NetInfo", method, args) else { throw NativeDecodeError.invalid("NetInfo.\(method)") }
            switch method {
            case "fetch":
                promise.resolve(try PNValues.checkedEncode(implementation.`fetch`()))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public enum NetInfoEvents {
    public static func `change`(_ payload: [String: PNJSONValue]) { PNModuleEvents.emit(module: "NetInfo", event: "change", payload: PNValues.encode(payload)) }
}

public protocol NotificationsImplementation {
    init()
    func `cancel`(`identifier`: String, completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)?
    func `get_device_token`(completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)?
    func `request_permission`(completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)?
    func `schedule`(`title`: String, `body`: String, `delay_seconds`: Double, `identifier`: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)?
}

public final class NotificationsModuleAdapter<Implementation: NotificationsImplementation>: PNNativeModule {
    public static var name: String { "Notifications" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Notifications", method, args) else { throw NativeDecodeError.invalid("Notifications.\(method)") }
            switch method {
            case "cancel":
                let `identifier` = try PNValues.decode(String.self, args["identifier"] ?? PNValues.defaultValue("\"default\""))
                let cancellation = implementation.`cancel`(`identifier`: `identifier`) { result in
                    switch result {
                    case .success(let value): promise.resolve(nil)
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "get_device_token":
                let cancellation = implementation.`get_device_token`() { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "request_permission":
                let cancellation = implementation.`request_permission`() { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "schedule":
                let `title` = try PNValues.decode(String.self, args["title"])
                let `body` = try PNValues.decode(String.self, args["body"] ?? PNValues.defaultValue("\"\""))
                let `delay_seconds` = try PNValues.decode(Double.self, args["delay_seconds"] ?? PNValues.defaultValue("0"))
                let `identifier` = try PNValues.decode(String.self, args["identifier"] ?? PNValues.defaultValue("\"default\""))
                let cancellation = implementation.`schedule`(`title`: `title`, `body`: `body`, `delay_seconds`: `delay_seconds`, `identifier`: `identifier`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol PermissionsImplementation {
    init()
    func `check`(`permission`: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)?
    func `request`(`permission`: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)?
}

public final class PermissionsModuleAdapter<Implementation: PermissionsImplementation>: PNNativeModule {
    public static var name: String { "Permissions" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Permissions", method, args) else { throw NativeDecodeError.invalid("Permissions.\(method)") }
            switch method {
            case "check":
                let `permission` = try PNValues.decode(String.self, args["permission"])
                let cancellation = implementation.`check`(`permission`: `permission`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            case "request":
                let `permission` = try PNValues.decode(String.self, args["permission"])
                let cancellation = implementation.`request`(`permission`: `permission`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol SecureStoreImplementation {
    init()
    func `clear`() throws -> Void
    func `delete_item`(`key`: String) throws -> Bool
    func `get_item`(`key`: String) throws -> String?
    func `set_item`(`key`: String, `value`: String) throws -> Bool
}

public final class SecureStoreModuleAdapter<Implementation: SecureStoreImplementation>: PNNativeModule {
    public static var name: String { "SecureStore" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("SecureStore", method, args) else { throw NativeDecodeError.invalid("SecureStore.\(method)") }
            switch method {
            case "clear":
                try implementation.`clear`(); promise.resolve(nil)
            case "delete_item":
                let `key` = try PNValues.decode(String.self, args["key"])
                promise.resolve(try PNValues.checkedEncode(implementation.`delete_item`(`key`: `key`)))
            case "get_item":
                let `key` = try PNValues.decode(String.self, args["key"])
                promise.resolve(try PNValues.checkedEncode(implementation.`get_item`(`key`: `key`)))
            case "set_item":
                let `key` = try PNValues.decode(String.self, args["key"])
                let `value` = try PNValues.decode(String.self, args["value"])
                promise.resolve(try PNValues.checkedEncode(implementation.`set_item`(`key`: `key`, `value`: `value`)))
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol ShareImplementation {
    init()
    func `share`(`message`: String?, `url`: String?, `title`: String?, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)?
}

public final class ShareModuleAdapter<Implementation: ShareImplementation>: PNNativeModule {
    public static var name: String { "Share" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Share", method, args) else { throw NativeDecodeError.invalid("Share.\(method)") }
            switch method {
            case "share":
                let `message` = try PNValues.decode(String?.self, args["message"] ?? PNValues.defaultValue("null"))
                let `url` = try PNValues.decode(String?.self, args["url"] ?? PNValues.defaultValue("null"))
                let `title` = try PNValues.decode(String?.self, args["title"] ?? PNValues.defaultValue("null"))
                let cancellation = implementation.`share`(`message`: `message`, `url`: `url`, `title`: `title`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol StorageImplementation {
    init()
    func `all_keys`() throws -> [String]
    func `clear`() throws -> Void
    func `delete`(`key`: String) throws -> Void
    func `get`(`key`: String) throws -> String?
    func `set`(`key`: String, `value`: String) throws -> Void
}

public final class StorageModuleAdapter<Implementation: StorageImplementation>: PNNativeModule {
    public static var name: String { "Storage" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("Storage", method, args) else { throw NativeDecodeError.invalid("Storage.\(method)") }
            switch method {
            case "all_keys":
                promise.resolve(try PNValues.checkedEncode(implementation.`all_keys`()))
            case "clear":
                try implementation.`clear`(); promise.resolve(nil)
            case "delete":
                let `key` = try PNValues.decode(String.self, args["key"])
                try implementation.`delete`(`key`: `key`); promise.resolve(nil)
            case "get":
                let `key` = try PNValues.decode(String.self, args["key"])
                promise.resolve(try PNValues.checkedEncode(implementation.`get`(`key`: `key`)))
            case "set":
                let `key` = try PNValues.decode(String.self, args["key"])
                let `value` = try PNValues.decode(String.self, args["value"])
                try implementation.`set`(`key`: `key`, `value`: `value`); promise.resolve(nil)
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}

public protocol WebViewsImplementation {
    init()
    func `eval_js`(`tag`: Int64, `script`: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)?
}

public final class WebViewsModuleAdapter<Implementation: WebViewsImplementation>: PNNativeModule {
    public static var name: String { "WebViews" }
    private let implementation: Implementation
    public init() { implementation = Implementation() }
    public init(implementation: Implementation) { self.implementation = implementation }
    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        do {
            guard PNContracts.validateModule("WebViews", method, args) else { throw NativeDecodeError.invalid("WebViews.\(method)") }
            switch method {
            case "eval_js":
                let `tag` = try PNValues.decode(Int64.self, args["tag"])
                let `script` = try PNValues.decode(String.self, args["script"])
                let cancellation = implementation.`eval_js`(`tag`: `tag`, `script`: `script`) { result in
                    switch result {
                    case .success(let value): do { promise.resolve(try PNValues.checkedEncode(value)) } catch { promise.reject(error) }
                    case .failure(let error): promise.reject(error)
                    }
                }
                if let cancellation = cancellation { promise.onCancel(cancellation) }
            default: promise.reject("Unknown method", code: "unknown_method")
            }
        } catch { promise.reject(error) }
    }
}
