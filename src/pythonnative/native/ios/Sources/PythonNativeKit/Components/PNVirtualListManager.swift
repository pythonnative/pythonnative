import UIKit

private final class PNListCell: UICollectionViewCell {
    var rowKey = ""
    override func prepareForReuse() {
        super.prepareForReuse()
        contentView.subviews.forEach { $0.removeFromSuperview() }
        rowKey = ""
    }
}

private final class PNCollectionList: UICollectionView, UICollectionViewDelegateFlowLayout {
    var keys: [String] = []
    var revision = 0
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
        register(PNListCell.self, forCellWithReuseIdentifier: "row")
        source = UICollectionViewDiffableDataSource<Int, String>(collectionView: self) { [weak self] collection, path, key in
            guard let self = self else { return nil }
            let cell = collection.dequeueReusableCell(withReuseIdentifier: "row", for: path) as! PNListCell
            cell.rowKey = key
            self.attach(cell, key)
            PNBridge.shared.emitEvent(tag: self.listTag, name: "on_bind_row", args: [[
                "index": path.item, "key": key, "revision": self.revision, "width": self.bounds.width,
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
    func update(_ props: [String: Any]) {
        let oldFirst = indexPathsForVisibleItems.sorted().first
        let anchor = oldFirst.flatMap { source.itemIdentifier(for: $0) }
        let offset = oldFirst.flatMap { layoutAttributesForItem(at: $0)?.frame }.map { horizontal ? contentOffset.x - $0.minX : contentOffset.y - $0.minY } ?? 0
        keys = props["keys"] as? [String] ?? []
        revision = props["revision"] as? Int ?? 0
        estimates = props["row_heights"] as? [Double] ?? []
        horizontal = props["horizontal"] as? Bool ?? false
        flow.scrollDirection = horizontal ? .horizontal : .vertical
        heights = heights.filter { keys.contains($0.key) }
        var snapshot = NSDiffableDataSourceSnapshot<Int, String>()
        snapshot.appendSections([0])
        snapshot.appendItems(keys)
        let previous = Set(source.snapshot().itemIdentifiers)
        snapshot.reloadItems(keys.filter { previous.contains($0) })
        source.apply(snapshot, animatingDifferences: false) { [weak self] in
            guard let self = self, let anchor = anchor, let position = self.keys.firstIndex(of: anchor) else { return }
            self.layoutIfNeeded()
            if let attributes = self.layoutAttributesForItem(at: IndexPath(item: position, section: 0)) {
                if self.horizontal { self.contentOffset.x = attributes.frame.minX + offset }
                else { self.contentOffset.y = attributes.frame.minY + offset }
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
    @objc private func refreshRequested() { PNBridge.shared.emitEvent(tag: listTag, name: "on_refresh", args: []) }
    func collectionView(_ collectionView: UICollectionView, layout: UICollectionViewLayout, sizeForItemAt indexPath: IndexPath) -> CGSize {
        let key = keys[indexPath.item]
        let extent = heights[key] ?? CGFloat(indexPath.item < estimates.count ? estimates[indexPath.item] : 44)
        return horizontal ? CGSize(width: max(1, extent), height: bounds.height) : CGSize(width: bounds.width, height: max(1, extent))
    }
    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        let visible = indexPathsForVisibleItems.map { $0.item }
        PNBridge.shared.emitEvent(tag: listTag, name: "on_scroll", args: [[
            "x": contentOffset.x, "y": contentOffset.y, "extent": horizontal ? bounds.width : bounds.height, "range": horizontal ? contentSize.width : contentSize.height,
            "first": visible.min() ?? 0, "last": visible.max() ?? -1,
        ]])
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
        if initial || props.keys.contains(where: { ["keys", "revision", "row_heights", "horizontal", "refresh_control"].contains($0) }) {
            list.update(state.props)
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
            guard height > 0, list.heights[key] != height else { return }
            list.heights[key] = height
            list.collectionViewLayout.invalidateLayout()
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
        } else if !list.keys.isEmpty {
            let index = name == "scroll_to_end" ? list.keys.count - 1 : args["index"] as? Int ?? 0
            list.scrollToItem(at: IndexPath(item: max(0, min(list.keys.count - 1, index)), section: 0),
                              at: list.horizontal ? .left : .top, animated: animated)
        }
        return nil
    }
    static func measured(_ tag: Int64, _ size: CGSize) { rowOwners[tag]?(size) }
}
