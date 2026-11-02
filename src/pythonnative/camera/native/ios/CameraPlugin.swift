import AVFoundation
import UIKit

/// Registers `Camera` and `CameraView`, and owns the `camera` and `microphone` permissions.
public enum CameraPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(CameraModuleAdapter<CameraModule>.self)
        registry.registerComponent("CameraView") { PNCameraViewManager() }
        PNPermissions.register("camera", PNCapturePermission(.video))
        PNPermissions.register("microphone", PNCapturePermission(.audio))
    }
}

private func cameraError(_ code: String, _ message: String) -> NSError {
    NSError(domain: code, code: 1, userInfo: [NSLocalizedDescriptionKey: message])
}

private func newCaptureFile(extension fileExtension: String) -> URL {
    let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? URL(fileURLWithPath: NSTemporaryDirectory())
    let directory = caches.appendingPathComponent("pn_camera", isDirectory: true)
    try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    return directory.appendingPathComponent("\(UUID().uuidString).\(fileExtension)")
}

/// Whether the app declared the usage string, without which the system kills it at the prompt.
private func hasUsageString(for media: AVMediaType) -> Bool {
    let key = media == .video ? "NSCameraUsageDescription" : "NSMicrophoneUsageDescription"
    return Bundle.main.object(forInfoDictionaryKey: key) != nil
}

private final class PNCapturePermission: PNPermissionProvider {
    private let media: AVMediaType

    init(_ media: AVMediaType) {
        self.media = media
    }

    func check(_ done: @escaping (String) -> Void) {
        switch AVCaptureDevice.authorizationStatus(for: media) {
        case .authorized: done("granted")
        case .denied, .restricted: done("blocked")
        case .notDetermined: done("undetermined")
        @unknown default: done("undetermined")
        }
    }

    func request(_ done: @escaping (String) -> Void) -> (() -> Void)? {
        guard hasUsageString(for: media) else {
            PNLog.modules.error("The \(self.media == .video ? "camera" : "microphone") permission isn't declared under [permissions] in pythonnative.toml")
            done("denied")
            return nil
        }
        AVCaptureDevice.requestAccess(for: media) { granted in
            DispatchQueue.main.async { done(granted ? "granted" : "blocked") }
        }
        return nil
    }
}

/// `Camera`: the system screen through `UIImagePickerController`, and the
/// answering half of `CameraViewHandle`, which addresses a view by its tag.
public final class CameraModule: CameraImplementation {
    private var activePicker: PNCapturePickerSession?
    public init() {}

    public func take_photo(allow_editing: Bool, quality: Double, completion: @escaping (Result<String?, Error>) -> Void) -> (() -> Void)? {
        guard UIImagePickerController.isSourceTypeAvailable(.camera), let top = PNWindow.topViewController() else {
            completion(.success(nil))
            return nil
        }
        guard activePicker == nil else {
            completion(.failure(cameraError("busy", "The camera screen is already open")))
            return nil
        }
        let session = PNCapturePickerSession(quality: CGFloat(max(0, min(1, quality)))) { [weak self] path in
            self?.activePicker = nil
            completion(.success(path))
        }
        activePicker = session
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.allowsEditing = allow_editing
        picker.delegate = session
        top.present(picker, animated: true)
        return { [weak self, weak picker] in
            picker?.delegate = nil
            picker?.dismiss(animated: true)
            self?.activePicker = nil
        }
    }

    private func cameraView(_ tag: Int64) -> PNCameraView? {
        PNViewRegistry.shared.view(for: tag) as? PNCameraView
    }

    private func noView<T>(_ tag: Int64, _ completion: (Result<T, Error>) -> Void) {
        completion(.failure(cameraError("not_ready", "No CameraView with tag \(tag) is mounted")))
    }

    public func take_picture(quality: Double, tag: Int64, completion: @escaping (Result<PNPhoto, Error>) -> Void) -> (() -> Void)? {
        guard let view = cameraView(tag) else { noView(tag, completion); return nil }
        view.takePicture(quality: quality, completion: completion)
        return nil
    }

    public func start_recording(audio: Bool, tag: Int64, completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)? {
        guard let view = cameraView(tag) else { noView(tag, completion); return nil }
        view.startRecording(audio: audio, completion: completion)
        return nil
    }

    public func stop_recording(tag: Int64, completion: @escaping (Result<PNRecording, Error>) -> Void) -> (() -> Void)? {
        guard let view = cameraView(tag) else { noView(tag, completion); return nil }
        view.stopRecording(completion: completion)
        return nil
    }
}

/// Picker delegate that writes the capture to Caches and reports its path.
private final class PNCapturePickerSession: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
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
        let file = newCaptureFile(extension: "jpg")
        do {
            try data.write(to: file, options: [.atomic])
            done(file.path)
        } catch {
            PNLog.modules.error("could not save the captured photo: \(error.localizedDescription)")
            done(nil)
        }
    }

    func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
        picker.dismiss(animated: true)
        done(nil)
    }
}

private final class PNCameraViewManager: PNTypedComponentManager<CameraViewProps> {
    init() { super.init(CameraViewProps.self) }

    override func makeView(props: [String: Any]) -> UIView {
        PNCameraView(frame: .zero)
    }

    override func applyTyped(view: UIView, props: CameraViewProps, initial: Bool) {
        PNViewStyler.applyCommon(view, props.values)
        guard let camera = view as? PNCameraView else { return }
        if initial || props.has_facing { camera.facing = props.facing == .front ? .front : .back }
        if initial || props.has_flash { camera.flash = props.flash ?? .off }
        if initial || props.has_zoom { camera.zoom = CGFloat(props.zoom ?? 1) }
        if initial || props.has_barcode_types { camera.barcodeTypes = props.barcode_types ?? [] }
    }

    override func childContainer(for view: UIView) -> UIView {
        (view as? PNCameraView)?.overlay ?? view
    }

    override func teardown(view: UIView) {
        (view as? PNCameraView)?.shutDown()
    }
}

/// A live preview on `AVCaptureSession`.
///
/// Session work happens on `sessionQueue`, because `startRunning` blocks for
/// long enough to drop frames. The properties the manager and the module touch
/// are main-thread only; everything crosses over with the values it needs.
final class PNCameraView: UIView, AVCaptureMetadataOutputObjectsDelegate {
    private static let barcodeTypes: [PNCameraViewBarcodeTypesItem: AVMetadataObject.ObjectType] = {
        var types: [PNCameraViewBarcodeTypesItem: AVMetadataObject.ObjectType] = [
            .aztec: .aztec,
            .code128: .code128,
            .code39: .code39,
            .code93: .code93,
            .data_matrix: .dataMatrix,
            .ean13: .ean13,
            .ean8: .ean8,
            .itf14: .itf14,
            .pdf417: .pdf417,
            .qr: .qr,
            // AVFoundation reports UPC-A as EAN-13 with a leading zero.
            .upc_a: .ean13,
            .upc_e: .upce,
        ]
        if #available(iOS 15.4, *) { types[.codabar] = .codabar }
        return types
    }()

    /// How long a barcode must stay out of view before it's reported again.
    private static let barcodeRepeatInterval: TimeInterval = 1.5

    let overlay = UIView()
    private let placeholder = UILabel()
    private let sessionQueue = DispatchQueue(label: "com.pythonnative.camera.session")
    private let session = AVCaptureSession()
    private let photoOutput = AVCapturePhotoOutput()
    private let movieOutput = AVCaptureMovieFileOutput()
    private let metadataOutput = AVCaptureMetadataOutput()
    private var videoInput: AVCaptureDeviceInput?
    private var audioInput: AVCaptureDeviceInput?
    private var photoCaptures: [UUID: PNPhotoCapture] = [:]
    private var movieCapture: PNMovieCapture?
    private var isConfigured = false
    private var isRunning = false
    private var isShutDown = false
    private var seenBarcodes: [String: Date] = [:]

    var facing: AVCaptureDevice.Position = .back {
        didSet { if facing != oldValue && isConfigured { switchCamera() } }
    }
    var flash: PNCameraViewFlash = .off {
        didSet { if isConfigured { applyDeviceSettings() } }
    }
    var zoom: CGFloat = 1 {
        didSet { if isConfigured { applyDeviceSettings() } }
    }
    var barcodeTypes: [PNCameraViewBarcodeTypesItem] = [] {
        didSet { if isConfigured { applyBarcodeTypes() } }
    }

    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    private var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        clipsToBounds = true
        previewLayer.videoGravity = .resizeAspectFill
        placeholder.textColor = .white
        placeholder.textAlignment = .center
        placeholder.numberOfLines = 0
        placeholder.font = .preferredFont(forTextStyle: .footnote)
        placeholder.adjustsFontForContentSizeCategory = true
        placeholder.isHidden = true
        addSubview(placeholder)
        overlay.frame = bounds
        overlay.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        addSubview(overlay)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func layoutSubviews() {
        super.layoutSubviews()
        placeholder.frame = bounds.insetBy(dx: 16, dy: 16)
        previewLayer.connection?.pnApply(orientation: currentOrientation)
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            start()
        } else if isConfigured {
            setRunning(false)
        }
    }

    private var currentOrientation: AVCaptureVideoOrientation {
        switch window?.windowScene?.interfaceOrientation {
        case .landscapeLeft: return .landscapeLeft
        case .landscapeRight: return .landscapeRight
        case .portraitUpsideDown: return .portraitUpsideDown
        default: return .portrait
        }
    }

    // MARK: - Starting

    private func start() {
        if isShutDown { return }
        if isConfigured {
            setRunning(true)
            return
        }
        guard Self.device(facing) != nil else {
            fail("unavailable", "This device has no \(facing == .front ? "front" : "back") camera. The iOS simulator has none at all.", label: "Camera unavailable")
            return
        }
        guard hasUsageString(for: .video) else {
            fail("permission_denied", "The camera permission isn't declared under [permissions] in pythonnative.toml.", label: "Camera permission not declared")
            return
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            configure()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    if granted {
                        if self.window != nil { self.configure() }
                    } else {
                        self.failDenied()
                    }
                }
            }
        default:
            failDenied()
        }
    }

    private func failDenied() {
        fail("permission_denied", "The user refused the camera permission.", label: "Camera permission denied")
    }

    private func fail(_ code: String, _ message: String, label: String) {
        placeholder.text = label
        placeholder.isHidden = false
        PNComponentEvents.CameraView.on_error(self, PNCameraError(code: code, message: message))
    }

    private static func device(_ position: AVCaptureDevice.Position) -> AVCaptureDevice? {
        AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: position)
    }

    private func configure() {
        guard !isConfigured, !isShutDown, let device = Self.device(facing) else { return }
        do {
            let input = try AVCaptureDeviceInput(device: device)
            session.beginConfiguration()
            session.sessionPreset = .high
            if session.canAddInput(input) { session.addInput(input) }
            if session.canAddOutput(photoOutput) { session.addOutput(photoOutput) }
            if session.canAddOutput(movieOutput) { session.addOutput(movieOutput) }
            if session.canAddOutput(metadataOutput) { session.addOutput(metadataOutput) }
            session.commitConfiguration()
            videoInput = input
        } catch {
            fail("capture_failed", error.localizedDescription, label: "Camera unavailable")
            return
        }
        metadataOutput.setMetadataObjectsDelegate(self, queue: .main)
        previewLayer.session = session
        NotificationCenter.default.addObserver(self, selector: #selector(sessionFailed(_:)), name: .AVCaptureSessionRuntimeError, object: session)
        isConfigured = true
        placeholder.isHidden = true
        applyBarcodeTypes()
        setRunning(window != nil)
    }

    private func setRunning(_ running: Bool) {
        if running == isRunning { return }
        isRunning = running
        let session = self.session
        sessionQueue.async { [weak self] in
            if running {
                session.startRunning()
                DispatchQueue.main.async {
                    guard let self = self, self.isRunning else { return }
                    self.applyDeviceSettings()
                    self.previewLayer.connection?.pnApply(orientation: self.currentOrientation)
                    PNComponentEvents.CameraView.on_ready(self)
                }
            } else {
                session.stopRunning()
            }
        }
    }

    private func switchCamera() {
        guard let device = Self.device(facing), let old = videoInput else {
            fail("unavailable", "This device has no \(facing == .front ? "front" : "back") camera.", label: "Camera unavailable")
            return
        }
        do {
            let input = try AVCaptureDeviceInput(device: device)
            session.beginConfiguration()
            session.removeInput(old)
            if session.canAddInput(input) {
                session.addInput(input)
                videoInput = input
            } else {
                session.addInput(old)
            }
            session.commitConfiguration()
            placeholder.isHidden = true
            applyDeviceSettings()
            if isRunning { PNComponentEvents.CameraView.on_ready(self) }
        } catch {
            fail("capture_failed", error.localizedDescription, label: "Camera unavailable")
        }
    }

    private func applyDeviceSettings() {
        guard let device = videoInput?.device else { return }
        do {
            try device.lockForConfiguration()
            device.videoZoomFactor = max(device.minAvailableVideoZoomFactor, min(zoom, device.maxAvailableVideoZoomFactor))
            if device.hasTorch {
                let mode: AVCaptureDevice.TorchMode = flash == .torch ? .on : .off
                if device.isTorchModeSupported(mode) { device.torchMode = mode }
            }
            device.unlockForConfiguration()
        } catch {
            PNLog.modules.error("could not configure the camera: \(error.localizedDescription)")
        }
    }

    private func applyBarcodeTypes() {
        let wanted = Set(barcodeTypes.compactMap { Self.barcodeTypes[$0] })
        metadataOutput.metadataObjectTypes = metadataOutput.availableMetadataObjectTypes.filter { wanted.contains($0) }
        seenBarcodes.removeAll()
    }

    @objc private func sessionFailed(_ notification: Notification) {
        let error = notification.userInfo?[AVCaptureSessionErrorKey] as? NSError
        fail("capture_failed", error?.localizedDescription ?? "The camera session stopped", label: "Camera unavailable")
    }

    func shutDown() {
        isShutDown = true
        NotificationCenter.default.removeObserver(self)
        if movieOutput.isRecording { movieOutput.stopRecording() }
        isRunning = false
        let session = self.session
        sessionQueue.async { session.stopRunning() }
    }

    // MARK: - Pictures

    func takePicture(quality: Double, completion: @escaping (Result<PNPhoto, Error>) -> Void) {
        guard isConfigured, isRunning, session.outputs.contains(photoOutput), videoInput != nil else {
            completion(.failure(cameraError("not_ready", "The camera isn't running")))
            return
        }
        let settings = AVCapturePhotoSettings(format: [
            AVVideoCodecKey: AVVideoCodecType.jpeg,
            AVVideoCompressionPropertiesKey: [AVVideoQualityKey: max(0, min(1, quality))],
        ])
        let mode: AVCaptureDevice.FlashMode = flash == .on ? .on : flash == .auto ? .auto : .off
        if photoOutput.supportedFlashModes.contains(mode) { settings.flashMode = mode }
        photoOutput.connection(with: .video)?.pnApply(orientation: currentOrientation)
        let id = UUID()
        let capture = PNPhotoCapture { [weak self] result in
            DispatchQueue.main.async {
                self?.photoCaptures.removeValue(forKey: id)
                completion(result)
            }
        }
        photoCaptures[id] = capture
        photoOutput.capturePhoto(with: settings, delegate: capture)
    }

    // MARK: - Video

    func startRecording(audio: Bool, completion: @escaping (Result<Void, Error>) -> Void) {
        guard isConfigured, isRunning, session.outputs.contains(movieOutput) else {
            completion(.failure(cameraError("not_ready", "The camera isn't running")))
            return
        }
        guard !movieOutput.isRecording, movieCapture == nil else {
            completion(.failure(cameraError("busy", "This CameraView is already recording")))
            return
        }
        guard audio else {
            setMicrophone(enabled: false)
            beginMovie(completion: completion)
            return
        }
        guard hasUsageString(for: .audio) else {
            completion(.failure(cameraError("permission_denied", "Declare microphone under [permissions] in pythonnative.toml, or pass audio=False")))
            return
        }
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard granted else {
                    completion(.failure(cameraError("permission_denied", "The user refused the microphone permission")))
                    return
                }
                self.setMicrophone(enabled: true)
                self.beginMovie(completion: completion)
            }
        }
    }

    private func setMicrophone(enabled: Bool) {
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        if !enabled {
            if let input = audioInput { session.removeInput(input) }
            audioInput = nil
            return
        }
        guard audioInput == nil, let device = AVCaptureDevice.default(for: .audio), let input = try? AVCaptureDeviceInput(device: device), session.canAddInput(input) else { return }
        session.addInput(input)
        audioInput = input
    }

    private func beginMovie(completion: @escaping (Result<Void, Error>) -> Void) {
        movieOutput.connection(with: .video)?.pnApply(orientation: currentOrientation)
        let capture = PNMovieCapture(started: completion) { [weak self] in
            DispatchQueue.main.async { self?.movieCapture = nil }
        }
        movieCapture = capture
        movieOutput.startRecording(to: newCaptureFile(extension: "mov"), recordingDelegate: capture)
    }

    func stopRecording(completion: @escaping (Result<PNRecording, Error>) -> Void) {
        guard movieOutput.isRecording, let capture = movieCapture else {
            completion(.failure(cameraError("not_recording", "This CameraView isn't recording")))
            return
        }
        capture.stopped = completion
        movieOutput.stopRecording()
    }

    // MARK: - Barcodes

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput metadataObjects: [AVMetadataObject], from connection: AVCaptureConnection) {
        let now = Date()
        for object in metadataObjects {
            guard let code = object as? AVMetadataMachineReadableCodeObject, let text = code.stringValue else { continue }
            guard let barcode = reported(type: code.type, text: text) else { continue }
            let key = "\(barcode.type.rawValue):\(barcode.data)"
            let isNew = (seenBarcodes[key].map { now.timeIntervalSince($0) >= Self.barcodeRepeatInterval }) ?? true
            seenBarcodes[key] = now
            if isNew { PNComponentEvents.CameraView.on_barcode(self, barcode) }
        }
    }

    /// The barcode to report, undoing AVFoundation's folding of UPC-A into
    /// EAN-13 so that each platform names a symbology the same way.
    private func reported(type: AVMetadataObject.ObjectType, text: String) -> PNBarcode? {
        if type == .ean13 {
            if barcodeTypes.contains(.upc_a), text.count == 13, text.hasPrefix("0") {
                return PNBarcode(data: String(text.dropFirst()), type: .upc_a)
            }
            return barcodeTypes.contains(.ean13) ? PNBarcode(data: text, type: .ean13) : nil
        }
        guard let match = Self.barcodeTypes.first(where: { $0.value == type && $0.key != .upc_a }) else { return nil }
        return PNBarcode(data: text, type: match.key)
    }
}

private extension AVCaptureConnection {
    func pnApply(orientation: AVCaptureVideoOrientation) {
        if isVideoOrientationSupported { videoOrientation = orientation }
    }
}

/// One `capturePhoto` call, retained until the file is written.
private final class PNPhotoCapture: NSObject, AVCapturePhotoCaptureDelegate {
    private let done: (Result<PNPhoto, Error>) -> Void

    init(done: @escaping (Result<PNPhoto, Error>) -> Void) {
        self.done = done
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        if let error = error {
            done(.failure(cameraError("capture_failed", error.localizedDescription)))
            return
        }
        guard let data = photo.fileDataRepresentation(), let image = UIImage(data: data) else {
            done(.failure(cameraError("capture_failed", "The camera returned no image data")))
            return
        }
        let file = newCaptureFile(extension: "jpg")
        do {
            try data.write(to: file, options: [.atomic])
            let size = image.size
            done(.success(PNPhoto(height: Int64(size.height * image.scale), path: file.path, width: Int64(size.width * image.scale))))
        } catch {
            done(.failure(cameraError("capture_failed", error.localizedDescription)))
        }
    }
}

/// One movie file, from `startRecording` until the output finishes writing it.
private final class PNMovieCapture: NSObject, AVCaptureFileOutputRecordingDelegate {
    private var started: ((Result<Void, Error>) -> Void)?
    private let finished: () -> Void
    var stopped: ((Result<PNRecording, Error>) -> Void)?

    init(started: @escaping (Result<Void, Error>) -> Void, finished: @escaping () -> Void) {
        self.started = started
        self.finished = finished
    }

    func fileOutput(_ output: AVCaptureFileOutput, didStartRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        started?(.success(()))
        started = nil
    }

    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        // AVFoundation reports a stop for a full disk or an ended session as
        // an error, but still reports whether the file is usable.
        let succeeded = ((error as NSError?)?.userInfo[AVErrorRecordingSuccessfullyFinishedKey] as? Bool) ?? (error == nil)
        let duration = output.recordedDuration.seconds
        DispatchQueue.main.async {
            if let started = self.started {
                started(.failure(cameraError("capture_failed", error?.localizedDescription ?? "Recording didn't start")))
                self.started = nil
            }
            if succeeded {
                self.stopped?(.success(PNRecording(duration: duration.isFinite ? duration : 0, path: outputFileURL.path)))
            } else {
                self.stopped?(.failure(cameraError("capture_failed", error?.localizedDescription ?? "No video was saved")))
            }
            self.stopped = nil
            self.finished()
        }
    }
}
