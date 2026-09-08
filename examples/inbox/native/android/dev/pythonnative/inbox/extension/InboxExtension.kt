package dev.pythonnative.inbox.extension

import android.content.Context
import android.view.View
import android.widget.TextView
import android.os.Handler
import android.os.Looper
import com.pythonnative.generated.InboxBadgeProps
import com.pythonnative.generated.InboxToolsImplementation
import com.pythonnative.generated.InboxToolsModule
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.components.ComponentManager
import org.json.JSONObject

object InboxExtension: PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerComponent("InboxBadge") { InboxBadgeManager() }
        registry.registerModule { InboxToolsModule(InboxToolsService()) }
    }
}

private class InboxBadgeManager: ComponentManager() {
    override fun createView(context: Context, tag: Long, props: JSONObject): View = TextView(context).apply { textSize = 12f }
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val values = InboxBadgeProps(propsOf(view))
        (view as TextView).text = "${values.count ?: 0} offline records"
    }
}

private class InboxToolsService: InboxToolsImplementation {
    override fun format_count(count: Int): String = "$count issues"
    override fun ready(completion: (Result<String>) -> Unit) {
        Handler(Looper.getMainLooper()).postDelayed({ completion(Result.success("Offline ready")) }, 10)
    }
}
