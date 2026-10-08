import UIKit

/// Hosts one PythonNative screen.
///
/// Lifecycle is forwarded to Python as `callback("host", screenId,
/// event, payload)`: `create` (viewDidLoad, carrying any
/// `restored_state`), `start`, `layout`, `resume`, `pause`, `stop`, and
/// `destroy`. Python attaches its root view with
/// `Host.attach_root`; the controller keeps that view below the top
/// safe-area inset and full-bleed at the bottom. Fast Refresh needs no
/// help from here: the Python dev client reloads modules and refreshes
/// the mounted screens itself.
open class PNViewController: UIViewController {
    /// Dotted path of the screen component (`nil` = the app entry module).
    public var requestedScreenPath: String?
    /// JSON-encoded screen args, or `nil`.
    public var requestedScreenArgsJSON: String?
    /// State JSON to hand to Python right after `create` (from a prior `saveState`).
    public var restoredStateJSON: String?
    public var cachedStateJSON: String?

    /// The id Python uses to address this screen.
    public private(set) var screenId: Int64 = 0
    /// Whether `create` has been sent (and not refused by a bootstrap error).
    public private(set) var isScreenCreated = false

    private(set) var rootView: UIView?
    private var lastLayoutPayload: String?
    /// The app's launch screen, shown until Python attaches the first root.
    private var launchPlaceholder: UIView?
    private var appeared = false

    /// The application host can instantiate its controller subclass dynamically.
    public required override init(nibName nibNameOrNil: String?, bundle nibBundleOrNil: Bundle?) {
        super.init(nibName: nibNameOrNil, bundle: nibBundleOrNil)
        screenId = PNScreenRegistry.shared.register(self)
    }

    public required init?(coder: NSCoder) {
        super.init(coder: coder)
        screenId = PNScreenRegistry.shared.register(self)
    }

    deinit {
        if isScreenCreated {
            PNBridge.shared.callPython(kind: "host", tag: screenId, name: "destroy", payload: "{}")
        }
        PNScreenRegistry.shared.unregister(screenId)
    }

    // MARK: - Subclass hooks

    /// Called from `viewDidLoad` before the screen is created. Call
    /// `completion(true)` once Python can create screens, or show an error
    /// and call `completion(false)`. The app template starts Python on a
    /// background queue at launch, so the main thread never waits for it;
    /// the launch screen stays visible until the first root view arrives.
    open func prepareRuntime(_ completion: @escaping (Bool) -> Void) {
        completion(true)
    }

    /// The screen path used when `requestedScreenPath` is `nil`.
    open var defaultScreenPath: String {
        (Bundle.main.object(forInfoDictionaryKey: "PNEntryModule") as? String) ?? "app.main"
    }

    // MARK: - Lifecycle

    open override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        var ready: Bool?
        prepareRuntime { [weak self] success in
            ready = success
            guard success, let self else { return }
            self.launchPlaceholder?.removeFromSuperview()
            self.launchPlaceholder = nil
            self.createScreen()
        }
        if ready == nil { showLaunchPlaceholder() }
    }

    private func showLaunchPlaceholder() {
        guard rootView == nil, launchPlaceholder == nil,
              let name = Bundle.main.object(forInfoDictionaryKey: "UILaunchStoryboardName") as? String,
              Bundle.main.path(forResource: name, ofType: "storyboardc") != nil,
              let placeholder = UIStoryboard(name: name, bundle: nil).instantiateInitialViewController()?.view
        else { return }
        placeholder.frame = view.bounds
        placeholder.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(placeholder)
        launchPlaceholder = placeholder
    }

    private func createScreen() {
        guard PNBridge.shared.hasCallback else {
            showBootstrapError("The Python bridge callback is not registered.\n\nImport pythonnative.bridge after starting the interpreter.")
            return
        }
        isScreenCreated = true
        // Keyboard height is part of the viewport payload, so every screen
        // keeps the observer running.
        PNKeyboardObserver.shared.start()
        var payload: [String: Any] = [
            "path": requestedScreenPath ?? defaultScreenPath,
            "args": requestedScreenArgsJSON ?? NSNull(),
        ]
        if let restored = restoredStateJSON {
            payload["restored_state"] = restored
        }
        PNBridge.shared.callPython(kind: "host", tag: screenId, name: "create", payload: PNJSON.encode(payload))
        // Python may become ready after UIKit already showed this screen.
        if isViewLoaded, view.window != nil {
            forward("start")
            lastLayoutPayload = nil
            view.setNeedsLayout()
            if appeared { forward("resume", viewportJSON()) }
        }
    }

    open override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        forward("start")
    }

    open override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        syncRootFrame()
        let payload = viewportJSON()
        // Every pass forwards (rotation, multitasking, keyboard), but a
        // pass that changed nothing about the viewport is skipped.
        if payload != lastLayoutPayload {
            lastLayoutPayload = payload
            forward("layout", payload)
        }
    }

    open override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        appeared = true
        syncRootFrame()
        forward("resume", viewportJSON())
    }

    open override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        forward("pause")
    }

    open override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        appeared = false
        forward("stop")
    }

    open override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if previousTraitCollection?.userInterfaceStyle != traitCollection.userInterfaceStyle {
            lastLayoutPayload = nil
            view.setNeedsLayout()
        }
    }

    /// Re-send `layout` when the keyboard frame changed the viewport.
    func keyboardDidChange() {
        guard isViewLoaded else { return }
        let payload = viewportJSON()
        if payload != lastLayoutPayload {
            lastLayoutPayload = payload
            forward("layout", payload)
        }
    }

    /// The screen's latest serialized state, as Python published it
    /// (`Host.set_state`).
    public func saveState() -> String? {
        isScreenCreated ? cachedStateJSON : nil
    }

    /// Restore previously saved state; it reaches Python with `create`.
    public func restoreState(_ json: String) {
        restoredStateJSON = json
    }

    open override var prefersStatusBarHidden: Bool { PNStatusBarState.hidden }
    open override var preferredStatusBarStyle: UIStatusBarStyle { PNStatusBarState.style }
    open override var preferredStatusBarUpdateAnimation: UIStatusBarAnimation { PNStatusBarState.animation }

    private func forward(_ event: String, _ payload: String = "{}") {
        guard isScreenCreated else { return }
        PNBridge.shared.callPython(kind: "host", tag: screenId, name: event, payload: payload)
    }

    // MARK: - Root view

    /// Attach Python's root view (`Host.attach_root`).
    func attachRoot(_ root: UIView) {
        if rootView !== root {
            rootView?.removeFromSuperview()
        }
        rootView = root
        root.translatesAutoresizingMaskIntoConstraints = true
        root.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(root)
        syncRootFrame()
        PNLaunch.firstScreenAttached()
    }

    /// Detach the root view (`Host.detach_root`).
    func detachRoot(_ root: UIView) {
        if root.superview === view {
            root.removeFromSuperview()
        }
        if rootView === root {
            rootView = nil
        }
    }

    /// The frame the root occupies: below the top inset, full-bleed at
    /// the bottom so a tab bar can reach the home indicator.
    public var rootFrame: CGRect {
        let bounds = view.bounds
        let insets = view.safeAreaInsets
        let w = max(0, bounds.width - insets.left - insets.right)
        let h = max(0, bounds.height - insets.top)
        if w > 0, h > 0 {
            return CGRect(x: insets.left, y: insets.top, width: w, height: h)
        }
        return bounds
    }

    private func syncRootFrame() {
        guard let root = rootView else { return }
        let frame = rootFrame
        if root.frame != frame {
            root.frame = frame
        }
    }

    /// The viewport payload shared by `layout`, `resume`, and
    /// `Host.viewport`: `width`, `height`, `insets`, `color_scheme`,
    /// `scale`, `font_scale`, `screen_width`, `screen_height`, and
    /// `keyboard_height`.
    public func viewport() -> [String: Any] {
        var frame = rootFrame
        let screen = PNWindow.screenBounds()
        if frame.width <= 0 || frame.height <= 0 {
            frame = screen
        }
        let insets = view.safeAreaInsets
        return [
            "width": Double(frame.width),
            "height": Double(frame.height),
            "insets": [
                "top": 0.0,
                "left": Double(insets.left),
                "bottom": Double(insets.bottom),
                "right": Double(insets.right),
            ],
            "color_scheme": PNWindow.colorScheme(for: view),
            "scale": Double(PNWindow.screenScale()),
            "font_scale": PNWindow.fontScale(),
            "screen_width": Double(screen.width),
            "screen_height": Double(screen.height),
            "keyboard_height": Double(PNKeyboardObserver.shared.height),
        ]
    }

    func viewportJSON() -> String {
        PNJSON.encode(viewport())
    }

    // MARK: - Bootstrap error UI

    /// Replace the screen with a full-bleed error report.
    public func showBootstrapError(_ message: String) {
        PNLog.screens.error("\(message)")
        let text = UITextView(frame: view.bounds)
        text.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        text.isEditable = false
        text.backgroundColor = UIColor(red: 0.75, green: 0.10, blue: 0.10, alpha: 1.0)
        text.textColor = .white
        text.font = UIFont.monospacedSystemFont(ofSize: 13, weight: .regular)
        text.textContainerInset = UIEdgeInsets(top: 60, left: 16, bottom: 40, right: 16)
        text.text = "PythonNative could not start\n\n\(message)"
        view.addSubview(text)
    }
}

/// Launch timing, logged once: how long the process took to show its first screen.
enum PNLaunch {
    private static var reported = false

    static func firstScreenAttached() {
        guard !reported else { return }
        reported = true
        var info = kinfo_proc()
        var size = MemoryLayout<kinfo_proc>.stride
        var name: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        guard sysctl(&name, 4, &info, &size, nil, 0) == 0 else { return }
        let start = info.kp_proc.p_un.__p_starttime
        let started = Double(start.tv_sec) + Double(start.tv_usec) / 1_000_000
        let elapsed = (Date().timeIntervalSince1970 - started) * 1000
        NSLog("[PN] First screen attached %.0f ms after process start", elapsed)
    }
}
