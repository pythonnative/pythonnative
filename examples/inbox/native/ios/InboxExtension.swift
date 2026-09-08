import UIKit

public enum InboxExtension: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerComponent("InboxBadge") { InboxBadgeManager() }
        registry.registerModule(InboxToolsModule<InboxToolsService>.self)
    }
}

private final class InboxBadgeManager: PNComponentManager {
    override func makeView(props: [String: Any]) -> UIView {
        let label = UILabel()
        label.font = UIFont.preferredFont(forTextStyle: .caption1)
        label.adjustsFontForContentSizeCategory = true
        label.textColor = .secondaryLabel
        return label
    }
    override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let label = view as? UILabel, let values = try? InboxBadgeProps(PNViewState.existing(for: view)?.props ?? props) else { return }
        label.text = "\(values.count ?? 0) offline records"
    }
}

private final class InboxToolsService: InboxToolsImplementation {
    init() {}
    func format_count(count: Int) throws -> String { "\(count) issues" }
    func ready(completion: @escaping (Result<String, Error>) -> Void) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.01) { completion(.success("Offline ready")) }
    }
}
