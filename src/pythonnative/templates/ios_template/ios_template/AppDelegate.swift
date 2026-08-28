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
        return true
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
