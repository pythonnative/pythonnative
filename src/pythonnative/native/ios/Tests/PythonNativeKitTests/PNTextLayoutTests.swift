import XCTest
import UIKit
@testable import PythonNativeKit

/// Text measurement off the main thread (RFC 0007): `PNTextLayout` must
/// agree with the `UILabel` that draws the same attributed string.
final class PNTextLayoutTests: XCTestCase {
    private let paragraph = "The quick brown fox jumps over the lazy dog, then naps in the warm afternoon sun."

    private func label(_ props: [String: Any], width: CGFloat) -> CGSize {
        let view = PNTextManager().createView(tag: 0, props: props) as! UILabel
        return view.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude))
    }

    func testSingleLineMatchesTheLabel() {
        let props: [String: Any] = ["text": "Hello, world", "font_size": 17]
        let measured = PNTextLayout(props).measure(maxWidth: .infinity)
        let drawn = label(props, width: .greatestFiniteMagnitude)
        XCTAssertEqual(measured.width, drawn.width, accuracy: 1)
        XCTAssertEqual(measured.height, drawn.height, accuracy: 1)
    }

    func testWrappingMatchesTheLabelAndRoundsToPixels() {
        let props: [String: Any] = ["text": paragraph, "font_size": 15]
        let layout = PNTextLayout(props)
        let wrapped = layout.measure(maxWidth: 160)
        let single = layout.measure(maxWidth: .infinity)
        XCTAssertLessThanOrEqual(wrapped.width, 160)
        XCTAssertGreaterThan(wrapped.height, single.height * 2, "the paragraph wraps onto several lines")
        XCTAssertEqual(wrapped.height, label(props, width: 160).height, accuracy: 1)
        let scale = UIScreen.main.scale
        XCTAssertEqual((wrapped.width * scale).rounded(), wrapped.width * scale, accuracy: 1e-6)
        XCTAssertEqual((wrapped.height * scale).rounded(), wrapped.height * scale, accuracy: 1e-6)
    }

    func testMaxLinesAndMaxHeightCapTheHeight() {
        let base: [String: Any] = ["text": paragraph, "font_size": 15]
        let one = PNTextLayout(["text": "x", "font_size": 15]).measure(maxWidth: .infinity).height
        var capped = base
        capped["max_lines"] = 2
        let two = PNTextLayout(capped).measure(maxWidth: 120)
        XCTAssertEqual(two.height, one * 2, accuracy: 1.5)
        XCTAssertEqual(PNTextLayout(capped).numberOfLines, 2)
        XCTAssertLessThanOrEqual(PNTextLayout(base).measure(maxWidth: 120, maxHeight: 30).height, 30)
    }

    func testLineHeightSpacingAndFontsChangeTheSize() {
        let plain = PNTextLayout(["text": paragraph, "font_size": 15]).measure(maxWidth: 200)
        let tall = PNTextLayout(["text": paragraph, "font_size": 15, "line_height": 30]).measure(maxWidth: 200)
        XCTAssertGreaterThan(tall.height, plain.height)
        let wide = PNTextLayout(["text": "spacing", "font_size": 15, "letter_spacing": 4]).measure(maxWidth: .infinity)
        let narrow = PNTextLayout(["text": "spacing", "font_size": 15]).measure(maxWidth: .infinity)
        XCTAssertGreaterThan(wide.width, narrow.width + 20)
        let bold = PNTextLayout(["text": "Weight", "font_size": 20, "font_weight": "bold"]).measure(maxWidth: .infinity)
        let regular = PNTextLayout(["text": "Weight", "font_size": 20]).measure(maxWidth: .infinity)
        XCTAssertGreaterThan(bold.width, regular.width)
    }

    func testSpansMeasureTheirOwnFonts() {
        let spans: [[String: Any]] = [["text": "small "], ["text": "BIG", "font_size": 40]]
        let layout = PNTextLayout(["spans": spans, "font_size": 12])
        XCTAssertEqual(layout.attributed.string, "small BIG")
        XCTAssertEqual(layout.spanRanges, [NSRange(location: 0, length: 6), NSRange(location: 6, length: 3)])
        let size = layout.measure(maxWidth: .infinity)
        XCTAssertGreaterThan(size.height, 40)
    }

    func testTransformAndEmptyText() {
        XCTAssertEqual(PNTextLayout(["text": "shout", "text_transform": "uppercase"]).attributed.string, "SHOUT")
        let empty = PNTextLayout(["text": ""]).measure(maxWidth: 100)
        XCTAssertEqual(empty.width, 0)
    }

    func testMeasuresOffTheMainThread() {
        let props: [String: Any] = ["text": paragraph, "font_size": 15]
        let onMain = PNTextLayout(props).measure(maxWidth: 160)
        let offMain = PNCoreHarness.onWorker { PNTextLayout(props).measure(maxWidth: 160) }
        XCTAssertEqual(onMain, offMain)
    }

    func testCoreLaysOutTextWithThePlatformMeasurement() throws {
        let core = PNCoreHarness()
        core.roots = [1]
        let props: [String: Any] = ["text": paragraph, "font_size": 15]
        core.commit([["c", 1, "Column", ["width": 160, "align_items": "flex_start", "background_color": "#FFFFFF"]],
                     ["c", 2, "Text", props], ["i", 1, 2, 0]])
        let text = try XCTUnwrap(PNViewRegistry.shared.view(for: 2))
        let expected = PNTextLayout(props).measure(maxWidth: 160)
        // Yoga rounds measured leaves up to whole points.
        XCTAssertEqual(text.bounds.width, expected.width.rounded(.up), accuracy: 0.01)
        XCTAssertEqual(text.bounds.height, expected.height.rounded(.up), accuracy: 0.01)
    }
}
