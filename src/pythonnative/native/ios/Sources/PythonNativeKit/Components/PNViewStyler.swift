import UIKit

/// Applies the visual props every element type shares.
///
/// `applyCommon` is the full container set (background, overflow,
/// display, opacity, z-index, pointer events, borders, shadows,
/// transform, accessibility). `applyDecoration` is the subset leaf
/// controls use (borders, shadow, transform, accessibility, opacity),
/// mirroring the per-handler behavior of the original iOS backend.
public enum PNViewStyler {
    static let cornerRadiusKeys = [
        "border_top_left_radius", "border_top_right_radius",
        "border_bottom_left_radius", "border_bottom_right_radius",
    ]
    static let sideWidthKeys = ["border_left_width", "border_top_width", "border_right_width", "border_bottom_width"]
    static let sideColorKeys = ["border_left_color", "border_top_color", "border_right_color", "border_bottom_color"]
    static let shadowKeys = ["shadow_color", "shadow_offset", "shadow_opacity", "shadow_radius", "elevation"]
    static let maskedCornerBits: [CACornerMask] = [
        .layerMinXMinYCorner, .layerMaxXMinYCorner, .layerMinXMaxYCorner, .layerMaxXMaxYCorner,
    ]
    static let allCorners: CACornerMask = [
        .layerMinXMinYCorner, .layerMaxXMinYCorner, .layerMinXMaxYCorner, .layerMaxXMaxYCorner,
    ]

    // MARK: - Entry points

    /// Apply every shared visual prop present in `props`.
    public static func applyCommon(_ view: UIView, _ props: [String: Any]) {
        if PNProps.has(props, "background_color") {
            view.backgroundColor = PNColor.parse(PNProps.value(props, "background_color"))
        }
        if PNProps.has(props, "overflow") {
            view.clipsToBounds = PNProps.string(PNProps.value(props, "overflow")) == "hidden"
        }
        if PNProps.has(props, "display") {
            view.isHidden = PNProps.string(PNProps.value(props, "display")) == "none"
        }
        if PNProps.has(props, "opacity") {
            view.alpha = CGFloat(PNProps.double(PNProps.value(props, "opacity")) ?? 1)
        }
        if PNProps.has(props, "z_index") {
            view.layer.zPosition = CGFloat(PNProps.double(PNProps.value(props, "z_index")) ?? 0)
        }
        if PNProps.has(props, "pointer_events") || PNProps.has(props, "hit_slop") {
            applyInteraction(view, props)
        }
        applyBorder(view, props)
        applySideBorders(view, props)
        let merged = PNViewState.existing(for: view)?.props ?? props
        let cornerKeysActive = cornerRadiusKeys.contains { PNProps.value(merged, $0) != nil }
        if cornerRadiusKeys.contains(where: { PNProps.has(props, $0) }) || (PNProps.has(props, "border_radius") && cornerKeysActive) {
            applyCornerRadii(view, merged)
        }
        applyShadow(view, props)
        if PNProps.has(props, "transform") {
            PNTransform.apply(view, spec: PNProps.value(props, "transform"))
        }
        applyAccessibility(view, props)
    }

    /// The leaf-control subset: border, shadow, transform, accessibility, opacity.
    public static func applyDecoration(_ view: UIView, _ props: [String: Any]) {
        applyBorder(view, props)
        applyShadow(view, props)
        if PNProps.has(props, "transform") {
            PNTransform.apply(view, spec: PNProps.value(props, "transform"))
        }
        applyAccessibility(view, props)
        if PNProps.has(props, "opacity") {
            view.alpha = CGFloat(PNProps.double(PNProps.value(props, "opacity")) ?? 1)
        }
    }

    /// Re-run the bounds-dependent parts of styling after a frame change.
    public static func syncFrameDependentStyles(_ view: UIView, size: CGSize) {
        guard let state = PNViewState.existing(for: view) else { return }
        let maxRadius = max(0, min(size.width, size.height) / 2)
        if let requested = state.requestedCornerRadius, maxRadius > 0 {
            view.layer.cornerRadius = min(requested, maxRadius)
        } else if state.requestedCornerRadius == nil, view.layer.cornerRadius > 0, maxRadius > 0 {
            view.layer.cornerRadius = min(view.layer.cornerRadius, maxRadius)
        }
        updateCornerMask(view, state: state, size: size)
        updateSideBorderLayers(view, state: state, size: size)
        updateBorderStyleLayer(view, state: state, size: size)
    }

    // MARK: - Borders

    static func applyBorder(_ view: UIView, _ props: [String: Any]) {
        let layer = view.layer
        if let radius = PNProps.double(PNProps.value(props, "border_radius")) {
            let requested = CGFloat(max(0, radius))
            PNViewState.existing(for: view)?.requestedCornerRadius = requested
            let size = view.bounds.size
            var value = requested
            if size.width > 0, size.height > 0 {
                value = min(requested, min(size.width, size.height) / 2)
            }
            layer.cornerRadius = value
            // Rounded corners clip implicitly (the React Native default).
            layer.masksToBounds = true
        } else if PNProps.has(props, "border_radius") {
            PNViewState.existing(for: view)?.requestedCornerRadius = nil
            layer.cornerRadius = 0
        }
        if let width = PNProps.double(PNProps.value(props, "border_width")) {
            layer.borderWidth = CGFloat(width)
        } else if PNProps.has(props, "border_width") {
            layer.borderWidth = 0
        }
        if PNProps.has(props, "border_color") {
            layer.borderColor = PNColor.parse(PNProps.value(props, "border_color"))?.cgColor
        }
        if PNProps.has(props, "border_style") || PNProps.has(props, "border_width") || PNProps.has(props, "border_color")
            || PNProps.has(props, "border_radius") {
            applyBorderStyle(view, props)
        }
    }

    // MARK: - Border style (dashed / dotted)

    /// `border_style`: `"solid"` (default) uses `layer.borderWidth`;
    /// `"dashed"` and `"dotted"` draw the uniform border with a
    /// `CAShapeLayer` whose `lineDashPattern` follows the border width
    /// (dashes are three widths long, dots one width; gaps match). The
    /// layer is refit on every frame change. Per-side widths and colors
    /// keep drawing solid.
    static func applyBorderStyle(_ view: UIView, _ props: [String: Any]) {
        guard let state = PNViewState.existing(for: view) else { return }
        let merged = state.props
        let style = PNProps.string(PNProps.value(merged, "border_style"))?.lowercased()
        let width = CGFloat(PNProps.double(PNProps.value(merged, "border_width")) ?? 0)
        guard let style = style, style == "dashed" || style == "dotted", width > 0 else {
            if state.borderStyle != nil {
                state.borderStyle = nil
                state.borderStyleLayer?.removeFromSuperlayer()
                state.borderStyleLayer = nil
                if state.sideBorderWidths == nil { view.layer.borderWidth = width }
            }
            return
        }
        state.borderStyle = style
        view.layer.borderWidth = 0
        let shape = state.borderStyleLayer ?? {
            let created = CAShapeLayer()
            created.fillColor = nil
            view.layer.addSublayer(created)
            state.borderStyleLayer = created
            return created
        }()
        shape.strokeColor = (PNColor.parse(PNProps.value(merged, "border_color")) ?? .black).cgColor
        shape.lineWidth = width
        shape.lineCap = .butt
        shape.lineDashPattern = style == "dashed"
            ? [NSNumber(value: Double(width * 3)), NSNumber(value: Double(width * 3))]
            : [NSNumber(value: Double(width)), NSNumber(value: Double(width))]
        let size = view.bounds.size
        if size.width > 0, size.height > 0 { updateBorderStyleLayer(view, state: state, size: size) }
    }

    static func updateBorderStyleLayer(_ view: UIView, state: PNViewState, size: CGSize) {
        guard let shape = state.borderStyleLayer, size.width > 0, size.height > 0 else { return }
        let width = shape.lineWidth
        shape.frame = CGRect(origin: .zero, size: size)
        let rect = CGRect(origin: .zero, size: size).insetBy(dx: width / 2, dy: width / 2)
        let radius = max(0, view.layer.cornerRadius - width / 2)
        shape.path = UIBezierPath(roundedRect: rect, cornerRadius: radius).cgPath
        // Keep the stroke above the side-border layers and any children.
        shape.zPosition = 1
    }

    static func applySideBorders(_ view: UIView, _ props: [String: Any]) {
        guard let state = PNViewState.existing(for: view),
              (sideWidthKeys + sideColorKeys + ["border_width", "border_color"]).contains(where: { PNProps.has(props, $0) }) else { return }
        let merged = state.props
        if !(sideWidthKeys + sideColorKeys).contains(where: { PNProps.value(merged, $0) != nil }) {
            state.sideBorderWidths = nil
            state.sideBorderColors = nil
            for index in 0..<4 { state.sideBorderLayers[index]?.removeFromSuperlayer(); state.sideBorderLayers[index] = nil }
            // A dashed / dotted border is stroked by its shape layer instead.
            view.layer.borderWidth = state.borderStyle == nil ? CGFloat(PNProps.double(PNProps.value(merged, "border_width")) ?? 0) : 0
            return
        }
        let baseWidth = CGFloat(PNProps.double(PNProps.value(merged, "border_width")) ?? 0)
        let baseColor = PNColor.parse(PNProps.value(merged, "border_color")) ?? .black
        state.sideBorderWidths = sideWidthKeys.map { key in
            CGFloat(PNProps.double(PNProps.value(merged, key)) ?? Double(baseWidth))
        }
        state.sideBorderColors = sideColorKeys.map { key in
            PNColor.parse(PNProps.value(merged, key)) ?? baseColor
        }
        view.layer.borderWidth = 0
        let size = view.bounds.size
        if size.width > 0, size.height > 0 {
            updateSideBorderLayers(view, state: state, size: size)
        }
    }

    static func updateSideBorderLayers(_ view: UIView, state: PNViewState, size: CGSize) {
        guard let widths = state.sideBorderWidths, let colors = state.sideBorderColors else { return }
        let frames = [
            CGRect(x: 0, y: 0, width: widths[0], height: size.height),
            CGRect(x: 0, y: 0, width: size.width, height: widths[1]),
            CGRect(x: size.width - widths[2], y: 0, width: widths[2], height: size.height),
            CGRect(x: 0, y: size.height - widths[3], width: size.width, height: widths[3]),
        ]
        for i in 0..<4 {
            if widths[i] <= 0 {
                state.sideBorderLayers[i]?.removeFromSuperlayer()
                state.sideBorderLayers[i] = nil
                continue
            }
            let layer = state.sideBorderLayers[i] ?? {
                let created = CALayer()
                view.layer.addSublayer(created)
                state.sideBorderLayers[i] = created
                return created
            }()
            layer.backgroundColor = colors[i].cgColor
            layer.frame = frames[i]
        }
    }

    // MARK: - Per-corner radii

    static func applyCornerRadii(_ view: UIView, _ merged: [String: Any]) {
        guard let state = PNViewState.existing(for: view) else { return }
        let anyCorner = cornerRadiusKeys.contains { PNProps.value(merged, $0) != nil }
        if !anyCorner {
            if state.cornerRadii != nil {
                state.cornerRadii = nil
                view.layer.mask = nil
                view.layer.maskedCorners = allCorners
                applyBorder(view, merged)
            }
            return
        }
        let base = CGFloat(max(0, PNProps.double(PNProps.value(merged, "border_radius")) ?? 0))
        let radii: [CGFloat] = cornerRadiusKeys.map { key in
            guard let value = PNProps.double(PNProps.value(merged, key)), value.isFinite else { return base }
            return CGFloat(max(0, value))
        }
        let distinct = Set(radii.filter { $0 > 0 })
        if distinct.count <= 1 {
            state.cornerRadii = nil
            let value = distinct.first ?? 0
            var mask: CACornerMask = []
            for (bit, r) in zip(maskedCornerBits, radii) where r > 0 {
                mask.insert(bit)
            }
            view.layer.mask = nil
            view.layer.cornerRadius = value
            view.layer.maskedCorners = mask.isEmpty ? allCorners : mask
            view.layer.masksToBounds = true
            state.requestedCornerRadius = value
            return
        }
        state.requestedCornerRadius = nil
        state.cornerRadii = radii
        view.layer.cornerRadius = 0
        view.layer.maskedCorners = allCorners
        let size = view.bounds.size
        if size.width > 0, size.height > 0 {
            updateCornerMask(view, state: state, size: size)
        }
    }

    static func updateCornerMask(_ view: UIView, state: PNViewState, size: CGSize) {
        guard let radii = state.cornerRadii, size.width > 0, size.height > 0 else { return }
        var scale: CGFloat = 1
        let (tl0, tr0, bl0, br0) = (radii[0], radii[1], radii[2], radii[3])
        for (sum, extent) in [(tl0 + tr0, size.width), (bl0 + br0, size.width), (tl0 + bl0, size.height), (tr0 + br0, size.height)]
        where sum > extent && extent > 0 {
            scale = min(scale, extent / sum)
        }
        let (tl, tr, bl, br) = (tl0 * scale, tr0 * scale, bl0 * scale, br0 * scale)
        let w = size.width, h = size.height
        let path = UIBezierPath()
        let halfPi = CGFloat.pi / 2
        path.move(to: CGPoint(x: tl, y: 0))
        path.addLine(to: CGPoint(x: w - tr, y: 0))
        if tr > 0 { path.addArc(withCenter: CGPoint(x: w - tr, y: tr), radius: tr, startAngle: -halfPi, endAngle: 0, clockwise: true) }
        path.addLine(to: CGPoint(x: w, y: h - br))
        if br > 0 { path.addArc(withCenter: CGPoint(x: w - br, y: h - br), radius: br, startAngle: 0, endAngle: halfPi, clockwise: true) }
        path.addLine(to: CGPoint(x: bl, y: h))
        if bl > 0 { path.addArc(withCenter: CGPoint(x: bl, y: h - bl), radius: bl, startAngle: halfPi, endAngle: .pi, clockwise: true) }
        path.addLine(to: CGPoint(x: 0, y: tl))
        if tl > 0 { path.addArc(withCenter: CGPoint(x: tl, y: tl), radius: tl, startAngle: .pi, endAngle: .pi + halfPi, clockwise: true) }
        path.close()
        let shape = CAShapeLayer()
        shape.frame = CGRect(origin: .zero, size: size)
        shape.path = path.cgPath
        view.layer.mask = shape
    }

    // MARK: - Shadow

    static func applyShadow(_ view: UIView, _ props: [String: Any]) {
        let layer = view.layer
        let hasShadow = shadowKeys.contains { PNProps.value(props, $0) != nil }
        if hasShadow, PNProps.string(PNProps.value(props, "overflow")) != "hidden" {
            layer.masksToBounds = false
            view.clipsToBounds = false
        }
        if PNProps.has(props, "shadow_color") { layer.shadowColor = PNColor.parse(PNProps.value(props, "shadow_color"))?.cgColor }
        if PNProps.has(props, "shadow_opacity") { layer.shadowOpacity = Float(PNProps.double(PNProps.value(props, "shadow_opacity")) ?? 0) }
        if PNProps.has(props, "shadow_radius") { layer.shadowRadius = CGFloat(PNProps.double(PNProps.value(props, "shadow_radius")) ?? 3) }
        if PNProps.has(props, "shadow_offset") {
            let (dx, dy) = shadowOffset(PNProps.value(props, "shadow_offset"))
            layer.shadowOffset = CGSize(width: dx, height: dy)
        }
    }

    /// Coerce a `shadow_offset` / `text_shadow_offset` value to `(dx, dy)`.
    public static func shadowOffset(_ value: Any?) -> (CGFloat, CGFloat) {
        if let dict = value as? [String: Any] {
            return (CGFloat(PNProps.double(dict["width"]) ?? 0), CGFloat(PNProps.double(dict["height"]) ?? 0))
        }
        if let list = value as? [Any], list.count >= 2 {
            return (CGFloat(PNProps.double(list[0]) ?? 0), CGFloat(PNProps.double(list[1]) ?? 0))
        }
        return (0, 0)
    }

    // MARK: - Interaction

    static func applyInteraction(_ view: UIView, _ props: [String: Any]) {
        guard let container = view as? PNContainerView else {
            PNLog.once(PNLog.components, key: "interaction:\(PNViewState.existing(for: view)?.tag ?? 0)",
                       "pointer_events / hit_slop only work on container elements; ignored")
            return
        }
        if PNProps.has(props, "pointer_events") {
            let mode = PNProps.string(PNProps.value(props, "pointer_events"))
            container.pointerEvents = ["none", "box_none", "box_only"].contains(mode ?? "") ? mode : nil
        }
        if PNProps.has(props, "hit_slop") {
            container.hitSlop = hitSlop(PNProps.value(props, "hit_slop"))
        }
    }

    /// Normalize a `hit_slop` prop into edge insets.
    public static func hitSlop(_ value: Any?) -> UIEdgeInsets {
        if let dict = value as? [String: Any] {
            return UIEdgeInsets(
                top: CGFloat(PNProps.double(dict["top"]) ?? 0), left: CGFloat(PNProps.double(dict["left"]) ?? 0),
                bottom: CGFloat(PNProps.double(dict["bottom"]) ?? 0), right: CGFloat(PNProps.double(dict["right"]) ?? 0)
            )
        }
        if let uniform = PNProps.double(value) {
            let v = CGFloat(uniform)
            return UIEdgeInsets(top: v, left: v, bottom: v, right: v)
        }
        return .zero
    }

    // MARK: - Accessibility

    static let traitByRole: [String: UIAccessibilityTraits] = [
        "button": .button, "link": .link, "image": .image, "search": .searchField,
        "keyboard_key": .keyboardKey, "static_text": .staticText, "summary_element": .summaryElement,
        "adjustable": .adjustable, "header": .header, "selected": .selected, "checkbox": .button, "none": [],
    ]

    static let accessibilityValueKeys = ["accessibility_value", "accessibility_role", "accessibility_state"]

    static func applyAccessibility(_ view: UIView, _ props: [String: Any]) {
        if PNProps.has(props, "accessible") {
            view.isAccessibilityElement = PNProps.bool(PNProps.value(props, "accessible")) ?? false
        }
        if PNProps.has(props, "accessibility_label") {
            view.accessibilityLabel = PNProps.string(PNProps.value(props, "accessibility_label")) ?? ""
        }
        if PNProps.has(props, "accessibility_hint") {
            view.accessibilityHint = PNProps.string(PNProps.value(props, "accessibility_hint")) ?? ""
        }
        if PNProps.has(props, "test_id") {
            view.accessibilityIdentifier = PNProps.string(PNProps.value(props, "test_id"))
        }
        if PNProps.has(props, "accessibility_actions") {
            applyAccessibilityActions(view, PNProps.value(props, "accessibility_actions"))
        }
        if PNProps.has(props, "important_for_accessibility") {
            applyImportance(view, PNProps.string(PNProps.value(props, "important_for_accessibility")))
        }
        guard accessibilityValueKeys.contains(where: { PNProps.has(props, $0) }) else { return }
        let merged = PNViewState.existing(for: view)?.props ?? props
        let role = PNProps.string(PNProps.value(merged, "accessibility_role"))
        let state = PNProps.dict(PNProps.value(merged, "accessibility_state"))
        var traits: UIAccessibilityTraits = []
        var value = accessibilityValue(PNProps.value(merged, "accessibility_value"))
        if let role = role {
            traits.formUnion(traitByRole[role.lowercased()] ?? [])
        }
        if let state = state {
            if PNProps.bool(state["selected"]) == true || PNProps.bool(state["checked"]) == true {
                traits.insert(.selected)
            }
            if PNProps.bool(state["disabled"]) == true { traits.insert(.notEnabled) }
            if PNProps.bool(state["busy"]) == true { traits.insert(.updatesFrequently) }
            if value == nil, let expanded = PNProps.bool(state["expanded"]) {
                value = expanded ? "expanded" : "collapsed"
            }
        }
        view.accessibilityValue = value
        view.accessibilityTraits = traits
    }

    /// `accessibility_value`: a string, or `{"min", "max", "now", "text"}`
    /// where `text` wins, then a `min`/`max`/`now` triple reads as a
    /// percentage (React Native's iOS behavior), then `now` alone.
    public static func accessibilityValue(_ raw: Any?) -> String? {
        guard let raw = raw, !(raw is NSNull) else { return nil }
        if let text = raw as? String { return text }
        if let number = raw as? NSNumber { return number.stringValue }
        guard let dict = raw as? [String: Any] else { return nil }
        if let text = PNProps.string(dict["text"]), !text.isEmpty { return text }
        let now = PNProps.double(dict["now"])
        if let now = now, let min = PNProps.double(dict["min"]), let max = PNProps.double(dict["max"]), max > min {
            let percent = (now - min) / (max - min) * 100
            return "\(Int(percent.rounded()))%"
        }
        if let now = now {
            return now.rounded() == now ? String(Int(now)) : String(now)
        }
        return nil
    }

    /// `accessibility_actions`: `[{"name", "label"?}]` become custom
    /// actions that emit `on_accessibility_action(name)`.
    static func applyAccessibilityActions(_ view: UIView, _ raw: Any?) {
        let specs = ((raw as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
        guard !specs.isEmpty else {
            view.accessibilityCustomActions = nil
            return
        }
        view.accessibilityCustomActions = specs.compactMap { spec in
            guard let name = PNProps.string(spec["name"]), !name.isEmpty else { return nil }
            let label = PNProps.string(spec["label"]) ?? name
            return UIAccessibilityCustomAction(name: label) { [weak view] _ in
                guard let view = view else { return false }
                PNEvents.emitIfWired(view, "on_accessibility_action", [name])
                return true
            }
        }
    }

    /// `important_for_accessibility`: `"yes"` exposes the view,
    /// `"no"` hides it but keeps its descendants, `"no_hide_descendants"`
    /// hides the whole subtree, `"auto"` restores the `accessible` prop.
    static func applyImportance(_ view: UIView, _ mode: String?) {
        let merged = PNViewState.existing(for: view)?.props
        switch mode {
        case "yes":
            view.accessibilityElementsHidden = false
            view.isAccessibilityElement = true
        case "no":
            view.accessibilityElementsHidden = false
            view.isAccessibilityElement = false
        case "no_hide_descendants":
            view.accessibilityElementsHidden = true
            view.isAccessibilityElement = false
        default:
            view.accessibilityElementsHidden = false
            view.isAccessibilityElement = merged.flatMap { PNProps.bool(PNProps.value($0, "accessible")) } ?? false
        }
    }
}
