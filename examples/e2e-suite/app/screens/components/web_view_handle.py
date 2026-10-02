"""Demo screen for [`pn.WebViewHandle`][pythonnative.WebViewHandle].

Passing a ``ref`` to a [`WebView`][pythonnative.WebView] publishes a typed
handle on ``ref.current``. The demo loads inline HTML (so it works
offline), then drives the page through the handle: ``reload()``,
``inject_javascript()``, the async ``eval_js()`` and ``can_go_back()``
queries, and ``load_url()`` with a ``data:`` URL. The page title changes
are visible to the page itself; the demo mirrors each call's result.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import ButtonsRow, DemoScreen, DemoSection, Hint, ResultText

_INLINE_HTML = (
    "<html><head><title>handle-page</title></head>"
    "<body style='font-family:sans-serif;padding:8px'>"
    "<h2>WebViewHandle page</h2><p id='p'>Inline HTML content.</p></body></html>"
)
_DATA_URL = "data:text/html,<html><head><title>second-page</title></head><body>Second page</body></html>"


@pn.component
def WebViewHandleDemo() -> pn.Node:
    """Drive a WebView through the handle published on its ref."""
    web_ref = pn.use_ref(None)
    last_call, set_last_call = pn.use_state("none")
    eval_result, set_eval_result = pn.use_state("(unread)")
    can_go_back, set_can_go_back = pn.use_state("unknown")
    reloads, set_reloads = pn.use_state(0)

    def reload() -> None:
        handle = web_ref.current
        if handle is not None:
            handle.reload()
            set_reloads(reloads + 1)
            set_last_call("reload")

    def inject() -> None:
        handle = web_ref.current
        if handle is not None:
            handle.inject_javascript("document.getElementById('p').textContent = 'injected';")
            set_last_call("inject_javascript")

    def load_second() -> None:
        handle = web_ref.current
        if handle is not None:
            handle.load_url(_DATA_URL)
            set_last_call("load_url")

    async def evaluate() -> None:
        handle = web_ref.current
        if handle is None:
            return
        result = await handle.eval_js("1 + 41")
        set_eval_result(str(result))
        set_can_go_back("yes" if await handle.can_go_back() else "no")
        set_last_call("eval_js")

    return DemoScreen(
        "WebViewHandle",
        "reload, inject JS, evaluate JS, and load URLs through ref.current.",
        DemoSection(
            "Handle",
            ResultText("Handle attached", "yes" if web_ref.current is not None else "no"),
            ResultText("Last call", last_call),
            ResultText("Eval result", eval_result),
            ResultText("Can go back", can_go_back),
            ResultText("Reloads", reloads),
            ButtonsRow(
                pn.Button("Evaluate JS", on_press=evaluate),
                pn.Button("Inject JS", on_press=inject),
            ),
            ButtonsRow(
                pn.Button("Reload page", on_press=reload),
                pn.Button("Load second page", on_press=load_second),
            ),
            Hint("eval_js('1 + 41') answers 42 on every platform."),
        ),
        DemoSection(
            "WebView body",
            pn.WebView(
                html=_INLINE_HTML,
                ref=web_ref,
                style=pn.style(height=140, border_radius=8, border_width=1, border_color="#CBD5E1"),
            ),
            pn.Text("WebViewHandle visible marker", style=pn.style(font_weight="600")),
        ),
    )
