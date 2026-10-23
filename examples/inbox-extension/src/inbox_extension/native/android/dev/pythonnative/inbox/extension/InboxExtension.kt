package dev.pythonnative.inbox.extension

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import androidx.collection.ArrayMap
import com.pythonnative.generated.*
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.components.TypedComponentManager
import org.json.JSONObject

object InboxExtension: PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerComponent("InboxBadge") { InboxBadgeManager() }
        registry.registerModule { InboxToolsModuleAdapter(InboxToolsService()) }
    }
}

private class InboxBadgeManager: TypedComponentManager<InboxBadgeProps>({ values, partial -> InboxBadgeProps(values, partial) }) {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = Button(context).apply {
        textSize = 12f
        setOnClickListener { PNComponentEvents.InboxBadge.on_press(this, InboxBadgeProps(propsOf(this)).count ?: 0L) }
    }
    override fun applyTyped(view: View, props: InboxBadgeProps, initial: Boolean) {
        com.pythonnative.runtime.components.ViewStyler.apply(view, props.values)
        if (initial || props.has_count) (view as Button).text = "${props.count ?: 0} offline records"
    }
}

private class InboxToolsService: InboxToolsImplementation {
    override fun prepare(records: List<PNInboxRecord>, limit: Long, delay_ms: Long,
                         completion: (Result<PNInboxBatch>) -> Unit): (() -> Unit)? {
        val handler = Handler(Looper.getMainLooper())
        val work = Runnable {
            val result = runCatching {
                val index = ArrayMap<String, PNInboxRecord>()
                val selected = ArrayList<PNInboxRecord>()
                for (record in records) {
                    if (!index.containsKey(record.identifier)) {
                        index[record.identifier] = record
                        if (selected.size.toLong() < limit) selected.add(record)
                    }
                }
                val labels = PNBridge.context().assets.open("InboxExtension/inbox_labels.json").bufferedReader().use { JSONObject(it.readText()) }
                PNInboxBatch(selected, labels.getString("ready"))
            }
            result.onSuccess { InboxToolsEvents.prepared(it) }
            completion(result)
        }
        handler.postDelayed(work, delay_ms.coerceAtLeast(0))
        return { handler.removeCallbacks(work) }
    }
}
