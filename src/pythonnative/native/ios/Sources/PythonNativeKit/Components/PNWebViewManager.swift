import UIKit
import WebKit

/// `WebView`: `WKWebView` with navigation and script-message delegates.
///
/// Page JavaScript reaches `on_message` through
/// `window.webkit.messageHandlers.pythonnative.postMessage(value)`.
public final class PNWebViewManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        let configuration = WKWebViewConfiguration()
        let delegate = PNWebViewDelegate()
        configuration.userContentController.add(delegate, name: "pythonnative")
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = delegate
        delegate.webView = webView
        pendingDelegates[ObjectIdentifier(webView)] = delegate
        return webView
    }

    private var pendingDelegates: [ObjectIdentifier: PNWebViewDelegate] = [:]

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        if let delegate = pendingDelegates.removeValue(forKey: ObjectIdentifier(view)) {
            PNViewState.existing(for: view)?.retained.append(delegate)
            delegate.injectJavaScript = PNProps.string(PNProps.value(props, "inject_javascript"))
        }
        return view
    }

    public override func teardown(view: UIView) {
        guard let webView = view as? WKWebView else { return }
        webView.configuration.userContentController.removeScriptMessageHandler(forName: "pythonnative")
        webView.navigationDelegate = nil
        webView.stopLoading()
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        guard let webView = view as? WKWebView else { return }
        if PNProps.has(props, "inject_javascript"),
           let delegate = PNViewState.existing(for: webView)?.retained.compactMap({ $0 as? PNWebViewDelegate }).first
        {
            delegate.injectJavaScript = PNProps.string(PNProps.value(props, "inject_javascript"))
        }
        if let html = PNProps.string(PNProps.value(props, "html")), !html.isEmpty {
            let base = PNProps.string(PNProps.value(mergedProps(webView), "base_url")).flatMap { URL(string: $0) }
            webView.loadHTMLString(html, baseURL: base)
        } else if let url = PNProps.string(PNProps.value(props, "url")), !url.isEmpty, let target = URL(string: url) {
            webView.load(URLRequest(url: target))
        }
        if PNProps.has(props, "scroll_enabled") {
            webView.scrollView.isScrollEnabled = PNProps.bool(PNProps.value(props, "scroll_enabled")) ?? true
        }
        if PNProps.has(props, "allows_back_forward_gestures") {
            webView.allowsBackForwardNavigationGestures = PNProps.bool(PNProps.value(props, "allows_back_forward_gestures")) ?? false
        }
        PNViewStyler.applyCommon(webView, props)
    }

    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let webView = view as? WKWebView else { return nil }
        switch name {
        case "eval_js", "inject_javascript":
            webView.evaluateJavaScript(PNProps.string(args["source"]) ?? PNProps.string(args["script"]) ?? "") { _, _ in }
        case "reload": webView.reload()
        case "go_back": webView.goBack()
        case "go_forward": webView.goForward()
        case "stop_loading": webView.stopLoading()
        case "load_url":
            if let url = PNProps.string(args["url"]).flatMap({ URL(string: $0) }) { webView.load(URLRequest(url: url)) }
        case "get_url":
            return webView.url?.absoluteString ?? ""
        case "can_go_back":
            return webView.canGoBack
        case "can_go_forward":
            return webView.canGoForward
        default:
            break
        }
        return nil
    }
}

/// `WKNavigationDelegate` + `WKScriptMessageHandler` bridge.
final class PNWebViewDelegate: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    weak var webView: WKWebView?
    var injectJavaScript: String?

    private func currentURL() -> String {
        webView?.url?.absoluteString ?? ""
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if let js = injectJavaScript, !js.isEmpty {
            webView.evaluateJavaScript(js) { _, _ in }
        }
        PNEvents.emit(webView, "on_load", [currentURL()])
        PNEvents.emitIfWired(webView, "on_navigation_state_change", [["url": currentURL(), "loading": false, "can_go_back": webView.canGoBack, "can_go_forward": webView.canGoForward, "title": webView.title ?? ""]])
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        PNEvents.emitIfWired(webView, "on_load_start", [currentURL()])
        PNEvents.emitIfWired(webView, "on_navigation_state_change", [["url": currentURL(), "loading": true, "can_go_back": webView.canGoBack, "can_go_forward": webView.canGoForward, "title": webView.title ?? ""]])
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        PNEvents.emit(webView, "on_error", [error.localizedDescription])
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        PNEvents.emit(webView, "on_error", [error.localizedDescription])
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let webView = webView else { return }
        let body: String
        if let text = message.body as? String {
            body = text
        } else {
            body = PNJSON.encode(message.body)
        }
        PNEvents.emit(webView, "on_message", [body])
    }
}
