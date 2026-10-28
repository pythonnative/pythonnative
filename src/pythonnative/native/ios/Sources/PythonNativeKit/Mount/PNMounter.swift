import UIKit
import PNCore

/// The UI thread's side of the renderer core: drains mount transactions and
/// applies them through the component managers (RFC 0007).
///
/// The core has already validated, laid out, and flattened every op, so the
/// mounter only creates widgets, applies props, moves children, and sets
/// frames. It keeps the mounted parent and child lists itself, which
/// `recreate` needs to rebuild a widget in place.
public enum PNMounter {
    private static let scheduleLock = NSLock()
    private static var scheduled = false
    private static var draining = false
    private static var parents: [Int64: Int64] = [:]
    private static var children: [Int64: [Int64]] = [:]

    /// Ask for a drain on the main queue; safe from any thread, coalesced.
    public static func schedule() {
        scheduleLock.lock()
        let needed = !scheduled
        scheduled = true
        scheduleLock.unlock()
        if needed { DispatchQueue.main.async { drain() } }
    }

    /// Apply every queued transaction. Runs on the main thread.
    public static func drain() {
        dispatchPrecondition(condition: .onQueue(.main))
        scheduleLock.lock()
        scheduled = false
        scheduleLock.unlock()
        guard !draining else { return }
        draining = true
        defer { draining = false }
        var bytes = pn_bytes()
        var id: UInt64 = 0
        while pn_core_mount_next(PNCore.handle, &bytes, &id) != 0 {
            var failure: String?
            do {
                let transaction = try PNMountDecoder.decode(UnsafeRawPointer(bytes.data!), count: bytes.size)
                failure = apply(transaction.ops)
            } catch {
                failure = "\(error)"
            }
            if let failure = failure {
                PNLog.rateLimited(PNLog.bridge, key: "mount", "[mount] \(failure)")
                failure.withCString { pn_core_mount_finished(PNCore.handle, id, $0) }
            } else {
                pn_core_mount_finished(PNCore.handle, id, nil)
            }
            applyWrites()
        }
    }

    /// Apply animated prop writes the core's animator produced.
    public static func applyWrites() {
        var bytes = pn_bytes()
        guard pn_core_take_writes(PNCore.handle, &bytes) != 0, let base = bytes.data,
              let writes = try? PNMountDecoder.writes(UnsafeRawPointer(base), count: bytes.size) else { return }
        let registry = PNViewRegistry.shared
        for (tag, prop, value) in writes {
            guard let record = registry.resolve(tag) else { continue }
            record.manager.setAnimatedProperty(view: record.view, prop: prop, value: value)
        }
    }

    /// The mounted parent of `tag`, as the core arranged it.
    public static func parent(of tag: Int64) -> Int64? { parents[tag] }

    /// The mounted children of `tag`, in order.
    public static func childTags(of tag: Int64) -> [Int64] { children[tag] ?? [] }

    // MARK: - Applying

    /// Apply decoded ops; returns a failure description, or nil.
    static func apply(_ ops: [PNMountOp]) -> String? {
        let registry = PNViewRegistry.shared
        for op in ops {
            _ = PNValues.takeDecodeFailure()
            var subject: (Int64, String?) = (0, nil)
            switch op {
            case .reset:
                for record in registry.allRecords() { destroy(record) }
                registry.removeAll()
                parents.removeAll()
                children.removeAll()
            case let .create(tag, component, props):
                subject = (tag, component)
                guard registry.resolve(tag) == nil else { return "duplicate create: \(tag)" }
                guard let manager = PNRegistry.shared.manager(for: component) else { return "unknown component: \(component)" }
                let view = manager.createView(tag: tag, props: props)
                registry.register(PNViewRecord(tag: tag, typeName: component, view: view, manager: manager))
                manager.didCreate(view: view, tag: tag, props: props)
            case let .update(tag, recreate, changed, removed):
                guard let record = registry.resolve(tag) else { return "unknown tag: \(tag)" }
                subject = (tag, record.typeName)
                if recreate {
                    self.recreate(record, changed: changed, removed: removed)
                } else {
                    var target = PNViewState.existing(for: record.view)?.props ?? [:]
                    for (key, value) in changed { target[key] = value }
                    for key in removed { target.removeValue(forKey: key) }
                    record.manager.update(view: record.view, changed: changed)
                    PNViewState.existing(for: record.view)?.props = target
                }
            case let .insert(parentTag, childTag, index):
                guard let parent = registry.resolve(parentTag), let child = registry.resolve(childTag) else {
                    return "unknown tag in insert: \(parentTag) -> \(childTag)"
                }
                subject = (parentTag, parent.typeName)
                if let old = parents[childTag], old != parentTag {
                    if let previous = registry.resolve(old) { previous.manager.removeChild(parent: previous.view, child: child.view) }
                    children[old]?.removeAll { $0 == childTag }
                }
                var siblings = children[parentTag] ?? []
                siblings.removeAll { $0 == childTag }
                siblings.insert(childTag, at: max(0, min(index, siblings.count)))
                children[parentTag] = siblings
                parents[childTag] = parentTag
                parent.manager.insertChild(parent: parent.view, child: child.view, index: index)
            case let .delete(tag):
                guard let record = registry.unregister(tag) else { continue }
                if let parentTag = parents.removeValue(forKey: tag) {
                    children[parentTag]?.removeAll { $0 == tag }
                    if let parent = registry.resolve(parentTag) {
                        parent.manager.removeChild(parent: parent.view, child: record.view)
                    }
                }
                for child in children.removeValue(forKey: tag) ?? [] { parents.removeValue(forKey: child) }
                destroy(record)
            case let .frame(tag, x, y, width, height):
                guard let record = registry.resolve(tag) else { continue }
                record.manager.setFrame(view: record.view, x: x, y: y, w: width, h: height)
                PNVirtualListManager.measured(tag, CGSize(width: width, height: height))
            case let .command(tag, name, arguments, callId):
                var reply: [String: Any] = ["call_id": callId, "ok": true, "value": NSNull()]
                if let record = registry.resolve(tag) {
                    reply["value"] = record.manager.command(view: record.view, name: name, args: arguments) ?? NSNull()
                } else {
                    reply = ["call_id": callId, "ok": false, "error": "view \(tag) is gone"]
                }
                PNBridge.shared.callPython(kind: "command", tag: 0, name: "", payload: PNJSON.encode(reply))
            }
            if let failure = PNValues.takeDecodeFailure() {
                return "props for \(subject.1 ?? "view") tag \(subject.0): \(failure)"
            }
        }
        return nil
    }

    private static func destroy(_ record: PNViewRecord) {
        record.manager.destroy(view: record.view)
        PNViewState.detach(record.view)
    }

    /// Replace a physical widget while retaining its logical tag and children.
    private static func recreate(_ record: PNViewRecord, changed: [String: Any], removed: [String]) {
        let registry = PNViewRegistry.shared
        let old = record.view
        var props = PNViewState.existing(for: old)?.props ?? [:]
        for (key, value) in changed { props[key] = value }
        for key in removed { props.removeValue(forKey: key) }
        let parent = parents[record.tag].flatMap { registry.resolve($0) }
        let index = parent.flatMap { children[$0.tag]?.firstIndex(of: record.tag) } ?? 0
        let kids = (children[record.tag] ?? []).compactMap { registry.resolve($0) }
        let superview = old.superview
        let physicalIndex = superview?.subviews.firstIndex(of: old) ?? 0
        let focused = old.isFirstResponder
        let input = old as? UITextInput
        let selection = input.flatMap { input in
            input.selectedTextRange.map { range in
                (input.offset(from: input.beginningOfDocument, to: range.start), input.offset(from: input.beginningOfDocument, to: range.end))
            }
        }
        // End the previous input session before moving focus to a new widget.
        // UIKit can otherwise finish an old composition in the new responder.
        if focused && record.typeName == "TextInput" { old.resignFirstResponder() }
        for child in kids { record.manager.removeChild(parent: old, child: child.view) }
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
        for (position, child) in kids.enumerated() {
            record.manager.insertChild(parent: replacement, child: child.view, index: position)
        }
        if let parent = parent {
            parent.manager.insertChild(parent: parent.view, child: replacement, index: index)
        } else {
            superview?.insertSubview(replacement, at: min(physicalIndex, superview?.subviews.count ?? 0))
        }
        record.manager.destroy(view: old)
        PNViewState.detach(old)
        if focused { replacement.becomeFirstResponder() }
        if let selection = selection, record.typeName == "TextInput" {
            _ = record.manager.command(view: replacement, name: "set_selection", args: ["start": selection.0, "end": selection.1])
        }
    }
}
