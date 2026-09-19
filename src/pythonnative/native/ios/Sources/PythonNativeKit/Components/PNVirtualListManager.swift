import UIKit

private final class PNListCell: UICollectionViewCell {
    var rowKey = ""
    override func prepareForReuse() {
        super.prepareForReuse()
        contentView.subviews.forEach { $0.removeFromSuperview() }
        rowKey = ""
    }
}

private final class PNCollectionList: UICollectionView, UICollectionViewDelegateFlowLayout, UICollectionViewDataSourcePrefetching {
    var keys: [String] = []
    var indices: [String: Int] = [:]
    private var measuring = false
    var revision = 0
    var itemRevisions: [String: Int] = [:]
    var estimates: [Double] = []
    var heights: [String: CGFloat] = [:]
    var roots: [String: UIView] = [:]
    var source: UICollectionViewDiffableDataSource<Int, String>!
    var listTag: Int64 = 0
    var horizontal = false
    private let flow = UICollectionViewFlowLayout()

    init() {
        flow.minimumLineSpacing = 0
        flow.minimumInteritemSpacing = 0
        super.init(frame: .zero, collectionViewLayout: flow)
        backgroundColor = .clear
        delegate = self
        prefetchDataSource = self
        register(PNListCell.self, forCellWithReuseIdentifier: "row")
        source = UICollectionViewDiffableDataSource<Int, String>(collectionView: self) { [weak self] collection, path, key in
            guard let self = self else { return nil }
            let cell = collection.dequeueReusableCell(withReuseIdentifier: "row", for: path) as! PNListCell
            cell.rowKey = key
            self.attach(cell, key)
            PNBridge.shared.emitEvent(tag: self.listTag, name: "on_bind_row", args: [[
                "index": path.item, "key": key, "revision": self.revision, "width": self.bounds.width, "extent": self.horizontal ? self.bounds.width : self.bounds.height,
            ]])
            return cell
        }
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    func attach(_ cell: PNListCell, _ key: String) {
        cell.contentView.subviews.forEach { $0.removeFromSuperview() }
        if let root = roots[key] {
            root.removeFromSuperview()
            cell.contentView.addSubview(root)
            root.frame = cell.contentView.bounds
            root.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        }
    }
    func anchor() -> (String, CGFloat)? {
        guard let path = indexPathsForVisibleItems.sorted().first,
              let key = source.itemIdentifier(for: path),
              let frame = layoutAttributesForItem(at: path)?.frame else { return nil }
        return (key, horizontal ? contentOffset.x - frame.minX : contentOffset.y - frame.minY)
    }
    func restore(_ anchor: (String, CGFloat)?) {
        guard let (key, offset) = anchor, let index = indices[key] else { return }
        layoutIfNeeded()
        if let frame = layoutAttributesForItem(at: IndexPath(item: index, section: 0))?.frame {
            if horizontal { contentOffset.x = max(0, min(max(0, contentSize.width - bounds.width), frame.minX + offset)) }
            else { contentOffset.y = max(0, min(max(0, contentSize.height - bounds.height), frame.minY + offset)) }
        }
    }
    func measured(_ key: String, _ extent: CGFloat) {
        guard extent > 0, heights[key] != extent else { return }
        let saved = anchor()
        heights[key] = extent
        collectionViewLayout.invalidateLayout()
        if !measuring {
            measuring = true
            DispatchQueue.main.async { [weak self] in
                self?.restore(saved)
                self?.measuring = false
            }
        }
    }
    func update(_ props: [String: Any], changed: Set<String>) {
        if !changed.isDisjoint(with: ["keys", "revision", "row_heights", "item_revisions", "horizontal"]) {
            let saved = anchor()
            let nextKeys = props["keys"] as? [String] ?? []
            let reordered = nextKeys != keys
            revision = props["revision"] as? Int ?? 0
            estimates = props["row_heights"] as? [Double] ?? []
            horizontal = props["horizontal"] as? Bool ?? false
            flow.scrollDirection = horizontal ? .horizontal : .vertical
            if reordered {
                keys = nextKeys
                indices = Dictionary(uniqueKeysWithValues: keys.enumerated().map { ($0.element, $0.offset) })
                heights = heights.filter { indices[$0.key] != nil }
            }
            let revisions = props["item_revisions"] as? [Int] ?? []
            let nextRevisions = Dictionary(uniqueKeysWithValues: keys.enumerated().map { ($0.element, $0.offset < revisions.count ? revisions[$0.offset] : 0) })
            let modified = keys.filter { itemRevisions[$0] != nil && itemRevisions[$0] != nextRevisions[$0] }
            var snapshot = source.snapshot()
            if reordered {
                snapshot = NSDiffableDataSourceSnapshot<Int, String>()
                snapshot.appendSections([0])
                snapshot.appendItems(keys)
            }
            snapshot.reloadItems(modified)
            itemRevisions = nextRevisions
            if reordered || !modified.isEmpty {
                source.apply(snapshot, animatingDifferences: false) { [weak self] in self?.restore(saved) }
            } else if changed.contains("row_heights") || changed.contains("horizontal") {
                collectionViewLayout.invalidateLayout()
                restore(saved)
            }
        }
        if let refresh = props["refresh_control"] as? [String: Any] {
            if refreshControl == nil {
                refreshControl = UIRefreshControl()
                refreshControl?.addTarget(self, action: #selector(refreshRequested), for: .valueChanged)
            }
            if refresh["refreshing"] as? Bool == true { refreshControl?.beginRefreshing() }
            else { refreshControl?.endRefreshing() }
        } else { refreshControl = nil }
    }
    func collectionView(_ collectionView: UICollectionView, prefetchItemsAt indexPaths: [IndexPath]) {
        guard let index = indexPaths.map({ $0.item }).min(), index < keys.count else { return }
        PNBridge.shared.emitEvent(tag: listTag, name: "on_bind_row", args: [[
            "index": index, "key": keys[index], "revision": revision,
            "extent": horizontal ? bounds.width : bounds.height, "width": bounds.width,
        ]])
    }
    @objc private func refreshRequested() { PNBridge.shared.emitEvent(tag: listTag, name: "on_refresh", args: []) }
    func collectionView(_ collectionView: UICollectionView, layout: UICollectionViewLayout, sizeForItemAt indexPath: IndexPath) -> CGSize {
        let key = keys[indexPath.item]
        let extent = heights[key] ?? CGFloat(indexPath.item < estimates.count ? estimates[indexPath.item] : 44)
        return horizontal ? CGSize(width: max(1, extent), height: bounds.height) : CGSize(width: bounds.width, height: max(1, extent))
    }
    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        // Like `ScrollView`, only emit when the app wired `on_scroll`.
        guard PNViewState.existing(for: self)?.hasEvent("on_scroll") == true else { return }
        let visible = indexPathsForVisibleItems.map { $0.item }
        // The `ScrollEvent` record, plus the window hints (`first`, `last`,
        // `extent`, `range`) Python's list windowing reads from this
        // untyped event.
        var payload = PNScrollPayload.make(self)
        payload["extent"] = Double(horizontal ? bounds.width : bounds.height)
        payload["range"] = Double(horizontal ? contentSize.width : contentSize.height)
        payload["first"] = visible.min() ?? 0
        payload["last"] = visible.max() ?? -1
        PNBridge.shared.emitEvent(tag: listTag, name: "on_scroll", args: [payload])
    }
}

/// Native recycled containers display children of the application's logical tree.
public final class PNVirtualListManager: PNComponentManager {
    private static var rowOwners: [Int64: (CGSize) -> Void] = [:]
    public override func makeView(props: [String: Any]) -> UIView { PNCollectionList() }
    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        PNViewStyler.applyCommon(view, props)
        guard let list = view as? PNCollectionList else { return }
        let state = PNViewState.existing(for: view)!
        list.listTag = state.tag
        list.showsVerticalScrollIndicator = state.props["shows_scroll_indicator"] as? Bool ?? true
        list.showsHorizontalScrollIndicator = list.showsVerticalScrollIndicator
        if initial || props.keys.contains(where: { ["keys", "revision", "item_revisions", "row_heights", "horizontal", "refresh_control"].contains($0) }) {
            list.update(state.props, changed: Set(initial ? Array(state.props.keys) : Array(props.keys)))
        }
    }
    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        guard let list = parent as? PNCollectionList else { return }
        let state = PNViewState.existing(for: child)!
        let key = state.props["_pn_list_key"] as? String ?? ""
        list.roots[key] = child
        Self.rowOwners[state.tag] = { [weak list] size in
            guard let list = list else { return }
            let height = list.horizontal ? size.width : size.height
            list.measured(key, height)
        }
        for cell in list.visibleCells.compactMap({ $0 as? PNListCell }) where cell.rowKey == key { list.attach(cell, key) }
    }
    public override func removeChild(parent: UIView, child: UIView) {
        let state = PNViewState.existing(for: child)!
        Self.rowOwners.removeValue(forKey: state.tag)
        (parent as? PNCollectionList)?.roots.removeValue(forKey: state.props["_pn_list_key"] as? String ?? "")
        child.removeFromSuperview()
    }
    public override func teardown(view: UIView) {
        guard let list = view as? PNCollectionList else { return }
        for root in list.roots.values { Self.rowOwners.removeValue(forKey: PNViewState.existing(for: root)!.tag) }
        list.roots.removeAll()
        list.delegate = nil
        list.prefetchDataSource = nil
        list.dataSource = nil
    }
    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        CGSize(width: maxW < 1e6 ? maxW : 0, height: maxH < 1e6 ? maxH : 0)
    }
    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let list = view as? PNCollectionList else { return nil }
        let animated = args["animated"] as? Bool ?? true
        if name == "scroll_to_offset" {
            list.setContentOffset(CGPoint(x: PNProps.double(args["x"]) ?? 0, y: PNProps.double(args["y"]) ?? 0), animated: animated)
        } else if name == "get_scroll_offset" {
            return ["x": list.contentOffset.x, "y": list.contentOffset.y]
        } else if name == "flash_scroll_indicators" {
            list.flashScrollIndicators()
        } else if ["scroll_to_index", "scroll_to_end"].contains(name) && !list.keys.isEmpty {
            let index = name == "scroll_to_end" ? list.keys.count - 1 : args["index"] as? Int ?? 0
            list.scrollToItem(at: IndexPath(item: max(0, min(list.keys.count - 1, index)), section: 0),
                              at: list.horizontal ? .left : .top, animated: animated)
        }
        return nil
    }
    static func measured(_ tag: Int64, _ size: CGSize) { rowOwners[tag]?(size) }
}
