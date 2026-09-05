import UIKit

/// Installs `UIGestureRecognizer`s from the `gestures` prop and emits
/// `gesture:<index>` events with the payload dict Python's
/// `GestureEvent` expects.
///
/// Spec fields:
/// - `kind`: `tap`, `long_press`, `pan`, `swipe`, `fling`, `pinch`, `rotation`
/// - per-kind config (`n_taps`, `max_distance`, `min_duration_ms`,
///   `min_distance`, `direction`, `n_pointers`, `min_velocity`)
/// - `simultaneous`: indices allowed to recognize together
/// - `wait_for`: indices that must fail before this one may begin
public final class PNGestureCoordinator: NSObject, UIGestureRecognizerDelegate {
    public static let shared = PNGestureCoordinator()

    /// Bookkeeping for one installed recognizer.
    final class Entry {
        let index: Int
        let kind: String
        var simultaneous: Set<Int>
        var minVelocity: CGFloat
        var direction: String
        var lastLocation: CGPoint = .zero

        init(index: Int, kind: String, simultaneous: Set<Int>, minVelocity: CGFloat, direction: String) {
            self.index = index
            self.kind = kind
            self.simultaneous = simultaneous
            self.minVelocity = minVelocity
            self.direction = direction
        }
    }

    private var entries: [ObjectIdentifier: Entry] = [:]

    private override init() {
        super.init()
    }

    // MARK: - Wiring

    /// Replace the recognizers on `view` with the ones described by `specs`.
    public func wire(view: UIView, specs: Any?) {
        unwire(view: view)
        guard let state = PNViewState.existing(for: view) else { return }
        let list = ((specs as? [Any]) ?? []).map { ($0 as? [String: Any]) ?? [:] }
        guard !list.isEmpty else { return }
        // A spec may own several recognizers (an any-direction swipe is
        // one `UISwipeGestureRecognizer` per direction), so relationships
        // are wired spec-to-spec across every recognizer on each side.
        var built: [Int: [UIGestureRecognizer]] = [:]
        for (index, spec) in list.enumerated() {
            let recognizers = makeRecognizers(spec)
            if recognizers.isEmpty {
                PNLog.once(PNLog.gestures, key: "kind:\(PNProps.string(spec["kind"]) ?? "")", "unsupported gesture kind '\(PNProps.string(spec["kind"]) ?? "")'")
                continue
            }
            for (recognizer, direction) in recognizers {
                let entry = Entry(
                    index: index,
                    kind: PNProps.string(spec["kind"]) ?? "",
                    simultaneous: Set(((spec["simultaneous"] as? [Any]) ?? []).compactMap { PNProps.int($0) }),
                    minVelocity: CGFloat(PNProps.double(spec["min_velocity"]) ?? 300),
                    direction: direction ?? PNProps.string(spec["direction"]) ?? "any"
                )
                entries[ObjectIdentifier(recognizer)] = entry
                recognizer.delegate = self
                recognizer.cancelsTouchesInView = false
                recognizer.addTarget(self, action: #selector(handle(_:)))
                view.addGestureRecognizer(recognizer)
                state.gestureRecognizers.append(recognizer)
                built[index, default: []].append(recognizer)
            }
        }
        for (index, spec) in list.enumerated() {
            guard let recognizers = built[index] else { continue }
            for wait in ((spec["wait_for"] as? [Any]) ?? []).compactMap({ PNProps.int($0) }) {
                guard wait != index, let others = built[wait] else { continue }
                for recognizer in recognizers {
                    for other in others {
                        recognizer.require(toFail: other)
                    }
                }
            }
        }
        view.isUserInteractionEnabled = true
    }

    /// Remove every recognizer previously installed on `view`.
    public func unwire(view: UIView) {
        guard let state = PNViewState.existing(for: view) else { return }
        for recognizer in state.gestureRecognizers {
            recognizer.removeTarget(self, action: nil)
            view.removeGestureRecognizer(recognizer)
            entries.removeValue(forKey: ObjectIdentifier(recognizer))
        }
        state.gestureRecognizers = []
    }

    // MARK: - Recognizer construction

    /// Build the recognizer(s) for one spec as `(recognizer, direction)`
    /// pairs. `direction` is set only for swipe / fling recognizers: a
    /// `UISwipeGestureRecognizer` reports its configured mask rather than
    /// the direction it resolved, so `direction = "any"` installs one
    /// recognizer per direction and tags each with its own name.
    func makeRecognizers(_ spec: [String: Any]) -> [(UIGestureRecognizer, String?)] {
        switch PNProps.string(spec["kind"]) ?? "" {
        case "tap":
            let tap = UITapGestureRecognizer()
            tap.numberOfTapsRequired = max(1, PNProps.int(spec["n_taps"]) ?? 1)
            return [(tap, nil)]
        case "long_press":
            let press = UILongPressGestureRecognizer()
            press.minimumPressDuration = max(0.01, (PNProps.double(spec["min_duration_ms"]) ?? 500) / 1000)
            press.allowableMovement = CGFloat(PNProps.double(spec["max_distance"]) ?? 12)
            return [(press, nil)]
        case "pan":
            return [(PNPanGestureRecognizer(minDistance: CGFloat(PNProps.double(spec["min_distance"]) ?? 10)), nil)]
        case "swipe", "fling":
            let requested = PNProps.string(spec["direction"]) ?? "any"
            let directions = PNGestureCoordinator.swipeDirectionNames.contains(requested)
                ? [requested]
                : PNGestureCoordinator.swipeDirectionNames
            let touches = max(1, PNProps.int(spec["n_pointers"]) ?? 1)
            return directions.map { name in
                let swipe = UISwipeGestureRecognizer()
                swipe.direction = PNGestureCoordinator.swipeDirection(name)
                swipe.numberOfTouchesRequired = touches
                return (swipe, name)
            }
        case "pinch":
            return [(UIPinchGestureRecognizer(), nil)]
        case "rotation":
            return [(UIRotationGestureRecognizer(), nil)]
        default:
            return []
        }
    }

    /// The single-direction names a swipe spec may request.
    public static let swipeDirectionNames = ["left", "right", "up", "down"]

    /// Map a Python direction name to `UISwipeGestureRecognizer.Direction`.
    public static func swipeDirection(_ name: String) -> UISwipeGestureRecognizer.Direction {
        switch name {
        case "left": return .left
        case "right": return .right
        case "up": return .up
        case "down": return .down
        default: return [.left, .right, .up, .down]
        }
    }

    // MARK: - Relationship lookups (exposed for tests)

    /// The spec index recorded for `recognizer`, if it was installed by the coordinator.
    public func index(of recognizer: UIGestureRecognizer) -> Int? {
        entries[ObjectIdentifier(recognizer)]?.index
    }

    /// Whether the two recognizers are allowed to recognize together.
    public func allowsSimultaneous(_ a: UIGestureRecognizer, _ b: UIGestureRecognizer) -> Bool {
        guard let ea = entries[ObjectIdentifier(a)], let eb = entries[ObjectIdentifier(b)] else {
            // One side isn't ours (Pressable, scroll view): don't block it.
            return true
        }
        if a.view !== b.view { return true }
        return ea.simultaneous.contains(eb.index) || eb.simultaneous.contains(ea.index)
    }

    // MARK: - UIGestureRecognizerDelegate

    public func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        allowsSimultaneous(gestureRecognizer, other)
    }

    // MARK: - Emission

    @objc private func handle(_ recognizer: UIGestureRecognizer) {
        guard let view = recognizer.view, let entry = entries[ObjectIdentifier(recognizer)] else { return }
        let location = recognizer.location(in: view)
        var payload: [String: Any] = [
            "kind": entry.kind,
            "x": Double(location.x),
            "y": Double(location.y),
            "translation_x": 0.0,
            "translation_y": 0.0,
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "scale": 1.0,
            "rotation": 0.0,
            "pointer_count": recognizer.numberOfTouches,
            "direction": NSNull(),
        ]
        var state = PNGestureCoordinator.stateName(recognizer.state)
        switch recognizer {
        case let pan as UIPanGestureRecognizer:
            let translation = pan.translation(in: view)
            let velocity = pan.velocity(in: view)
            payload["translation_x"] = Double(translation.x)
            payload["translation_y"] = Double(translation.y)
            payload["velocity_x"] = Double(velocity.x)
            payload["velocity_y"] = Double(velocity.y)
        case let pinch as UIPinchGestureRecognizer:
            payload["scale"] = Double(pinch.scale)
            payload["velocity_x"] = Double(pinch.velocity)
        case let rotation as UIRotationGestureRecognizer:
            payload["rotation"] = Double(rotation.rotation)
            payload["velocity_x"] = Double(rotation.velocity)
        case let swipe as UISwipeGestureRecognizer:
            // UIKit reports swipes as a single `.ended`; Python expects `ended`.
            guard swipe.state == .ended || swipe.state == .recognized else { return }
            state = "ended"
            payload["direction"] = entry.direction
            payload["pointer_count"] = max(1, swipe.numberOfTouchesRequired)
        case is UITapGestureRecognizer:
            guard recognizer.state == .ended || recognizer.state == .recognized else { return }
            state = "ended"
        default:
            break
        }
        guard state != "possible" else { return }
        payload["state"] = state
        PNEvents.emit(view, "gesture:\(entry.index)", [payload])
    }

    static func stateName(_ state: UIGestureRecognizer.State) -> String {
        switch state {
        case .began: return "began"
        case .changed: return "changed"
        case .ended: return "ended"
        case .cancelled: return "cancelled"
        case .failed: return "failed"
        default: return "possible"
        }
    }

    /// The direction name recorded for a swipe / fling recognizer (exposed for tests).
    public func direction(of recognizer: UIGestureRecognizer) -> String? {
        guard let entry = entries[ObjectIdentifier(recognizer)], entry.kind == "swipe" || entry.kind == "fling" else {
            return nil
        }
        return entry.direction
    }
}

/// A pan recognizer that records the Python `min_distance` threshold.
///
/// UIKit applies its own ~10 pt hysteresis before a pan begins, which
/// matches the Python default; the value is kept for diagnostics and
/// for future tuning rather than overriding UIKit's touch pipeline.
final class PNPanGestureRecognizer: UIPanGestureRecognizer {
    let minDistance: CGFloat

    init(minDistance: CGFloat) {
        self.minDistance = max(0, minDistance)
        super.init(target: nil, action: nil)
    }
}
