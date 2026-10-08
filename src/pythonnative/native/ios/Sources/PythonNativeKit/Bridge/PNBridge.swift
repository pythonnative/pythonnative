import Foundation
import UIKit

/// The version of the wire protocol compiled into this library. Python
/// refuses to start when `pythonnative.bridge.PROTOCOL_VERSION` differs.
public let PNProtocolVersion = Int32(PNContracts.protocolVersion)

/// The C signature Python registers through `pn_bridge_set_callback`:
/// `(kind, tag, name, payload_json)`. Python handles every message
/// asynchronously and returns nothing.
public typealias PNCallbackFn = @convention(c) (
    UnsafePointer<CChar>?, Int64, UnsafePointer<CChar>?, UnsafePointer<CChar>?
) -> Void

/// Swift-side entry point for the reverse direction (native -> Python) and
/// the owner of the registered C callback.
public final class PNBridge {
    public static let shared = PNBridge()

    private let pythonQueue = DispatchQueue(label: "dev.pythonnative.events")
    private static let continuousEvents: Set<String> = ["on_scroll", "on_window", "on_selection_change", "on_gesture_update"]
    private struct Message {
        let kind: String; let tag: Int64; let name: String; let payload: String
        /// Whether a newer message for the same view and event replaces this
        /// one. Computed once, before the mailbox lock is taken.
        let continuous: Bool
        init(kind: String, tag: Int64, name: String, payload: String) {
            self.kind = kind; self.tag = tag; self.name = name; self.payload = payload
            if kind != "event" {
                continuous = false
            } else if PNBridge.continuousEvents.contains(name) {
                continuous = true
            } else if name.hasPrefix("gesture:"), let args = PNJSON.decodeObject(payload)["args"] as? [[String: Any]] {
                continuous = args.first?["state"] as? String == "changed"
            } else {
                continuous = false
            }
        }
    }
    private let mailboxLock = NSLock()
    private var mailbox: [Message] = []
    private var draining = false
    private var callback: PNCallbackFn?
    private var registrationWaiters: [() -> Void] = []

    private init() {
        // Reference every exported entry point so the linker never
        // dead-strips them out of the host executable; Python resolves
        // them through `dlsym` at runtime.
        _ = PNBridge.exportedSymbols
    }

    /// Whether Python has registered its callback yet.
    public var hasCallback: Bool { callback != nil }

    /// Install (or clear) the Python callback. Delivers the messages queued
    /// before it existed, then runs any pending `whenCallbackRegistered`
    /// blocks.
    public func setCallback(_ fn: PNCallbackFn?) {
        mailboxLock.lock()
        callback = fn
        mailboxLock.unlock()
        guard fn != nil else { return }
        scheduleDrain()
        let waiters = registrationWaiters
        registrationWaiters = []
        for waiter in waiters { waiter() }
    }

    /// Run `block` immediately if the callback is registered, otherwise
    /// once it is. Used to buffer deep links and other early events.
    public func whenCallbackRegistered(_ block: @escaping () -> Void) {
        if callback != nil {
            block()
        } else {
            registrationWaiters.append(block)
        }
    }

    /// Queue one message for Python. Messages are delivered in order on the
    /// events queue; consecutive continuous events for the same view
    /// coalesce. Messages sent before Python registers its callback wait
    /// for it. Python never answers.
    public func callPython(kind: String, tag: Int64, name: String, payload: String) {
        let encoded = kind == "layout" ? PNJSON.encode(PNCommit.layout(PNJSON.decode(payload) ?? [])) : payload
        let message = Message(kind: kind, tag: tag, name: name, payload: encoded)
        mailboxLock.lock()
        if message.continuous, let last = mailbox.last, last.continuous,
           last.tag == tag, last.name == name {
            mailbox[mailbox.count - 1] = message
        } else { mailbox.append(message) }
        mailboxLock.unlock()
        scheduleDrain()
    }

    private func scheduleDrain() {
        mailboxLock.lock()
        let schedule = !draining && callback != nil && !mailbox.isEmpty
        if schedule { draining = true }
        mailboxLock.unlock()
        if schedule { pythonQueue.async { [self] in drainMailbox() } }
    }

    private func drainMailbox() {
        while true {
            mailboxLock.lock()
            guard let callback = callback, !mailbox.isEmpty else {
                draining = false
                mailboxLock.unlock()
                return
            }
            let message = mailbox.removeFirst()
            mailboxLock.unlock()
            message.kind.withCString { kind in
                message.name.withCString { name in
                    message.payload.withCString { payload in
                        callback(kind, message.tag, name, payload)
                    }
                }
            }
        }
    }

    static func onUI<T>(_ body: () -> T) -> T {
        if Thread.isMainThread { return body() }
        return DispatchQueue.main.sync(execute: body)
    }

    /// Emit a view event: `callback("event", tag, name, args_array_json)`.
    public func emitEvent(tag: Int64, name: String, args: [Any?]) {
        PNAnimationGraph.event(tag, name, args)
        var editRevision = 0
        if name == "on_change", let view = PNViewRegistry.shared.view(for: tag),
           view is UITextInput, let state = PNViewState.existing(for: view) {
            editRevision = (state.extras["edit_revision"] as? Int ?? 0) + 1
            state.extras["edit_revision"] = editRevision
        }
        callPython(kind: "event", tag: tag, name: name, payload: PNCommit.event(args, editRevision: editRevision))
    }

    /// Copy a Swift string into a `strdup`'d buffer Python frees via `pn_bridge_free`.
    static func duplicate(_ string: String?) -> UnsafeMutablePointer<CChar>? {
        guard let string = string else { return nil }
        return strdup(string)
    }

    private static let exportedSymbols: [Any] = [
        pn_bridge_apply as Any,
        pn_bridge_command as Any,
        pn_bridge_animate as Any,
        pn_bridge_call as Any,
        pn_bridge_free as Any,
        pn_bridge_set_callback as Any,
        pn_bridge_protocol_version as Any,
    ]
}

// MARK: - C exports

/// Apply one serialized transaction (a JSON array of ops).
@_cdecl("pn_bridge_apply")
public func pn_bridge_apply(_ transactionJSON: UnsafePointer<CChar>?) -> UnsafeMutablePointer<CChar>? {
    guard let transactionJSON = transactionJSON else { return nil }
    let json = String(cString: transactionJSON)
    let started = DispatchTime.now().uptimeNanoseconds
    let envelope = PNJSON.decodeObject(json)
    let decoded = DispatchTime.now().uptimeNanoseconds
    return PNBridge.onUI {
        let mounted = DispatchTime.now().uptimeNanoseconds
        var reply = PNCommit.apply(envelope)
        var metrics = reply["metrics"] as? [String: Any] ?? [:]
        metrics["decode_ns"] = decoded - started; metrics["queue_ns"] = mounted - decoded
        reply["metrics"] = metrics
        return PNBridge.duplicate(PNJSON.encode(reply))
    }
}

/// Run an imperative command on one view; returns an optional JSON result.
@_cdecl("pn_bridge_command")
public func pn_bridge_command(
    _ tag: Int64, _ name: UnsafePointer<CChar>?, _ argsJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    return PNBridge.onUI {

    guard let name = name, let record = PNViewRegistry.shared.resolve(tag) else { return nil }
    let args = PNJSON.decodeObject(argsJSON.map { String(cString: $0) })
    guard PNContracts.validateCommand(record.typeName, String(cString: name), args) else {
        return PNBridge.duplicate(PNJSON.encode(["error": "Invalid view command"]))
    }
    let result = record.manager.command(view: record.view, name: String(cString: name), args: args)
    guard let result = result else { return nil }
    return PNBridge.duplicate(PNJSON.encode(result))
    }
}

/// Drive a view's animatable properties (`set` / `start` / `cancel`).
@_cdecl("pn_bridge_animate")
public func pn_bridge_animate(
    _ tag: Int64, _ requestJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    return PNBridge.onUI {

    let request = PNJSON.decodeObject(requestJSON.map { String(cString: $0) })
    let result = PNAnimator.shared.handle(tag: tag, request: request)
    guard let result = result else { return nil }
    return PNBridge.duplicate(PNJSON.encode(result))
    }
}

/// Call a native module method. The result is `{"ok":..}`, `{"pending":true}`, or an error envelope.
@_cdecl("pn_bridge_call")
public func pn_bridge_call(
    _ module: UnsafePointer<CChar>?, _ method: UnsafePointer<CChar>?, _ argsJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    return PNBridge.onUI {

    guard let module = module, let method = method else {
        return PNBridge.duplicate(PNJSON.encode(["ok": false, "error": "missing module or method"]))
    }
    let envelope = PNJSON.decodeObject(argsJSON.map { String(cString: $0) })
    if String(cString: module) == "Runtime" {
        return PNBridge.duplicate(PNJSON.encode(["ok": true, "value": [
            "protocol": PNContracts.protocolVersion, "yoga": PNContracts.yogaVersion, "schema": PNContracts.fingerprint,
            "animation_graph": true, "logical_lists": true, "native_layout": true]]))
    }
    if String(cString: module) == "Layout" {
        return PNBridge.duplicate(PNJSON.encode(["ok": true, "value": PNCommit.layout(PNLayout.compute(envelope["args"] as? [String: Any] ?? [:]))]))
    }
    let result = PNModuleDispatcher.shared.call(
        module: String(cString: module), method: String(cString: method), envelope: envelope
    )
    return PNBridge.duplicate(PNJSON.encode(result))
    }
}

/// Free a string previously returned by a `pn_bridge_*` function.
@_cdecl("pn_bridge_free")
public func pn_bridge_free(_ ptr: UnsafeMutablePointer<CChar>?) {
    free(ptr)
}

/// Register the Python callback used for every native -> Python message.
@_cdecl("pn_bridge_set_callback")
public func pn_bridge_set_callback(_ fn: PNCallbackFn?) {
    PNBridge.onUI {

    PNRegistry.shared.ensureBuiltins()
    PNBridge.shared.setCallback(fn)
    }
}

/// The protocol version this library speaks.
@_cdecl("pn_bridge_protocol_version")
public func pn_bridge_protocol_version() -> Int32 {
    PNProtocolVersion
}
