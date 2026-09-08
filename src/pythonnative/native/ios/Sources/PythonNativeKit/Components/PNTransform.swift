import UIKit

/// Builds `CGAffineTransform`s from the `transform` style prop.
///
/// The prop is a list of single-key dicts: `rotate` (degrees, or a
/// `"45deg"` / `"0.5rad"` string), `scale`, `scale_x`, `scale_y`,
/// `translate_x`, `translate_y`, `skew_x`, `skew_y` (degrees).
public enum PNTransform {
    /// Build a transform from a spec list (or single dict). `nil` is identity.
    public static func make(_ spec: Any?) -> CGAffineTransform {
        var transform = CGAffineTransform.identity
        guard let spec = spec, !(spec is NSNull) else { return transform }
        let entries: [Any] = (spec as? [Any]) ?? [spec]
        for entry in entries {
            guard let dict = entry as? [String: Any] else { continue }
            if let rotate = dict["rotate"] {
                transform = transform.rotated(by: angle(rotate))
            }
            if let scale = PNProps.double(dict["scale"]) {
                transform = transform.scaledBy(x: CGFloat(scale), y: CGFloat(scale))
            }
            if let sx = PNProps.double(dict["scale_x"]) {
                transform = transform.scaledBy(x: CGFloat(sx), y: 1)
            }
            if let sy = PNProps.double(dict["scale_y"]) {
                transform = transform.scaledBy(x: 1, y: CGFloat(sy))
            }
            if dict["translate_x"] != nil || dict["translate_y"] != nil {
                let tx = PNProps.double(dict["translate_x"]) ?? 0
                let ty = PNProps.double(dict["translate_y"]) ?? 0
                transform = transform.translatedBy(x: CGFloat(tx), y: CGFloat(ty))
            }
            if dict["skew_x"] != nil || dict["skew_y"] != nil {
                let skew = CGAffineTransform(
                    a: 1, b: tan(angle(dict["skew_y"] ?? 0)),
                    c: tan(angle(dict["skew_x"] ?? 0)), d: 1,
                    tx: 0, ty: 0
                )
                transform = skew.concatenating(transform)
            }
        }
        return transform
    }

    /// Whether every component of `t` is finite.
    public static func isFinite(_ t: CGAffineTransform) -> Bool {
        t.a.isFinite && t.b.isFinite && t.c.isFinite && t.d.isFinite && t.tx.isFinite && t.ty.isFinite
    }

    /// Apply the `transform` prop to `view` (identity when `null`).
    public static func apply(_ view: UIView, spec: Any?) {
        let transform = make(spec)
        guard isFinite(transform) else {
            PNLog.rateLimited(PNLog.components, key: "set_transform:nan", "[set_transform:nan] spec=\(String(describing: spec))")
            view.transform = .identity
            return
        }
        view.transform = transform
    }

    /// Parse a rotation value into radians (`"90deg"`, `"1.5rad"`, or numeric degrees).
    public static func angle(_ value: Any) -> CGFloat {
        if let text = value as? String {
            let lower = text.lowercased()
            if lower.hasSuffix("deg"), let degrees = Double(lower.dropLast(3)) {
                return CGFloat(degrees * .pi / 180)
            }
            if lower.hasSuffix("rad"), let radians = Double(lower.dropLast(3)) {
                return CGFloat(radians)
            }
        }
        return CGFloat((PNProps.double(value) ?? 0) * .pi / 180)
    }

    /// Decompose an affine transform into the animatable channels.
    public static func decompose(_ t: CGAffineTransform) -> (translateX: CGFloat, translateY: CGFloat, scaleX: CGFloat, scaleY: CGFloat, rotateDegrees: CGFloat) {
        let scaleX = sqrt(t.a * t.a + t.b * t.b)
        let scaleY = sqrt(t.c * t.c + t.d * t.d)
        let rotation = atan2(t.b, t.a)
        return (t.tx, t.ty, scaleX, scaleY, rotation * 180 / .pi)
    }
}
