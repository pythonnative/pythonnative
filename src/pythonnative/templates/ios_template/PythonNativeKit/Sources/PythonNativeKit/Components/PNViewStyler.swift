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
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            view.backgroundColor = color
        }
        if PNProps.has(props, "overflow") {
            view.clipsToBounds = PNProps.string(PNProps.value(props, "overflow")) == "hidden"
        }
        if PNProps.has(props, "display") {
            view.isHidden = PNProps.string(PNProps.value(props, "display")) == "none"
        }
        if let opacity = PNProps.double(PNProps.value(props, "opacity")) {
            view.alpha = CGFloat(opacity)
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
        if let opacity = PNProps.double(PNProps.value(props, "opacity")) {
            view.alpha = CGFloat(opacity)
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
        if let color = PNColor.parse(PNProps.value(props, "border_color")) {
            layer.borderColor = color.cgColor
        }
    }

    static func applySideBorders(_ view: UIView, _ props: [String: Any]) {
        guard sideWidthKeys.contains(where: { PNProps.value(props, $0) != nil }),
              let state = PNViewState.existing(for: view)
        else { return }
        let merged = state.props
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
        if let color = PNColor.parse(PNProps.value(props, "shadow_color")) {
            layer.shadowColor = color.cgColor
        }
        if let opacity = PNProps.double(PNProps.value(props, "shadow_opacity")) {
            layer.shadowOpacity = Float(opacity)
        }
        if let radius = PNProps.double(PNProps.value(props, "shadow_radius")) {
            layer.shadowRadius = CGFloat(radius)
        }
        if let offset = PNProps.value(props, "shadow_offset") {
            let (dx, dy) = shadowOffset(offset)
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
        let role = PNProps.string(PNProps.value(props, "accessibility_role"))
        let state = PNProps.dict(PNProps.value(props, "accessibility_state"))
        if role == nil, state == nil { return }
        var traits: UIAccessibilityTraits = []
        if let role = role {
            traits.formUnion(traitByRole[role.lowercased()] ?? [])
        }
        if let state = state {
            if PNProps.bool(state["selected"]) == true || PNProps.bool(state["checked"]) == true {
                traits.insert(.selected)
            }
            if PNProps.bool(state["disabled"]) == true { traits.insert(.notEnabled) }
            if PNProps.bool(state["busy"]) == true { traits.insert(.updatesFrequently) }
            if let expanded = PNProps.bool(state["expanded"]) {
                view.accessibilityValue = expanded ? "expanded" : "collapsed"
            }
        }
        view.accessibilityTraits = traits
    }
}
