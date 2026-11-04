import StoreKit
import UIKit

/// Registers `Purchases`, and starts listening for transactions at launch, as
/// StoreKit asks, so one that arrives with no screen isn't missed.
public enum PurchasesPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(PurchasesModuleAdapter<PurchasesModule>.self)
        registry.registerLifecycleHook(PNPurchasesHook())
    }
}

private final class PNPurchasesHook: PNAppLifecycleHook {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {
        if #available(iOS 15.0, *) {
            Task { await PNStore.shared.startListening() }
        }
    }
}

private func storeError(_ code: String, _ message: String) -> NSError {
    NSError(domain: code, code: 1, userInfo: [NSLocalizedDescriptionKey: message])
}

private let unsupported = storeError("unsupported", "Purchases need StoreKit 2, which arrived in iOS 15")

@available(iOS 15.0, *)
private func perform<Value>(_ completion: @escaping (Result<Value, Error>) -> Void, _ body: @escaping () async throws -> Value) -> (() -> Void)? {
    let task = Task {
        do {
            let value = try await body()
            DispatchQueue.main.async { completion(.success(value)) }
        } catch {
            DispatchQueue.main.async { completion(.failure(error)) }
        }
    }
    return { task.cancel() }
}

/// `Purchases`, through StoreKit 2. Below iOS 15 everything but `is_available` raises `unsupported`.
public final class PurchasesModule: PurchasesImplementation {
    public init() {}

    public func is_available(completion: @escaping (Result<Bool, Error>) -> Void) -> (() -> Void)? {
        if #available(iOS 15.0, *) {
            completion(.success(AppStore.canMakePayments))
        } else {
            completion(.success(false))
        }
        return nil
    }

    public func products(ids: [String], completion: @escaping (Result<[[String: PNJSONValue]], Error>) -> Void) -> (() -> Void)? {
        guard #available(iOS 15.0, *) else { completion(.failure(unsupported)); return nil }
        return perform(completion) { try await PNStore.shared.products(ids) }
    }

    public func purchase(product_id: String, completion: @escaping (Result<[String: PNJSONValue], Error>) -> Void) -> (() -> Void)? {
        guard #available(iOS 15.0, *) else { completion(.failure(unsupported)); return nil }
        return perform(completion) { try await PNStore.shared.purchase(product_id) }
    }

    public func restore(completion: @escaping (Result<[[String: PNJSONValue]], Error>) -> Void) -> (() -> Void)? {
        guard #available(iOS 15.0, *) else { completion(.failure(unsupported)); return nil }
        return perform(completion) { try await PNStore.shared.restore() }
    }

    public func finish(consume: Bool, id: String, token: String, completion: @escaping (Result<Void, Error>) -> Void) -> (() -> Void)? {
        guard #available(iOS 15.0, *) else { completion(.failure(unsupported)); return nil }
        return perform(completion) { await PNStore.shared.finish(id) }
    }

    public func listen() throws {
        guard #available(iOS 15.0, *) else { throw unsupported }
        Task { await PNStore.shared.subscribe() }
    }
}

@available(iOS 15.0, *)
private actor PNStore {
    static let shared = PNStore()

    private var catalog: [String: Product] = [:]
    private var unfinished: [String: Transaction] = [:]
    private var listener: Task<Void, Never>?
    private var subscribed = false
    private var held: [[String: PNJSONValue]] = []

    func startListening() {
        if listener != nil { return }
        listener = Task {
            for await update in Transaction.updates {
                await self.received(update)
            }
        }
    }

    /// Updates start at launch and Python subscribes when it gets there, so
    /// what arrives first (StoreKit replays unfinished transactions) waits.
    func subscribe() {
        subscribed = true
        let waiting = held
        held = []
        for update in waiting { announce(update) }
    }

    private func received(_ update: VerificationResult<Transaction>) {
        let wire = record(update)
        if subscribed { announce(wire) } else { held.append(wire) }
    }

    private func announce(_ wire: [String: PNJSONValue]) {
        PNModuleEvents.emit(module: "Purchases", event: "update", payload: PNValues.encode(wire))
    }

    private func record(_ verification: VerificationResult<Transaction>) -> [String: PNJSONValue] {
        let transaction = verification.unsafePayloadValue
        unfinished[String(transaction.id)] = transaction
        var verified = false
        if case .verified = verification { verified = true }
        return [
            "id": .string(String(transaction.id)),
            "product_id": .string(transaction.productID),
            "purchase_date": .number(transaction.purchaseDate.timeIntervalSince1970),
            "token": .string(verification.jwsRepresentation),
            "verified": .bool(verified),
            "revoked": .bool(transaction.revocationDate != nil),
        ]
    }

    private func wire(_ product: Product) -> [String: PNJSONValue] {
        let kind: String
        switch product.type {
        case .consumable: kind = "consumable"
        case .nonConsumable: kind = "non_consumable"
        default: kind = "subscription"
        }
        return [
            "id": .string(product.id),
            "title": .string(product.displayName),
            "description": .string(product.description),
            "price": .string("\(product.price)"),
            "currency": .string(product.priceFormatStyle.currencyCode),
            "display_price": .string(product.displayPrice),
            "kind": .string(kind),
        ]
    }

    func products(_ ids: [String]) async throws -> [[String: PNJSONValue]] {
        let found = try await Product.products(for: ids)
        for product in found { catalog[product.id] = product }
        return found.map(wire)
    }

    func purchase(_ id: String) async throws -> [String: PNJSONValue] {
        var product = catalog[id]
        if product == nil { product = try await Product.products(for: [id]).first }
        guard let product = product else {
            throw storeError("unknown_product", "The App Store doesn't know the product \"\(id)\"")
        }
        do {
            switch try await product.purchase() {
            case .success(let verification):
                return ["status": .string("purchased"), "transaction": .object(record(verification))]
            case .pending:
                return ["status": .string("pending")]
            case .userCancelled:
                return ["status": .string("cancelled")]
            @unknown default:
                throw storeError("purchase_failed", "StoreKit returned an unknown purchase result")
            }
        } catch StoreKitError.userCancelled {
            return ["status": .string("cancelled")]
        } catch let error as NSError where error.domain == "purchase_failed" {
            throw error
        } catch {
            throw storeError("purchase_failed", error.localizedDescription)
        }
    }

    func restore() async throws -> [[String: PNJSONValue]] {
        do {
            try await AppStore.sync()
        } catch StoreKitError.userCancelled {
            // Declining to sign in still leaves what's already on this device.
        } catch {
            throw storeError("restore_failed", error.localizedDescription)
        }
        var owned: [[String: PNJSONValue]] = []
        for await entitlement in Transaction.currentEntitlements {
            owned.append(record(entitlement))
        }
        return owned
    }

    func finish(_ id: String) async {
        if let transaction = unfinished.removeValue(forKey: id) {
            await transaction.finish()
            return
        }
        // A transaction from an earlier launch that this one hasn't seen yet.
        for await pending in Transaction.unfinished where String(pending.unsafePayloadValue.id) == id {
            await pending.unsafePayloadValue.finish()
            return
        }
    }
}
