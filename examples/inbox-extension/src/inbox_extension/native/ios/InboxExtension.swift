import UIKit
import DequeModule

public enum InboxExtension: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("InboxBadge") { InboxBadgeManager() }
        registry.registerModule(InboxToolsModuleAdapter<InboxToolsService>.self)
    }
}

private final class InboxBadgeManager: PNTypedComponentManager<InboxBadgeProps> {
    init() { super.init(InboxBadgeProps.self) }
    override func makeView(props: [String: Any]) -> UIView {
        let button = UIButton(type: .system)
        button.titleLabel?.font = UIFont.preferredFont(forTextStyle: .caption1)
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        return button
    }
    override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        guard let button = view as? UIButton else { return view }
        // Attach after creation so the view's state retains the action target.
        PNActionTarget.attach(button, events: .touchUpInside) { [weak button] in
            guard let button = button,
                  let props = try? InboxBadgeProps(PNViewState.existing(for: button)?.props ?? [:]) else { return }
            PNComponentEvents.InboxBadge.on_press(button, props.count ?? 0)
        }
        return button
    }
    override func applyTyped(view: UIView, props: InboxBadgeProps, initial: Bool) {
        PNViewStyler.applyCommon(view, props.values)
        guard let button = view as? UIButton else { return }
        if initial || props.has_count { button.setTitle("\(props.count ?? 0) offline records", for: .normal) }
    }
}

private final class InboxToolsService: InboxToolsImplementation {
    init() {}
    func prepare(records: [PNInboxRecord], limit: Int64, delay_ms: Int64,
                 completion: @escaping (Result<PNInboxBatch, Error>) -> Void) -> (() -> Void)? {
        let work = DispatchWorkItem {
            var queue = Deque<PNInboxRecord>()
            var seen = Set<String>()
            for record in records where seen.insert(record.identifier).inserted { queue.append(record) }
            var selected: [PNInboxRecord] = []
            for _ in 0..<min(max(0, Int(limit)), queue.count) {
                if let record = queue.popFirst() { selected.append(record) }
            }
            do {
                guard let resource = Bundle.module.url(forResource: "inbox_labels", withExtension: "json", subdirectory: "PluginResources/InboxExtension/ios/resources") else {
                    throw NSError(domain: "InboxExtension", code: 1, userInfo: [NSLocalizedDescriptionKey: "Bundled inbox labels are missing"])
                }
                let labels = try JSONDecoder().decode([String: String].self, from: Data(contentsOf: resource))
                let batch = PNInboxBatch(records: selected, message: labels["ready"] ?? "Offline ready")
                InboxToolsEvents.prepared(batch)
                completion(.success(batch))
            } catch { completion(.failure(error)) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + Double(max(0, delay_ms)) / 1000, execute: work)
        return { work.cancel() }
    }
}
