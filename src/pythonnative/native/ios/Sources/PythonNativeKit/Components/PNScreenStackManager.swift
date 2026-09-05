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

public final class PNScreenManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView { PNLogicalScreen(frame: .zero) }
    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        if let controller = view.next as? UIViewController {
            HostModule.applyOptions(PNViewState.existing(for: view)?.props ?? props, to: controller)
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
                parent.navigationController?.setNavigationBarHidden(true, animated: false)
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
            self.applying = true
            self.navigation.setViewControllers(self.order.compactMap { self.controllers[$0] }, animated: false)
            if let tag = self.order.last, let state = PNViewRegistry.shared.view(for: tag).flatMap({ PNViewState.existing(for: $0) }),
               let controller = self.controllers[tag] { HostModule.applyOptions(state.props, to: controller) }
            self.applying = false
        }
    }
    func navigationController(_ navigationController: UINavigationController, didShow viewController: UIViewController, animated: Bool) {
        if !applying && navigation.viewControllers.count < order.count {
            PNEvents.emit(self, "on_native_back", [order.count - navigation.viewControllers.count])
        }
    }
}

/// Native screen presentation without importing or remounting App.
public final class PNScreenStackManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView { PNLogicalStack(frame: .zero) }
    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        guard let stack = parent as? PNLogicalStack, let state = PNViewState.existing(for: child) else { return }
        let controller = stack.controllers[state.tag] ?? UIViewController()
        controller.edgesForExtendedLayout = []
        controller.view = child
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
