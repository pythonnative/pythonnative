import UIKit

/// Application events a plugin can observe, the counterpart of
/// `ExpoAppDelegateSubscriber`. Every method has a default that does nothing,
/// so a hook implements only what it needs. Register one from a plugin's
/// `register(into:)` with `registry.registerLifecycleHook(_:)`.
///
/// Methods returning `Bool` report whether the hook handled the event.
/// Registration happens before `didFinishLaunching` returns, which is what
/// `UNUserNotificationCenter` delegates and `BGTaskScheduler` need.
public protocol PNAppLifecycleHook: AnyObject {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?)
    func didRegisterForRemoteNotifications(deviceToken: Data)
    func didFailToRegisterForRemoteNotifications(error: Error)
    func didReceiveRemoteNotification(_ userInfo: [AnyHashable: Any], completion: @escaping (UIBackgroundFetchResult) -> Void) -> Bool
    func handleEventsForBackgroundSession(identifier: String, completion: @escaping () -> Void) -> Bool
    func openURL(_ url: URL) -> Bool
    func continueUserActivity(_ activity: NSUserActivity) -> Bool
    func didEnterBackground()
    func willEnterForeground()
}

public extension PNAppLifecycleHook {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {}
    func didRegisterForRemoteNotifications(deviceToken: Data) {}
    func didFailToRegisterForRemoteNotifications(error: Error) {}
    func didReceiveRemoteNotification(_ userInfo: [AnyHashable: Any], completion: @escaping (UIBackgroundFetchResult) -> Void) -> Bool { false }
    func handleEventsForBackgroundSession(identifier: String, completion: @escaping () -> Void) -> Bool { false }
    func openURL(_ url: URL) -> Bool { false }
    func continueUserActivity(_ activity: NSUserActivity) -> Bool { false }
    func didEnterBackground() {}
    func willEnterForeground() {}
}

/// Dispatches the `AppDelegate` and `SceneDelegate` callbacks to every
/// registered hook. The first call forces plugin registration.
public final class PNAppLifecycle {
    public static let shared = PNAppLifecycle()
    private var hooks: [PNAppLifecycleHook] = []

    private init() {}

    func add(_ hook: PNAppLifecycleHook) {
        hooks.append(hook)
    }

    private var registered: [PNAppLifecycleHook] {
        PNRegistry.shared.ensureBuiltins()
        return hooks
    }

    public func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {
        for hook in registered { hook.didFinishLaunching(application, options: options) }
    }

    public func didRegisterForRemoteNotifications(deviceToken: Data) {
        for hook in registered { hook.didRegisterForRemoteNotifications(deviceToken: deviceToken) }
    }

    public func didFailToRegisterForRemoteNotifications(error: Error) {
        for hook in registered { hook.didFailToRegisterForRemoteNotifications(error: error) }
    }

    public func didReceiveRemoteNotification(_ userInfo: [AnyHashable: Any], completion: @escaping (UIBackgroundFetchResult) -> Void) {
        // UIKit allows one completion, but several hooks may handle one push: the
        // first to finish decides, and the rest are ignored.
        var finished = false
        let once: (UIBackgroundFetchResult) -> Void = { result in
            if finished { return }
            finished = true
            completion(result)
        }
        var handled = false
        for hook in registered where hook.didReceiveRemoteNotification(userInfo, completion: once) { handled = true }
        if !handled { once(.noData) }
    }

    public func handleEventsForBackgroundSession(identifier: String, completion: @escaping () -> Void) {
        var finished = false
        let once: () -> Void = {
            if finished { return }
            finished = true
            completion()
        }
        var handled = false
        for hook in registered where hook.handleEventsForBackgroundSession(identifier: identifier, completion: once) { handled = true }
        if !handled { once() }
    }

    /// Whether a hook consumed `url`; otherwise it reaches `Linking`.
    public func openURL(_ url: URL) -> Bool {
        registered.contains { $0.openURL(url) }
    }

    /// Whether a hook consumed `activity`; otherwise a web link reaches `Linking`.
    public func continueUserActivity(_ activity: NSUserActivity) -> Bool {
        registered.contains { $0.continueUserActivity(activity) }
    }

    public func didEnterBackground() {
        for hook in registered { hook.didEnterBackground() }
    }

    public func willEnterForeground() {
        for hook in registered { hook.willEnterForeground() }
    }
}
