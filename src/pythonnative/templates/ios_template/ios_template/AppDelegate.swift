//
//  AppDelegate.swift
//  ios_template
//
//  Application-level callbacks, forwarded to the lifecycle hooks plugins
//  register (see PNAppLifecycle in PythonNativeKit).
//

import PythonNativeKit
import UIKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Python starts beside UIKit's own launch work; the first screen
        // waits for it without blocking the main thread.
        PythonRuntime.shared.startInBackground()
        BatteryModule.startMonitoring()
        PNAppLifecycle.shared.didFinishLaunching(application, options: launchOptions)
        return true
    }

    // MARK: - Remote notifications (APNs)

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        PNAppLifecycle.shared.didRegisterForRemoteNotifications(deviceToken: deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        PNAppLifecycle.shared.didFailToRegisterForRemoteNotifications(error: error)
    }

    func application(
        _ application: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable: Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        PNAppLifecycle.shared.didReceiveRemoteNotification(userInfo, completion: completionHandler)
    }

    func application(
        _ application: UIApplication,
        handleEventsForBackgroundURLSession identifier: String,
        completionHandler: @escaping () -> Void
    ) {
        PNAppLifecycle.shared.handleEventsForBackgroundSession(identifier: identifier, completion: completionHandler)
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
