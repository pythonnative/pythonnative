import UIKit

/// `ScrollView`: a `UIScrollView` wrapping one layout-engine-sized child.
///
/// Scroll events (`on_scroll`, `on_scroll_begin_drag`, `on_scroll_end_drag`,
/// `on_momentum_scroll_end`) carry exactly the `ScrollEvent` record:
/// `{"x", "y", "content_width", "content_height", "viewport_width",
/// "viewport_height"}`. Commands: `scroll_to_offset`, `scroll_to_end`,
/// `get_scroll_offset`, `flash_scroll_indicators`.
public final class PNScrollViewManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let scroll = UIScrollView(frame: .zero)
        scroll.contentInsetAdjustmentBehavior = .never
        return scroll
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let scroll = view as? UIScrollView {
            let delegate = PNScrollDelegate()
            scroll.delegate = delegate
            PNViewState.existing(for: scroll)?.retained.append(delegate)
            let tap = UITapGestureRecognizer(target: delegate, action: #selector(PNScrollDelegate.backgroundTapped(_:)))
            tap.cancelsTouchesInView = false
            tap.delegate = delegate
            scroll.addGestureRecognizer(tap)
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        let typed = try! ScrollViewProps(props)

        guard let scroll = view as? UIScrollView, let state = PNViewState.existing(for: scroll) else { return }
        PNViewStyler.applyCommon(scroll, props)
        if typed.has_refresh_control {
            applyRefresh(scroll, PNProps.value(props, "refresh_control"))
        }
        if typed.has_shows_scroll_indicator {
            let visible = typed.shows_scroll_indicator ?? true
            scroll.showsVerticalScrollIndicator = visible
            scroll.showsHorizontalScrollIndicator = visible
        }
        if typed.has_paging_enabled {
            scroll.isPagingEnabled = typed.paging_enabled ?? false
        }
        if typed.has_bounces {
            scroll.bounces = typed.bounces ?? true
        }
        if typed.has_scroll_enabled {
            scroll.isScrollEnabled = typed.scroll_enabled ?? true
        }
        if typed.has_horizontal {
            let horizontal = typed.horizontal ?? false
            state.extras["horizontal"] = horizontal
            scroll.alwaysBounceHorizontal = horizontal
            scroll.alwaysBounceVertical = !horizontal && scroll.refreshControl != nil
        }
        if let mode = typed.keyboard_dismiss_mode?.rawValue {
            switch mode {
            case "on_drag": scroll.keyboardDismissMode = .onDrag
            case "interactive": scroll.keyboardDismissMode = .interactive
            default: scroll.keyboardDismissMode = .none
            }
        }
        if typed.has_keyboard_should_persist_taps {
            state.extras["persist_taps"] = typed.keyboard_should_persist_taps?.rawValue ?? "never"
        }
        if typed.has_content_inset {
            scroll.contentInset = PNScrollViewManager.edgeInsets(PNProps.value(props, "content_inset"))
        }
        if PNProps.has(props, "scroll_indicator_insets") {
            let insets = PNScrollViewManager.edgeInsets(PNProps.value(props, "scroll_indicator_insets"))
            scroll.verticalScrollIndicatorInsets = insets
            scroll.horizontalScrollIndicatorInsets = insets
        }
        if typed.has_scroll_event_throttle {
            state.extras["throttle"] = typed.scroll_event_throttle ?? 0
        }
        if typed.has_snap_to_interval {
            state.extras["snap_interval"] = typed.snap_to_interval.map { max(0, $0) } as Any? ?? NSNull()
        }
        if typed.has_snap_to_alignment {
            state.extras["snap_alignment"] = typed.snap_to_alignment?.rawValue ?? "start"
        }
        if typed.has_deceleration_rate {
            scroll.decelerationRate = PNScrollViewManager.decelerationRate(PNProps.value(props, "deceleration_rate"))
        }
    }

    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let scroll = view as? UIScrollView else { return nil }
        let animated = PNProps.bool(args["animated"]) ?? true
        switch name {
        case "scroll_to_offset":
            let x = CGFloat(PNProps.finite(args["x"]))
            let y = CGFloat(PNProps.finite(args["y"]))
            scroll.setContentOffset(CGPoint(x: x, y: y), animated: animated)
        case "scroll_to_end":
            let content = scroll.contentSize
            let bounds = scroll.bounds.size
            let targetY = max(0, content.height - bounds.height)
            let targetX = max(0, content.width - bounds.width)
            let horizontal = PNScrollViewManager.isHorizontal(scroll)
            scroll.setContentOffset(horizontal ? CGPoint(x: targetX, y: 0) : CGPoint(x: 0, y: targetY), animated: animated)
        case "get_scroll_offset":
            return ["x": Double(scroll.contentOffset.x), "y": Double(scroll.contentOffset.y)]
        case "flash_scroll_indicators":
            scroll.flashScrollIndicators()
        default:
            break
        }
        return nil
    }

    // MARK: - Helpers

    /// Whether the scroll view scrolls horizontally (the `horizontal` prop,
    /// or the content shape when the prop is absent).
    static func isHorizontal(_ scroll: UIScrollView) -> Bool {
        if let flag = PNViewState.existing(for: scroll)?.extras["horizontal"] as? Bool { return flag }
        let content = scroll.contentSize, bounds = scroll.bounds.size
        return content.width > bounds.width && content.height <= bounds.height
    }

    /// `EdgeInsets` (`top`/`left`/`bottom`/`right` with the `all`,
    /// `horizontal`, and `vertical` shorthands) to `UIEdgeInsets`.
    public static func edgeInsets(_ value: Any?) -> UIEdgeInsets {
        guard let dict = value as? [String: Any] else {
            if let uniform = PNProps.double(value) { return UIEdgeInsets(top: CGFloat(uniform), left: CGFloat(uniform), bottom: CGFloat(uniform), right: CGFloat(uniform)) }
            return .zero
        }
        let all = PNProps.double(dict["all"]) ?? 0
        let horizontal = PNProps.double(dict["horizontal"]) ?? all
        let vertical = PNProps.double(dict["vertical"]) ?? all
        return UIEdgeInsets(
            top: CGFloat(PNProps.double(dict["top"]) ?? vertical), left: CGFloat(PNProps.double(dict["left"]) ?? horizontal),
            bottom: CGFloat(PNProps.double(dict["bottom"]) ?? vertical), right: CGFloat(PNProps.double(dict["right"]) ?? horizontal)
        )
    }

    /// `deceleration_rate`: `"normal"`, `"fast"`, or a raw per-frame rate.
    public static func decelerationRate(_ value: Any?) -> UIScrollView.DecelerationRate {
        if let name = value as? String {
            return name == "fast" ? .fast : .normal
        }
        if let rate = PNProps.double(value), rate.isFinite, rate > 0, rate < 1 {
            return UIScrollView.DecelerationRate(rawValue: CGFloat(rate))
        }
        return .normal
    }

    /// The offset a drag ending at `proposed` with `velocity` settles on
    /// for `snap_to_interval` / `snap_to_alignment`.
    public static func snapTarget(proposed: CGFloat, velocity: CGFloat, interval: CGFloat, alignment: String, viewport: CGFloat, maximum: CGFloat) -> CGFloat {
        guard interval > 0 else { return proposed }
        let shift: CGFloat
        switch alignment {
        case "center": shift = (viewport - interval) / 2
        case "end": shift = viewport - interval
        default: shift = 0
        }
        let raw = (proposed + shift) / interval
        let index: CGFloat
        if abs(velocity) > 0.1 {
            index = velocity > 0 ? ceil(raw) : floor(raw)
        } else {
            index = raw.rounded()
        }
        return min(max(0, index * interval - shift), max(0, maximum))
    }

    // MARK: - Refresh control

    private func applyRefresh(_ scroll: UIScrollView, _ spec: Any?) {
        guard let spec = spec else {
            if let existing = scroll.refreshControl {
                existing.endRefreshing()
                scroll.refreshControl = nil
                scroll.alwaysBounceVertical = false
            }
            return
        }
        let control: UIRefreshControl
        if let existing = scroll.refreshControl {
            control = existing
        } else {
            control = UIRefreshControl()
            scroll.refreshControl = control
            // Content that fits its bounds never engages the pan gesture
            // without this, making the refresh control unreachable.
            scroll.alwaysBounceVertical = true
            let target = PNActionTarget { [weak scroll] in
                guard let scroll = scroll else { return }
                PNEvents.emit(scroll, "on_refresh")
            }
            control.addTarget(target, action: #selector(PNActionTarget.fire(_:forEvent:)), for: .valueChanged)
            PNViewState.existing(for: scroll)?.retained.append(target)
        }
        let dict = spec as? [String: Any] ?? [:]
        if let color = PNColor.parse(PNProps.value(dict, "tint_color") ?? PNProps.value(dict, "color")) {
            control.tintColor = color
        }
        if let title = PNProps.string(PNProps.value(dict, "title")) {
            control.attributedTitle = NSAttributedString(string: title)
        }
        if PNProps.bool(dict["refreshing"]) == true {
            if !control.isRefreshing { control.beginRefreshing() }
        } else if control.isRefreshing {
            control.endRefreshing()
        }
    }
}

/// Shared scroll payload builder: the `ScrollEvent` record and nothing else.
enum PNScrollPayload {
    static func event(_ scroll: UIScrollView) -> PNScrollEvent {
        let offset = scroll.contentOffset
        let bounds = scroll.bounds.size
        let content = scroll.contentSize
        return PNScrollEvent(
            x: Double(offset.x), y: Double(offset.y),
            content_width: Double(content.width), content_height: Double(content.height),
            viewport_width: Double(bounds.width), viewport_height: Double(bounds.height)
        )
    }

    static func make(_ scroll: UIScrollView) -> [String: Any] {
        (PNValues.encode(event(scroll)) as? [String: Any]) ?? [:]
    }
}

/// Forwards `UIScrollViewDelegate` callbacks to Python events.
final class PNScrollDelegate: NSObject, UIScrollViewDelegate, UIGestureRecognizerDelegate {
    private var lastEmit: TimeInterval = 0

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        guard let state = PNViewState.existing(for: scrollView), state.hasEvent("on_scroll") else { return }
        let throttle = (state.extras["throttle"] as? Double ?? 0) / 1000
        let now = CACurrentMediaTime()
        if throttle > 0, now - lastEmit < throttle, scrollView.isDragging || scrollView.isDecelerating { return }
        lastEmit = now
        PNComponentEvents.ScrollView.on_scroll(scrollView, PNScrollPayload.event(scrollView))
    }

    func scrollViewWillBeginDragging(_ scrollView: UIScrollView) {
        PNComponentEvents.ScrollView.on_scroll_begin_drag(scrollView, PNScrollPayload.event(scrollView))
    }

    func scrollViewWillEndDragging(_ scrollView: UIScrollView, withVelocity velocity: CGPoint, targetContentOffset: UnsafeMutablePointer<CGPoint>) {
        guard let state = PNViewState.existing(for: scrollView), let interval = state.extras["snap_interval"] as? Double, interval > 0 else { return }
        let alignment = state.extras["snap_alignment"] as? String ?? "start"
        let horizontal = PNScrollViewManager.isHorizontal(scrollView)
        let proposed = targetContentOffset.pointee
        if horizontal {
            let maximum = scrollView.contentSize.width - scrollView.bounds.width
            targetContentOffset.pointee.x = PNScrollViewManager.snapTarget(
                proposed: proposed.x, velocity: velocity.x, interval: CGFloat(interval), alignment: alignment,
                viewport: scrollView.bounds.width, maximum: maximum
            )
        } else {
            let maximum = scrollView.contentSize.height - scrollView.bounds.height
            targetContentOffset.pointee.y = PNScrollViewManager.snapTarget(
                proposed: proposed.y, velocity: velocity.y, interval: CGFloat(interval), alignment: alignment,
                viewport: scrollView.bounds.height, maximum: maximum
            )
        }
    }

    func scrollViewDidEndDragging(_ scrollView: UIScrollView, willDecelerate decelerate: Bool) {
        PNComponentEvents.ScrollView.on_scroll_end_drag(scrollView, PNScrollPayload.event(scrollView))
        if !decelerate {
            PNComponentEvents.ScrollView.on_momentum_scroll_end(scrollView, PNScrollPayload.event(scrollView))
        }
    }

    func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) {
        PNComponentEvents.ScrollView.on_momentum_scroll_end(scrollView, PNScrollPayload.event(scrollView))
    }

    func scrollViewDidEndScrollingAnimation(_ scrollView: UIScrollView) {
        PNComponentEvents.ScrollView.on_scroll(scrollView, PNScrollPayload.event(scrollView))
    }

    // MARK: keyboard_should_persist_taps

    /// `never` (default): a tap anywhere in the content dismisses the
    /// keyboard. `handled`: only taps that no control handles dismiss it.
    /// `always`: taps never dismiss it.
    @objc func backgroundTapped(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended, let scroll = recognizer.view as? UIScrollView,
              PNKeyboardObserver.shared.isVisible || scroll.window?.firstResponderView != nil else { return }
        let mode = PNViewState.existing(for: scroll)?.extras["persist_taps"] as? String ?? "never"
        guard mode != "always" else { return }
        let hit = scroll.hitTest(recognizer.location(in: scroll), with: nil)
        if hit is UITextInput || hit?.isFirstResponder == true { return }
        if mode == "handled", PNScrollDelegate.isHandled(hit, within: scroll) { return }
        scroll.window?.endEditing(true)
    }

    /// Whether a tap on `view` is consumed by a control or a pressable
    /// between it and the scroll view.
    static func isHandled(_ view: UIView?, within scroll: UIScrollView) -> Bool {
        var current = view
        while let candidate = current, candidate !== scroll {
            if candidate is UIControl { return true }
            if let recognizers = candidate.gestureRecognizers, recognizers.contains(where: { $0 is UITapGestureRecognizer || $0 is UILongPressGestureRecognizer }) {
                return true
            }
            current = candidate.superview
        }
        return false
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        true
    }
}

extension UIWindow {
    /// The view that currently owns the keyboard, if any.
    var firstResponderView: UIView? {
        func search(_ view: UIView) -> UIView? {
            if view.isFirstResponder { return view }
            for child in view.subviews { if let found = search(child) { return found } }
            return nil
        }
        return search(self)
    }
}
