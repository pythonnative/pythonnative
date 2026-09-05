import UIKit

/// `Host`: screen root attachment, stack navigation, viewport queries,
/// and the main-queue pump.
public final class HostModule: PNNativeModule {
    public static let name = "Host"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "post":
            DispatchQueue.main.async {
                PNBridge.shared.callPython(kind: "pump", tag: 0, name: "", payload: "")
            }
            promise.resolve(nil)
        case "is_main_thread":
            promise.resolve(Thread.isMainThread)
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
            HostModule.applyOptions(PNProps.dict(args["options"]) ?? [:], to: controller)
            promise.resolve(nil)
        case "push":
            guard let controller = screen(args, promise) else { return }
            let next = HostModule.makeScreen(args, from: controller)
            promise.resolve(HostModule.runNavOp(controller) { nav in nav.pushViewController(next, animated: true) })
        case "pop":
            guard let controller = screen(args, promise) else { return }
            let count = max(1, PNProps.int(args["count"]) ?? 1)
            promise.resolve(HostModule.runNavOp(controller) { nav in
                if count <= 1 {
                    nav.popViewController(animated: true)
                    return
                }
                let controllers = nav.viewControllers
                let target = max(0, controllers.count - 1 - count)
                nav.popToViewController(controllers[target], animated: true)
            })
        case "pop_to_root":
            guard let controller = screen(args, promise) else { return }
            promise.resolve(HostModule.runNavOp(controller) { nav in nav.popToRootViewController(animated: true) })
        case "replace":
            guard let controller = screen(args, promise) else { return }
            let next = HostModule.makeScreen(args, from: controller)
            promise.resolve(HostModule.runNavOp(controller) { nav in
                var controllers = nav.viewControllers
                if let index = controllers.firstIndex(where: { $0 === controller }) {
                    controllers[index] = next
                } else if controllers.isEmpty {
                    controllers = [next]
                } else {
                    controllers[controllers.count - 1] = next
                }
                nav.setViewControllers(controllers, animated: true)
            })
        case "reset":
            guard let controller = screen(args, promise) else { return }
            let specs = ((args["screens"] as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
            let screens = specs.map { HostModule.makeScreen($0, from: controller) }
            promise.resolve(HostModule.runNavOp(controller) { nav in
                guard let root = nav.viewControllers.first else {
                    nav.setViewControllers(screens, animated: true)
                    return
                }
                nav.setViewControllers([root] + screens, animated: true)
            })
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

    /// Build a sibling screen controller of the same class as `source`.
    static func makeScreen(_ args: [String: Any], from source: PNViewController) -> PNViewController {
        let next = type(of: source).init(nibName: nil, bundle: nil)
        next.requestedScreenPath = PNProps.string(args["path"])
        if let screenArgs = args["args"], !(screenArgs is NSNull) {
            next.requestedScreenArgsJSON = (screenArgs as? String) ?? PNJSON.encode(screenArgs)
        }
        if let title = PNProps.string(args["title"]) {
            next.title = title
        }
        if let options = PNProps.dict(args["options"]) {
            applyOptions(options, to: next)
        }
        return next
    }

    static func applyOptions(_ options: [String: Any], to controller: UIViewController) {
        if let title = PNProps.string(options["title"]) {
            controller.title = title
        }
        if let hidden = PNProps.bool(options["header_shown"]) {
            controller.navigationController?.setNavigationBarHidden(!hidden, animated: false)
        }
        if let hidesBack = PNProps.bool(options["hide_back_button"]) {
            controller.navigationItem.hidesBackButton = hidesBack
        }
        if let color = PNColor.parse(options["header_tint_color"]) {
            controller.navigationController?.navigationBar.tintColor = color
        }
        if let color = PNColor.parse(options["header_background_color"]) {
            let appearance = UINavigationBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = color
            controller.navigationItem.standardAppearance = appearance
            controller.navigationItem.scrollEdgeAppearance = appearance
        }
    }

    /// Run `op` on the controller's navigation stack unless a transition
    /// is in flight (UIKit doesn't queue navigation calls). Returns
    /// whether the op ran.
    @discardableResult
    static func runNavOp(_ controller: UIViewController, _ op: (UINavigationController) -> Void) -> Bool {
        guard let nav = controller.navigationController else {
            PNLog.screens.error("navigation requested but the screen is not inside a UINavigationController")
            return false
        }
        if nav.transitionCoordinator != nil {
            PNLog.rateLimited(PNLog.screens, key: "nav-inflight", "navigation op dropped: transition in flight")
            return false
        }
        op(nav)
        return true
    }
}
