import UIKit

/// `LinearGradient`: a flex container whose backing layer is a `CAGradientLayer`.
public final class PNLinearGradientManager: PNTypedComponentManager<LinearGradientProps> {
    public init() { super.init(LinearGradientProps.self) }

    public override func makeView(props: [String: Any]) -> UIView {
        PNGradientView(frame: .zero)
    }

    public override func applyTyped(view: UIView, props: LinearGradientProps, initial: Bool) {
        guard let gradient = view as? PNGradientView else { return }
        if props.has_colors || props.has_locations || props.has_start_point || props.has_end_point {
            let merged = mergedProps(gradient)
            let colors = ((PNProps.value(merged, "colors") as? [Any]) ?? []).compactMap { PNColor.parse($0) }
            gradient.configure(
                colors: colors,
                locations: (PNProps.value(merged, "locations") as? [Any])?.compactMap { PNProps.double($0) },
                start: Self.point(PNProps.value(merged, "start_point"), fallback: CGPoint(x: 0, y: 0)),
                end: Self.point(PNProps.value(merged, "end_point"), fallback: CGPoint(x: 0, y: 1))
            )
        }
        PNViewStyler.applyCommon(gradient, props.values)
    }

    static func point(_ value: Any?, fallback: CGPoint) -> CGPoint {
        guard let list = value as? [Any], list.count == 2,
              let x = PNProps.double(list[0]), let y = PNProps.double(list[1]) else { return fallback }
        return CGPoint(x: x, y: y)
    }
}

/// Container view backed by a gradient layer (so corner radius and
/// frame changes apply to the gradient for free).
public final class PNGradientView: PNContainerView {
    public override class var layerClass: AnyClass { CAGradientLayer.self }

    public var gradientLayer: CAGradientLayer { layer as! CAGradientLayer }

    public override init(frame: CGRect) {
        super.init(frame: frame)
        gradientLayer.type = .axial
    }

    public required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    public func configure(colors: [UIColor], locations: [Double]?, start: CGPoint, end: CGPoint) {
        // Resolve dynamic colors for the current appearance; refreshed on trait changes.
        gradientLayer.colors = colors.map { $0.resolvedColor(with: traitCollection).cgColor }
        if let locations = locations, locations.count == colors.count {
            gradientLayer.locations = locations.map { NSNumber(value: $0) }
        } else {
            gradientLayer.locations = nil
        }
        gradientLayer.startPoint = start
        gradientLayer.endPoint = end
        storedColors = colors
    }

    private var storedColors: [UIColor] = []

    public override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if traitCollection.hasDifferentColorAppearance(comparedTo: previousTraitCollection) {
            gradientLayer.colors = storedColors.map { $0.resolvedColor(with: traitCollection).cgColor }
        }
    }
}

/// `BlurView`: a `UIVisualEffectView` container. Children go into
/// `contentView`; `intensity` pauses a property animator part way into
/// the effect so the blur can be dialed down.
public final class PNBlurViewManager: PNTypedComponentManager<BlurViewProps> {
    public init() { super.init(BlurViewProps.self) }

    public override func makeView(props: [String: Any]) -> UIView {
        PNBlurView(frame: .zero)
    }

    public override func applyTyped(view: UIView, props: BlurViewProps, initial: Bool) {
        guard let blur = view as? PNBlurView else { return }
        if props.has_blur_type || props.has_intensity || initial {
            let merged = mergedProps(blur)
            let type = PNProps.string(PNProps.value(merged, "blur_type")) ?? "regular"
            let intensity = PNProps.double(PNProps.value(merged, "intensity")) ?? 100
            blur.configure(style: Self.style(type), intensity: CGFloat(max(0, min(100, intensity)) / 100))
        }
        // Visual props (radius, borders, shadows) apply to the outer view;
        // a background color would hide the blur, so it is dropped.
        var values = props.values
        values.removeValue(forKey: "background_color")
        PNViewStyler.applyCommon(blur, values)
    }

    public override func childContainer(for view: UIView) -> UIView {
        (view as? PNBlurView)?.effectView.contentView ?? view
    }

    static func style(_ name: String) -> UIBlurEffect.Style {
        switch name {
        case "light": return .light
        case "dark": return .dark
        case "extra_light": return .extraLight
        case "prominent": return .prominent
        case "system_thin_material": return .systemThinMaterial
        case "system_material": return .systemMaterial
        case "system_thick_material": return .systemThickMaterial
        case "system_chrome_material": return .systemChromeMaterial
        default: return .regular
        }
    }
}

/// Hit-test-aware wrapper around a `UIVisualEffectView`.
public final class PNBlurView: PNContainerView {
    public let effectView = UIVisualEffectView(effect: nil)
    private var animator: UIViewPropertyAnimator?

    public override init(frame: CGRect) {
        super.init(frame: frame)
        effectView.frame = bounds
        effectView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        addSubview(effectView)
        clipsToBounds = true
    }

    public required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    public func configure(style: UIBlurEffect.Style, intensity: CGFloat) {
        animator?.stopAnimation(true)
        animator?.finishAnimation(at: .current)
        animator = nil
        effectView.effect = nil
        if intensity >= 0.999 {
            effectView.effect = UIBlurEffect(style: style)
            return
        }
        if intensity <= 0.001 { return }
        let animator = UIViewPropertyAnimator(duration: 1, curve: .linear) { [effectView] in
            effectView.effect = UIBlurEffect(style: style)
        }
        animator.pausesOnCompletion = true
        animator.fractionComplete = intensity
        self.animator = animator
    }

    public override func layoutSubviews() {
        super.layoutSubviews()
        effectView.frame = bounds
        effectView.layer.cornerRadius = layer.cornerRadius
        effectView.clipsToBounds = layer.cornerRadius > 0
    }

    deinit {
        animator?.stopAnimation(true)
    }
}
