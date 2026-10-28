import XCTest
import UIKit
import PNCore
@testable import PythonNativeKit

/// The mount decoder against transactions the host core produced, and the
/// mounter against the iOS core (RFC 0007).
final class PNMountTests: XCTestCase {
    private func fixtures() throws -> [[String: Any]] {
        #if SWIFT_PACKAGE
        let bundle = Bundle.module
        #else
        let bundle = Bundle(for: PNMountTests.self)
        #endif
        let file = try XCTUnwrap(bundle.url(forResource: "mount", withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: file)) as? [[String: Any]])
    }

    /// The shape `scripts/generate-native-contracts.py` records for one op.
    private func describe(_ op: PNMountOp) -> [String: Any] {
        switch op {
        case .reset:
            return ["kind": "reset", "tag": 0]
        case let .create(tag, component, props):
            return ["kind": "create", "tag": tag, "component": component, "props": props]
        case let .update(tag, recreate, changed, removed):
            return ["kind": "update", "tag": tag, "props": changed, "removed": removed, "recreate": recreate]
        case let .insert(parent, child, index):
            return ["kind": "insert", "tag": child, "parent": parent, "index": index]
        case let .delete(tag):
            return ["kind": "delete", "tag": tag]
        case let .frame(tag, x, y, width, height):
            return ["kind": "frame", "tag": tag, "frame": [x, y, width, height]]
        case let .command(tag, name, arguments, callId):
            return ["kind": "command", "tag": tag, "name": name, "arguments": arguments, "call_id": callId]
        }
    }

    func testDecoderMatchesHostCoreTransactions() throws {
        let cases = try fixtures()
        XCTAssertGreaterThanOrEqual(cases.count, 5)
        for item in cases {
            let name = item["name"] as! String
            let data = try XCTUnwrap(Data(base64Encoded: item["bytes"] as! String), name)
            let transaction = try data.withUnsafeBytes { try PNMountDecoder.decode($0.baseAddress!, count: data.count) }
            XCTAssertEqual(transaction.surface, (item["surface"] as! NSNumber).int64Value, name)
            XCTAssertEqual(transaction.revision, (item["revision"] as! NSNumber).int64Value, name)
            XCTAssertEqual(transaction.id, (item["id"] as! NSNumber).int64Value, name)
            let expected = item["ops"] as! [[String: Any]]
            XCTAssertEqual(transaction.ops.count, expected.count, name)
            for (op, want) in zip(transaction.ops, expected) {
                let got = describe(op)
                XCTAssertTrue(NSDictionary(dictionary: got).isEqual(to: want), "\(name): \(got) != \(want)")
            }
        }
    }

    func testDecoderKeepsValueKinds() throws {
        let create = try fixtures()[0]
        let data = Data(base64Encoded: create["bytes"] as! String)!
        let transaction = try data.withUnsafeBytes { try PNMountDecoder.decode($0.baseAddress!, count: data.count) }
        guard case let .create(_, component, props)? = transaction.ops.first(where: {
            if case let .create(_, component, _) = $0 { return component == "Text" }
            return false
        }) else { return XCTFail("no Text create") }
        XCTAssertEqual(component, "Text")
        XCTAssertEqual(props["text"] as? String, "Héllo ✓")
        XCTAssertEqual(props["font_size"] as? Double, 15.5)
        XCTAssertEqual(props["max_lines"] as? Int, 2)
        XCTAssertTrue((props["bold"] as? NSNumber).map { CFGetTypeID($0) == CFBooleanGetTypeID() } ?? false, "bools stay bools")
    }

    func testDecoderRejectsTruncatedAndForeignBytes() throws {
        let data = Data(base64Encoded: try fixtures()[0]["bytes"] as! String)!
        for cut in [0, 3, 12, 40, data.count - 1] {
            XCTAssertThrowsError(try data.prefix(cut).withUnsafeBytes { try PNMountDecoder.decode($0.baseAddress ?? UnsafeRawPointer(bitPattern: 1)!, count: cut) }, "cut at \(cut)")
        }
        var foreign = data
        foreign[0] = 0
        XCTAssertThrowsError(try foreign.withUnsafeBytes { try PNMountDecoder.decode($0.baseAddress!, count: foreign.count) })
    }

    func testInfinityMarkersDecodeAsDoubles() throws {
        // u32 count, then one object holding the string "inf".
        var bytes: [UInt8] = [7, 1, 0, 0, 0, 5, 0, 0, 0]
        bytes += Array("width".utf8)
        bytes += [5, 3, 0, 0, 0] + Array("inf".utf8)
        let props = bytes.withUnsafeBytes { PNMountDecoder.props($0.baseAddress, count: bytes.count) }
        XCTAssertEqual(props["width"] as? Double, .infinity)
    }

    // MARK: - Mounting through the iOS core

    func testCoreFlattensLayoutOnlyViewsAndOffsetsTheirChildren() throws {
        let core = PNCoreHarness()
        core.roots = [1]
        core.commit([["c", 1, "Column", ["flex": 1, "background_color": "#FFFFFF"]],
                     ["c", 2, "View", ["padding": 10]],
                     ["c", 3, "View", ["width": 30, "height": 20, "background_color": "#FF0000"]],
                     ["i", 2, 3, 0], ["i", 1, 2, 0]])
        XCTAssertNil(PNViewRegistry.shared.view(for: 2), "a layout-only View isn't mounted")
        let root = try XCTUnwrap(PNViewRegistry.shared.view(for: 1))
        let leaf = try XCTUnwrap(PNViewRegistry.shared.view(for: 3))
        XCTAssertTrue(leaf.superview === root, "the flattened View's child is adopted by the nearest mounted ancestor")
        XCTAssertEqual(leaf.frame, CGRect(x: 10, y: 10, width: 30, height: 20))
        XCTAssertEqual(PNMounter.parent(of: 3), 1)

        // Giving the View paint mounts it, and its child moves inside.
        core.commit([["u", 2, ["background_color": "#00FF00"], []]])
        let wrapper = try XCTUnwrap(PNViewRegistry.shared.view(for: 2))
        XCTAssertTrue(wrapper.superview === root)
        XCTAssertTrue(leaf.superview === wrapper)
        XCTAssertEqual(leaf.frame, CGRect(x: 10, y: 10, width: 30, height: 20))
        XCTAssertEqual(PNMounter.childTags(of: 2), [3])

        core.commit([["d", 3]])
        XCTAssertNil(PNViewRegistry.shared.view(for: 3))
        XCTAssertNil(leaf.superview)
    }

    func testRemovedPropsArriveAsDefaults() throws {
        let core = PNCoreHarness()
        core.roots = [1]
        core.commit([["c", 1, "View", ["background_color": "#FF0000", "opacity": 0.5]]])
        let view = try XCTUnwrap(PNViewRegistry.shared.view(for: 1))
        XCTAssertEqual(view.alpha, 0.5, accuracy: 0.001)
        core.commit([["u", 1, [:], ["opacity"]]])
        XCTAssertEqual(view.alpha, 1, accuracy: 0.001)
        XCTAssertNil(PNViewState.existing(for: view)?.props["opacity"])
    }

    func testRejectedCommitsMountNothing() {
        let core = PNCoreHarness()
        core.roots = [1]
        core.commit([["c", 1, "View", ["no_such_prop": 1]]], expectOK: false)
        XCTAssertNil(PNViewRegistry.shared.view(for: 1))
        XCTAssertEqual(core.revision, 0)
    }

    func testCommandsRunAfterTheirMountAndReply() throws {
        let core = PNCoreHarness()
        core.roots = [1]
        PNBridge.shared.setCallback { kind, tag, name, payload in
            PNEventCapture.record(kind.map { String(cString: $0) } ?? "", tag, name.map { String(cString: $0) } ?? "",
                                  payload.map { String(cString: $0) } ?? "{}")
        }
        PNEventCapture.reset()
        defer { PNBridge.shared.setCallback(nil) }
        var replies: [[String: Any]] { PNEventCapture.all.filter { $0.kind == "command" }.map { $0.payload } }
        core.commit([["c", 1, "TextInput", ["value": "hello"]]])
        let reply = "{\"start\": 1, \"end\": 3}".withCString { pn_core_command(PNCore.handle, PNCore.surface, 1, "set_selection", $0, 9) }
        pn_core_free(reply)
        PNMounter.drain()
        let delivered = expectation(for: NSPredicate { _, _ in !replies.isEmpty }, evaluatedWith: nil)
        wait(for: [delivered], timeout: 5)
        XCTAssertEqual(replies.first?["call_id"] as? Int, 9)
        XCTAssertEqual(replies.first?["ok"] as? Bool, true)
        let field = try XCTUnwrap(PNViewRegistry.shared.view(for: 1) as? UITextField)
        let range = try XCTUnwrap(field.selectedTextRange)
        XCTAssertEqual(field.offset(from: field.beginningOfDocument, to: range.start), 1)
    }
}
