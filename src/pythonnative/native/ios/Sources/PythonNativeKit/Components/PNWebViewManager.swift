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
        let typed = try! WebViewProps(props, validated: true)

        guard let webView = view as? WKWebView else { return }
        if typed.has_inject_javascript,
           let delegate = PNViewState.existing(for: webView)?.retained.compactMap({ $0 as? PNWebViewDelegate }).first
        {
            delegate.injectJavaScript = typed.inject_javascript
        }
        if let html = typed.html, !html.isEmpty {
            let base = PNProps.string(PNProps.value(mergedProps(webView), "base_url")).flatMap { URL(string: $0) }
            webView.loadHTMLString(html, baseURL: base)
        } else if let url = typed.url, !url.isEmpty, let target = URL(string: url) {
            webView.load(URLRequest(url: target))
        }
        if typed.has_scroll_enabled {
            webView.scrollView.isScrollEnabled = typed.scroll_enabled ?? true
        }
        if PNProps.has(props, "allows_back_forward_gestures") {
            webView.allowsBackForwardNavigationGestures = PNProps.bool(PNProps.value(props, "allows_back_forward_gestures")) ?? false
        }
        PNViewStyler.applyCommon(webView, props)
    }

    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        guard let webView = view as? WKWebView else { return nil }
        switch name {
        case "inject_javascript":
            webView.evaluateJavaScript(PNProps.string(args["script"]) ?? "") { _, _ in }
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
        PNComponentEvents.WebView.on_navigation_state_change(webView, PNWebNavigationEvent(url: currentURL(), loading: false, can_go_back: webView.canGoBack, can_go_forward: webView.canGoForward, title: webView.title ?? ""))
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        PNEvents.emitIfWired(webView, "on_load_start", [currentURL()])
        PNComponentEvents.WebView.on_navigation_state_change(webView, PNWebNavigationEvent(url: currentURL(), loading: true, can_go_back: webView.canGoBack, can_go_forward: webView.canGoForward, title: webView.title ?? ""))
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

/// `WebViews`: asynchronous questions for a mounted `WebView`. WebKit
/// answers `evaluateJavaScript` later on the main thread, so the result
/// settles a promise instead of returning from a synchronous view command.
public final class WebViewsModule: WebViewsImplementation {
    public init() {}

    public func eval_js(tag: Int64, script: String, completion: @escaping (Result<String, Error>) -> Void) -> (() -> Void)? {
        DispatchQueue.main.async {
            guard let webView = PNViewRegistry.shared.view(for: tag) as? WKWebView else {
                completion(.failure(NSError(domain: "WebViews", code: 1, userInfo: [NSLocalizedDescriptionKey: "no WebView with tag \(tag)"])))
                return
            }
            webView.evaluateJavaScript(script) { value, error in
                if let error = error {
                    completion(.failure(error))
                } else {
                    completion(.success(WebViewsModule.stringify(value)))
                }
            }
        }
        return nil
    }

    /// A script result as a string: strings as-is, `null` and `undefined`
    /// as `""`, booleans and numbers in their JavaScript spelling, and
    /// arrays and objects as JSON.
    public static func stringify(_ value: Any?) -> String {
        switch value {
        case nil, is NSNull:
            return ""
        case let string as String:
            return string
        case let number as NSNumber:
            if CFGetTypeID(number) == CFBooleanGetTypeID() { return number.boolValue ? "true" : "false" }
            let double = number.doubleValue
            if double.isFinite, double == double.rounded(), abs(double) < 1e15 { return String(Int64(double)) }
            return number.stringValue
        default:
            if let value = value, JSONSerialization.isValidJSONObject(value),
               let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) {
                return String(decoding: data, as: UTF8.self)
            }
            return String(describing: value!)
        }
    }
}
