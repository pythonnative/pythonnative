import CoreLocation
import UIKit

/// `Camera`: `take_photo` / `pick_from_gallery` through `UIImagePickerController`.
public final class CameraModule: CameraImplementation {
    private var activePicker: PNImagePickerSession?
    public init() {}

    public func take_photo(quality: Double, allow_editing: Bool, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        launch(.camera, quality: quality, editing: allow_editing, completion: completion)
    }

    public func pick_from_gallery(quality: Double, allow_editing: Bool, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        launch(.photoLibrary, quality: quality, editing: allow_editing, completion: completion)
    }

    private func launch(_ source: UIImagePickerController.SourceType, quality: Double, editing: Bool, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        guard UIImagePickerController.isSourceTypeAvailable(source), let top = PNWindow.topViewController() else {
            completion(.success(nil)); return nil
        }
        guard activePicker == nil else {
            completion(.failure(NSError(domain: "busy", code: 1, userInfo: [NSLocalizedDescriptionKey: "A picker is already open"]))); return nil
        }
        let session = PNImagePickerSession(quality: CGFloat(max(0, min(1, quality)))) { [weak self] path in
            self?.activePicker = nil
            completion(.success(path))
        }
        activePicker = session
        let picker = UIImagePickerController()
        picker.sourceType = source
        picker.allowsEditing = editing
        picker.delegate = session
        top.present(picker, animated: true)
        return { [weak self, weak picker] in
            picker?.delegate = nil
            picker?.dismiss(animated: true)
            self?.activePicker = nil
        }
    }
}

/// Picker delegate that writes the chosen image to Caches and reports its path.
final class PNImagePickerSession: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
    private let quality: CGFloat
    private let done: (String?) -> Void

    init(quality: CGFloat, done: @escaping (String?) -> Void) {
        self.quality = quality
        self.done = done
    }

    func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
        picker.dismiss(animated: true)
        let image = (info[.editedImage] as? UIImage) ?? (info[.originalImage] as? UIImage)
        guard let image = image, let data = image.jpegData(compressionQuality: quality) else {
            done(nil)
            return
        }
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? URL(fileURLWithPath: NSTemporaryDirectory())
        let dir = caches.appendingPathComponent("pn_camera", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("\(UUID().uuidString).jpg")
        do {
            try data.write(to: file, options: [.atomic])
            done(file.path)
        } catch {
            PNLog.modules.error("could not save picked image: \(error.localizedDescription)")
            done(nil)
        }
    }

    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
        picker.dismiss(animated: true)
        done(nil)
    }
}

/// `Location`: one-shot `get_current` fix via `CLLocationManager`.
public final class LocationModule: LocationImplementation {
    private var sessions: [UUID: PNLocationSession] = [:]
    public init() {}

    public func get_current(accuracy: PNLocationGetCurrentAccuracy, timeout: Double, completion: @escaping (Result<[String: Double]?, Error>) -> Void) -> (() -> Void)? {
        let id = UUID()
        let session = PNLocationSession(accuracy: accuracy.rawValue, timeout: timeout) { [weak self] fix in
            self?.sessions.removeValue(forKey: id)
            completion(.success(fix))
        }
        sessions[id] = session
        session.start()
        return { [weak self] in self?.sessions.removeValue(forKey: id)?.cancel() }
    }
}

/// One location request: authorization, a single fix, and a timeout.
final class PNLocationSession: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let done: ([String: Double]?) -> Void
    private let timeout: TimeInterval
    private var finished = false
    private var timer: Timer?

    init(accuracy: String?, timeout: TimeInterval, done: @escaping ([String: Double]?) -> Void) {
        self.done = done
        self.timeout = max(1, timeout)
        super.init()
        manager.delegate = self
        switch accuracy {
        case "high": manager.desiredAccuracy = kCLLocationAccuracyBest
        default: manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        }
    }

    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in
            self?.finish(nil)
        }
        switch manager.pnAuthorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            finish(nil)
        default:
            manager.requestLocation()
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        switch manager.pnAuthorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            manager.requestLocation()
        case .denied, .restricted:
            finish(nil)
        default:
            break
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        var fix: [String: Double] = [
            "latitude": location.coordinate.latitude,
            "longitude": location.coordinate.longitude,
            "accuracy": location.horizontalAccuracy,
            "altitude": location.altitude,
            "timestamp": location.timestamp.timeIntervalSince1970,
        ]
        if location.speed >= 0 { fix["speed"] = location.speed }
        if location.course >= 0 { fix["heading"] = location.course }
        finish(fix)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        PNLog.modules.error("location failed: \(error.localizedDescription)")
        finish(nil)
    }

    func cancel() {
        finished = true
        timer?.invalidate()
        timer = nil
        manager.stopUpdatingLocation()
        manager.delegate = nil
    }

    private func finish(_ fix: [String: Double]?) {
        if finished { return }
        cancel()
        done(fix)
    }
}
