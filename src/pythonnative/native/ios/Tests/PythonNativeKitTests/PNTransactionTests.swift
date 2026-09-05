import XCTest
@testable import PythonNativeKit

final class PNTransactionTests: XCTestCase {
    override func tearDown() {
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    func testDecodesEveryOpcode() throws {
        let json = """
        [["c", 1, "View", {"background_color": "#ff0000"}],
         ["u", 1, {"opacity": 0.5}],
         ["c", 2, "Text", {"text": "hi"}],
         ["i", 1, 2, 0],
         ["f", 2, 1.5, 2.5, 100, 20],
         ["d", 2]]
        """
        let ops = try PNTransaction.decode(json)
        XCTAssertEqual(ops.count, 6)
        XCTAssertEqual(ops[0], .create(tag: 1, type: "View", props: ["background_color": "#ff0000"]))
        XCTAssertEqual(ops[1], .update(tag: 1, changed: ["opacity": 0.5]))
        XCTAssertEqual(ops[3], .insert(parent: 1, child: 2, index: 0))
        XCTAssertEqual(ops[4], .frame(tag: 2, x: 1.5, y: 2.5, w: 100, h: 20))
        XCTAssertEqual(ops[5], .destroy(tag: 2))
    }

    func testInfinityStringsBecomeInfinity() throws {
        let ops = try PNTransaction.decode("[[\"c\", 5, \"View\", {\"max_width\": \"inf\", \"nested\": {\"h\": \"inf\"}}]]")
        guard case let .create(_, _, props) = ops[0] else { return XCTFail("expected create") }
        XCTAssertEqual(props["max_width"] as? Double, Double.infinity)
        XCTAssertEqual((props["nested"] as? [String: Any])?["h"] as? Double, Double.infinity)
    }

    func testMalformedOpsAreSkippedNotFatal() throws {
        let ops = try PNTransaction.decode("[[\"c\", 1, \"View\", {}], [\"zz\", 9], [\"u\"], 42, [\"d\", 1]]")
        XCTAssertEqual(ops.count, 2)
        XCTAssertEqual(ops[0], .create(tag: 1, type: "View", props: [:]))
        XCTAssertEqual(ops[1], .destroy(tag: 1))
    }

    func testNonArrayDocumentThrows() {
        XCTAssertThrowsError(try PNTransaction.decode("{\"not\": \"an array\"}"))
    }

    func testApplyBuildsHierarchyAndIsolatesFailures() {
        PNTransaction.apply("""
        [["c", 10, "View", {"background_color": "#00ff00"}],
         ["c", 11, "Text", {"text": "hello"}],
         ["u", 999, {"opacity": 0.1}],
         ["i", 10, 11, 0],
         ["i", 10, 12345, 0],
         ["f", 11, 4, 8, 120, 30],
         ["c", 13, "NoSuchType", {}]]
        """)
        let parent = PNViewRegistry.shared.view(for: 10)
        let child = PNViewRegistry.shared.view(for: 11)
        XCTAssertNotNil(parent)
        XCTAssertNotNil(child)
        XCTAssertTrue(child?.superview === parent)
        XCTAssertEqual(child?.frame, CGRect(x: 4, y: 8, width: 120, height: 30))
        XCTAssertNotNil(PNViewRegistry.shared.view(for: 13), "unknown types get a placeholder view")
        XCTAssertEqual(PNViewRegistry.shared.resolve(13)?.typeName, "NoSuchType")

        PNTransaction.apply("[[\"d\", 11]]")
        XCTAssertNil(PNViewRegistry.shared.view(for: 11))
        XCTAssertEqual(parent?.subviews.count, 0)
    }

    func testInsertIsMoveAwareAndClamps() {
        PNTransaction.apply("""
        [["c", 20, "View", {}], ["c", 21, "View", {}], ["c", 22, "View", {}], ["c", 23, "View", {}],
         ["i", 20, 21, 0], ["i", 20, 22, 1], ["i", 20, 23, 99]]
        """)
        let parent = PNViewRegistry.shared.view(for: 20)
        XCTAssertEqual(parent?.subviews.map { PNViewState.existing(for: $0)?.tag }, [21, 22, 23])
        PNTransaction.apply("[[\"i\", 20, 23, 0]]")
        XCTAssertEqual(parent?.subviews.map { PNViewState.existing(for: $0)?.tag }, [23, 21, 22])
        XCTAssertEqual(parent?.subviews.count, 3)
    }

    func testFrameClampsNonFiniteValues() {
        PNTransaction.apply("[[\"c\", 30, \"View\", {}]]")
        guard let record = PNViewRegistry.shared.resolve(30) else { return XCTFail("missing view") }
        record.manager.setFrame(view: record.view, x: .nan, y: 5, w: .infinity, h: -3)
        XCTAssertEqual(record.view.frame.origin.x, 0)
        XCTAssertEqual(record.view.frame.origin.y, 5)
        XCTAssertEqual(record.view.frame.size.height, 0)
        XCTAssertTrue(record.view.frame.size.width.isFinite)
    }
}
