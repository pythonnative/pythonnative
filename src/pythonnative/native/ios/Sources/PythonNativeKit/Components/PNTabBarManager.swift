import UIKit

/// `TabBar`: a native `UITabBar`. Height is 49 pt plus the bottom safe
/// area so the bar reaches the home indicator (the screen root extends
/// past the bottom inset for this reason).
public final class PNTabBarManager: PNComponentManager {
    public static let baseHeight: CGFloat = 49

    /// The intrinsic bar height for the current bottom safe-area inset.
    public static func height(for view: UIView?) -> CGFloat {
        let bottom = view?.window?.safeAreaInsets.bottom ?? PNWindow.keyWindow()?.safeAreaInsets.bottom ?? 0
        return baseHeight + bottom
    }

    public override func makeView(props: [String: Any]) -> UIView {
        UITabBar(frame: CGRect(x: 0, y: 0, width: 0, height: PNTabBarManager.height(for: nil)))
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let bar = view as? UITabBar {
            let delegate = PNTabBarDelegate()
            bar.delegate = delegate
            PNViewState.existing(for: bar)?.retained.append(delegate)
        }
        return view
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let w = maxW.isFinite && maxW < 1e6 ? maxW : 320
        return CGSize(width: w, height: PNTabBarManager.height(for: view))
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        let typed = try! TabBarProps(props)

        guard let bar = view as? UITabBar else { return }
        let merged = mergedProps(bar)
        let items = PNTabBarManager.items(merged)
        if typed.has_items {
            bar.setItems(items.enumerated().map { index, item in
                let title = PNProps.string(item["title"]) ?? PNProps.string(item["name"]) ?? ""
                let icon = PNTabBarManager.icon(item["icon"])
                let barItem = UITabBarItem(title: title, image: icon, tag: index)
                if let badge = PNProps.string(PNProps.value(item, "badge")) { barItem.badgeValue = badge }
                return barItem
            }, animated: false)
        }
        if typed.has_active_tab || PNProps.has(props, "active_index") || typed.has_items {
            let activeName = PNProps.string(PNProps.value(merged, "active_tab"))
            var index = PNProps.int(PNProps.value(merged, "active_index"))
            if index == nil, let activeName = activeName {
                index = items.firstIndex { PNProps.string($0["name"]) == activeName }
            }
            if let index = index, let barItems = bar.items, index >= 0, index < barItems.count {
                bar.selectedItem = barItems[index]
            }
        }
        if let color = PNColor.parse(PNProps.value(props, "active_color") ?? PNProps.value(props, "tint_color")) {
            bar.tintColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "inactive_color")) {
            bar.unselectedItemTintColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            bar.barTintColor = color
            bar.backgroundColor = color
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = color
            bar.standardAppearance = appearance
            if #available(iOS 15.0, *) {
                bar.scrollEdgeAppearance = appearance
            }
        }
        if PNProps.has(props, "translucent") {
            bar.isTranslucent = PNProps.bool(PNProps.value(props, "translucent")) ?? true
        }
        PNViewStyler.applyAccessibility(bar, props)
    }

    static func items(_ props: [String: Any]) -> [[String: Any]] {
        ((PNProps.value(props, "items") as? [Any]) ?? []).compactMap { $0 as? [String: Any] }
    }

    /// The size tab bar icons are rasterized at, in points.
    static let iconSize = CGSize(width: 25, height: 25)

    /// Resolve an icon spec to a template image.
    ///
    /// `{"shapes": [...], "view_box": "..."}` is drawn with the SVG
    /// renderer (Lucide icons resolved by Python); `{"uri": "asset://..."}`
    /// loads a bundled image. Anything else yields no icon.
    static func icon(_ spec: Any?) -> UIImage? {
        guard let dict = spec as? [String: Any] else { return nil }
        if let raw = dict["shapes"] as? [Any], !raw.isEmpty {
            let shapes = raw.compactMap { try? PNValues.decode(PNSvgShape.self, $0) }
            let viewBox = PNSvgView.parseViewBox(PNProps.string(dict["view_box"])) ?? CGRect(x: 0, y: 0, width: 24, height: 24)
            let paint = PNSvgPaint(fill: "none", stroke: "currentColor", strokeWidth: 2, lineCap: "round", lineJoin: "round")
            return PNSvgRenderer.image(shapes, viewBox: viewBox, size: iconSize, root: paint)
        }
        if let uri = PNProps.string(dict["uri"]), !uri.isEmpty,
           let image = PNImageManager.loadLocal(uri, targetSize: iconSize) {
            return image.withRenderingMode(.alwaysTemplate)
        }
        return nil
    }
}

/// Forwards `tabBar(_:didSelect:)` as `on_tab_select(name)` (plus `on_select(index)`).
final class PNTabBarDelegate: NSObject, UITabBarDelegate {
    func tabBar(_ tabBar: UITabBar, didSelect item: UITabBarItem) {
        let index = item.tag
        let items = PNTabBarManager.items(PNViewState.existing(for: tabBar)?.props ?? [:])
        guard index >= 0, index < items.count else { return }
        PNEvents.emit(tabBar, "on_tab_select", [PNProps.string(items[index]["name"]) ?? ""])
        PNEvents.emitIfWired(tabBar, "on_select", [index])
    }
}
