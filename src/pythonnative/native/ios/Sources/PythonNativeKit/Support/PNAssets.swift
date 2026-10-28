import CoreText
import UIKit

/// Resolves `asset://` URIs against the bundled `app/assets/` directory
/// and, while connected to `pn start`, the dev overlay that shadows it.
///
/// The bundle ships a `pn_assets.json` manifest written by `pn build`
/// that lists every file, groups density variants (`logo@2x.png`), and
/// carries the parsed font faces. The overlay manifest arrives over the
/// bridge through the `Assets` module. Resolution looks in the overlay
/// first, then the bundle, and picks the variant closest to the screen
/// scale (preferring the next denser one so images are downsampled, not
/// upsampled).
public final class PNAssets {
    public static let shared = PNAssets()

    /// The URI scheme Python emits for bundled files.
    public static let scheme = "asset://"
    /// Posted on the main queue after `configure` swaps the overlay.
    public static let didChange = Notification.Name("PNAssetsDidChange")

    /// One resolved file: where it lives and the density it was drawn for.
    public struct Resolved: Equatable {
        public let url: URL
        public let scale: CGFloat
        public let path: String
    }

    private struct Root {
        let directory: URL
        let manifest: PNAssetManifest?
    }

    private let lock = NSLock()
    private var overlay: Root?
    private var bundled: Root?
    private var registeredFonts: Set<String> = []
    private var faces: [PNFontFace] = []
    private(set) public var generation = 0

    init(bundleRoot: URL? = nil) {
        let root = bundleRoot ?? Bundle.main.resourceURL?.appendingPathComponent("app/assets", isDirectory: true)
        if let root = root, FileManager.default.fileExists(atPath: root.path) {
            bundled = Root(directory: root, manifest: Self.readManifest(root))
        }
        rebuildFonts()
    }

    // MARK: - Configuration

    /// Point the resolver at a dev overlay (or clear it with `nil`).
    public func configure(overlay directory: String?, manifest: PNAssetManifest?) {
        lock.lock()
        if let directory = directory, !directory.isEmpty {
            overlay = Root(directory: URL(fileURLWithPath: directory, isDirectory: true), manifest: manifest)
        } else {
            overlay = nil
        }
        generation += 1
        lock.unlock()
        rebuildFonts()
        PNMain.run { NotificationCenter.default.post(name: PNAssets.didChange, object: self) }
    }

    /// Whether `value` is an `asset://` URI.
    public static func isAssetURI(_ value: String?) -> Bool {
        value?.hasPrefix(scheme) == true
    }

    /// The asset path named by a URI (`asset://images/a.png` -> `images/a.png`).
    public static func path(of uri: String) -> String {
        var text = uri
        if text.hasPrefix(scheme) { text.removeFirst(scheme.count) }
        while text.hasPrefix("/") { text.removeFirst() }
        return text
    }

    // MARK: - Resolution

    /// Resolve a path or URI to a file, preferring the overlay and the best density variant.
    public func resolve(_ pathOrURI: String, scale: CGFloat = PNWindow.screenScale()) -> Resolved? {
        let path = Self.path(of: pathOrURI)
        lock.lock()
        let roots = [overlay, bundled].compactMap { $0 }
        lock.unlock()
        for root in roots {
            if let manifest = root.manifest, let variant = Self.variant(in: manifest, path: path, scale: scale) {
                let url = root.directory.appendingPathComponent(variant)
                if FileManager.default.fileExists(atPath: url.path) {
                    return Resolved(url: url, scale: Self.scale(of: variant), path: variant)
                }
            }
            let url = root.directory.appendingPathComponent(path)
            if FileManager.default.fileExists(atPath: url.path) {
                return Resolved(url: url, scale: Self.scale(of: path), path: path)
            }
        }
        return nil
    }

    /// Whether some copy of `pathOrURI` exists.
    public func exists(_ pathOrURI: String) -> Bool {
        resolve(pathOrURI) != nil
    }

    /// Read the bytes of an asset (the base file, not a density variant).
    public func read(_ pathOrURI: String) throws -> Data {
        let path = Self.path(of: pathOrURI)
        lock.lock()
        let roots = [overlay, bundled].compactMap { $0 }
        lock.unlock()
        for root in roots {
            let url = root.directory.appendingPathComponent(path)
            if FileManager.default.fileExists(atPath: url.path) { return try Data(contentsOf: url) }
        }
        throw PNAssetError.notFound(path)
    }

    /// Pick the manifest variant of `path` for `scale`, or nil when the manifest has no entry.
    static func variant(in manifest: PNAssetManifest, path: String, scale: CGFloat) -> String? {
        let base = baseName(path)
        if let group = manifest.variants[base], !group.isEmpty {
            var options: [(CGFloat, String)] = []
            for (key, value) in group {
                if let number = Double(key) { options.append((CGFloat(number), value)) }
            }
            if let exact = options.first(where: { abs($0.0 - scale) < 0.001 }) { return exact.1 }
            let above = options.filter { $0.0 > scale }.sorted { $0.0 < $1.0 }
            if let next = above.first { return next.1 }
            return options.max { $0.0 < $1.0 }?.1
        }
        return manifest.files.contains(base) ? base : nil
    }

    /// `images/logo@2x.png` -> `images/logo.png`.
    static func baseName(_ path: String) -> String {
        let url = URL(fileURLWithPath: path)
        let ext = url.pathExtension
        var stem = url.deletingPathExtension().lastPathComponent
        if let at = stem.lastIndex(of: "@"), stem.hasSuffix("x"), Double(stem[stem.index(after: at)..<stem.index(before: stem.endIndex)]) != nil {
            stem = String(stem[..<at])
        }
        let directory = (path as NSString).deletingLastPathComponent
        let name = ext.isEmpty ? stem : "\(stem).\(ext)"
        return directory.isEmpty ? name : "\(directory)/\(name)"
    }

    /// The density encoded in a variant name (`@2x` -> 2), or 1.
    static func scale(of path: String) -> CGFloat {
        let stem = URL(fileURLWithPath: path).deletingPathExtension().lastPathComponent
        guard let at = stem.lastIndex(of: "@"), stem.hasSuffix("x"),
              let value = Double(stem[stem.index(after: at)..<stem.index(before: stem.endIndex)]) else { return 1 }
        return CGFloat(value)
    }

    // MARK: - Fonts

    /// Every bundled font face (overlay faces shadow bundle faces of the same family/weight/style).
    public var fontFaces: [PNFontFace] {
        lock.lock()
        defer { lock.unlock() }
        return faces
    }

    /// The PostScript name of the best face for `family`, or nil when the family isn't bundled.
    public func fontName(family: String, weight: Int, italic: Bool) -> String? {
        let wanted = family.trimmingCharacters(in: .whitespaces).lowercased()
        let candidates = fontFaces.filter { $0.family.lowercased() == wanted }
        guard !candidates.isEmpty else { return nil }
        let best = candidates.min { lhs, rhs in
            let l = (lhs.italic == italic ? 0 : 1000) + abs(Int(lhs.weight) - weight)
            let r = (rhs.italic == italic ? 0 : 1000) + abs(Int(rhs.weight) - weight)
            return l < r
        }
        return best?.postscript_name
    }

    private func rebuildFonts() {
        lock.lock()
        let roots = [overlay, bundled].compactMap { $0 }
        lock.unlock()
        var merged: [PNFontFace] = []
        var seen: Set<String> = []
        for root in roots {
            for face in root.manifest?.fonts ?? [] {
                let key = "\(face.family.lowercased())|\(face.weight)|\(face.italic)"
                if seen.contains(key) { continue }
                seen.insert(key)
                let url = root.directory.appendingPathComponent(face.path)
                register(url)
                merged.append(face)
            }
        }
        lock.lock()
        faces = merged
        lock.unlock()
    }

    private func register(_ url: URL) {
        lock.lock()
        let already = registeredFonts.contains(url.path)
        if !already { registeredFonts.insert(url.path) }
        lock.unlock()
        if already { return }
        var error: Unmanaged<CFError>?
        if !CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error) {
            let description = (error?.takeRetainedValue()).map { CFErrorCopyDescription($0) as String } ?? "unknown error"
            // Already-registered fonts (bundle plus overlay) report an error that isn't a problem.
            if !description.contains("already") {
                PNLog.rateLimited(PNLog.components, key: "font:\(url.lastPathComponent)", "[assets] could not register \(url.lastPathComponent): \(description)")
            }
        }
    }

    // MARK: - Manifest

    static func readManifest(_ directory: URL) -> PNAssetManifest? {
        let url = directory.appendingPathComponent("pn_assets.json")
        guard let data = try? Data(contentsOf: url),
              let object = try? JSONSerialization.jsonObject(with: data) else { return nil }
        return try? PNValues.decode(PNAssetManifest.self, object)
    }
}

public enum PNAssetError: Error, LocalizedError {
    case notFound(String)

    public var errorDescription: String? {
        switch self {
        case .notFound(let path): return "asset not found: \(path)"
        }
    }
}

/// `Assets`: the bridge face of `PNAssets` (overlay configuration and raw reads).
public final class AssetsModule: AssetsImplementation {
    public init() {}

    public func configure(overlay: String?, manifest: PNAssetManifest) throws {
        PNAssets.shared.configure(overlay: overlay, manifest: manifest)
    }

    public func exists(path: String) throws -> Bool {
        PNAssets.shared.exists(path)
    }

    public func read(path: String) throws -> String? {
        try PNAssets.shared.read(path).base64EncodedString()
    }
}
