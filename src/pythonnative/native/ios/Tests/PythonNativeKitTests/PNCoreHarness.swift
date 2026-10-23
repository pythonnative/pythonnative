import XCTest
import PNCore
@testable import PythonNativeKit

/// Commits wire ops to the iOS build of the renderer core and mounts the
/// result, as Python and the main thread do in an app.
///
/// The commit runs on a background queue while the test waits on the main
/// run loop, so the core can hop to the main thread to measure widgets.
final class PNCoreHarness {
    static let surface = PNCore.surface
    private static var contracts: String = {
        #if SWIFT_PACKAGE
        let bundle = Bundle.module
        #else
        let bundle = Bundle(for: PNCoreHarness.self)
        #endif
        let url = bundle.url(forResource: "contracts", withExtension: "json", subdirectory: "Fixtures")!
        return try! String(contentsOf: url, encoding: .utf8)
    }()

    let application = UUID().uuidString
    private(set) var revision: Int64 = 0
    var roots: [Int64] = []
    var viewport = CGSize(width: 390, height: 844)

    /// Forget every surface and mounted view, then load the contracts.
    init() {
        PNCoreBridge.install()
        pn_core_reset(PNCore.handle)
        _ = PNMounter.apply([.reset])
        let error = PNCoreHarness.contracts.withCString { pn_core_load_contracts(PNCore.handle, $0, "ios") }
        if let error = error {
            XCTFail("contracts: \(String(cString: error))")
            pn_core_free(error)
        }
    }

    /// Commit `ops`, lay out `roots` (when any), and mount the transaction.
    @discardableResult
    func commit(_ ops: [[Any]], expectOK: Bool = true, file: StaticString = #filePath, line: UInt = #line) -> [String: Any] {
        var envelope: [String: Any] = [
            "version": Int(pn_core_protocol_version()), "application": application,
            "surface": PNCoreHarness.surface, "revision": revision + 1, "ops": ops,
        ]
        if !roots.isEmpty {
            envelope["layout"] = ["roots": roots, "width": viewport.width, "height": viewport.height, "selective": false]
        }
        let json = PNJSON.encode(envelope)
        let ack = PNCoreHarness.onWorker { () -> [String: Any] in
            guard let reply = json.withCString({ pn_core_commit(PNCore.handle, $0) }) else { return [:] }
            defer { pn_core_free(reply) }
            return PNJSON.decodeObject(String(cString: reply))
        }
        let ok = ack["ok"] as? Bool == true
        XCTAssertEqual(ok, expectOK, String(describing: ack), file: file, line: line)
        if ok { revision += 1 }
        PNMounter.drain()
        return ack
    }

    /// Queue an animation request and mount it.
    func animate(tag: Int64, _ request: [String: Any]) {
        let json = PNJSON.encode(request)
        if let reply = json.withCString({ pn_core_animate(PNCore.handle, PNCoreHarness.surface, tag, $0) }) {
            pn_core_free(reply)
        }
        PNMounter.drain()
    }

    /// Run `body` on a background queue, servicing the main queue meanwhile.
    static func onWorker<T>(_ body: @escaping () -> T) -> T {
        var result: T?
        let done = DispatchSemaphore(value: 0)
        DispatchQueue.global(qos: .userInitiated).async {
            result = body()
            done.signal()
        }
        while done.wait(timeout: .now()) == .timedOut {
            RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 0.002))
        }
        return result!
    }
}
