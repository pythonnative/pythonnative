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
        XCTAssertEqual(info["os"] as? String, "ios")
        XCTAssertNotNil(info["os_version"])
        XCTAssertNotNil(info["app_dir"])
        XCTAssertNotNil(info["cache_dir"])
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
