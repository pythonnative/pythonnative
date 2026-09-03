import CoreLocation
import UIKit

/// `Camera`: `take_photo` / `pick_from_gallery` through `UIImagePickerController`.
public final class CameraModule: PNNativeModule {
    public static let name = "Camera"

    private var activePicker: PNImagePickerSession?

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        let source: UIImagePickerController.SourceType
        switch method {
        case "take_photo": source = .camera
        case "pick_from_gallery": source = .photoLibrary
        default:
            promise.reject("Camera has no method '\(method)'", code: "unknown_method")
            return
        }
        guard UIImagePickerController.isSourceTypeAvailable(source), let top = PNWindow.topViewController() else {
            promise.resolve(nil)
            return
        }
        if activePicker != nil {
            promise.reject("a picker is already open", code: "busy")
            return
        }
        let quality = PNProps.double(args["quality"]) ?? 0.9
        let session = PNImagePickerSession(quality: CGFloat(max(0, min(1, quality)))) { [weak self] path in
            self?.activePicker = nil
            promise.resolve(path)
        }
        activePicker = session
        let picker = UIImagePickerController()
        picker.sourceType = source
        picker.allowsEditing = PNProps.bool(args["allow_editing"]) ?? false
        picker.delegate = session
        top.present(picker, animated: true)
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
public final class LocationModule: PNNativeModule {
    public static let name = "Location"

    private var sessions: [PNLocationSession] = []

    public init() {}

    public func call(_ method: String, args: [String: Any], promise: PNPromise) {
        guard method == "get_current" else {
            promise.reject("Location has no method '\(method)'", code: "unknown_method")
            return
        }
        let timeout = PNProps.double(args["timeout"]) ?? 15
        var session: PNLocationSession?
        session = PNLocationSession(accuracy: PNProps.string(args["accuracy"]), timeout: timeout) { [weak self] fix in
            if let finished = session {
                self?.sessions.removeAll { $0 === finished }
            }
            promise.resolve(fix)
        }
        guard let started = session else { return }
        sessions.append(started)
        started.start()
    }
}

/// One location request: authorization, a single fix, and a timeout.
final class PNLocationSession: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let done: ([String: Any]?) -> Void
    private let timeout: TimeInterval
    private var finished = false
    private var timer: Timer?

    init(accuracy: String?, timeout: TimeInterval, done: @escaping ([String: Any]?) -> Void) {
        self.done = done
        self.timeout = max(1, timeout)
        super.init()
        manager.delegate = self
        switch accuracy {
        case "high", "best": manager.desiredAccuracy = kCLLocationAccuracyBest
        case "low", "coarse": manager.desiredAccuracy = kCLLocationAccuracyKilometer
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
        var fix: [String: Any] = [
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

    private func finish(_ fix: [String: Any]?) {
        if finished { return }
        finished = true
        timer?.invalidate()
        manager.stopUpdatingLocation()
        done(fix)
    }
}
