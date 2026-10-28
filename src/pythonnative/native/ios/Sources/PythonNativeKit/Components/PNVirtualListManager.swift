import UIKit
import PNCore

/// A list's keyed rows as the renderer core's mount side holds them.
///
/// The core validated each dataset patch when it was committed; `apply`
/// publishes the next one when the list's update reaches the main thread.
/// Keys are cached until a structural edit; extents and sticky flags are
/// read from the core.
final class PNListData {
    var tag: Int64 = 0
    private(set) var keys: [String] = []
    private(set) var indices: [String: Int] = [:]
    private(set) var stickyIndices: [Int] = []
    private(set) var revision = 0

    /// Publish the next queued patch; returns whether it was a reset, or nil when none was queued.
    /// A fresh store (a recreated list view) starts from the dataset the core already published.
    @discardableResult
    func apply() -> (reset: Bool, structural: Bool)? {
        guard let raw = pn_core_list_apply(PNCore.handle, PNCore.surface, tag) else {
            guard revision == 0 else { return nil }
            let published = Int(pn_core_list_revision(PNCore.handle, PNCore.surface, tag))
            guard published > 0 else { return nil }
            revision = published
            reloadKeys()
            return (true, true)
        }
        let edits = PNJSON.decodeObject(String(cString: raw))
        pn_core_free(raw)
        revision = PNProps.int(edits["revision"]) ?? revision
        let reset = edits["reset"] as? Bool ?? false
        let structural = reset || !((edits["edits"] as? [Any]) ?? []).isEmpty
        if structural {
            reloadKeys()
        } else {
            reloadSticky()
        }
        return (reset, structural)
    }

    private func reloadKeys() {
        let count = Int(pn_core_list_count(PNCore.handle, PNCore.surface, tag))
        keys = (0..<count).map { index in
            guard let key = pn_core_list_key(PNCore.handle, PNCore.surface, tag, Int64(index)) else { return "" }
            defer { pn_core_free(key) }
            return String(cString: key)
        }
        indices = Dictionary(keys.enumerated().map { ($0.element, $0.offset) }, uniquingKeysWith: { first, _ in first })
        reloadSticky()
    }

    private func reloadSticky() {
        stickyIndices = keys.indices.filter { pn_core_list_sticky(PNCore.handle, PNCore.surface, tag, Int64($0)) != 0 }
    }

    func extent(_ index: Int) -> Double { pn_core_list_extent(PNCore.handle, PNCore.surface, tag, Int64(index)) }
    func isSticky(_ index: Int) -> Bool { stickyIndices.contains(index) }

    /// The sticky row at or before `index`, or -1.
    func sticky(at index: Int) -> Int {
        var low = 0, high = stickyIndices.count
        while low < high {
            let mid = (low + high) / 2
            if stickyIndices[mid] <= index { low = mid + 1 } else { high = mid }
        }
        return low > 0 ? stickyIndices[low - 1] : -1
    }
}

private final class PNListCell: UICollectionViewCell {
    var rowKey = ""
    override func prepareForReuse() {
        super.prepareForReuse()
        contentView.subviews.forEach { $0.removeFromSuperview() }
        rowKey = ""
    }
}

private final class PNStickyListLayout: UICollectionViewFlowLayout {
    weak var owner: PNCollectionList?
    /// Whether a header is pinned, which moves with every scroll offset.
    private var pins: Bool {
        guard let owner = owner else { return false }
        return !owner.horizontal && !owner.store.stickyIndices.isEmpty
    }
    override func shouldInvalidateLayout(forBoundsChange newBounds: CGRect) -> Bool {
        // Without pinned headers, only a size change needs new attributes.
        pins || super.shouldInvalidateLayout(forBoundsChange: newBounds)
    }
    override func layoutAttributesForElements(in rect: CGRect) -> [UICollectionViewLayoutAttributes]? {
        guard pins, let owner = owner else { return super.layoutAttributesForElements(in: rect) }
        guard var attributes = super.layoutAttributesForElements(in: rect)?.map({ $0.copy() as! UICollectionViewLayoutAttributes }) else { return nil }
        let offset = owner.contentOffset.y + owner.adjustedContentInset.top
        let headers = owner.store.stickyIndices
        var low = 0, high = headers.count
        while low < high {
            let mid = (low + high) / 2
            let top = super.layoutAttributesForItem(at: IndexPath(item: headers[mid], section: 0))?.frame.minY ?? .infinity
            if top <= offset { low = mid + 1 } else { high = mid }
        }
        guard low > 0 else { return attributes }
        let index = headers[low - 1]
        guard let pinned = super.layoutAttributesForItem(at: IndexPath(item: index, section: 0))?.copy() as? UICollectionViewLayoutAttributes else { return attributes }
        let next = low < headers.count ? (super.layoutAttributesForItem(at: IndexPath(item: headers[low], section: 0))?.frame.minY ?? .infinity) : .infinity
        pinned.frame.origin.y = min(offset, next - pinned.frame.height)
        pinned.zIndex = 1024
        attributes.removeAll { $0.indexPath.item == index }
        attributes.append(pinned)
        return attributes
    }
}

private final class PNCollectionList: UICollectionView, UICollectionViewDelegateFlowLayout, UICollectionViewDataSource, UICollectionViewDataSourcePrefetching {
    let store = PNListData()
    var keys: [String] { store.keys }
    private var measuring = false
    var heights: [String: CGFloat] = [:]
    var roots: [String: UIView] = [:]
    var listTag: Int64 = 0
    var horizontal = false
    private var lastWindow: [Int] = []
    private let flow = PNStickyListLayout()

    init() {
        flow.minimumLineSpacing = 0
        flow.minimumInteritemSpacing = 0
        super.init(frame: .zero, collectionViewLayout: flow)
        backgroundColor = .clear
        delegate = self
        prefetchDataSource = self
        register(PNListCell.self, forCellWithReuseIdentifier: "row")
        dataSource = self
        flow.owner = self
    }
    func collectionView(_ collectionView: UICollectionView, numberOfItemsInSection section: Int) -> Int { keys.count }
    func collectionView(_ collectionView: UICollectionView, cellForItemAt indexPath: IndexPath) -> UICollectionViewCell {
        let cell = collectionView.dequeueReusableCell(withReuseIdentifier: "row", for: indexPath) as! PNListCell
        let key = keys[indexPath.item]
        cell.rowKey = key
        attach(cell, key)
        request(indexPath.item)
        return cell
    }
    private func request(_ index: Int) {
        guard keys.indices.contains(index), roots[keys[index]] == nil, !store.isSticky(index) else { return }
        PNBridge.shared.emitEvent(tag: listTag, name: "on_bind_row", args: [[
            "index": index, "key": keys[index], "revision": store.revision, "width": bounds.width,
            "extent": horizontal ? bounds.width : bounds.height, "sticky": store.sticky(at: index),
        ]])
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
        guard let path = indexPathsForVisibleItems.filter({ keys.indices.contains($0.item) && !store.isSticky($0.item) }).sorted().first,
              keys.indices.contains(path.item),
              let frame = layoutAttributesForItem(at: path)?.frame else { return nil }
        return (keys[path.item], horizontal ? contentOffset.x - frame.minX : contentOffset.y - frame.minY)
    }
    func restore(_ anchor: (String, CGFloat)?) {
        guard let (key, offset) = anchor, let index = store.indices[key] else { return }
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
        if !measuring {
            measuring = true
            DispatchQueue.main.async { [weak self] in
                self?.collectionViewLayout.invalidateLayout()
                self?.restore(saved)
                self?.measuring = false
            }
        }
    }
    func update(_ props: [String: Any], changed: Set<String>) {
        if changed.contains("dataset"), props["dataset"] is [String: Any] {
            let saved = anchor()
            let before = Set(keys)
            if let patch = store.apply() {
                if patch.reset { heights.removeAll() }
                else if patch.structural {
                    for key in before.subtracting(keys) { heights.removeValue(forKey: key) }
                }
                if patch.structural {
                    // Multiple moves use sequential indices; a reload preserves the
                    // logical keyed roots and avoids UIKit's pre/post-index ambiguity.
                    reloadData()
                }
                collectionViewLayout.invalidateLayout()
                restore(saved)
            }
            lastWindow = []
            DispatchQueue.main.async { [weak self] in self?.emitWindow() }
        }
        if changed.contains("horizontal") {
            horizontal = props["horizontal"] as? Bool ?? false
            flow.scrollDirection = horizontal ? .horizontal : .vertical
            collectionViewLayout.invalidateLayout()
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
        request(index)
    }
    @objc private func refreshRequested() { PNBridge.shared.emitEvent(tag: listTag, name: "on_refresh", args: []) }
    func collectionView(_ collectionView: UICollectionView, layout: UICollectionViewLayout, sizeForItemAt indexPath: IndexPath) -> CGSize {
        let key = keys[indexPath.item]
        let extent = heights[key] ?? CGFloat(store.extent(indexPath.item) > 0 ? store.extent(indexPath.item) : 44)
        return horizontal ? CGSize(width: max(1, extent), height: bounds.height) : CGSize(width: bounds.width, height: max(1, extent))
    }
    func emitWindow() {
        let visible = indexPathsForVisibleItems.map { $0.item }.filter { store.keys.indices.contains($0) && !store.isSticky($0) }.sorted()
        let first = visible.first ?? 0, last = visible.last ?? -1
        let extent = horizontal ? bounds.width : bounds.height
        let sticky = store.sticky(at: first)
        let identity = [first, last, Int(extent), sticky, store.revision]
        guard identity != lastWindow else { return }
        lastWindow = identity
        var payload = PNScrollPayload.make(self)
        payload["first"] = first; payload["last"] = last
        payload["extent"] = Double(extent); payload["range"] = Double(horizontal ? contentSize.width : contentSize.height)
        payload["sticky"] = sticky; payload["revision"] = store.revision
        PNBridge.shared.emitEvent(tag: listTag, name: "on_window", args: [payload])
    }
    override func layoutSubviews() {
        super.layoutSubviews()
        emitWindow()
    }
    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        emitWindow()
        guard PNViewState.existing(for: self)?.hasEvent("on_scroll") == true else { return }
        PNBridge.shared.emitEvent(tag: listTag, name: "on_scroll", args: [PNScrollPayload.make(self)])
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
        list.store.tag = state.tag
        list.showsVerticalScrollIndicator = state.props["shows_scroll_indicator"] as? Bool ?? true
        list.showsHorizontalScrollIndicator = list.showsVerticalScrollIndicator
        if initial || props.keys.contains(where: { ["dataset", "horizontal", "refresh_control"].contains($0) }) {
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
