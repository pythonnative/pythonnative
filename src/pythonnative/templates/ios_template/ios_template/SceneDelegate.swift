//
//  SceneDelegate.swift
//  ios_template
//
//  Creates the window programmatically and forwards scene-level events
//  (deep links, foreground/background transitions) to the Python side.
//

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
        // Python is running; PythonRuntime buffers it and flushes after
        // startup so Linking.get_initial_url() sees it.
        for context in connectionOptions.urlContexts {
            PythonRuntime.shared.deliverURL(context.url.absoluteString)
        }
        let window = UIWindow(windowScene: windowScene)
        let root = ViewController()
        let nav = UINavigationController(rootViewController: root)
        window.rootViewController = nav
        self.window = window
        window.makeKeyAndVisible()
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        for context in URLContexts {
            PythonRuntime.shared.deliverURL(context.url.absoluteString)
        }
    }

    // MARK: - AppState forwarding

    private func dispatchAppState(_ state: String) {
        guard PythonRuntime.shared.started else { return }
        PythonRuntime.shared.notify(
            module: "pythonnative.native_modules.app_state", function: "dispatch_app_state", state
        )
    }

    func sceneDidBecomeActive(_ scene: UIScene) {
        dispatchAppState("active")
    }

    func sceneWillResignActive(_ scene: UIScene) {
        dispatchAppState("inactive")
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        dispatchAppState("inactive")
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        dispatchAppState("background")
    }

    func sceneDidDisconnect(_ scene: UIScene) {}
}
