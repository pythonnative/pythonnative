import XCTest
@testable import PythonNativeKit

final class PNColorTests: XCTestCase {
    private func rgba(_ color: UIColor?) -> [Int] {
        guard let color = color else { return [] }
        let c = PNColor.components(color)
        return [c.r, c.g, c.b, c.a].map { Int(round($0 * 255)) }
    }

    func testHexForms() {
        XCTAssertEqual(rgba(PNColor.parse("#f00")), [255, 0, 0, 255])
        XCTAssertEqual(rgba(PNColor.parse("#00ff00")), [0, 255, 0, 255])
        XCTAssertEqual(rgba(PNColor.parse("#800000ff")), [0, 0, 255, 128])
        XCTAssertEqual(rgba(PNColor.parse("#0000FF")), [0, 0, 255, 255])
    }

    func testFunctionalForms() {
        XCTAssertEqual(rgba(PNColor.parse("rgb(10, 20, 30)")), [10, 20, 30, 255])
        XCTAssertEqual(rgba(PNColor.parse("rgba(10, 20, 30, 0.5)")), [10, 20, 30, 128])
    }

    func testNamedColorsAndTransparent() {
        XCTAssertEqual(rgba(PNColor.parse("red")), [255, 0, 0, 255])
        XCTAssertEqual(rgba(PNColor.parse("white")), [255, 255, 255, 255])
        XCTAssertEqual(rgba(PNColor.parse("transparent")), [0, 0, 0, 0])
        XCTAssertNil(PNColor.parse(nil))
        XCTAssertNil(PNColor.parse(""))
        XCTAssertNil(PNColor.parse("not-a-color"))
    }

    func testIntegerARGB() {
        XCTAssertEqual(rgba(PNColor.parse(0xFF112233 as Int64)), [0x11, 0x22, 0x33, 255])
    }

    func testDynamicLightDark() {
        let color = PNColor.parse(["light": "#ffffff", "dark": "#000000"])
        XCTAssertNotNil(color)
        let light = color?.resolvedColor(with: UITraitCollection(userInterfaceStyle: .light))
        let dark = color?.resolvedColor(with: UITraitCollection(userInterfaceStyle: .dark))
        XCTAssertEqual(rgba(light), [255, 255, 255, 255])
        XCTAssertEqual(rgba(dark), [0, 0, 0, 255])
    }

    func testHexRoundTrip() {
        let hex = PNColor.hexString(UIColor(red: 1, green: 0, blue: 0, alpha: 1))
        XCTAssertEqual(hex.lowercased(), "#ffff0000", "ARGB, matching the Python animated color format")
        XCTAssertEqual(rgba(PNColor.parse(hex)), [255, 0, 0, 255])
    }
}
