import UIKit

/// One live native view addressed by its reconciler tag.
public final class PNViewRecord {
    public let tag: Int64
    public let typeName: String
    public let view: UIView
    public let manager: PNComponentManager

    init(tag: Int64, typeName: String, view: UIView, manager: PNComponentManager) {
        self.tag = tag
        self.typeName = typeName
        self.view = view
        self.manager = manager
    }
}

/// Tag -> view table. Every view created through a transaction is
/// registered here until its `d` op arrives.
public final class PNViewRegistry {
    public static let shared = PNViewRegistry()

    private var records: [Int64: PNViewRecord] = [:]

    private init() {}

    /// The record for `tag`, or `nil` when no such view exists.
    public func resolve(_ tag: Int64) -> PNViewRecord? {
        records[tag]
    }

    /// The registered view for `tag`.
    public func view(for tag: Int64) -> UIView? {
        records[tag]?.view
    }

    /// Number of live records (used by tests and diagnostics).
    public var count: Int { records.count }

    func register(_ record: PNViewRecord) {
        records[record.tag] = record
    }

    @discardableResult
    func unregister(_ tag: Int64) -> PNViewRecord? {
        records.removeValue(forKey: tag)
    }

    /// Drop every record. Intended for tests.
    public func removeAll() {
        records.removeAll()
    }
}
