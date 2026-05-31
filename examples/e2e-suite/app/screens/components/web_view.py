"""Demo screen for [`pn.WebView`][pythonnative.WebView].

The page content depends on the runner having network access, which
isn't guaranteed in CI. We render inline markup via the ``html=``
prop so the demo is hermetic (no network) and exercises the inline
HTML code path. Maestro only asserts the surrounding labels — there's
no reliable cross-platform way to assert text *inside* a native
WebView via the accessibility tree.
"""

from __future__ import annotations

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, section

_INLINE_HTML = (
    "<html><body style='font-family:sans-serif;padding:8px'>"
    "<h2>WebView inline page</h2><p>Inline HTML content.</p></body></html>"
)


@pn.component
def WebViewDemo() -> pn.Element:
    """Render a WebView with inline HTML via the ``html=`` prop."""
    return demo_screen(
        "WebView",
        "Renders inline HTML via the html= prop so the demo works offline.",
        section(
            "WebView body",
            pn.WebView(
                html=_INLINE_HTML,
                style=pn.style(height=160, border_radius=8, border_width=1, border_color="#CBD5E1"),
            ),
            pn.Text("WebView visible marker", style=pn.style(font_weight="600")),
            hint("Maestro asserts the 'WebView visible marker' label is present."),
        ),
    )
