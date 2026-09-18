import XCTest
@testable import PythonNativeKit

final class PNAssetTests: XCTestCase {
    private var root: URL!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("pn-assets-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("images"), withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: root)
    }

    private func write(_ path: String, _ text: String = "x") throws {
        let url = root.appendingPathComponent(path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try text.data(using: .utf8)!.write(to: url)
    }

    private func manifest(files: [String], variants: [String: [String: String]] = [:]) throws {
        let manifest = PNAssetManifest(files: files, variants: variants, fonts: [])
        let json = try JSONSerialization.data(withJSONObject: PNValues.encode(manifest))
        try json.write(to: root.appendingPathComponent("pn_assets.json"))
    }

    func testURIHelpers() {
        XCTAssertTrue(PNAssets.isAssetURI("asset://images/a.png"))
        XCTAssertFalse(PNAssets.isAssetURI("https://example.com/a.png"))
        XCTAssertFalse(PNAssets.isAssetURI(nil))
        XCTAssertEqual(PNAssets.path(of: "asset:///images/a.png"), "images/a.png")
        XCTAssertEqual(PNAssets.path(of: "images/a.png"), "images/a.png")
        XCTAssertEqual(PNAssets.baseName("images/logo@2x.png"), "images/logo.png")
        XCTAssertEqual(PNAssets.baseName("images/logo@1.5x.png"), "images/logo.png")
        XCTAssertEqual(PNAssets.baseName("logo.png"), "logo.png")
        XCTAssertEqual(PNAssets.baseName("email@work.png"), "email@work.png")
        XCTAssertEqual(PNAssets.scale(of: "images/logo@3x.png"), 3)
        XCTAssertEqual(PNAssets.scale(of: "images/logo.png"), 1)
    }

    func testResolvesDensityVariantsFromManifest() throws {
        try write("images/logo.png")
        try write("images/logo@2x.png")
        try write("images/logo@3x.png")
        try manifest(files: ["images/logo.png"], variants: [
            "images/logo.png": ["1": "images/logo.png", "2": "images/logo@2x.png", "3": "images/logo@3x.png"],
        ])
        let assets = PNAssets(bundleRoot: root)

        XCTAssertEqual(assets.resolve("asset://images/logo.png", scale: 2)?.path, "images/logo@2x.png")
        XCTAssertEqual(assets.resolve("asset://images/logo.png", scale: 2)?.scale, 2)
        // No exact match: prefer the next denser variant so we downsample.
        XCTAssertEqual(assets.resolve("images/logo.png", scale: 2.5)?.path, "images/logo@3x.png")
        // Above the densest: take the densest.
        XCTAssertEqual(assets.resolve("images/logo.png", scale: 4)?.path, "images/logo@3x.png")
        XCTAssertEqual(assets.resolve("images/logo.png", scale: 1)?.path, "images/logo.png")
        XCTAssertNil(assets.resolve("images/missing.png"))
        XCTAssertTrue(assets.exists("asset://images/logo.png"))
        XCTAssertEqual(String(data: try assets.read("images/logo.png"), encoding: .utf8), "x")
        XCTAssertThrowsError(try assets.read("nope.txt"))
    }

    func testFallsBackToDiskWithoutManifestAndOverlayShadowsBundle() throws {
        try write("data/config.json", "bundle")
        let assets = PNAssets(bundleRoot: root)
        XCTAssertEqual(assets.resolve("asset://data/config.json")?.path, "data/config.json")

        let overlay = FileManager.default.temporaryDirectory.appendingPathComponent("pn-overlay-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: overlay) }
        try FileManager.default.createDirectory(at: overlay.appendingPathComponent("data"), withIntermediateDirectories: true)
        try "overlay".data(using: .utf8)!.write(to: overlay.appendingPathComponent("data/config.json"))
        try "new".data(using: .utf8)!.write(to: overlay.appendingPathComponent("data/extra.json"))

        let before = assets.generation
        assets.configure(overlay: overlay.path, manifest: PNAssetManifest(files: ["data/config.json", "data/extra.json"], variants: [:], fonts: []))
        XCTAssertEqual(assets.generation, before + 1)
        XCTAssertEqual(String(data: try assets.read("data/config.json"), encoding: .utf8), "overlay")
        XCTAssertTrue(assets.exists("data/extra.json"))

        assets.configure(overlay: nil, manifest: nil)
        XCTAssertEqual(String(data: try assets.read("data/config.json"), encoding: .utf8), "bundle")
        XCTAssertFalse(assets.exists("data/extra.json"))
    }

    func testFontLookupPrefersMatchingStyleThenClosestWeight() {
        let assets = PNAssets(bundleRoot: root)
        // No fonts registered: family unknown.
        XCTAssertNil(assets.fontName(family: "Inter", weight: 400, italic: false))
        let faces = [
            PNFontFace(family: "Inter", weight: 400, italic: false, postscript_name: "Inter-Regular", path: "fonts/a.ttf"),
            PNFontFace(family: "Inter", weight: 700, italic: false, postscript_name: "Inter-Bold", path: "fonts/b.ttf"),
            PNFontFace(family: "Inter", weight: 400, italic: true, postscript_name: "Inter-Italic", path: "fonts/c.ttf"),
        ]
        // Registration of the (nonexistent) files fails quietly; the lookup table still fills.
        assets.configure(overlay: root.path, manifest: PNAssetManifest(files: [], variants: [:], fonts: faces))
        XCTAssertEqual(assets.fontName(family: "inter", weight: 400, italic: false), "Inter-Regular")
        XCTAssertEqual(assets.fontName(family: "Inter", weight: 600, italic: false), "Inter-Bold")
        XCTAssertEqual(assets.fontName(family: "Inter", weight: 900, italic: true), "Inter-Italic")
        XCTAssertNil(assets.fontName(family: "Roboto", weight: 400, italic: false))
    }
}

final class PNSvgTests: XCTestCase {
    private func shape(_ kind: PNPNSvgShapeKind, d: String? = nil, cx: Double? = nil, cy: Double? = nil, r: Double? = nil,
                       x: Double? = nil, y: Double? = nil, width: Double? = nil, height: Double? = nil,
                       points: String? = nil, fill: String? = nil, stroke: String? = nil, transform: String? = nil) -> PNSvgShape {
        PNSvgShape(kind: kind, d: d, cx: cx, cy: cy, r: r, rx: nil, ry: nil, x: x, y: y, width: width, height: height,
                   x1: nil, y1: nil, x2: nil, y2: nil, points: points, fill: fill, fill_opacity: nil, fill_rule: nil,
                   stroke: stroke, stroke_width: nil, stroke_opacity: nil, stroke_linecap: nil, stroke_linejoin: nil,
                   stroke_dasharray: nil, opacity: nil, transform: transform)
    }

    func testViewBoxParsing() {
        XCTAssertEqual(PNSvgView.parseViewBox("0 0 24 24"), CGRect(x: 0, y: 0, width: 24, height: 24))
        XCTAssertEqual(PNSvgView.parseViewBox("-5,-5, 10 10"), CGRect(x: -5, y: -5, width: 10, height: 10))
        XCTAssertNil(PNSvgView.parseViewBox("0 0 24"))
        XCTAssertNil(PNSvgView.parseViewBox("0 0 0 24"))
        XCTAssertNil(PNSvgView.parseViewBox(nil))
    }

    func testPathParserHandlesCommandsRelativeMovesAndPackedArcFlags() throws {
        let box = try XCTUnwrap(PNSvgPathParser.parse("M0 0h10v10H0z")).boundingBoxOfPath
        XCTAssertEqual(box, CGRect(x: 0, y: 0, width: 10, height: 10))

        // Relative segments, scientific notation, and implicit lineto after moveto.
        let poly = try XCTUnwrap(PNSvgPathParser.parse("m1,1 2 0 0 2 -2 0z l1e1 0")).boundingBoxOfPath
        XCTAssertEqual(poly.minX, 1, accuracy: 0.001)
        XCTAssertEqual(poly.maxX, 11, accuracy: 0.001)

        // Curves: cubic, smooth cubic, quadratic, smooth quadratic.
        XCTAssertNotNil(PNSvgPathParser.parse("M0 0 C 1 1, 2 1, 3 0 S 5 -1, 6 0 Q 7 1 8 0 T 10 0"))

        // Arc flags may run together without separators ("10" is two flags,
        // not the number ten), as Lucide's minified paths do.
        let packed = try XCTUnwrap(PNSvgPathParser.parse("M5 0A5 5 0 10 5 5")).boundingBoxOfPath
        let spaced = try XCTUnwrap(PNSvgPathParser.parse("M5 0A5 5 0 1 0 5 5")).boundingBoxOfPath
        XCTAssertEqual(packed.width, spaced.width, accuracy: 0.001)
        XCTAssertEqual(packed.height, spaced.height, accuracy: 0.001)
        // Chord of 5 on a radius-5 circle: center sits 5*cos(30) from the
        // chord, so the large arc spans 4.33 + 5 horizontally.
        XCTAssertEqual(packed.width, 9.33, accuracy: 0.01)
        let lucide = try XCTUnwrap(PNSvgPathParser.parse("M21 12a9 9 0 11-6.219-8.56"))
        XCTAssertGreaterThan(lucide.boundingBoxOfPath.width, 10)

        XCTAssertNil(PNSvgPathParser.parse(""))
        XCTAssertNil(PNSvgPathParser.parse("garbage"))
    }

    func testTransformParsing() throws {
        let translate = try XCTUnwrap(PNSvgTransform.parse("translate(10, 20)"))
        XCTAssertEqual(translate.tx, 10)
        XCTAssertEqual(translate.ty, 20)
        let scale = try XCTUnwrap(PNSvgTransform.parse("scale(2)"))
        XCTAssertEqual(scale.a, 2)
        XCTAssertEqual(scale.d, 2)
        let rotate = try XCTUnwrap(PNSvgTransform.parse("rotate(90)"))
        let point = CGPoint(x: 1, y: 0).applying(rotate)
        XCTAssertEqual(point.x, 0, accuracy: 0.0001)
        XCTAssertEqual(point.y, 1, accuracy: 0.0001)
        // rotate about a center, composed with a translate.
        let composed = try XCTUnwrap(PNSvgTransform.parse("translate(5 5) rotate(180 1 1)"))
        let moved = CGPoint(x: 0, y: 0).applying(composed)
        XCTAssertEqual(moved.x, 7, accuracy: 0.0001)
        XCTAssertEqual(moved.y, 7, accuracy: 0.0001)
        let matrix = try XCTUnwrap(PNSvgTransform.parse("matrix(1 0 0 1 3 4)"))
        XCTAssertEqual(matrix.tx, 3)
        XCTAssertEqual(matrix.ty, 4)
        XCTAssertNil(PNSvgTransform.parse("spin(3)"))
    }

    func testGeometryForPrimitives() {
        XCTAssertEqual(PNSvgRenderer.geometry(shape(.rect, x: 1, y: 2, width: 3, height: 4))?.boundingBoxOfPath, CGRect(x: 1, y: 2, width: 3, height: 4))
        XCTAssertEqual(PNSvgRenderer.geometry(shape(.circle, cx: 5, cy: 5, r: 5))?.boundingBoxOfPath, CGRect(x: 0, y: 0, width: 10, height: 10))
        let polygon = PNSvgRenderer.geometry(shape(.polygon, points: "0,0 4,0 4,4"))?.boundingBoxOfPath
        XCTAssertEqual(polygon, CGRect(x: 0, y: 0, width: 4, height: 4))
        XCTAssertNil(PNSvgRenderer.geometry(shape(.path, d: "")))
    }

    func testViewBoxTransformModes() {
        let box = CGRect(x: 0, y: 0, width: 10, height: 10)
        let bounds = CGRect(x: 0, y: 0, width: 40, height: 20)
        let meet = PNSvgRenderer.viewBoxTransform(box, bounds: bounds, preserveAspectRatio: "meet")
        XCTAssertEqual(meet.a, 2)
        XCTAssertEqual(meet.tx, 10) // centered horizontally
        let slice = PNSvgRenderer.viewBoxTransform(box, bounds: bounds, preserveAspectRatio: "slice")
        XCTAssertEqual(slice.a, 4)
        let none = PNSvgRenderer.viewBoxTransform(box, bounds: bounds, preserveAspectRatio: "none")
        XCTAssertEqual(none.a, 4)
        XCTAssertEqual(none.d, 2)
    }

    func testRasterizesShapesWithCurrentColorAsTemplate() {
        let shapes = [shape(.rect, x: 0, y: 0, width: 24, height: 24, fill: "currentColor")]
        let image = PNSvgRenderer.image(shapes, viewBox: CGRect(x: 0, y: 0, width: 24, height: 24), size: CGSize(width: 25, height: 25), root: PNSvgPaint())
        XCTAssertEqual(image.size, CGSize(width: 25, height: 25))
        XCTAssertEqual(image.renderingMode, .alwaysTemplate)
        // Something was actually drawn: sample the center pixel's alpha.
        let cg = image.cgImage!
        let data = cg.dataProvider!.data!
        let bytes = CFDataGetBytePtr(data)!
        let x = cg.width / 2, y = cg.height / 2
        let offset = y * cg.bytesPerRow + x * (cg.bitsPerPixel / 8)
        let alphaIndex = cg.alphaInfo == .premultipliedFirst || cg.alphaInfo == .first ? 0 : 3
        XCTAssertGreaterThan(bytes[offset + alphaIndex], 0)
    }

    func testManagerAppliesPropsAndMeasuresFromViewBox() throws {
        let manager = PNSvgManager()
        let view = manager.createView(tag: 1, props: [
            "shapes": [["kind": "circle", "cx": 12, "cy": 12, "r": 10]],
            "view_box": "0 0 48 24",
            "stroke": "#ff0000",
            "stroke_width": 2,
        ])
        let svg = try XCTUnwrap(view as? PNSvgView)
        XCTAssertEqual(svg.shapes.count, 1)
        XCTAssertEqual(svg.viewBox, CGRect(x: 0, y: 0, width: 48, height: 24))
        XCTAssertEqual(svg.rootPaint.stroke, "#ff0000")
        XCTAssertEqual(svg.rootPaint.strokeWidth, 2)
        XCTAssertEqual(manager.measure(view: svg, maxW: .infinity, maxH: .infinity), CGSize(width: 48, height: 24))
        XCTAssertEqual(manager.measure(view: svg, maxW: 24, maxH: .infinity), CGSize(width: 24, height: 12))
        manager.update(view: svg, changed: ["shapes": []])
        XCTAssertTrue(svg.shapes.isEmpty)
    }

    func testTabBarIconFromShapesAndMissingSpec() {
        let spec: [String: Any] = ["shapes": [["kind": "path", "d": "M0 0h24v24H0z"]], "view_box": "0 0 24 24"]
        let image = PNTabBarManager.icon(spec)
        XCTAssertNotNil(image)
        XCTAssertEqual(image?.size, PNTabBarManager.iconSize)
        XCTAssertNil(PNTabBarManager.icon(nil))
        XCTAssertNil(PNTabBarManager.icon("house"))
        XCTAssertNil(PNTabBarManager.icon(["uri": "asset://missing.png"]))
    }
}

final class PNEffectManagerTests: XCTestCase {
    func testLinearGradientConfiguresLayer() throws {
        let manager = PNLinearGradientManager()
        let view = manager.createView(tag: 1, props: [
            "colors": ["#ff0000", "#0000ff"],
            "locations": [0, 1],
            "start_point": [0, 0],
            "end_point": [1, 0],
        ])
        let gradient = try XCTUnwrap(view as? PNGradientView)
        XCTAssertEqual(gradient.gradientLayer.colors?.count, 2)
        XCTAssertEqual(gradient.gradientLayer.locations, [0, 1])
        XCTAssertEqual(gradient.gradientLayer.startPoint, CGPoint(x: 0, y: 0))
        XCTAssertEqual(gradient.gradientLayer.endPoint, CGPoint(x: 1, y: 0))
        // Mismatched location count is ignored rather than crashing CoreAnimation.
        manager.update(view: gradient, changed: ["colors": ["#000", "#fff", "#f00"]])
        XCTAssertEqual(gradient.gradientLayer.colors?.count, 3)
        XCTAssertNil(gradient.gradientLayer.locations)
        // Defaults when points are removed: top to bottom.
        manager.update(view: gradient, changed: ["start_point": NSNull(), "end_point": NSNull()])
        XCTAssertEqual(gradient.gradientLayer.startPoint, CGPoint(x: 0, y: 0))
        XCTAssertEqual(gradient.gradientLayer.endPoint, CGPoint(x: 0, y: 1))
    }

    func testBlurViewInstallsEffectAndHostsChildrenInContentView() throws {
        let manager = PNBlurViewManager()
        let view = manager.createView(tag: 1, props: ["blur_type": "dark", "intensity": 100])
        let blur = try XCTUnwrap(view as? PNBlurView)
        XCTAssertNotNil(blur.effectView.effect)
        XCTAssertTrue(manager.childContainer(for: blur) === blur.effectView.contentView)
        manager.update(view: blur, changed: ["intensity": 0])
        XCTAssertNil(blur.effectView.effect)
        manager.update(view: blur, changed: ["intensity": 50])
        // A partial intensity is driven by a paused animator, which installs
        // the effect at its fractionComplete.
        XCTAssertNotNil(blur.effectView.effect)
        XCTAssertEqual(PNBlurViewManager.style("light"), .light)
        XCTAssertEqual(PNBlurViewManager.style("system_material"), .systemMaterial)
        XCTAssertEqual(PNBlurViewManager.style("bogus"), .regular)
    }
}
