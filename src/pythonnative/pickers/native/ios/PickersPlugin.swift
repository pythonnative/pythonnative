import MobileCoreServices
import Photos
import PhotosUI
import UIKit

/// Registers `Pickers` and owns the `photo_library` permission.
public enum PickersPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(PickersModuleAdapter<PickersModule>.self)
        PNPermissions.register("photo_library", PNPhotoLibraryPermission())
    }
}

private func permissionStatus(_ status: PHAuthorizationStatus) -> String {
    switch status {
    case .authorized, .limited: return "granted"
    case .denied, .restricted: return "blocked"
    case .notDetermined: return "undetermined"
    @unknown default: return "undetermined"
    }
}

private final class PNPhotoLibraryPermission: PNPermissionProvider {
    func check(_ done: @escaping (String) -> Void) {
        if #available(iOS 14, *) {
            done(permissionStatus(PHPhotoLibrary.authorizationStatus(for: .readWrite)))
        } else {
            done(permissionStatus(PHPhotoLibrary.authorizationStatus()))
        }
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        // Without the usage string, the system kills the app at the prompt.
        guard Bundle.main.object(forInfoDictionaryKey: "NSPhotoLibraryUsageDescription") != nil else {
            PNLog.modules.error("The photo_library permission isn't declared under [permissions] in pythonnative.toml")
            done("denied")
            return nil
        }
        let finish: (PHAuthorizationStatus) -> Void = { status in
            DispatchQueue.main.async { done(permissionStatus(status)) }
        }
        if #available(iOS 14, *) {
            PHPhotoLibrary.requestAuthorization(for: .readWrite, handler: finish)
        } else {
            PHPhotoLibrary.requestAuthorization(finish)
        }
        return nil
    }
}

/// A picked file's destination: a fresh directory, so that two files with one name can't collide.
private func newPickedFile(named name: String) throws -> URL {
    let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? URL(fileURLWithPath: NSTemporaryDirectory())
    let directory = caches.appendingPathComponent("pn_pickers", isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let safe = (name as NSString).lastPathComponent
    return directory.appendingPathComponent(safe.isEmpty ? "file" : safe)
}

private func mimeType(of url: URL) -> String {
    let fallback = "application/octet-stream"
    let pathExtension = url.pathExtension as CFString
    guard let uti = UTTypeCreatePreferredIdentifierForTag(kUTTagClassFilenameExtension, pathExtension, nil)?.takeRetainedValue() else { return fallback }
    return UTTypeCopyPreferredTagWithClass(uti, kUTTagClassMIMEType)?.takeRetainedValue() as String? ?? fallback
}

private func pickedFile(at url: URL) throws -> PNPickedFile {
    let size = (try FileManager.default.attributesOfItem(atPath: url.path)[.size] as? NSNumber)?.int64Value ?? 0
    return PNPickedFile(mime_type: mimeType(of: url), name: url.lastPathComponent, path: url.path, size: size)
}

/// Copy `source` into the app's cache, re-encoding a JPEG or HEIC photo at
/// `quality` below 1. PNG and GIF keep their bytes for transparency and animation.
private func importFile(from source: URL, name: String, quality: Double?) throws -> PNPickedFile {
    let lowered = source.pathExtension.lowercased()
    if let quality = quality, quality < 1, lowered != "png", lowered != "gif",
       let image = UIImage(contentsOfFile: source.path),
       let data = image.jpegData(compressionQuality: CGFloat(quality)) {
        let stem = ((name as NSString).deletingPathExtension as NSString).lastPathComponent
        let target = try newPickedFile(named: (stem.isEmpty ? "image" : stem) + ".jpg")
        try data.write(to: target, options: [.atomic])
        return try pickedFile(at: target)
    }
    let target = try newPickedFile(named: name)
    try FileManager.default.copyItem(at: source, to: target)
    return try pickedFile(at: target)
}

/// The type identifier the document picker wants for a MIME type or wildcard.
/// iOS's own tables have no entry for a wildcard.
private func typeIdentifier(mime: String) -> String? {
    switch mime.lowercased() {
    case "*/*": return kUTTypeItem as String
    case "image/*": return kUTTypeImage as String
    case "video/*": return kUTTypeMovie as String
    case "audio/*": return kUTTypeAudio as String
    case "text/*": return kUTTypeText as String
    case "application/*": return kUTTypeData as String
    default:
        return UTTypeCreatePreferredIdentifierForTag(kUTTagClassMIMEType, mime as CFString, nil)?.takeRetainedValue() as String?
    }
}

/// `Pickers`: `PHPickerViewController` on iOS 14, `UIImagePickerController`
/// for one item on iOS 13, and `UIDocumentPickerViewController`.
public final class PickersModule: PickersImplementation {
    private var active: AnyObject?
    public init() {}

    private func present(_ completion: @escaping (Result<[PNPickedFile], Error>) -> Void, build: (@escaping (Result<[PNPickedFile], Error>) -> Void) -> (UIViewController, AnyObject)) -> (() -> Void)? {
        guard active == nil else {
            completion(.failure(NSError(domain: "busy", code: 1, userInfo: [NSLocalizedDescriptionKey: "A picker is already open"])))
            return nil
        }
        guard let top = PNWindow.topViewController() else {
            completion(.success([]))
            return nil
        }
        let (controller, session) = build { [weak self] result in
            self?.active = nil
            completion(result)
        }
        active = session
        top.present(controller, animated: true)
        return { [weak self, weak controller] in
            controller?.dismiss(animated: true)
            self?.active = nil
        }
    }

    private func presentMedia(video: Bool, limit: Int64, quality: Double?, completion: @escaping (Result<[PNPickedFile], Error>) -> Void) -> (() -> Void)? {
        present(completion) { done in
            if #available(iOS 14, *) {
                var configuration = PHPickerConfiguration()
                configuration.filter = video ? .videos : .images
                configuration.selectionLimit = Int(limit)
                let picker = PHPickerViewController(configuration: configuration)
                let session = PNPhotoPickerSession(quality: quality, done: done)
                picker.delegate = session
                picker.presentationController?.delegate = session
                return (picker, session)
            }
            let picker = UIImagePickerController()
            picker.sourceType = .photoLibrary
            picker.mediaTypes = [(video ? kUTTypeMovie : kUTTypeImage) as String]
            let session = PNLegacyPickerSession(quality: quality, done: done)
            picker.delegate = session
            picker.presentationController?.delegate = session
            return (picker, session)
        }
    }

    public func pick_images(limit: Int64, quality: Double, completion: @escaping (Result<[PNPickedFile], Error>) -> Void) -> (() -> Void)? {
        presentMedia(video: false, limit: limit, quality: quality, completion: completion)
    }

    public func pick_videos(limit: Int64, completion: @escaping (Result<[PNPickedFile], Error>) -> Void) -> (() -> Void)? {
        presentMedia(video: true, limit: limit, quality: nil, completion: completion)
    }

    public func pick_documents(multiple: Bool, types: [String]?, completion: @escaping (Result<[PNPickedFile], Error>) -> Void) -> (() -> Void)? {
        var identifiers = (types ?? ["*/*"]).compactMap(typeIdentifier(mime:))
        if identifiers.isEmpty { identifiers = [kUTTypeItem as String] }
        return present(completion) { done in
            // `documentTypes:in: .import` copies the file to the app's inbox on
            // every supported iOS, so there's no security scope to manage.
            let picker = UIDocumentPickerViewController(documentTypes: identifiers, in: .import)
            picker.allowsMultipleSelection = multiple
            let session = PNDocumentPickerSession(done: done)
            picker.delegate = session
            picker.presentationController?.delegate = session
            return (picker, session)
        }
    }
}

/// One open picker. Swiping a sheet away calls none of a picker's own
/// delegate methods on some iOS versions, so that counts as a cancel here.
/// Otherwise the module would stay `busy` forever.
private class PNPickerSession: NSObject, UIAdaptivePresentationControllerDelegate {
    private var done: ((Result<[PNPickedFile], Error>) -> Void)?

    init(done: @escaping (Result<[PNPickedFile], Error>) -> Void) {
        self.done = done
    }

    final func finish(_ result: Result<[PNPickedFile], Error>) {
        done?(result)
        done = nil
    }

    /// Copy files off the main thread and settle on it.
    final func importInBackground(_ work: @escaping () throws -> [PNPickedFile]) {
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result(catching: work)
            DispatchQueue.main.async { self.finish(result) }
        }
    }

    func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
        finish(.success([]))
    }
}

@available(iOS 14, *)
private final class PNPhotoPickerSession: PNPickerSession, PHPickerViewControllerDelegate {
    private let quality: Double?

    init(quality: Double?, done: @escaping (Result<[PNPickedFile], Error>) -> Void) {
        self.quality = quality
        super.init(done: done)
    }

    func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
        picker.dismiss(animated: true)
        if results.isEmpty {
            finish(.success([]))
            return
        }
        let group = DispatchGroup()
        let lock = NSLock()
        var files = [PNPickedFile?](repeating: nil, count: results.count)
        var failure: Error?
        let isVideo = quality == nil
        for (index, result) in results.enumerated() {
            let provider = result.itemProvider
            let identifier = (isVideo ? kUTTypeMovie : kUTTypeImage) as String
            guard provider.hasItemConformingToTypeIdentifier(identifier) else { continue }
            group.enter()
            // The provider deletes the file when this callback returns, so the copy happens inside it.
            provider.loadFileRepresentation(forTypeIdentifier: identifier) { url, error in
                defer { group.leave() }
                do {
                    guard let url = url else {
                        throw error ?? NSError(domain: "pick_failed", code: 1, userInfo: [NSLocalizedDescriptionKey: "The picker returned no file"])
                    }
                    let file = try importFile(from: url, name: provider.suggestedName.map { $0 + "." + url.pathExtension } ?? url.lastPathComponent, quality: self.quality)
                    lock.lock()
                    files[index] = file
                    lock.unlock()
                } catch {
                    lock.lock()
                    failure = error
                    lock.unlock()
                }
            }
        }
        group.notify(queue: .main) {
            if let failure = failure {
                self.finish(.failure(NSError(domain: "pick_failed", code: 1, userInfo: [NSLocalizedDescriptionKey: failure.localizedDescription])))
            } else {
                self.finish(.success(files.compactMap { $0 }))
            }
        }
    }
}

/// iOS 13: one item, which the system has already written to a temporary file for a video.
private final class PNLegacyPickerSession: PNPickerSession, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
    private let quality: Double?

    init(quality: Double?, done: @escaping (Result<[PNPickedFile], Error>) -> Void) {
        self.quality = quality
        super.init(done: done)
    }

    func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
        picker.dismiss(animated: true)
        let source = info[.mediaURL] as? URL ?? info[.imageURL] as? URL
        let image = info[.originalImage] as? UIImage
        let quality = self.quality
        importInBackground {
            if let source = source {
                return [try importFile(from: source, name: source.lastPathComponent, quality: quality)]
            }
            guard let data = image?.jpegData(compressionQuality: CGFloat(quality ?? 1)) else { return [] }
            let target = try newPickedFile(named: "image.jpg")
            try data.write(to: target, options: [.atomic])
            return [try pickedFile(at: target)]
        }
    }

    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
        picker.dismiss(animated: true)
        finish(.success([]))
    }
}

private final class PNDocumentPickerSession: PNPickerSession, UIDocumentPickerDelegate {
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        importInBackground { try urls.map { try importFile(from: $0, name: $0.lastPathComponent, quality: nil) } }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        finish(.success([]))
    }
}
