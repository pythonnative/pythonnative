import UIKit

/// `ScrollView`: a `UIScrollView` wrapping one layout-engine-sized child.
///
/// Scroll offsets are reported through `on_scroll` with
/// `{"x", "y", "extent", "range", "content_width", "content_height"}`.
/// Commands: `scroll_to_offset`, `scroll_to_end`, `get_scroll_offset`,
/// `flash_scroll_indicators`.
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
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let scroll = view as? UIScrollView else { return }
        PNViewStyler.applyCommon(scroll, props)
        if PNProps.has(props, "refresh_control") {
            applyRefresh(scroll, PNProps.value(props, "refresh_control"))
        }
        if PNProps.has(props, "shows_scroll_indicator") {
            let visible = PNProps.bool(PNProps.value(props, "shows_scroll_indicator")) ?? true
            scroll.showsVerticalScrollIndicator = visible
            scroll.showsHorizontalScrollIndicator = visible
        }
        if PNProps.has(props, "paging_enabled") {
            scroll.isPagingEnabled = PNProps.bool(PNProps.value(props, "paging_enabled")) ?? false
        }
        if PNProps.has(props, "bounces") {
            scroll.bounces = PNProps.bool(PNProps.value(props, "bounces")) ?? true
        }
        if PNProps.has(props, "scroll_enabled") {
            scroll.isScrollEnabled = PNProps.bool(PNProps.value(props, "scroll_enabled")) ?? true
        }
        if PNProps.has(props, "horizontal") {
            let horizontal = PNProps.bool(PNProps.value(props, "horizontal")) ?? false
            scroll.alwaysBounceHorizontal = horizontal
            scroll.alwaysBounceVertical = !horizontal && scroll.refreshControl != nil
        }
        if let mode = PNProps.string(PNProps.value(props, "keyboard_dismiss_mode")) {
            switch mode {
            case "on_drag": scroll.keyboardDismissMode = .onDrag
            case "interactive": scroll.keyboardDismissMode = .interactive
            default: scroll.keyboardDismissMode = .none
            }
        }
        if PNProps.has(props, "content_inset") {
            let inset = PNProps.dict(PNProps.value(props, "content_inset")) ?? [:]
            scroll.contentInset = UIEdgeInsets(
                top: CGFloat(PNProps.double(inset["top"]) ?? 0), left: CGFloat(PNProps.double(inset["left"]) ?? 0),
                bottom: CGFloat(PNProps.double(inset["bottom"]) ?? 0), right: CGFloat(PNProps.double(inset["right"]) ?? 0)
            )
        }
        if PNProps.has(props, "scroll_indicator_insets") {
            let inset = PNProps.dict(PNProps.value(props, "scroll_indicator_insets")) ?? [:]
            let insets = UIEdgeInsets(
                top: CGFloat(PNProps.double(inset["top"]) ?? 0), left: CGFloat(PNProps.double(inset["left"]) ?? 0),
                bottom: CGFloat(PNProps.double(inset["bottom"]) ?? 0), right: CGFloat(PNProps.double(inset["right"]) ?? 0)
            )
            scroll.verticalScrollIndicatorInsets = insets
            scroll.horizontalScrollIndicatorInsets = insets
        }
        if PNProps.has(props, "scroll_event_throttle") {
            PNViewState.existing(for: scroll)?.extras["throttle"] = PNProps.double(PNProps.value(props, "scroll_event_throttle")) ?? 0
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
            let horizontal = content.width > bounds.width && content.height <= bounds.height
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

/// Shared scroll payload builder.
enum PNScrollPayload {
    static func make(_ scroll: UIScrollView) -> [String: Any] {
        let offset = scroll.contentOffset
        let bounds = scroll.bounds.size
        let content = scroll.contentSize
        let horizontal = content.width > bounds.width && content.height <= bounds.height
        return [
            "x": Double(offset.x),
            "y": Double(offset.y),
            "extent": Double(horizontal ? bounds.width : bounds.height),
            "range": Double(horizontal ? content.width : content.height),
            "content_width": Double(content.width),
            "content_height": Double(content.height),
            "width": Double(bounds.width),
            "height": Double(bounds.height),
        ]
    }
}

/// Forwards `UIScrollViewDelegate` callbacks to Python events.
final class PNScrollDelegate: NSObject, UIScrollViewDelegate {
    private var lastEmit: TimeInterval = 0

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        guard let state = PNViewState.existing(for: scrollView), state.hasEvent("on_scroll") else { return }
        let throttle = (state.extras["throttle"] as? Double ?? 0) / 1000
        let now = CACurrentMediaTime()
        if throttle > 0, now - lastEmit < throttle, scrollView.isDragging || scrollView.isDecelerating { return }
        lastEmit = now
        PNEvents.emit(scrollView, "on_scroll", [PNScrollPayload.make(scrollView)])
    }

    func scrollViewWillBeginDragging(_ scrollView: UIScrollView) {
        PNEvents.emitIfWired(scrollView, "on_scroll_begin_drag", [PNScrollPayload.make(scrollView)])
    }

    func scrollViewDidEndDragging(_ scrollView: UIScrollView, willDecelerate decelerate: Bool) {
        PNEvents.emitIfWired(scrollView, "on_scroll_end_drag", [PNScrollPayload.make(scrollView)])
        if !decelerate {
            PNEvents.emitIfWired(scrollView, "on_momentum_scroll_end", [PNScrollPayload.make(scrollView)])
        }
    }

    func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) {
        PNEvents.emitIfWired(scrollView, "on_momentum_scroll_end", [PNScrollPayload.make(scrollView)])
    }

    func scrollViewDidEndScrollingAnimation(_ scrollView: UIScrollView) {
        PNEvents.emitIfWired(scrollView, "on_scroll", [PNScrollPayload.make(scrollView)])
    }
}
