import ImageIO
import UIKit

/// `Images`: measure, prefetch, and clear images through the shared pipeline.
public final class ImagesModule: ImagesImplementation {
    public init() {}

    public func clear_cache() throws {
        PNImageLoader.shared.clear()
    }

    public func get_size(uri: String, completion: @escaping (Result<PNImageSize, Error>) -> Void) -> (() -> Void)? {
        if PNImageManager.isRemote(uri) {
            return PNImageLoader.shared.fetch(uri) { result in
                DispatchQueue.global(qos: .utility).async {
                    completion(result.flatMap { data in
                        guard let size = Self.pixelSize(data) else { return .failure(PNImageLoader.LoadError.decode) }
                        return .success(PNImageSize(width: Double(size.width), height: Double(size.height)))
                    })
                }
            }
        }
        let work = DispatchWorkItem {
            completion(Result {
                var scale: CGFloat = 1
                let data: Data
                if PNAssets.isAssetURI(uri) {
                    guard let resolved = PNAssets.shared.resolve(uri) else { throw PNAssetError.notFound(PNAssets.path(of: uri)) }
                    scale = resolved.scale
                    data = try Data(contentsOf: resolved.url, options: [.mappedIfSafe])
                } else if uri.hasPrefix("data:") {
                    guard let comma = uri.firstIndex(of: ","),
                          let decoded = Data(base64Encoded: String(uri[uri.index(after: comma)...])) else {
                        throw PNImageLoader.LoadError.decode
                    }
                    data = decoded
                } else {
                    let path = uri.hasPrefix("file://") ? (URL(string: uri)?.path ?? uri) : uri
                    data = try Data(contentsOf: URL(fileURLWithPath: path), options: [.mappedIfSafe])
                }
                guard let size = Self.pixelSize(data) else { throw PNImageLoader.LoadError.decode }
                return PNImageSize(width: Double(size.width / scale), height: Double(size.height / scale))
            })
        }
        DispatchQueue.global(qos: .utility).async(execute: work)
        return { work.cancel() }
    }

    public func prefetch(uri: String, completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        if PNImageManager.isRemote(uri) {
            return PNImageLoader.shared.fetch(uri) { result in
                switch result {
                case .success: completion(.success(true))
                case .failure(let error): completion(.failure(error))
                }
            }
        }
        DispatchQueue.global(qos: .utility).async {
            if PNAssets.isAssetURI(uri) {
                completion(.success(PNAssets.shared.exists(uri)))
            } else if uri.hasPrefix("data:") {
                completion(.success(true))
            } else {
                let path = uri.hasPrefix("file://") ? (URL(string: uri)?.path ?? uri) : uri
                completion(.success(FileManager.default.fileExists(atPath: path)))
            }
        }
        return nil
    }

    /// Pixel dimensions from the image header, honoring EXIF orientation.
    static func pixelSize(_ data: Data) -> CGSize? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
              let width = properties[kCGImagePropertyPixelWidth] as? CGFloat,
              let height = properties[kCGImagePropertyPixelHeight] as? CGFloat else { return nil }
        let orientation = (properties[kCGImagePropertyOrientation] as? UInt32) ?? 1
        return orientation >= 5 ? CGSize(width: height, height: width) : CGSize(width: width, height: height)
    }
}
