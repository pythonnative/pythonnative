import UIKit

private final class PNLogicalScreen: UIView {
    var headerSlots: [String: UIView] = [:]
    weak var controller: PNLogicalScreenController?
    func applySlots() {
        controller?.navigationItem.leftBarButtonItem = headerSlots["left"].map { UIBarButtonItem(customView: $0) }
        controller?.navigationItem.rightBarButtonItem = headerSlots["right"].map { UIBarButtonItem(customView: $0) }
    }
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
    init(screen: UIView) {
        self.screen = screen; super.init(nibName: nil, bundle: nil)
        (screen as? PNLogicalScreen)?.controller = self
        (screen as? PNLogicalScreen)?.applySlots()
    }
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
                (controller.navigationController?.delegate as? PNLogicalStack)?.schedule()
                break
            }
            responder = current.next
        }
    }
    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        if let screen = parent as? PNLogicalScreen, let side = PNViewState.existing(for: child)?.props["_pn_header_slot"] as? String {
            screen.headerSlots[side] = child
            screen.applySlots()
        } else { super.insertChild(parent: parent, child: child, index: index) }
    }
    public override func removeChild(parent: UIView, child: UIView) {
        if let screen = parent as? PNLogicalScreen, let side = screen.headerSlots.first(where: { $0.value === child })?.key {
            screen.headerSlots.removeValue(forKey: side)
            screen.applySlots()
        }
        super.removeChild(parent: parent, child: child)
    }
    // UIKit owns the controller's content rectangle, including its navigation bar.
    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {}
}

private final class PNLogicalStack: UIView, UINavigationControllerDelegate, UIAdaptivePresentationControllerDelegate {
    let navigation = UINavigationController()
    var controllers: [Int64: UIViewController] = [:]
    var order: [Int64] = []
    var applying: Set<ObjectIdentifier> = []
    var modalNavigations: [UINavigationController] = []
    var modalRoots: [Int64] = []
    var transitioning = false
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
        var responder: UIResponder? = next
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
            self.synchronize()
        }
    }
    private func properties(_ tag: Int64) -> [String: Any] {
        PNViewRegistry.shared.view(for: tag).flatMap { PNViewState.existing(for: $0)?.props } ?? [:]
    }
    private func routeGroups() -> [[Int64]] {
        var groups: [[Int64]] = [[]]
        for tag in order {
            if !groups[0].isEmpty, properties(tag)["presentation"] as? String == "modal" { groups.append([]) }
            groups[groups.count - 1].append(tag)
        }
        return groups
    }
    private func synchronize() {
        guard !transitioning else { return }
        let groups = routeGroups()
        let desiredRoots = groups.dropFirst().compactMap { $0.first }
        var common = 0
        while common < min(modalRoots.count, desiredRoots.count), modalRoots[common] == desiredRoots[common] { common += 1 }
        if common < modalNavigations.count {
            let outgoing = modalNavigations[common]
            modalNavigations.removeSubrange(common...)
            modalRoots.removeSubrange(common...)
            transitioning = true
            outgoing.dismiss(animated: window != nil) { [weak self] in
                self?.transitioning = false
                self?.schedule()
            }
            return
        }
        for (index, tags) in groups.enumerated() {
            if index > modalNavigations.count { break }
            let nav = index == 0 ? navigation : modalNavigations[index - 1]
            if let transition = nav.transitionCoordinator {
                transition.animate(alongsideTransition: nil) { [weak self] _ in self?.schedule() }
                return
            }
            let target = tags.compactMap { controllers[$0] }
            if target != nav.viewControllers {
                let animated = window != nil && !nav.viewControllers.isEmpty && tags.last.map { properties($0)["animation"] as? String != "none" } == true
                applying.insert(ObjectIdentifier(nav))
                nav.setViewControllers(target, animated: animated)
                if !animated { applying.remove(ObjectIdentifier(nav)) }
            }
            if let tag = tags.last, let controller = controllers[tag] {
                HostModule.applyOptions(properties(tag), to: controller)
                nav.isModalInPresentation = !(properties(tag)["gesture_enabled"] as? Bool ?? true)
            }
        }
        if modalNavigations.count < desiredRoots.count, window != nil {
            let index = modalNavigations.count + 1
            let nav = UINavigationController()
            nav.delegate = self
            nav.modalPresentationStyle = .pageSheet
            let tags = groups[index]
            nav.setViewControllers(tags.compactMap { controllers[$0] }, animated: false)
            modalNavigations.append(nav)
            modalRoots.append(desiredRoots[index - 1])
            let presenter = index == 1 ? navigation : modalNavigations[index - 2]
            transitioning = true
            presenter.present(nav, animated: properties(tags[0])["animation"] as? String != "none") { [weak self] in
                self?.transitioning = false
                self?.schedule()
                PNLayout.containerDidLayout()
            }
            nav.presentationController?.delegate = self
        }
    }
    func navigationController(_ navigationController: UINavigationController, didShow viewController: UIViewController, animated: Bool) {
        if applying.remove(ObjectIdentifier(navigationController)) != nil { return }
        let index = navigationController === navigation ? 0 : (modalNavigations.firstIndex { $0 === navigationController }.map { $0 + 1 } ?? -1)
        let groups = routeGroups()
        guard index >= 0, index < groups.count else { return }
        let removed = groups[index].count - navigationController.viewControllers.count
        if removed > 0 { PNComponentEvents.ScreenStack.on_native_back(self, Int64(removed)) }
    }
    func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
        guard let index = modalNavigations.firstIndex(where: { $0 === presentationController.presentedViewController }) else { return }
        let groups = routeGroups()
        let removed = groups.dropFirst(index + 1).reduce(0) { $0 + $1.count }
        modalNavigations.removeSubrange(index...)
        modalRoots.removeSubrange(index...)
        if removed > 0 { PNComponentEvents.ScreenStack.on_native_back(self, Int64(removed)) }
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
        stack.navigation.dismiss(animated: false)
        for modal in stack.modalNavigations { modal.delegate = nil; modal.presentationController?.delegate = nil }
        stack.modalNavigations.removeAll()
        stack.modalRoots.removeAll()
        stack.navigation.willMove(toParent: nil)
        stack.navigation.view.removeFromSuperview()
        stack.navigation.removeFromParent()
        stack.controllers.removeAll()
        stack.navigation.delegate = nil
    }
}
