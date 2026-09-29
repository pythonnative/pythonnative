import XCTest
@testable import PythonNativeKit

final class PNContractFixtureTests: XCTestCase {
    func testGeneratedRecordsPreserveNullPresenceAndEscapedDefaults() throws {
        for optional in [nil, NSNull(), "value"] as [Any?] {
            var note: [String: Any] = ["required": NSNull()]
            if let optional = optional { note["optional"] = optional }
            let decoded = try PNValues.decode(PNNativeFixtureDefault.self, ["note": note])
            let encoded = try XCTUnwrap(PNValues.encode(decoded) as? [String: Any])
            let returned = try XCTUnwrap(encoded["note"] as? [String: Any])
            XCTAssertTrue(returned["required"] is NSNull)
            XCTAssertEqual(returned.keys.contains("optional"), optional != nil)
            // Compare structurally: JSON key order isn't stable across processes.
            XCTAssertTrue(NSDictionary(dictionary: returned).isEqual(to: note), "\(returned) != \(note)")
            XCTAssertTrue(encoded["nullable"] is NSNull)
            XCTAssertEqual(encoded["label"] as? String, "$total \"quoted\" \\path\n\u{0}\u{8}")
        }
    }

    func testSharedListTrace() throws {
        let store = PNListStore()
        let cases = try JSONSerialization.jsonObject(with: Data(PNListFixtures.trace.utf8)) as! [[String: Any]]
        for item in cases {
            let packet = item["packet"] as! [String: Any]
            if item["valid"] as! Bool { store.publish(try store.prepare(packet)) }
            else { XCTAssertThrowsError(try store.prepare(packet), item["name"] as! String) }
            XCTAssertEqual(store.keys, item["keys"] as! [String], item["name"] as! String)
            XCTAssertEqual(store.revision, item["revision"] as! Int, item["name"] as! String)
        }
    }

    func testPortableFixtures() throws {
        #if SWIFT_PACKAGE
        let bundle = Bundle.module
        #else
        let bundle = Bundle(for: PNContractFixtureTests.self)
        #endif
        let file = try XCTUnwrap(bundle.url(forResource: "validation", withExtension: "json", subdirectory: "Fixtures"))
        let cases = try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as! [[String: Any]]
        for (index, item) in cases.enumerated() {
            XCTAssertEqual(PNValidationFixtures.matches(index, item["value"]!), item["valid"] as! Bool, item["name"] as! String)
        }
    }
}
