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
/// Only PNCommit may submit validated operation batches.
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

    enum MountError: Error { case duplicateTag(Int64), missingTag(Int64), missingManager(String) }

    /// Apply a validated batch; runtime inconsistencies fail the entire surface.
    static func apply(_ ops: [Op]) throws {
        let registry = PNViewRegistry.shared
        for op in ops {
            switch op {
            case let .create(tag, type, props):
                if registry.resolve(tag) != nil {
                    throw MountError.duplicateTag(tag)
                }
                guard let manager = PNRegistry.shared.manager(for: type) else {
                    throw MountError.missingManager(type)
                }
                let view = manager.createView(tag: tag, props: props)
                registry.register(PNViewRecord(tag: tag, typeName: type, view: view, manager: manager))
                manager.didCreate(view: view, tag: tag, props: props)

            case let .update(tag, changed):
                guard let record = registry.resolve(tag) else {
                    throw MountError.missingTag(tag)
                }
                let normalized = PNContracts.normalize(record.typeName, changed)
                if PNContracts.requiresRecreation(record.typeName, changed) {
                    recreate(record, changed: normalized)
                } else {
                    record.manager.update(view: record.view, changed: normalized)
                }

            case let .insert(parent, child, index):
                guard let parentRecord = registry.resolve(parent), let childRecord = registry.resolve(child) else {
                    throw MountError.missingTag(child)
                }
                parentRecord.manager.insertChild(parent: parentRecord.view, child: childRecord.view, index: index)

            case let .destroy(tag):
                PNAnimationGraph.forget(tag)
                guard let record = registry.unregister(tag) else { continue }
                if let parentTag = PNLayout.nodes[tag]?.parent, let parentRecord = registry.resolve(parentTag) {
                    parentRecord.manager.removeChild(parent: parentRecord.view, child: record.view)
                } else if let parent = record.view.superview,
                          let state = PNViewState.existing(for: parent), let parentRecord = registry.resolve(state.tag) {
                    parentRecord.manager.removeChild(parent: parent, child: record.view)
                }
                record.manager.destroy(view: record.view)
                PNViewState.detach(record.view)

            case let .frame(tag, x, y, w, h):
                guard let record = registry.resolve(tag) else { throw MountError.missingTag(tag) }
                record.manager.setFrame(view: record.view, x: x, y: y, w: w, h: h)
            }
            // Later operations in this batch need the current logical owners,
            // especially when replacing a container after moving its children.
            PNLayout.observe([op])
        }
    }
    /// Replace a physical widget while retaining its logical tag and children.
    private static func recreate(_ record: PNViewRecord, changed: [String: Any]) {
        let registry = PNViewRegistry.shared
        let old = record.view
        var props = PNViewState.existing(for: old)?.props ?? [:]
        for (key, value) in changed {
            if value is NSNull { props.removeValue(forKey: key) } else { props[key] = value }
        }
        let parent = PNLayout.nodes[record.tag]?.parent.flatMap { registry.resolve($0) }
        let siblings = parent.flatMap { PNLayout.nodes[$0.tag]?.children } ?? []
        let index = siblings.firstIndex(of: record.tag) ?? 0
        let children = (PNLayout.nodes[record.tag]?.children ?? []).compactMap { registry.resolve($0) }
        let superview = old.superview
        let physicalIndex = superview?.subviews.firstIndex(of: old) ?? 0
        let focused = old.isFirstResponder
        let input = old as? UITextInput
        let selection = input?.selectedTextRange.map { range in
            (input!.offset(from: input!.beginningOfDocument, to: range.start), input!.offset(from: input!.beginningOfDocument, to: range.end))
        }
        // End the previous input session before moving focus to a new widget.
        // UIKit can otherwise finish an old composition in the new responder.
        if focused && record.typeName == "TextInput" { old.resignFirstResponder() }
        for child in children { record.manager.removeChild(parent: old, child: child.view) }
        if let parent = parent { parent.manager.removeChild(parent: parent.view, child: old) }
        let edited = PNViewState.existing(for: old)?.extras["edit_revision"] as? Int ?? 0
        if record.typeName == "TextInput", changed["value"] == nil || (PNProps.int(changed["_pn_edit_revision"]) ?? 0) < edited {
            props["value"] = (old as? UITextField)?.text ?? (old as? UITextView)?.text ?? ""
        }
        let replacement = record.manager.createView(tag: record.tag, props: props)
        replacement.frame = old.frame
        registry.register(PNViewRecord(tag: record.tag, typeName: record.typeName, view: replacement, manager: record.manager))
        record.manager.didCreate(view: replacement, tag: record.tag, props: props)
        if record.typeName == "TextInput" { PNViewState.existing(for: replacement)?.extras["edit_revision"] = edited }
        for (index, child) in children.enumerated() { record.manager.insertChild(parent: replacement, child: child.view, index: index) }
        if let parent = parent { parent.manager.insertChild(parent: parent.view, child: replacement, index: index) }
        else { superview?.insertSubview(replacement, at: min(physicalIndex, superview?.subviews.count ?? 0)) }
        record.manager.destroy(view: old)
        PNViewState.detach(old)
        if focused { replacement.becomeFirstResponder() }
        if let selection = selection, record.typeName == "TextInput" {
            _ = record.manager.command(view: replacement, name: "set_selection", args: ["start": selection.0, "end": selection.1])
        }
    }

}
