import Foundation

/// A named native module callable from Python through `pn_bridge_call`.
public protocol PNNativeModule: AnyObject {
    /// The module name Python addresses (`native_module("Clipboard")`).
    static var name: String { get }
    init()
    /// Handle one method call, settling `promise` now or later.
    func call(_ method: String, args: [String: Any], promise: PNPromise)
}

/// The settlement handle for one module call.
///
/// Resolving or rejecting before `call` returns answers Python inline;
/// settling afterwards posts `callback("module", 0, module,
/// {"call_id": n, "ok": ..., ...})` on the main thread.
public final class PNPromise {
    public let callId: Int64
    public let module: String
    public let method: String

    private(set) var result: [String: Any]?
    private var returned = false
    private let lock = NSLock()

    init(callId: Int64, module: String, method: String) {
        self.callId = callId
        self.module = module
        self.method = method
    }

    /// Whether the promise has been resolved or rejected.
    public var isSettled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return result != nil
    }

    /// Settle successfully with `value` (JSON-encodable or `nil`).
    public func resolve(_ value: Any?) {
        settle(["ok": true, "value": value ?? NSNull()])
    }

    /// Settle with an error message and optional machine-readable code.
    public func reject(_ message: String, code: String? = nil) {
        var envelope: [String: Any] = ["ok": false, "error": message]
        if let code = code { envelope["code"] = code }
        settle(envelope)
    }

    /// Settle from a Swift `Error`.
    public func reject(_ error: Error) {
        reject(error.localizedDescription, code: (error as NSError).domain)
    }

    private func settle(_ envelope: [String: Any]) {
        lock.lock()
        if result != nil {
            lock.unlock()
            PNLog.rateLimited(PNLog.modules, key: "double-settle", "\(module).\(method) settled twice; ignoring")
            return
        }
        result = envelope
        let deliverAsync = returned
        lock.unlock()
        if deliverAsync {
            var payload = envelope
            payload["call_id"] = callId
            let module = self.module
            PNMain.run {
                PNBridge.shared.callPython(kind: "module", tag: 0, name: module, payload: PNJSON.encode(payload))
            }
        }
    }

    /// Called by the dispatcher once `call` returns: the inline result,
    /// or `{"pending": true}` when the module will settle later.
    func takeInlineResult() -> [String: Any] {
        lock.lock()
        defer { lock.unlock() }
        returned = true
        if let result = result { return result }
        return ["pending": true]
    }
}

/// Unsolicited module events: `callback("module", 0, module, {"event", "payload"})`.
public enum PNModuleEvents {
    /// Emit `event` from `module` with `payload` on the main thread.
    public static func emit(module: String, event: String, payload: [String: Any]) {
        PNMain.run {
            PNBridge.shared.callPython(kind: "module", tag: 0, name: module, payload: PNJSON.encode(["event": event, "payload": payload]))
        }
    }
}

/// Main-thread hop that runs inline when already on main.
public enum PNMain {
    public static func run(_ block: @escaping () -> Void) {
        if Thread.isMainThread {
            block()
        } else {
            DispatchQueue.main.async(execute: block)
        }
    }
}

/// Routes `pn_bridge_call` to modules and shapes the reply envelope.
public final class PNModuleDispatcher {
    public static let shared = PNModuleDispatcher()

    private init() {}

    /// Dispatch one call. `envelope` is `{"call_id": n, "args": {...}}`.
    public func call(module: String, method: String, envelope: [String: Any]) -> [String: Any] {
        let callId = Int64(PNProps.int(envelope["call_id"]) ?? 0)
        let args = PNProps.dict(envelope["args"]) ?? [:]
        guard let instance = PNRegistry.shared.module(named: module) else {
            return ["ok": false, "error": "unknown native module '\(module)'", "code": "unknown_module"]
        }
        let promise = PNPromise(callId: callId, module: module, method: method)
        instance.call(method, args: args, promise: promise)
        return promise.takeInlineResult()
    }
}
