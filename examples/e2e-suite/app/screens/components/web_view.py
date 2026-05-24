"""Demo screen for [`pn.WebView`][pythonnative.WebView].

The page content depends on the runner having network access, which
isn't guaranteed in CI. We render a WebView pointed at a small inline
``data:`` URL so the demo is hermetic. Maestro only asserts the
surrounding labels — there's no reliable cross-platform way to assert
text *inside* a native WebView via the accessibility tree.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

_INLINE_DOC = (
    "data:text/html,<html><body style='font-family:sans-serif;padding:8px'>"
    "<h2>WebView inline page</h2><p>Inline HTML content.</p></body></html>"
)


@pn.component
def WebViewDemo() -> pn.Element:
    """Render a WebView with an inline HTML data URL."""
    return demo_screen(
        "WebView",
        "Renders inline HTML via a data: URL so the demo works offline.",
        section(
            "WebView body",
            pn.WebView(
                url=_INLINE_DOC,
                style=pn.style(height=160, border_radius=8, border_width=1, border_color="#CBD5E1"),
            ),
            pn.Text("WebView visible marker", style=pn.style(font_weight="600")),
            hint("Maestro asserts the 'WebView visible marker' label is present."),
        ),
    )
