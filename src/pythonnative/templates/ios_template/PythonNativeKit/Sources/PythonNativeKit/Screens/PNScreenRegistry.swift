import UIKit

/// Screen id <-> `PNViewController` table.
///
/// Python addresses screens by the integer id assigned here; the
/// controller is held weakly so a popped screen is reclaimed normally.
public final class PNScreenRegistry {
    public static let shared = PNScreenRegistry()

    private final class WeakBox {
        weak var controller: PNViewController?
        init(_ controller: PNViewController) { self.controller = controller }
    }

    private var screens: [Int64: WeakBox] = [:]
    private var nextId: Int64 = 1

    private init() {}

    /// Assign a fresh id to `controller`.
    func register(_ controller: PNViewController) -> Int64 {
        let id = nextId
        nextId += 1
        screens[id] = WeakBox(controller)
        return id
    }

    /// Forget `id` (called from the controller's deinit).
    func unregister(_ id: Int64) {
        screens.removeValue(forKey: id)
    }

    /// The controller for `id`, if it's still alive.
    public func controller(for id: Int64) -> PNViewController? {
        guard let box = screens[id] else { return nil }
        if box.controller == nil {
            screens.removeValue(forKey: id)
        }
        return box.controller
    }

    /// Ids of every live screen.
    public var screenIds: [Int64] {
        screens.compactMap { $0.value.controller == nil ? nil : $0.key }.sorted()
    }
}
