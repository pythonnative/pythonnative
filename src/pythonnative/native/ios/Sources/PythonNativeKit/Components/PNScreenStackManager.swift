import UIKit

private final class PNLogicalScreen: UIView {
    private var lastSize = CGSize.zero
    override func layoutSubviews() {
        super.layoutSubviews()
        if bounds.size != lastSize {
            lastSize = bounds.size
            PNLayout.containerDidLayout()
        }
    }
}

private final class PNLogicalScreenController: UIViewController {
    let screen: UIView
    init(screen: UIView) { self.screen = screen; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func loadView() {
        view = UIView()
        view.addSubview(screen)
        screen.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    }
    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        screen.frame = view.bounds
    }
}

public final class PNScreenManager: PNComponentManager {
    // UINavigationController must detach its outgoing screen as part of the
    // transition. Removing it early prevents UIKit from attaching the destination.
    public override var detachesOnDestroy: Bool { false }
    public override func makeView(props: [String: Any]) -> UIView { PNLogicalScreen(frame: .zero) }
    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        var responder: UIResponder? = view.next
        while let current = responder {
            if let controller = current as? PNLogicalScreenController {
                HostModule.applyOptions(PNViewState.existing(for: view)?.props ?? props, to: controller)
                break
            }
            responder = current.next
        }
    }
    // UIKit owns the controller's content rectangle, including its navigation bar.
    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {}
}

private final class PNLogicalStack: UIView, UINavigationControllerDelegate {
    let navigation = UINavigationController()
    var controllers: [Int64: UIViewController] = [:]
    var order: [Int64] = []
    var applying = false
    var scheduled = false
    override init(frame: CGRect) {
        super.init(frame: frame)
        navigation.delegate = self
        addSubview(navigation.view)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func didMoveToWindow() {
        super.didMoveToWindow()
        guard window != nil, navigation.parent == nil else { return }
        var responder: UIResponder? = superview
        while let current = responder {
            if let parent = current as? UIViewController {
                parent.addChild(navigation)
                navigation.didMove(toParent: parent)
                if !(parent is PNLogicalScreenController) { parent.navigationController?.setNavigationBarHidden(true, animated: false) }
                break
            }
            responder = current.next
        }
    }
    override func layoutSubviews() {
        super.layoutSubviews()
        navigation.view.frame = bounds
    }
    func schedule() {
        guard !scheduled else { return }
        scheduled = true
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.scheduled = false
            if let transition = self.navigation.transitionCoordinator {
                transition.animate(alongsideTransition: nil) { [weak self] _ in self?.schedule() }
                return
            }
            let target = self.order.compactMap { self.controllers[$0] }
            let changed = target != self.navigation.viewControllers
            let options = self.order.last.flatMap { PNViewRegistry.shared.view(for: $0) }.flatMap { PNViewState.existing(for: $0)?.props } ?? [:]
            let animated = changed && self.window != nil && !self.navigation.viewControllers.isEmpty && options["animation"] as? String != "none"
            self.applying = changed
            if changed { self.navigation.setViewControllers(target, animated: animated) }
            if !animated { self.applying = false }
            if let tag = self.order.last, let state = PNViewRegistry.shared.view(for: tag).flatMap({ PNViewState.existing(for: $0) }),
               let controller = self.controllers[tag] { HostModule.applyOptions(state.props, to: controller) }
        }
    }
    func navigationController(_ navigationController: UINavigationController, didShow viewController: UIViewController, animated: Bool) {
        if applying { applying = false; return }
        if navigation.viewControllers.count < order.count {
            PNEvents.emit(self, "on_native_back", [order.count - navigation.viewControllers.count])
        }
    }
}

/// Native screen presentation without importing or remounting App.
public final class PNScreenStackManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView { PNLogicalStack(frame: .zero) }
    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        guard let stack = parent as? PNLogicalStack, let state = PNViewState.existing(for: child) else { return }
        let controller = stack.controllers[state.tag] ?? PNLogicalScreenController(screen: child)
        controller.edgesForExtendedLayout = []
        controller.title = state.props["title"] as? String
        stack.controllers[state.tag] = controller
        stack.order.removeAll { $0 == state.tag }
        stack.order.insert(state.tag, at: min(index, stack.order.count))
        stack.schedule()
    }
    public override func removeChild(parent: UIView, child: UIView) {
        guard let stack = parent as? PNLogicalStack, let state = PNViewState.existing(for: child) else { return }
        stack.order.removeAll { $0 == state.tag }
        stack.controllers.removeValue(forKey: state.tag)
        stack.schedule()
    }
    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        if name == "restore_stack", let stack = view as? PNLogicalStack { stack.schedule() }
        return nil
    }
    public override func teardown(view: UIView) {
        guard let stack = view as? PNLogicalStack else { return }
        stack.navigation.willMove(toParent: nil)
        stack.navigation.view.removeFromSuperview()
        stack.navigation.removeFromParent()
        stack.controllers.removeAll()
        stack.navigation.delegate = nil
    }
}
