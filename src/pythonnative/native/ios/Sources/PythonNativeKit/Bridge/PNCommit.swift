import Foundation
import CoreFoundation

/// Validates complete surface transactions before invoking a view manager.
enum PNCommit {
    private static var application = ""
    private static var surface = 0
    private static var revision = 0
    private static var parents: [Int64: Int64] = [:]
    private static var live: Set<Int64> = []
    private static var childCounts: [Int64: Int] = [:]
    private static var types: [Int64: String] = [:]
    private static var failed = false

    /// The identity of the commit being applied, while its operations run.
    /// A view that emits during its own creation (an image starting to
    /// load, a text input reporting its selection) belongs to that commit's
    /// revision; stamping it with the previous one would make Python drop
    /// the event as older than the view.
    private static var applying: (application: String, surface: Int, revision: Int)?

    private static var sequence = 0
    static func event(_ args: [Any?], editRevision: Int = 0) -> String {
        sequence += 1
        let identity = applying ?? (application, surface, revision)
        return PNJSON.encode(["application": identity.application, "surface": identity.surface,
                              "revision": identity.revision, "sequence": sequence, "args": args, "edit_revision": editRevision])
    }

    static func layout(_ frames: Any) -> [String: Any] {
        ["application": application, "surface": surface, "revision": revision, "frames": frames, "metrics": PNLayout.metrics]
    }

    static func apply(_ json: String) -> String {
        PNJSON.encode(apply(PNJSON.decodeObject(json)))
    }

    /// Validate and mount one commit, returning the acknowledgement.
    ///
    /// Validation updates the live structural maps in place and records
    /// the inverse of every change, so the work is proportional to the
    /// commit rather than to the mounted tree. A rejected commit replays
    /// the inverses in reverse order.
    static func apply(_ envelope: [String: Any]) -> [String: Any] {
        let prepareStarted = DispatchTime.now().uptimeNanoseconds
        let app = envelope["application"] as? String ?? ""
        let target = envelope["surface"] as? Int ?? 0
        let next = envelope["revision"] as? Int ?? 0
        func error(_ message: String) -> [String: Any] {
            ["ok": false, "application": app, "surface": target, "revision": next, "error": message, "failed": false]
        }
        guard envelope["version"] as? Int == PNContracts.protocolVersion, !app.isEmpty, target > 0,
              let raw = envelope["ops"] as? [[Any]] else { return error("invalid v\(PNContracts.protocolVersion) envelope") }
        let replacing = app != application
        guard next == (replacing ? 1 : revision + 1), replacing || (!failed && target == surface)
        else { return error("stale revision or failed surface") }

        var undo: [() -> Void] = []
        func rollback() {
            for restore in undo.reversed() { restore() }
            undo.removeAll()
        }
        let previous = replacing ? (live, parents, types, childCounts) : nil
        if replacing {
            undo.append { (live, parents, types, childCounts) = previous! }
            live = []; parents = [:]; types = [:]; childCounts = [:]
        }
        func setParent(_ child: Int64, _ parent: Int64?) {
            let old = parents[child]
            undo.append { parents[child] = old }
            parents[child] = parent
        }
        func adjustCount(_ tag: Int64, by delta: Int) {
            let old = childCounts[tag]
            undo.append { childCounts[tag] = old }
            childCounts[tag] = (old ?? 0) + delta
        }
        func reject(_ message: String) -> [String: Any] {
            rollback()
            return error(message)
        }

        var decoded: [PNTransaction.Op] = []
        decoded.reserveCapacity(raw.count)
        var listPatches: Set<Int64> = []
        do {
            for (index, parts) in raw.enumerated() {
                guard let code = parts.first as? String,
                      parts.count == ["c": 4, "u": 4, "i": 4, "d": 2][code],
                      let number = parts[1] as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(), number.doubleValue > 0,
                      number.doubleValue <= 9_007_199_254_740_991,
                      number.doubleValue.rounded() == number.doubleValue else {
                    throw PNTransaction.DecodeError.malformedOp(index: index)
                }
                let tag = number.int64Value
                if code == "c" {
                    guard !live.contains(tag), let type = parts[2] as? String, !type.isEmpty,
                          let props = parts[3] as? [String: Any] else { return reject("invalid create") }
                    guard PNRegistry.shared.componentNames.contains(type) else { return reject("unknown component") }
                    guard PNContracts.validate(type, props) else { return reject("invalid typed props") }
                    if type == "VirtualList", !PNVirtualListManager.validateDataset(tag: tag, props: props, initial: true) { return reject("invalid list dataset") }
                    live.insert(tag)
                    types[tag] = type
                    undo.append { live.remove(tag); types.removeValue(forKey: tag) }
                } else {
                    guard live.contains(tag) else { return reject("unknown tag") }
                    if code == "u" {
                        guard let props = parts[2] as? [String: Any], let removed = parts[3] as? [String] else { return reject("invalid props") }
                        if let type = types[tag], (!PNContracts.validate(type, props, partial: true) || !PNContracts.validateRemoval(type, props, removed)) { return reject("invalid typed update") }
                        if types[tag] == "VirtualList", !PNVirtualListManager.validateDataset(tag: tag, props: props, initial: false) { return reject("invalid list dataset") }
                    }
                    if code == "i" {
                        guard let child = parts[2] as? Int64, live.contains(child),
                              let position = parts[3] as? Int, position >= 0 else { return reject("invalid insertion") }
                        var ancestor: Int64? = tag
                        while let current = ancestor {
                            if current == child { return reject("cycle") }
                            ancestor = parents[current]
                        }
                        let siblings = (childCounts[tag] ?? 0) - (parents[child] == tag ? 1 : 0)
                        guard position <= siblings else { return reject("insertion index exceeds child count") }
                        if let old = parents[child] { adjustCount(old, by: -1) }
                        adjustCount(tag, by: 1)
                        setParent(child, tag)
                    }
                    if code == "d" {
                        guard (childCounts[tag] ?? 0) == 0 else { return reject("destroy children first") }
                        let type = types[tag], count = childCounts[tag]
                        live.remove(tag)
                        types.removeValue(forKey: tag)
                        childCounts.removeValue(forKey: tag)
                        undo.append { live.insert(tag); types[tag] = type; childCounts[tag] = count }
                        if let old = parents[tag] {
                            adjustCount(old, by: -1)
                            setParent(tag, nil)
                        }
                    }
                }
                if (code == "c" || code == "u"), types[tag] == "VirtualList", let props = parts[code == "c" ? 3 : 2] as? [String: Any], props["dataset"] != nil {
                    guard listPatches.insert(tag).inserted else { return reject("multiple list patches in one commit") }
                }
                decoded.append(try PNTransaction.decodeOp(parts, index: index))
            }
        } catch {
            rollback()
            return ["ok": false, "error": String(describing: error), "failed": false]
        }
        let layoutRequest = envelope["layout"] as? [String: Any]
        if envelope["layout"] != nil && layoutRequest == nil { return reject("invalid layout request") }
        if let request = layoutRequest {
            guard let roots = request["roots"] as? [Int64], roots.allSatisfy({ live.contains($0) }),
                  let width = request["width"] as? Double, width.isFinite, width > 0,
                  let height = request["height"] as? Double, height.isFinite, height > 0 else { return reject("invalid layout request") }
        }
        let mutationStarted = DispatchTime.now().uptimeNanoseconds
        do {
            if let previous = previous {
                for tag in previous.0 { try PNTransaction.apply([.destroy(tag: tag)]) }
                PNLayout.reset()
            }
            applying = (app, target, next)
            defer { applying = nil }
            try PNTransaction.apply(decoded)
        } catch {
            failed = true
            let candidate = live
            rollback()
            for tag in candidate.union(live) { try? PNTransaction.apply([.destroy(tag: tag)]) }
            PNLayout.reset()
            return ["ok": false, "error": String(describing: error), "failed": true]
        }
        application = app
        surface = target
        revision = next
        failed = false
        var reply: [String: Any] = ["ok": true, "application": app, "surface": target, "revision": next,
                                    "metrics": ["mutation_ns": DispatchTime.now().uptimeNanoseconds - mutationStarted, "prepare_ns": mutationStarted - prepareStarted]]
        if let request = layoutRequest { reply["layout"] = layout(PNLayout.compute(request)) }
        return reply
    }
}
