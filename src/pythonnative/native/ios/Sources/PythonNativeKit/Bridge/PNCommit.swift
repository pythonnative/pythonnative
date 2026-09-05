import Foundation

/// Validates complete surface transactions before invoking a view manager.
enum PNCommit {
    private static var application = ""
    private static var surface = 0
    private static var revision = 0
    private static var parents: [Int64: Int64] = [:]
    private static var live: Set<Int64> = []
    private static var types: [Int64: String] = [:]
    private static var failed = false

    private static var sequence = 0
    static func event(_ args: [Any?], editRevision: Int = 0) -> String {
        sequence += 1
        return PNJSON.encode(["application": application, "surface": surface,
                              "revision": revision, "sequence": sequence, "args": args, "edit_revision": editRevision])
    }

    static func apply(_ json: String) -> String {
        let envelope = PNJSON.decodeObject(json)
        let app = envelope["application"] as? String ?? ""
        let target = envelope["surface"] as? Int ?? 0
        let next = envelope["revision"] as? Int ?? 0
        func error(_ message: String) -> String {
            PNJSON.encode(["ok": false, "application": app, "surface": target,
                           "revision": next, "error": message])
        }
        guard envelope["version"] as? Int == 2, !app.isEmpty, target > 0,
              let raw = envelope["ops"] as? [[Any]] else { return error("invalid v2 envelope") }
        let replacing = app != application
        guard next == (replacing ? 1 : revision + 1), replacing || (!failed && target == surface)
        else { return error("stale revision or failed surface") }
        var tags: Set<Int64> = replacing ? [] : live
        var links: [Int64: Int64] = replacing ? [:] : parents
        var names: [Int64: String] = replacing ? [:] : types
        var decoded: [PNTransaction.Op] = []
        do {
            for (index, parts) in raw.enumerated() {
                guard let code = parts.first as? String,
                      parts.count == ["c": 4, "u": 3, "i": 4, "d": 2, "f": 6][code],
                      let number = parts[1] as? NSNumber, number.doubleValue > 0,
                      number.doubleValue.rounded() == number.doubleValue else {
                    throw PNTransaction.DecodeError.malformedOp(index: index)
                }
                let tag = number.int64Value
                if code == "c" {
                    guard !tags.contains(tag), let type = parts[2] as? String, !type.isEmpty,
                          parts[3] is [String: Any] else { return error("invalid create") }
                    guard PNRegistry.shared.componentNames.contains(type) else { return error("unknown component") }
                    guard PNContracts.validate(type, parts[3] as! [String: Any]) else { return error("invalid typed props") }
                    tags.insert(tag)
                    names[tag] = type
                } else {
                    guard tags.contains(tag) else { return error("unknown tag") }
                    if code == "u" {
                        guard let props = parts[2] as? [String: Any] else { return error("invalid props") }
                        if let type = names[tag], !PNContracts.validate(type, props, partial: true) { return error("invalid typed update") }
                    }
                    if code == "i" {
                        guard let child = parts[2] as? Int64, tags.contains(child),
                              let position = parts[3] as? Int, position >= 0 else { return error("invalid insertion") }
                        var ancestor: Int64? = tag
                        while let current = ancestor {
                            if current == child { return error("cycle") }
                            ancestor = links[current]
                        }
                        let siblings = links.filter { $0.value == tag && $0.key != child }.count
                        guard position <= siblings else { return error("insertion index exceeds child count") }
                        links[child] = tag
                    }
                    if code == "d" {
                        guard !links.values.contains(tag) else { return error("destroy children first") }
                        tags.remove(tag)
                        names.removeValue(forKey: tag)
                        links.removeValue(forKey: tag)
                    }
                    if code == "f" {
                        for value in parts[2...] {
                            guard let number = value as? NSNumber, number.doubleValue.isFinite else { return error("invalid frame") }
                        }
                        guard (parts[4] as! NSNumber).doubleValue >= 0,
                              (parts[5] as! NSNumber).doubleValue >= 0 else { return error("negative size") }
                    }
                }
                decoded.append(try PNTransaction.decodeOp(parts, index: index))
            }
        } catch { return PNJSON.encode(["ok": false, "error": String(describing: error)]) }
        if replacing {
            for tag in live { PNTransaction.apply([.destroy(tag: tag)]) }
            PNLayout.reset()
        }
        PNTransaction.apply(decoded)
        PNLayout.observe(decoded)
        application = app
        surface = target
        revision = next
        live = tags
        types = names
        parents = links
        failed = false
        return PNJSON.encode(["ok": true, "application": app, "surface": target, "revision": next])
    }
}
