package com.pythonnative.runtime.modules

import androidx.fragment.app.FragmentActivity
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import com.pythonnative.runtime.screens.PNScreenFragment
import com.pythonnative.runtime.screens.ScreenRegistry
import org.json.JSONObject

/**
 * `Host`: screen hosting and navigation. Screens are the integer ids
 * assigned by [ScreenRegistry] when a [PNScreenFragment] is created.
 */
class HostModule : NativeModule {
    override val name = "Host"

    private fun screen(args: JSONObject): PNScreenFragment? = ScreenRegistry.get(JsonUtil.toInt(args.opt("screen")))

    private fun activity(): FragmentActivity? = PNBridge.activity() as? FragmentActivity

    override fun call(method: String, args: JSONObject, promise: Promise) {
        when (method) {
            "show_error" -> {
                ErrorOverlay.show(args.optLong("screen"), args.optString("title"), args.optString("trace"))
                promise.resolve(null)
            }
            "dismiss_error" -> { ErrorOverlay.dismiss(); promise.resolve(null) }
            "cache_state" -> {
                screen(args)?.cachedStateJSON = args.str("state")
                promise.resolve(null)
            }
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
            "finish" -> { activity()?.finish(); promise.resolve(null) }
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
            "active_screen" -> promise.resolve(ScreenRegistry.activeId())
            // Predictive back: `false` when Python has nothing to pop, so the
            // system plays its back-to-home preview; see PNScreenFragment.
            "set_back_enabled" -> {
                val enabled = args.value("enabled") != false
                val target = screen(args) ?: ScreenRegistry.get(ScreenRegistry.activeId())
                target?.backEnabled = enabled
                promise.resolve(null)
            }
            "keyboard" -> promise.resolve(
                JSONObject().put("height", com.pythonnative.runtime.screens.PNKeyboard.heightDp)
                    .put("visible", com.pythonnative.runtime.screens.PNKeyboard.isVisible),
            )
            else -> promise.rejectUnknownMethod(method)
        }
    }
}
