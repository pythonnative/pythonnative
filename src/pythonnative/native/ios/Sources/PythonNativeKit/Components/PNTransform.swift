import UIKit

/// Builds `CATransform3D`s from the `transform` style prop.
///
/// The prop is a list of single-key dicts applied in order (later entries
/// act in the local space of earlier ones, as in React Native):
/// `rotate` / `rotate_z` (degrees, or a `"45deg"` / `"0.5rad"` string),
/// `rotate_x`, `rotate_y`, `scale`, `scale_x`, `scale_y`, `translate_x`,
/// `translate_y`, `skew_x`, `skew_y` (degrees), and `perspective`
/// (distance in points; sets `m34 = -1 / d`).
///
/// A motion write of `transform` carries the whole list and replaces the
/// static one while it's set (RFC 0009).
public enum PNTransform {
    /// Build a 3D transform from a spec list (or single dict). `nil` is identity.
    public static func make(_ spec: Any?) -> CATransform3D {
        var transform = CATransform3DIdentity
        guard let spec = spec, !(spec is NSNull) else { return transform }
        let entries: [Any] = (spec as? [Any]) ?? [spec]
        for entry in entries {
            guard let dict = entry as? [String: Any] else { continue }
            if let distance = PNProps.double(dict["perspective"]), distance != 0 {
                var perspective = CATransform3DIdentity
                perspective.m34 = CGFloat(-1 / distance)
                transform = CATransform3DConcat(perspective, transform)
            }
            if let rotate = dict["rotate"] ?? dict["rotate_z"] {
                transform = CATransform3DRotate(transform, angle(rotate), 0, 0, 1)
            }
            if let rotate = dict["rotate_x"] {
                transform = CATransform3DRotate(transform, angle(rotate), 1, 0, 0)
            }
            if let rotate = dict["rotate_y"] {
                transform = CATransform3DRotate(transform, angle(rotate), 0, 1, 0)
            }
            if let scale = PNProps.double(dict["scale"]) {
                transform = CATransform3DScale(transform, CGFloat(scale), CGFloat(scale), 1)
            }
            if let sx = PNProps.double(dict["scale_x"]) {
                transform = CATransform3DScale(transform, CGFloat(sx), 1, 1)
            }
            if let sy = PNProps.double(dict["scale_y"]) {
                transform = CATransform3DScale(transform, 1, CGFloat(sy), 1)
            }
            if dict["translate_x"] != nil || dict["translate_y"] != nil {
                let tx = PNProps.double(dict["translate_x"]) ?? 0
                let ty = PNProps.double(dict["translate_y"]) ?? 0
                transform = CATransform3DTranslate(transform, CGFloat(tx), CGFloat(ty), 0)
            }
            if dict["skew_x"] != nil || dict["skew_y"] != nil {
                let skew = CGAffineTransform(
                    a: 1, b: tan(angle(dict["skew_y"] ?? 0)),
                    c: tan(angle(dict["skew_x"] ?? 0)), d: 1,
                    tx: 0, ty: 0
                )
                transform = CATransform3DConcat(CATransform3DMakeAffineTransform(skew), transform)
            }
        }
        return transform
    }

    /// The 2D projection of a spec (identity `z`), for callers that only
    /// need affine components.
    public static func makeAffine(_ spec: Any?) -> CGAffineTransform {
        let t = make(spec)
        return CATransform3DIsAffine(t) ? CATransform3DGetAffineTransform(t) : .identity
    }

    /// Whether every component of `t` is finite.
    public static func isFinite(_ t: CATransform3D) -> Bool {
        [t.m11, t.m12, t.m13, t.m14, t.m21, t.m22, t.m23, t.m24,
         t.m31, t.m32, t.m33, t.m34, t.m41, t.m42, t.m43, t.m44].allSatisfy { $0.isFinite }
    }

    /// Apply a `transform` list to `view` (identity when `nil`).
    public static func apply(_ view: UIView, spec: Any?) {
        assign(view, make(spec), spec: spec)
    }

    private static func assign(_ view: UIView, _ transform: CATransform3D, spec: Any?) {
        guard isFinite(transform) else {
            PNLog.rateLimited(PNLog.components, key: "set_transform:nan", "[set_transform:nan] spec=\(String(describing: spec))")
            view.layer.transform = CATransform3DIdentity
            return
        }
        view.layer.transform = transform
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

    /// Decompose an affine transform into the animatable 2D channels.
    public static func decompose(_ t: CGAffineTransform) -> (translateX: CGFloat, translateY: CGFloat, scaleX: CGFloat, scaleY: CGFloat, rotateDegrees: CGFloat) {
        let scaleX = sqrt(t.a * t.a + t.b * t.b)
        let scaleY = sqrt(t.c * t.c + t.d * t.d)
        let rotation = atan2(t.b, t.a)
        return (t.tx, t.ty, scaleX, scaleY, rotation * 180 / .pi)
    }
}
