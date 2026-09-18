import UIKit

/// `Modal`: a hidden on-tree placeholder whose children mount into a
/// presented `UIViewController` while `visible` is true.
public final class PNModalManager: PNComponentManager {
    final class Presentation {
        let controller: UIViewController
        let content: UIView
        init(controller: UIViewController, content: UIView) {
            self.controller = controller
            self.content = content
        }
    }

    public override func makeView(props: [String: Any]) -> UIView {
        let placeholder = UIView(frame: .zero)
        placeholder.isHidden = true
        return placeholder
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let state = PNViewState.existing(for: view) else { return }
        let visible = PNProps.bool(PNProps.value(state.props, "visible")) ?? false
        let presented = state.extras["modal"] is Presentation
        if visible, !presented {
            present(view, state)
        } else if !visible, presented {
            dismiss(view, state, emit: true)
        }
    }

    public override func teardown(view: UIView) {
        if let state = PNViewState.existing(for: view), state.extras["modal"] is Presentation {
            dismiss(view, state, emit: false)
        }
    }

    public override func childContainer(for view: UIView) -> UIView {
        guard let state = PNViewState.existing(for: view), let modal = state.extras["modal"] as? Presentation else {
            return view
        }
        return modal.content
    }

    /// The children stay mounted while the modal is hidden (Python keeps
    /// them in the tree), so the manager keeps their order and moves all
    /// of them into every presentation's content view.
    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        guard let state = PNViewState.existing(for: parent) else {
            super.insertChild(parent: parent, child: child, index: index)
            return
        }
        var children = (state.extras["modal_children"] as? [UIView]) ?? []
        children.removeAll { $0 === child }
        children.insert(child, at: max(0, min(index, children.count)))
        state.extras["modal_children"] = children
        if state.extras["modal"] is Presentation {
            super.insertChild(parent: parent, child: child, index: index)
        }
    }

    public override func removeChild(parent: UIView, child: UIView) {
        // A hidden modal's children still sit in the last presentation's content view.
        super.removeChild(parent: parent, child: child)
        if let state = PNViewState.existing(for: parent), var children = state.extras["modal_children"] as? [UIView] {
            children.removeAll { $0 === child }
            state.extras["modal_children"] = children
        }
    }

    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {}

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize { .zero }

    private func present(_ placeholder: UIView, _ state: PNViewState) {
        let props = state.props
        let controller = PNModalViewController()
        controller.placeholder = placeholder
        controller.onDismissed = { [weak placeholder] in
            guard let placeholder = placeholder, let state = PNViewState.existing(for: placeholder),
                  state.extras["modal"] is Presentation
            else { return }
            state.extras.removeValue(forKey: "modal")
            PNEvents.emit(placeholder, "on_dismiss")
        }
        let style = PNProps.string(PNProps.value(props, "presentation_style")) ?? "page_sheet"
        let isOverlay = style == "overlay" || PNProps.bool(PNProps.value(props, "transparent")) == true
        let content = UIView(frame: controller.view.bounds)
        content.backgroundColor = isOverlay ? .clear : PNColor.parse(PNProps.value(props, "background_color")) ?? .systemBackground
        content.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        controller.view.addSubview(content)
        controller.view.backgroundColor = isOverlay ? UIColor.black.withAlphaComponent(0.4) : content.backgroundColor
        switch isOverlay ? "overlay" : style {
        case "full_screen": controller.modalPresentationStyle = .fullScreen
        case "form_sheet": controller.modalPresentationStyle = .formSheet
        case "overlay": controller.modalPresentationStyle = .overCurrentContext
        default: controller.modalPresentationStyle = .pageSheet
        }
        switch PNProps.string(PNProps.value(props, "animation_type")) ?? PNProps.string(PNProps.value(props, "animation")) {
        case "fade": controller.modalTransitionStyle = .crossDissolve
        case "flip": controller.modalTransitionStyle = .flipHorizontal
        default: controller.modalTransitionStyle = .coverVertical
        }
        let backdropCloses = PNProps.bool(PNProps.value(props, "dismiss_on_backdrop")) != false
        if !isOverlay, !backdropCloses {
            controller.isModalInPresentation = true
        }
        if isOverlay, backdropCloses {
            // A tap on the dimmed backdrop, outside every child, asks to close.
            let tap = UITapGestureRecognizer(target: controller, action: #selector(PNModalViewController.backdropTapped))
            tap.cancelsTouchesInView = false
            tap.delegate = controller
            content.addGestureRecognizer(tap)
            controller.backdrop = content
        }
        // `status_bar_translucent` is Android-only and ignored here.
        controller.presentationController?.delegate = controller
        let presentation = Presentation(controller: controller, content: content)
        state.extras["modal"] = presentation
        // Each presentation builds a new content view; move every child into
        // it, including children the previous presentation showed.
        for child in (state.extras["modal_children"] as? [UIView]) ?? [] {
            child.translatesAutoresizingMaskIntoConstraints = true
            content.addSubview(child)
        }
        let animated = PNProps.string(PNProps.value(props, "animation_type")) != "none"
        guard let top = PNWindow.topViewController() else {
            state.extras.removeValue(forKey: "modal")
            return
        }
        top.present(controller, animated: animated) { [weak placeholder] in
            if let placeholder = placeholder { PNEvents.emit(placeholder, "on_show") }
        }
    }

    private func dismiss(_ placeholder: UIView, _ state: PNViewState, emit: Bool) {
        guard let modal = state.extras.removeValue(forKey: "modal") as? Presentation else { return }
        (modal.controller as? PNModalViewController)?.onDismissed = nil
        let animated = PNProps.string(PNProps.value(state.props, "animation_type")) != "none"
        modal.controller.dismiss(animated: animated)
        if emit { PNEvents.emit(placeholder, "on_dismiss") }
    }
}

/// Owns the sheet's interactive dismissal. A pull-down never dismisses
/// the modal by itself: `visible` is Python's. When `on_request_close`
/// is wired the pull-down reports it (Python then sets `visible=False`);
/// when it isn't, the sheet bounces back and stays presented. An overlay's
/// backdrop tap reports the same way.
final class PNModalViewController: UIViewController, UIAdaptivePresentationControllerDelegate, UIGestureRecognizerDelegate {
    var onDismissed: (() -> Void)?
    weak var placeholder: UIView?
    /// The overlay content view whose empty area counts as the backdrop.
    weak var backdrop: UIView?

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed || presentingViewController == nil {
            onDismissed?()
        }
    }

    func presentationControllerShouldDismiss(_ presentationController: UIPresentationController) -> Bool {
        // UIKit follows a refusal with `presentationControllerDidAttemptToDismiss`,
        // which reports the request; reporting here too would send it twice.
        false
    }

    func presentationControllerDidAttemptToDismiss(_ presentationController: UIPresentationController) {
        // `dismiss_on_backdrop=False` locks the sheet; its pull-down isn't a request.
        if !isModalInPresentation { requestClose() }
    }

    @objc func backdropTapped() {
        requestClose()
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        guard let backdrop = backdrop else { return false }
        return isBackdrop(touch.location(in: backdrop))
    }

    /// Whether `point`, in the backdrop's coordinates, misses every visible child.
    func isBackdrop(_ point: CGPoint) -> Bool {
        guard let backdrop = backdrop else { return false }
        return !backdrop.subviews.contains { !$0.isHidden && $0.frame.contains(point) }
    }

    /// Ask Python to close (`on_request_close`), if the app listens.
    @discardableResult
    func requestClose() -> Bool {
        guard let placeholder = placeholder, PNViewState.existing(for: placeholder)?.hasEvent("on_request_close") == true else { return false }
        PNComponentEvents.Modal.on_request_close(placeholder)
        return true
    }
}

/// Overlay view that only claims touches landing on one of its subviews.
final class PNPortalView: UIView {
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        for sub in subviews where !sub.isHidden && sub.alpha > 0.01 && sub.isUserInteractionEnabled {
            if sub.frame.contains(point) { return true }
        }
        return false
    }
}

/// `Portal`: floats children over the screen in a top-level overlay that
/// mirrors the screen host's root frame.
public final class PNPortalManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let overlay = PNPortalView(frame: .zero)
        overlay.backgroundColor = .clear
        return overlay
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        PNViewStyler.applyCommon(view, props)
        if !initial { ensureAttached(view) }
    }

    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        ensureAttached(parent)
        super.insertChild(parent: parent, child: child, index: index)
    }

    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {}

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize { .zero }

    private func ensureAttached(_ overlay: UIView) {
        guard let host = PNWindow.topViewController()?.view else { return }
        if overlay.superview === host {
            if host.subviews.last !== overlay {
                host.bringSubviewToFront(overlay)
            }
            syncFrame(overlay, host: host)
            return
        }
        overlay.removeFromSuperview()
        host.addSubview(overlay)
        syncFrame(overlay, host: host)
    }

    static func rootFrame(in host: UIView) -> CGRect {
        let bounds = host.bounds
        let insets = host.safeAreaInsets
        let w = max(0, bounds.width - insets.left - insets.right)
        let h = max(0, bounds.height - insets.top)
        return CGRect(x: insets.left, y: insets.top, width: w, height: h)
    }

    private func syncFrame(_ overlay: UIView, host: UIView) {
        overlay.frame = PNPortalManager.rootFrame(in: host)
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    }
}

/// Process-wide status bar state consulted by `PNViewController`.
public enum PNStatusBarState {
    public static var hidden = false
    public static var style: UIStatusBarStyle = .default
    public static var animation: UIStatusBarAnimation = .fade

    static func refresh() {
        var controller = PNWindow.keyWindow()?.rootViewController
        if let nav = controller as? UINavigationController { controller = nav.topViewController }
        controller?.setNeedsStatusBarAppearanceUpdate()
    }
}

/// `StatusBar`: a global side effect (hidden / style), no on-screen view.
public final class PNStatusBarManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let placeholder = UIView(frame: .zero)
        placeholder.isHidden = true
        return placeholder
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        let typed = try! StatusBarProps(props)

        if let hidden = typed.hidden {
            PNStatusBarState.hidden = hidden
        }
        if let style = typed.bar_style?.rawValue {
            switch style {
            case "light", "light_content": PNStatusBarState.style = .lightContent
            case "dark", "dark_content": PNStatusBarState.style = .darkContent
            default: PNStatusBarState.style = .default
            }
        }
        if let animation = PNProps.string(PNProps.value(props, "animation")) {
            switch animation {
            case "slide": PNStatusBarState.animation = .slide
            case "none": PNStatusBarState.animation = .none
            default: PNStatusBarState.animation = .fade
            }
        }
        // `translucent` is Android-only and ignored here.
        let animated = PNProps.bool(PNProps.value(PNViewState.existing(for: view)?.props ?? props, "animated")) ?? false
        if animated {
            UIView.animate(withDuration: 0.3) { PNStatusBarState.refresh() }
        } else {
            PNStatusBarState.refresh()
        }
    }

    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {}

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize { .zero }
}
