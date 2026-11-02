//
//  SceneDelegate.swift
//  ios_template
//
//  Creates the window programmatically and forwards scene-level events
//  (deep links, foreground/background transitions) to the Swift native
//  modules, which relay them to Python over the bridge.
//

import PythonNativeKit
import UIKit

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = (scene as? UIWindowScene) else { return }
        // A cold start from a deep link delivers the URL here, before
        // Python is running; LinkingModule buffers it until the bridge
        // callback is registered so Linking.get_initial_url() sees it.
        for context in connectionOptions.urlContexts {
            deliver(url: context.url)
        }
        for activity in connectionOptions.userActivities {
            deliver(activity: activity)
        }
        // PNWindow opens the dev menu (shake, Cmd+D) once Python enables
        // development support; release builds never enable it.
        let window = PNWindow(windowScene: windowScene)
        let root = ViewController()
        let nav = UINavigationController(rootViewController: root)
        window.rootViewController = nav
        self.window = window
        window.makeKeyAndVisible()
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        for context in URLContexts {
            deliver(url: context.url)
        }
    }

    // A universal link, or any other activity handed to the app.
    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        deliver(activity: userActivity)
    }

    private func deliver(url: URL) {
        if !PNAppLifecycle.shared.openURL(url) {
            LinkingModule.deliver(url: url.absoluteString)
        }
    }

    private func deliver(activity: NSUserActivity) {
        if PNAppLifecycle.shared.continueUserActivity(activity) { return }
        if activity.activityType == NSUserActivityTypeBrowsingWeb, let url = activity.webpageURL {
            LinkingModule.deliver(url: url.absoluteString)
        }
    }

    // MARK: - AppState forwarding

    func sceneDidBecomeActive(_ scene: UIScene) {
        AppStateModule.dispatch("active")
    }

    func sceneWillResignActive(_ scene: UIScene) {
        AppStateModule.dispatch("inactive")
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        AppStateModule.dispatch("inactive")
        PNAppLifecycle.shared.willEnterForeground()
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        AppStateModule.dispatch("background")
        PNAppLifecycle.shared.didEnterBackground()
    }

    func sceneDidDisconnect(_ scene: UIScene) {}
}
