//
//  PythonRuntime.swift
//  ios_template
//
//  Embeds CPython directly through the C API (no PythonKit). The
//  Python.xcframework is linked at build time, so a missing runtime is
//  a build error, never a silent runtime fallback.
//

import Foundation

enum PythonRuntimeError: Error, CustomStringConvertible {
    case startup(String)
    case call(String)

    var description: String {
        switch self {
        case .startup(let message): return message
        case .call(let message): return message
        }
    }
}

/// An owned reference to a Python object. Reference counting is handled
/// automatically; the wrapped pointer is released on deinit.
final class PyRef {
    fileprivate let pointer: UnsafeMutablePointer<PyObject>

    fileprivate init(owned pointer: UnsafeMutablePointer<PyObject>) {
        self.pointer = pointer
    }

    deinit {
        let gil = PyGILState_Ensure()
        Py_DecRef(pointer)
        PyGILState_Release(gil)
    }

    /// Call a method on this object with string/number/bool arguments.
    @discardableResult
    func call(_ method: String, _ args: Any...) throws -> PyRef {
        let gil = PyGILState_Ensure()
        defer { PyGILState_Release(gil) }
        guard let bound = PyObject_GetAttrString(pointer, method) else {
            throw PythonRuntimeError.call("Python object has no method '\(method)': \(PythonRuntime.consumeError())")
        }
        defer { Py_DecRef(bound) }
        return try PythonRuntime.invoke(bound, args: args, context: method)
    }

    /// Truthiness of the wrapped object (`PyObject_IsTrue`).
    var isTruthy: Bool {
        let gil = PyGILState_Ensure()
        defer { PyGILState_Release(gil) }
        return PyObject_IsTrue(pointer) == 1
    }
}

/// Owns the embedded CPython interpreter for the whole process.
final class PythonRuntime {
    static let shared = PythonRuntime()

    private(set) var started = false
    private(set) var startupError: String? = nil
    private var pendingURLs: [String] = []

    private init() {}

    // MARK: - Startup

    /// Initialize the embedded interpreter once. Throws with a full
    /// description when the bundle is not packaged correctly; there is
    /// deliberately no fallback mode.
    func ensureStarted() throws {
        if started { return }
        if let error = startupError { throw PythonRuntimeError.startup(error) }
        do {
            try start()
            started = true
            flushPendingURLs()
        } catch let error as PythonRuntimeError {
            startupError = error.description
            throw error
        }
    }

    private func start() throws {
        guard let resourcePath = Bundle.main.resourcePath else {
            throw PythonRuntimeError.startup("The app bundle has no resource path; the build is corrupt.")
        }
        let pythonHome = "\(resourcePath)/python"
        let appPath = "\(resourcePath)/app"
        let packagesPath = "\(resourcePath)/app_packages"
        for (path, hint) in [
            (pythonHome, "the embedded Python runtime"),
            (appPath, "the app's Python sources"),
            (packagesPath, "the bundled Python packages"),
        ] where !FileManager.default.fileExists(atPath: path) {
            throw PythonRuntimeError.startup(
                "Missing \(hint) at \(path). Build the app with 'pn run ios' or 'pn build ios' "
                    + "so the PythonNative CLI stages the Python runtime; the raw Xcode template "
                    + "cannot run on its own."
            )
        }

        // Signal to pythonnative that we're running on iOS. Read on the
        // Python side (pythonnative.utils.IS_IOS) before the first import.
        setenv("PN_PLATFORM", "ios", 1)

        var preconfig = PyPreConfig()
        PyPreConfig_InitIsolatedConfig(&preconfig)
        preconfig.utf8_mode = 1
        var status = Py_PreInitialize(&preconfig)
        if PyStatus_Exception(status) != 0 {
            throw PythonRuntimeError.startup("Unable to pre-initialize Python: \(Self.statusMessage(status))")
        }

        var config = PyConfig()
        PyConfig_InitIsolatedConfig(&config)
        defer { PyConfig_Clear(&config) }
        // Unbuffered stdio so print() reaches the device log immediately.
        config.buffered_stdio = 0
        // The signed bundle is immutable; never try to write bytecode.
        config.write_bytecode = 0

        guard let homeW = Py_DecodeLocale(pythonHome, nil) else {
            throw PythonRuntimeError.startup("Could not decode the Python home path.")
        }
        status = withUnsafeMutablePointer(to: &config) { cfg in
            PyConfig_SetString(cfg, &cfg.pointee.home, homeW)
        }
        PyMem_RawFree(homeW)
        if PyStatus_Exception(status) != 0 {
            throw PythonRuntimeError.startup("Unable to set the Python home: \(Self.statusMessage(status))")
        }

        status = PyConfig_Read(&config)
        if PyStatus_Exception(status) != 0 {
            throw PythonRuntimeError.startup("Unable to read the Python config: \(Self.statusMessage(status))")
        }

        status = Py_InitializeFromConfig(&config)
        if PyStatus_Exception(status) != 0 {
            throw PythonRuntimeError.startup("Unable to initialize Python: \(Self.statusMessage(status))")
        }

        // The interpreter is live and this thread holds the GIL. Finish
        // path setup, then release the GIL; every later entry point
        // re-acquires it via PyGILState_Ensure.
        do {
            try bootstrapPaths(appPath: appPath, packagesPath: packagesPath)
        } catch {
            PyEval_SaveThread()
            throw error
        }
        PyEval_SaveThread()
        NSLog("[PN] Embedded Python initialized (home: \(pythonHome))")
    }

    private func bootstrapPaths(appPath: String, packagesPath: String) throws {
        // site.addsitedir(app_packages): adds to sys.path and honors .pth files.
        guard let site = PyImport_ImportModule("site"),
              let addsitedir = PyObject_GetAttrString(site, "addsitedir")
        else {
            throw PythonRuntimeError.startup("Could not import the site module: \(Self.consumeError())")
        }
        defer { Py_DecRef(site) }
        defer { Py_DecRef(addsitedir) }
        guard let packagesObj = PyUnicode_FromString(packagesPath),
              let argsTuple = PyTuple_New(1)
        else {
            throw PythonRuntimeError.startup("Could not build site.addsitedir arguments.")
        }
        PyTuple_SetItem(argsTuple, 0, packagesObj)  // steals packagesObj
        defer { Py_DecRef(argsTuple) }
        guard let addResult = PyObject_CallObject(addsitedir, argsTuple) else {
            throw PythonRuntimeError.startup("site.addsitedir failed: \(Self.consumeError())")
        }
        Py_DecRef(addResult)

        // sys.path.insert(0, app) so `import app.main` resolves.
        guard let sys = PyImport_ImportModule("sys"),
              let sysPath = PyObject_GetAttrString(sys, "path"),
              let appObj = PyUnicode_FromString(appPath)
        else {
            throw PythonRuntimeError.startup("Could not access sys.path: \(Self.consumeError())")
        }
        defer { Py_DecRef(sys) }
        defer { Py_DecRef(sysPath) }
        defer { Py_DecRef(appObj) }
        // The bundle root itself is also importable ("app" package form).
        if let resourceObj = PyUnicode_FromString(Bundle.main.resourcePath ?? appPath) {
            PyList_Insert(sysPath, 0, resourceObj)
            Py_DecRef(resourceObj)
        }
        if PyList_Insert(sysPath, 0, appObj) != 0 {
            throw PythonRuntimeError.startup("Could not add the app directory to sys.path.")
        }

        #if DEBUG
        // Dev-only: prioritize the writable hot-reload overlay. Release
        // builds never look outside the signed bundle.
        let documents = NSHomeDirectory() + "/Documents"
        guard let hotReload = PyImport_ImportModule("pythonnative.hot_reload"),
              let configure = PyObject_GetAttrString(hotReload, "configure_dev_environment"),
              let docsObj = PyUnicode_FromString(documents),
              let devArgs = PyTuple_New(1)
        else {
            throw PythonRuntimeError.startup(
                "Could not import pythonnative: \(Self.consumeError())\n"
                    + "The pythonnative package must be staged into app_packages by the pn CLI."
            )
        }
        defer { Py_DecRef(hotReload) }
        defer { Py_DecRef(configure) }
        PyTuple_SetItem(devArgs, 0, docsObj)  // steals docsObj
        defer { Py_DecRef(devArgs) }
        if let devResult = PyObject_CallObject(configure, devArgs) {
            Py_DecRef(devResult)
        } else {
            throw PythonRuntimeError.startup("Hot-reload setup failed: \(Self.consumeError())")
        }
        #endif
    }

    // MARK: - Calling into Python

    /// Import `module` and call its `function` with the given arguments.
    /// Supported argument types: String, Int, UInt, Bool, Double.
    @discardableResult
    func call(module: String, function: String, _ args: Any...) throws -> PyRef {
        try callList(module: module, function: function, args)
    }

    @discardableResult
    func callList(module: String, function: String, _ args: [Any]) throws -> PyRef {
        guard started else {
            throw PythonRuntimeError.call("Python is not running (startup failed or never happened).")
        }
        let gil = PyGILState_Ensure()
        defer { PyGILState_Release(gil) }
        guard let moduleObj = PyImport_ImportModule(module) else {
            throw PythonRuntimeError.call("Could not import \(module): \(Self.consumeError())")
        }
        defer { Py_DecRef(moduleObj) }
        guard let fnObj = PyObject_GetAttrString(moduleObj, function) else {
            throw PythonRuntimeError.call("\(module) has no attribute '\(function)': \(Self.consumeError())")
        }
        defer { Py_DecRef(fnObj) }
        return try Self.invoke(fnObj, args: args, context: "\(module).\(function)")
    }

    /// Like `call`, but logs failures instead of throwing. For host
    /// notifications where the app must keep running.
    func notify(module: String, function: String, _ args: Any...) {
        do {
            _ = try callList(module: module, function: function, args)
        } catch {
            NSLog("[PN] \(module).\(function) failed: \(error)")
        }
    }

    /// Shared invocation helper. The caller must hold the GIL.
    fileprivate static func invoke(
        _ callable: UnsafeMutablePointer<PyObject>,
        args: [Any],
        context: String
    ) throws -> PyRef {
        guard let tuple = PyTuple_New(args.count) else {
            throw PythonRuntimeError.call("Could not allocate arguments for \(context).")
        }
        for (index, arg) in args.enumerated() {
            guard let converted = convert(arg) else {
                Py_DecRef(tuple)
                throw PythonRuntimeError.call("Unsupported argument type \(type(of: arg)) for \(context).")
            }
            PyTuple_SetItem(tuple, index, converted)  // steals converted
        }
        defer { Py_DecRef(tuple) }
        guard let result = PyObject_CallObject(callable, tuple) else {
            throw PythonRuntimeError.call("\(context) raised: \(consumeError())")
        }
        return PyRef(owned: result)
    }

    private static func convert(_ value: Any) -> UnsafeMutablePointer<PyObject>? {
        switch value {
        case let string as String:
            return PyUnicode_FromString(string)
        case let flag as Bool:
            return PyBool_FromLong(flag ? 1 : 0)
        case let unsigned as UInt:
            return PyLong_FromUnsignedLongLong(UInt64(unsigned))
        case let integer as Int:
            return PyLong_FromLongLong(Int64(integer))
        case let double as Double:
            return PyFloat_FromDouble(double)
        default:
            return nil
        }
    }

    // MARK: - Deep links

    /// Deliver a deep-link URL to the Python side, buffering it until
    /// the interpreter is running.
    func deliverURL(_ url: String) {
        guard started else {
            pendingURLs.append(url)
            return
        }
        notify(module: "pythonnative.native_modules.linking", function: "dispatch_url", url)
    }

    private func flushPendingURLs() {
        let urls = pendingURLs
        pendingURLs = []
        for url in urls {
            notify(module: "pythonnative.native_modules.linking", function: "dispatch_url", url)
        }
    }

    // MARK: - Error formatting

    /// Format and clear the pending Python exception (caller holds the GIL).
    fileprivate static func consumeError() -> String {
        var ptype: UnsafeMutablePointer<PyObject>? = nil
        var pvalue: UnsafeMutablePointer<PyObject>? = nil
        var ptrace: UnsafeMutablePointer<PyObject>? = nil
        PyErr_Fetch(&ptype, &pvalue, &ptrace)
        PyErr_NormalizeException(&ptype, &pvalue, &ptrace)
        defer {
            Py_DecRef(ptype)
            Py_DecRef(pvalue)
            Py_DecRef(ptrace)
        }
        guard ptype != nil else { return "unknown Python error" }

        if let traceback = PyImport_ImportModule("traceback") {
            defer { Py_DecRef(traceback) }
            let fnName = ptrace != nil ? "format_exception" : "format_exception_only"
            if let formatFn = PyObject_GetAttrString(traceback, fnName) {
                defer { Py_DecRef(formatFn) }
                let count = ptrace != nil ? 3 : 2
                if let tuple = PyTuple_New(count) {
                    Py_IncRef(ptype)
                    PyTuple_SetItem(tuple, 0, ptype)
                    Py_IncRef(pvalue)
                    PyTuple_SetItem(tuple, 1, pvalue)
                    if count == 3 {
                        Py_IncRef(ptrace)
                        PyTuple_SetItem(tuple, 2, ptrace)
                    }
                    defer { Py_DecRef(tuple) }
                    if let lines = PyObject_CallObject(formatFn, tuple) {
                        defer { Py_DecRef(lines) }
                        if let empty = PyUnicode_FromString(""),
                           let joined = PyUnicode_Join(empty, lines)
                        {
                            Py_DecRef(empty)
                            defer { Py_DecRef(joined) }
                            if let utf8 = PyUnicode_AsUTF8(joined) {
                                return String(cString: utf8)
                            }
                        }
                    }
                }
            }
        }
        // Fallback: str(value).
        if let value = pvalue, let str = PyObject_Str(value) {
            defer { Py_DecRef(str) }
            if let utf8 = PyUnicode_AsUTF8(str) {
                return String(cString: utf8)
            }
        }
        return "unknown Python error"
    }

    private static func statusMessage(_ status: PyStatus) -> String {
        if let errMsg = status.err_msg {
            return String(cString: errMsg)
        }
        return "unknown error"
    }
}

/// Exported for the Python side: `pythonnative.runtime` wakes the guest
/// asyncio loop by resolving this symbol via `ctypes.CDLL(None)` and
/// calling it whenever loop work is scheduled.
@_cdecl("pn_schedule_render_drain")
public func pn_schedule_render_drain() {
    DispatchQueue.main.async {
        guard PythonRuntime.shared.started else { return }
        PythonRuntime.shared.notify(module: "pythonnative.screen", function: "drain_ios_scheduled_renders")
    }
}
