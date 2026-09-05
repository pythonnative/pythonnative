import UIKit

/// Hosts one PythonNative screen.
///
/// Lifecycle is forwarded to Python as `callback("host", screenId,
/// event, payload)`: `create` (viewDidLoad), `start`, `layout`,
/// `resume`, `pause`, `stop`, `destroy`, `save_state`, and
/// `restore_state`. Python attaches its root view with
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

    /// The id Python uses to address this screen.
    public private(set) var screenId: Int64 = 0
    /// Whether `create` has been sent (and not refused by a bootstrap error).
    public private(set) var isScreenCreated = false

    private(set) var rootView: UIView?
    private var lastLayoutPayload: String?

    /// `required` so `Host.push` can instantiate the app's subclass dynamically.
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

    /// Called from `viewDidLoad` before the screen is created. Return
    /// `false` (after showing an error) to skip creating the screen.
    open func prepareRuntime() -> Bool {
        true
    }

    /// The screen path used when `requestedScreenPath` is `nil`.
    open var defaultScreenPath: String {
        (Bundle.main.object(forInfoDictionaryKey: "PNEntryModule") as? String) ?? "app.main"
    }

    // MARK: - Lifecycle

    open override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        guard prepareRuntime() else { return }
        guard PNBridge.shared.hasCallback else {
            showBootstrapError("The Python bridge callback is not registered.\n\nImport pythonnative.bridge after starting the interpreter.")
            return
        }
        isScreenCreated = true
        var payload: [String: Any] = [
            "path": requestedScreenPath ?? defaultScreenPath,
            "args": requestedScreenArgsJSON ?? NSNull(),
        ]
        if let restored = restoredStateJSON {
            payload["restored_state"] = restored
        }
        PNBridge.shared.callPython(kind: "host", tag: screenId, name: "create", payload: PNJSON.encode(payload))
        if let restored = restoredStateJSON {
            PNBridge.shared.callPython(kind: "host", tag: screenId, name: "restore_state", payload: restored)
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
        syncRootFrame()
        forward("resume", viewportJSON())
    }

    open override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        forward("pause")
    }

    open override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        forward("stop")
    }

    open override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if previousTraitCollection?.userInterfaceStyle != traitCollection.userInterfaceStyle {
            lastLayoutPayload = nil
            view.setNeedsLayout()
        }
    }

    /// Ask Python for the screen's serialized state (`save_state`).
    @discardableResult
    public func saveState() -> String? {
        guard isScreenCreated else { return nil }
        return PNBridge.shared.callPython(kind: "host", tag: screenId, name: "save_state", payload: "{}")
    }

    /// Hand previously saved state back to Python (`restore_state`).
    public func restoreState(_ json: String) {
        guard isScreenCreated else {
            restoredStateJSON = json
            return
        }
        PNBridge.shared.callPython(kind: "host", tag: screenId, name: "restore_state", payload: json)
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

    /// The `{"width","height","insets","color_scheme"}` payload shared by
    /// `layout`, `resume`, and `Host.viewport`.
    public func viewport() -> [String: Any] {
        var frame = rootFrame
        if frame.width <= 0 || frame.height <= 0 {
            frame = PNWindow.screenBounds()
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
