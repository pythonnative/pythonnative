import UIKit

/// Decodes and applies reconciler transactions.
///
/// A transaction is a JSON array of ops:
///
/// - `["c", tag, "Type", {props}]` create a view
/// - `["u", tag, {changed}]` apply changed props (`null` removes a prop)
/// - `["i", parent, child, index]` ensure `child` is at `index` under `parent`
/// - `["d", tag]` destroy the view
/// - `["f", tag, x, y, w, h]` set the frame in points
///
/// Ops are applied strictly in order; a failing op is logged and skipped
/// so one bad prop can't desync the rest of the tree.
public enum PNTransaction {
    /// A decoded op.
    public enum Op: Equatable {
        case create(tag: Int64, type: String, props: [String: Any])
        case update(tag: Int64, changed: [String: Any])
        case insert(parent: Int64, child: Int64, index: Int)
        case destroy(tag: Int64)
        case frame(tag: Int64, x: Double, y: Double, w: Double, h: Double)

        public static func == (lhs: Op, rhs: Op) -> Bool {
            switch (lhs, rhs) {
            case let (.create(t1, ty1, p1), .create(t2, ty2, p2)):
                return t1 == t2 && ty1 == ty2 && NSDictionary(dictionary: p1).isEqual(to: p2)
            case let (.update(t1, p1), .update(t2, p2)):
                return t1 == t2 && NSDictionary(dictionary: p1).isEqual(to: p2)
            case let (.insert(p1, c1, i1), .insert(p2, c2, i2)):
                return p1 == p2 && c1 == c2 && i1 == i2
            case let (.destroy(t1), .destroy(t2)):
                return t1 == t2
            case let (.frame(t1, x1, y1, w1, h1), .frame(t2, x2, y2, w2, h2)):
                return t1 == t2 && x1 == x2 && y1 == y2 && w1 == w2 && h1 == h2
            default:
                return false
            }
        }
    }

    /// Errors raised while decoding a single op.
    public enum DecodeError: Error, Equatable {
        case notAnArray
        case malformedOp(index: Int)
        case unknownOpcode(String)
    }

    // MARK: - Decoding

    /// Decode a transaction document into ops. Malformed ops are skipped
    /// (and logged) rather than failing the whole batch.
    public static func decode(_ json: String) throws -> [Op] {
        guard let root = PNJSON.decode(json) as? [Any] else { throw DecodeError.notAnArray }
        var ops: [Op] = []
        ops.reserveCapacity(root.count)
        for (index, raw) in root.enumerated() {
            do {
                ops.append(try decodeOp(raw, index: index))
            } catch {
                PNLog.rateLimited(PNLog.bridge, key: "decode-op", "skipping malformed op #\(index): \(error)")
            }
        }
        return ops
    }

    static func decodeOp(_ raw: Any, index: Int) throws -> Op {
        guard let parts = raw as? [Any], let code = parts.first as? String else {
            throw DecodeError.malformedOp(index: index)
        }
        func tag(_ i: Int) throws -> Int64 {
            guard i < parts.count, let value = PNProps.double(parts[i]), value.isFinite else {
                throw DecodeError.malformedOp(index: index)
            }
            return Int64(value)
        }
        func number(_ i: Int) throws -> Double {
            guard i < parts.count, let value = PNProps.double(parts[i]) else {
                throw DecodeError.malformedOp(index: index)
            }
            return value
        }
        switch code {
        case "c":
            guard parts.count >= 4, let type = parts[2] as? String else { throw DecodeError.malformedOp(index: index) }
            let props = (PNJSON.resolveInfinity(parts[3]) as? [String: Any]) ?? [:]
            return .create(tag: try tag(1), type: type, props: props)
        case "u":
            guard parts.count >= 3 else { throw DecodeError.malformedOp(index: index) }
            let changed = (PNJSON.resolveInfinity(parts[2]) as? [String: Any]) ?? [:]
            return .update(tag: try tag(1), changed: changed)
        case "i":
            guard parts.count >= 4 else { throw DecodeError.malformedOp(index: index) }
            return .insert(parent: try tag(1), child: try tag(2), index: Int(try number(3)))
        case "d":
            return .destroy(tag: try tag(1))
        case "f":
            guard parts.count >= 6 else { throw DecodeError.malformedOp(index: index) }
            return .frame(tag: try tag(1), x: try number(2), y: try number(3), w: try number(4), h: try number(5))
        default:
            throw DecodeError.unknownOpcode(code)
        }
    }

    // MARK: - Applying

    /// Decode and apply a transaction document.
    public static func apply(_ json: String) {
        let ops: [Op]
        do {
            ops = try decode(json)
        } catch {
            PNLog.bridge.error("transaction rejected: \(String(describing: error))")
            return
        }
        apply(ops)
    }

    /// Apply already-decoded ops in order with per-op error isolation.
    public static func apply(_ ops: [Op]) {
        let registry = PNViewRegistry.shared
        for op in ops {
            switch op {
            case let .create(tag, type, props):
                if registry.resolve(tag) != nil {
                    PNLog.rateLimited(PNLog.bridge, key: "dup-create", "create for tag \(tag) ignored: already exists")
                    continue
                }
                let manager = PNRegistry.shared.manager(for: type)
                let view = manager.createView(tag: tag, props: props)
                registry.register(PNViewRecord(tag: tag, typeName: type, view: view, manager: manager))
                manager.didCreate(view: view, tag: tag, props: props)

            case let .update(tag, changed):
                guard let record = registry.resolve(tag) else {
                    PNLog.rateLimited(PNLog.bridge, key: "missing-update", "update for unknown tag \(tag)")
                    continue
                }
                record.manager.update(view: record.view, changed: changed)

            case let .insert(parent, child, index):
                guard let parentRecord = registry.resolve(parent), let childRecord = registry.resolve(child) else {
                    PNLog.rateLimited(PNLog.bridge, key: "missing-insert", "insert \(child) into \(parent): unknown tag")
                    continue
                }
                parentRecord.manager.insertChild(parent: parentRecord.view, child: childRecord.view, index: index)

            case let .destroy(tag):
                guard let record = registry.unregister(tag) else { continue }
                if let parent = record.view.superview,
                   let parentState = PNViewState.existing(for: parent),
                   let parentRecord = registry.resolve(parentState.tag)
                {
                    parentRecord.manager.removeChild(parent: parent, child: record.view)
                }
                record.manager.destroy(view: record.view)
                PNViewState.detach(record.view)

            case let .frame(tag, x, y, w, h):
                guard let record = registry.resolve(tag) else { continue }
                record.manager.setFrame(view: record.view, x: x, y: y, w: w, h: h)
            }
        }
    }
}
