package com.pythonnative.runtime.modules

import android.app.Activity
import android.content.Intent
import com.pythonnative.runtime.bridge.PNRegistry

/**
 * Registers the built-in modules and forwards activity callbacks to
 * the modules that need them. The app's `MainActivity` calls the
 * `on*` hooks; nothing here touches Python directly.
 */
object BuiltinModules {
    val host = HostModule()
    val device = DeviceModule()
    val alert = AlertModule()
    val storage = StorageModule()
    val secureStore = SecureStoreModule()
    val clipboard = ClipboardModule()
    val share = ShareModule()
    val linking = LinkingModule()
    val haptics = HapticsModule()
    val battery = BatteryModule()
    val netInfo = NetInfoModule()
    val appState = AppStateModule()
    val permissions = PermissionsModule()
    val notifications = NotificationsModule()
    val camera = CameraModule()
    val location = LocationModule()
    val biometrics = BiometricsModule()
    val assets = AssetsModule()
    val images = ImagesModule()

    private val all: List<NativeModule> = listOf(
        host,
        com.pythonnative.generated.DeviceModuleAdapter(device),
        com.pythonnative.generated.AlertModuleAdapter(alert),
        com.pythonnative.generated.StorageModuleAdapter(storage),
        com.pythonnative.generated.SecureStoreModuleAdapter(secureStore),
        com.pythonnative.generated.ClipboardModuleAdapter(clipboard),
        com.pythonnative.generated.ShareModuleAdapter(share),
        com.pythonnative.generated.LinkingModuleAdapter(linking),
        com.pythonnative.generated.HapticsModuleAdapter(haptics),
        com.pythonnative.generated.BatteryModuleAdapter(battery),
        com.pythonnative.generated.NetInfoModuleAdapter(netInfo),
        com.pythonnative.generated.AppStateModuleAdapter(appState),
        com.pythonnative.generated.PermissionsModuleAdapter(permissions),
        com.pythonnative.generated.NotificationsModuleAdapter(notifications),
        com.pythonnative.generated.CameraModuleAdapter(camera),
        com.pythonnative.generated.LocationModuleAdapter(location),
        com.pythonnative.generated.BiometricsModuleAdapter(biometrics),
        com.pythonnative.generated.AssetsModuleAdapter(assets),
        com.pythonnative.generated.ImagesModuleAdapter(images),
    )

    fun register(registry: PNRegistry) {
        for (module in all) registry.registerModule { module }
    }

    /** Called from `PNBridge.setContext`; starts the observers that need a context. */
    fun onContextAttached(activity: Activity) {
        com.pythonnative.runtime.assets.PNAssets.attach(activity)
        battery.attach(activity)
        netInfo.attach(activity)
        activity.intent?.dataString?.let { linking.onDeepLink(it) }
    }

    /** Forward `Activity.onActivityResult`. Returns `true` when a module consumed it. */
    fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?): Boolean =
        camera.onActivityResult(requestCode, resultCode, data) || share.onActivityResult(requestCode)

    /** Forward `Activity.onRequestPermissionsResult`. Returns `true` when a module consumed it. */
    fun onRequestPermissionsResult(
        requestCode: Int,
        @Suppress("UNUSED_PARAMETER") permissionNames: Array<out String>,
        grantResults: IntArray,
    ): Boolean = permissions.onRequestPermissionsResult(requestCode, grantResults)

    /** Forward `Activity.onNewIntent` (deep links). */
    fun onNewIntent(intent: Intent?) {
        intent?.dataString?.let { linking.onDeepLink(it) }
    }

    /** Forward activity lifecycle transitions to the `AppState` module. */
    fun onActivityResumed() = appState.transition("active")
    fun onActivityPaused() = appState.transition("inactive")
    fun onActivityStopped() = appState.transition("background")

    /** Release observers when the activity is destroyed. */
    fun onActivityDestroyed(activity: Activity) {
        battery.detach(activity)
        netInfo.detach(activity)
    }
}
