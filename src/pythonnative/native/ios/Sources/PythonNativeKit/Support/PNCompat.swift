import UIKit

/// Back-deployment shims for APIs that moved or appeared after iOS 13, so
/// the kit compiles at the lowest deployment target `pn` accepts.
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
