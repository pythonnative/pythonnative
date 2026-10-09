import XCTest
@testable import PythonNativeKit

private final class PNInvalidLocation: LocationImplementation {
    var complete: ((Result<[String: Double]?, Error>) -> Void)?
    init() {}
    func get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: @escaping (Result<[String: Double]?, Error>) -> Void) -> (() -> Void)? {
        complete = completion
        return nil
    }
}

/// A module that settles inline or later depending on the method.
final class PNTestEchoModule: PNNativeModule {
    static let name = "TestEcho"
    static var pending: PNPromise?

    init() {}

    func call(_ method: String, args: [String: Any], promise: PNPromise) {
        switch method {
        case "echo": promise.resolve(args["value"])
        case "fail": promise.reject("nope", code: "test_code")
        case "later": PNTestEchoModule.pending = promise
        default: promise.reject("unknown method \(method)")
        }
    }
}

final class PNModuleTests: XCTestCase {
    func testGeneratedAdapterRejectsInvalidLateNativeResult() {
        let implementation = PNInvalidLocation()
        let adapter = LocationModuleAdapter(implementation: implementation)
        let promise = PNPromise(callId: 200, module: "Location", method: "get_current")
        adapter.call("get_current", args: [:], promise: promise)
        XCTAssertEqual(promise.takeInlineResult()["pending"] as? Bool, true)
        implementation.complete?(.success(["latitude": .nan]))
        XCTAssertEqual(promise.result?["ok"] as? Bool, false)
        XCTAssertNotNil(promise.result?["error"])
    }

    private let dispatcher = PNModuleDispatcher { module, method, args in
        if module != "TestEcho" { return PNContracts.validateModule(module, method, args) }
        return method == "echo" ? (args.count == 1 && args["value"] is Int) : (["fail", "later"].contains(method) && args.isEmpty)
    }
    override func setUp() {
        super.setUp()
        PNRegistry.shared.registerModule(PNTestEchoModule.self)
    }

    func testSynchronousResolveProducesOkEnvelope() {
        let result = dispatcher.call(module: "TestEcho", method: "echo", envelope: ["call_id": 7, "args": ["value": 42]])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(result["value"] as? Int, 42)
        XCTAssertNil(result["pending"])
    }

    func testRejectProducesErrorEnvelope() {
        let result = dispatcher.call(module: "TestEcho", method: "fail", envelope: ["call_id": 8, "args": [:]])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertEqual(result["error"] as? String, "nope")
        XCTAssertEqual(result["code"] as? String, "test_code")
    }

    func testUnknownModuleAndMethod() {
        let missing = dispatcher.call(module: "Nope", method: "x", envelope: [:])
        XCTAssertEqual(missing["ok"] as? Bool, false)
        XCTAssertEqual(missing["code"] as? String, "unknown_module")
        let method = dispatcher.call(module: "TestEcho", method: "zzz", envelope: [:])
        XCTAssertEqual(method["ok"] as? Bool, false)
    }

    func testAsynchronousSettlementReturnsPending() {
        let result = dispatcher.call(module: "TestEcho", method: "later", envelope: ["call_id": 9, "args": [:]])
        XCTAssertEqual(result["pending"] as? Bool, true)
        guard let promise = PNTestEchoModule.pending else { return XCTFail("promise not captured") }
        XCTAssertFalse(promise.isSettled)
        XCTAssertEqual(promise.callId, 9)
        promise.resolve("done")
        XCTAssertTrue(promise.isSettled)
        promise.resolve("again")
        XCTAssertEqual(promise.result?["value"] as? String, "done", "second settlement is ignored")
    }

    func testEnvelopeJSONRoundTrip() {
        let ok = PNJSON.encode(["ok": true, "value": ["a": 1]])
        let decoded = PNJSON.decodeObject(ok)
        XCTAssertEqual(decoded["ok"] as? Bool, true)
        XCTAssertEqual((decoded["value"] as? [String: Any])?["a"] as? Int, 1)
        XCTAssertEqual(PNJSON.decodeObject(PNJSON.encode(["pending": true]))["pending"] as? Bool, true)
        XCTAssertEqual(PNJSON.encode(Double.infinity), "null", "non-finite numbers never leave Swift as JSON numbers")
        XCTAssertEqual(PNJSON.resolveInfinity("inf") as? Double, Double.infinity)
        XCTAssertEqual(PNJSON.encode(nil), "null")
    }

    func testGeneratedValuesPreserveNumbersAndBooleansAcrossBridgeEncoding() throws {
        let values: [Any] = [PNValues.encode(Int64(0)), PNValues.encode(Int64(1)),
                             PNValues.encode(true), PNValues.encode(false),
                             PNValues.encode(["index": Int64(1)])]
        let encoded = PNJSON.encode(values)
        let decoded = try JSONDecoder().decode([PNJSONValue].self, from: Data(encoded.utf8))
        XCTAssertEqual(decoded, [.number(0), .number(1), .bool(true), .bool(false),
                                 .object(["index": .number(1)])])
    }

    func testCancellationReleasesNativeWorkAndIgnoresLateCompletion() {
        _ = dispatcher.call(module: "TestEcho", method: "later", envelope: ["call_id": 99, "args": [:]])
        guard let promise = PNTestEchoModule.pending else { return XCTFail("missing promise") }
        var cancelled = 0
        promise.onCancel { cancelled += 1 }
        _ = dispatcher.call(module: "TestEcho", method: "_pn_cancel", envelope: ["args": ["call_id": 99]])
        promise.cancel()
        promise.resolve("late")
        XCTAssertTrue(promise.isCancelled)
        XCTAssertEqual(cancelled, 1)
        XCTAssertNil(promise.result)
    }

    func testDeviceInfoShape() {
        let info = DeviceModule.snapshot()
        XCTAssertEqual(info["platform"] as? String, "ios")
        XCTAssertNotNil(info["os_version"])
        XCTAssertNotNil(info["app_dir"])
        XCTAssertNotNil(info["bundle_id"])
        XCTAssertNotNil(info["scale"])
    }

    func testStorageModuleRoundTrip() {
        let storage = StorageModuleAdapter<StorageModule>()
        _ = dispatcher.call(module: "Storage", method: "clear", envelope: [:])
        let set = PNPromise(callId: 1, module: "Storage", method: "set")
        storage.call("set", args: ["key": "k", "value": "v"], promise: set)
        let get = PNPromise(callId: 2, module: "Storage", method: "get")
        storage.call("get", args: ["key": "k"], promise: get)
        XCTAssertEqual(get.result?["value"] as? String, "v")
        let keys = PNPromise(callId: 3, module: "Storage", method: "all_keys")
        storage.call("all_keys", args: [:], promise: keys)
        XCTAssertEqual(keys.result?["value"] as? [String], ["k"])
        let del = PNPromise(callId: 4, module: "Storage", method: "delete")
        storage.call("delete", args: ["key": "k"], promise: del)
        let missing = PNPromise(callId: 5, module: "Storage", method: "get")
        storage.call("get", args: ["key": "k"], promise: missing)
        XCTAssertTrue(missing.result?["value"] is NSNull)
    }
}

// MARK: - DevSupport and the error screen

private func allSubviews(of view: UIView) -> [UIView] {
    view.subviews + view.subviews.flatMap { allSubviews(of: $0) }
}

extension PNModuleTests {
    private func devSupport(_ method: String, _ args: [String: Any] = [:]) -> [String: Any] {
        dispatcher.call(module: "DevSupport", method: method, envelope: ["call_id": 0, "args": args])
    }

    func testDevSupportIsInertUntilEnabled() {
        DevSupportModule.reset()
        defer { DevSupportModule.reset() }
        XCTAssertFalse(DevSupportModule.trigger("menu"))
        XCTAssertEqual(devSupport("enable")["ok"] as? Bool, true)
        XCTAssertTrue(DevSupportModule.isEnabled)
        XCTAssertTrue(DevSupportModule.trigger("menu"))
        let stats = devSupport("frame_stats")["value"] as? [String: Any]
        XCTAssertNotNil(stats?["fps"] as? Double)
        XCTAssertEqual(stats?["dropped"] as? Int, 0)
        XCTAssertEqual(devSupport("show_menu")["code"] as? String, "unknown_method")
    }

    func testDevSupportHighlightsInspectsAndShowsTheMonitor() throws {
        DevSupportModule.reset()
        let window = try XCTUnwrap(PNWindow.keyWindow())
        let manager = try XCTUnwrap(PNRegistry.shared.manager(for: "View"))
        let outer = UIView(frame: CGRect(x: 20, y: 100, width: 200, height: 200))
        let inner = UILabel(frame: CGRect(x: 10, y: 10, width: 50, height: 20))
        outer.addSubview(inner)
        window.addSubview(outer)
        for (tag, view) in [(Int64(98001), outer), (Int64(98002), inner)] {
            PNViewState.attach(view, tag: tag, typeName: "View")
            PNViewRegistry.shared.register(PNViewRecord(tag: tag, typeName: "View", view: view, manager: manager))
        }
        defer {
            DevSupportModule.reset()
            outer.removeFromSuperview()
            PNViewRegistry.shared.unregister(98001)
            PNViewRegistry.shared.unregister(98002)
        }

        // Labels don't take touches, but the inspector still selects them.
        XCTAssertEqual(DevSupportModule.inspect(at: CGPoint(x: 35, y: 115), in: window), 98002)
        XCTAssertEqual(DevSupportModule.inspect(at: CGPoint(x: 150, y: 250), in: window), 98001)

        XCTAssertEqual(devSupport("highlight", ["tag": 98002, "label": "App › Text"])["value"] as? Bool, true)
        XCTAssertTrue(DevSupportModule.highlightView?.superview === window)
        XCTAssertEqual(devSupport("highlight", ["tag": NSNull(), "label": ""])["value"] as? Bool, false)
        XCTAssertNil(DevSupportModule.highlightView)

        XCTAssertEqual(devSupport("set_inspecting", ["enabled": true])["ok"] as? Bool, true)
        XCTAssertTrue(DevSupportModule.inspector?.superview === window)
        XCTAssertEqual(DevSupportModule.inspect(at: CGPoint(x: 35, y: 115), in: window), 98002)
        _ = devSupport("set_inspecting", ["enabled": false])
        XCTAssertNil(DevSupportModule.inspector)

        _ = devSupport("set_perf_monitor", ["visible": true, "lines": ["Py 2 ms"]])
        let monitor = try XCTUnwrap(DevSupportModule.perfMonitor)
        XCTAssertTrue(monitor.superview === window)
        XCTAssertTrue(monitor.text.hasPrefix("UI "))
        XCTAssertTrue(monitor.text.hasSuffix("fps\nPy 2 ms"))
        _ = devSupport("set_perf_monitor", ["visible": false, "lines": []])
        XCTAssertNil(DevSupportModule.perfMonitor)
    }

    func testErrorScreenRendersTheStructuredReport() throws {
        let host = HostModule()
        let promise = PNPromise(callId: 0, module: "Host", method: "show_error")
        host.call("show_error", args: [
            "screen": 0, "level": "error", "phase": "render", "type": "ZeroDivisionError",
            "message": "division by zero", "title": "ZeroDivisionError in render: division by zero",
            "component_stack": [["name": "Counter", "file": "app/main.py", "line": 14], ["name": "App", "file": NSNull(), "line": NSNull()]],
            "frames": [
                ["file": "/lib/runtime.py", "line": 3, "function": "run", "code": "", "title": "/lib/runtime.py:3 in run", "excerpt": "", "framework": true],
                ["file": "/lib/hooks.py", "line": 9, "function": "call", "code": "", "title": "/lib/hooks.py:9 in call", "excerpt": "", "framework": true],
                ["file": "app/main.py", "line": 15, "function": "Counter", "code": "1 / 0", "title": "app/main.py:15 in Counter",
                 "excerpt": "  14 | def Counter():\n> 15 |     1 / 0", "framework": false],
            ],
            "text": "Traceback (most recent call last): ...", "timestamp": 0,
        ], promise: promise)
        XCTAssertEqual(promise.takeInlineResult()["ok"] as? Bool, true)
        let overlay = try XCTUnwrap(PNErrorOverlay.visible)
        defer { PNErrorOverlay.dismiss() }
        let views = allSubviews(of: overlay)
        let texts = views.compactMap { ($0 as? UILabel)?.text }
        for expected in ["ZeroDivisionError", "division by zero", "Error during render", "<Counter> (app/main.py:14)\n<App>",
                         "2 framework frames", "app/main.py:15 in Counter"] {
            XCTAssertTrue(texts.contains(expected), "missing \(expected)")
        }
        let identifiers = Set(views.compactMap { $0.accessibilityIdentifier })
        XCTAssertTrue(identifiers.isSuperset(of: ["pn-error-trace", "pn-error-reload", "pn-error-dismiss", "pn-error-copy"]))
        XCTAssertTrue(views.first { $0.accessibilityIdentifier == "pn-error-trace" } is UIScrollView)

        let excerpt = PNErrorOverlay.excerpt("  14 | def Counter():\n> 15 |     1 / 0")
        XCTAssertNil(excerpt.attribute(.backgroundColor, at: 0, effectiveRange: nil))
        XCTAssertNotNil(excerpt.attribute(.backgroundColor, at: excerpt.length - 1, effectiveRange: nil))

        let dismiss = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "pn-error-dismiss" } as? UIButton)
        dismiss.sendActions(for: .touchUpInside)
        XCTAssertNil(PNErrorOverlay.visible)
    }
}
