import CryptoKit
import UIKit

/// `Image`: a `UIImageView` loading from http(s) URLs (with memory and
/// disk caching), local file paths, bundle asset names, and base64 data URIs.
public final class PNImageManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let view = UIImageView(frame: .zero)
        view.clipsToBounds = true
        view.contentMode = .scaleAspectFit
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let imageView = view as? UIImageView else { return }
        if let tint = PNColor.parse(PNProps.value(props, "tint_color") ?? PNProps.value(props, "tint")) {
            imageView.tintColor = tint
            if let image = imageView.image {
                imageView.image = image.withRenderingMode(.alwaysTemplate)
            }
        }
        if let placeholder = PNColor.parse(PNProps.value(props, "placeholder_color")) {
            imageView.backgroundColor = placeholder
        }
        if let source = PNProps.string(PNProps.value(props, "source")), !source.isEmpty {
            load(imageView, source: source)
        }
        if let mode = PNProps.string(PNProps.value(props, "scale_type") ?? PNProps.value(props, "resize_mode")) {
            imageView.contentMode = PNImageManager.contentMode(mode)
        }
        PNViewStyler.applyCommon(imageView, props)
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
        state.extras["pending_source"] = source
        if source.hasPrefix("data:") {
            loadDataURI(imageView, source)
        } else if source.hasPrefix("http://") || source.hasPrefix("https://") {
            PNImageLoader.shared.fetch(source) { [weak imageView] result in
                guard let imageView = imageView, PNViewState.existing(for: imageView)?.extras["pending_source"] as? String == source else { return }
                switch result {
                case .success(let data):
                    if let image = PNImageManager.decode(data, targetSize: imageView.bounds.size) {
                        self.setImage(imageView, image)
                        PNEvents.emit(imageView, "on_load", [["width": Double(image.size.width), "height": Double(image.size.height)]])
                    } else {
                        PNEvents.emit(imageView, "on_error", ["decode failed"])
                    }
                case .failure(let error):
                    PNEvents.emit(imageView, "on_error", [error.localizedDescription])
                }
            }
        } else {
            var image = UIImage(named: source)
            if image == nil {
                let path = source.hasPrefix("file://") ? (URL(string: source)?.path ?? source) : source
                image = UIImage(contentsOfFile: path)
            }
            if let image = image {
                setImage(imageView, image)
                PNEvents.emit(imageView, "on_load", [["width": Double(image.size.width), "height": Double(image.size.height)]])
            } else {
                PNEvents.emit(imageView, "on_error", ["image '\(source)' not found"])
            }
        }
    }

    private func setImage(_ imageView: UIImageView, _ image: UIImage) {
        let tinted = PNProps.value(mergedProps(imageView), "tint_color") ?? PNProps.value(mergedProps(imageView), "tint")
        imageView.image = tinted != nil ? image.withRenderingMode(.alwaysTemplate) : image
    }

    private func loadDataURI(_ imageView: UIImageView, _ source: String) {
        guard let comma = source.firstIndex(of: ","),
              let data = Data(base64Encoded: String(source[source.index(after: comma)...]), options: [.ignoreUnknownCharacters]),
              let image = UIImage(data: data)
        else {
            PNEvents.emit(imageView, "on_error", ["data URI decode failed"])
            return
        }
        setImage(imageView, image)
        PNEvents.emit(imageView, "on_load", [["width": Double(image.size.width), "height": Double(image.size.height)]])
    }

    /// Decode `data`, downsampling when the bitmap is more than 2x the target.
    static func decode(_ data: Data, targetSize: CGSize) -> UIImage? {
        guard let image = UIImage(data: data) else { return nil }
        guard targetSize.width > 0, targetSize.height > 0 else { return image }
        let size = image.size
        if size.width <= targetSize.width * 2, size.height <= targetSize.height * 2 { return image }
        let scale = min(targetSize.width * 2 / size.width, targetSize.height * 2 / size.height)
        let newSize = CGSize(width: size.width * scale, height: size.height * scale)
        let renderer = UIGraphicsImageRenderer(size: newSize)
        return renderer.image { _ in image.draw(in: CGRect(origin: .zero, size: newSize)) }
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

        public var errorDescription: String? {
            switch self {
            case .badURL: return "invalid image URL"
            case .http(let code): return "HTTP \(code)"
            case .empty: return "empty response"
            }
        }
    }

    private let memory = NSCache<NSString, NSData>()
    private var inflight: [String: [(Result<Data, Error>) -> Void]] = [:]
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
    public func fetch(_ url: String, completion: @escaping (Result<Data, Error>) -> Void) {
        if let cached = memory.object(forKey: url as NSString) {
            completion(.success(cached as Data))
            return
        }
        if inflight[url] != nil {
            inflight[url]?.append(completion)
            return
        }
        inflight[url] = [completion]
        let path = cachePath(for: url)
        queue.async {
            if let data = try? Data(contentsOf: path), !data.isEmpty {
                self.deliver(url, .success(data))
                return
            }
            guard let remote = URL(string: url) else {
                self.deliver(url, .failure(LoadError.badURL))
                return
            }
            let task = self.session.dataTask(with: remote) { data, response, error in
                if let error = error {
                    self.deliver(url, .failure(error))
                    return
                }
                if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                    self.deliver(url, .failure(LoadError.http(http.statusCode)))
                    return
                }
                guard let data = data, !data.isEmpty else {
                    self.deliver(url, .failure(LoadError.empty))
                    return
                }
                try? data.write(to: path, options: [.atomic])
                self.deliver(url, .success(data))
            }
            task.resume()
        }
    }

    /// Remove every cached image (memory and disk).
    public func clear() {
        memory.removeAllObjects()
        try? FileManager.default.removeItem(at: directory)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    private func deliver(_ url: String, _ result: Result<Data, Error>) {
        DispatchQueue.main.async {
            if case .success(let data) = result {
                self.memory.setObject(data as NSData, forKey: url as NSString, cost: data.count)
            }
            let waiters = self.inflight.removeValue(forKey: url) ?? []
            for waiter in waiters { waiter(result) }
        }
    }

    private func cachePath(for url: String) -> URL {
        let digest = SHA256.hash(data: Data(url.utf8)).map { String(format: "%02x", $0) }.joined()
        let ext = URL(string: url)?.pathExtension ?? ""
        return directory.appendingPathComponent(ext.isEmpty ? digest : "\(digest).\(ext)")
    }
}
