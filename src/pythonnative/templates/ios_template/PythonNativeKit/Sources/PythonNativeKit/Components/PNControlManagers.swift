import UIKit

/// `Switch`: `UISwitch` emitting `on_change(bool)`.
public final class PNSwitchManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UISwitch(frame: .zero)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let control = view as? UISwitch {
            PNActionTarget.attach(control, events: .valueChanged) { [weak control] in
                guard let control = control, PNViewState.existing(for: control)?.flag("suppress") != true else { return }
                PNEvents.emit(control, "on_change", [control.isOn])
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let control = view as? UISwitch, let state = PNViewState.existing(for: control) else { return }
        if PNProps.has(props, "value") {
            let value = PNProps.bool(PNProps.value(props, "value")) ?? false
            if control.isOn != value {
                state.extras["suppress"] = true
                control.setOn(value, animated: !initial)
                state.extras["suppress"] = false
            }
        }
        if let color = PNColor.parse(PNProps.value(props, "on_tint_color") ?? PNProps.value(props, "tint_color")) {
            control.onTintColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "thumb_color")) {
            control.thumbTintColor = color
        }
        if PNProps.has(props, "enabled") {
            control.isEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true
        }
        PNViewStyler.applyAccessibility(control, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        CGSize(width: 51, height: 31)
    }

    /// `UISwitch` ignores the size part of `frame`, but the base class sets
    /// `bounds` directly, which would stretch its hit area (and accessibility
    /// frame) across a stretched flex cross axis. Pin the box to the natural
    /// size at the layout origin so taps land on the visible control.
    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {
        let natural = view.intrinsicContentSize
        let pw = natural.width > 0 ? min(w, Double(natural.width)) : w
        let ph = natural.height > 0 ? min(h, Double(natural.height)) : h
        super.setFrame(view: view, x: x, y: y, w: pw, h: ph)
    }
}

/// `Slider`: `UISlider` emitting `on_change(float)`.
public final class PNSliderManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        UISlider(frame: .zero)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let slider = view as? UISlider {
            PNActionTarget.attach(slider, events: .valueChanged) { [weak slider] in
                guard let slider = slider, PNViewState.existing(for: slider)?.flag("suppress") != true else { return }
                PNEvents.emit(slider, "on_change", [Double(slider.value)])
            }
            PNActionTarget.attach(slider, events: [.touchUpInside, .touchUpOutside, .touchCancel]) { [weak slider] in
                guard let slider = slider else { return }
                PNEvents.emitIfWired(slider, "on_sliding_complete", [Double(slider.value)])
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let slider = view as? UISlider, let state = PNViewState.existing(for: slider) else { return }
        if let min = PNProps.double(PNProps.value(props, "min_value")) { slider.minimumValue = Float(min) }
        if let max = PNProps.double(PNProps.value(props, "max_value")) { slider.maximumValue = Float(max) }
        if let value = PNProps.double(PNProps.value(props, "value")), abs(Double(slider.value) - value) > 1e-9 {
            state.extras["suppress"] = true
            slider.setValue(Float(value), animated: !initial)
            state.extras["suppress"] = false
        }
        if let color = PNColor.parse(PNProps.value(props, "minimum_track_color") ?? PNProps.value(props, "tint_color")) {
            slider.minimumTrackTintColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "maximum_track_color")) { slider.maximumTrackTintColor = color }
        if let color = PNColor.parse(PNProps.value(props, "thumb_color")) { slider.thumbTintColor = color }
        if PNProps.has(props, "enabled") { slider.isEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true }
        PNViewStyler.applyAccessibility(slider, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let w = maxW.isFinite && maxW < 1e6 ? maxW : 200
        return CGSize(width: max(w, 100), height: 34)
    }
}

/// `ActivityIndicator`: `UIActivityIndicatorView`.
public final class PNActivityIndicatorManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let style: UIActivityIndicatorView.Style = PNProps.string(PNProps.value(props, "size")) == "large" ? .large : .medium
        let view = UIActivityIndicatorView(style: style)
        view.hidesWhenStopped = true
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let indicator = view as? UIActivityIndicatorView else { return }
        if !initial, let size = PNProps.string(PNProps.value(props, "size")) {
            indicator.style = size == "large" ? .large : .medium
        }
        if let color = PNColor.parse(PNProps.value(props, "color")) { indicator.color = color }
        if PNProps.has(props, "animating") || initial {
            let animating = PNProps.bool(PNProps.value(props, "animating")) ?? true
            if animating { indicator.startAnimating() } else { indicator.stopAnimating() }
        }
        if PNProps.has(props, "hides_when_stopped") {
            indicator.hidesWhenStopped = PNProps.bool(PNProps.value(props, "hides_when_stopped")) ?? true
        }
        PNViewStyler.applyAccessibility(indicator, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let size = view.intrinsicContentSize
        return size.width > 0 ? size : CGSize(width: 20, height: 20)
    }
}

/// `ProgressBar`: a determinate `UIProgressView`, or a spinning
/// `UIActivityIndicatorView` when `indeterminate` is set at creation.
public final class PNProgressBarManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        if PNProps.bool(PNProps.value(props, "indeterminate")) == true {
            let spinner = UIActivityIndicatorView(style: .medium)
            spinner.startAnimating()
            return spinner
        }
        return UIProgressView(progressViewStyle: .default)
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        if let spinner = view as? UIActivityIndicatorView {
            if let color = PNColor.parse(PNProps.value(props, "color")) { spinner.color = color }
            spinner.startAnimating()
        } else if let bar = view as? UIProgressView {
            if let value = PNProps.double(PNProps.value(props, "value") ?? PNProps.value(props, "progress")) {
                bar.setProgress(Float(max(0, min(1, value))), animated: !initial)
            }
            if let color = PNColor.parse(PNProps.value(props, "color")) { bar.progressTintColor = color }
            if let color = PNColor.parse(PNProps.value(props, "track_color")) { bar.trackTintColor = color }
        }
        PNViewStyler.applyAccessibility(view, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        if view is UIActivityIndicatorView { return CGSize(width: 20, height: 20) }
        let w = maxW.isFinite && maxW < 1e6 ? maxW : 200
        return CGSize(width: max(w, 40), height: 4)
    }
}

/// `SegmentedControl`: `UISegmentedControl` emitting `on_change(index)`.
public final class PNSegmentedControlManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let segments = ((PNProps.value(props, "segments") as? [Any]) ?? []).map { PNProps.string($0) ?? "" }
        return UISegmentedControl(items: segments)
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let control = view as? UISegmentedControl {
            PNActionTarget.attach(control, events: .valueChanged) { [weak control] in
                guard let control = control, PNViewState.existing(for: control)?.flag("suppress") != true else { return }
                PNEvents.emit(control, "on_change", [control.selectedSegmentIndex])
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let control = view as? UISegmentedControl, let state = PNViewState.existing(for: control) else { return }
        let merged = state.props
        var rebuilt = false
        if let segments = PNProps.value(props, "segments") as? [Any] {
            let titles = segments.map { PNProps.string($0) ?? "" }
            if !initial, titles != (state.extras["segments"] as? [String]) {
                state.extras["suppress"] = true
                control.removeAllSegments()
                for (i, title) in titles.enumerated() {
                    control.insertSegment(withTitle: title, at: i, animated: false)
                }
                state.extras["suppress"] = false
                rebuilt = true
            }
            state.extras["segments"] = titles
        }
        if rebuilt || initial || PNProps.value(props, "selected_index") != nil {
            state.extras["suppress"] = true
            control.selectedSegmentIndex = PNProps.int(PNProps.value(merged, "selected_index")) ?? 0
            state.extras["suppress"] = false
        }
        if let color = PNColor.parse(PNProps.value(props, "tint_color")) {
            control.selectedSegmentTintColor = color
            control.tintColor = color
        }
        if PNProps.has(props, "enabled") {
            control.isEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true
        }
        PNViewStyler.applyAccessibility(control, props)
    }
}

/// `DatePicker`: compact `UIDatePicker` emitting ISO-style strings.
public final class PNDatePickerManager: PNComponentManager {
    static let formats = ["date": "yyyy-MM-dd", "time": "HH:mm", "datetime": "yyyy-MM-dd'T'HH:mm"]
    static var formatters: [String: DateFormatter] = [:]

    static func formatter(mode: String) -> DateFormatter {
        let format = formats[mode] ?? formats["date"]!
        if let cached = formatters[format] { return cached }
        let formatter = DateFormatter()
        formatter.dateFormat = format
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatters[format] = formatter
        return formatter
    }

    public override func makeView(props: [String: Any]) -> UIView {
        let picker = UIDatePicker(frame: .zero)
        picker.pnApplyCompactStyle()
        return picker
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let picker = view as? UIDatePicker {
            PNActionTarget.attach(picker, events: .valueChanged) { [weak picker] in
                guard let picker = picker, let state = PNViewState.existing(for: picker), !state.flag("suppress") else { return }
                let mode = PNProps.string(PNProps.value(state.props, "mode")) ?? "date"
                PNEvents.emit(picker, "on_change", [PNDatePickerManager.formatter(mode: mode).string(from: picker.date)])
            }
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let picker = view as? UIDatePicker, let state = PNViewState.existing(for: picker) else { return }
        let mode = PNProps.string(PNProps.value(state.props, "mode")) ?? "date"
        if PNProps.value(props, "mode") != nil {
            switch mode {
            case "time": picker.datePickerMode = .time
            case "datetime": picker.datePickerMode = .dateAndTime
            default: picker.datePickerMode = .date
            }
        }
        let formatter = PNDatePickerManager.formatter(mode: mode)
        if PNProps.has(props, "minimum") {
            picker.minimumDate = PNProps.string(PNProps.value(props, "minimum")).flatMap { formatter.date(from: $0) }
        }
        if PNProps.has(props, "maximum") {
            picker.maximumDate = PNProps.string(PNProps.value(props, "maximum")).flatMap { formatter.date(from: $0) }
        }
        if let value = PNProps.string(PNProps.value(props, "value")), !value.isEmpty, let date = formatter.date(from: value) {
            state.extras["suppress"] = true
            picker.setDate(date, animated: false)
            state.extras["suppress"] = false
        }
        if PNProps.has(props, "enabled") {
            picker.isEnabled = PNProps.bool(PNProps.value(props, "enabled")) ?? true
        }
        if let color = PNColor.parse(PNProps.value(props, "tint_color")) {
            picker.tintColor = color
        }
        PNViewStyler.applyAccessibility(picker, props)
    }
}
