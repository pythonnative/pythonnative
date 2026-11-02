package com.pythonnative.plugins.background

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.pythonnative.generated.BackgroundImplementation
import com.pythonnative.generated.BackgroundModuleAdapter
import com.pythonnative.generated.PNBackgroundCompleteResult
import com.pythonnative.generated.PNJSONValue
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.core.PNCore
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNHeadless
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit

private const val KEY_NAME = "pn_task"
private const val WORK_PREFIX = "pn.background."

// JobScheduler stops work at 10 minutes. Finishing first lets Python hear why.
private const val RUN_TIMEOUT_MS = 9 * 60 * 1000L

/** Registers `Background`. WorkManager's own manifest entries arrive through its library. */
object BackgroundPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { BackgroundModuleAdapter(BackgroundModule()) }
    }
}

/** `Background`: schedules through WorkManager. The runs themselves belong to [BackgroundRuns]. */
class BackgroundModule : BackgroundImplementation {
    private val context: Context get() = PNBridge.context()

    override fun ready() = BackgroundRuns.markReady()

    override fun schedule(every: Double, name: String, processing: Boolean, requires_charging: Boolean, requires_network: Boolean) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(if (requires_network) NetworkType.CONNECTED else NetworkType.NOT_REQUIRED)
            .setRequiresCharging(requires_charging)
            .build()
        val request = PeriodicWorkRequestBuilder<BackgroundWorker>(every.toLong(), TimeUnit.SECONDS)
            // WorkManager would run the first period immediately. iOS can't, and `every` is the shortest gap.
            .setInitialDelay(every.toLong(), TimeUnit.SECONDS)
            .setConstraints(constraints)
            .setInputData(workDataOf(KEY_NAME to name))
            .build()
        // UPDATE applies changed settings and keeps the task's place in the queue.
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK_PREFIX + name, ExistingPeriodicWorkPolicy.UPDATE, request)
        BackgroundState.update(context, name) { it.put("scheduled", true).put("every", every) }
    }

    override fun cancel(name: String) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_PREFIX + name)
        BackgroundState.update(context, name) { it.put("scheduled", false) }
    }

    override fun status(): List<Map<String, PNJSONValue>> = BackgroundState.all(context).map { (name, row) ->
        buildMap {
            put("name", PNJSONValue(name))
            put("scheduled", PNJSONValue(row.optBoolean("scheduled")))
            if (row.has("every")) put("every", PNJSONValue(row.getDouble("every")))
            if (row.has("last_run")) put("last_run", PNJSONValue(row.getDouble("last_run")))
            if (row.has("last_result")) put("last_result", PNJSONValue(row.getString("last_result")))
        }
    }

    override fun complete(id: String, result: PNBackgroundCompleteResult) = BackgroundRuns.complete(id, result.rawValue)
}

/** What `status()` reports, kept because WorkManager's own answer can't be read without blocking. */
private object BackgroundState {
    private const val FILE = "pn_background"

    @Synchronized
    fun all(context: Context): Map<String, JSONObject> {
        val saved = context.getSharedPreferences(FILE, Context.MODE_PRIVATE).all
        return saved.mapValues { (_, row) -> JSONObject(row as String) }
    }

    @Synchronized
    fun update(context: Context, name: String, change: (JSONObject) -> Unit) {
        val preferences = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val row = JSONObject(preferences.getString(name, null) ?: "{}")
        change(row)
        preferences.edit().putString(name, row.toString()).apply()
    }
}

/** Connects workers to Python: a `run` event with an invocation id, then Python's `complete(id, result)`. */
private object BackgroundRuns {
    private var pythonReady = false
    private val held = ArrayList<Map<String, String>>()
    private val waiting = HashMap<String, CompletableDeferred<String>>()

    @Synchronized
    fun markReady() {
        pythonReady = true
        held.forEach { ModuleEvents.emit("Background", "run", it) }
        held.clear()
    }

    /** `run` waits here until the facade has subscribed. A process that started for this job isn't there yet. */
    @Synchronized
    fun begin(id: String, name: String): CompletableDeferred<String> {
        val outcome = CompletableDeferred<String>()
        waiting[id] = outcome
        val payload = mapOf("id" to id, "name" to name)
        if (pythonReady) ModuleEvents.emit("Background", "run", payload) else held.add(payload)
        return outcome
    }

    @Synchronized
    fun complete(id: String, result: String) {
        waiting.remove(id)?.complete(result)
    }

    /** The system or the timeout ended a run. A run Python never heard of just disappears. */
    @Synchronized
    fun expire(id: String) {
        waiting.remove(id)
        if (!held.removeAll { it["id"] == id }) ModuleEvents.emit("Background", "expired", mapOf("id" to id))
    }
}

/** One periodic run. WorkManager constructs this by name, possibly in a process with no activity. */
class BackgroundWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val name = inputData.getString(KEY_NAME) ?: return Result.failure()
        val id = UUID.randomUUID().toString()
        BackgroundState.update(applicationContext, name) { it.put("last_run", System.currentTimeMillis() / 1000.0) }
        val outcome = BackgroundRuns.begin(id, name)
        try {
            withContext(Dispatchers.IO) {
                // `PNBridge.setContext` does this when an activity exists, and
                // Python can't open the renderer core without it.
                PNCore.install(applicationContext)
                PNHeadless.ensureStarted()
            }
            val result = withTimeoutOrNull(RUN_TIMEOUT_MS) { outcome.await() }
            if (result == null) BackgroundRuns.expire(id)
            BackgroundState.update(applicationContext, name) { it.put("last_result", result ?: "expired") }
            return when (result) {
                "success" -> Result.success()
                "failure" -> Result.failure()
                else -> Result.retry()
            }
        } catch (stopped: CancellationException) {
            // The system took the job back: its constraints lapsed, or it ran out of time.
            BackgroundRuns.expire(id)
            BackgroundState.update(applicationContext, name) { it.put("last_result", "expired") }
            throw stopped
        } catch (error: Exception) {
            Log.e(PNBridge.TAG, "background task $name couldn't start Python", error)
            BackgroundRuns.expire(id)
            BackgroundState.update(applicationContext, name) { it.put("last_result", "failure") }
            return Result.retry()
        }
    }
}
