import UIKit
import YogaCore

/// The layout tree stays beside UIKit, including intrinsic text measurement.
final class PNLayoutNode {
    let tag: Int64
    let node: YGNodeRef
    var props: [String: Any] = [:]
    var children: [Int64] = []
    var parent: Int64?
    var frame: [Double] = []
    init(_ tag: Int64) {
        self.tag = tag
        node = YGNodeNew()!
        YGNodeSetContext(node, Unmanaged.passUnretained(self).toOpaque())
    }
    deinit { YGNodeFree(node) }
}

private let measureLeaf: YGMeasureFunc = { raw, width, widthMode, height, heightMode in
    guard let raw = raw, let context = YGNodeGetContext(raw) else { return YGSize(width: 0, height: 0) }
    let node = Unmanaged<PNLayoutNode>.fromOpaque(context).takeUnretainedValue()
    guard let record = PNViewRegistry.shared.resolve(node.tag) else { return YGSize(width: 0, height: 0) }
    let size = record.manager.measure(view: record.view,
        maxW: widthMode.rawValue == 0 ? 1e6 : CGFloat(width),
        maxH: heightMode.rawValue == 0 ? 1e6 : CGFloat(height))
    return YGSize(width: Float(max(0, size.width)), height: Float(max(0, size.height)))
}

private let baselineLeaf: YGBaselineFunc = { raw, _, height in
    guard let raw = raw, let context = YGNodeGetContext(raw) else { return height }
    let node = Unmanaged<PNLayoutNode>.fromOpaque(context).takeUnretainedValue()
    if let label = PNViewRegistry.shared.view(for: node.tag) as? UILabel {
        return Float(label.font.ascender)
    }
    return height
}

enum PNLayout {
    static var nodes: [Int64: PNLayoutNode] = [:]
    static var viewport: [String: Any] = [:]
    private static var scheduled = false

    static func containerDidLayout() {
        guard !scheduled else { return }
        scheduled = true
        DispatchQueue.main.async {
            scheduled = false
            let frames = compute(viewport)
            if !frames.isEmpty { PNBridge.shared.callPython(kind: "layout", tag: 0, name: "", payload: PNJSON.encode(frames)) }
        }
    }

    static func reset() {
        for entry in nodes.values { YGNodeRemoveAllChildren(entry.node) }
        nodes.removeAll()
        viewport = [:]
    }

    static func observe(_ ops: [PNTransaction.Op]) {
        for op in ops {
            switch op {
            case let .create(tag, _, props):
                let entry = PNLayoutNode(tag)
                nodes[tag] = entry
                update(entry, props)
            case let .update(tag, changed):
                if let entry = nodes[tag] { update(entry, changed) }
            case let .insert(parent, child, index):
                guard let p = nodes[parent], let c = nodes[child] else { continue }
                if let old = c.parent, let previous = nodes[old] {
                    previous.children.removeAll { $0 == child }
                    YGNodeRemoveChild(previous.node, c.node)
                }
                p.children.insert(child, at: min(index, p.children.count))
                c.parent = parent
                // Detached surfaces keep logical ownership but supply their own viewport.
                let type = PNViewRegistry.shared.resolve(parent)?.typeName ?? ""
                if !["VirtualList", "Modal", "ScreenStack"].contains(type) {
                    YGNodeSetMeasureFunc(p.node, nil)
                    YGNodeInsertChild(p.node, c.node, min(index, Int(YGNodeGetChildCount(p.node))))
                }
            case let .destroy(tag):
                if let entry = nodes.removeValue(forKey: tag), let parent = entry.parent, let p = nodes[parent] {
                    p.children.removeAll { $0 == tag }
                    YGNodeRemoveChild(p.node, entry.node)
                }
            case .frame: break
            }
        }
    }

    private static func update(_ entry: PNLayoutNode, _ changed: [String: Any]) {
        for (key, value) in changed {
            if value is NSNull { entry.props.removeValue(forKey: key) }
            else { entry.props[key] = value }
        }
        let fresh = YGNodeNew()!
        for (key, value) in entry.props {
            if let edges = value as? [String: Any], key == "margin" || key == "padding" {
                for (edge, amount) in edges {
                    let name = edge == "all" ? key : "\(key)_\(edge)"
                    _ = PNYogaSetStyle(fresh, name, String(describing: amount))
                }
            } else { _ = PNYogaSetStyle(fresh, key, String(describing: value)) }
        }
        let type = PNViewRegistry.shared.resolve(entry.tag)?.typeName ?? ""
        if ["ScrollView", "VirtualList", "ScreenStack"].contains(type) {
            YGNodeStyleSetOverflow(fresh, YGOverflow(rawValue: 1)!)
            YGNodeStyleSetFlexShrink(fresh, 1)
        }
        YGNodeCopyStyle(entry.node, fresh)
        YGNodeFree(fresh)
        if YGNodeGetChildCount(entry.node) == 0 && !["View", "Column", "Row", "ScrollView", "Modal", "Portal", "ScreenStack"].contains(type) {
            YGNodeSetMeasureFunc(entry.node, measureLeaf)
            YGNodeSetBaselineFunc(entry.node, baselineLeaf)
            YGNodeMarkDirty(entry.node)
        }
    }

    static func compute(_ request: [String: Any]) -> [[Double]] {
        viewport = request
        let width = (request["width"] as? NSNumber)?.floatValue ?? 0
        let height = (request["height"] as? NSNumber)?.floatValue ?? 0
        guard width > 0, height > 0 else { return [] }
        let roots = request["roots"] as? [Int64] ?? []
        for tag in roots {
            if let entry = nodes[tag] { YGNodeCalculateLayout(entry.node, width, height, YGDirection(rawValue: 1)!) }
        }
        // A portal is absent from the screen tree, but remains a Yoga parent
        // so absolute insets and sibling layout resolve against its viewport.
        for entry in nodes.values {
            guard let record = PNViewRegistry.shared.resolve(entry.tag), record.typeName == "Portal" else { continue }
            let size = record.view.bounds.size
            let portalWidth = size.width > 0 ? Float(size.width) : width
            let portalHeight = size.height > 0 ? Float(size.height) : height
            YGNodeStyleSetWidth(entry.node, portalWidth)
            YGNodeStyleSetHeight(entry.node, portalHeight)
            YGNodeCalculateLayout(entry.node, portalWidth, portalHeight, YGDirection(rawValue: 1)!)
        }
        // Every detached root is laid out in its native container's available space.
        for entry in nodes.values where entry.parent != nil && YGNodeGetOwner(entry.node) == nil {
            let parent = entry.parent.flatMap { PNViewRegistry.shared.resolve($0) }
            let screen = PNViewRegistry.shared.resolve(entry.tag)
            let size = (screen?.typeName == "Screen" ? screen?.view.bounds.size : parent?.view.bounds.size)
                ?? CGSize(width: CGFloat(width), height: CGFloat(height))
            let isList = parent?.typeName == "VirtualList"
            let horizontal = parent.flatMap { PNViewState.existing(for: $0.view)?.props["horizontal"] as? Bool } ?? false
            YGNodeCalculateLayout(entry.node, isList && horizontal ? Float.nan : Float(size.width > 0 ? size.width : CGFloat(width)),
                                  isList && !horizontal ? Float.nan : Float(size.height > 0 ? size.height : CGFloat(height)), YGDirection(rawValue: 1)!)
        }
        var frames: [[Double]] = []
        for entry in nodes.values {
            let frame = [Double(YGNodeLayoutGetLeft(entry.node)), Double(YGNodeLayoutGetTop(entry.node)),
                         Double(YGNodeLayoutGetWidth(entry.node)), Double(YGNodeLayoutGetHeight(entry.node))]
            if frame == entry.frame { continue }
            entry.frame = frame
            if !roots.contains(entry.tag), let record = PNViewRegistry.shared.resolve(entry.tag) {
                record.manager.setFrame(view: record.view, x: frame[0], y: frame[1], w: frame[2], h: frame[3])
            }
            PNVirtualListManager.measured(entry.tag, CGSize(width: frame[2], height: frame[3]))
            frames.append([Double(entry.tag)] + frame)
        }
        return frames
    }

    static func invalidate(_ tag: Int64) {
        guard let node = nodes[tag], YGNodeHasMeasureFunc(node.node) else { return }
        YGNodeMarkDirty(node.node)
        let frames = compute(viewport)
        if !frames.isEmpty { PNBridge.shared.callPython(kind: "layout", tag: 0, name: "", payload: PNJSON.encode(frames)) }
    }
}
