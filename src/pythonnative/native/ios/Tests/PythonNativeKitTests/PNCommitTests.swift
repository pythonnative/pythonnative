import XCTest
@testable import PythonNativeKit

final class PNCommitTests: XCTestCase {
    private let app = UUID().uuidString

    private func commit(_ operations: [[Any]], revision: Int = 1) -> [String: Any] {
        PNJSON.decodeObject(PNCommit.apply(PNJSON.encode([
            "version": 2, "application": app, "surface": 1,
            "revision": revision, "ops": operations,
        ])))
    }

    override func tearDown() {
        _ = PNCommit.apply(PNJSON.encode([
            "version": 2, "application": UUID().uuidString, "surface": 1,
            "revision": 1, "ops": [],
        ]))
        super.tearDown()
    }

    func testInvalidInsertionDoesNotPartiallyCreateWidgets() {
        let result = commit([["c", 9101, "View", [:]], ["c", 9102, "Text", ["text": "pending"]], ["i", 9101, 9102, 3]])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertNil(PNViewRegistry.shared.view(for: 9101))
        XCTAssertNil(PNViewRegistry.shared.view(for: 9102))
        XCTAssertEqual(commit([["c", 9101, "View", [:]]])["ok"] as? Bool, true)
    }

    func testTypedUpdatesValidateTagsCreatedInTheSameCommit() {
        let result = commit([["c", 9201, "TextInput", ["value": "valid"]], ["u", 9201, ["value": 12]]])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertNil(PNViewRegistry.shared.view(for: 9201))
    }

    func testHorizontalListMeasuresRowsAlongTheirWidth() {
        let result = commit([
            ["c", 9601, "VirtualList", ["keys": ["one"], "revision": 1, "horizontal": true, "width": 300, "height": 100]],
            ["c", 9602, "View", ["_pn_list_key": "one", "width": 80, "height": 100]],
            ["i", 9601, 9602, 0],
        ])
        XCTAssertEqual(result["ok"] as? Bool, true)
        PNViewRegistry.shared.view(for: 9601)?.frame = CGRect(x: 0, y: 0, width: 300, height: 100)
        let frames = PNLayout.compute(["roots": [Int64(9601)], "width": 300, "height": 100])
        let row = frames.first { $0.first == 9602 }
        XCTAssertEqual(row?[3], 80)
        XCTAssertEqual(row?[4], 100)
    }

    func testPortalLaysOutAgainstItsViewportWithoutAScreenParent() {
        XCTAssertEqual(commit([
            ["c", 9700, "View", [:]],
            ["c", 9701, "Portal", [:]],
            ["c", 9702, "View", ["position": "absolute", "left": 24, "right": 24, "bottom": 40, "height": 80]],
            ["c", 9703, "View", ["height": 30]],
            ["c", 9704, "View", ["height": 20]],
            ["i", 9701, 9702, 0],
            ["i", 9701, 9703, 1],
            ["i", 9701, 9704, 2],
        ])["ok"] as? Bool, true)
        let request: [String: Any] = ["roots": [Int64(9700)], "width": 320, "height": 640]
        // The native overlay can be smaller than the screen, for example below a navigation bar.
        PNViewRegistry.shared.view(for: 9701)?.frame = CGRect(x: 0, y: 0, width: 300, height: 600)
        let frames = PNLayout.compute(request)
        XCTAssertTrue(frames.flatMap { $0 }.allSatisfy { $0.isFinite })
        XCTAssertEqual(frames.first { $0.first == 9701 }, [9701, 0, 0, 300, 600])
        XCTAssertEqual(frames.first { $0.first == 9702 }, [9702, 24, 480, 252, 80])
        XCTAssertEqual(frames.first { $0.first == 9704 }, [9704, 0, 30, 300, 20])
        XCTAssertTrue(PNLayout.compute(request).isEmpty)

        PNViewRegistry.shared.view(for: 9701)?.frame = CGRect(x: 0, y: 0, width: 400, height: 700)
        let resized = PNLayout.compute(request)
        XCTAssertEqual(resized.first { $0.first == 9702 }, [9702, 24, 580, 352, 80])
        XCTAssertEqual(commit([["d", 9702], ["d", 9703], ["d", 9704], ["d", 9701]], revision: 2)["ok"] as? Bool, true)
        XCTAssertNil(PNLayout.nodes[9701])
        XCTAssertTrue(PNLayout.compute(request).isEmpty)
    }

    func testReplayCannotDestroyAnAcceptedWidget() {
        XCTAssertEqual(commit([["c", 9301, "View", [:]]])["ok"] as? Bool, true)
        XCTAssertEqual(commit([["d", 9301]])["ok"] as? Bool, false)
        XCTAssertNotNil(PNViewRegistry.shared.view(for: 9301))
        XCTAssertEqual(commit([["d", 9301]], revision: 2)["ok"] as? Bool, true)
        XCTAssertNil(PNViewRegistry.shared.view(for: 9301))
    }
}
