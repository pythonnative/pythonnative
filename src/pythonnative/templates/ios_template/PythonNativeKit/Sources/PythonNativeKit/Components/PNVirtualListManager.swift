import UIKit

/// `VirtualList`: a `UITableView` whose rows host PythonNative subtrees.
///
/// Rows are requested synchronously from Python: `on_bind_row` with
/// `[{"container": key, "index": i, "width": w, "height": h}]` returns
/// `{"root": tag}`, and the view with that tag is added to the cell's
/// content view. Recycled containers emit `on_unbind_row` with
/// `[{"container": key}]`.
public final class PNVirtualListManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let table = UITableView(frame: .zero, style: .plain)
        table.separatorStyle = .none
        table.contentInsetAdjustmentBehavior = .never
        table.register(PNVirtualListCell.self, forCellReuseIdentifier: PNVirtualListCell.reuseIdentifier)
        table.rowHeight = 44
        table.estimatedRowHeight = 0
        table.estimatedSectionHeaderHeight = 0
        table.estimatedSectionFooterHeight = 0
        if #available(iOS 15.0, *) {
            table.sectionHeaderTopPadding = 0
        }
        return table
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let table = view as? UITableView {
            let source = PNVirtualListSource(table: table)
            table.dataSource = source
            table.delegate = source
            PNViewState.existing(for: table)?.retained.append(source)
        }
        return view
    }

    public override func teardown(view: UIView) {
        guard let table = view as? UITableView else { return }
        // The list's `d` op tells Python to unmount every subtree, so the
        // cells only need to drop their hosted views.
        for cell in table.visibleCells {
            (cell as? PNVirtualListCell)?.unhost()
        }
        table.dataSource = nil
        table.delegate = nil
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let table = view as? UITableView, let state = PNViewState.existing(for: table) else { return }
        PNViewStyler.applyCommon(table, props)
        var needsReload = false
        if PNProps.has(props, "count") || PNProps.has(props, "row_height") || PNProps.has(props, "row_heights") {
            needsReload = true
        }
        if PNProps.has(props, "row_height") {
            table.rowHeight = CGFloat(PNProps.double(PNProps.value(props, "row_height")) ?? 44)
        }
        if PNProps.has(props, "shows_scroll_indicator") {
            table.showsVerticalScrollIndicator = PNProps.bool(PNProps.value(props, "shows_scroll_indicator")) ?? true
        }
        if PNProps.has(props, "scroll_enabled") {
            table.isScrollEnabled = PNProps.bool(PNProps.value(props, "scroll_enabled")) ?? true
        }
        if PNProps.has(props, "bounces") {
            table.bounces = PNProps.bool(PNProps.value(props, "bounces")) ?? true
        }
        if PNProps.has(props, "separator") {
            table.separatorStyle = PNProps.bool(PNProps.value(props, "separator")) == true ? .singleLine : .none
        }
        if PNProps.has(props, "content_inset") {
            let inset = PNProps.dict(PNProps.value(props, "content_inset")) ?? [:]
            table.contentInset = UIEdgeInsets(
                top: CGFloat(PNProps.double(inset["top"]) ?? 0), left: CGFloat(PNProps.double(inset["left"]) ?? 0),
                bottom: CGFloat(PNProps.double(inset["bottom"]) ?? 0), right: CGFloat(PNProps.double(inset["right"]) ?? 0)
            )
        }
        if let mode = PNProps.string(PNProps.value(props, "keyboard_dismiss_mode")) {
            switch mode {
            case "on_drag": table.keyboardDismissMode = .onDrag
            case "interactive": table.keyboardDismissMode = .interactive
            default: table.keyboardDismissMode = .none
            }
        }
        if PNProps.has(props, "generation") || PNProps.has(props, "data_version") {
            needsReload = true
        }
        if needsReload, !initial {
            state.extras["reload_pending"] = true
            table.reloadData()
            state.extras["reload_pending"] = false
        }
    }

    public override func setFrame(view: UIView, x: Double, y: Double, w: Double, h: Double) {
        let before = view.bounds.size
        super.setFrame(view: view, x: x, y: y, w: w, h: h)
        if let table = view as? UITableView, before.width != table.bounds.width, before.width > 0 {
            table.reloadData()
        }
    }

    public override func insertChild(parent: UIView, child: UIView, index: Int) {
        // Row subtrees are attached by the data source, never by the
        // reconciler; static children are not supported.
        PNLog.once(PNLog.components, key: "virtuallist-child", "VirtualList ignores direct children; rows come from on_bind_row")
    }

    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let table = view as? UITableView else { return nil }
        let animated = PNProps.bool(args["animated"]) ?? true
        switch name {
        case "scroll_to_offset":
            let y = CGFloat(PNProps.finite(args["y"] ?? args["offset"]))
            let x = CGFloat(PNProps.finite(args["x"]))
            table.setContentOffset(CGPoint(x: x, y: y), animated: animated)
        case "scroll_to_index":
            let count = table.numberOfRows(inSection: 0)
            guard count > 0, let index = PNProps.int(args["index"]) else { return nil }
            let row = max(0, min(index, count - 1))
            let position: UITableView.ScrollPosition
            switch PNProps.string(args["position"]) {
            case "middle", "center": position = .middle
            case "bottom", "end": position = .bottom
            case "top", "start": position = .top
            default: position = .none
            }
            table.scrollToRow(at: IndexPath(row: row, section: 0), at: position, animated: animated)
        case "scroll_to_end":
            let count = table.numberOfRows(inSection: 0)
            if count > 0 {
                table.scrollToRow(at: IndexPath(row: count - 1, section: 0), at: .bottom, animated: animated)
            }
        case "get_scroll_offset":
            return ["x": Double(table.contentOffset.x), "y": Double(table.contentOffset.y)]
        case "reload":
            table.reloadData()
        case "flash_scroll_indicators":
            table.flashScrollIndicators()
        default:
            break
        }
        return nil
    }
}

/// A recycled row container. `containerKey` is stable for the cell's lifetime.
final class PNVirtualListCell: UITableViewCell {
    static let reuseIdentifier = "PNVirtualListCell"
    private static var nextKey: Int64 = 1

    let containerKey: Int64
    private(set) var hosted: UIView?

    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        containerKey = PNVirtualListCell.nextKey
        PNVirtualListCell.nextKey += 1
        super.init(style: style, reuseIdentifier: reuseIdentifier)
        selectionStyle = .none
        backgroundColor = .clear
        contentView.clipsToBounds = true
    }

    required init?(coder: NSCoder) {
        containerKey = PNVirtualListCell.nextKey
        PNVirtualListCell.nextKey += 1
        super.init(coder: coder)
    }

    func host(_ view: UIView) {
        if hosted === view { return }
        hosted?.removeFromSuperview()
        hosted = view
        view.translatesAutoresizingMaskIntoConstraints = true
        contentView.addSubview(view)
    }

    func unhost() {
        hosted?.removeFromSuperview()
        hosted = nil
    }
}

/// Data source and delegate for one list.
final class PNVirtualListSource: NSObject, UITableViewDataSource, UITableViewDelegate {
    private weak var table: UITableView?
    private var bound: Set<Int64> = []

    init(table: UITableView) {
        self.table = table
        super.init()
    }

    private var props: [String: Any] {
        table.flatMap { PNViewState.existing(for: $0)?.props } ?? [:]
    }

    // MARK: UITableViewDataSource

    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        max(0, PNProps.int(PNProps.value(props, "count")) ?? 0)
    }

    func tableView(_ tableView: UITableView, heightForRowAt indexPath: IndexPath) -> CGFloat {
        let props = self.props
        if let heights = PNProps.value(props, "row_heights") as? [Any], indexPath.row < heights.count,
           let height = PNProps.double(heights[indexPath.row])
        {
            return CGFloat(height)
        }
        return CGFloat(PNProps.double(PNProps.value(props, "row_height")) ?? Double(tableView.rowHeight))
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let dequeued = tableView.dequeueReusableCell(withIdentifier: PNVirtualListCell.reuseIdentifier, for: indexPath)
        guard let cell = dequeued as? PNVirtualListCell else { return dequeued }
        let width = tableView.bounds.width
        let height = self.tableView(tableView, heightForRowAt: indexPath)
        bind(cell, index: indexPath.row, width: width, height: height)
        return cell
    }

    private func bind(_ cell: PNVirtualListCell, index: Int, width: CGFloat, height: CGFloat) {
        guard let table = table else { return }
        let payload: [String: Any] = [
            "container": cell.containerKey, "index": index, "width": Double(width), "height": Double(height),
        ]
        bound.insert(cell.containerKey)
        guard let reply = PNEvents.emit(table, "on_bind_row", [payload]) else {
            cell.unhost()
            return
        }
        let root = PNProps.dict(PNJSON.decode(reply))?["root"]
        guard let tag = PNProps.int(root), let view = PNViewRegistry.shared.view(for: Int64(tag)) else {
            cell.unhost()
            return
        }
        cell.host(view)
    }

    func tableView(_ tableView: UITableView, didEndDisplaying cell: UITableViewCell, forRowAt indexPath: IndexPath) {
        guard let cell = cell as? PNVirtualListCell, let table = table else { return }
        cell.unhost()
        if bound.remove(cell.containerKey) != nil {
            PNEvents.emit(table, "on_unbind_row", [["container": cell.containerKey]])
        }
    }

    // MARK: UIScrollViewDelegate

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        PNEvents.emitIfWired(scrollView, "on_scroll", [PNScrollPayload.make(scrollView)])
    }

    func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) {
        PNEvents.emitIfWired(scrollView, "on_momentum_scroll_end", [PNScrollPayload.make(scrollView)])
    }
}
