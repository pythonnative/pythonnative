import XCTest
import UIKit
@testable import PythonNativeKit

final class PNLifecycleTests: XCTestCase {
    private var window: UIWindow!
    private var revision = 0
    private let application = UUID().uuidString
    private func apply(_ ops: [[Any]]) {
        revision += 1
        let json = PNJSON.encode(["version": 2, "application": application, "surface": 1, "revision": revision, "ops": ops])
        let result = PNJSON.decodeObject(PNCommit.apply(json))
        XCTAssertEqual(result["ok"] as? Bool, true, String(describing: result))
    }
    private func settle() {
        let ready = expectation(description: "native transition completes")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { ready.fulfill() }
        wait(for: [ready], timeout: 3)
        window.layoutIfNeeded()
    }
    override func tearDown() {
        window?.isHidden = true
        window?.rootViewController = nil
        window = nil
        super.tearDown()
    }
    func testNativeStackPushPopKeepsOriginalScreenAttached() throws {
        apply([["c", 801, "ScreenStack", ["flex": 1]], ["c", 802, "Screen", ["title": "Inbox", "flex": 1]],
               ["c", 803, "Text", ["text": "Original screen"]], ["i", 802, 803, 0], ["i", 801, 802, 0]])
        let stack = try XCTUnwrap(PNViewRegistry.shared.view(for: 801))
        let first = try XCTUnwrap(PNViewRegistry.shared.view(for: 802))
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let controller = UIViewController()
        controller.view = stack
        window.rootViewController = controller
        window.makeKeyAndVisible()
        settle()
        _ = PNLayout.compute(["roots": [801], "width": 390, "height": 844])
        XCTAssertTrue(first.window === window)
        apply([["c", 804, "Screen", ["title": "Detail", "flex": 1]], ["c", 805, "Text", ["text": "Detail screen"]],
               ["i", 804, 805, 0], ["i", 801, 804, 1]])
        settle()
        apply([["d", 805], ["d", 804]])
        settle()
        XCTAssertTrue(first.window === window, "Pop must restore the original physical screen")
        XCTAssertTrue(PNViewRegistry.shared.view(for: 803)?.window === window)
        XCTAssertGreaterThan(first.bounds.width, 0, "screen=\(first.frame) stack=\(stack.frame)")
        XCTAssertGreaterThan(first.bounds.height, 0, "screen=\(first.frame) stack=\(stack.frame)")
        XCTAssertFalse(first.isHidden)
    }

    func testControlledCompositionAndSelectionSurviveReplacement() throws {
        apply([["c", 811, "TextInput", ["value": "hello", "multiline": true]]])
        let input = try XCTUnwrap(PNViewRegistry.shared.view(for: 811) as? UITextView)
        window = UIWindow(frame: CGRect(x: 0, y: 0, width: 390, height: 844))
        let controller = UIViewController()
        window.rootViewController = controller
        controller.view.addSubview(input)
        input.frame = CGRect(x: 0, y: 80, width: 300, height: 120)
        window.makeKeyAndVisible()
        input.becomeFirstResponder()
        input.setMarkedText("composing", selectedRange: NSRange(location: 2, length: 0))
        XCTAssertNotNil(input.markedTextRange)
        apply([["u", 811, ["value": "controlled", "_pn_edit_revision": 100]]])
        XCTAssertNotEqual(input.text, "controlled")
        input.unmarkText()
        PNTextInputManager.scheduleCompositionFlush(input)
        settle()
        XCTAssertEqual(input.text, "controlled", "after composition flush")
        input.selectedRange = NSRange(location: 1, length: 3)
        XCTAssertEqual(input.text, "controlled", "after selection change")
        apply([["u", 811, ["multiline": false]]])
        let replacement = try XCTUnwrap(PNViewRegistry.shared.view(for: 811) as? UITextField)
        XCTAssertEqual(replacement.text, "controlled", "after physical replacement")
        XCTAssertTrue(replacement.isFirstResponder)
        let range = try XCTUnwrap(replacement.selectedTextRange)
        XCTAssertEqual(replacement.offset(from: replacement.beginningOfDocument, to: range.start), 1)
        XCTAssertEqual(replacement.offset(from: replacement.beginningOfDocument, to: range.end), 4)
    }
}
