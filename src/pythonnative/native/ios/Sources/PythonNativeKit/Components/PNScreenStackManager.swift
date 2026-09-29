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

// MARK: - Presentation and animation vocabulary

/// Maps the `Screen` props `presentation`, `animation`, `gesture_enabled`,
/// and `guarded` to UIKit.
///
/// - `presentation`: `card` (push), `modal` (`.pageSheet`),
///   `full_screen_modal` (`.fullScreen`), `form_sheet` (`.formSheet`),
///   `transparent_modal` (`.overFullScreen` with a clear background).
/// - `animation`: `default` / `slide_from_right` (the stock push),
///   `none`, `fade` (cross-dissolve), `slide_from_bottom` (cover vertical
///   for pushes, `.coverVertical` for modals).
/// - `gesture_enabled`: the interactive pop gesture on cards, and
///   `isModalInPresentation` on modal roots. Never both.
/// - `guarded`: Python has a `before_remove` listener on this screen, so
///   native back is refused and Python is asked through `on_native_back`.
enum PNScreenOptions {
    static let modalPresentations: Set<String> = ["modal", "full_screen_modal", "form_sheet", "transparent_modal"]

    static func presentation(_ props: [String: Any]) -> String {
        PNProps.string(props["presentation"]) ?? "card"
    }
    static func isModal(_ props: [String: Any]) -> Bool {
        modalPresentations.contains(presentation(props))
    }
    static func animation(_ props: [String: Any]) -> String {
        PNProps.string(props["animation"]) ?? "default"
    }
    static func animates(_ props: [String: Any]) -> Bool {
        animation(props) != "none"
    }
    static func gestureEnabled(_ props: [String: Any]) -> Bool {
        PNProps.bool(props["gesture_enabled"]) ?? true
    }
    static func isGuarded(_ props: [String: Any]) -> Bool {
        PNProps.bool(props["guarded"]) ?? false
    }

    static func modalStyle(_ presentation: String) -> UIModalPresentationStyle {
        switch presentation {
        case "full_screen_modal": return .fullScreen
        case "form_sheet": return .formSheet
        case "transparent_modal": return .overFullScreen
        default: return .pageSheet
        }
    }

    static func modalTransition(_ animation: String) -> UIModalTransitionStyle {
        animation == "fade" ? .crossDissolve : .coverVertical
    }

    /// The custom push/pop animator for `animation`, or `nil` for UIKit's default slide.
    static func transition(animation: String, operation: UINavigationController.Operation) -> UIViewControllerAnimatedTransitioning? {
        switch animation {
        case "fade": return PNFadeTransition(operation: operation)
        case "slide_from_bottom": return PNSlideFromBottomTransition(operation: operation)
        default: return nil
        }
    }
}

/// Cross-dissolve push/pop.
final class PNFadeTransition: NSObject, UIViewControllerAnimatedTransitioning {
    let operation: UINavigationController.Operation
    init(operation: UINavigationController.Operation) { self.operation = operation }
    func transitionDuration(using context: UIViewControllerContextTransitioning?) -> TimeInterval { 0.3 }
    func animateTransition(using context: UIViewControllerContextTransitioning) {
        guard let fromView = context.view(forKey: .from), let toView = context.view(forKey: .to),
              let toController = context.viewController(forKey: .to) else {
            context.completeTransition(true)
            return
        }
        let container = context.containerView
        toView.frame = context.finalFrame(for: toController)
        if operation == .pop {
            container.insertSubview(toView, belowSubview: fromView)
        } else {
            container.addSubview(toView)
            toView.alpha = 0
        }
        UIView.animate(withDuration: transitionDuration(using: context), delay: 0, options: [.curveEaseInOut], animations: {
            if self.operation == .pop { fromView.alpha = 0 } else { toView.alpha = 1 }
        }, completion: { _ in
            fromView.alpha = 1
            toView.alpha = 1
            context.completeTransition(!context.transitionWasCancelled)
        })
    }
}

/// Cover-vertical push/pop: the screen slides up over its parent and back down.
final class PNSlideFromBottomTransition: NSObject, UIViewControllerAnimatedTransitioning {
    let operation: UINavigationController.Operation
    init(operation: UINavigationController.Operation) { self.operation = operation }
    func transitionDuration(using context: UIViewControllerContextTransitioning?) -> TimeInterval { 0.35 }
    func animateTransition(using context: UIViewControllerContextTransitioning) {
        guard let fromView = context.view(forKey: .from), let toView = context.view(forKey: .to),
              let toController = context.viewController(forKey: .to) else {
            context.completeTransition(true)
            return
        }
        let container = context.containerView
        let final = context.finalFrame(for: toController)
        let offscreen = CGRect(x: final.minX, y: container.bounds.height, width: final.width, height: final.height)
        if operation == .pop {
            toView.frame = final
            container.insertSubview(toView, belowSubview: fromView)
        } else {
            toView.frame = offscreen
            container.addSubview(toView)
        }
        UIView.animate(withDuration: transitionDuration(using: context), delay: 0, options: [.curveEaseOut], animations: {
            if self.operation == .pop {
                fromView.frame = CGRect(x: fromView.frame.minX, y: container.bounds.height, width: fromView.frame.width, height: fromView.frame.height)
            } else {
                toView.frame = final
            }
        }, completion: { _ in
            context.completeTransition(!context.transitionWasCancelled)
        })
    }
}

// MARK: - Navigation controller with a vetoable back button

/// Answers `navigationBar(_:shouldPop:)` from the owning stack. A back
/// button tap on a guarded screen is refused and forwarded to Python; on
/// any other screen the pop runs and `didShow` reports it as usual.
final class PNNavigationController: UINavigationController, UINavigationBarDelegate {
    weak var backHandler: PNBackButtonHandling?
    /// Whether dismissing this modal group animates (its root's `animation`).
    var dismissAnimated = true

    func navigationBar(_ navigationBar: UINavigationBar, shouldPop item: UINavigationItem) -> Bool {
        // A programmatic pop already removed the controller; let the bar follow.
        if viewControllers.count < (navigationBar.items?.count ?? 0) { return true }
        if let handler = backHandler, handler.vetoesBackButton(in: self) {
            // Restore the back button UIKit dimmed when the tap began.
            for subview in navigationBar.subviews where subview.alpha > 0 && subview.alpha < 1 {
                UIView.animate(withDuration: 0.25) { subview.alpha = 1 }
            }
            return false
        }
        DispatchQueue.main.async { [weak self] in self?.popViewController(animated: true) }
        return false
    }
}

protocol PNBackButtonHandling: AnyObject {
    /// `true` refuses the pop (Python has been asked instead).
    func vetoesBackButton(in navigation: UINavigationController) -> Bool
}

// MARK: - The logical stack

private final class PNLogicalStack: UIView, UINavigationControllerDelegate, UIAdaptivePresentationControllerDelegate, PNBackButtonHandling {
    let navigation = PNNavigationController()
    var controllers: [Int64: UIViewController] = [:]
    var order: [Int64] = []
    var applying: Set<ObjectIdentifier> = []
    var modalNavigations: [PNNavigationController] = []
    var modalRoots: [Int64] = []
    var transitioning = false
    var scheduled = false
    /// Set by `restore_stack`: the next synchronization re-applies UIKit's
    /// stack without animation (Python vetoed a native back).
    var restoring = false
    override init(frame: CGRect) {
        super.init(frame: frame)
        navigation.delegate = self
        navigation.backHandler = self
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
    func properties(_ tag: Int64) -> [String: Any] {
        PNViewRegistry.shared.view(for: tag).flatMap { PNViewState.existing(for: $0)?.props } ?? [:]
    }
    func tag(for controller: UIViewController?) -> Int64? {
        guard let controller = controller else { return nil }
        return controllers.first { $0.value === controller }?.key
    }
    func routeGroups() -> [[Int64]] {
        var groups: [[Int64]] = [[]]
        for tag in order {
            if !groups[0].isEmpty, PNScreenOptions.isModal(properties(tag)) { groups.append([]) }
            groups[groups.count - 1].append(tag)
        }
        return groups
    }
    private func groupIndex(of navigationController: UINavigationController) -> Int {
        navigationController === navigation ? 0 : (modalNavigations.firstIndex { $0 === navigationController }.map { $0 + 1 } ?? -1)
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
            outgoing.dismiss(animated: window != nil && outgoing.dismissAnimated && !restoring) { [weak self] in
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
                // A push animates per the incoming screen, a pop per the
                // outgoing one (React Navigation's rule).
                let subject = target.count >= nav.viewControllers.count ? tags.last : tag(for: nav.viewControllers.last)
                let animated = window != nil && !nav.viewControllers.isEmpty && !restoring
                    && subject.map { PNScreenOptions.animates(properties($0)) } == true
                applying.insert(ObjectIdentifier(nav))
                nav.setViewControllers(target, animated: animated)
                if !animated { applying.remove(ObjectIdentifier(nav)) }
            }
            // Every controller carries its own item appearance so a pop
            // reveals the right header without waiting for Python.
            for tag in tags.dropLast() { if let controller = controllers[tag] { HostModule.applyItemAppearance(properties(tag), to: controller) } }
            if let tag = tags.last, let controller = controllers[tag] {
                let props = properties(tag)
                HostModule.applyOptions(props, to: controller)
                applyGestures(nav, group: tags, index: index)
                if index > 0, PNScreenOptions.presentation(properties(tags[0])) == "transparent_modal" {
                    nav.view.backgroundColor = .clear
                    controller.view.backgroundColor = .clear
                }
            }
        }
        if modalNavigations.count < desiredRoots.count, window != nil {
            let index = modalNavigations.count + 1
            let nav = PNNavigationController()
            nav.delegate = self
            nav.backHandler = self
            let tags = groups[index]
            let root = properties(tags[0])
            nav.modalPresentationStyle = PNScreenOptions.modalStyle(PNScreenOptions.presentation(root))
            nav.modalTransitionStyle = PNScreenOptions.modalTransition(PNScreenOptions.animation(root))
            nav.dismissAnimated = PNScreenOptions.animates(root)
            if PNScreenOptions.presentation(root) == "transparent_modal" {
                nav.view.backgroundColor = .clear
            }
            nav.setViewControllers(tags.compactMap { controllers[$0] }, animated: false)
            modalNavigations.append(nav)
            modalRoots.append(desiredRoots[index - 1])
            let presenter = index == 1 ? navigation : modalNavigations[index - 2]
            transitioning = true
            presenter.present(nav, animated: nav.dismissAnimated && !restoring) { [weak self] in
                self?.transitioning = false
                self?.schedule()
                PNLayout.containerDidLayout()
            }
            nav.presentationController?.delegate = self
        }
        restoring = false
    }

    /// `gesture_enabled` drives the pop gesture on cards and
    /// `isModalInPresentation` on modal roots; a guarded card also loses the
    /// pop gesture because UIKit can't wait for Python's answer mid-swipe.
    private func applyGestures(_ nav: UINavigationController, group tags: [Int64], index: Int) {
        guard let top = tags.last else { return }
        let props = properties(top)
        let isModalRoot = index > 0 && tags.count == 1
        if isModalRoot {
            nav.isModalInPresentation = !PNScreenOptions.gestureEnabled(props)
        } else {
            nav.interactivePopGestureRecognizer?.isEnabled = PNScreenOptions.gestureEnabled(props) && !PNScreenOptions.isGuarded(props)
            if index > 0 { nav.isModalInPresentation = !PNScreenOptions.gestureEnabled(properties(tags[0])) }
        }
    }

    // MARK: UINavigationControllerDelegate

    func navigationController(_ navigationController: UINavigationController, willShow viewController: UIViewController, animated: Bool) {
        // Bar-level chrome (tint, hidden state, background) follows the
        // screen about to show, including after a native pop.
        guard let tag = tag(for: viewController) else { return }
        HostModule.applyOptions(properties(tag), to: viewController)
    }

    func navigationController(_ navigationController: UINavigationController, didShow viewController: UIViewController, animated: Bool) {
        if applying.remove(ObjectIdentifier(navigationController)) != nil { return }
        let index = groupIndex(of: navigationController)
        let groups = routeGroups()
        guard index >= 0, index < groups.count else { return }
        let removed = groups[index].count - navigationController.viewControllers.count
        if removed > 0 { PNComponentEvents.ScreenStack.on_native_back(self, Int64(removed)) }
    }

    func navigationController(_ navigationController: UINavigationController, animationControllerFor operation: UINavigationController.Operation,
                              from fromVC: UIViewController, to toVC: UIViewController) -> UIViewControllerAnimatedTransitioning? {
        guard let tag = tag(for: operation == .push ? toVC : fromVC) else { return nil }
        return PNScreenOptions.transition(animation: PNScreenOptions.animation(properties(tag)), operation: operation)
    }

    // MARK: PNBackButtonHandling

    func vetoesBackButton(in navigationController: UINavigationController) -> Bool {
        let index = groupIndex(of: navigationController)
        let groups = routeGroups()
        guard index >= 0, index < groups.count, let top = groups[index].last, PNScreenOptions.isGuarded(properties(top)) else { return false }
        PNComponentEvents.ScreenStack.on_native_back(self, 1)
        return true
    }

    // MARK: UIAdaptivePresentationControllerDelegate

    func presentationControllerShouldDismiss(_ presentationController: UIPresentationController) -> Bool {
        guard let index = modalNavigations.firstIndex(where: { $0 === presentationController.presentedViewController }) else { return true }
        let groups = routeGroups()
        guard index + 1 < groups.count, let top = groups[index + 1].last, PNScreenOptions.isGuarded(properties(top)) else { return true }
        let removed = groups.dropFirst(index + 1).reduce(0) { $0 + $1.count }
        if removed > 0 { PNComponentEvents.ScreenStack.on_native_back(self, Int64(removed)) }
        return false
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
        if name == "restore_stack", let stack = view as? PNLogicalStack {
            // Python vetoed a native back: put UIKit back where Python is,
            // without animation and without another `on_native_back`.
            stack.restoring = true
            stack.schedule()
        }
        return nil
    }
    public override func teardown(view: UIView) {
        guard let stack = view as? PNLogicalStack else { return }
        stack.navigation.dismiss(animated: false)
        for modal in stack.modalNavigations { modal.delegate = nil; modal.presentationController?.delegate = nil; modal.backHandler = nil }
        stack.modalNavigations.removeAll()
        stack.modalRoots.removeAll()
        stack.navigation.willMove(toParent: nil)
        stack.navigation.view.removeFromSuperview()
        stack.navigation.removeFromParent()
        stack.controllers.removeAll()
        stack.navigation.delegate = nil
        stack.navigation.backHandler = nil
    }

    // MARK: - Test hooks

    /// The UIKit navigation controller behind `stack` (root group).
    static func navigationController(of stack: UIView) -> UINavigationController? {
        (stack as? PNLogicalStack)?.navigation
    }
}
