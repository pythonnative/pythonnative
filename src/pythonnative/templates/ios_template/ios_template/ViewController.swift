//
//  ViewController.swift
//  ios_template
//
//  Created by Owen Carey on 6/19/23.
//

import UIKit
// PythonKit isn't available on iOS by default; guard its use so the
// template builds out of the box and falls back to a native label.
#if canImport(PythonKit)
import PythonKit
#endif
#if canImport(Python)
import Python
#endif

#if canImport(PythonKit)
private func drainPythonNativeScheduledRenders() {
    do {
        let pn = try Python.attemptImport("pythonnative.screen")
        _ = try pn.drain_ios_scheduled_renders.throwing.dynamicallyCall(withArguments: [])
    } catch {
        NSLog("[PN] swift.renderScheduler -> drain_ios_scheduled_renders failed: \(error)")
    }
}
#endif

@_cdecl("pn_schedule_render_drain")
public func pn_schedule_render_drain() {
    DispatchQueue.main.async {
        #if canImport(PythonKit)
        drainPythonNativeScheduledRenders()
        #endif
    }
}

class ViewController: UIViewController {
    // Ensure Python.framework is configured only once per process
    private static var hasInitializedPython: Bool = false
    // Optional keys for dynamic screen navigation
    @objc dynamic var requestedScreenPath: String? = nil
    @objc dynamic var requestedScreenArgsJSON: String? = nil
    private var pythonReady: Bool = false
    #if canImport(PythonKit)
    private var screen: PythonObject? = nil
    #endif
    private var hotReloadTimer: Timer? = nil

    override func viewDidLoad() {
        super.viewDidLoad()
        // Ensure a visible background when created programmatically (storyboards set this automatically)
        view.backgroundColor = .systemBackground

        let firstInit = !ViewController.hasInitializedPython

        // Signal to pythonnative that we're running on iOS. Read on the
        // Python side (pythonnative.utils.IS_IOS) to gate iOS-only setup
        // like sys.stdout redirection. Set before Python starts so it's
        // visible to the very first import.
        setenv("PN_PLATFORM", "ios", 1)

        // Configure embedded Python if available in bundle. PYTHONHOME /
        // PYTHONPATH only need to be set once per process, but setting them
        // again is harmless and keeps the flow simple.
        if let resourcePath = Bundle.main.resourcePath {
            let pyStd = "\(resourcePath)/python-stdlib"
            let pyDyn = "\(resourcePath)/python-stdlib/lib-dynload"
            let devRoot = "\(NSHomeDirectory())/Documents/pythonnative_dev"
            var pyPath = "\(devRoot):\(pyStd):\(pyDyn):\(resourcePath):\(resourcePath)/app"
            let platSite = "\(resourcePath)/platform-site"
            if FileManager.default.fileExists(atPath: platSite) {
                pyPath += ":\(platSite)"
            }
            setenv("PYTHONHOME", pyStd, 1)
            setenv("PYTHONPATH", pyPath, 1)
        }
        #if canImport(PythonKit)
        // Ensure PythonKit knows where to load the Python library from when using an embedded framework.
        if let bundlePath = Bundle.main.bundlePath as String? {
            let frameworkLib = "\(bundlePath)/Frameworks/Python.framework/Python"
            setenv("PYTHON_LIBRARY", frameworkLib, 1)
            if FileManager.default.fileExists(atPath: frameworkLib) {
                if firstInit {
                    PythonLibrary.useLibrary(at: frameworkLib)
                    ViewController.hasInitializedPython = true
                }
                pythonReady = true
            } else {
                NSLog("[PN] Embedded Python library not found at: \(frameworkLib)")
            }
        }
        let sys = Python.import("sys")
        if firstInit {
            // One concise bootstrap line per process; per-screen detail is left
            // to Python-side print() statements streamed via pn run ios.
            let shortVersion = "\(sys.version)".split(separator: "\n").first.map(String.init) ?? "\(sys.version)"
            NSLog("[PN] Python \(shortVersion) initialized")
        }
        if let resourcePath = Bundle.main.resourcePath {
            let devRoot = "\(NSHomeDirectory())/Documents/pythonnative_dev"
            sys.path.insert(0, devRoot)
            sys.path.append(resourcePath)
            sys.path.append("\(resourcePath)/app")
            do {
                let hotReload = try Python.attemptImport("pythonnative.hot_reload")
                let docsPath = "\(NSHomeDirectory())/Documents"
                _ = try hotReload.configure_dev_environment.throwing.dynamicallyCall(withArguments: [docsPath])
            } catch {
                NSLog("[PN] Hot reload setup skipped: \(error)")
            }
        }
        // Determine which Python module to load. PythonNative's
        // convention is "import the module and grab its top-level
        // `App` attribute", so the default is just the module path
        // "app.main". Push navigation overrides this via
        // `requestedScreenPath`, which may also be a dotted-attribute
        // path like "app.main.RootScreen".
        let screenPath: String = requestedScreenPath ?? "app.main"
        do {
            let pnScreen = try Python.attemptImport("pythonnative.screen")
            let ptr = Unmanaged.passUnretained(self).toOpaque()
            let addr = UInt(bitPattern: ptr)
            let argsJson: PythonObject = (requestedScreenArgsJSON != nil)
                ? PythonObject(requestedScreenArgsJSON!)
                : Python.None
            let screen = try pnScreen.create_screen.throwing.dynamicallyCall(
                withArguments: [screenPath, addr, argsJson]
            )
            self.screen = screen
            let devRoot = "\(NSHomeDirectory())/Documents/pythonnative_dev"
            let manifestPath = "\(devRoot)/reload.json"
            _ = try screen.enable_hot_reload.throwing.dynamicallyCall(withArguments: [manifestPath, devRoot])
            _ = try screen.on_create.throwing.dynamicallyCall(withArguments: [])
            startHotReloadPolling()
            return
        } catch {
            NSLog("[PN] Python bootstrap failed: \(error)")
        }
        #endif

        // Fallback UI if Python import/bootstrap fails
        NSLog("[PN] Python unavailable or bootstrap failed; showing fallback UILabel")
        let label = UILabel(frame: view.bounds)
        label.text = "Hello from PythonNative (iOS template)"
        label.textAlignment = .center
        label.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(label)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_start"])
            } catch {}
        }
        #endif
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        // The root view's safeAreaInsets are only valid after iOS has
        // positioned the view in its window; forward every layout pass
        // to Python so the reconciler can re-run layout against the
        // correct viewport (initial mount, rotation, multitasking, etc.).
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_layout"])
            } catch {
                NSLog("[PN] swift.viewDidLayoutSubviews -> on_layout failed: \(error)")
            }
        }
        #endif
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        #if canImport(PythonKit)
        if pythonReady {
            let ptrAddr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptrAddr, "on_resume"])
            } catch {
                NSLog("[PN] swift.viewDidAppear -> on_resume failed: \(error)")
            }
        }
        #endif
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_pause"])
            } catch {}
        }
        #endif
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_stop"])
            } catch {}
        }
        #endif
    }

    override func encodeRestorableState(with coder: NSCoder) {
        super.encodeRestorableState(with: coder)
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_save_instance_state"])
            } catch {}
        }
        #endif
    }

    override func decodeRestorableState(with coder: NSCoder) {
        super.decodeRestorableState(with: coder)
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_restore_instance_state"])
            } catch {}
        }
        #endif
    }

    deinit {
        hotReloadTimer?.invalidate()
        #if canImport(PythonKit)
        if pythonReady {
            let ptr = UInt(bitPattern: Unmanaged.passUnretained(self).toOpaque())
            do {
                let pn = try Python.attemptImport("pythonnative.screen")
                _ = try pn.forward_lifecycle.throwing.dynamicallyCall(withArguments: [ptr, "on_destroy"])
            } catch {}
        }
        #endif
    }

    private func startHotReloadPolling() {
        #if canImport(PythonKit)
        hotReloadTimer?.invalidate()
        hotReloadTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            guard let screen = self?.screen else { return }
            do {
                _ = try screen.hot_reload_tick.throwing.dynamicallyCall(withArguments: [])
            } catch {
                NSLog("[PN] hot_reload_tick failed: \(error)")
            }
        }
        #endif
    }

}

