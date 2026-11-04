import MapKit
import UIKit

/// Registers the `MapView` component, backed by MapKit.
public enum MapsPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("MapView") { PNMapManager() }
    }
}

/// One `Marker`, as MapKit's annotation.
private final class PNMapPin: NSObject, MKAnnotation {
    let id: String
    @objc dynamic var coordinate: CLLocationCoordinate2D
    var title: String?
    var subtitle: String?
    var color: UIColor?

    init(_ marker: PNMarker) {
        id = marker.id
        coordinate = CLLocationCoordinate2D(latitude: marker.coordinate.latitude, longitude: marker.coordinate.longitude)
        title = marker.title
        subtitle = marker.description
        color = marker.color.flatMap { PNColor.parse($0) }
    }
}

/// One `Polyline`: MapKit asks the delegate for a renderer, so the line carries its own stroke.
private final class PNMapLine: MKPolyline {
    var color: UIColor?
    var width: CGFloat = 2
}

private let pinReuseIdentifier = "pn-map-pin"

final class PNMapHostView: MKMapView, MKMapViewDelegate, UIGestureRecognizerDelegate {
    private var pins: [String: PNMapPin] = [:]
    private var pendingRegion: MKCoordinateRegion?
    private var didReportReady = false
    private var lastError: String?

    override init(frame: CGRect) {
        super.init(frame: frame)
        delegate = self
        register(MKMarkerAnnotationView.self, forAnnotationViewWithReuseIdentifier: pinReuseIdentifier)
        let tap = UITapGestureRecognizer(target: self, action: #selector(tapped(_:)))
        tap.delegate = self
        addGestureRecognizer(tap)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func layoutSubviews() {
        super.layoutSubviews()
        // MapKit fits a region to the view's shape, so one set at zero size comes out wrong.
        if let region = pendingRegion, !bounds.isEmpty {
            pendingRegion = nil
            setRegion(region, animated: false)
        }
    }

    // MARK: - Applying props

    func show(_ value: PNRegion, animated: Bool) {
        let region = Self.valid(value)
        if bounds.isEmpty {
            pendingRegion = region
            return
        }
        if !animated && Self.isClose(region, self.region) { return }
        setRegion(region, animated: animated)
    }

    /// `setRegion` throws an Objective-C exception on an out-of-range region, which no Swift code can catch.
    private static func valid(_ value: PNRegion) -> MKCoordinateRegion {
        let latitude = min(max(value.center.latitude, -85), 85)
        let longitude = min(max(value.center.longitude, -180), 180)
        let latitudeDelta = min(max(value.latitude_delta, 0), 2 * (90 - abs(latitude)))
        let longitudeDelta = min(max(value.longitude_delta, 0), 360)
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: latitude, longitude: longitude),
            span: MKCoordinateSpan(latitudeDelta: latitudeDelta, longitudeDelta: longitudeDelta)
        )
    }

    /// Whether the difference is only MapKit's rounding, so a region reported
    /// by `on_region_change` and passed straight back doesn't move the map.
    private static func isClose(_ first: MKCoordinateRegion, _ second: MKCoordinateRegion) -> Bool {
        let tolerance = 0.001
        return abs(first.center.latitude - second.center.latitude) <= first.span.latitudeDelta * tolerance
            && abs(first.center.longitude - second.center.longitude) <= first.span.longitudeDelta * tolerance
            && abs(first.span.latitudeDelta - second.span.latitudeDelta) <= first.span.latitudeDelta * tolerance
            && abs(first.span.longitudeDelta - second.span.longitudeDelta) <= first.span.longitudeDelta * tolerance
    }

    func setMarkers(_ markers: [PNMarker]) {
        let wanted = Set(markers.map { $0.id })
        for (id, pin) in pins where !wanted.contains(id) {
            removeAnnotation(pin)
            pins.removeValue(forKey: id)
        }
        for marker in markers {
            let next = PNMapPin(marker)
            guard let pin = pins[marker.id] else {
                pins[marker.id] = next
                addAnnotation(next)
                continue
            }
            // A recolored pin needs a new annotation view; a moved one animates in place.
            if pin.color != next.color || pin.title != next.title || pin.subtitle != next.subtitle {
                removeAnnotation(pin)
                pins[marker.id] = next
                addAnnotation(next)
            } else {
                pin.coordinate = next.coordinate
            }
        }
    }

    func setPolylines(_ polylines: [PNPolyline]) {
        removeOverlays(overlays)
        for polyline in polylines {
            let coordinates = polyline.coordinates.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
            let line = PNMapLine(coordinates: coordinates, count: coordinates.count)
            line.color = polyline.color.flatMap { PNColor.parse($0) }
            line.width = CGFloat(polyline.width)
            addOverlay(line)
        }
    }

    func release() {
        delegate = nil
        showsUserLocation = false
        removeAnnotations(annotations)
        removeOverlays(overlays)
    }

    // MARK: - Delegate

    func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
        guard let pin = annotation as? PNMapPin else { return nil }
        let view = dequeueReusableAnnotationView(withIdentifier: pinReuseIdentifier, for: pin)
        view.canShowCallout = true
        (view as? MKMarkerAnnotationView)?.markerTintColor = pin.color
        return view
    }

    func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
        let renderer = MKPolylineRenderer(overlay: overlay)
        if let line = overlay as? PNMapLine {
            renderer.strokeColor = line.color ?? tintColor
            renderer.lineWidth = line.width
        }
        return renderer
    }

    func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
        guard let pin = view.annotation as? PNMapPin else { return }
        PNComponentEvents.MapView.on_marker_press(self, pin.id)
    }

    func mapView(_ mapView: MKMapView, regionDidChangeAnimated animated: Bool) {
        if bounds.isEmpty { return }
        let current = region
        PNComponentEvents.MapView.on_region_change(self, PNRegion(
            center: PNCoordinate(latitude: current.center.latitude, longitude: current.center.longitude),
            latitude_delta: current.span.latitudeDelta,
            longitude_delta: current.span.longitudeDelta
        ))
    }

    func mapViewDidFinishRenderingMap(_ mapView: MKMapView, fullyRendered: Bool) {
        reportReady()
    }

    func mapViewDidFailLoadingMap(_ mapView: MKMapView, withError error: Error) {
        reportReady()
        let message = "The map failed to load: \(error.localizedDescription)"
        if message == lastError { return }
        lastError = message
        PNComponentEvents.MapView.on_error(self, message)
    }

    private func reportReady() {
        if didReportReady { return }
        didReportReady = true
        PNComponentEvents.MapView.on_ready(self)
    }

    // MARK: - Presses

    /// MapKit's own recognizers keep working: panning and double-tap zoom aren't ours to block.
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        true
    }

    @objc private func tapped(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended else { return }
        let point = recognizer.location(in: self)
        // A press on a marker or its callout is `on_marker_press`, not `on_press`.
        var hit = hitTest(point, with: nil)
        while let view = hit, view !== self {
            if view is MKAnnotationView { return }
            hit = view.superview
        }
        let coordinate = convert(point, toCoordinateFrom: self)
        PNComponentEvents.MapView.on_press(self, PNCoordinate(latitude: coordinate.latitude, longitude: coordinate.longitude))
    }
}

final class PNMapManager: PNTypedComponentManager<MapViewProps> {
    init() { super.init(MapViewProps.self) }

    override func makeView(props: [String: Any]) -> UIView {
        PNMapHostView(frame: .zero)
    }

    override func applyTyped(view: UIView, props: MapViewProps, initial: Bool) {
        PNViewStyler.applyCommon(view, props.values)
        guard let map = view as? PNMapHostView else { return }
        if initial || props.has_map_type {
            switch props.map_type ?? .standard {
            case .standard: map.mapType = .standard
            case .satellite: map.mapType = .satellite
            case .hybrid: map.mapType = .hybrid
            }
        }
        if initial || props.has_zoom_enabled { map.isZoomEnabled = props.zoom_enabled ?? true }
        if initial || props.has_scroll_enabled { map.isScrollEnabled = props.scroll_enabled ?? true }
        if initial || props.has_shows_user_location { map.showsUserLocation = props.shows_user_location ?? false }
        if initial, let region = props.region ?? props.initial_region {
            map.show(region, animated: false)
        } else if !initial, let region = props.region {
            map.show(region, animated: false)
        }
        if initial || props.has_markers { map.setMarkers(props.markers ?? []) }
        if initial || props.has_polylines { map.setPolylines(props.polylines ?? []) }
    }

    override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard name == "animate_to", let map = view as? PNMapHostView else {
            return super.command(view: view, name: name, args: args)
        }
        if let region = try? PNValues.decode(PNRegion.self, args["region"]) {
            map.show(region, animated: true)
        }
        return nil
    }

    override func teardown(view: UIView) {
        (view as? PNMapHostView)?.release()
    }
}
