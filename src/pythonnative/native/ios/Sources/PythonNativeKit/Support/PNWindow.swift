import UIKit

/// Window and presenter lookups shared by modals, alerts, pickers, and portals.
public enum PNWindow {
    /// The app's key window (scene-based lookup, no deprecated APIs).
    public static func keyWindow() -> UIWindow? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        for scene in scenes where scene.activationState == .foregroundActive {
            if let window = scene.windows.first(where: { $0.isKeyWindow }) { return window }
        }
        for scene in scenes {
            if let window = scene.windows.first(where: { $0.isKeyWindow }) { return window }
        }
        return scenes.first?.windows.first
    }

    /// Bounds of the main screen (or `.zero` when no scene is connected).
    public static func screenBounds() -> CGRect {
        if let window = keyWindow() {
            return window.windowScene?.screen.bounds ?? window.bounds
        }
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        return scenes.first?.screen.bounds ?? .zero
    }

    /// The display scale of the main screen.
    public static func screenScale() -> CGFloat {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        return scenes.first?.screen.scale ?? 2.0
    }

    /// The topmost view controller suitable for presenting alerts and sheets.
    public static func topViewController() -> UIViewController? {
        guard var top = keyWindow()?.rootViewController else { return nil }
        if let nav = top as? UINavigationController, let visible = nav.visibleViewController {
            top = visible
        } else if let tabs = top as? UITabBarController, let selected = tabs.selectedViewController {
            top = selected
        }
        while let presented = top.presentedViewController {
            top = presented
        }
        return top
    }

    /// Current system appearance as `"light"` or `"dark"`.
    public static func colorScheme(for view: UIView? = nil) -> String {
        let traits = view?.traitCollection ?? keyWindow()?.traitCollection ?? UITraitCollection.current
        return traits.userInterfaceStyle == .dark ? "dark" : "light"
    }
}
