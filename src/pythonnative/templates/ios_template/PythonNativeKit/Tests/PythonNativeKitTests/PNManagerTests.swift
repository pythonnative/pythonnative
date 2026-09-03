import XCTest
@testable import PythonNativeKit

final class PNManagerTests: XCTestCase {
    override func tearDown() {
        PNViewRegistry.shared.removeAll()
        super.tearDown()
    }

    func testViewManagerAppliesCommonProps() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 1, props: [
            "background_color": "#ff0000",
            "opacity": 0.5,
            "border_width": 2,
            "border_color": "#00ff00",
            "border_radius": 8,
            "test_id": "hero",
            "accessibility_label": "Hero card",
        ])
        XCTAssertEqual(view.alpha, 0.5, accuracy: 0.001)
        XCTAssertEqual(view.layer.borderWidth, 2)
        XCTAssertEqual(view.layer.cornerRadius, 8)
        XCTAssertEqual(view.accessibilityIdentifier, "hero")
        XCTAssertEqual(view.accessibilityLabel, "Hero card")
        XCTAssertEqual(PNColor.hexString(view.backgroundColor ?? .clear).lowercased(), "#ffff0000")

        manager.update(view: view, changed: ["opacity": 1, "background_color": NSNull(), "display": "none"])
        XCTAssertEqual(view.alpha, 1, accuracy: 0.001)
        XCTAssertTrue(view.isHidden)
        XCTAssertNil(PNViewState.existing(for: view)?.props["background_color"])
        XCTAssertEqual(PNProps.double(PNViewState.existing(for: view)?.props["opacity"]), 1)
    }

    func testTransformPropBuildsAffineTransform() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 2, props: [
            "transform": [["translate_x": 10], ["translate_y": 5], ["scale": 2]],
        ])
        XCTAssertEqual(view.transform.tx, 10, accuracy: 0.001)
        XCTAssertEqual(view.transform.ty, 5, accuracy: 0.001)
        XCTAssertEqual(view.transform.a, 2, accuracy: 0.001)
        XCTAssertEqual(view.transform.d, 2, accuracy: 0.001)

        manager.update(view: view, changed: ["transform": [["rotate": "90deg"]]])
        XCTAssertEqual(view.transform.b, 1, accuracy: 0.001)
        XCTAssertEqual(view.transform.a, 0, accuracy: 0.001)

        manager.update(view: view, changed: ["transform": NSNull()])
        XCTAssertTrue(view.transform.isIdentity)
    }

    func testFrameSurvivesTransform() {
        let manager = PNViewManager()
        let view = manager.createView(tag: 3, props: ["transform": [["scale": 2]]])
        manager.setFrame(view: view, x: 10, y: 20, w: 100, h: 50)
        XCTAssertEqual(view.bounds.size, CGSize(width: 100, height: 50))
        XCTAssertEqual(view.center, CGPoint(x: 60, y: 45))
    }

    func testTextMeasureAndTransform() {
        let manager = PNTextManager()
        let view = manager.createView(tag: 4, props: ["text": "hello world", "font_size": 20, "text_transform": "uppercase"])
        XCTAssertEqual((view as? UILabel)?.text, "HELLO WORLD")
        let unconstrained = manager.measure(view: view, maxW: .infinity, maxH: .infinity)
        XCTAssertGreaterThan(unconstrained.width, 50)
        XCTAssertGreaterThan(unconstrained.height, 15)
        let narrow = manager.measure(view: view, maxW: 60, maxH: 1e6)
        XCTAssertLessThanOrEqual(narrow.width, 60)
        XCTAssertGreaterThan(narrow.height, unconstrained.height, "wrapped text grows in height")
        XCTAssertEqual(PNTextManager.transform("hello big world", mode: "capitalize"), "Hello Big World")
    }

    func testTextSpansProduceAttributedString() {
        let manager = PNTextManager()
        let view = manager.createView(tag: 5, props: [
            "spans": [["text": "Hi "], ["text": "there", "bold": true, "color": "#ff0000"]],
        ])
        let label = view as? UILabel
        XCTAssertEqual(label?.attributedText?.string, "Hi there")
        var range = NSRange()
        let color = label?.attributedText?.attribute(.foregroundColor, at: 3, effectiveRange: &range) as? UIColor
        XCTAssertNotNil(color)
        XCTAssertEqual(range.location, 3)
        XCTAssertEqual(range.length, 5)
    }

    func testVirtualListBindsRowsThroughRegistry() {
        PNTransaction.apply("[[\"c\", 40, \"View\", {\"background_color\": \"#123456\"}]]")
        let manager = PNVirtualListManager()
        guard let table = manager.createView(tag: 41, props: ["count": 3, "row_height": 50]) as? UITableView else {
            return XCTFail("expected a table")
        }
        XCTAssertEqual(table.dataSource?.tableView(table, numberOfRowsInSection: 0), 3)
        XCTAssertEqual(table.delegate?.tableView?(table, heightForRowAt: IndexPath(row: 1, section: 0)), 50)
        manager.update(view: table, changed: ["row_heights": [10, 20, 30]])
        XCTAssertEqual(table.delegate?.tableView?(table, heightForRowAt: IndexPath(row: 2, section: 0)), 30)
    }

    func testScrollPayloadShape() {
        let scroll = UIScrollView(frame: CGRect(x: 0, y: 0, width: 100, height: 200))
        scroll.contentSize = CGSize(width: 100, height: 800)
        scroll.contentOffset = CGPoint(x: 0, y: 40)
        let payload = PNScrollPayload.make(scroll)
        XCTAssertEqual(payload["y"] as? Double, 40)
        XCTAssertEqual(payload["extent"] as? Double, 200)
        XCTAssertEqual(payload["range"] as? Double, 800)
    }

    func testRegistryKnowsEveryBuiltinType() {
        let names = PNRegistry.shared.componentNames
        for type in ["View", "Column", "Row", "Text", "Button", "TextInput", "Image", "Switch", "ProgressBar",
                     "ActivityIndicator", "WebView", "Spacer", "ScrollView", "SafeAreaView", "Modal", "Portal",
                     "Slider", "TabBar", "Pressable", "StatusBar", "KeyboardAvoidingView", "Picker", "Checkbox",
                     "SegmentedControl", "DatePicker", "VirtualList"] {
            XCTAssertTrue(names.contains(type), "missing manager for \(type)")
        }
        for module in ["Host", "Device", "Alert", "Storage", "SecureStore", "Clipboard", "Share", "Linking",
                       "Haptics", "Battery", "NetInfo", "AppState", "Permissions", "Notifications", "Camera",
                       "Location", "Biometrics"] {
            XCTAssertTrue(PNRegistry.shared.moduleNames.contains(module), "missing module \(module)")
        }
    }
}
