import Foundation

/// One op of a mount transaction (see `include/pn_core.h`).
public enum PNMountOp {
    case reset
    case create(tag: Int64, component: String, props: [String: Any])
    case update(tag: Int64, recreate: Bool, changed: [String: Any], removed: [String])
    case insert(parent: Int64, child: Int64, index: Int)
    case delete(tag: Int64)
    case frame(tag: Int64, x: Double, y: Double, width: Double, height: Double)
    case command(tag: Int64, name: String, arguments: [String: Any], callId: Int64)
}

/// A decoded mount transaction.
public struct PNMountTransaction {
    public let surface: Int64
    public let revision: Int64
    public let id: Int64
    public let ops: [PNMountOp]
}

public enum PNMountDecodeError: Error, CustomStringConvertible {
    case truncated
    case malformed(String)

    public var description: String {
        switch self {
        case .truncated: return "truncated mount transaction"
        case .malformed(let message): return "malformed mount transaction: \(message)"
        }
    }
}

/// Little-endian reader over the core's binary formats.
struct PNByteReader {
    private let base: UnsafeRawPointer
    private let count: Int
    private(set) var offset = 0

    init(_ base: UnsafeRawPointer, count: Int) {
        self.base = base
        self.count = count
    }

    private mutating func take<T: FixedWidthInteger>(_: T.Type) throws -> T {
        let size = MemoryLayout<T>.size
        guard offset + size <= count else { throw PNMountDecodeError.truncated }
        var value: T = 0
        withUnsafeMutableBytes(of: &value) { $0.copyMemory(from: UnsafeRawBufferPointer(start: base + offset, count: size)) }
        offset += size
        return T(littleEndian: value)
    }

    mutating func u8() throws -> UInt8 { try take(UInt8.self) }
    mutating func u16() throws -> UInt16 { try take(UInt16.self) }
    mutating func u32() throws -> UInt32 { try take(UInt32.self) }
    mutating func i64() throws -> Int64 { try take(Int64.self) }
    mutating func f64() throws -> Double { Double(bitPattern: try take(UInt64.self)) }

    mutating func string() throws -> String {
        let length = Int(try u32())
        guard offset + length <= count else { throw PNMountDecodeError.truncated }
        let text = String(decoding: UnsafeRawBufferPointer(start: base + offset, count: length), as: UTF8.self)
        offset += length
        return text
    }

    /// One encoded value as the Foundation types managers read; `"inf"` and
    /// `"-inf"` become infinite doubles, as Python's codec spells them.
    mutating func value() throws -> Any {
        switch try u8() {
        case 0: return NSNull()
        case 1: return false
        case 2: return true
        case 3: return NSNumber(value: try i64())
        case 4: return NSNumber(value: try f64())
        case 5:
            let text = try string()
            if text == "inf" { return Double.infinity }
            if text == "-inf" { return -Double.infinity }
            return text
        case 6:
            let n = Int(try u32())
            var items: [Any] = []
            items.reserveCapacity(n)
            for _ in 0..<n { items.append(try value()) }
            return items
        case 7:
            let n = Int(try u32())
            var members: [String: Any] = [:]
            members.reserveCapacity(n)
            for _ in 0..<n {
                let key = try string()
                members[key] = try value()
            }
            return members
        case let kind:
            throw PNMountDecodeError.malformed("value kind \(kind)")
        }
    }

    mutating func object() throws -> [String: Any] {
        guard let members = try value() as? [String: Any] else { throw PNMountDecodeError.malformed("expected an object") }
        return members
    }
}

public enum PNMountDecoder {
    static let magic: UInt32 = 0x544D_4E50  // "PNMT"

    /// Decode a transaction the core produced.
    public static func decode(_ base: UnsafeRawPointer, count: Int) throws -> PNMountTransaction {
        var reader = PNByteReader(base, count: count)
        guard try reader.u32() == magic else { throw PNMountDecodeError.malformed("bad magic") }
        guard try reader.u16() == 1 else { throw PNMountDecodeError.malformed("unknown format") }
        _ = try reader.u16()
        let surface = try reader.i64(), revision = try reader.i64(), id = try reader.i64()
        let opCount = Int(try reader.u32())
        var ops: [PNMountOp] = []
        ops.reserveCapacity(opCount)
        for _ in 0..<opCount {
            switch try reader.u8() {
            case 0:
                ops.append(.reset)
            case 1:
                let tag = try reader.i64()
                let component = try reader.string()
                ops.append(.create(tag: tag, component: component, props: try reader.object()))
            case 2:
                let tag = try reader.i64()
                let flags = try reader.u8()
                let changed = try reader.object()
                let removedCount = Int(try reader.u32())
                var removed: [String] = []
                for _ in 0..<removedCount { removed.append(try reader.string()) }
                ops.append(.update(tag: tag, recreate: flags & 1 != 0, changed: changed, removed: removed))
            case 3:
                let parent = try reader.i64(), child = try reader.i64()
                ops.append(.insert(parent: parent, child: child, index: Int(try reader.u32())))
            case 5:
                ops.append(.delete(tag: try reader.i64()))
            case 6:
                let tag = try reader.i64()
                ops.append(.frame(tag: tag, x: try reader.f64(), y: try reader.f64(), width: try reader.f64(), height: try reader.f64()))
            case 7:
                let tag = try reader.i64()
                let name = try reader.string()
                let arguments = try reader.value() as? [String: Any] ?? [:]
                ops.append(.command(tag: tag, name: name, arguments: arguments, callId: try reader.i64()))
            case let code:
                throw PNMountDecodeError.malformed("op \(code)")
            }
        }
        return PNMountTransaction(surface: surface, revision: revision, id: id, ops: ops)
    }

    /// Decode animated writes: `(tag, prop, value)` in order.
    public static func writes(_ base: UnsafeRawPointer, count: Int) throws -> [(Int64, String, Any)] {
        var reader = PNByteReader(base, count: count)
        let n = Int(try reader.u32())
        var out: [(Int64, String, Any)] = []
        out.reserveCapacity(n)
        for _ in 0..<n {
            let tag = try reader.i64()
            let prop = try reader.string()
            out.append((tag, prop, try reader.value()))
        }
        return out
    }

    /// Decode one encoded props object (measurement requests carry these).
    public static func props(_ base: UnsafeRawPointer?, count: Int) -> [String: Any] {
        guard let base = base, count > 0 else { return [:] }
        var reader = PNByteReader(base, count: count)
        return (try? reader.object()) ?? [:]
    }
}
