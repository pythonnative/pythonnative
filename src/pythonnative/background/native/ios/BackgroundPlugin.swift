import BackgroundTasks
import UIKit

/// Registers `Background`, and the system's launch handlers before `didFinishLaunching` returns.
public enum BackgroundPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(BackgroundModuleAdapter<BackgroundModule>.self)
        registry.registerLifecycleHook(PNBackgroundHook())
    }
}

private final class PNBackgroundHook: PNAppLifecycleHook {
    func didFinishLaunching(_ application: UIApplication, options: [UIApplication.LaunchOptionsKey: Any]?) {
        PNBackgroundRuns.shared.registerHandlers()
    }

    func didEnterBackground() {
        PNBackgroundRuns.shared.resubmitMissing()
    }
}

/// `Background`: schedules through `BGTaskScheduler`. The runs themselves belong to `PNBackgroundRuns`.
public final class BackgroundModule: BackgroundImplementation {
    public init() {}

    public func ready() {
        PNBackgroundRuns.shared.markReady()
    }

    public func schedule(every: Double, name: String, processing: Bool, requires_charging: Bool, requires_network: Bool) throws {
        try PNBackgroundRuns.shared.schedule(PNBackgroundTask(name: name, every: every, network: requires_network, charging: requires_charging, processing: processing))
    }

    public func cancel(name: String) {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: name)
        PNBackgroundStore.update(name) { $0["scheduled"] = false }
    }

    public func status() -> [[String: PNJSONValue]] {
        PNBackgroundStore.all().map { name, row in
            var result: [String: PNJSONValue] = ["name": .string(name), "scheduled": .bool(row["scheduled"] as? Bool ?? false)]
            if let every = row["every"] as? Double { result["every"] = .number(every) }
            if let lastRun = row["last_run"] as? Double { result["last_run"] = .number(lastRun) }
            if let lastResult = row["last_result"] as? String { result["last_result"] = .string(lastResult) }
            return result
        }
    }

    public func complete(id: String, result: PNBackgroundCompleteResult) {
        PNBackgroundRuns.shared.complete(id, result: result.rawValue)
    }
}

/// One scheduled task's settings. A `BGTask` request is one-shot, so these are
/// kept to submit the next period, and across launches.
struct PNBackgroundTask {
    let name: String
    let every: Double
    let network: Bool
    let charging: Bool
    let processing: Bool

    init(name: String, every: Double, network: Bool, charging: Bool, processing: Bool) {
        self.name = name
        self.every = every
        self.network = network
        self.charging = charging
        self.processing = processing
    }

    init?(name: String, row: [String: Any]) {
        guard row["scheduled"] as? Bool == true, let every = row["every"] as? Double else { return nil }
        self.init(name: name, every: every, network: row["network"] as? Bool ?? false, charging: row["charging"] as? Bool ?? false, processing: row["processing"] as? Bool ?? false)
    }

    var row: [String: Any] {
        ["scheduled": true, "every": every, "network": network, "charging": charging, "processing": processing]
    }

    func submit() throws {
        let request: BGTaskRequest
        if processing {
            let long = BGProcessingTaskRequest(identifier: name)
            long.requiresNetworkConnectivity = network
            long.requiresExternalPower = charging
            request = long
        } else {
            request = BGAppRefreshTaskRequest(identifier: name)
        }
        request.earliestBeginDate = Date(timeIntervalSinceNow: every)
        try BGTaskScheduler.shared.submit(request)
    }
}

enum PNBackgroundStore {
    private static let key = "pn.background.tasks"

    static func all() -> [String: [String: Any]] {
        UserDefaults.standard.dictionary(forKey: key) as? [String: [String: Any]] ?? [:]
    }

    static func update(_ name: String, _ change: (inout [String: Any]) -> Void) {
        var tasks = all()
        var row = tasks[name] ?? [:]
        change(&row)
        tasks[name] = row
        UserDefaults.standard.set(tasks, forKey: key)
    }
}

/// Connects the system's launches to Python: a `run` event with an invocation
/// id, then Python's `complete(id, result)` or the system's expiration. Everything
/// here runs on the main queue.
final class PNBackgroundRuns {
    static let shared = PNBackgroundRuns()

    private var active: [String: BGTask] = [:]
    private var pythonReady = false
    private var held: [[String: String]] = []
    private var registered = false

    private var permitted: [String] {
        Bundle.main.object(forInfoDictionaryKey: "BGTaskSchedulerPermittedIdentifiers") as? [String] ?? []
    }

    func registerHandlers() {
        if registered { return }
        registered = true
        for identifier in permitted {
            BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: .main) { [weak self] task in
                self?.started(task)
            }
        }
    }

    func schedule(_ task: PNBackgroundTask) throws {
        guard permitted.contains(task.name) else {
            throw NSError(domain: "unregistered_task", code: 1, userInfo: [NSLocalizedDescriptionKey: "Add \"\(task.name)\" to [plugins.background].tasks in pythonnative.toml and rebuild; iOS only launches for identifiers listed in Info.plist"])
        }
        // An unchanged task keeps its place. Submitting again would push its
        // earliest date back on every launch.
        let saved = PNBackgroundStore.all()[task.name].flatMap { PNBackgroundTask(name: task.name, row: $0) }
        if let saved = saved, saved.every == task.every, saved.network == task.network, saved.charging == task.charging, saved.processing == task.processing {
            return
        }
        do {
            try task.submit()
        } catch {
            throw NSError(domain: "unavailable", code: 1, userInfo: [NSLocalizedDescriptionKey: "BGTaskScheduler refused \"\(task.name)\": \(error.localizedDescription)"])
        }
        PNBackgroundStore.update(task.name) { $0.merge(task.row) { _, new in new } }
    }

    /// A request can go missing if a run was killed before the next submit.
    func resubmitMissing() {
        let tasks = PNBackgroundStore.all().compactMap { name, row in PNBackgroundTask(name: name, row: row) }
        if tasks.isEmpty { return }
        BGTaskScheduler.shared.getPendingTaskRequests { requests in
            let pending = Set(requests.map(\.identifier))
            for task in tasks where !pending.contains(task.name) {
                do {
                    try task.submit()
                } catch {
                    PNLog.modules.error("background: couldn't resubmit \(task.name): \(error.localizedDescription)")
                }
            }
        }
    }

    func markReady() {
        pythonReady = true
        let waiting = held
        held = []
        for payload in waiting { PNModuleEvents.emit(module: "Background", event: "run", payload: payload) }
    }

    func started(_ task: BGTask) {
        let id = UUID().uuidString
        let name = task.identifier
        active[id] = task
        task.expirationHandler = { [weak self] in PNMain.run { self?.expired(id) } }
        PNBackgroundStore.update(name) { $0["last_run"] = Date().timeIntervalSince1970 }
        if let settings = PNBackgroundStore.all()[name].flatMap({ PNBackgroundTask(name: name, row: $0) }) {
            do {
                try settings.submit()
            } catch {
                PNLog.modules.error("background: couldn't submit the next \(name): \(error.localizedDescription)")
            }
        }
        // Python starts on every launch, but the app's imports may still be
        // running, so `run` waits until the facade has subscribed.
        let payload = ["id": id, "name": name]
        if pythonReady {
            PNModuleEvents.emit(module: "Background", event: "run", payload: payload)
        } else {
            held.append(payload)
        }
    }

    func complete(_ id: String, result: String) {
        guard let task = active.removeValue(forKey: id) else { return }
        PNBackgroundStore.update(task.identifier) { $0["last_result"] = result }
        task.setTaskCompleted(success: result == "success")
    }

    private func expired(_ id: String) {
        guard let task = active.removeValue(forKey: id) else { return }
        if let index = held.firstIndex(where: { $0["id"] == id }) {
            held.remove(at: index)
        } else {
            PNModuleEvents.emit(module: "Background", event: "expired", payload: ["id": id])
        }
        PNBackgroundStore.update(task.identifier) { $0["last_result"] = "expired" }
        task.setTaskCompleted(success: false)
    }
}
