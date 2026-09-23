import XCTest
import UIKit
@testable import PythonNativeKit

/// Captures every native -> Python message so tests can assert on events.
enum PNEventCapture {
    struct Message { let kind: String; let tag: Int64; let name: String; let payload: [String: Any] }
    private static let lock = NSLock()
    private static var messages: [Message] = []

    static func record(_ kind: String, _ tag: Int64, _ name: String, _ payload: String) {
        lock.lock(); defer { lock.unlock() }
        messages.append(Message(kind: kind, tag: tag, name: name, payload: PNJSON.decodeObject(payload)))
    }
    static func reset() { lock.lock(); messages = []; lock.unlock() }
    static var all: [Message] { lock.lock(); defer { lock.unlock() }; return messages }
    static func events(named name: String) -> [Message] { all.filter { $0.kind == "event" && $0.name == name } }
}

private let captureCallback: PNCallbackFn = { kind, tag, name, payload in
    PNEventCapture.record(
        kind.map { String(cString: $0) } ?? "", tag,
        name.map { String(cString: $0) } ?? "", payload.map { String(cString: $0) } ?? "{}"
    )
    return nil
}

final class PNParityTests: XCTestCase {
    private var window: UIWindow!
    private var revision = 0
    private let application = UUID().uuidString

    override func setUp() {
        super.setUp()
        PNEventCapture.reset()
        PNBridge.shared.setCallback(captureCallback)
    }

    override func tearDown() {
        PNBridge.shared.setCallback(nil)
        window?.isHidden = true
        window?.rootViewController = nil
        window = nil
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    private func apply(_ ops: [[Any]]) {
        revision += 1
        let json = PNJSON.encode(["version": 4, "application": application, "surface": 1, "revision": revision, "ops": ops])
        let result = PNJSON.decodeObject(PNCommit.apply(json))
        XCTAssertEqual(result["ok"] as? Bool, true, String(describing: result))
    }

    private func settle(_ seconds: TimeInterval = 0.6) {
        let ready = expectation(description: "native work settles")
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { ready.fulfill() }
        wait(for: [ready], timeout: seconds + 3)
        window?.layoutIfNeeded()
    }

    private func show(_ view: UIView) {
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let controller = UIViewController()
        controller.view = view
        window.rootViewController = controller
        window.makeKeyAndVisible()
    }

    // MARK: - Transform composition

    func testAnimatedTransformChannelsComposeOverStaticTransform() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 5001, props: ["transform": [["rotate": "90deg"]]])
        manager.setAnimatedProperty(view: view, prop: "translate_x", value: 10)
        manager.setAnimatedProperty(view: view, prop: "translate_y", value: 5)
        let state = PNViewState.existing(for: view)!
        XCTAssertEqual(state.animatedTransform["translate_x"], 10)
        XCTAssertEqual(state.animatedTransform["translate_y"], 5, "binding translate_y must not wipe translate_x")
        // The static rotate stays applied...
        XCTAssertEqual(view.transform.b, 1, accuracy: 0.001)
        XCTAssertEqual(view.transform.a, 0, accuracy: 0.001)
        // ...and both animated channels are present in the overlay.
        let overlay = PNTransform.presentedOverlay(view)!
        let parts = PNTransform.decompose(overlay)
        XCTAssertEqual(parts.translateX, 10, accuracy: 0.001)
        XCTAssertEqual(parts.translateY, 5, accuracy: 0.001)
        XCTAssertEqual(PNProps.double(PNAnimator.shared.presentationValue(view: view, prop: "translate_x")), 10)
        XCTAssertEqual(PNProps.double(PNAnimator.shared.presentationValue(view: view, prop: "translate_y")), 5)
        // Restyling the static transform keeps the animated channels.
        manager.update(view: view, changed: ["transform": [["scale": 2]]])
        let scaled = PNTransform.decompose(CATransform3DGetAffineTransform(view.layer.transform))
        XCTAssertEqual(scaled.scaleX, 2, accuracy: 0.001)
        XCTAssertEqual(scaled.translateX, 20, accuracy: 0.001, "animated translate is appended after the static list")
        XCTAssertEqual(scaled.translateY, 10, accuracy: 0.001)
    }

    func testGraphBindingsComposeTransformChannels() {
        try! PNTransaction.apply([.create(tag: 5002, type: "View", props: [:])])
        defer { PNAnimationGraph.forget(5002) }
        PNAnimationGraph.install(["id": 501, "nodes": [
            ["id": 501, "kind": "value", "value": 0.0],
            ["id": 502, "kind": "value", "value": 0.0],
        ], "bindings": [[5002, "translate_x", 501], [5002, "translate_y", 502]]])
        PNAnimationGraph.set(501, 30)
        PNAnimationGraph.set(502, 40)
        let view = PNViewRegistry.shared.view(for: 5002)!
        let parts = PNTransform.decompose(view.transform)
        XCTAssertEqual(parts.translateX, 30, accuracy: 0.001)
        XCTAssertEqual(parts.translateY, 40, accuracy: 0.001)
    }

    func testThreeDimensionalStaticTransform() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 5003, props: ["transform": [["perspective": 500], ["rotate_x": "45deg"], ["skew_x": "10deg"]]])
        let t = view.layer.transform
        XCTAssertFalse(CATransform3DIsAffine(t), "perspective and rotate_x leave the affine plane")
        XCTAssertEqual(PNTransform.make([["perspective": 500]]).m34, -1 / 500, accuracy: 1e-6)
        XCTAssertNotEqual(t.m34, 0)
        XCTAssertEqual(PNTransform.make([["rotate_y": "90deg"]]).m11, 0, accuracy: 1e-6)
        XCTAssertEqual(PNTransform.makeAffine([["skew_x": "45deg"]]).c, 1, accuracy: 1e-6)
        manager.update(view: view, changed: ["transform": NSNull()])
        XCTAssertTrue(CATransform3DIsIdentity(view.layer.transform))
    }

    // MARK: - Decay

    func testDecayFollowsReactNativeClosedForm() {
        let x0 = 100.0, v0 = 2.0, d = 0.998
        XCTAssertEqual(PNDecayDriver.finalValue(from: x0, velocity: v0, deceleration: d), x0 + v0 / (1 - d), accuracy: 1e-9)
        for t in [0.0, 16.0, 250.0, 1000.0] {
            XCTAssertEqual(PNDecayDriver.velocity(velocity: v0, deceleration: d, elapsedMs: t), v0 * pow(d, t), accuracy: 1e-12)
            XCTAssertEqual(PNDecayDriver.position(from: x0, velocity: v0, deceleration: d, elapsedMs: t), x0 + v0 * (1 - pow(d, t)) / (1 - d), accuracy: 1e-9)
        }
        XCTAssertEqual(PNDecayDriver.position(from: x0, velocity: v0, deceleration: d, elapsedMs: 0), x0)
        XCTAssertFalse(PNDecayDriver.isAtRest(from: x0, velocity: v0, deceleration: d, elapsedMs: 500))
        // |v| drops under 0.001 pt/ms after ln(0.0005) / ln(0.998) ~ 3800 ms.
        XCTAssertTrue(PNDecayDriver.isAtRest(from: x0, velocity: v0, deceleration: d, elapsedMs: 4000))
        var frames: [Double] = []
        var completed = false
        let driver = PNDecayDriver(from: x0, velocity: v0, deceleration: d, frame: { frames.append($0) }, completion: { completed = true })
        XCTAssertFalse(driver.advance(elapsedMs: 500))
        XCTAssertEqual(frames.last!, x0 + v0 * (1 - pow(d, 500)) / (1 - d), accuracy: 1e-9)
        XCTAssertTrue(driver.advance(elapsedMs: 10_000))
        XCTAssertEqual(driver.currentValue, driver.finalValue, "a finished decay lands exactly on its rest point")
        XCTAssertFalse(completed, "the display link, not advance, reports completion")
        XCTAssertEqual(PNDecayDriver.clamp(1.5), 0.999_999)
        XCTAssertEqual(PNDecayDriver.clamp(.nan), PNDecayDriver.defaultDeceleration)
    }

    // MARK: - Screen presentation and animation

    func testScreenPresentationAndAnimationMapping() {
        XCTAssertEqual(PNScreenOptions.modalStyle("modal"), .pageSheet)
        XCTAssertEqual(PNScreenOptions.modalStyle("full_screen_modal"), .fullScreen)
        XCTAssertEqual(PNScreenOptions.modalStyle("form_sheet"), .formSheet)
        XCTAssertEqual(PNScreenOptions.modalStyle("transparent_modal"), .overFullScreen)
        XCTAssertFalse(PNScreenOptions.isModal(["presentation": "card"]))
        XCTAssertFalse(PNScreenOptions.isModal([:]))
        for presentation in ["modal", "full_screen_modal", "form_sheet", "transparent_modal"] {
            XCTAssertTrue(PNScreenOptions.isModal(["presentation": presentation]), presentation)
        }
        XCTAssertEqual(PNScreenOptions.modalTransition("fade"), .crossDissolve)
        XCTAssertEqual(PNScreenOptions.modalTransition("slide_from_bottom"), .coverVertical)
        XCTAssertTrue(PNScreenOptions.transition(animation: "fade", operation: .push) is PNFadeTransition)
        XCTAssertTrue(PNScreenOptions.transition(animation: "slide_from_bottom", operation: .pop) is PNSlideFromBottomTransition)
        XCTAssertNil(PNScreenOptions.transition(animation: "default", operation: .push))
        XCTAssertNil(PNScreenOptions.transition(animation: "slide_from_right", operation: .push))
        XCTAssertNil(PNScreenOptions.transition(animation: "none", operation: .push))
        XCTAssertFalse(PNScreenOptions.animates(["animation": "none"]))
        XCTAssertTrue(PNScreenOptions.animates([:]))
    }

    func testGestureEnabledSplitsBetweenCardsAndModals() {
        let navigation = UINavigationController(rootViewController: UIViewController())
        let card = UIViewController()
        navigation.pushViewController(card, animated: false)
        HostModule.applyGestureOptions(["gesture_enabled": false], to: card)
        XCTAssertEqual(navigation.interactivePopGestureRecognizer?.isEnabled, false)
        XCTAssertFalse(navigation.isModalInPresentation, "cards never touch isModalInPresentation")
        HostModule.applyGestureOptions(["gesture_enabled": false, "presentation": "modal"], to: card)
        XCTAssertTrue(navigation.isModalInPresentation)
        HostModule.applyGestureOptions(["gesture_enabled": true, "presentation": "form_sheet"], to: card)
        XCTAssertFalse(navigation.isModalInPresentation)
    }

    // MARK: - Back veto and restore_stack

    func testRestoreStackAfterNativePopRestoresBothScreensWithoutDuplicateEvents() throws {
        apply([["c", 5101, "ScreenStack", ["flex": 1, "_pn_events": ["on_native_back"]]],
               ["c", 5102, "Screen", ["title": "Inbox", "flex": 1]],
               ["c", 5103, "Screen", ["title": "Detail", "flex": 1]],
               ["i", 5101, 5102, 0], ["i", 5101, 5103, 1]])
        let stack = try XCTUnwrap(PNViewRegistry.shared.view(for: 5101))
        show(stack)
        settle()
        let navigation = try XCTUnwrap(PNScreenStackManager.navigationController(of: stack))
        XCTAssertEqual(navigation.viewControllers.map(\.title), ["Inbox", "Detail"])
        XCTAssertEqual(navigation.interactivePopGestureRecognizer?.isEnabled, true)

        // UIKit pops natively (swipe or back button) before Python knows.
        navigation.popViewController(animated: false)
        settle()
        XCTAssertEqual(navigation.viewControllers.count, 1)
        var backs = PNEventCapture.events(named: "on_native_back")
        XCTAssertEqual(backs.count, 1)
        XCTAssertEqual((backs.first?.payload["args"] as? [Any])?.first as? Int, 1)

        // Python vetoes: it keeps both routes and asks UIKit to follow.
        let manager = try XCTUnwrap(PNViewRegistry.shared.resolve(5101)?.manager)
        XCTAssertNil(manager.command(view: stack, name: "restore_stack", args: [:]))
        settle()
        XCTAssertEqual(navigation.viewControllers.map(\.title), ["Inbox", "Detail"], "both controllers, in order")
        XCTAssertTrue(PNViewRegistry.shared.view(for: 5103)?.window === window)
        backs = PNEventCapture.events(named: "on_native_back")
        XCTAssertEqual(backs.count, 1, "restoring must not report another native back")
    }

    func testGuardedScreenRefusesBackButtonAndAsksPython() throws {
        apply([["c", 5201, "ScreenStack", ["flex": 1, "_pn_events": ["on_native_back"]]],
               ["c", 5202, "Screen", ["title": "Inbox", "flex": 1]],
               ["c", 5203, "Screen", ["title": "Compose", "flex": 1]],
               ["i", 5201, 5202, 0], ["i", 5201, 5203, 1]])
        let stack = try XCTUnwrap(PNViewRegistry.shared.view(for: 5201))
        // `guarded` arrives as a Screen prop once the contract carries it; mark it directly for now.
        PNViewState.existing(for: try XCTUnwrap(PNViewRegistry.shared.view(for: 5203)))?.props["guarded"] = true
        show(stack)
        settle()
        let navigation = try XCTUnwrap(PNScreenStackManager.navigationController(of: stack) as? PNNavigationController)
        XCTAssertEqual(navigation.viewControllers.count, 2)
        XCTAssertEqual(navigation.interactivePopGestureRecognizer?.isEnabled, false, "a guarded card can't be swiped away")

        let item = try XCTUnwrap(navigation.navigationBar.topItem)
        XCTAssertFalse(navigation.navigationBar(navigation.navigationBar, shouldPop: item))
        settle(0.3)
        XCTAssertEqual(navigation.viewControllers.count, 2, "UIKit keeps the guarded screen")
        XCTAssertEqual(PNEventCapture.events(named: "on_native_back").count, 1, "Python is asked exactly once")

        // Python vetoes again: restore_stack finds nothing to change and stays quiet.
        _ = PNViewRegistry.shared.resolve(5201)?.manager.command(view: stack, name: "restore_stack", args: [:])
        settle(0.3)
        XCTAssertEqual(navigation.viewControllers.count, 2)
        XCTAssertEqual(PNEventCapture.events(named: "on_native_back").count, 1)

        // An unguarded screen pops on the back button and reports it.
        PNViewState.existing(for: try XCTUnwrap(PNViewRegistry.shared.view(for: 5203)))?.props["guarded"] = false
        XCTAssertFalse(navigation.navigationBar(navigation.navigationBar, shouldPop: item), "the controller performs the pop itself")
        settle()
        XCTAssertEqual(navigation.viewControllers.count, 1)
        XCTAssertEqual(PNEventCapture.events(named: "on_native_back").count, 2)
    }

    // MARK: - VirtualList

    func testVirtualListEmitsScrollOnlyWhenWired() throws {
        try PNTransaction.apply([.create(tag: 5301, type: "VirtualList", props: ["dataset": ["base": 0, "revision": 1, "changes": [["reset", [["a", 1, 40.0, false], ["b", 1, 40.0, false]]]]]])])
        let list = try XCTUnwrap(PNViewRegistry.shared.view(for: 5301) as? UICollectionView)
        list.frame = CGRect(x: 0, y: 0, width: 200, height: 50)
        list.delegate?.scrollViewDidScroll?(list)
        settle(0.2)
        XCTAssertTrue(PNEventCapture.events(named: "on_scroll").isEmpty, "nothing wired, nothing emitted")
        PNViewState.existing(for: list)?.props["_pn_events"] = ["on_scroll"]
        list.delegate?.scrollViewDidScroll?(list)
        settle(0.2)
        XCTAssertEqual(PNEventCapture.events(named: "on_scroll").count, 1)
    }

    // MARK: - Event identity

    func testEventsEmittedWhileACommitAppliesCarryThatCommitsIdentity() throws {
        let pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        apply([["c", 6401, "Image", ["source": pixel, "_pn_events": ["on_load_start", "on_load_end"]]]])
        settle(0.4)
        // on_load_start fires synchronously while the create applies; the
        // view is born in this revision, so the event must carry it.
        let start = try XCTUnwrap(PNEventCapture.events(named: "on_load_start").first)
        XCTAssertEqual(start.payload["application"] as? String, application)
        XCTAssertEqual(start.payload["revision"] as? Int, revision)
        let end = try XCTUnwrap(PNEventCapture.events(named: "on_load_end").first)
        XCTAssertEqual(end.payload["revision"] as? Int, revision)
    }

    // MARK: - Viewport, keyboard, device

    func testViewportPayloadCarriesScaleFontScaleScreenAndKeyboard() {
        let controller = PNViewController(nibName: nil, bundle: nil)
        controller.loadViewIfNeeded()
        let viewport = controller.viewport()
        for key in ["width", "height", "insets", "color_scheme", "scale", "font_scale", "screen_width", "screen_height", "keyboard_height"] {
            XCTAssertNotNil(viewport[key], "missing \(key)")
        }
        XCTAssertGreaterThan(viewport["scale"] as? Double ?? 0, 0)
        XCTAssertGreaterThan(viewport["font_scale"] as? Double ?? 0, 0)
        XCTAssertGreaterThan(viewport["screen_width"] as? Double ?? 0, 0)
        XCTAssertEqual(viewport["keyboard_height"] as? Double, Double(PNKeyboardObserver.shared.height))
    }

    func testKeyboardObserverPublishesSnapshotsAndViewport() {
        let observer = PNKeyboardObserver.shared
        var seen: [PNKeyboardObserver.Snapshot] = []
        let unsubscribe = observer.addListener { seen.append($0) }
        defer { unsubscribe(); observer.publish(0) }
        observer.publish(0)
        observer.publish(320, frame: CGRect(x: 0, y: 524, width: 390, height: 320), durationMs: 250)
        XCTAssertEqual(observer.height, 320)
        XCTAssertTrue(observer.isVisible)
        XCTAssertEqual(observer.lastDurationMs, 250)
        XCTAssertEqual(seen.last, PNKeyboardObserver.Snapshot(height: 320, visible: true, durationMs: 250))
        observer.publish(320, durationMs: 250)
        XCTAssertEqual(seen.count, 1, "an unchanged keyboard frame is not republished")
        observer.publish(0, durationMs: 250)
        XCTAssertEqual(seen.last?.visible, false)
        settle(0.2)
        let keyboard = PNEventCapture.all.filter { $0.kind == "module" && $0.name == "Keyboard" && $0.payload["event"] as? String == "change" }
        XCTAssertEqual(keyboard.count, 2)
        let payload = keyboard.first?.payload["payload"] as? [String: Any]
        XCTAssertEqual(payload?["height"] as? Double, 320)
        XCTAssertEqual(payload?["visible"] as? Bool, true)
        XCTAssertEqual(payload?["duration_ms"] as? Double, 250)
    }

    func testDeviceInfoReturnsTheContractKeys() {
        let info = DeviceModule.snapshot()
        let expected: Set<String> = ["platform", "os_version", "model", "manufacturer", "is_simulator", "is_tablet", "app_name",
                                     "app_version", "build_number", "bundle_id", "scale", "font_scale", "locale", "app_dir"]
        XCTAssertEqual(Set(info.keys), expected)
        XCTAssertEqual(info["platform"] as? String, "ios")
        XCTAssertEqual(info["manufacturer"] as? String, "Apple")
        XCTAssertEqual(info["is_simulator"] as? Bool, true)
        XCTAssertEqual(info["is_tablet"] as? Bool, UIDevice.current.userInterfaceIdiom == .pad)
        XCTAssertFalse((info["locale"] as? String ?? "").contains("_"), "locale is a BCP 47 tag")
        XCTAssertEqual(DeviceModule.languageTag(Locale(identifier: "en_US")), "en-US")
        XCTAssertGreaterThan(info["font_scale"] as? Double ?? 0, 0)
    }

    // MARK: - Text

    func testTextEllipsizeModeAndSelectable() throws {
        let manager = PNTextManager()
        let label = try XCTUnwrap(manager.createView(tag: 5401, props: ["text": "hello", "ellipsize_mode": "middle", "selectable": true]) as? PNLabel)
        XCTAssertEqual(label.lineBreakMode, .byTruncatingMiddle)
        XCTAssertTrue(label.isSelectable)
        XCTAssertTrue(label.canBecomeFirstResponder)
        XCTAssertTrue(label.canPerformAction(#selector(UIResponderStandardEditActions.copy(_:)), withSender: nil))
        XCTAssertFalse(label.canPerformAction(#selector(UIResponderStandardEditActions.paste(_:)), withSender: nil))
        XCTAssertTrue(label.gestureRecognizers?.contains { $0 is UILongPressGestureRecognizer } == true)
        manager.update(view: label, changed: ["ellipsize_mode": "clip", "selectable": false])
        XCTAssertEqual(label.lineBreakMode, .byClipping)
        XCTAssertFalse(label.canBecomeFirstResponder)
        XCTAssertFalse(label.gestureRecognizers?.contains { $0 is UILongPressGestureRecognizer } == true)
        XCTAssertEqual(PNTextManager.lineBreakMode("head"), .byTruncatingHead)
        XCTAssertEqual(PNTextManager.lineBreakMode("tail"), .byTruncatingTail)
        XCTAssertEqual(PNTextManager.lineBreakMode(nil), .byTruncatingTail)
    }

    // MARK: - Border style

    func testDashedAndDottedBorders() throws {
        let manager = PNViewManager()
        let view = manager.createView(tag: 5501, props: ["border_width": 2, "border_color": "#ff0000", "border_style": "dashed", "border_radius": 4])
        let state = try XCTUnwrap(PNViewState.existing(for: view))
        XCTAssertEqual(state.borderStyle, "dashed")
        XCTAssertEqual(view.layer.borderWidth, 0, "the shape layer replaces the solid border")
        let shape = try XCTUnwrap(state.borderStyleLayer)
        XCTAssertEqual(shape.lineDashPattern?.map { $0.doubleValue }, [6, 6])
        XCTAssertEqual(shape.lineWidth, 2)
        manager.setFrame(view: view, x: 0, y: 0, w: 100, h: 40)
        XCTAssertNotNil(shape.path)
        XCTAssertEqual(shape.frame.size, CGSize(width: 100, height: 40))
        manager.update(view: view, changed: ["border_style": "dotted"])
        XCTAssertEqual(state.borderStyleLayer?.lineDashPattern?.map { $0.doubleValue }, [2, 2])
        manager.update(view: view, changed: ["border_style": "solid"])
        XCTAssertNil(state.borderStyle)
        XCTAssertNil(state.borderStyleLayer)
        XCTAssertNil(shape.superlayer)
        XCTAssertEqual(view.layer.borderWidth, 2)
    }

    // MARK: - Accessibility

    func testAccessibilityValueActionsAndImportance() throws {
        let manager = PNViewManager()
        let view = manager.createView(tag: 5601, props: [
            "accessible": true,
            "accessibility_role": "adjustable",
            "accessibility_value": ["min": 0, "max": 200, "now": 50],
            "accessibility_actions": [["name": "increment", "label": "Turn up"], ["name": "decrement"]],
        ])
        XCTAssertEqual(view.accessibilityValue, "25%")
        XCTAssertTrue(view.accessibilityTraits.contains(.adjustable))
        let actions = try XCTUnwrap(view.accessibilityCustomActions)
        XCTAssertEqual(actions.map(\.name), ["Turn up", "decrement"])
        manager.update(view: view, changed: ["accessibility_value": "half"])
        XCTAssertEqual(view.accessibilityValue, "half")
        manager.update(view: view, changed: ["accessibility_value": ["text": "loud", "now": 3]])
        XCTAssertEqual(view.accessibilityValue, "loud")
        manager.update(view: view, changed: ["accessibility_value": ["now": 3]])
        XCTAssertEqual(view.accessibilityValue, "3")
        manager.update(view: view, changed: ["accessibility_value": NSNull(), "accessibility_state": ["expanded": true]])
        XCTAssertEqual(view.accessibilityValue, "expanded", "state falls back once the explicit value is gone")

        manager.update(view: view, changed: ["important_for_accessibility": "no_hide_descendants"])
        XCTAssertTrue(view.accessibilityElementsHidden)
        XCTAssertFalse(view.isAccessibilityElement)
        manager.update(view: view, changed: ["important_for_accessibility": "no"])
        XCTAssertFalse(view.accessibilityElementsHidden)
        XCTAssertFalse(view.isAccessibilityElement)
        manager.update(view: view, changed: ["important_for_accessibility": "yes"])
        XCTAssertTrue(view.isAccessibilityElement)
        manager.update(view: view, changed: ["important_for_accessibility": "auto"])
        XCTAssertTrue(view.isAccessibilityElement, "auto restores the `accessible` prop")

        // Custom actions report their `name`, not their label.
        try PNTransaction.apply([.create(tag: 5602, type: "View", props: ["_pn_events": ["on_accessibility_action"]])])
        let wired = try XCTUnwrap(PNViewRegistry.shared.view(for: 5602))
        manager.update(view: wired, changed: ["accessibility_actions": [["name": "activate", "label": "Go"]]])
        let action = try XCTUnwrap(wired.accessibilityCustomActions?.first)
        XCTAssertTrue(action.actionHandler?(action) == true)
        settle(0.2)
        let events = PNEventCapture.events(named: "on_accessibility_action")
        XCTAssertEqual(events.count, 1)
        XCTAssertEqual((events.first?.payload["args"] as? [Any])?.first as? String, "activate")
    }
}
