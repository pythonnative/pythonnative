import XCTest
@testable import PythonNativeKit

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
    override func setUp() {
        super.setUp()
        PNRegistry.shared.registerModule(PNTestEchoModule.self)
    }

    func testSynchronousResolveProducesOkEnvelope() {
        let result = PNModuleDispatcher.shared.call(module: "TestEcho", method: "echo", envelope: ["call_id": 7, "args": ["value": 42]])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(result["value"] as? Int, 42)
        XCTAssertNil(result["pending"])
    }

    func testRejectProducesErrorEnvelope() {
        let result = PNModuleDispatcher.shared.call(module: "TestEcho", method: "fail", envelope: ["call_id": 8, "args": [:]])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertEqual(result["error"] as? String, "nope")
        XCTAssertEqual(result["code"] as? String, "test_code")
    }

    func testUnknownModuleAndMethod() {
        let missing = PNModuleDispatcher.shared.call(module: "Nope", method: "x", envelope: [:])
        XCTAssertEqual(missing["ok"] as? Bool, false)
        XCTAssertEqual(missing["code"] as? String, "unknown_module")
        let method = PNModuleDispatcher.shared.call(module: "TestEcho", method: "zzz", envelope: [:])
        XCTAssertEqual(method["ok"] as? Bool, false)
    }

    func testAsynchronousSettlementReturnsPending() {
        let result = PNModuleDispatcher.shared.call(module: "TestEcho", method: "later", envelope: ["call_id": 9, "args": [:]])
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

    func testDeviceInfoShape() {
        let info = DeviceModule.info()
        XCTAssertEqual(info["os"] as? String, "ios")
        XCTAssertNotNil(info["os_version"])
        XCTAssertNotNil(info["app_dir"])
        XCTAssertNotNil(info["cache_dir"])
        XCTAssertNotNil(info["scale"])
    }

    func testStorageModuleRoundTrip() {
        let storage = StorageModule()
        _ = PNModuleDispatcher.shared.call(module: "Storage", method: "clear", envelope: [:])
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
