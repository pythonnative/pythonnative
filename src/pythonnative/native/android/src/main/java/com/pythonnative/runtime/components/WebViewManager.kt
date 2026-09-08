package com.pythonnative.runtime.components

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.view.MotionEvent
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import com.pythonnative.runtime.bridge.JsonUtil
import com.pythonnative.runtime.bridge.str
import com.pythonnative.runtime.bridge.value
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLDecoder

/**
 * `WebView` element. Fires `on_navigation_state_change`, `on_load`,
 * `on_error`, and `on_message` (via a `window.pythonnative.postMessage`
 * shim that navigates to a `pythonnative://message/` URL). Commands:
 * `load_url`, `reload`, `go_back`, `go_forward`, `stop_loading`,
 * `inject_javascript`, `post_message`.
 */
class WebViewManager : ComponentManager() {
    private val scheme = "pythonnative://message/"

    override fun createView(context: Context, tag: Long, props: JSONObject): View {
        val wv = WebView(context)
        wv.webViewClient = client(wv)
        return wv
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun applyProps(view: View, props: JSONObject, initial: Boolean) {
        val wv = view as WebView
        val merged = propsOf(wv)
        val events = merged.value("_pn_events") as? JSONArray
        val needsJs = merged.value("inject_javascript") != null ||
            (events != null && events.length() > 0) ||
            merged.value("javascript_enabled") != false
        if (needsJs) wv.settings.javaScriptEnabled = true
        if (props.has("javascript_enabled")) wv.settings.javaScriptEnabled = JsonUtil.truthy(props.value("javascript_enabled"))
        if (props.has("dom_storage_enabled")) wv.settings.domStorageEnabled = JsonUtil.truthy(props.value("dom_storage_enabled"))
        if (props.has("user_agent")) wv.settings.userAgentString = props.str("user_agent")

        val html = props.str("html")
        val url = props.str("url") ?: sourceUrl(props.value("source"))
        // `html` takes precedence over `url` when both are present.
        if (!html.isNullOrEmpty()) {
            wv.loadDataWithBaseURL(props.str("base_url"), html, "text/html", "utf-8", null)
        } else if (!url.isNullOrEmpty()) {
            wv.loadUrl(url)
        }
        if (props.has("scroll_enabled")) applyScrollEnabled(wv, props.value("scroll_enabled"))
        ViewStyler.apply(wv, props)
    }

    private fun sourceUrl(source: Any?): String? = when (source) {
        is JSONObject -> source.str("uri") ?: source.str("url")
        is String -> source
        else -> null
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun applyScrollEnabled(wv: WebView, enabled: Any?) {
        if (enabled == false) {
            wv.setOnTouchListener { _, event -> event.action == MotionEvent.ACTION_MOVE }
        } else {
            wv.setOnTouchListener(null)
        }
    }

    private fun client(wv: WebView): WebViewClient = object : WebViewClient() {
        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            fire(wv, "on_navigation_state_change", url ?: "")
            fire(wv, "on_load_start", url ?: "")
        }

        override fun onPageFinished(view: WebView, url: String?) {
            fire(wv, "on_load", url ?: "")
            if (hasEvent(wv, "on_message")) {
                val shim = "(function(){window.pythonnative=window.pythonnative||{};" +
                    "window.pythonnative.postMessage=function(m){" +
                    "window.location.href='$scheme'+encodeURIComponent(m);};})();"
                view.evaluateJavascript(shim, null)
            }
            propsOf(wv).str("inject_javascript")?.takeIf { it.isNotEmpty() }?.let { view.evaluateJavascript(it, null) }
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) {
                fire(wv, "on_error", error.description?.toString() ?: "load error")
            }
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url?.toString() ?: return false
            return handleUrl(url)
        }

        @Deprecated("Deprecated in Java")
        override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean = handleUrl(url)

        private fun handleUrl(url: String): Boolean {
            if (url.startsWith(scheme)) {
                val message = try {
                    URLDecoder.decode(url.substring(scheme.length), "UTF-8")
                } catch (e: Exception) {
                    url.substring(scheme.length)
                }
                fire(wv, "on_message", message)
                return true
            }
            return false
        }
    }

    override fun command(view: View, name: String, args: JSONObject): Any? {
        val wv = view as? WebView ?: return null
        when (name) {
            "load_url" -> args.str("url")?.let { wv.loadUrl(it) }
            "reload" -> wv.reload()
            "go_back" -> if (wv.canGoBack()) wv.goBack()
            "go_forward" -> if (wv.canGoForward()) wv.goForward()
            "stop_loading" -> wv.stopLoading()
            "inject_javascript", "evaluate_javascript" -> {
                val script = args.str("script") ?: args.str("javascript") ?: return null
                wv.evaluateJavascript(script, null)
            }
            "post_message" -> {
                val message = JSONObject.quote(args.str("message") ?: "")
                wv.evaluateJavascript("window.dispatchEvent(new MessageEvent('message',{data:$message}));", null)
            }
            "can_go_back" -> return wv.canGoBack()
            "can_go_forward" -> return wv.canGoForward()
            "get_url" -> return wv.url
        }
        return null
    }

    override fun teardown(view: View) {
        (view as? WebView)?.let {
            it.stopLoading()
            it.destroy()
        }
    }
}
