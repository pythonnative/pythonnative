import UIKit

/// `Host`: screen root attachment, stack navigation, viewport queries,
/// and the main-queue pump.
public final class HostModule: PNNativeModule {
    public static let name = "Host"

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
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
            HostModule.applyOptions(PNProps.dict(args["options"]) ?? [:], to: controller)
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

}
