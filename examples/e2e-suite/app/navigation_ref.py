"""The app-wide [`NavigationRef`][pythonnative.NavigationRef].

``main.py`` binds it to the root ``NavigationContainer`` so code that
runs outside any component (push handlers, deep links, tests) can drive
navigation. The ``navigation_ref`` demo reads and drives it.
"""

from __future__ import annotations

import pythonnative as pn

nav_ref: pn.NavigationRef = pn.create_navigation_ref()
"""Bound to the root container while the app is mounted."""
