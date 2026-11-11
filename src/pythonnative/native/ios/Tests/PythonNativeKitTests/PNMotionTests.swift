import XCTest
import PNCore
import UIKit
@testable import PythonNativeKit

/// Motion on the iOS host (RFC 0009): the write format, paint props routed
/// like static updates, exits of both owners, shared-element transitions,
/// and list item animations.
final class PNMotionTests: XCTestCase {
    private var window: UIWindow!
    private var core: PNCoreHarness!

    override func setUp() {
        super.setUp()
        core = PNCoreHarness()
        PNEventCapture.reset()
        PNBridge.shared.setCallback { kind, tag, name, payload in
            PNEventCapture.record(kind.map { String(cString: $0) } ?? "", tag, name.map { String(cString: $0) } ?? "",
                                  payload.map { String(cString: $0) } ?? "{}")
        }
    }

    override func tearDown() {
        PNBridge.shared.setCallback(nil)
        window?.isHidden = true
        window?.rootViewController = nil
        window = nil
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    private func show(_ view: UIView) {
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let controller = UIViewController()
        controller.view = view
        window.rootViewController = controller
        window.makeKeyAndVisible()
    }

    private func settle(_ seconds: TimeInterval = 0.6) {
        let ready = expectation(description: "native work settles")
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { ready.fulfill() }
        wait(for: [ready], timeout: seconds + 3)
        window?.layoutIfNeeded()
    }

    /// Spin the main run loop in small steps until `condition` holds.
    private func waitUntil(_ description: String, timeout: TimeInterval = 3, file: StaticString = #filePath, line: UInt = #line,
                           _ condition: () -> Bool) {
        let deadline = Date(timeIntervalSinceNow: timeout)
        while !condition() {
            guard Date() < deadline else { return XCTFail("timed out: \(description)", file: file, line: line) }
            RunLoop.main.run(until: Date(timeIntervalSinceNow: 0.005))
        }
    }

    private func view(_ tag: Int64) -> UIView? { PNViewRegistry.shared.view(for: tag) }

    // MARK: - Write encoding

    private struct Writes {
        var bytes: [UInt8] = []
        var count: UInt32 = 0
        mutating func u8(_ v: UInt8) { bytes.append(v) }
        mutating func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { bytes += $0 } }
        mutating func i64(_ v: Int64) { withUnsafeBytes(of: v.littleEndian) { bytes += $0 } }
        mutating func f64(_ v: Double) { withUnsafeBytes(of: v.bitPattern.littleEndian) { bytes += $0 } }
        mutating func str(_ s: String) { u32(UInt32(s.utf8.count)); bytes += Array(s.utf8) }
        mutating func value(_ v: Any) {
            switch v {
            case is NSNull: u8(0)
            case let b as Bool: u8(b ? 2 : 1)
            case let i as Int: u8(3); i64(Int64(i))
            case let d as Double: u8(4); f64(d)
            case let s as String: u8(5); str(s)
            case let a as [Any]: u8(6); u32(UInt32(a.count)); a.forEach { value($0) }
            case let o as [String: Any]:
                u8(7); u32(UInt32(o.count))
                for (key, item) in o { str(key); value(item) }
            default: XCTFail("unencodable \(v)")
            }
        }
        mutating func prop(_ tag: Int64, _ name: String, _ v: Any) { count += 1; u8(0); i64(tag); str(name); value(v) }
        mutating func frame(_ tag: Int64, _ x: Double, _ y: Double, _ w: Double, _ h: Double) {
            count += 1; u8(1); i64(tag); f64(x); f64(y); f64(w); f64(h)
        }
        mutating func remove(_ tags: [Int64]) { count += 1; u8(2); u32(UInt32(tags.count)); tags.forEach { i64($0) } }
        var encoded: [UInt8] {
            var head = Writes()
            head.u32(count)
            return head.bytes + bytes
        }
    }

    private func decode(_ writes: Writes) throws -> [PNMotionWrite] {
        let bytes = writes.encoded
        return try bytes.withUnsafeBytes { try PNMountDecoder.writes($0.baseAddress!, count: bytes.count) }
    }

    private func apply(_ writes: Writes) throws {
        PNMounter.apply(writes: try decode(writes))
    }

    func testWritesDecodeEveryKind() throws {
        var writes = Writes()
        writes.prop(7, "opacity", 0.5)
        writes.prop(7, "transform", NSNull())
        writes.frame(7, 1, 2, 3, 4)
        writes.remove([9, 8])
        let decoded = try decode(writes)
        XCTAssertEqual(decoded.count, 4)
        guard case let .prop(tag, name, value) = decoded[0] else { return XCTFail("\(decoded[0])") }
        XCTAssertEqual(tag, 7)
        XCTAssertEqual(name, "opacity")
        XCTAssertEqual(PNProps.double(value), 0.5)
        guard case let .prop(_, _, reset) = decoded[1] else { return XCTFail("\(decoded[1])") }
        XCTAssertTrue(reset is NSNull)
        guard case let .frame(_, x, y, w, h) = decoded[2] else { return XCTFail("\(decoded[2])") }
        XCTAssertEqual([x, y, w, h], [1, 2, 3, 4])
        guard case let .remove(tags) = decoded[3] else { return XCTFail("\(decoded[3])") }
        XCTAssertEqual(tags, [9, 8])

        var unknown = Writes()
        unknown.count = 1
        unknown.u8(9)
        XCTAssertThrowsError(try decode(unknown))
        var truncated = writes.encoded
        truncated.removeLast()
        XCTAssertThrowsError(try truncated.withUnsafeBytes { try PNMountDecoder.writes($0.baseAddress!, count: truncated.count) })
    }

    // MARK: - Paint props

    func testPropWritesApplyLikeStaticUpdates() throws {
        core.roots = [1]
        core.commit([["c", 1, "View", ["flex": 1, "background_color": "#FFFFFF"]],
                     ["c", 2, "View", ["width": 100, "height": 100, "background_color": "#000000", "transform": [["rotate": "90deg"]]]],
                     ["c", 3, "Text", ["text": "hello", "color": "#000000"]],
                     ["i", 1, 2, 0], ["i", 1, 3, 1]])
        let box = try XCTUnwrap(view(2))
        let label = try XCTUnwrap(view(3) as? UILabel)
        XCTAssertEqual(box.transform.b, 1, accuracy: 0.001, "the static rotate")

        var writes = Writes()
        writes.prop(2, "opacity", 0.25)
        writes.prop(2, "transform", [["translate_x": 12]])
        writes.prop(2, "background_color", "#FF00FF00")
        writes.prop(2, "border_radius", 6)
        writes.prop(2, "z_index", 3)
        writes.prop(2, "shadow_opacity", 0.5)
        writes.prop(3, "color", "#FFFF0000")
        writes.prop(404, "opacity", 0)
        try apply(writes)
        XCTAssertEqual(box.alpha, 0.25, accuracy: 0.001)
        XCTAssertEqual(box.transform.tx, 12, accuracy: 0.001)
        XCTAssertEqual(box.transform.b, 0, accuracy: 0.001, "a written transform replaces the static list")
        XCTAssertEqual(box.backgroundColor.map(PNColor.hexString), "#FF00FF00")
        XCTAssertEqual(box.layer.cornerRadius, 6, accuracy: 0.001)
        XCTAssertEqual(box.layer.zPosition, 3)
        XCTAssertEqual(box.layer.shadowOpacity, 0.5, accuracy: 0.001)
        let color = label.attributedText?.attribute(.foregroundColor, at: 0, effectiveRange: nil) as? UIColor
        XCTAssertEqual(color.map(PNColor.hexString), "#FFFF0000", "text color goes through the label's layout")

        // A corner key composes with the written `border_radius` in the merged props.
        var corner = Writes()
        corner.prop(2, "border_top_left_radius", 20)
        try apply(corner)
        XCTAssertEqual(PNViewState.existing(for: box)?.cornerRadii, [20, 6, 6, 6])

        // A commit that changes another key leaves written values alone.
        core.commit([["u", 2, ["background_color": "#0000FF"], []]])
        XCTAssertEqual(box.alpha, 0.25, accuracy: 0.001, "the write wins until the core writes the key again")
        XCTAssertEqual(box.transform.tx, 12, accuracy: 0.001)

        // `null` restores the default; the core sends a committed value explicitly.
        var reset = Writes()
        reset.prop(2, "opacity", NSNull())
        reset.prop(2, "transform", NSNull())
        try apply(reset)
        XCTAssertEqual(box.alpha, 1, accuracy: 0.001)
        XCTAssertTrue(CATransform3DIsIdentity(box.layer.transform))
        XCTAssertNil(PNViewState.existing(for: box)?.props["opacity"])
        var restore = Writes()
        restore.prop(2, "transform", [["rotate": "90deg"]])
        try apply(restore)
        XCTAssertEqual(box.transform.b, 1, accuracy: 0.001)
    }

    func testFrameAndRemoveWrites() throws {
        core.roots = [1]
        core.commit([["c", 1, "View", ["flex": 1, "background_color": "#FFFFFF"]],
                     ["c", 2, "View", ["width": 50, "height": 50, "background_color": "#000000"]],
                     ["c", 3, "View", ["width": 10, "height": 10, "background_color": "#FF0000"]],
                     ["i", 2, 3, 0], ["i", 1, 2, 0]])
        let box = try XCTUnwrap(view(2))
        let leaf = try XCTUnwrap(view(3))
        var writes = Writes()
        writes.frame(2, 10, 20, 30, 40)
        try apply(writes)
        XCTAssertEqual(box.frame, CGRect(x: 10, y: 20, width: 30, height: 40))

        var remove = Writes()
        remove.remove([3, 2, 99])
        try apply(remove)
        XCTAssertNil(view(2))
        XCTAssertNil(view(3))
        XCTAssertNil(box.superview)
        XCTAssertNil(leaf.superview)
        XCTAssertEqual(PNMounter.childTags(of: 1), [])
    }

    // MARK: - Layout animations through the core

    func testEnteringViewStartsFromItsInitialStyleInTheSameTurn() throws {
        core.roots = [1]
        core.commit([["c", 1, "View", ["flex": 1, "background_color": "#FFFFFF"]]])
        core.commit([["c", 2, "View", ["width": 40, "height": 40, "background_color": "#000000",
                                       "entering": ["type": "fade_in", "duration": 120, "delay": 0, "easing": "linear"]]],
                     ["i", 1, 2, 0]])
        let box = try XCTUnwrap(view(2))
        XCTAssertEqual(box.alpha, 0, accuracy: 0.001, "the initial value is written before the first frame")
        core.frames(4)
        XCTAssertGreaterThan(box.alpha, 0)
        XCTAssertLessThan(box.alpha, 1)
        core.frames(30)
        XCTAssertEqual(box.alpha, 1, accuracy: 0.001)
    }

    func testCoreOwnedExitKeepsTheViewAndSkipsItInInsertIndices() throws {
        core.roots = [1]
        core.commit([["c", 1, "View", ["flex": 1, "background_color": "#FFFFFF"]],
                     ["c", 2, "View", ["height": 20, "background_color": "#FF0000",
                                       "exiting": ["type": "fade_out", "duration": 120, "delay": 0, "easing": "linear"]]],
                     ["c", 3, "View", ["height": 20, "background_color": "#00FF00"]],
                     ["i", 1, 2, 0], ["i", 1, 3, 1]])
        let root = try XCTUnwrap(view(1))
        let leaving = try XCTUnwrap(view(2))
        let frame = leaving.frame
        core.commit([["d", 2]])
        XCTAssertTrue(view(2) === leaving, "an exiting view stays registered")
        XCTAssertTrue(leaving.superview === root)
        XCTAssertEqual(leaving.frame, frame, "and stays where it was")
        XCTAssertFalse(leaving.isUserInteractionEnabled)
        XCTAssertTrue(PNMounter.isExiting(2))

        // The core's indices count only children that aren't exiting.
        core.commit([["c", 4, "View", ["height": 20, "background_color": "#0000FF"]],
                     ["c", 5, "View", ["height": 20, "background_color": "#00FFFF"]],
                     ["i", 1, 4, 1], ["i", 1, 5, 0]])
        XCTAssertEqual(PNMounter.childTags(of: 1), [2, 5, 3, 4])
        XCTAssertEqual(root.subviews.map { PNViewState.existing(for: $0)?.tag }, [2, 5, 3, 4])

        core.frames(4)
        XCTAssertLessThan(leaving.alpha, 1, "the core animates the exit with writes")
        core.frames(30)
        XCTAssertNil(view(2), "the remove write destroys it")
        XCTAssertNil(leaving.superview)
        XCTAssertFalse(PNMounter.isExiting(2))
        XCTAssertEqual(root.subviews.map { PNViewState.existing(for: $0)?.tag }, [5, 3, 4])
    }

    // MARK: - Platform-owned exits

    func testPoppedScreenKeepsItsContentUntilThePopEnds() throws {
        core.commit([["c", 7001, "ScreenStack", ["flex": 1, "_pn_events": ["on_native_back"]]],
                     ["c", 7002, "Screen", ["title": "Inbox", "flex": 1]],
                     ["c", 7003, "Screen", ["title": "Detail", "flex": 1]],
                     ["c", 7004, "View", ["width": 40, "height": 40, "background_color": "#FF0000"]],
                     ["i", 7003, 7004, 0], ["i", 7001, 7002, 0], ["i", 7001, 7003, 1]])
        let stack = try XCTUnwrap(view(7001))
        show(stack)
        settle()
        let navigation = try XCTUnwrap(PNScreenStackManager.navigationController(of: stack))
        XCTAssertEqual(navigation.viewControllers.count, 2)
        let screen = try XCTUnwrap(view(7003))
        let content = try XCTUnwrap(view(7004))

        core.commit([["d", 7004], ["d", 7003]])
        XCTAssertTrue(view(7003) === screen)
        XCTAssertTrue(view(7004) === content)
        XCTAssertTrue(content.superview === screen, "the leaving screen keeps its content")
        waitUntil("the pop starts") { navigation.viewControllers.count == 1 }
        XCTAssertTrue(view(7004) === content, "content survives the pop animation")
        XCTAssertTrue(content.superview === screen)
        waitUntil("the pop ends and the core removes the screen") { self.view(7003) == nil && self.view(7004) == nil }
        XCTAssertTrue(PNEventCapture.events(named: "on_native_back").isEmpty, "a programmatic pop isn't a native back")
        XCTAssertEqual(navigation.viewControllers.map(\.title), ["Inbox"])
    }

    func testRemovedModalDismissesBeforeItsSubtreeIsDestroyed() throws {
        core.commit([["c", 7100, "View", ["flex": 1, "background_color": "#FFFFFF"]],
                     ["c", 7101, "Modal", ["visible": true]],
                     ["c", 7102, "View", ["width": 40, "height": 40, "background_color": "#FF0000"]],
                     ["i", 7101, 7102, 0], ["i", 7100, 7101, 0]])
        let modal = try XCTUnwrap(view(7101))
        let presentation = try XCTUnwrap(PNViewState.existing(for: modal)?.extras["modal"] as? PNModalManager.Presentation)
        let presented = presentation.controller
        waitUntil("the modal presents") { presented.presentingViewController != nil && !presented.isBeingPresented }
        let content = try XCTUnwrap(view(7102))
        XCTAssertTrue(content.isDescendant(of: presented.view))

        core.commit([["d", 7102], ["d", 7101]])
        XCTAssertTrue(view(7102) === content, "the content stays while the modal dismisses")
        XCTAssertTrue(content.isDescendant(of: presented.view))
        XCTAssertTrue(presented.isBeingDismissed, "the dismissal is running")
        waitUntil("the dismissal ends and the core removes the modal") { self.view(7101) == nil && self.view(7102) == nil }
        XCTAssertNil(presented.presentingViewController)
    }

    // MARK: - Shared elements

    func testSharedElementsFlyOnPushAndPop() throws {
        core.roots = [7201]
        core.commit([["c", 7201, "ScreenStack", ["flex": 1, "_pn_events": ["on_native_back"]]],
                     ["c", 7202, "Screen", ["title": "List", "flex": 1]],
                     ["c", 7203, "View", ["width": 40, "height": 40, "background_color": "#FF0000", "border_radius": 4,
                                          "shared_tag": "hero"]],
                     ["i", 7202, 7203, 0], ["i", 7201, 7202, 0]])
        let stack = try XCTUnwrap(view(7201))
        show(stack)
        settle()
        let navigation = try XCTUnwrap(PNScreenStackManager.navigationController(of: stack))
        let source = try XCTUnwrap(view(7203))

        core.commit([["c", 7204, "Screen", ["title": "Detail", "flex": 1]],
                     ["c", 7205, "View", ["width": 200, "height": 120, "background_color": "#0000FF", "shared_tag": "hero",
                                          "shared_transition": ["duration": 400, "easing": "ease_in_out"]]],
                     ["i", 7204, 7205, 0], ["i", 7201, 7204, 1]])
        let target = try XCTUnwrap(view(7205))
        let parent = try XCTUnwrap(target.superview)
        let pairs = PNSharedElements.pairs(from: 7202, to: 7204)
        XCTAssertEqual(pairs.count, 1)
        XCTAssertEqual(pairs.first?.name, "hero")
        XCTAssertEqual(pairs.first?.source, 7203)
        XCTAssertEqual(pairs.first?.target, 7205)
        XCTAssertEqual(PNProps.double(pairs.first?.transition?["duration"]), 400)

        waitUntil("the destination flies") { PNSharedElementTransition.isFlying(target) }
        XCTAssertFalse(target.superview === parent, "lifted into the transition's container")
        XCTAssertEqual(source.alpha, 0, "the source hides during the flight")
        waitUntil("the push lands") { !PNSharedElementTransition.isFlying(target) && navigation.transitionCoordinator == nil }
        XCTAssertTrue(target.superview === parent, "back in its own parent")
        XCTAssertEqual(target.bounds.size, CGSize(width: 200, height: 120))
        XCTAssertEqual(source.alpha, 1)
        XCTAssertEqual(target.layer.cornerRadius, 0, accuracy: 0.001, "the destination keeps its own style")
        XCTAssertEqual(navigation.viewControllers.count, 2)

        // The delegate picks the shared-element animator for screens that share views.
        let controllers = navigation.viewControllers
        let animator = navigation.delegate?.navigationController?(navigation, animationControllerFor: .pop, from: controllers[1], to: controllers[0])
        XCTAssertTrue(animator is PNSharedElementTransition)

        // Popping flies the list's view back in, and the leaving screen exits after.
        core.commit([["d", 7205], ["d", 7204]])
        waitUntil("the list's view flies") { PNSharedElementTransition.isFlying(source) }
        waitUntil("the pop lands and the detail screen is removed") {
            !PNSharedElementTransition.isFlying(source) && self.view(7204) == nil && self.view(7205) == nil
        }
        XCTAssertEqual(source.alpha, 1)
        XCTAssertEqual(source.bounds.size, CGSize(width: 40, height: 40))
        XCTAssertEqual(navigation.viewControllers.count, 1)
    }

    func testSharedElementPairsParseAndTiming() {
        let pairs = PNSharedElements.parse("""
        [{"name": "a", "source": 1, "target": 2, "transition": {"spring": {"duration": 450, "damping_ratio": 0.9}},
          "source_style": {"border_radius": 8}, "target_style": {}},
         {"name": "b", "source": 3, "target": 4, "transition": null, "source_style": {}, "target_style": {}},
         {"name": "broken"}]
        """)
        XCTAssertEqual(pairs.map(\.name), ["a", "b"])
        XCTAssertNil(pairs[1].transition)
        let spring = PNMotionTiming(pairs[0].transition)
        XCTAssertEqual(spring.duration, 0.45, accuracy: 1e-9)
        XCTAssertEqual(spring.curve, .spring(dampingRatio: 0.9))
        let timed = PNMotionTiming(["duration": 200, "easing": [0.1, 0.2, 0.3, 0.4]])
        XCTAssertEqual(timed.duration, 0.2, accuracy: 1e-9)
        XCTAssertEqual(timed.curve, .bezier(CGPoint(x: 0.1, y: 0.2), CGPoint(x: 0.3, y: 0.4)))
        let fallback = PNMotionTiming(nil)
        XCTAssertEqual(fallback.duration, 0.35, accuracy: 1e-9)
        XCTAssertEqual(PNMotionTiming(["easing": "linear"]).curve, .bezier(.zero, CGPoint(x: 1, y: 1)))
        // The core's exact beziers for t² and t³.
        XCTAssertEqual(PNMotionTiming(["easing": "quad"]).curve, .bezier(CGPoint(x: 1.0 / 3.0, y: 0), CGPoint(x: 2.0 / 3.0, y: 1.0 / 3.0)))
        XCTAssertEqual(PNMotionTiming(["easing": "cubic"]).curve, .bezier(CGPoint(x: 1.0 / 3.0, y: 0), CGPoint(x: 2.0 / 3.0, y: 0)))
        XCTAssertEqual(PNSharedElements.parse("not json").count, 0)
    }

    // MARK: - List item animations

    func testListDiffReportsDeletesInsertsAndOnlyRealMoves() {
        let diff = PNListDiff(["a", "b", "c", "d"], ["b", "a", "d", "e"])
        XCTAssertEqual(diff.deleted, [2])
        XCTAssertEqual(diff.inserted, [3])
        XCTAssertEqual(diff.moved.count, 1, "one of a/b moves; d keeps its relative order")
        let shifted = PNListDiff(["a", "b"], ["x", "a", "b"])
        XCTAssertEqual(shifted.inserted, [0])
        XCTAssertTrue(shifted.moved.isEmpty, "a shift isn't a move")
    }

    func testListPresetsSetStartAndEndAttributes() {
        let extent = CGSize(width: 300, height: 600)
        func attributes(_ preset: [String: Any]) -> UICollectionViewLayoutAttributes {
            let attributes = UICollectionViewLayoutAttributes(forCellWith: IndexPath(item: 0, section: 0))
            PNListItemAnimations.apply(preset, to: attributes, appearing: true, extent: extent)
            return attributes
        }
        XCTAssertEqual(attributes(["type": "fade_in"]).alpha, 0)
        XCTAssertEqual(attributes(["type": "slide_in", "edge": "left"]).transform.tx, -300)
        XCTAssertEqual(attributes(["type": "slide_out", "edge": "bottom"]).transform.ty, 600)
        XCTAssertEqual(attributes(["type": "zoom_out"]).transform.a, 0.01, accuracy: 1e-6)
        XCTAssertNil(PNListItemAnimations([:]))
        XCTAssertNotNil(PNListItemAnimations(["item_layout": ["type": "linear", "duration": 250]]))
        let timing = PNListItemAnimations(["item_entering": ["type": "fade_in", "duration": 100],
                                           "item_exiting": ["type": "fade_out", "duration": 500]])?.timing
        XCTAssertEqual(timing?.duration ?? 0, 0.5, accuracy: 1e-9, "the batch runs as long as its longest preset")
    }

    func testListAnimatesDatasetPatchesWithBatchUpdates() throws {
        func row(_ key: String) -> [Any] { [key, 1, 40.0, false] }
        core.commit([["c", 7301, "VirtualList", [
            "dataset": ["base": 0, "revision": 1, "changes": [["reset", [row("a"), row("b"), row("c")]]]],
            "item_entering": ["type": "fade_in", "duration": 150],
            "item_exiting": ["type": "slide_out", "edge": "left", "duration": 150],
            "item_layout": ["type": "linear", "duration": 150],
        ]]])
        let list = try XCTUnwrap(view(7301) as? UICollectionView)
        list.frame = CGRect(x: 0, y: 0, width: 300, height: 400)
        show(list)
        settle(0.3)
        XCTAssertEqual(list.numberOfItems(inSection: 0), 3)

        core.commit([["u", 7301, ["dataset": ["base": 1, "revision": 2, "changes": [
            ["i", 1, row("x")], ["d", "a"], ["m", "c", 0],
        ]]], []]])
        XCTAssertEqual(list.numberOfItems(inSection: 0), 3, "the batch update leaves UIKit's count in step")
        settle(0.5)
        XCTAssertEqual(list.numberOfItems(inSection: 0), 3)
        XCTAssertEqual(list.visibleCells.count, 3)
        let keys = list.indexPathsForVisibleItems.sorted().compactMap { pn_core_list_key(PNCore.handle, PNCore.surface, 7301, Int64($0.item)) }
            .map { pointer -> String in
                defer { pn_core_free(pointer) }
                return String(cString: pointer)
            }
        XCTAssertEqual(keys, ["c", "x", "b"])
    }
}
