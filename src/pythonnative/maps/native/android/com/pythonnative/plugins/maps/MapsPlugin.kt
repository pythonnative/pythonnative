package com.pythonnative.plugins.maps

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.Application
import android.content.ComponentCallbacks
import android.content.Context
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.MapView
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.android.gms.maps.model.Marker
import com.google.android.gms.maps.model.MarkerOptions
import com.google.android.gms.maps.model.Polyline
import com.google.android.gms.maps.model.PolylineOptions
import com.pythonnative.generated.MapViewProps
import com.pythonnative.generated.PNComponentEvents
import com.pythonnative.generated.PNCoordinate
import com.pythonnative.generated.PNMapViewMapType
import com.pythonnative.generated.PNMarker
import com.pythonnative.generated.PNPolyline
import com.pythonnative.generated.PNRegion
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNLog
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.components.PNColor
import com.pythonnative.runtime.components.TypedComponentManager
import com.pythonnative.runtime.components.ViewStyler
import com.pythonnative.runtime.modules.PNLifecycleHook
import org.json.JSONObject
import kotlin.math.abs

private const val API_KEY_NAME = "com.google.android.geo.API_KEY"
private const val MISSING_KEY = "This map needs a Google Maps API key. Set [plugins.maps].android_api_key " +
    "in pythonnative.toml, or GOOGLE_MAPS_API_KEY when building, and rebuild."

/** Registers the `MapView` component, backed by the Google Maps SDK. */
object MapsPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerComponent("MapView") { MapViewManager() }
        registry.registerLifecycleHook(MapLifecycle)
    }
}

/**
 * Forwards activity events to every live map: `MapView` draws nothing, and
 * leaks, unless its host calls `onStart`, `onResume`, and the rest. Hosts
 * combine the activity's level with their own attach state.
 *
 * `onSaveInstanceState` isn't forwarded because no hook reports it. Python owns
 * the region, so a recreated view comes back where its props say.
 */
private object MapLifecycle : PNLifecycleHook {
    const val CREATED = 0
    const val STARTED = 1
    const val RESUMED = 2

    private val hosts = LinkedHashSet<MapHost>()
    private var reported: Int? = null

    /** The hook only hears transitions, and the first screen can mount before one arrives. */
    val level: Int
        get() = reported ?: when ((PNBridge.activity() as? LifecycleOwner)?.lifecycle?.currentState) {
            Lifecycle.State.RESUMED -> RESUMED
            Lifecycle.State.STARTED -> STARTED
            else -> CREATED
        }

    fun add(host: MapHost) { hosts.add(host) }

    fun remove(host: MapHost) { hosts.remove(host) }

    private fun moveTo(next: Int) {
        reported = next
        hosts.toList().forEach { it.syncLifecycle() }
    }

    override fun onApplicationCreate(application: Application) {
        application.registerComponentCallbacks(object : ComponentCallbacks {
            override fun onConfigurationChanged(newConfig: Configuration) {}
            override fun onLowMemory() { hosts.toList().forEach { it.mapView?.onLowMemory() } }
        })
    }

    override fun onActivityResumed(activity: Activity) {
        moveTo(RESUMED)
        // The user may have just come back from granting location in a prompt or in Settings.
        hosts.toList().forEach { it.applyUserLocation() }
    }

    override fun onActivityPaused(activity: Activity) = moveTo(STARTED)

    override fun onActivityStopped(activity: Activity) = moveTo(CREATED)

    override fun onActivityDestroyed(activity: Activity) {
        reported = null
        hosts.toList().forEach { it.destroy() }
    }
}

/** A `MapView`, or the message saying why there can't be one. */
private class MapHost(context: Context, private val manager: MapViewManager) : FrameLayout(context) {
    var mapView: MapView? = null
        private set
    var map: GoogleMap? = null
        private set

    var markers: List<PNMarker> = emptyList()
    var polylines: List<PNPolyline> = emptyList()
    var mapType = GoogleMap.MAP_TYPE_NORMAL
    var zoomEnabled = true
    var scrollEnabled = true
    var showsUserLocation = false

    private var level = MapLifecycle.CREATED
    private var destroyed = false
    private var pending: Pair<PNRegion, Boolean>? = null
    private val placedMarkers = HashMap<String, Pair<PNMarker, Marker>>()
    private val placedLines = ArrayList<Polyline>()
    private var reportedLocation = false

    fun showMessage(message: String) {
        addView(
            TextView(context).apply {
                text = message
                gravity = Gravity.CENTER
                setTextColor(Color.DKGRAY)
                setBackgroundColor(Color.rgb(232, 234, 237))
                val inset = (16 * resources.displayMetrics.density).toInt()
                setPadding(inset, inset, inset, inset)
            },
            LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT),
        )
    }

    fun start() {
        val view = MapView(context)
        view.onCreate(null)
        mapView = view
        addView(view, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        MapLifecycle.add(this)
        syncLifecycle()
        view.getMapAsync { ready ->
            if (destroyed) return@getMapAsync
            map = ready
            manager.wire(this, ready)
            applyAll()
            manager.reportReady(this)
        }
    }

    /** Walk `MapView` one step at a time toward what the activity and the window allow. */
    fun syncLifecycle() {
        val view = mapView ?: return
        if (destroyed) return
        val target = if (isAttachedToWindow) MapLifecycle.level else MapLifecycle.CREATED
        while (level < target) {
            level += 1
            if (level == MapLifecycle.STARTED) view.onStart() else view.onResume()
        }
        while (level > target) {
            if (level == MapLifecycle.RESUMED) view.onPause() else view.onStop()
            level -= 1
        }
    }

    fun destroy() {
        if (destroyed) return
        val view = mapView
        if (view != null) {
            level.takeIf { it == MapLifecycle.RESUMED }?.let { view.onPause() }
            level.takeIf { it >= MapLifecycle.STARTED }?.let { view.onStop() }
            view.onDestroy()
        }
        destroyed = true
        map = null
        MapLifecycle.remove(this)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        syncLifecycle()
    }

    override fun onDetachedFromWindow() {
        syncLifecycle()
        super.onDetachedFromWindow()
    }

    override fun onSizeChanged(width: Int, height: Int, oldWidth: Int, oldHeight: Int) {
        super.onSizeChanged(width, height, oldWidth, oldHeight)
        // Fires inside layout, and the camera needs the map to have its new size first.
        post { flushRegion() }
    }

    /** A map inside a `ScrollView` would otherwise lose its pan to the scroll view. */
    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        if (mapView != null && (scrollEnabled || zoomEnabled)) {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> parent?.requestDisallowInterceptTouchEvent(true)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> parent?.requestDisallowInterceptTouchEvent(false)
            }
        }
        return super.dispatchTouchEvent(event)
    }

    fun show(region: PNRegion, animated: Boolean) {
        pending = region to animated
        flushRegion()
    }

    private fun flushRegion() {
        val current = map ?: return
        val (region, animated) = pending ?: return
        if (width == 0 || height == 0) return
        pending = null
        if (!animated && isClose(region, readRegion(current))) return
        val update = CameraUpdateFactory.newLatLngBounds(bounds(region), width, height, 0)
        if (animated) current.animateCamera(update) else current.moveCamera(update)
    }

    fun applyAll() {
        applySettings()
        applyMarkers()
        applyPolylines()
        applyUserLocation()
        flushRegion()
    }

    fun applySettings() {
        val current = map ?: return
        current.mapType = mapType
        current.uiSettings.isZoomGesturesEnabled = zoomEnabled
        current.uiSettings.isScrollGesturesEnabled = scrollEnabled
    }

    fun applyMarkers() {
        val current = map ?: return
        val wanted = markers.map { it.id }.toSet()
        placedMarkers.keys.filter { it !in wanted }.forEach { id -> placedMarkers.remove(id)?.second?.remove() }
        for (marker in markers) {
            val placed = placedMarkers[marker.id]
            if (placed?.first == marker) continue
            val position = LatLng(marker.coordinate.latitude, marker.coordinate.longitude)
            val icon = BitmapDescriptorFactory.defaultMarker(hue(marker.color))
            if (placed != null) {
                placed.second.position = position
                placed.second.title = marker.title
                placed.second.snippet = marker.description
                placed.second.setIcon(icon)
                placedMarkers[marker.id] = marker to placed.second
                continue
            }
            val added = current.addMarker(MarkerOptions().position(position).title(marker.title).snippet(marker.description).icon(icon)) ?: continue
            added.tag = marker.id
            placedMarkers[marker.id] = marker to added
        }
    }

    fun applyPolylines() {
        val current = map ?: return
        placedLines.forEach { it.remove() }
        placedLines.clear()
        val density = resources.displayMetrics.density
        for (line in polylines) {
            val options = PolylineOptions()
                .addAll(line.coordinates.map { LatLng(it.latitude, it.longitude) })
                .width((line.width * density).toFloat())
                .color(line.color?.let { PNColor.parse(it) } ?: Color.rgb(26, 115, 232))
            placedLines.add(current.addPolyline(options))
        }
    }

    /**
     * `isMyLocationEnabled` throws `SecurityException` without the permission,
     * which this plugin doesn't request: the app asks, and the next resume
     * picks the answer up.
     */
    @SuppressLint("MissingPermission")
    fun applyUserLocation() {
        val current = map ?: return
        if (!showsUserLocation) {
            if (current.isMyLocationEnabled) current.isMyLocationEnabled = false
            reportedLocation = false
            return
        }
        val granted = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            .any { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }
        if (granted) {
            current.isMyLocationEnabled = true
            reportedLocation = false
        } else if (!reportedLocation) {
            reportedLocation = true
            manager.reportError(this, "shows_user_location needs location permission, which the app hasn't been granted.")
        }
    }

    companion object {
        fun readRegion(map: GoogleMap): PNRegion {
            val bounds = map.projection.visibleRegion.latLngBounds
            val center = bounds.center
            return PNRegion(
                PNCoordinate(center.latitude, center.longitude),
                bounds.northeast.latitude - bounds.southwest.latitude,
                // Positive even when the view crosses the antimeridian.
                (bounds.northeast.longitude - bounds.southwest.longitude + 360.0) % 360.0,
            )
        }

        private fun bounds(region: PNRegion): LatLngBounds {
            val latitude = region.center.latitude
            val longitude = region.center.longitude
            val halfHeight = region.latitude_delta.coerceIn(0.0, 180.0) / 2
            // Exactly 360 degrees would make both edges the same meridian.
            val halfWidth = region.longitude_delta.coerceIn(0.0, 359.9) / 2
            return LatLngBounds(
                LatLng((latitude - halfHeight).coerceAtLeast(-90.0), longitude - halfWidth),
                LatLng((latitude + halfHeight).coerceAtMost(90.0), longitude + halfWidth),
            )
        }

        /** Whether the difference is only the camera's rounding, so a region passed straight back doesn't move the map. */
        private fun isClose(first: PNRegion, second: PNRegion): Boolean {
            val tolerance = 0.001
            return abs(first.center.latitude - second.center.latitude) <= first.latitude_delta * tolerance &&
                abs(first.center.longitude - second.center.longitude) <= first.longitude_delta * tolerance &&
                abs(first.latitude_delta - second.latitude_delta) <= first.latitude_delta * tolerance &&
                abs(first.longitude_delta - second.longitude_delta) <= first.longitude_delta * tolerance
        }

        /** Google's default pin is tinted by hue alone. */
        private fun hue(color: String?): Float {
            val parsed = color?.let { PNColor.parse(it) } ?: return BitmapDescriptorFactory.HUE_RED
            val hsv = FloatArray(3)
            Color.colorToHSV(parsed, hsv)
            return hsv[0].coerceIn(0f, 359.9f)
        }
    }
}

private class MapViewManager : TypedComponentManager<MapViewProps>({ values, partial -> MapViewProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val host = MapHost(context, this)
        val problem = problem(context)
        if (problem != null) {
            host.showMessage(problem)
            // The view has no tag yet, so an event fired now couldn't reach Python.
            host.post { reportError(host, problem) }
            return host
        }
        try {
            host.start()
        } catch (error: Exception) {
            PNLog.swallowed("MapView.create", error)
            val message = "The map couldn't start: ${error.message ?: error.javaClass.simpleName}"
            host.removeAllViews()
            host.showMessage(message)
            host.post { reportError(host, message) }
        }
        return host
    }

    /** What stops the SDK from starting. A missing key would otherwise throw from inside it. */
    private fun problem(context: Context): String? {
        val info = context.packageManager.getApplicationInfo(context.packageName, PackageManager.GET_META_DATA)
        if (info.metaData?.getString(API_KEY_NAME).isNullOrBlank()) return MISSING_KEY
        val availability = GoogleApiAvailability.getInstance()
        val status = availability.isGooglePlayServicesAvailable(context)
        if (status == ConnectionResult.SUCCESS) return null
        return "This map needs Google Play services, which reports: ${availability.getErrorString(status)}."
    }

    fun wire(host: MapHost, map: GoogleMap) {
        map.setOnCameraIdleListener {
            if (hasEvent(host, "on_region_change")) PNComponentEvents.MapView.on_region_change(host, MapHost.readRegion(map))
        }
        map.setOnMapClickListener { point ->
            if (hasEvent(host, "on_press")) PNComponentEvents.MapView.on_press(host, PNCoordinate(point.latitude, point.longitude))
        }
        map.setOnMarkerClickListener { marker ->
            val id = marker.tag as? String
            if (id != null && hasEvent(host, "on_marker_press")) PNComponentEvents.MapView.on_marker_press(host, id)
            // Keep the default behavior: show the info window and center on the marker.
            false
        }
    }

    fun reportReady(host: MapHost) {
        if (hasEvent(host, "on_ready")) PNComponentEvents.MapView.on_ready(host)
    }

    fun reportError(host: MapHost, message: String) {
        if (hasEvent(host, "on_error")) PNComponentEvents.MapView.on_error(host, message)
    }

    override fun applyTyped(view: View, props: MapViewProps, initial: Boolean) {
        ViewStyler.apply(view, props.values)
        val host = view as? MapHost ?: return
        if (initial || props.has_map_type) {
            host.mapType = when (props.map_type) {
                PNMapViewMapType.`satellite` -> GoogleMap.MAP_TYPE_SATELLITE
                PNMapViewMapType.`hybrid` -> GoogleMap.MAP_TYPE_HYBRID
                else -> GoogleMap.MAP_TYPE_NORMAL
            }
        }
        if (initial || props.has_zoom_enabled) host.zoomEnabled = props.zoom_enabled ?: true
        if (initial || props.has_scroll_enabled) host.scrollEnabled = props.scroll_enabled ?: true
        host.applySettings()
        if (initial || props.has_shows_user_location) {
            host.showsUserLocation = props.shows_user_location ?: false
            host.applyUserLocation()
        }
        if (initial) {
            (props.region ?: props.initial_region)?.let { host.show(it, false) }
        } else {
            props.region?.let { host.show(it, false) }
        }
        if (initial || props.has_markers) {
            host.markers = props.markers ?: emptyList()
            host.applyMarkers()
        }
        if (initial || props.has_polylines) {
            host.polylines = props.polylines ?: emptyList()
            host.applyPolylines()
        }
    }

    override fun command(view: View, name: String, args: JSONObject): Any? {
        if (name == "animate_to") (view as? MapHost)?.show(PNRegion.decode(args.get("region")), true)
        return null
    }

    override fun teardown(view: View) {
        (view as? MapHost)?.destroy()
    }
}
