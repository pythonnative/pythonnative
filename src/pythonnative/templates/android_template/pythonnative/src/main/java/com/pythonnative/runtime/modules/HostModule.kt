package com.pythonnative.runtime.modules

import androidx.fragment.app.FragmentActivity
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.screens.Navigator
import com.pythonnative.runtime.screens.PNScreenFragment
import com.pythonnative.runtime.screens.ScreenRegistry
import org.json.JSONArray
import org.json.JSONObject

/**
 * `Host`: screen hosting and navigation. Screens are the integer ids
 * assigned by [ScreenRegistry] when a [PNScreenFragment] is created.
 */
class HostModule : NativeModule {
    override val name = "Host"

    private fun screen(args: JSONObject): PNScreenFragment? = ScreenRegistry.get(JsonUtil.toInt(args.opt("screen")))

    private fun activity(): FragmentActivity? = PNBridge.activity() as? FragmentActivity

    private fun argsJson(args: JSONObject): String? {
        val value = args.value("args") ?: return null
        return if (value is String) value else value.toString()
    }

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "attach_root" -> {
                val fragment = screen(args) ?: return promise.reject("unknown screen", "unknown_screen")
                val record = PNBridge.registry.get(JsonUtil.toLong(args.opt("tag")))
                    ?: return promise.reject("unknown tag", "unknown_tag")
                fragment.attachRoot(record.view)
                promise.resolve(null)
            }
            "detach_root" -> {
                val fragment = screen(args)
                val record = PNBridge.registry.get(JsonUtil.toLong(args.opt("tag")))
                if (record != null) {
                    if (fragment != null) fragment.detachRoot(record.view) else (record.view.parent as? android.view.ViewGroup)?.removeView(record.view)
                }
                promise.resolve(null)
            }
            "push" -> {
                val activity = activity() ?: return promise.resolve(false)
                promise.resolve(Navigator.push(activity, args.str("path") ?: "", argsJson(args), args.str("title")))
            }
            "pop" -> {
                val activity = activity() ?: return promise.resolve(false)
                promise.resolve(Navigator.pop(activity, JsonUtil.toInt(args.opt("count"), 1).coerceAtLeast(1)))
            }
            "pop_to_root" -> {
                val activity = activity() ?: return promise.resolve(false)
                promise.resolve(Navigator.popToRoot(activity))
            }
            "replace" -> {
                val activity = activity() ?: return promise.resolve(false)
                promise.resolve(Navigator.replace(activity, args.str("path") ?: "", argsJson(args), args.str("title")))
            }
            "reset" -> {
                val activity = activity() ?: return promise.resolve(false)
                val screens = ArrayList<Triple<String, String?, String?>>()
                val list = args.value("screens") as? JSONArray
                if (list != null) {
                    for (i in 0 until list.length()) {
                        val entry = list.optJSONObject(i) ?: continue
                        screens.add(Triple(entry.str("path") ?: "", argsJson(entry), entry.str("title")))
                    }
                }
                promise.resolve(Navigator.reset(activity, screens))
            }
            "set_options" -> {
                val options = args.value("options") as? JSONObject ?: JSONObject()
                options.str("title")?.let { title -> activity()?.title = title }
                promise.resolve(null)
            }
            "viewport" -> {
                val fragment = screen(args) ?: ScreenRegistry.get(ScreenRegistry.activeId())
                val payload = fragment?.viewport() ?: activity()?.window?.decorView?.let {
                    com.pythonnative.runtime.screens.Viewport.describe(it)
                } ?: JSONObject()
                promise.resolve(payload)
            }
            "post" -> {
                MainThread.post { PNBridge.callPython("pump", 0, "", "") }
                promise.resolve(null)
            }
            "is_main_thread" -> promise.resolve(MainThread.isMain())
            "active_screen" -> promise.resolve(ScreenRegistry.activeId())
            else -> promise.rejectUnknownMethod(method)
        }
    }
}
