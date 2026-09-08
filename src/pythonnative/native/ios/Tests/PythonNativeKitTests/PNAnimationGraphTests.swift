import XCTest
@testable import PythonNativeKit

final class PNAnimationGraphTests: XCTestCase {
    override func tearDown() {
        PNAnimationGraph.forget(9401)
        super.tearDown()
    }

    func testDerivedGraphReplacementKeepsDriverAndReleasesItOnUnmount() {
        let nodes: [[String: Any]] = [
            ["id": 101, "kind": "value", "value": 0.0],
            ["id": 102, "kind": "multiply", "inputs": [["node": 101], ["constant": 2.0]]],
        ]
        PNAnimationGraph.install(["id": 101, "nodes": nodes, "bindings": [[9401, "opacity", 102]]])
        PNAnimationGraph.set(101, 0.25)
        XCTAssertEqual(PNAnimationGraph.values[102], 0.5)
        XCTAssertTrue(PNAnimationGraph.start(9501, node: 101, spec: ["kind": "timing", "to": 1.0]))
        PNAnimationGraph.install(["id": 100, "nodes": nodes, "bindings": [[9401, "opacity", 102]]])
        XCTAssertNotNil(PNAnimationGraph.drivers[9501])
        XCTAssertEqual(PNAnimationGraph.values[101], 0.25)
        PNAnimationGraph.forget(9401)
        XCTAssertNil(PNAnimationGraph.drivers[9501])
        XCTAssertNil(PNAnimationGraph.values[101])
    }
}
