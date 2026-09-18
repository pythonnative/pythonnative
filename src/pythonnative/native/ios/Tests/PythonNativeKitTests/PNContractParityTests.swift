import XCTest
import UIKit
import WebKit
@testable import PythonNativeKit

/// Round-2 coverage: the regenerated typed contract end to end.
final class PNContractParityTests: XCTestCase {
    private var window: UIWindow!

    override func setUp() {
        super.setUp()
        PNEventCapture.reset()
        PNBridge.shared.setCallback(captureCallbackForContractTests)
    }

    override func tearDown() {
        PNBridge.shared.setCallback(nil)
        window?.isHidden = true
        window?.rootViewController = nil
        window = nil
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    private func settle(_ seconds: TimeInterval = 0.2) {
        let ready = expectation(description: "settle")
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { ready.fulfill() }
        wait(for: [ready], timeout: seconds + 3)
    }

    private func mount<T: UIView>(_ view: UIView, as type: T.Type = UIView.self) -> UIView {
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let controller = UIViewController()
        window.rootViewController = controller
        controller.view.addSubview(view)
        window.makeKeyAndVisible()
        return view
    }

    private func create(_ type: String, tag: Int64, _ props: [String: Any]) throws -> UIView {
        try PNTransaction.apply([.create(tag: tag, type: type, props: props)])
        return try XCTUnwrap(PNViewRegistry.shared.view(for: tag))
    }

    private func firstArg(_ name: String) -> Any? {
        (PNEventCapture.events(named: name).first?.payload["args"] as? [Any])?.first
    }

    // MARK: - Modules

    func testNewModulesAreRegisteredAndAnswer() throws {
        for module in ["Keyboard", "AccessibilityInfo", "Localization"] {
            XCTAssertTrue(PNRegistry.shared.moduleNames.contains(module), "missing module \(module)")
        }
        let visible = PNModuleDispatcher.shared.call(module: "Keyboard", method: "is_visible", envelope: ["call_id": 1, "args": [:]])
        XCTAssertEqual(visible["ok"] as? Bool, true)
        XCTAssertEqual(visible["value"] as? Bool, PNKeyboardObserver.shared.isVisible)
        XCTAssertEqual(PNModuleDispatcher.shared.call(module: "Keyboard", method: "dismiss", envelope: ["call_id": 2, "args": [:]])["ok"] as? Bool, true)

        let reader = PNModuleDispatcher.shared.call(module: "AccessibilityInfo", method: "is_screen_reader_enabled", envelope: ["call_id": 3, "args": [:]])
        XCTAssertEqual(reader["value"] as? Bool, UIAccessibility.isVoiceOverRunning)
        let motion = PNModuleDispatcher.shared.call(module: "AccessibilityInfo", method: "is_reduce_motion_enabled", envelope: ["call_id": 4, "args": [:]])
        XCTAssertEqual(motion["value"] as? Bool, UIAccessibility.isReduceMotionEnabled)
        XCTAssertEqual(PNModuleDispatcher.shared.call(module: "AccessibilityInfo", method: "announce", envelope: ["call_id": 5, "args": ["message": "Saved"]])["ok"] as? Bool, true)
        _ = try create("View", tag: 6001, [:])
        XCTAssertEqual(PNModuleDispatcher.shared.call(module: "AccessibilityInfo", method: "set_accessibility_focus", envelope: ["call_id": 6, "args": ["tag": 6001]])["ok"] as? Bool, true)
        XCTAssertEqual(PNModuleDispatcher.shared.call(module: "AccessibilityInfo", method: "set_accessibility_focus", envelope: ["call_id": 7, "args": ["tag": 99]])["ok"] as? Bool, false)

        let locales = PNModuleDispatcher.shared.call(module: "Localization", method: "get_locales", envelope: ["call_id": 8, "args": [:]])
        let first = try XCTUnwrap((locales["value"] as? [[String: Any]])?.first)
        XCTAssertEqual(Set(first.keys), ["language_tag", "language_code", "region_code", "is_rtl"])
        XCTAssertFalse((first["language_tag"] as? String ?? "_").contains("_"))
        let zone = PNModuleDispatcher.shared.call(module: "Localization", method: "get_timezone", envelope: ["call_id": 9, "args": [:]])
        XCTAssertEqual(zone["value"] as? String, TimeZone.current.identifier)

        let arabic = LocalizationModule.locales(["ar-EG", "en-US"])
        XCTAssertEqual(arabic[0]["language_code"] as? String, "ar")
        XCTAssertEqual(arabic[0]["region_code"] as? String, "EG")
        XCTAssertEqual(arabic[0]["is_rtl"] as? Bool, true)
        XCTAssertEqual(arabic[1]["is_rtl"] as? Bool, false)
    }

    func testModuleChangeEventsUseTypedEmitters() {
        AccessibilityInfoModule.dispatch()
        LocalizationModule.dispatch()
        BatteryModule.dispatch()
        settle()
        let events = PNEventCapture.all.filter { $0.kind == "module" && $0.payload["event"] as? String == "change" }
        let names = Set(events.map(\.name))
        XCTAssertTrue(names.isSuperset(of: ["AccessibilityInfo", "Localization", "Battery"]), "\(names)")
        let accessibility = events.first { $0.name == "AccessibilityInfo" }?.payload["payload"] as? [String: Any]
        XCTAssertEqual(Set(accessibility?.keys.map { $0 } ?? []), ["screen_reader", "reduce_motion"])
        let localization = events.first { $0.name == "Localization" }?.payload["payload"] as? [String: Any]
        XCTAssertEqual(Set(localization?.keys.map { $0 } ?? []), ["locales", "timezone"])
        let battery = events.first { $0.name == "Battery" }?.payload["payload"] as? [String: Any]
        XCTAssertEqual(Set(battery?.keys.map { $0 } ?? []), ["level", "state"])
    }

    func testSecureStoreDeleteOfAbsentKeySucceeds() {
        XCTAssertTrue(SecureStoreModule.delete("pn-test-missing-\(UUID().uuidString)"))
    }

    // MARK: - ScrollView

    func testScrollViewTypedPropsAndEvents() throws {
        let scroll = try XCTUnwrap(try create("ScrollView", tag: 6101, [
            "horizontal": true, "content_inset": ["top": 4, "horizontal": 8], "scroll_enabled": false,
            "scroll_event_throttle": 16, "keyboard_should_persist_taps": "handled", "snap_to_interval": 100,
            "snap_to_alignment": "center", "deceleration_rate": "fast",
            "_pn_events": ["on_scroll", "on_scroll_begin_drag", "on_scroll_end_drag", "on_momentum_scroll_end"],
        ]) as? UIScrollView)
        XCTAssertEqual(scroll.contentInset, UIEdgeInsets(top: 4, left: 8, bottom: 0, right: 8))
        XCTAssertFalse(scroll.isScrollEnabled)
        XCTAssertTrue(scroll.alwaysBounceHorizontal)
        XCTAssertEqual(scroll.decelerationRate, .fast)
        let state = try XCTUnwrap(PNViewState.existing(for: scroll))
        XCTAssertEqual(state.extras["persist_taps"] as? String, "handled")
        XCTAssertEqual(state.extras["snap_interval"] as? Double, 100)
        XCTAssertEqual(state.extras["throttle"] as? Double, 16)
        scroll.frame = CGRect(x: 0, y: 0, width: 200, height: 100)
        scroll.contentSize = CGSize(width: 1000, height: 100)
        scroll.contentOffset = CGPoint(x: 30, y: 0)
        let delegate = try XCTUnwrap(scroll.delegate)
        PNEventCapture.reset() // inset and offset changes above already scrolled
        delegate.scrollViewWillBeginDragging?(scroll)
        delegate.scrollViewDidScroll?(scroll)
        delegate.scrollViewDidEndDragging?(scroll, willDecelerate: false)
        delegate.scrollViewDidEndDecelerating?(scroll)
        settle()
        for name in ["on_scroll", "on_scroll_begin_drag", "on_scroll_end_drag", "on_momentum_scroll_end"] {
            let payload = try XCTUnwrap(firstArg(name) as? [String: Any], name)
            XCTAssertEqual(Set(payload.keys), ["x", "y", "content_width", "content_height", "viewport_width", "viewport_height"], name)
            XCTAssertEqual(payload["x"] as? Double, 30)
            XCTAssertEqual(payload["content_width"] as? Double, 1000)
            XCTAssertEqual(payload["viewport_width"] as? Double, 200)
        }
        XCTAssertEqual(PNEventCapture.events(named: "on_momentum_scroll_end").count, 2)

        // Snapping through targetContentOffset.
        var target = CGPoint(x: 240, y: 0)
        delegate.scrollViewWillEndDragging?(scroll, withVelocity: .zero, targetContentOffset: &target)
        XCTAssertEqual(target.x, 250, accuracy: 0.001, "center alignment: (240 + 50) / 100 rounds to 3 -> 300 - 50")
        XCTAssertEqual(PNScrollViewManager.snapTarget(proposed: 130, velocity: 0, interval: 100, alignment: "start", viewport: 200, maximum: 800), 100)
        XCTAssertEqual(PNScrollViewManager.snapTarget(proposed: 130, velocity: 1, interval: 100, alignment: "start", viewport: 200, maximum: 800), 200)
        XCTAssertEqual(PNScrollViewManager.snapTarget(proposed: 130, velocity: -1, interval: 100, alignment: "start", viewport: 200, maximum: 800), 100)
        XCTAssertEqual(PNScrollViewManager.snapTarget(proposed: 790, velocity: 1, interval: 100, alignment: "end", viewport: 200, maximum: 800), 800)
        XCTAssertEqual(PNScrollViewManager.decelerationRate(0.5).rawValue, 0.5)
        XCTAssertEqual(PNScrollViewManager.decelerationRate("normal"), .normal)
        XCTAssertEqual(PNScrollViewManager.edgeInsets(["all": 5, "bottom": 1]), UIEdgeInsets(top: 5, left: 5, bottom: 1, right: 5))
    }

    // MARK: - Key presses

    func testKeyNamesIgnoreNoOpEditsAndReportReturn() {
        XCTAssertEqual(PNTextInputManager.keyName(for: "", range: NSRange(location: 3, length: 1)), "Backspace")
        XCTAssertNil(
            PNTextInputManager.keyName(for: "", range: NSRange(location: 7, length: 0)),
            "UIKit's empty edit when committing text deletes nothing, so it isn't a key press"
        )
        XCTAssertEqual(PNTextInputManager.keyName(for: "\n", range: NSRange(location: 7, length: 0)), "Enter")
        XCTAssertEqual(PNTextInputManager.keyName(for: "o", range: NSRange(location: 6, length: 0)), "o")
    }

    func testClearCommandReportsTheEdit() throws {
        let field = try XCTUnwrap(try create("TextInput", tag: 6311, ["value": "draft", "_pn_events": ["on_change"]]) as? UITextField)
        _ = mount(field)
        _ = PNTextInputManager().command(view: field, name: "clear", args: [:])
        settle(0.2)
        XCTAssertEqual(field.text, "")
        let changes = PNEventCapture.events(named: "on_change").compactMap { ($0.payload["args"] as? [Any])?.first as? String }
        XCTAssertEqual(changes, [""], "clear() reports the empty value so a controlled input follows")
    }

    func testWebViewsEvalAnswersWithTheScriptResult() throws {
        XCTAssertTrue(PNRegistry.shared.moduleNames.contains("WebViews"))
        XCTAssertEqual(WebViewsModule.stringify(nil), "")
        XCTAssertEqual(WebViewsModule.stringify(NSNull()), "")
        XCTAssertEqual(WebViewsModule.stringify("hi"), "hi")
        XCTAssertEqual(WebViewsModule.stringify(NSNumber(value: 42)), "42")
        XCTAssertEqual(WebViewsModule.stringify(NSNumber(value: 4.5)), "4.5")
        XCTAssertEqual(WebViewsModule.stringify(kCFBooleanTrue), "true")
        XCTAssertEqual(WebViewsModule.stringify([1, 2]), "[1,2]")
        let web = try XCTUnwrap(try create("WebView", tag: 6321, ["html": "<p>hi</p>"]) as? WKWebView)
        _ = mount(web)
        let answered = expectation(description: "the page answers")
        var result: String?
        _ = WebViewsModule().eval_js(tag: 6321, script: "1 + 41") { outcome in
            result = try? outcome.get()
            answered.fulfill()
        }
        wait(for: [answered], timeout: 20)
        XCTAssertEqual(result, "42")
    }

    // MARK: - Text

    func testTextPressAndSpanPress() throws {
        let manager = PNTextManager()
        let label = try XCTUnwrap(manager.createView(tag: 6201, props: [
            "spans": [["text": "Read the "], ["text": "terms", "pressable": true], ["text": "."]],
            "font_size": 20, "ellipsize_mode": "tail", "selectable": false, "allow_font_scaling": false,
        ]) as? PNLabel)
        try PNTransaction.apply([.create(tag: 6202, type: "Text", props: ["text": "Tap me", "_pn_events": ["on_press"]])])
        let plain = try XCTUnwrap(PNViewRegistry.shared.view(for: 6202) as? PNLabel)
        XCTAssertTrue(label.isPressable, "a pressable span installs the tap recognizer")
        XCTAssertTrue(plain.isPressable, "a wired on_press installs the tap recognizer")
        XCTAssertFalse(label.adjustsFontForContentSizeCategory)
        XCTAssertEqual(label.lineBreakMode, .byTruncatingTail)

        // Register the span label so emitted events resolve to a tag.
        PNViewRegistry.shared.register(PNViewRecord(tag: 6201, typeName: "Text", view: label, manager: manager))
        PNViewState.existing(for: label)?.props["_pn_events"] = ["on_span_press"]
        let size = manager.measure(view: label, maxW: 1000, maxH: 1000)
        label.frame = CGRect(origin: .zero, size: size)
        let prefix = ("Read the " as NSString).size(withAttributes: [.font: label.font!]).width
        let termsWidth = ("terms" as NSString).size(withAttributes: [.font: label.font!]).width
        XCTAssertEqual(PNTextManager.spanIndex(at: CGPoint(x: prefix + termsWidth / 2, y: size.height / 2), in: label), 1)
        XCTAssertEqual(PNTextManager.spanIndex(at: CGPoint(x: 4, y: size.height / 2), in: label), 0)
        XCTAssertNil(PNTextManager.spanIndex(at: CGPoint(x: size.width + 60, y: size.height / 2), in: label))
        XCTAssertTrue(label.press(at: CGPoint(x: prefix + termsWidth / 2, y: size.height / 2)))
        XCTAssertFalse(label.press(at: CGPoint(x: 4, y: size.height / 2)), "an unpressable span with no on_press reports nothing")
        plain.frame = CGRect(x: 0, y: 0, width: 100, height: 30)
        XCTAssertTrue(plain.press(at: CGPoint(x: 10, y: 10)))
        settle()
        XCTAssertEqual(firstArg("on_span_press") as? Int, 1)
        XCTAssertEqual(PNEventCapture.events(named: "on_press").count, 1)
    }

    // MARK: - TextInput

    func testTextInputSelectionKeysAndSubmit() throws {
        let field = try XCTUnwrap(try create("TextInput", tag: 6301, [
            "value": "hello world", "selection": ["start": 1, "end": 3], "keyboard_type": "visible_password", "secure": true,
            "keyboard_appearance": "dark", "select_text_on_focus": true,
            "_pn_events": ["on_selection_change", "on_key_press", "on_submit"],
        ]) as? UITextField)
        _ = mount(field)
        XCTAssertEqual(field.keyboardAppearance, .dark)
        XCTAssertFalse(field.isSecureTextEntry, "visible_password turns masking off")
        XCTAssertEqual(field.keyboardType, .default)
        XCTAssertEqual(PNTextInputManager.currentSelection(field).map { [$0.0, $0.1] }, [1, 3])
        let delegate = try XCTUnwrap(field.delegate)
        _ = delegate.textField?(field, shouldChangeCharactersIn: NSRange(location: 3, length: 0), replacementString: "a")
        _ = delegate.textField?(field, shouldChangeCharactersIn: NSRange(location: 3, length: 1), replacementString: "")
        // UIKit's empty edit over an empty range (sent while committing
        // text) deletes nothing and isn't a key press.
        _ = delegate.textField?(field, shouldChangeCharactersIn: NSRange(location: 3, length: 0), replacementString: "")
        field.becomeFirstResponder()
        settle()
        XCTAssertTrue(field.isFirstResponder)
        XCTAssertEqual(delegate.textFieldShouldReturn?(field), true)
        settle(0.1)
        XCTAssertFalse(field.isFirstResponder, "single-line inputs blur on submit by default")
        let keys = PNEventCapture.events(named: "on_key_press").compactMap { ($0.payload["args"] as? [[String: Any]])?.first?["key"] as? String }
        XCTAssertEqual(keys, ["a", "Backspace", "Enter"], "Return in a single-line field reports Enter from textFieldShouldReturn")
        XCTAssertFalse(PNEventCapture.events(named: "on_selection_change").isEmpty)
        let selection = try XCTUnwrap(firstArg("on_selection_change") as? [String: Any])
        XCTAssertEqual(Set(selection.keys), ["start", "end"])

        XCTAssertEqual(PNTextInputManager.keyboardType("ascii"), .asciiCapable)
        XCTAssertEqual(PNTextInputManager.keyboardType("numbers_and_punctuation"), .numbersAndPunctuation)
        XCTAssertEqual(PNTextInputManager.keyboardType("web_search"), .webSearch)
        XCTAssertTrue(PNTextInputManager.blursOnSubmit([:], multiline: false))
        XCTAssertFalse(PNTextInputManager.blursOnSubmit([:], multiline: true))
        XCTAssertTrue(PNTextInputManager.blursOnSubmit(["blur_on_submit": true], multiline: true))
    }

    func testMultilineInputReportsContentSizeAndSubmitsOnBlurOnSubmit() throws {
        let textView = try XCTUnwrap(try create("TextInput", tag: 6302, [
            "value": "line", "multiline": true, "blur_on_submit": true,
            "_pn_events": ["on_content_size_change", "on_submit"],
        ]) as? UITextView)
        _ = mount(textView)
        textView.frame = CGRect(x: 0, y: 0, width: 200, height: 80)
        let delegate = try XCTUnwrap(textView.delegate)
        delegate.textViewDidChange?(textView)
        XCTAssertEqual(delegate.textView?(textView, shouldChangeTextIn: NSRange(location: 4, length: 0), replacementText: "\n"), false,
                       "blur_on_submit swallows the newline and submits")
        settle()
        let size = try XCTUnwrap(firstArg("on_content_size_change") as? [String: Any])
        XCTAssertEqual(Set(size.keys), ["width", "height"])
        XCTAssertEqual(firstArg("on_submit") as? String, "line")
    }

    // MARK: - Image, Modal, StatusBar, Pressable, TabBar

    func testImageLoadLifecycleEvents() throws {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 4, height: 4))
        let png = renderer.pngData { context in UIColor.red.setFill(); context.fill(CGRect(x: 0, y: 0, width: 4, height: 4)) }
        let source = "data:image/png;base64," + png.base64EncodedString()
        _ = try create("Image", tag: 6401, ["source": source, "fade_duration": 120, "headers": ["Authorization": "Bearer x"],
                                             "_pn_events": ["on_load_start", "on_load", "on_load_end"]])
        settle(0.5)
        let names = PNEventCapture.all.filter { $0.kind == "event" && $0.tag == 6401 }.map(\.name)
        XCTAssertEqual(names, ["on_load_start", "on_load", "on_load_end"])
        XCTAssertEqual(PNViewState.existing(for: PNViewRegistry.shared.view(for: 6401)!)?.extras["headers"] as? [String: String], ["Authorization": "Bearer x"])
    }

    func testModalRequestCloseKeepsSheetPresented() throws {
        let placeholder = try create("Modal", tag: 6501, ["visible": false, "_pn_events": ["on_request_close"]])
        _ = mount(placeholder)
        PNViewRegistry.shared.resolve(6501)?.manager.update(view: placeholder, changed: ["visible": true])
        settle(0.5)
        let state = try XCTUnwrap(PNViewState.existing(for: placeholder))
        let presentation = try XCTUnwrap(state.extras["modal"] as? PNModalManager.Presentation)
        let controller = try XCTUnwrap(presentation.controller as? PNModalViewController)
        let presentationController = try XCTUnwrap(controller.presentationController)
        // UIKit's sequence for a pull-down: ask, then report the refused attempt.
        XCTAssertFalse(controller.presentationControllerShouldDismiss(presentationController), "a pull-down never dismisses on its own")
        controller.presentationControllerDidAttemptToDismiss(presentationController)
        settle()
        XCTAssertEqual(PNEventCapture.events(named: "on_request_close").count, 1, "one pull-down is one request")
        XCTAssertNotNil(state.extras["modal"], "the sheet stays presented until Python flips `visible`")
        state.props["_pn_events"] = []
        XCTAssertFalse(controller.requestClose(), "without a listener the sheet simply bounces back")
        PNViewRegistry.shared.resolve(6501)?.manager.update(view: placeholder, changed: ["visible": false])
        settle(0.5)
    }

    func testModalKeepsItsChildrenAcrossPresentations() throws {
        let placeholder = try create("Modal", tag: 6502, ["visible": false, "_pn_events": ["on_dismiss"]])
        _ = mount(placeholder)
        try PNTransaction.apply([.create(tag: 6503, type: "View", props: [:]), .insert(parent: 6502, child: 6503, index: 0)])
        let child = try XCTUnwrap(PNViewRegistry.shared.view(for: 6503))
        let state = try XCTUnwrap(PNViewState.existing(for: placeholder))
        try PNTransaction.apply([.update(tag: 6502, changed: ["visible": true])])
        settle(0.6)
        let first = try XCTUnwrap(state.extras["modal"] as? PNModalManager.Presentation)
        XCTAssertTrue(child.superview === first.content)
        try PNTransaction.apply([.update(tag: 6502, changed: ["visible": false])])
        settle(0.6)
        XCTAssertEqual(PNEventCapture.events(named: "on_dismiss").count, 1)
        try PNTransaction.apply([.update(tag: 6502, changed: ["visible": true])])
        settle(0.6)
        let second = try XCTUnwrap(state.extras["modal"] as? PNModalManager.Presentation)
        XCTAssertFalse(first === second)
        XCTAssertTrue(child.superview === second.content, "a reopened modal shows its children again")
        try PNTransaction.apply([.update(tag: 6502, changed: ["visible": false])])
        settle(0.6)
    }

    func testModalBackdropAndLockedSheetRequests() throws {
        let overlay = try create("Modal", tag: 6504, ["visible": false, "presentation_style": "overlay", "_pn_events": ["on_request_close"]])
        _ = mount(overlay)
        try PNTransaction.apply([.create(tag: 6505, type: "View", props: [:]), .insert(parent: 6504, child: 6505, index: 0)])
        try PNTransaction.apply([.update(tag: 6504, changed: ["visible": true])])
        settle(0.6)
        let overlayState = try XCTUnwrap(PNViewState.existing(for: overlay))
        let controller = try XCTUnwrap((overlayState.extras["modal"] as? PNModalManager.Presentation)?.controller as? PNModalViewController)
        PNViewRegistry.shared.view(for: 6505)?.frame = CGRect(x: 20, y: 200, width: 200, height: 100)
        XCTAssertFalse(controller.isBackdrop(CGPoint(x: 40, y: 250)), "a tap on a child isn't a backdrop tap")
        XCTAssertTrue(controller.isBackdrop(CGPoint(x: 300, y: 600)))
        controller.backdropTapped()
        settle()
        XCTAssertEqual(PNEventCapture.events(named: "on_request_close").count, 1)
        try PNTransaction.apply([.update(tag: 6504, changed: ["visible": false])])
        settle(0.6)

        // `dismiss_on_backdrop=False` locks a sheet; its pull-down isn't a request.
        let sheet = try create("Modal", tag: 6506, ["visible": false, "dismiss_on_backdrop": false, "_pn_events": ["on_request_close"]])
        window.rootViewController?.view.addSubview(sheet)
        try PNTransaction.apply([.update(tag: 6506, changed: ["visible": true])])
        settle(0.6)
        let sheetState = try XCTUnwrap(PNViewState.existing(for: sheet))
        let locked = try XCTUnwrap((sheetState.extras["modal"] as? PNModalManager.Presentation)?.controller as? PNModalViewController)
        XCTAssertTrue(locked.isModalInPresentation)
        locked.presentationControllerDidAttemptToDismiss(try XCTUnwrap(locked.presentationController))
        settle()
        XCTAssertEqual(PNEventCapture.events(named: "on_request_close").count, 1)
        try PNTransaction.apply([.update(tag: 6506, changed: ["visible": false])])
        settle(0.6)
    }

    func testStatusBarAnimatedAndPressableDisabled() throws {
        let bar = try create("StatusBar", tag: 6601, ["hidden": true, "animated": true, "translucent": true])
        XCTAssertTrue(PNStatusBarState.hidden)
        PNViewRegistry.shared.resolve(6601)?.manager.update(view: bar, changed: ["hidden": false])
        XCTAssertFalse(PNStatusBarState.hidden)

        let pressable = try create("Pressable", tag: 6602, ["disabled": true, "delay_long_press": 700, "android_ripple": ["color": "#000"],
                                                             "_pn_events": ["on_press", "on_long_press"]])
        XCTAssertTrue(pressable.isUserInteractionEnabled, "disabled pressables keep their children interactive")
        XCTAssertTrue(pressable.accessibilityTraits.contains(.notEnabled))
        let handler = try XCTUnwrap(PNViewState.existing(for: pressable)?.retained.compactMap { $0 as? PNPressHandler }.first)
        XCTAssertEqual(handler.longPress.minimumPressDuration, 0.7, accuracy: 0.001)
        XCTAssertTrue(PNViewState.existing(for: pressable)?.flag("press_disabled") == true)
        PNViewRegistry.shared.resolve(6602)?.manager.update(view: pressable, changed: ["disabled": false])
        XCTAssertFalse(pressable.accessibilityTraits.contains(.notEnabled))
    }

    func testTabBarThemeProps() throws {
        let bar = try XCTUnwrap(try create("TabBar", tag: 6701, [
            "items": [["name": "home", "title": "Home"], ["name": "search", "title": "Search"]],
            "tint_color": "#ff0000", "inactive_tint_color": "#00ff00", "background_color": "#0000ff", "translucent": false, "shows_labels": false,
        ]) as? UITabBar)
        XCTAssertEqual(PNColor.hexString(bar.tintColor).lowercased(), "#ffff0000")
        XCTAssertEqual(bar.unselectedItemTintColor.map { PNColor.hexString($0).lowercased() }, "#ff00ff00")
        XCTAssertFalse(bar.isTranslucent)
        XCTAssertEqual(bar.items?.map(\.title), [nil, nil], "shows_labels=false hides the titles")
        XCTAssertEqual(bar.items?.map(\.accessibilityLabel), ["Home", "Search"])
        PNViewRegistry.shared.resolve(6701)?.manager.update(view: bar, changed: ["shows_labels": true])
        XCTAssertEqual(bar.items?.map(\.title), ["Home", "Search"])
    }

    // MARK: - Navigation theme colors

    func testHeaderThemeColorsApplyToEveryStackScreen() throws {
        let navigation = UINavigationController(rootViewController: UIViewController())
        let screen = UIViewController()
        navigation.pushViewController(screen, animated: false)
        let options: [String: Any] = [
            "title": "Inbox", "header_tint_color": "#ff0000",
            "header_style": ["background_color": "#00ff00"], "header_title_style": ["color": "#0000ff"],
        ]
        HostModule.applyOptions(options, to: screen)
        XCTAssertEqual(PNColor.hexString(navigation.navigationBar.tintColor).lowercased(), "#ffff0000")
        XCTAssertEqual(navigation.navigationBar.barTintColor.map { PNColor.hexString($0).lowercased() }, "#ff00ff00")
        let appearance = try XCTUnwrap(screen.navigationItem.standardAppearance)
        XCTAssertEqual(appearance.backgroundColor.map { PNColor.hexString($0).lowercased() }, "#ff00ff00")
        XCTAssertEqual((appearance.titleTextAttributes[.foregroundColor] as? UIColor).map { PNColor.hexString($0).lowercased() }, "#ff0000ff")
        let root = navigation.viewControllers[0]
        HostModule.applyItemAppearance(["header_style": ["background_color": "#123456"]], to: root)
        XCTAssertEqual(root.navigationItem.standardAppearance?.backgroundColor.map { PNColor.hexString($0).lowercased() }, "#ff123456")
    }

    // MARK: - Easing

    func testEasingVocabulary() {
        XCTAssertEqual(PNEasing.controlPoints("ease")!.0, 0.42)
        XCTAssertEqual(PNEasing.controlPoints("ease")!.2, 1)
        XCTAssertEqual(PNEasing.controlPoints("ease_out")!.2, 0.58)
        XCTAssertNil(PNEasing.controlPoints("bounce"))
        XCTAssertNil(PNEasing.controlPoints("wobble"))
        XCTAssertNil(PNEasing.controlPoints([1, 2, 3]))
        XCTAssertNotNil(PNEasing.controlPoints([0.1, 0.2, 0.3, 0.4]))
        XCTAssertTrue(PNEasing.isValid("bounce"))
        XCTAssertFalse(PNEasing.isValid("wobble"))
        let quad = PNEasing.function("quad")!
        let cubic = PNEasing.function("cubic")!
        for t in stride(from: 0.0, through: 1.0, by: 0.125) {
            XCTAssertEqual(quad(t), t * t, accuracy: 1e-4, "quad(\(t))")
            XCTAssertEqual(cubic(t), t * t * t, accuracy: 1e-4, "cubic(\(t))")
        }
        XCTAssertEqual(PNEasing.bounce(1), 1, accuracy: 1e-9)
        XCTAssertEqual(PNEasing.bounce(0), 0, accuracy: 1e-9)
        XCTAssertEqual(PNEasing.bounce(1 / 2.75), 1, accuracy: 1e-9, "first bounce lands at 1")
        XCTAssertLessThan(PNEasing.bounce(0.8), 1)
        XCTAssertNil(PNEasing.function("nope"))

        var frames: [Double] = []
        let driver = PNSampledDriver(from: 0, to: 100, durationMs: 200, delayMs: 0, easing: PNEasing.bounce, frame: { frames.append($0) }, completion: {})
        XCTAssertFalse(driver.advance(elapsedMs: 100))
        XCTAssertEqual(frames.last!, 100 * PNEasing.bounce(0.5), accuracy: 1e-9)
        XCTAssertTrue(driver.advance(elapsedMs: 250))
        XCTAssertEqual(driver.currentValue, 100)
    }

    func testAnimatorRejectsUnknownEasingAndRunsBounceBySampling() throws {
        let view = try create("View", tag: 6801, [:])
        _ = mount(view)
        let rejected = PNAnimator.shared.handle(tag: 6801, request: ["op": "start", "id": 1, "prop": "opacity", "spec": ["kind": "timing", "to": 0.5, "easing": "wobble"]])
        XCTAssertEqual((rejected as? [String: Any])?["ok"] as? Bool, false)
        let bounce = PNAnimator.shared.handle(tag: 6801, request: ["op": "start", "id": 2, "prop": "translate_x", "spec": ["kind": "timing", "from": 0, "to": 50, "duration_ms": 100, "easing": "bounce"]])
        XCTAssertEqual((bounce as? [String: Any])?["ok"] as? Bool, true)
        settle(0.4)
        XCTAssertEqual(PNViewState.existing(for: view)?.animatedTransform["translate_x"] ?? 0, 50, accuracy: 0.001)
        let completions = PNEventCapture.all.filter { $0.kind == "animation" && PNProps.int($0.payload["id"]) == 2 }
        XCTAssertEqual(completions.count, 1)
        XCTAssertEqual(completions.first?.payload["finished"] as? Bool, true)
        let rotated = PNAnimator.shared.handle(tag: 6801, request: ["op": "set", "prop": "rotate_x", "value": 45])
        XCTAssertNil(rotated)
        XCTAssertFalse(CATransform3DIsAffine(view.layer.transform), "rotate_x is an animated channel")
    }

    // MARK: - Gestures

    func testDisabledGesturesKeepIndicesAndPanConfigActivationRules() throws {
        let manager = PNViewManager()
        let view = manager.createView(tag: 6901, props: [
            "gestures": [
                ["kind": "tap", "enabled": false],
                ["kind": "pan", "enabled": true, "min_distance": NSNull(), "min_pointers": 1, "max_pointers": 2,
                 "active_offset_x": [-20, 20], "fail_offset_y": [-15, 15], "min_velocity": NSNull()],
                ["kind": "long_press", "wait_for": [0]],
            ],
        ])
        let recognizers = PNViewState.existing(for: view)?.gestureRecognizers ?? []
        XCTAssertEqual(recognizers.count, 2, "the disabled tap installs nothing")
        let pan = try XCTUnwrap(recognizers[0] as? PNPanGestureRecognizer)
        XCTAssertEqual(PNGestureCoordinator.shared.index(of: pan), 1, "indices follow spec positions")
        XCTAssertEqual(PNGestureCoordinator.shared.index(of: recognizers[1]), 2)
        XCTAssertEqual(pan.maximumNumberOfTouches, 2)
        XCTAssertEqual(pan.minimumNumberOfTouches, 1)
        XCTAssertEqual(pan.evaluate(dx: 10, dy: 0, speed: 0), .possible)
        XCTAssertEqual(pan.evaluate(dx: 20, dy: 0, speed: 0), .possible, "crossing is strict")
        XCTAssertEqual(pan.evaluate(dx: 21, dy: 0, speed: 0), .began)
        let vertical = PNPanGestureRecognizer(config: PNPanConfig(["active_offset_x": [-20, 20], "fail_offset_y": [-15, 15]]))
        XCTAssertEqual(vertical.evaluate(dx: 5, dy: 16, speed: 0), .failed)
        XCTAssertEqual(vertical.evaluate(dx: 50, dy: 0, speed: 0), .failed, "a failed interaction stays failed")

        let distance = PNPanConfig(["min_distance": 10, "min_pointers": 1])
        XCTAssertFalse(distance.activates(dx: 6, dy: 6, speed: 0))
        XCTAssertTrue(distance.activates(dx: 8, dy: 8, speed: 0))
        let velocity = PNPanConfig(["min_distance": NSNull(), "min_velocity": 500])
        XCTAssertFalse(velocity.activates(dx: 100, dy: 100, speed: 100), "distance alone doesn't count once min_distance is null")
        XCTAssertTrue(velocity.activates(dx: 1, dy: 1, speed: 600))
        let open = PNPanConfig(["min_distance": NSNull()])
        XCTAssertTrue(open.activates(dx: 0.5, dy: 0, speed: 0), "no criteria: any movement activates")
        let oneSided = PNPanConfig(["active_offset_x": [NSNull(), 30]])
        XCTAssertFalse(oneSided.activates(dx: -100, dy: 0, speed: 0))
        XCTAssertTrue(oneSided.activates(dx: 31, dy: 0, speed: 0))
        XCTAssertEqual(PNPanConfig(["min_pointers": 2, "max_pointers": 1]).maxPointers, 2, "max_pointers never drops below min_pointers")
    }

    func testGesturePayloadCarriesAbsoluteCoordinates() throws {
        let view = try create("View", tag: 6902, ["gestures": [["kind": "tap"]], "_pn_events": ["gesture:0"]])
        _ = mount(view)
        view.frame = CGRect(x: 50, y: 100, width: 100, height: 100)
        let tap = try XCTUnwrap(PNViewState.existing(for: view)?.gestureRecognizers.first as? UITapGestureRecognizer)
        PNGestureCoordinator.shared.emitForTesting(tap, state: .ended)
        settle()
        let payload = try XCTUnwrap(firstArg("gesture:0") as? [String: Any])
        for key in ["kind", "state", "x", "y", "absolute_x", "absolute_y", "translation_x", "translation_y", "velocity_x", "velocity_y", "scale", "rotation", "pointer_count", "direction"] {
            XCTAssertNotNil(payload[key], "missing \(key)")
        }
        XCTAssertTrue(payload["direction"] is NSNull)
        XCTAssertEqual(payload["state"] as? String, "ended")
    }
}

private let captureCallbackForContractTests: PNCallbackFn = { kind, tag, name, payload in
    PNEventCapture.record(
        kind.map { String(cString: $0) } ?? "", tag,
        name.map { String(cString: $0) } ?? "", payload.map { String(cString: $0) } ?? "{}"
    )
    return nil
}
