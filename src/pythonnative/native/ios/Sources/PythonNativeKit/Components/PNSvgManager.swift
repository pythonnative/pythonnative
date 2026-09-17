import UIKit

/// `Svg`: one view that draws a list of flattened `SvgShape` records with
/// Core Graphics. Coordinates are in `view_box` units and are mapped into
/// the view's bounds according to `preserve_aspect_ratio`.
public final class PNSvgManager: PNTypedComponentManager<SvgProps> {
    public init() { super.init(SvgProps.self) }

    public override func makeView(props: [String: Any]) -> UIView {
        let view = PNSvgView(frame: .zero)
        view.isAccessibilityElement = false
        return view
    }

    public override func applyTyped(view: UIView, props: SvgProps, initial: Bool) {
        guard let svg = view as? PNSvgView else { return }
        var redraw = false
        if props.has_shapes {
            svg.shapes = props.shapes ?? []
            redraw = true
        }
        if props.has_view_box {
            svg.viewBox = PNSvgView.parseViewBox(props.view_box) ?? CGRect(x: 0, y: 0, width: 24, height: 24)
            redraw = true
            if let state = PNViewState.existing(for: svg) { PNLayout.invalidate(state.tag) }
        }
        if props.has_preserve_aspect_ratio {
            svg.preserveAspectRatio = props.preserve_aspect_ratio?.rawValue ?? "meet"
            redraw = true
        }
        let paintKeys = ["fill", "stroke", "stroke_width", "stroke_linecap", "stroke_linejoin", "fill_rule", "color"]
        if paintKeys.contains(where: { PNProps.has(props.values, $0) }) {
            let merged = mergedProps(svg)
            svg.rootPaint = PNSvgPaint(
                fill: PNProps.string(PNProps.value(merged, "fill")),
                stroke: PNProps.string(PNProps.value(merged, "stroke")),
                strokeWidth: PNProps.double(PNProps.value(merged, "stroke_width")).map { CGFloat($0) },
                lineCap: PNProps.string(PNProps.value(merged, "stroke_linecap")),
                lineJoin: PNProps.string(PNProps.value(merged, "stroke_linejoin")),
                fillRule: PNProps.string(PNProps.value(merged, "fill_rule"))
            )
            svg.currentColor = PNColor.parse(PNProps.value(merged, "color"))
            redraw = true
        }
        if redraw { svg.setNeedsDisplay() }
        PNViewStyler.applyCommon(svg, props.values)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        guard let svg = view as? PNSvgView else { return .zero }
        var size = svg.viewBox.size
        if size.width <= 0 || size.height <= 0 { size = CGSize(width: 24, height: 24) }
        if maxW.isFinite, maxW > 0, size.width > maxW {
            size = CGSize(width: maxW, height: size.height * maxW / size.width)
        }
        if maxH.isFinite, maxH > 0, size.height > maxH {
            size = CGSize(width: size.width * maxH / size.height, height: maxH)
        }
        return size
    }
}

/// Root paint defaults applied to shapes that leave an attribute unset.
public struct PNSvgPaint {
    public var fill: String?
    public var stroke: String?
    public var strokeWidth: CGFloat?
    public var lineCap: String?
    public var lineJoin: String?
    public var fillRule: String?

    public init(fill: String? = nil, stroke: String? = nil, strokeWidth: CGFloat? = nil, lineCap: String? = nil, lineJoin: String? = nil, fillRule: String? = nil) {
        self.fill = fill
        self.stroke = stroke
        self.strokeWidth = strokeWidth
        self.lineCap = lineCap
        self.lineJoin = lineJoin
        self.fillRule = fillRule
    }
}

/// The drawing surface behind `Svg` (also used to rasterize tab bar icons).
public final class PNSvgView: UIView {
    public var shapes: [PNSvgShape] = [] { didSet { setNeedsDisplay() } }
    public var viewBox = CGRect(x: 0, y: 0, width: 24, height: 24) { didSet { setNeedsDisplay() } }
    public var preserveAspectRatio = "meet" { didSet { setNeedsDisplay() } }
    public var rootPaint = PNSvgPaint() { didSet { setNeedsDisplay() } }
    /// What `currentColor` resolves to; nil falls back to the label color.
    public var currentColor: UIColor? { didSet { setNeedsDisplay() } }

    public override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        backgroundColor = .clear
        contentMode = .redraw
    }

    public required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    public override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if traitCollection.hasDifferentColorAppearance(comparedTo: previousTraitCollection) { setNeedsDisplay() }
    }

    public override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        PNSvgRenderer.draw(shapes, viewBox: viewBox, preserveAspectRatio: preserveAspectRatio, root: rootPaint,
            currentColor: currentColor ?? .label, in: context, bounds: bounds)
    }

    /// Parse `"minx miny width height"` (commas allowed); nil when malformed.
    public static func parseViewBox(_ text: String?) -> CGRect? {
        guard let text = text else { return nil }
        let parts = text.split(whereSeparator: { $0 == " " || $0 == "," || $0 == "\n" || $0 == "\t" }).compactMap { Double($0) }
        guard parts.count == 4, parts[2] > 0, parts[3] > 0 else { return nil }
        return CGRect(x: parts[0], y: parts[1], width: parts[2], height: parts[3])
    }
}

/// Stateless Core Graphics renderer for flattened shapes.
public enum PNSvgRenderer {
    /// The transform from view box units to `bounds` for a `preserve_aspect_ratio` mode.
    public static func viewBoxTransform(_ viewBox: CGRect, bounds: CGRect, preserveAspectRatio: String) -> CGAffineTransform {
        guard viewBox.width > 0, viewBox.height > 0, bounds.width > 0, bounds.height > 0 else { return .identity }
        let sx = bounds.width / viewBox.width
        let sy = bounds.height / viewBox.height
        var scaleX = sx, scaleY = sy
        switch preserveAspectRatio {
        case "none": break
        case "slice": scaleX = max(sx, sy); scaleY = scaleX
        default: scaleX = min(sx, sy); scaleY = scaleX
        }
        let tx = bounds.minX + (bounds.width - viewBox.width * scaleX) / 2 - viewBox.minX * scaleX
        let ty = bounds.minY + (bounds.height - viewBox.height * scaleY) / 2 - viewBox.minY * scaleY
        return CGAffineTransform(a: scaleX, b: 0, c: 0, d: scaleY, tx: tx, ty: ty)
    }

    public static func draw(_ shapes: [PNSvgShape], viewBox: CGRect, preserveAspectRatio: String, root: PNSvgPaint,
                            currentColor: UIColor, in context: CGContext, bounds: CGRect) {
        let base = viewBoxTransform(viewBox, bounds: bounds, preserveAspectRatio: preserveAspectRatio)
        for shape in shapes {
            guard let path = geometry(shape) else { continue }
            var transform = base
            if let text = shape.transform, let local = PNSvgTransform.parse(text) {
                transform = local.concatenating(base)
            }
            context.saveGState()
            context.setAlpha(CGFloat(shape.opacity ?? 1))
            context.concatenate(transform)
            context.setLineWidth(CGFloat(shape.stroke_width ?? Double(root.strokeWidth ?? 1)))
            context.setLineCap(lineCap(shape.stroke_linecap?.rawValue ?? root.lineCap))
            context.setLineJoin(lineJoin(shape.stroke_linejoin?.rawValue ?? root.lineJoin))
            if let dashes = shape.stroke_dasharray, !dashes.isEmpty {
                context.setLineDash(phase: 0, lengths: dashes.map { CGFloat($0) })
            }
            let fillSpec = shape.fill ?? root.fill ?? "#000000"
            if let fill = paint(fillSpec, currentColor: currentColor) {
                context.addPath(path)
                context.setFillColor(fill.withAlphaComponent(fill.cgColor.alpha * CGFloat(shape.fill_opacity ?? 1)).cgColor)
                let rule = shape.fill_rule?.rawValue ?? root.fillRule
                context.fillPath(using: rule == "evenodd" ? .evenOdd : .winding)
            }
            if let strokeSpec = shape.stroke ?? root.stroke, let stroke = paint(strokeSpec, currentColor: currentColor) {
                context.addPath(path)
                context.setStrokeColor(stroke.withAlphaComponent(stroke.cgColor.alpha * CGFloat(shape.stroke_opacity ?? 1)).cgColor)
                context.strokePath()
            }
            context.restoreGState()
        }
    }

    /// A color for a paint value; nil for `"none"` (and unparseable input).
    public static func paint(_ value: String, currentColor: UIColor) -> UIColor? {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        if trimmed.isEmpty || trimmed == "none" || trimmed == "transparent" { return nil }
        if trimmed == "currentColor" { return currentColor }
        return PNColor.parse(trimmed)
    }

    /// The `CGPath` for one shape record, in view box units.
    public static func geometry(_ shape: PNSvgShape) -> CGPath? {
        switch shape.kind {
        case .path:
            return shape.d.flatMap { PNSvgPathParser.parse($0) }
        case .circle:
            let r = CGFloat(shape.r ?? 0)
            return CGPath(ellipseIn: CGRect(x: CGFloat(shape.cx ?? 0) - r, y: CGFloat(shape.cy ?? 0) - r, width: r * 2, height: r * 2), transform: nil)
        case .ellipse:
            let rx = CGFloat(shape.rx ?? 0), ry = CGFloat(shape.ry ?? 0)
            return CGPath(ellipseIn: CGRect(x: CGFloat(shape.cx ?? 0) - rx, y: CGFloat(shape.cy ?? 0) - ry, width: rx * 2, height: ry * 2), transform: nil)
        case .rect:
            let rect = CGRect(x: CGFloat(shape.x ?? 0), y: CGFloat(shape.y ?? 0), width: CGFloat(shape.width ?? 0), height: CGFloat(shape.height ?? 0))
            var rx = CGFloat(shape.rx ?? shape.ry ?? 0)
            var ry = CGFloat(shape.ry ?? shape.rx ?? 0)
            rx = min(rx, rect.width / 2)
            ry = min(ry, rect.height / 2)
            if rx > 0 || ry > 0 {
                return CGPath(roundedRect: rect, cornerWidth: rx, cornerHeight: ry, transform: nil)
            }
            return CGPath(rect: rect, transform: nil)
        case .line:
            let path = CGMutablePath()
            path.move(to: CGPoint(x: CGFloat(shape.x1 ?? 0), y: CGFloat(shape.y1 ?? 0)))
            path.addLine(to: CGPoint(x: CGFloat(shape.x2 ?? 0), y: CGFloat(shape.y2 ?? 0)))
            return path
        case .polyline, .polygon:
            let numbers = PNSvgPathParser.numbers(in: shape.points ?? "")
            guard numbers.count >= 4 else { return nil }
            let path = CGMutablePath()
            path.move(to: CGPoint(x: numbers[0], y: numbers[1]))
            var index = 2
            while index + 1 < numbers.count {
                path.addLine(to: CGPoint(x: numbers[index], y: numbers[index + 1]))
                index += 2
            }
            if shape.kind == .polygon { path.closeSubpath() }
            return path
        }
    }

    static func lineCap(_ value: String?) -> CGLineCap {
        switch value {
        case "round": return .round
        case "square": return .square
        default: return .butt
        }
    }

    static func lineJoin(_ value: String?) -> CGLineJoin {
        switch value {
        case "round": return .round
        case "bevel": return .bevel
        default: return .miter
        }
    }

    /// Rasterize shapes into a template image of `size` points (tab bar icons).
    public static func image(_ shapes: [PNSvgShape], viewBox: CGRect, size: CGSize, root: PNSvgPaint) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: size)
        let image = renderer.image { context in
            draw(shapes, viewBox: viewBox, preserveAspectRatio: "meet", root: root, currentColor: .black,
                 in: context.cgContext, bounds: CGRect(origin: .zero, size: size))
        }
        return image.withRenderingMode(.alwaysTemplate)
    }
}

/// Parser for SVG `transform` attribute lists.
public enum PNSvgTransform {
    /// Parse `translate(...) rotate(...) ...` into one affine transform (nil when malformed).
    public static func parse(_ text: String) -> CGAffineTransform? {
        var result = CGAffineTransform.identity
        var scanner = text[...]
        var any = false
        while let open = scanner.firstIndex(of: "(") {
            let name = scanner[..<open].trimmingCharacters(in: CharacterSet(charactersIn: " ,\n\t"))
            guard let close = scanner[open...].firstIndex(of: ")") else { return nil }
            let args = PNSvgPathParser.numbers(in: String(scanner[scanner.index(after: open)..<close]))
            let component: CGAffineTransform
            switch name {
            case "matrix" where args.count == 6:
                component = CGAffineTransform(a: args[0], b: args[1], c: args[2], d: args[3], tx: args[4], ty: args[5])
            case "translate" where !args.isEmpty:
                component = CGAffineTransform(translationX: args[0], y: args.count > 1 ? args[1] : 0)
            case "scale" where !args.isEmpty:
                component = CGAffineTransform(scaleX: args[0], y: args.count > 1 ? args[1] : args[0])
            case "rotate" where !args.isEmpty:
                let angle = args[0] * .pi / 180
                if args.count >= 3 {
                    component = CGAffineTransform(translationX: args[1], y: args[2]).rotated(by: angle).translatedBy(x: -args[1], y: -args[2])
                } else {
                    component = CGAffineTransform(rotationAngle: angle)
                }
            case "skewX" where !args.isEmpty:
                component = CGAffineTransform(a: 1, b: 0, c: tan(args[0] * .pi / 180), d: 1, tx: 0, ty: 0)
            case "skewY" where !args.isEmpty:
                component = CGAffineTransform(a: 1, b: tan(args[0] * .pi / 180), c: 0, d: 1, tx: 0, ty: 0)
            default:
                return nil
            }
            // SVG applies transforms left to right: later components act first.
            result = component.concatenating(result)
            any = true
            scanner = scanner[scanner.index(after: close)...]
        }
        return any ? result : nil
    }
}

/// Parser for SVG path data (`M L H V C S Q T A Z`, absolute and relative).
public enum PNSvgPathParser {
    /// Parse `d` into a `CGPath`; nil when the data has no drawable commands.
    public static func parse(_ d: String) -> CGPath? {
        let path = CGMutablePath()
        var tokens = tokenize(d)[...]
        var current = CGPoint.zero
        var start = CGPoint.zero
        var lastControl: CGPoint?
        var lastCommand: Character = "M"
        var drew = false

        func finish() -> CGPath? {
            drew || !path.isEmpty ? path : nil
        }
        func number() -> CGFloat? {
            guard let token = tokens.first, case .number(let value) = token else { return nil }
            tokens.removeFirst()
            return value
        }
        func point(relative: Bool) -> CGPoint? {
            guard let x = number(), let y = number() else { return nil }
            return relative ? CGPoint(x: current.x + x, y: current.y + y) : CGPoint(x: x, y: y)
        }
        func reflect(_ point: CGPoint?) -> CGPoint {
            guard let point = point else { return current }
            return CGPoint(x: 2 * current.x - point.x, y: 2 * current.y - point.y)
        }

        while let token = tokens.first {
            var command: Character
            if case .command(let letter) = token {
                command = letter
                tokens.removeFirst()
            } else {
                // Implicit repetition: numbers after a command repeat it
                // (M becomes L, m becomes l).
                command = lastCommand
                if command == "M" { command = "L" }
                if command == "m" { command = "l" }
            }
            let relative = command.isLowercase
            let upper = Character(command.uppercased())
            var consumed = false
            switch upper {
            case "M":
                guard let target = point(relative: relative) else { return finish() }
                path.move(to: target)
                current = target
                start = target
                lastControl = nil
                consumed = true
            case "L":
                guard let target = point(relative: relative) else { return finish() }
                path.addLine(to: target)
                current = target
                lastControl = nil
                drew = true
                consumed = true
            case "H":
                guard let x = number() else { return finish() }
                current = CGPoint(x: relative ? current.x + x : x, y: current.y)
                path.addLine(to: current)
                lastControl = nil
                drew = true
                consumed = true
            case "V":
                guard let y = number() else { return finish() }
                current = CGPoint(x: current.x, y: relative ? current.y + y : y)
                path.addLine(to: current)
                lastControl = nil
                drew = true
                consumed = true
            case "C":
                guard let c1 = point(relative: relative), let c2 = point(relative: relative), let target = point(relative: relative) else { return finish() }
                path.addCurve(to: target, control1: c1, control2: c2)
                lastControl = c2
                current = target
                drew = true
                consumed = true
            case "S":
                let c1 = "CS".contains(lastCommand.uppercased()) ? reflect(lastControl) : current
                guard let c2 = point(relative: relative), let target = point(relative: relative) else { return finish() }
                path.addCurve(to: target, control1: c1, control2: c2)
                lastControl = c2
                current = target
                drew = true
                consumed = true
            case "Q":
                guard let control = point(relative: relative), let target = point(relative: relative) else { return finish() }
                path.addQuadCurve(to: target, control: control)
                lastControl = control
                current = target
                drew = true
                consumed = true
            case "T":
                let control = "QT".contains(lastCommand.uppercased()) ? reflect(lastControl) : current
                guard let target = point(relative: relative) else { return finish() }
                path.addQuadCurve(to: target, control: control)
                lastControl = control
                current = target
                drew = true
                consumed = true
            case "A":
                guard let rx = number(), let ry = number(), let rotation = number(),
                      let largeArc = number(), let sweep = number(), let target = point(relative: relative) else { return finish() }
                arc(path, from: current, to: target, rx: rx, ry: ry, rotation: rotation, largeArc: largeArc != 0, sweep: sweep != 0)
                current = target
                lastControl = nil
                drew = true
                consumed = true
            case "Z":
                path.closeSubpath()
                current = start
                lastControl = nil
                drew = true
                consumed = true
            default:
                return finish()
            }
            if !consumed { return finish() }
            lastCommand = command
            if upper == "Z", case .number? = tokens.first {
                // Numbers after Z start a new subpath from the close point.
                lastCommand = relative ? "l" : "L"
                path.move(to: current)
            }
        }
        return finish()
    }

    enum Token {
        case command(Character)
        case number(CGFloat)
    }

    /// Split path data into commands and numbers (handles `1-2`, `.5.5`, exponents, flags).
    static func tokenize(_ text: String) -> [Token] {
        var tokens: [Token] = []
        let scalars = Array(text.unicodeScalars)
        var index = 0
        // Inside an arc command the 4th and 5th of every 7 numbers are
        // single-digit flags that may be run together ("1 0 01 5 5").
        var arcMode = false
        var arcCount = 0
        while index < scalars.count {
            let scalar = scalars[index]
            if scalar == " " || scalar == "," || scalar == "\n" || scalar == "\t" || scalar == "\r" {
                index += 1
                continue
            }
            if CharacterSet.letters.contains(scalar), scalar != "e", scalar != "E" {
                let letter = Character(scalar)
                tokens.append(.command(letter))
                arcMode = letter == "A" || letter == "a"
                arcCount = 0
                index += 1
                continue
            }
            if arcMode, arcCount % 7 == 3 || arcCount % 7 == 4, scalar == "0" || scalar == "1" {
                tokens.append(.number(scalar == "1" ? 1 : 0))
                arcCount += 1
                index += 1
                continue
            }
            var end = index
            var sawDigit = false
            var sawDot = false
            var sawExponent = false
            if scalars[end] == "-" || scalars[end] == "+" { end += 1 }
            while end < scalars.count {
                let c = scalars[end]
                if CharacterSet.decimalDigits.contains(c) {
                    sawDigit = true
                } else if c == "." && !sawDot && !sawExponent {
                    sawDot = true
                } else if (c == "e" || c == "E") && sawDigit && !sawExponent {
                    sawExponent = true
                    if end + 1 < scalars.count, scalars[end + 1] == "-" || scalars[end + 1] == "+" { end += 1 }
                } else {
                    break
                }
                end += 1
            }
            guard sawDigit, let value = Double(String(String.UnicodeScalarView(scalars[index..<end]))) else {
                index += 1
                continue
            }
            tokens.append(.number(CGFloat(value)))
            index = end
            if arcMode { arcCount += 1 }
        }
        return tokens
    }

    /// Every number in a `points` list or transform argument list.
    public static func numbers(in text: String) -> [CGFloat] {
        tokenize(text).compactMap { if case .number(let value) = $0 { return value } else { return nil } }
    }

    /// Append an SVG elliptical arc as cubic Bézier segments (SVG implementation notes, F.6.5).
    static func arc(_ path: CGMutablePath, from p1: CGPoint, to p2: CGPoint, rx: CGFloat, ry: CGFloat, rotation: CGFloat, largeArc: Bool, sweep: Bool) {
        if p1 == p2 { return }
        var rx = abs(rx), ry = abs(ry)
        if rx == 0 || ry == 0 {
            path.addLine(to: p2)
            return
        }
        let phi = rotation * .pi / 180
        let cosPhi = cos(phi), sinPhi = sin(phi)
        let dx = (p1.x - p2.x) / 2, dy = (p1.y - p2.y) / 2
        let x1p = cosPhi * dx + sinPhi * dy
        let y1p = -sinPhi * dx + cosPhi * dy
        let lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
        if lambda > 1 {
            rx *= sqrt(lambda)
            ry *= sqrt(lambda)
        }
        let numerator = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
        let denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
        var coefficient = denominator == 0 ? 0 : sqrt(max(0, numerator / denominator))
        if largeArc == sweep { coefficient = -coefficient }
        let cxp = coefficient * rx * y1p / ry
        let cyp = -coefficient * ry * x1p / rx
        let cx = cosPhi * cxp - sinPhi * cyp + (p1.x + p2.x) / 2
        let cy = sinPhi * cxp + cosPhi * cyp + (p1.y + p2.y) / 2

        func angle(_ ux: CGFloat, _ uy: CGFloat, _ vx: CGFloat, _ vy: CGFloat) -> CGFloat {
            let dot = ux * vx + uy * vy
            let length = sqrt(ux * ux + uy * uy) * sqrt(vx * vx + vy * vy)
            var value = acos(max(-1, min(1, dot / length)))
            if ux * vy - uy * vx < 0 { value = -value }
            return value
        }
        let theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
        var delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
        if !sweep && delta > 0 { delta -= 2 * .pi }
        if sweep && delta < 0 { delta += 2 * .pi }

        let segments = Int(ceil(abs(delta) / (.pi / 2)))
        let step = delta / CGFloat(segments)
        let t = 4 / 3 * tan(step / 4)
        var angleStart = theta1
        for _ in 0..<segments {
            let angleEnd = angleStart + step
            let cos1 = cos(angleStart), sin1 = sin(angleStart)
            let cos2 = cos(angleEnd), sin2 = sin(angleEnd)
            let e1 = CGPoint(x: cos1 - t * sin1, y: sin1 + t * cos1)
            let e2 = CGPoint(x: cos2 + t * sin2, y: sin2 - t * cos2)
            let end = CGPoint(x: cos2, y: sin2)
            func map(_ p: CGPoint) -> CGPoint {
                let x = rx * p.x, y = ry * p.y
                return CGPoint(x: cosPhi * x - sinPhi * y + cx, y: sinPhi * x + cosPhi * y + cy)
            }
            path.addCurve(to: map(end), control1: map(e1), control2: map(e2))
            angleStart = angleEnd
        }
        // Land exactly on the end point regardless of rounding.
        path.addLine(to: p2)
    }
}
