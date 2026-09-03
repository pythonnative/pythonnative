import XCTest
@testable import PythonNativeKit

final class PNGestureTests: XCTestCase {
    override func tearDown() {
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    func testSpecsBecomeRecognizersWithRelationships() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 1, props: [
            "gestures": [
                ["kind": "tap", "n_taps": 2, "simultaneous": [1], "wait_for": []],
                ["kind": "pan", "min_distance": 10, "simultaneous": [0], "wait_for": []],
                ["kind": "long_press", "min_duration_ms": 800, "simultaneous": [], "wait_for": [0]],
                ["kind": "swipe", "direction": "left", "simultaneous": [], "wait_for": []],
                ["kind": "pinch", "simultaneous": [], "wait_for": []],
                ["kind": "rotation", "simultaneous": [], "wait_for": []],
                ["kind": "fling", "direction": "down", "n_pointers": 2, "simultaneous": [], "wait_for": []],
            ],
        ])
        let recognizers = PNViewState.existing(for: view)?.gestureRecognizers ?? []
        XCTAssertEqual(recognizers.count, 7)
        XCTAssertEqual((recognizers[0] as? UITapGestureRecognizer)?.numberOfTapsRequired, 2)
        XCTAssertTrue(recognizers[1] is UIPanGestureRecognizer)
        XCTAssertEqual((recognizers[2] as? UILongPressGestureRecognizer)?.minimumPressDuration ?? 0, 0.8, accuracy: 0.001)
        XCTAssertEqual((recognizers[3] as? UISwipeGestureRecognizer)?.direction, .left)
        XCTAssertTrue(recognizers[4] is UIPinchGestureRecognizer)
        XCTAssertTrue(recognizers[5] is UIRotationGestureRecognizer)
        XCTAssertEqual((recognizers[6] as? UISwipeGestureRecognizer)?.numberOfTouchesRequired, 2)
        XCTAssertEqual((recognizers[6] as? UISwipeGestureRecognizer)?.direction, .down)

        let coordinator = PNGestureCoordinator.shared
        XCTAssertEqual(coordinator.index(of: recognizers[2]), 2)
        XCTAssertTrue(coordinator.allowsSimultaneous(recognizers[0], recognizers[1]))
        XCTAssertFalse(coordinator.allowsSimultaneous(recognizers[0], recognizers[2]))
        XCTAssertFalse(coordinator.allowsSimultaneous(recognizers[3], recognizers[4]))
        XCTAssertTrue(view.isUserInteractionEnabled)
        XCTAssertTrue(recognizers.allSatisfy { $0.view === view && !$0.cancelsTouchesInView })
    }

    func testRewiringReplacesRecognizersAndUnknownKindsAreSkipped() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 2, props: ["gestures": [["kind": "tap"]]])
        XCTAssertEqual(view.gestureRecognizers?.count, 1)
        manager.update(view: view, changed: ["gestures": [["kind": "nonsense"], ["kind": "pan"]]])
        let recognizers = PNViewState.existing(for: view)?.gestureRecognizers ?? []
        XCTAssertEqual(recognizers.count, 1)
        XCTAssertTrue(recognizers[0] is UIPanGestureRecognizer)
        XCTAssertEqual(PNGestureCoordinator.shared.index(of: recognizers[0]), 1, "index follows the spec position")
        manager.update(view: view, changed: ["gestures": NSNull()])
        XCTAssertEqual(view.gestureRecognizers?.count ?? 0, 0)
    }

    func testStateAndDirectionNames() {
        XCTAssertEqual(PNGestureCoordinator.stateName(.began), "began")
        XCTAssertEqual(PNGestureCoordinator.stateName(.changed), "changed")
        XCTAssertEqual(PNGestureCoordinator.stateName(.ended), "ended")
        XCTAssertEqual(PNGestureCoordinator.stateName(.cancelled), "cancelled")
        XCTAssertEqual(PNGestureCoordinator.swipeDirection("up"), .up)
        XCTAssertEqual(PNGestureCoordinator.swipeDirection("any"), [.left, .right, .up, .down])
    }

    func testAnyDirectionSwipeInstallsOneRecognizerPerDirection() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 3, props: [
            "gestures": [
                ["kind": "tap", "simultaneous": [], "wait_for": [1]],
                ["kind": "swipe", "direction": "any", "simultaneous": [], "wait_for": []],
            ],
        ])
        let recognizers = PNViewState.existing(for: view)?.gestureRecognizers ?? []
        XCTAssertEqual(recognizers.count, 5, "one tap plus four single-direction swipes")
        let coordinator = PNGestureCoordinator.shared
        let swipes = recognizers.compactMap { $0 as? UISwipeGestureRecognizer }
        XCTAssertEqual(swipes.map { coordinator.direction(of: $0) }, ["left", "right", "up", "down"])
        XCTAssertEqual(swipes.map { $0.direction }, [.left, .right, .up, .down])
        XCTAssertTrue(swipes.allSatisfy { coordinator.index(of: $0) == 1 }, "every recognizer reports the spec index")
        XCTAssertNil(coordinator.direction(of: recognizers[0]))
    }

    func testAnimatorTimingParameters() {
        let timing = PNAnimator.timingParameters(kind: "timing", spec: ["duration_ms": 250, "easing": "linear"])
        XCTAssertEqual(timing.duration, 0.25, accuracy: 0.0001)
        let spring = PNAnimator.timingParameters(kind: "spring", spec: ["stiffness": 100, "damping": 10, "mass": 1, "from": 0, "to": 1])
        XCTAssertGreaterThan(spring.duration, 0.15)
        XCTAssertTrue(spring.parameters is UISpringTimingParameters)
        XCTAssertTrue(PNAnimator.curve(for: [0.1, 0.2, 0.3, 0.4]) is UICubicTimingParameters)
    }

    func testAnimatorSetAppliesImmediately() {
        PNTransaction.apply("[[\"c\", 50, \"View\", {}]]")
        _ = PNAnimator.shared.handle(tag: 50, request: ["op": "set", "prop": "opacity", "value": 0.25])
        XCTAssertEqual(PNViewRegistry.shared.view(for: 50)?.alpha ?? 0, 0.25, accuracy: 0.001)
        _ = PNAnimator.shared.handle(tag: 50, request: ["op": "set", "prop": "translate_x", "value": 12])
        XCTAssertEqual(PNViewRegistry.shared.view(for: 50)?.transform.tx ?? 0, 12, accuracy: 0.001)
        let rejected = PNAnimator.shared.handle(tag: 50, request: ["op": "start", "id": 1, "prop": "opacity", "spec": ["kind": "mystery"]])
        XCTAssertEqual((rejected as? [String: Any])?["ok"] as? Bool, false)
    }
}
