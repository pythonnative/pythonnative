"""Development tools that run inside the app: the devtools agent.

Development builds (PythonNative Go, a project's debug build, and the
browser preview) install one [`Agent`][pythonnative.devtools.agent.Agent].
It answers DevTools requests (the component tree, inspection, the REPL,
performance sampling, the debugger) and publishes what the app does
(warnings and errors, network requests, performance samples). It also
owns the on-device dev menu, element inspector, and performance monitor.

Release bundles omit this package, like the dev client and Fast Refresh.
See RFC 0006 and the DevTools guide.
"""

from .agent import Agent, MenuItem, current, install, uninstall

__all__ = ["Agent", "MenuItem", "current", "install", "uninstall"]
