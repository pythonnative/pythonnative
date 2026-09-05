import UIKit

/// UI-thread expression evaluation, input bindings, and graph animation drivers.
enum PNAnimationGraph {
    struct Graph { var nodes: [[String: Any]]; var bindings: [[Any]] }
    static var graphs: [Int64: Graph] = [:]
    static var values: [Int64: Double] = [:]
    static var previous: [Int64: Double] = [:]
    static var outputs: [Int64: Any] = [:]
    static var drivers: [Int64: PNGraphDriver] = [:]

    static func number(_ value: Any?) -> Double { (value as? NSNumber)?.doubleValue ?? 0 }
    static func identity(_ value: Any?) -> Int64 { (value as? NSNumber)?.int64Value ?? 0 }
    static func install(_ spec: [String: Any]) {
        let id = identity(spec["id"])
        let bindings = spec["bindings"] as? [[Any]] ?? []
        let nodes = spec["nodes"] as? [[String: Any]] ?? []
        let ids = Set(nodes.map { identity($0["id"]) })
        for (key, graph) in graphs where graph.nodes.contains(where: { ids.contains(identity($0["id"])) }) { graphs.removeValue(forKey: key) }
        if !bindings.isEmpty {
            for node in nodes {
                let key = identity(node["id"])
                if values[key] == nil { values[key] = number(node["value"]) }
                if previous[key] == nil { previous[key] = number(node["previous"]) }
            }
            graphs[id] = Graph(nodes: nodes, bindings: bindings)
        }
        collect()
        evaluate()
    }
    static func set(_ id: Int64, _ value: Double) {
        guard value.isFinite else { return }
        values[id] = value
        evaluate()
    }
    static func event(_ tag: Int64, _ name: String, _ args: [Any?]) {
        guard let view = PNViewRegistry.shared.view(for: tag), let props = PNViewState.existing(for: view)?.props,
              let payload = args.first as? [String: Any] else { return }
        var fields: [String: Any]?
        if name.hasPrefix("gesture:"), let index = Int(name.dropFirst(8)),
           let gestures = props["gestures"] as? [[String: Any]], gestures.indices.contains(index),
           let events = gestures[index]["animated_events"] as? [String: [String: Any]] {
            fields = events[payload["state"] as? String ?? ""]
        } else { fields = (props["_pn_animated_events"] as? [String: [String: Any]])?[name] }
        guard let fields = fields else { return }
        for (field, node) in fields { if let value = payload[field] as? NSNumber { values[identity(node)] = value.doubleValue } }
        evaluate()
    }
    static func forget(_ tag: Int64) {
        for (id, var graph) in graphs {
            graph.bindings.removeAll { identity($0[0]) == tag }
            if graph.bindings.isEmpty { graphs.removeValue(forKey: id) } else { graphs[id] = graph }
        }
        collect()
    }
    static func collect() {
        let live = Set(graphs.values.flatMap { $0.nodes.map { identity($0["id"]) } })
        values = values.filter { live.contains($0.key) }
        previous = previous.filter { live.contains($0.key) }
        outputs = outputs.filter { live.contains($0.key) }
        for (id, driver) in drivers where !live.contains(driver.node) {
            driver.stop()
            drivers.removeValue(forKey: id)
            PNAnimator.reportCompletion(id: id, finished: false)
        }
    }
    static func input(_ value: [String: Any]) -> Double {
        value["node"] == nil ? number(value["constant"]) : values[identity(value["node"])] ?? 0
    }
    static func evaluate() {
        for graph in graphs.values {
            for node in graph.nodes {
                let id = identity(node["id"])
                let inputs = (node["inputs"] as? [[String: Any]] ?? []).map(input)
                let a = inputs.first ?? 0, b = inputs.count > 1 ? inputs[1] : 0
                var value: Double = 0
                switch node["kind"] as? String {
                case "value": value = values[id] ?? 0
                case "add": value = a + b
                case "subtract": value = a - b
                case "multiply": value = a * b
                case "divide": value = b == 0 ? 0 : a / b
                case "modulo": value = b == 0 ? 0 : a.truncatingRemainder(dividingBy: b)
                case "negate": value = -a
                case "diff_clamp":
                    value = min(number(node["maximum"]), max(number(node["minimum"]), (values[id] ?? 0) + a - (previous[id] ?? a)))
                    previous[id] = a
                case "interpolate": value = interpolate(node, a, id)
                default: break
                }
                values[id] = value.isFinite ? value : 0
                if node["color"] as? Bool != true { outputs[id] = values[id] }
            }
            for binding in graph.bindings {
                guard binding.count == 3, let record = PNViewRegistry.shared.resolve(identity(binding[0])), let prop = binding[1] as? String else { continue }
                record.manager.setAnimatedProperty(view: record.view, prop: prop, value: outputs[identity(binding[2])])
            }
        }
    }
    private static func interpolate(_ node: [String: Any], _ incoming: Double, _ id: Int64) -> Double {
        guard let ranges = node["ranges"] as? [Double], ranges.count >= 2,
              let outputs = node["outputs"] as? [Any], outputs.count == ranges.count else { return 0 }
        var x = incoming
        let mode = x < ranges[0] ? node["left"] as? String : x > ranges.last! ? node["right"] as? String : "extend"
        if mode == "identity" { return x }
        if mode == "clamp" { x = min(ranges.last!, max(ranges[0], x)) }
        var index = 0
        while index < ranges.count - 2 && x >= ranges[index + 1] { index += 1 }
        let span = ranges[index + 1] - ranges[index]
        let t = span == 0 ? 0 : (x - ranges[index]) / span
        if node["color"] as? Bool == true, let from = outputs[index] as? [Double], let to = outputs[index + 1] as? [Double] {
            self.outputs[id] = "#" + zip(from, to).map { String(format: "%02X", Int(min(255, max(0, ($0 + ($1 - $0) * min(1, max(0, t))).rounded())))) }.joined()
            return 0
        }
        return number(outputs[index]) + (number(outputs[index + 1]) - number(outputs[index])) * t
    }
    static func start(_ id: Int64, node: Int64, spec: [String: Any]) -> Bool {
        guard values[node] != nil, ["timing", "spring", "decay"].contains(spec["kind"] as? String ?? "") else { return false }
        drivers.removeValue(forKey: id)?.stop()
        let driver = PNGraphDriver(id: id, node: node, spec: spec)
        drivers[id] = driver
        driver.start()
        return true
    }
    static func cancel(_ id: Int64) -> Double? {
        guard let driver = drivers.removeValue(forKey: id) else { return nil }
        driver.stop()
        return values[driver.node]
    }
}

final class PNGraphDriver: NSObject {
    let id: Int64, node: Int64
    let spec: [String: Any]
    var link: CADisplayLink?
    var elapsed = 0.0, previousTime = 0.0
    var current: Double, velocity: Double
    init(id: Int64, node: Int64, spec: [String: Any]) {
        self.id = id; self.node = node; self.spec = spec
        current = PNAnimationGraph.number(spec["from"])
        velocity = PNAnimationGraph.number(spec["velocity"] ?? spec["initial_velocity"])
    }
    func start() {
        let display = CADisplayLink(target: self, selector: #selector(tick(_:)))
        link = display
        display.add(to: .main, forMode: .common)
    }
    func stop() { link?.invalidate(); link = nil }
    @objc func tick(_ display: CADisplayLink) {
        let dt = previousTime == 0 ? display.duration : min(0.064, display.timestamp - previousTime)
        previousTime = display.timestamp
        elapsed += dt
        let delay = PNAnimationGraph.number(spec["delay_ms"]) / 1000
        guard elapsed >= delay else { return }
        let target = PNAnimationGraph.number(spec["to"])
        var done = false
        switch spec["kind"] as? String {
        case "spring":
            let mass = max(0.001, (spec["mass"] as? Double) ?? 1)
            let stiffness = (spec["stiffness"] as? Double) ?? 100
            let damping = (spec["damping"] as? Double) ?? 10
            let steps = max(1, Int(ceil(dt / 0.004)))
            for _ in 0..<steps {
                let step = dt / Double(steps)
                velocity += (-stiffness * (current - target) - damping * velocity) / mass * step
                current += velocity * step
            }
            done = abs(velocity) < ((spec["rest_speed_threshold"] as? Double) ?? 0.01) && abs(current - target) < ((spec["rest_displacement_threshold"] as? Double) ?? 0.01)
            if done { current = target }
        case "decay":
            velocity *= pow(min(0.999999, max(0.001, (spec["deceleration"] as? Double) ?? 0.997)), dt * 1000)
            current += velocity * dt
            done = abs(velocity) < ((spec["rest_threshold"] as? Double) ?? 0.1)
        default:
            let duration = max(0.001, ((spec["duration_ms"] as? Double) ?? 300) / 1000)
            let t = min(1, max(0, (elapsed - delay) / duration))
            let curve = PNAnimator.curve(for: spec["easing"]) as? UICubicTimingParameters
            let eased = curve.map { Self.bezier(t, $0.controlPoint1, $0.controlPoint2) } ?? t
            let from = PNAnimationGraph.number(spec["from"])
            current = from + (target - from) * eased
            done = t >= 1
        }
        if UIAccessibility.isReduceMotionEnabled { current = target; done = true }
        PNAnimationGraph.set(node, current)
        if done {
            stop(); PNAnimationGraph.drivers.removeValue(forKey: id)
            PNAnimator.reportCompletion(id: id, finished: true)
        }
    }
    static func bezier(_ t: Double, _ p1: CGPoint, _ p2: CGPoint) -> Double {
        func coordinate(_ u: Double, _ a: Double, _ b: Double) -> Double { 3 * (1-u) * (1-u) * u * a + 3 * (1-u) * u * u * b + u * u * u }
        var low = 0.0, high = 1.0
        for _ in 0..<18 {
            let mid = (low + high) / 2
            if coordinate(mid, p1.x, p2.x) < t { low = mid } else { high = mid }
        }
        return coordinate((low + high) / 2, p1.y, p2.y)
    }
}
