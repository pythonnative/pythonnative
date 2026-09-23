import UIKit

/// `Host`: screen root attachment, stack navigation, viewport queries,
/// and the main-queue pump.
public final class HostModule: PNNativeModule {
    public static let name = "Host"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "show_error":
            PNErrorOverlay.show(screen: Int64(PNProps.int(args["screen"]) ?? 0), title: args["title"] as? String ?? "Python error", trace: args["trace"] as? String ?? "")
            promise.resolve(nil)
        case "dismiss_error":
            PNErrorOverlay.dismiss()
            promise.resolve(nil)
        case "cache_state":
            guard let controller = screen(args, promise) else { return }
            controller.cachedStateJSON = args["state"] as? String
            promise.resolve(nil)
        case "attach_root":
            guard let controller = screen(args, promise) else { return }
            guard let tag = PNProps.int(args["tag"]), let view = PNViewRegistry.shared.view(for: Int64(tag)) else {
                promise.reject("attach_root: unknown view tag", code: "unknown_tag")
                return
            }
            controller.attachRoot(view)
            promise.resolve(controller.viewport())
        case "detach_root":
            guard let controller = screen(args, promise) else { return }
            if let tag = PNProps.int(args["tag"]), let view = PNViewRegistry.shared.view(for: Int64(tag)) {
                controller.detachRoot(view)
            }
            promise.resolve(nil)
        case "viewport":
            guard let controller = screen(args, promise) else { return }
            promise.resolve(controller.viewport())
        case "set_options":
            guard let controller = screen(args, promise) else { return }
            let options = PNProps.dict(args["options"]) ?? [:]
            HostModule.applyOptions(options, to: controller)
            HostModule.applyGestureOptions(options, to: controller)
            promise.resolve(nil)
        case "finish":
            promise.resolve(nil)
        default:
            promise.reject("Host has no method '\(method)'", code: "unknown_method")
        }
    }

    // MARK: - Helpers

    private func screen(_ args: [String: Any], _ promise: PNPromise) -> PNViewController? {
        guard let id = PNProps.int(args["screen"]) else {
            promise.reject("missing 'screen' id", code: "bad_args")
            return nil
        }
        guard let controller = PNScreenRegistry.shared.controller(for: Int64(id)) else {
            promise.reject("no screen with id \(id)", code: "unknown_screen")
            return nil
        }
        return controller
    }

    /// `gesture_enabled` for a standalone host screen: the interactive pop
    /// gesture when the screen is a card in a navigation controller, or
    /// `isModalInPresentation` when it's presented modally. Never both.
    static func applyGestureOptions(_ options: [String: Any], to controller: UIViewController) {
        let enabled = PNScreenOptions.gestureEnabled(options)
        if PNScreenOptions.isModal(options) || (controller.navigationController == nil && controller.presentingViewController != nil) {
            (controller.navigationController ?? controller).isModalInPresentation = !enabled
        } else {
            controller.navigationController?.interactivePopGestureRecognizer?.isEnabled = enabled
        }
    }

    /// Header and title options shared by native stack screens and `Host.set_options`.
    ///
    /// Bar-level state (hidden, large titles, tint, background) is applied
    /// to the controller's navigation bar; the item-level appearance is
    /// applied through `applyItemAppearance` so every screen in a stack
    /// carries its own header colors. Python always sends
    /// `header_tint_color`, `header_style.background_color`, and
    /// `header_title_style.color` from the navigation theme.
    static func applyOptions(_ options: [String: Any], to controller: UIViewController) {
        controller.title = PNProps.string(options["title"]) ?? ""
        let item = controller.navigationItem
        let navigation = controller.navigationController
        navigation?.setNavigationBarHidden(!(PNProps.bool(options["header_shown"]) ?? true), animated: false)
        item.hidesBackButton = !(PNProps.bool(options["header_back_visible"]) ?? true)
        item.backButtonTitle = PNProps.string(options["header_back_title"])
        let large = PNProps.bool(options["header_large_title"]) ?? false
        navigation?.navigationBar.prefersLargeTitles = large
        item.largeTitleDisplayMode = large ? .always : .never
        if let bar = navigation?.navigationBar {
            bar.tintColor = PNColor.parse(options["header_tint_color"])
            let barStyle = PNProps.dict(options["header_style"]) ?? [:]
            bar.barTintColor = PNColor.parse(barStyle["background_color"])
            let appearance = headerAppearance(options)
            bar.standardAppearance = appearance
            bar.scrollEdgeAppearance = appearance
            bar.compactAppearance = appearance
        }
        applyItemAppearance(options, to: controller)
    }

    /// The per-screen navigation item appearance (background and title colors).
    static func applyItemAppearance(_ options: [String: Any], to controller: UIViewController) {
        let appearance = headerAppearance(options)
        let item = controller.navigationItem
        item.standardAppearance = appearance
        item.scrollEdgeAppearance = appearance
        item.compactAppearance = appearance
    }

    /// `header_style.background_color` and `header_title_style` as a bar appearance.
    static func headerAppearance(_ options: [String: Any]) -> UINavigationBarAppearance {
        let appearance = UINavigationBarAppearance()
        appearance.configureWithDefaultBackground()
        let barStyle = PNProps.dict(options["header_style"]) ?? [:]
        if let color = PNColor.parse(barStyle["background_color"]) {
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = color
        }
        let titleStyle = PNProps.dict(options["header_title_style"]) ?? [:]
        var attributes: [NSAttributedString.Key: Any] = [:]
        if let color = PNColor.parse(titleStyle["color"]) { attributes[.foregroundColor] = color }
        if titleStyle["font_size"] != nil || titleStyle["bold"] != nil || titleStyle["font_weight"] != nil {
            attributes[.font] = PNTextManager.font(from: titleStyle, base: nil)
        }
        appearance.titleTextAttributes = attributes
        appearance.largeTitleTextAttributes = attributes
        return appearance
    }
}
