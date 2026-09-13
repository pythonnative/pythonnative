import CryptoKit
import ImageIO
import UIKit

/// `Image`: a `UIImageView` loading from http(s) URLs (with memory and
/// disk caching), local file paths, bundle asset names, and base64 data URIs.
public final class PNImageManager: PNTypedComponentManager<ImageProps> {
    public init() { super.init(ImageProps.self) }

    public override func makeView(props: [String: Any]) -> UIView {
        let view = UIImageView(frame: .zero)
        view.clipsToBounds = true
        view.contentMode = .scaleAspectFit
        return view
    }

    public override func applyTyped(view: UIView, props: ImageProps, initial: Bool) {
        guard let imageView = view as? UIImageView else { return }
        if props.has_tint_color {
            imageView.tintColor = props.tint_color.flatMap { PNColor.parse(PNValues.encode($0)) }
            if let image = imageView.image {
                imageView.image = image.withRenderingMode(props.tint_color == nil ? .alwaysOriginal : .alwaysTemplate)
            }
        }
        if props.has_placeholder_color {
            imageView.backgroundColor = props.placeholder_color.flatMap { PNColor.parse(PNValues.encode($0)) }
        }
        if props.has_source {
            (PNViewState.existing(for: imageView)?.extras.removeValue(forKey: "cancel_image") as? (() -> Void))?()
            if let source = props.source, !source.isEmpty { load(imageView, source: source) }
            else {
                PNViewState.existing(for: imageView)?.extras.removeValue(forKey: "pending_source")
                PNViewState.existing(for: imageView)?.extras.removeValue(forKey: "image_request")
                imageView.image = nil
            }
        }
        if props.has_scale_type {
            imageView.contentMode = Self.contentMode(props.scale_type.map { PNValues.encode($0) as? String ?? "contain" } ?? "contain")
        }
        PNViewStyler.applyCommon(imageView, props.values)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        guard let image = (view as? UIImageView)?.image else { return .zero }
        var size = image.size
        if maxW.isFinite, maxW > 0, size.width > maxW {
            let scale = maxW / size.width
            size = CGSize(width: maxW, height: size.height * scale)
        }
        return size
    }

    static func contentMode(_ name: String) -> UIView.ContentMode {
        switch name {
        case "cover": return .scaleAspectFill
        case "stretch": return .scaleToFill
        case "center": return .center
        case "repeat": return .scaleAspectFill
        default: return .scaleAspectFit
        }
    }

    // MARK: - Loading

    private func load(_ imageView: UIImageView, source: String) {
        guard let state = PNViewState.existing(for: imageView) else { return }
        let request = UUID()
        state.extras["image_request"] = request
        state.extras["pending_source"] = source
        if source.hasPrefix("http://") || source.hasPrefix("https://") {
            let size = imageView.bounds.size
            state.extras["cancel_image"] = PNImageLoader.shared.fetch(source) { [weak imageView] result in
                DispatchQueue.global(qos: .userInitiated).async {
                    let decoded = result.flatMap { data -> Result<UIImage, Error> in
                        guard let image = PNImageManager.decode(data, targetSize: size) else { return .failure(PNImageLoader.LoadError.decode) }
                        return .success(image)
                    }
                    DispatchQueue.main.async {
                        guard let imageView = imageView,
                              PNViewState.existing(for: imageView)?.extras["image_request"] as? UUID == request else { return }
                        switch decoded {
                        case .success(let image):
                            self.setImage(imageView, image)
                            PNComponentEvents.Image.on_load(imageView, PNImageLoadEvent(width: Double(image.size.width), height: Double(image.size.height)))
                        case .failure(let error): PNComponentEvents.Image.on_error(imageView, error.localizedDescription)
                        }
                    }
                }
            }
        } else if !source.hasPrefix("data:"), let image = UIImage(named: source) {
            setImage(imageView, image)
            PNComponentEvents.Image.on_load(imageView, PNImageLoadEvent(width: Double(image.size.width), height: Double(image.size.height)))
        } else {
            let size = imageView.bounds.size
            let work = DispatchWorkItem { [weak imageView] in
                let result: Result<UIImage, Error> = Result {
                    let data: Data
                    if source.hasPrefix("data:") {
                        guard source.utf8.count <= 90 * 1024 * 1024, let comma = source.firstIndex(of: ","),
                              let decoded = Data(base64Encoded: String(source[source.index(after: comma)...])) else {
                            throw PNImageLoader.LoadError.decode
                        }
                        data = decoded
                    } else {
                        let path = source.hasPrefix("file://") ? (URL(string: source)?.path ?? source) : source
                        data = try Data(contentsOf: URL(fileURLWithPath: path), options: [.mappedIfSafe])
                    }
                    guard data.count <= 64 * 1024 * 1024, let image = Self.decode(data, targetSize: size) else {
                        throw PNImageLoader.LoadError.decode
                    }
                    return image
                }
                DispatchQueue.main.async {
                    guard let imageView = imageView,
                          PNViewState.existing(for: imageView)?.extras["image_request"] as? UUID == request else { return }
                    switch result {
                    case .success(let image):
                        self.setImage(imageView, image)
                        PNComponentEvents.Image.on_load(imageView, PNImageLoadEvent(width: Double(image.size.width), height: Double(image.size.height)))
                    case .failure(let error): PNComponentEvents.Image.on_error(imageView, error.localizedDescription)
                    }
                }
            }
            state.extras["cancel_image"] = { work.cancel() }
            DispatchQueue.global(qos: .userInitiated).async(execute: work)
        }
    }

    private func setImage(_ imageView: UIImageView, _ image: UIImage) {
        let tinted = PNProps.value(mergedProps(imageView), "tint_color")
        imageView.image = tinted != nil ? image.withRenderingMode(.alwaysTemplate) : image
        if let state = PNViewState.existing(for: imageView) { PNLayout.invalidate(state.tag) }
    }

    /// Decode with ImageIO before allocating a full bitmap; cap either edge at 4096 pixels.
    static func decode(_ data: Data, targetSize: CGSize) -> UIImage? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let maximum = targetSize.width > 0 && targetSize.height > 0 ? max(targetSize.width, targetSize.height) * 3 : 2048
        let options: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceThumbnailMaxPixelSize: min(4096, maximum)]
        guard let bitmap = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else { return nil }
        return UIImage(cgImage: bitmap)
    }

    public override func teardown(view: UIView) {
        let extras = PNViewState.existing(for: view)
        (extras?.extras.removeValue(forKey: "cancel_image") as? (() -> Void))?()
        extras?.extras.removeValue(forKey: "image_request")
        extras?.extras.removeValue(forKey: "pending_source")
    }
}

/// Shared image pipeline: memory LRU + disk cache under `Caches/pn_images`,
/// request deduplication, delivery on the main queue.
public final class PNImageLoader {
    public static let shared = PNImageLoader()

    public enum LoadError: Error, LocalizedError {
        case badURL
        case http(Int)
        case empty
        case decode

        public var errorDescription: String? {
            switch self {
            case .badURL: return "invalid image URL"
            case .http(let code): return "HTTP \(code)"
            case .empty: return "Image response is empty or exceeds 64 MB"
            case .decode: return "Image decode failed"
            }
        }
    }

    private let memory = NSCache<NSString, NSData>()
    private final class Request {
        var callbacks: [UUID: (Result<Data, Error>) -> Void] = [:]
        var task: URLSessionTask?
    }
    private var inflight: [String: Request] = [:]
    private let diskLimit = 64 * 1024 * 1024
    private let session: URLSession
    private let queue = DispatchQueue(label: "com.pythonnative.images", qos: .utility)
    private lazy var directory: URL = {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? URL(fileURLWithPath: NSTemporaryDirectory())
        let dir = caches.appendingPathComponent("pn_images", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    private init() {
        memory.totalCostLimit = 16 * 1024 * 1024
        let config = URLSessionConfiguration.default
        config.requestCachePolicy = .returnCacheDataElseLoad
        session = URLSession(configuration: config)
    }

    /// Fetch `url`, delivering the raw bytes on the main queue.
    @discardableResult public func fetch(_ url: String, completion: @escaping (Result<Data, Error>) -> Void) -> () -> Void {
        if let cached = memory.object(forKey: url as NSString) { completion(.success(cached as Data)); return {} }
        let id = UUID()
        let request: Request
        if let existing = inflight[url] { request = existing }
        else {
            request = Request()
            inflight[url] = request
            let path = cachePath(for: url)
            queue.async {
                if let data = try? Data(contentsOf: path), !data.isEmpty {
                    self.deliver(url, request, .success(data))
                    return
                }
                DispatchQueue.main.async {
                    guard self.inflight[url] === request else { return }
                    guard let remote = URL(string: url) else {
                        self.deliver(url, request, .failure(LoadError.badURL)); return
                    }
                    let task = self.session.downloadTask(with: remote) { file, response, error in
                        if let error = error { self.deliver(url, request, .failure(error)); return }
                        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                            self.deliver(url, request, .failure(LoadError.http(http.statusCode))); return
                        }
                        guard let file = file,
                              let size = try? file.resourceValues(forKeys: [.fileSizeKey]).fileSize,
                              size > 0, size <= self.diskLimit,
                              let data = try? Data(contentsOf: file, options: [.mappedIfSafe]) else {
                            self.deliver(url, request, .failure(LoadError.empty)); return
                        }
                        self.queue.async {
                            try? data.write(to: path, options: [.atomic])
                            self.trimDisk()
                            self.deliver(url, request, .success(data))
                        }
                    }
                    request.task = task
                    task.resume()
                }
            }
        }
        request.callbacks[id] = completion
        return { [weak self, weak request] in
            PNMain.run {
                guard let self = self, let request = request, self.inflight[url] === request else { return }
                request.callbacks.removeValue(forKey: id)
                if request.callbacks.isEmpty {
                    self.inflight.removeValue(forKey: url)
                    request.task?.cancel()
                }
            }
        }
    }

    /// Remove every cached image (memory and disk).
    public func clear() {
        memory.removeAllObjects()
        queue.async {
            try? FileManager.default.removeItem(at: self.directory)
            try? FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
        }
    }

    private func deliver(_ url: String, _ request: Request, _ result: Result<Data, Error>) {
        DispatchQueue.main.async {
            guard self.inflight[url] === request else { return }
            self.inflight.removeValue(forKey: url)
            if case .success(let data) = result { self.memory.setObject(data as NSData, forKey: url as NSString, cost: data.count) }
            for callback in request.callbacks.values { callback(result) }
            request.callbacks.removeAll()
        }
    }

    private func trimDisk() {
        let files = (try? FileManager.default.contentsOfDirectory(at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey])) ?? []
        let entries = files.compactMap { url -> (URL, Date, Int)? in
            guard let values = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey]) else { return nil }
            return (url, values.contentModificationDate ?? .distantPast, values.fileSize ?? 0)
        }.sorted { $0.1 < $1.1 }
        var total = entries.reduce(0) { $0 + $1.2 }
        for (url, _, size) in entries where total > diskLimit {
            try? FileManager.default.removeItem(at: url)
            total -= size
        }
    }

    private func cachePath(for url: String) -> URL {
        let digest = SHA256.hash(data: Data(url.utf8)).map { String(format: "%02x", $0) }.joined()
        let ext = URL(string: url)?.pathExtension ?? ""
        return directory.appendingPathComponent(ext.isEmpty ? digest : "\(digest).\(ext)")
    }
}
