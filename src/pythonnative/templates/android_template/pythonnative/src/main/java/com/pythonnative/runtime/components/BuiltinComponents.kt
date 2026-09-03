package com.pythonnative.runtime.components

import com.pythonnative.runtime.bridge.PNRegistry

/** Registers the built-in element types with the registry. */
object BuiltinComponents {
    fun register(registry: PNRegistry) {
        registry.registerComponent("View") { ViewManager() }
        registry.registerComponent("Column") { ViewManager() }
        registry.registerComponent("Row") { ViewManager() }
        registry.registerComponent("Text") { TextManager() }
        registry.registerComponent("Button") { ButtonManager() }
        registry.registerComponent("TextInput") { TextInputManager() }
        registry.registerComponent("Image") { ImageManager() }
        registry.registerComponent("Switch") { SwitchManager() }
        registry.registerComponent("Checkbox") { CheckboxManager() }
        registry.registerComponent("ProgressBar") { ProgressBarManager() }
        registry.registerComponent("ActivityIndicator") { ActivityIndicatorManager() }
        registry.registerComponent("Slider") { SliderManager() }
        registry.registerComponent("WebView") { WebViewManager() }
        registry.registerComponent("Spacer") { SpacerManager() }
        registry.registerComponent("ScrollView") { ScrollViewManager() }
        registry.registerComponent("SafeAreaView") { SafeAreaViewManager() }
        registry.registerComponent("KeyboardAvoidingView") { KeyboardAvoidingViewManager() }
        registry.registerComponent("Modal") { ModalManager() }
        registry.registerComponent("Portal") { PortalManager() }
        registry.registerComponent("TabBar") { TabBarManager() }
        registry.registerComponent("Pressable") { PressableManager() }
        registry.registerComponent("StatusBar") { StatusBarManager() }
        registry.registerComponent("Picker") { PickerManager() }
        registry.registerComponent("SegmentedControl") { SegmentedControlManager() }
        registry.registerComponent("DatePicker") { DatePickerManager() }
        registry.registerComponent("VirtualList") { VirtualListManager() }
    }
}
