import Foundation
import UIKit

/// The version of the wire protocol compiled into this library. Python
/// refuses to start when `pythonnative.bridge.PROTOCOL_VERSION` differs.
public let PNProtocolVersion: Int32 = 1

/// The C signature Python registers through `pn_bridge_set_callback`.
///
/// `(kind, tag, name, payload_json) -> optional JSON string owned by
/// Python and valid until the next callback returns`.
public typealias PNCallbackFn = @convention(c) (
    UnsafePointer<CChar>?, Int64, UnsafePointer<CChar>?, UnsafePointer<CChar>?
) -> UnsafePointer<CChar>?

/// Swift-side entry point for the reverse direction (native -> Python) and
/// the owner of the registered C callback.
public final class PNBridge {
    public static let shared = PNBridge()

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

    /// Install (or clear) the Python callback. Runs any pending
    /// `whenCallbackRegistered` blocks when a callback becomes available.
    public func setCallback(_ fn: PNCallbackFn?) {
        callback = fn
        guard fn != nil else { return }
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

    /// Invoke the Python callback. Returns the JSON string Python returned
    /// (copied immediately), or `nil` when Python returned NULL or no
    /// callback is registered.
    @discardableResult
    public func callPython(kind: String, tag: Int64, name: String, payload: String) -> String? {
        PNBridge.ensureMainThread("callPython(\(kind))")
        guard let callback = callback else {
            PNLog.rateLimited(PNLog.bridge, key: "no-callback", "callPython(\(kind), \(name)) dropped: no Python callback registered")
            return nil
        }
        let result: UnsafePointer<CChar>? = kind.withCString { kindPtr in
            name.withCString { namePtr in
                payload.withCString { payloadPtr in
                    callback(kindPtr, tag, namePtr, payloadPtr)
                }
            }
        }
        guard let result = result else { return nil }
        return String(cString: result)
    }

    /// Emit a view event: `callback("event", tag, name, args_array_json)`.
    @discardableResult
    public func emitEvent(tag: Int64, name: String, args: [Any?]) -> String? {
        callPython(kind: "event", tag: tag, name: name, payload: PNJSON.encode(args))
    }

    /// Log when an entry point is reached off the main thread. Python
    /// always calls from the main thread, so this only guards misuse.
    static func ensureMainThread(_ context: String) {
        if !Thread.isMainThread {
            PNLog.rateLimited(PNLog.bridge, key: "off-main:\(context)", "\(context) called off the main thread; running inline")
        }
    }

    /// Copy a Swift string into a `strdup`'d buffer Python frees via `pn_bridge_free`.
    static func duplicate(_ string: String?) -> UnsafeMutablePointer<CChar>? {
        guard let string = string else { return nil }
        return strdup(string)
    }

    private static let exportedSymbols: [Any] = [
        pn_bridge_apply as Any,
        pn_bridge_measure as Any,
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
public func pn_bridge_apply(_ transactionJSON: UnsafePointer<CChar>?) {
    PNBridge.ensureMainThread("pn_bridge_apply")
    guard let transactionJSON = transactionJSON else { return }
    PNTransaction.apply(String(cString: transactionJSON))
}

/// Measure the view with `tag` under the given constraints (`1e6` means unconstrained).
@_cdecl("pn_bridge_measure")
public func pn_bridge_measure(
    _ tag: Int64, _ maxW: Double, _ maxH: Double,
    _ outW: UnsafeMutablePointer<Double>?, _ outH: UnsafeMutablePointer<Double>?
) {
    PNBridge.ensureMainThread("pn_bridge_measure")
    var size = CGSize.zero
    if let record = PNViewRegistry.shared.resolve(tag) {
        size = record.manager.measure(view: record.view, maxW: CGFloat(maxW), maxH: CGFloat(maxH))
    }
    outW?.pointee = size.width.isFinite ? Double(size.width) : 0
    outH?.pointee = size.height.isFinite ? Double(size.height) : 0
}

/// Run an imperative command on one view; returns an optional JSON result.
@_cdecl("pn_bridge_command")
public func pn_bridge_command(
    _ tag: Int64, _ name: UnsafePointer<CChar>?, _ argsJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    PNBridge.ensureMainThread("pn_bridge_command")
    guard let name = name, let record = PNViewRegistry.shared.resolve(tag) else { return nil }
    let args = PNJSON.decodeObject(argsJSON.map { String(cString: $0) })
    let result = record.manager.command(view: record.view, name: String(cString: name), args: args)
    guard let result = result else { return nil }
    return PNBridge.duplicate(PNJSON.encode(result))
}

/// Drive a view's animatable properties (`set` / `start` / `cancel`).
@_cdecl("pn_bridge_animate")
public func pn_bridge_animate(
    _ tag: Int64, _ requestJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    PNBridge.ensureMainThread("pn_bridge_animate")
    let request = PNJSON.decodeObject(requestJSON.map { String(cString: $0) })
    let result = PNAnimator.shared.handle(tag: tag, request: request)
    guard let result = result else { return nil }
    return PNBridge.duplicate(PNJSON.encode(result))
}

/// Call a native module method. The result is `{"ok":..}`, `{"pending":true}`, or an error envelope.
@_cdecl("pn_bridge_call")
public func pn_bridge_call(
    _ module: UnsafePointer<CChar>?, _ method: UnsafePointer<CChar>?, _ argsJSON: UnsafePointer<CChar>?
) -> UnsafeMutablePointer<CChar>? {
    PNBridge.ensureMainThread("pn_bridge_call")
    guard let module = module, let method = method else {
        return PNBridge.duplicate(PNJSON.encode(["ok": false, "error": "missing module or method"]))
    }
    let envelope = PNJSON.decodeObject(argsJSON.map { String(cString: $0) })
    let result = PNModuleDispatcher.shared.call(
        module: String(cString: module), method: String(cString: method), envelope: envelope
    )
    return PNBridge.duplicate(PNJSON.encode(result))
}

/// Free a string previously returned by a `pn_bridge_*` function.
@_cdecl("pn_bridge_free")
public func pn_bridge_free(_ ptr: UnsafeMutablePointer<CChar>?) {
    free(ptr)
}

/// Register the Python callback used for every native -> Python message.
@_cdecl("pn_bridge_set_callback")
public func pn_bridge_set_callback(_ fn: PNCallbackFn?) {
    PNBridge.ensureMainThread("pn_bridge_set_callback")
    PNRegistry.shared.ensureBuiltins()
    PNBridge.shared.setCallback(fn)
}

/// The protocol version this library speaks.
@_cdecl("pn_bridge_protocol_version")
public func pn_bridge_protocol_version() -> Int32 {
    PNProtocolVersion
}
