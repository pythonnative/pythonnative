import UIKit

/// A native plugin bundled into the app by `pn build`. The generated
/// `PNGeneratedPlugins.registerAll(into:)` calls each entry's `register`.
public protocol PNPlugin {
    /// Register component managers and native modules.
    static func register(into registry: PNRegistry)
}

/// Component-manager and native-module registry.
///
/// Built-ins register lazily on first use; plugins register through
/// `PNPlugin.register(into:)`. Component factories are invoked once per
/// element type and the resulting manager is shared by every view of
/// that type (managers are stateless; per-view state lives in
/// `PNViewState`).
public final class PNRegistry {
    public static let shared = PNRegistry()

    private var componentFactories: [String: () -> PNComponentManager] = [:]
    private var componentManagers: [String: PNComponentManager] = [:]
    private var moduleTypes: [String: PNNativeModule.Type] = [:]
    private var moduleInstances: [String: PNNativeModule] = [:]
    private var builtinsRegistered = false
    private let placeholder = PNPlaceholderManager()

    private init() {}

    // MARK: - Registration

    /// Register (or replace) the manager factory for element type `name`.
    public func registerComponent(_ name: String, factory: @escaping () -> PNComponentManager) {
        componentFactories[name] = factory
        componentManagers.removeValue(forKey: name)
    }

    /// Register (or replace) a native module by its `name`.
    public func registerModule(_ type: PNNativeModule.Type) {
        moduleTypes[type.name] = type
        moduleInstances.removeValue(forKey: type.name)
    }

    /// Element type names currently registered.
    public var componentNames: [String] {
        ensureBuiltins()
        return Array(componentFactories.keys).sorted()
    }

    /// Module names currently registered.
    public var moduleNames: [String] {
        ensureBuiltins()
        return Array(moduleTypes.keys).sorted()
    }

    // MARK: - Lookup

    /// The shared manager for `type`, or a placeholder manager for unknown types.
    public func manager(for type: String) -> PNComponentManager {
        ensureBuiltins()
        if let existing = componentManagers[type] { return existing }
        if let factory = componentFactories[type] {
            let manager = factory()
            componentManagers[type] = manager
            return manager
        }
        PNLog.once(PNLog.components, key: "unknown-type:\(type)", "unknown element type '\(type)'; using a placeholder UIView")
        return placeholder
    }

    /// The module instance registered under `name`, created on first use.
    public func module(named name: String) -> PNNativeModule? {
        ensureBuiltins()
        if let existing = moduleInstances[name] { return existing }
        guard let type = moduleTypes[name] else { return nil }
        let instance = type.init()
        moduleInstances[name] = instance
        return instance
    }

    // MARK: - Built-ins

    /// Register every built-in manager and module, then the generated plugins.
    public func ensureBuiltins() {
        if builtinsRegistered { return }
        builtinsRegistered = true
        PNBuiltins.register(into: self)
        PNGeneratedPlugins.registerAll(into: self)
    }
}

/// Registration of the components and modules that ship with PythonNativeKit.
enum PNBuiltins {
    static func register(into registry: PNRegistry) {
        let flex: () -> PNComponentManager = { PNViewManager() }
        registry.registerComponent("View", factory: flex)
        registry.registerComponent("Column", factory: flex)
        registry.registerComponent("Row", factory: flex)
        registry.registerComponent("Text") { PNTextManager() }
        registry.registerComponent("Button") { PNButtonManager() }
        registry.registerComponent("TextInput") { PNTextInputManager() }
        registry.registerComponent("Image") { PNImageManager() }
        registry.registerComponent("Switch") { PNSwitchManager() }
        registry.registerComponent("ProgressBar") { PNProgressBarManager() }
        registry.registerComponent("ActivityIndicator") { PNActivityIndicatorManager() }
        registry.registerComponent("WebView") { PNWebViewManager() }
        registry.registerComponent("Spacer") { PNSpacerManager() }
        registry.registerComponent("ScrollView") { PNScrollViewManager() }
        registry.registerComponent("SafeAreaView") { PNSafeAreaViewManager() }
        registry.registerComponent("Modal") { PNModalManager() }
        registry.registerComponent("Portal") { PNPortalManager() }
        registry.registerComponent("Slider") { PNSliderManager() }
        registry.registerComponent("TabBar") { PNTabBarManager() }
        registry.registerComponent("Pressable") { PNPressableManager() }
        registry.registerComponent("StatusBar") { PNStatusBarManager() }
        registry.registerComponent("KeyboardAvoidingView") { PNKeyboardAvoidingViewManager() }
        registry.registerComponent("Picker") { PNPickerManager() }
        registry.registerComponent("Checkbox") { PNCheckboxManager() }
        registry.registerComponent("SegmentedControl") { PNSegmentedControlManager() }
        registry.registerComponent("DatePicker") { PNDatePickerManager() }
        registry.registerComponent("VirtualList") { PNVirtualListManager() }

        registry.registerModule(HostModule.self)
        registry.registerModule(DeviceModule.self)
        registry.registerModule(AlertModule.self)
        registry.registerModule(StorageModule.self)
        registry.registerModule(SecureStoreModule.self)
        registry.registerModule(ClipboardModule.self)
        registry.registerModule(ShareModule.self)
        registry.registerModule(LinkingModule.self)
        registry.registerModule(HapticsModule.self)
        registry.registerModule(BatteryModule.self)
        registry.registerModule(NetInfoModule.self)
        registry.registerModule(AppStateModule.self)
        registry.registerModule(PermissionsModule.self)
        registry.registerModule(NotificationsModule.self)
        registry.registerModule(CameraModule.self)
        registry.registerModule(LocationModule.self)
        registry.registerModule(BiometricsModule.self)
    }
}
