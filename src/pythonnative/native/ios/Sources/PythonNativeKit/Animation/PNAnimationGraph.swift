import UIKit

/// UI-thread expression evaluation, input bindings, and graph animation drivers.
enum PNAnimationGraph {
    struct Graph { var nodes: [[String: Any]]; var bindings: [[Any]] }
    static var graphs: [Int64: Graph] = [:]
    static var values: [Int64: Double] = [:]
    static var previous: [Int64: Double] = [:]
    static var outputs: [Int64: Any] = [:]
    static var drivers: [Int64: PNGraphDriver] = [:]
    private static var membership: [Int64: Set<Int64>] = [:]
    private static var applied: [String: (ObjectIdentifier, NSObject)] = [:]
    static var evaluatedNodes = 0
    static var evaluatedGraphs = 0
    static var frameCount = 0

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
        guard values[id] != value else { return }
        values[id] = value
        evaluate(changed: [id])
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
        var changed: Set<Int64> = []
        for (field, node) in fields {
            if let value = payload[field] as? NSNumber, value.doubleValue.isFinite {
                let id = identity(node)
                if values[id] != value.doubleValue { values[id] = value.doubleValue; changed.insert(id) }
            }
        }
        evaluate(changed: changed)
    }
    static func forget(_ tag: Int64) {
        applied = applied.filter { !$0.key.hasPrefix("\(tag):") }
        for (id, var graph) in graphs {
            graph.bindings.removeAll { identity($0[0]) == tag }
            if graph.bindings.isEmpty { graphs.removeValue(forKey: id) } else { graphs[id] = graph }
        }
        collect()
    }
    static func collect() {
        membership.removeAll(keepingCapacity: true)
        for (graphID, graph) in graphs {
            for node in graph.nodes { membership[identity(node["id"]), default: []].insert(graphID) }
        }
        let live = Set(graphs.values.flatMap { $0.nodes.map { identity($0["id"]) } })
        values = values.filter { live.contains($0.key) }
        previous = previous.filter { live.contains($0.key) }
        outputs = outputs.filter { live.contains($0.key) }
        for (id, driver) in drivers where !live.contains(driver.node) {
            driver.stop()
            drivers.removeValue(forKey: id)
            PNAnimator.reportCompletion(id: id, finished: false)
        }
        PNGraphClock.shared.stopIfIdle()
    }
    static func input(_ value: [String: Any]) -> Double {
        value["node"] == nil ? number(value["constant"]) : values[identity(value["node"])] ?? 0
    }
    static func evaluate(changed: Set<Int64>? = nil) {
        let affected = changed.map { Set($0.flatMap { membership[$0] ?? [] }) } ?? Set(graphs.keys)
        for graphID in affected {
            guard let graph = graphs[graphID] else { continue }
            evaluatedGraphs += 1
            var dirty = changed ?? Set(graph.nodes.map { identity($0["id"]) })
            for node in graph.nodes {
                let id = identity(node["id"])
                let rawInputs = node["inputs"] as? [[String: Any]] ?? []
                guard dirty.contains(id) || rawInputs.contains(where: { dirty.contains(identity($0["node"])) }) else { continue }
                dirty.insert(id)
                evaluatedNodes += 1
                let inputs = rawInputs.map(input)
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
                guard let value = outputs[identity(binding[2])] as? NSObject else { continue }
                let key = "\(record.tag):\(prop)", viewID = ObjectIdentifier(record.view)
                if let old = applied[key], old.0 == viewID && old.1.isEqual(value) { continue }
                applied[key] = (viewID, value)
                record.manager.setAnimatedProperty(view: record.view, prop: prop, value: value)
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
        if spec["kind"] as? String == "timing", !PNEasing.isValid(spec["easing"]) { return false }
        drivers.removeValue(forKey: id)?.stop()
        let driver = PNGraphDriver(id: id, node: node, spec: spec)
        drivers[id] = driver
        driver.start()
        return true
    }
    static func cancel(_ id: Int64) -> Double? {
        guard let driver = drivers.removeValue(forKey: id) else { return nil }
        driver.stop()
        PNGraphClock.shared.stopIfIdle()
        return values[driver.node]
    }
}

/// All graph drivers share one display link and publish one evaluation per frame.
final class PNGraphClock: NSObject {
    static let shared = PNGraphClock()
    private var link: CADisplayLink?
    private var previousTime = 0.0
    var running: Bool { link != nil }

    func start() {
        guard link == nil else { return }
        previousTime = 0
        let display = CADisplayLink(target: self, selector: #selector(tick(_:)))
        link = display
        display.add(to: .main, forMode: .common)
    }
    func stopIfIdle() {
        if PNAnimationGraph.drivers.values.allSatisfy({ !$0.active }) {
            link?.invalidate(); link = nil; previousTime = 0
        }
    }
    @objc private func tick(_ display: CADisplayLink) {
        let dt = previousTime == 0 ? display.duration : min(0.064, display.timestamp - previousTime)
        previousTime = display.timestamp
        advance(dt)
    }
    func advance(_ dt: Double) {
        var changed: Set<Int64> = [], completed: [Int64] = []
        PNAnimationGraph.frameCount += 1
        for driver in Array(PNAnimationGraph.drivers.values) where driver.active {
            let before = PNAnimationGraph.values[driver.node]
            if driver.advance(dt) { completed.append(driver.id) }
            if before != PNAnimationGraph.values[driver.node] { changed.insert(driver.node) }
        }
        PNAnimationGraph.evaluate(changed: changed)
        for id in completed {
            PNAnimationGraph.drivers.removeValue(forKey: id)
            PNAnimator.reportCompletion(id: id, finished: true)
        }
        stopIfIdle()
    }
}

final class PNGraphDriver: NSObject {
    let id: Int64, node: Int64
    let spec: [String: Any]
    var active = false
    var elapsed = 0.0
    var current: Double, velocity: Double
    init(id: Int64, node: Int64, spec: [String: Any]) {
        self.id = id; self.node = node; self.spec = spec
        current = PNAnimationGraph.number(spec["from"])
        velocity = PNAnimationGraph.number(spec["velocity"] ?? spec["initial_velocity"])
    }
    func start() { active = true; PNGraphClock.shared.start() }
    func stop() { active = false }
    func advance(_ dt: Double) -> Bool {
        elapsed += dt
        let delay = PNAnimationGraph.number(spec["delay_ms"]) / 1000
        guard elapsed >= delay else { return false }
        var target = PNAnimationGraph.number(spec["to"])
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
            // React Native's model: velocity in points per millisecond,
            // `v(t) = v0 * d^t`, shared with `PNDecayDriver`.
            let from = PNAnimationGraph.number(spec["from"])
            let v0 = PNAnimationGraph.number(spec["velocity"])
            let d = PNProps.double(spec["deceleration"]) ?? PNDecayDriver.defaultDeceleration
            let t = (elapsed - delay) * 1000
            done = PNDecayDriver.isAtRest(from: from, velocity: v0, deceleration: d, elapsedMs: t)
            current = done
                ? PNDecayDriver.finalValue(from: from, velocity: v0, deceleration: d)
                : PNDecayDriver.position(from: from, velocity: v0, deceleration: d, elapsedMs: t)
            velocity = PNDecayDriver.velocity(velocity: v0, deceleration: d, elapsedMs: t)
            target = PNDecayDriver.finalValue(from: from, velocity: v0, deceleration: d)
        default:
            let duration = max(0.001, ((spec["duration_ms"] as? Double) ?? 300) / 1000)
            let t = min(1, max(0, (elapsed - delay) / duration))
            let eased = PNEasing.function(spec["easing"]).map { $0(t) } ?? t
            let from = PNAnimationGraph.number(spec["from"])
            current = from + (target - from) * eased
            done = t >= 1
        }
        if UIAccessibility.isReduceMotionEnabled { current = target; done = true }
        PNAnimationGraph.values[node] = current.isFinite ? current : 0
        if done { stop() }
        return done
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
