//
//  AppDelegate.swift
//  ios_template
//
//  Application-level callbacks. Remote-notification registration
//  results are forwarded to pythonnative.native_modules.notifications,
//  which resolves the awaitable returned by
//  Notifications.get_device_token().
//

import UIKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        registerBatteryObservers()
        return true
    }

    // MARK: - Battery forwarding

    // UIDevice only posts battery notifications while monitoring is on;
    // Battery.add_listener subscribers receive {"level", "state"}.
    private func registerBatteryObservers() {
        UIDevice.current.isBatteryMonitoringEnabled = true
        let center = NotificationCenter.default
        for name in [UIDevice.batteryLevelDidChangeNotification, UIDevice.batteryStateDidChangeNotification] {
            center.addObserver(forName: name, object: nil, queue: .main) { _ in
                self.dispatchBattery()
            }
        }
    }

    private func dispatchBattery() {
        guard PythonRuntime.shared.started else { return }
        let device = UIDevice.current
        let state: String
        switch device.batteryState {
        case .unplugged: state = "unplugged"
        case .charging: state = "charging"
        case .full: state = "full"
        default: state = "unknown"
        }
        PythonRuntime.shared.notify(
            module: "pythonnative.native_modules.battery",
            function: "dispatch_battery",
            Double(device.batteryLevel),
            state
        )
    }

    // MARK: - Remote notifications (APNs)

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        guard PythonRuntime.shared.started else { return }
        PythonRuntime.shared.notify(
            module: "pythonnative.native_modules.notifications",
            function: "dispatch_device_token",
            token
        )
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        guard PythonRuntime.shared.started else { return }
        PythonRuntime.shared.notify(
            module: "pythonnative.native_modules.notifications",
            function: "dispatch_device_token_error",
            String(describing: error)
        )
    }

    // MARK: - UISceneSession lifecycle

    func application(
        _ application: UIApplication,
        configurationForConnecting connectingSceneSession: UISceneSession,
        options: UIScene.ConnectionOptions
    ) -> UISceneConfiguration {
        return UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
    }

    func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {}
}
