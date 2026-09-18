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

    /// The shared manager for `type`, or nil if its implementation is missing.
    public func manager(for type: String) -> PNComponentManager? {
        ensureBuiltins()
        if let existing = componentManagers[type] { return existing }
        if let factory = componentFactories[type] {
            let manager = factory()
            componentManagers[type] = manager
            return manager
        }
        return nil
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
        registry.registerComponent("Screen") { PNScreenManager() }
        registry.registerComponent("ScreenStack") { PNScreenStackManager() }
        registry.registerComponent("Column", factory: flex)
        registry.registerComponent("Row", factory: flex)
        registry.registerComponent("Text") { PNTextManager() }
        registry.registerComponent("Button") { PNButtonManager() }
        registry.registerComponent("TextInput") { PNTextInputManager() }
        registry.registerComponent("Image") { PNImageManager() }
        registry.registerComponent("Svg") { PNSvgManager() }
        registry.registerComponent("LinearGradient") { PNLinearGradientManager() }
        registry.registerComponent("BlurView") { PNBlurViewManager() }
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
        registry.registerModule(DeviceModuleAdapter<DeviceModule>.self)
        registry.registerModule(AlertModuleAdapter<AlertModule>.self)
        registry.registerModule(StorageModuleAdapter<StorageModule>.self)
        registry.registerModule(SecureStoreModuleAdapter<SecureStoreModule>.self)
        registry.registerModule(ClipboardModuleAdapter<ClipboardModule>.self)
        registry.registerModule(ShareModuleAdapter<ShareModule>.self)
        registry.registerModule(LinkingModuleAdapter<LinkingModule>.self)
        registry.registerModule(HapticsModuleAdapter<HapticsModule>.self)
        registry.registerModule(BatteryModuleAdapter<BatteryModule>.self)
        registry.registerModule(NetInfoModuleAdapter<NetInfoModule>.self)
        registry.registerModule(AppStateModuleAdapter<AppStateModule>.self)
        registry.registerModule(PermissionsModuleAdapter<PermissionsModule>.self)
        registry.registerModule(NotificationsModuleAdapter<NotificationsModule>.self)
        registry.registerModule(CameraModuleAdapter<CameraModule>.self)
        registry.registerModule(LocationModuleAdapter<LocationModule>.self)
        registry.registerModule(BiometricsModuleAdapter<BiometricsModule>.self)
        registry.registerModule(AssetsModuleAdapter<AssetsModule>.self)
        registry.registerModule(ImagesModuleAdapter<ImagesModule>.self)
    }
}
