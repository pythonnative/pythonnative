import Foundation
import CoreFoundation

/// A list's keyed metadata. Updating one row never copies the dataset.
final class PNListStore {
    struct Row: Equatable {
        let key: String
        let revision: Int
        let extent: Double
        let sticky: Bool
    }
    struct Edit {
        let code: String
        let from: Int
        let to: Int
    }
    struct Patch {
        let base: Int
        let revision: Int
        let order: [String]?
        let changed: [String: Row]
        let deleted: Set<String>
        let reset: Bool
        let edits: [Edit]
    }
    private(set) var revision = 0
    private(set) var keys: [String] = []
    private(set) var rows: [String: Row] = [:]
    private(set) var indices: [String: Int] = [:]
    private(set) var stickyIndices: [Int] = []

    func prepare(_ packet: [String: Any]) throws -> Patch {
        func invalid() -> Error { NativeDecodeError.invalid("Invalid or stale list patch") }
        func integer(_ value: Any?) -> Int? {
            guard let n = value as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID(), n.doubleValue.isFinite,
                  abs(n.doubleValue) <= 9_007_199_254_740_991, n.doubleValue.rounded() == n.doubleValue else { return nil }
            return n.intValue
        }
        func decodeRow(_ raw: Any) throws -> Row {
            guard let values = raw as? [Any], values.count == 4,
                  let key = values[0] as? String, !key.isEmpty,
                  let version = integer(values[1]), version > 0,
                  let extent = values[2] as? NSNumber, CFGetTypeID(extent) != CFBooleanGetTypeID(), extent.doubleValue.isFinite, extent.doubleValue > 0,
                  let sticky = values[3] as? NSNumber, CFGetTypeID(sticky) == CFBooleanGetTypeID() else { throw invalid() }
            return Row(key: key, revision: version, extent: extent.doubleValue, sticky: sticky.boolValue)
        }
        guard Set(packet.keys) == ["base", "revision", "changes"], integer(packet["base"]) == revision,
              let next = integer(packet["revision"]), next == revision + 1,
              let changes = packet["changes"] as? [[Any]] else { throw invalid() }
        var order: [String]?
        var changed: [String: Row] = [:]
        var deleted: Set<String> = []
        var reset = false
        var edits: [Edit] = []
        func exists(_ key: String) -> Bool { !deleted.contains(key) && (changed[key] != nil || (!reset && rows[key] != nil)) }
        for change in changes {
            guard let code = change.first as? String else { throw invalid() }
            switch code {
            case "reset":
                guard change.count == 2, edits.isEmpty, changed.isEmpty, !reset, let values = change[1] as? [Any] else { throw invalid() }
                reset = true; order = []
                for value in values {
                    let row = try decodeRow(value)
                    guard changed[row.key] == nil else { throw invalid() }
                    changed[row.key] = row; order!.append(row.key)
                }
                edits.append(Edit(code: code, from: 0, to: 0))
            case "i":
                guard change.count == 3, let index = integer(change[1]) else { throw invalid() }
                let row = try decodeRow(change[2])
                guard !exists(row.key), index >= 0, index <= (order?.count ?? keys.count) else { throw invalid() }
                if order == nil { order = keys }
                order!.insert(row.key, at: index); changed[row.key] = row; deleted.remove(row.key)
                edits.append(Edit(code: code, from: index, to: index))
            case "u":
                guard change.count == 2 else { throw invalid() }
                let row = try decodeRow(change[1])
                guard exists(row.key) else { throw invalid() }
                changed[row.key] = row
            case "d", "m":
                guard change.count == (code == "d" ? 2 : 3), let key = change[1] as? String, exists(key) else { throw invalid() }
                if order == nil { order = keys }
                guard let old = order!.firstIndex(of: key) else { throw invalid() }
                if code == "d" {
                    order!.remove(at: old); changed.removeValue(forKey: key); deleted.insert(key)
                    edits.append(Edit(code: code, from: old, to: old))
                } else {
                    guard let index = integer(change[2]), index >= 0, index < order!.count else { throw invalid() }
                    order!.remove(at: old); order!.insert(key, at: index)
                    edits.append(Edit(code: code, from: old, to: index))
                }
            default: throw invalid()
            }
        }
        return Patch(base: revision, revision: next, order: order, changed: changed, deleted: deleted, reset: reset, edits: edits)
    }

    func publish(_ patch: Patch) {
        precondition(patch.base == revision)
        let stickyChanged = patch.changed.contains { rows[$0.key]?.sticky != $0.value.sticky }
        if patch.reset { rows = patch.changed }
        else {
            for key in patch.deleted { rows.removeValue(forKey: key) }
            for (key, value) in patch.changed { rows[key] = value }
        }
        if let order = patch.order {
            keys = order
            indices = Dictionary(uniqueKeysWithValues: keys.enumerated().map { ($0.element, $0.offset) })
        }
        if patch.order != nil || stickyChanged { stickyIndices = keys.indices.filter { rows[keys[$0]]!.sticky } }
        revision = patch.revision
    }

    func sticky(at index: Int) -> Int {
        var low = 0, high = stickyIndices.count
        while low < high {
            let mid = (low + high) / 2
            if stickyIndices[mid] <= index { low = mid + 1 } else { high = mid }
        }
        return low > 0 ? stickyIndices[low - 1] : -1
    }
}
