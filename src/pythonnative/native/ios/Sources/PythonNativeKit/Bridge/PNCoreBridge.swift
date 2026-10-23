import UIKit
import PNCore

/// The process's renderer core and the surface every host mounts into.
public enum PNCore {
    public static let handle: OpaquePointer? = pn_core_shared()
    public static let surface: Int64 = 1
}

/// Registers PythonNativeKit as the renderer core's platform (RFC 0007).
///
/// The core calls these from the Python commit worker and its own layout
/// work; none of them blocks on the core. The main thread never waits on
/// another thread, so a worker may hop to it synchronously to measure a
/// widget.
public enum PNCoreBridge {
    private static let workQueue = DispatchQueue(label: "dev.pythonnative.core", qos: .userInitiated)
    private static var installed = false
    private static let installLock = NSLock()

    /// The renderer core's protocol version (Python checks it at handshake).
    public static var protocolVersion: Int { Int(pn_core_protocol_version()) }

    /// Install the platform callbacks. Call before Python starts; idempotent.
    public static func install() {
        installLock.lock()
        defer { installLock.unlock() }
        if installed { return }
        installed = true
        PNTextLayout.captureEnvironment()
        var platform = pn_platform()
        platform.context = nil
        platform.schedule_mount = { _ in PNMounter.schedule() }
        platform.schedule_work = { _ in PNCoreBridge.workQueue.async { pn_core_work(PNCore.handle) } }
        platform.request_frames = { _ in DispatchQueue.main.async { PNFrameClock.shared.start() } }
        platform.measure = { _, request, size in
            guard let request = request, let size = size else { return }
            size.pointee = PNMeasurement.measure(request.pointee)
        }
        platform.baseline = { _, _, tag, _, height in PNMeasurement.baseline(tag: tag, height: height) }
        platform.emit = { _, kind, _, tag, name, payload in
            PNBridge.shared.callPython(
                kind: kind.map { String(cString: $0) } ?? "", tag: tag,
                name: name.map { String(cString: $0) } ?? "", payload: payload.map { String(cString: $0) } ?? ""
            )
        }
        pn_core_set_platform(PNCore.handle, &platform)
        _ = exportedSymbols
        let update = { pn_core_set_reduce_motion(PNCore.handle, UIAccessibility.isReduceMotionEnabled ? 1 : 0) }
        PNMain.run(update)
        NotificationCenter.default.addObserver(
            forName: UIAccessibility.reduceMotionStatusDidChangeNotification, object: nil, queue: .main
        ) { _ in update() }
        NotificationCenter.default.addObserver(
            forName: UIContentSizeCategory.didChangeNotification, object: nil, queue: .main
        ) { _ in PNCoreBridge.contentSizeCategoryChanged() }
    }

    /// Report the frame (in window coordinates) of the container a detached
    /// root lays out in: a stack screen, a modal's content, a portal.
    public static func reportContainer(tag: Int64, view: UIView) {
        let frame = view.window.map { view.convert(view.bounds, to: $0) } ?? view.bounds
        guard frame.width > 0, frame.height > 0 else { return }
        pn_core_report_container(PNCore.handle, PNCore.surface, tag, Float(frame.minX), Float(frame.minY),
                                 Float(frame.width), Float(frame.height))
    }

    /// Report a leaf's loaded content size (an image) so the core relayouts.
    public static func reportIntrinsic(tag: Int64, size: CGSize) {
        pn_core_report_intrinsic(PNCore.handle, PNCore.surface, tag, Float(size.width), Float(size.height))
    }

    /// Ask the core to measure one leaf again (a text input's content changed).
    public static func invalidate(tag: Int64) {
        pn_core_invalidate(PNCore.handle, PNCore.surface, tag)
    }

    private static func contentSizeCategoryChanged() {
        PNTextLayout.captureEnvironment()
        for record in PNViewRegistry.shared.allRecords() where ["Text", "TextInput", "Button"].contains(record.typeName) {
            let props = PNViewState.existing(for: record.view)?.props ?? [:]
            record.manager.update(view: record.view, changed: ["font_size": props["font_size"] ?? 17])
        }
        pn_core_invalidate_measurements(PNCore.handle)
    }

    /// Python binds these with `ctypes.CDLL(None)`; referencing them keeps
    /// the linker from stripping any (the template exports `_pn_core_*`).
    private static let exportedSymbols: [Any] = [
        pn_core_shared as Any, pn_core_protocol_version as Any, pn_core_set_platform as Any,
        pn_core_load_contracts as Any, pn_core_contract_fingerprint as Any, pn_core_set_flattening as Any,
        pn_core_reset as Any, pn_core_free as Any, pn_core_commit as Any, pn_core_layout as Any,
        pn_core_command as Any, pn_core_animate as Any, pn_core_measure as Any, pn_core_inspect as Any,
        pn_core_validate_module as Any, pn_core_work as Any, pn_core_mount_next as Any,
        pn_core_mount_finished as Any, pn_core_is_mounted as Any, pn_core_report_container as Any,
        pn_core_report_intrinsic as Any, pn_core_invalidate as Any, pn_core_invalidate_measurements as Any,
        pn_core_event as Any, pn_core_animation_frame as Any, pn_core_take_writes as Any,
        pn_core_set_reduce_motion as Any, pn_core_pointer as Any, pn_core_gesture_deadline as Any,
        pn_core_gesture_poll as Any, pn_core_has_gestures as Any, pn_core_list_apply as Any,
        pn_core_list_count as Any, pn_core_list_revision as Any, pn_core_list_key as Any, pn_core_list_index as Any,
        pn_core_list_extent as Any, pn_core_list_sticky as Any, pn_core_list_row_revision as Any,
        pn_core_list_sticky_at as Any, pn_core_check_value as Any,
    ]
}

/// Drives the core's animator once per display frame while animations run.
final class PNFrameClock: NSObject {
    static let shared = PNFrameClock()
    private var link: CADisplayLink?

    func start() {
        guard link == nil else { return }
        let display = CADisplayLink(target: self, selector: #selector(tick(_:)))
        display.add(to: .main, forMode: .common)
        link = display
    }

    @objc private func tick(_ display: CADisplayLink) {
        let running = pn_core_animation_frame(PNCore.handle, display.timestamp * 1000)
        PNMounter.applyWrites()
        if running == 0 {
            link?.invalidate()
            link = nil
        }
    }
}

/// Leaf measurement on behalf of the core.
enum PNMeasurement {
    private static let lock = NSLock()
    private static var ascenders: [Int64: CGFloat] = [:]

    static func measure(_ request: pn_measure_request) -> pn_size {
        let props = PNMountDecoder.props(UnsafeRawPointer(request.props.data), count: request.props.size)
        let component = request.component.map { String(cString: $0) } ?? ""
        let maxW = request.width_mode == Int32(PN_MEASURE_UNDEFINED) || !request.width.isFinite ? CGFloat.infinity : CGFloat(request.width)
        let maxH = request.height_mode == Int32(PN_MEASURE_UNDEFINED) || !request.height.isFinite ? CGFloat.infinity : CGFloat(request.height)
        let size: CGSize
        switch Int(request.mode) {
        case Int(PN_MEASURE_TEXT):
            let layout = PNTextLayout(props)
            size = layout.measure(maxWidth: maxW, maxHeight: maxH)
            lock.lock()
            ascenders[request.tag] = layout.ascender
            lock.unlock()
        case Int(PN_MEASURE_NATIVE):
            let manager = onMain { PNRegistry.shared.manager(for: component) }
            size = manager?.measureNative(props: props, maxW: maxW, maxH: maxH) ?? .zero
        default:
            let tag = request.tag
            size = onMain {
                PNRegistry.shared.manager(for: component)?.measureIntrinsic(props: props, tag: tag, maxW: maxW, maxH: maxH) ?? .zero
            }
        }
        return pn_size(width: Float(size.width.isFinite ? max(0, size.width) : 0), height: Float(size.height.isFinite ? max(0, size.height) : 0))
    }

    static func baseline(tag: Int64, height: Float) -> Float {
        lock.lock()
        defer { lock.unlock() }
        return ascenders[tag].map { Float($0) } ?? height
    }

    private static func onMain<T>(_ body: () -> T) -> T {
        Thread.isMainThread ? body() : DispatchQueue.main.sync(execute: body)
    }
}
