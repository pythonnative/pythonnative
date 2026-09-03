import CoreLocation
import Photos
import UIKit

/// Back-deployment shims for APIs that moved or appeared after iOS 13, so
/// the kit compiles at the lowest deployment target `pn` accepts.
extension CLLocationManager {
    /// `authorizationStatus` (instance, iOS 14+) with the class-method
    /// fallback used on iOS 13.
    var pnAuthorizationStatus: CLAuthorizationStatus {
        if #available(iOS 14.0, *) {
            return authorizationStatus
        }
        return CLLocationManager.authorizationStatus()
    }
}

extension PHPhotoLibrary {
    /// Read/write library access status on iOS 14+, the legacy status before.
    static func pnReadWriteAuthorizationStatus() -> PHAuthorizationStatus {
        if #available(iOS 14.0, *) {
            return authorizationStatus(for: .readWrite)
        }
        return authorizationStatus()
    }

    /// Request read/write library access with the API available on this OS.
    static func pnRequestReadWriteAuthorization(_ handler: @escaping (PHAuthorizationStatus) -> Void) {
        if #available(iOS 14.0, *) {
            requestAuthorization(for: .readWrite, handler: handler)
        } else {
            requestAuthorization(handler)
        }
    }
}

extension UIDatePicker {
    /// Prefer the compact inline style where the OS offers it.
    func pnApplyCompactStyle() {
        if #available(iOS 14.0, *) {
            preferredDatePickerStyle = .compact
        } else if #available(iOS 13.4, *) {
            preferredDatePickerStyle = .wheels
        }
    }
}
