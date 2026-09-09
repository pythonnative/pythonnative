import XCTest
import UIKit
@testable import PythonNativeKit

final class PNTransactionTests: XCTestCase {
    private let application = UUID().uuidString
    private var revision = 0
    @discardableResult private func apply(_ operations: String, success: Bool = true) -> [String: Any] {
        let result = PNJSON.decodeObject(PNCommit.apply("{\"version\":2,\"application\":\"\(application)\",\"surface\":1,\"revision\":\(revision + 1),\"ops\":\(operations)}"))
        XCTAssertEqual(result["ok"] as? Bool, success, String(describing: result))
        if success { revision += 1 }
        return result
    }
    func testWholeCommitRejectsMalformedOperations() {
        XCTAssertNil(PNRegistry.shared.manager(for: "MissingImplementation"))
        XCTAssertThrowsError(try PNTransaction.apply([.create(tag: 999, type: "MissingImplementation", props: [:])]))
        apply("[[\"c\",1,\"View\",{}],[\"u\",999,{}]]", success: false)
        XCTAssertNil(PNViewRegistry.shared.view(for: 1))
        apply("[[\"c\",1,\"View\",{}]]")
        apply("[[\"u\",1,{\"opacity\":\"invalid\"}]]", success: false)
        apply("[[\"u\",1,{\"typo\":3}]]", success: false)
        XCTAssertEqual(PNViewRegistry.shared.view(for: 1)?.alpha, 1)
    }
    func testHierarchyMoveAndDestroy() {
        apply("[[\"c\",10,\"View\",{}],[\"c\",11,\"Text\",{\"text\":\"hello\"}],[\"c\",12,\"View\",{}],[\"i\",10,11,0],[\"i\",10,12,1]]")
        apply("[[\"i\",10,12,0]]")
        XCTAssertEqual(PNViewRegistry.shared.view(for: 10)?.subviews.map { PNViewState.existing(for: $0)?.tag }, [12,11])
        apply("[[\"d\",10]]", success: false)
        apply("[[\"d\",11],[\"d\",12],[\"d\",10]]")
        XCTAssertNil(PNViewRegistry.shared.view(for: 10))
    }
    func testRecreationPreservesTagAndParentAndRestoresDefaults() {
        apply("[[\"c\",20,\"View\",{}],[\"c\",21,\"TextInput\",{\"value\":\"abc\",\"multiline\":false}],[\"i\",20,21,0]]")
        let original = PNViewRegistry.shared.view(for: 21)
        XCTAssertTrue(original is UITextField)
        apply("[[\"u\",21,{\"multiline\":true}]]")
        let replacement = PNViewRegistry.shared.view(for: 21)
        XCTAssertTrue(replacement is UITextView)
        XCTAssertFalse(original === replacement)
        XCTAssertTrue(replacement?.superview === PNViewRegistry.shared.view(for: 20))
        XCTAssertEqual((replacement as? UITextView)?.text, "abc")
        apply("[[\"c\",22,\"Text\",{\"text\":\"reset\",\"color\":\"#ff0000\",\"font_size\":40}],[\"i\",20,22,1]]")
        apply("[[\"u\",22,{\"font_size\":null,\"color\":null}]]")
        let label = PNViewRegistry.shared.view(for: 22) as? UILabel
        XCTAssertNotEqual(label?.textColor, UIColor.red)
        XCTAssertLessThan(label?.font.pointSize ?? 99, 40)
    }

    func testContainerRecreationUsesChildrenInsertedInTheSameCommit() {
        apply("[[\"c\",30,\"View\",{\"background_color\":\"#ff0000\"}],[\"c\",31,\"Text\",{\"text\":\"child\"}],[\"i\",30,31,0],[\"u\",30,{\"background_color\":null}]]")
        let parent = PNViewRegistry.shared.view(for: 30)
        XCTAssertTrue(PNViewRegistry.shared.view(for: 31)?.superview === parent)
        XCTAssertEqual(parent?.subviews.count, 1)
    }
}
