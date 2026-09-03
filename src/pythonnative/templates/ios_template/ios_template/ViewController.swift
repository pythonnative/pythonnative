//
//  ViewController.swift
//  ios_template
//
//  Hosts one PythonNative screen. Python is initialized through
//  PythonRuntime (linked CPython, no PythonKit); a bootstrap failure
//  shows a full-screen error report instead of a silent fallback.
//

import UIKit

class ViewController: UIViewController {
    // Optional keys for dynamic screen navigation. Push navigation sets
    // these before presenting the controller; nil means the app's entry
    // module (Info.plist `PNEntryModule`, default "app.main").
    @objc dynamic var requestedScreenPath: String? = nil
    @objc dynamic var requestedScreenArgsJSON: String? = nil

    private var screen: PyRef? = nil
    #if DEBUG
    private var hotReloadTimer: Timer? = nil
    #endif

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground

        do {
            try PythonRuntime.shared.ensureStarted()
        } catch {
            showBootstrapError("Python failed to start.\n\n\(error)")
            return
        }

        // PythonNative's convention is "import the module and grab its
        // top-level `App` attribute". The entry module comes from
        // `app.entry_point` in pythonnative.toml (written to Info.plist as
        // `PNEntryModule` by `pn build`); push navigation overrides it via
        // `requestedScreenPath`.
        let entryModule = Bundle.main.object(forInfoDictionaryKey: "PNEntryModule") as? String
        let screenPath: String = requestedScreenPath ?? entryModule ?? "app.main"
        let addr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
        do {
            let screen: PyRef
            if let argsJSON = requestedScreenArgsJSON {
                screen = try PythonRuntime.shared.call(
                    module: "pythonnative.hosts", function: "create_screen", screenPath, addr, argsJSON
                )
            } else {
                screen = try PythonRuntime.shared.call(
                    module: "pythonnative.hosts", function: "create_screen", screenPath, addr
                )
            }
            self.screen = screen
            #if DEBUG
            let devRoot = "\(NSHomeDirectory())/Documents/pythonnative_dev"
            try screen.call("enable_hot_reload", "\(devRoot)/reload.json", devRoot)
            #endif
            try screen.call("on_create")
            #if DEBUG
            startHotReloadPolling()
            #endif
        } catch {
            showBootstrapError("The PythonNative screen failed to mount.\n\n\(error)")
        }
    }

    // MARK: - Lifecycle forwarding

    private func forwardLifecycle(_ event: String) {
        guard screen != nil else { return }
        let addr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
        PythonRuntime.shared.notify(
            module: "pythonnative.hosts", function: "forward_lifecycle", addr, event
        )
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        forwardLifecycle("on_start")
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        // The root view's safeAreaInsets are only valid after iOS has
        // positioned the view in its window; forward every layout pass
        // to Python so the reconciler can re-run layout against the
        // correct viewport (initial mount, rotation, multitasking, etc.).
        forwardLifecycle("on_layout")
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        forwardLifecycle("on_resume")
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        forwardLifecycle("on_pause")
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        forwardLifecycle("on_stop")
    }

    override func encodeRestorableState(with coder: NSCoder) {
        super.encodeRestorableState(with: coder)
        forwardLifecycle("on_save_instance_state")
    }

    override func decodeRestorableState(with coder: NSCoder) {
        super.decodeRestorableState(with: coder)
        forwardLifecycle("on_restore_instance_state")
    }

    deinit {
        #if DEBUG
        hotReloadTimer?.invalidate()
        #endif
        if screen != nil {
            let addr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            PythonRuntime.shared.notify(
                module: "pythonnative.hosts", function: "forward_lifecycle", addr, "on_destroy"
            )
        }
    }

    // MARK: - Hot reload (dev builds only)

    #if DEBUG
    private func startHotReloadPolling() {
        hotReloadTimer?.invalidate()
        hotReloadTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let screen = self?.screen else { return }
            do {
                try screen.call("hot_reload_tick")
            } catch {
                NSLog("[PN] hot_reload_tick failed: \(error)")
            }
        }
    }
    #endif

    // MARK: - Bootstrap error UI

    private func showBootstrapError(_ message: String) {
        NSLog("[PN] %@", message)
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
