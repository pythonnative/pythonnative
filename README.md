<p align="center">
  <img src="docs/assets/banner.jpg" alt="PythonNative" width="800" />
</p>

<p align="center">
  <em>Build native Android and iOS apps in Python.</em>
</p>

<p align="center">
  <a href="https://github.com/pythonnative/pythonnative/actions/workflows/ci.yml"><img src="https://github.com/pythonnative/pythonnative/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/pythonnative/pythonnative/actions/workflows/release.yml"><img src="https://github.com/pythonnative/pythonnative/actions/workflows/release.yml/badge.svg" alt="Release" /></a>
  <a href="https://pypi.org/project/pythonnative/"><img src="https://img.shields.io/pypi/v/pythonnative" alt="PyPI Version" /></a>
  <a href="https://pypi.org/project/pythonnative/"><img src="https://img.shields.io/pypi/pyversions/pythonnative" alt="Python Versions" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/pythonnative" alt="License: MIT" /></a>
  <a href="https://docs.pythonnative.com/"><img src="https://img.shields.io/website?url=https%3A%2F%2Fdocs.pythonnative.com&label=docs" alt="Docs" /></a>
</p>

<p align="center">
  <a href="https://docs.pythonnative.com/">Documentation</a> ·
  <a href="https://docs.pythonnative.com/getting-started/">Getting Started</a> ·
  <a href="https://docs.pythonnative.com/examples/">Examples</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Overview

PythonNative is a cross-platform toolkit for building native Android and iOS apps in Python. It provides a **declarative, React-like component model** with hooks and automatic reconciliation, powered by Chaquopy on Android and rubicon-objc on iOS. Write function components with `use_state`, `use_effect`, and friends, just like React, and let PythonNative handle creating and updating native views.

## Features

- **Declarative UI:** Describe *what* your UI should look like with element functions (`Text`, `Button`, `Column`, `Row`, etc.). PythonNative creates and updates native views automatically.
- **Hooks and function components:** Manage state with `use_state`, side effects with `use_effect`, and navigation with `use_navigation`, all through one consistent pattern.
- **Typed `style` prop:** Pass all visual and layout properties through a single `style` dict, fully described by the `pn.Style` `TypedDict` and the ergonomic `pn.style(...)` helper for IDE autocomplete and static checking. Compose reusable styles with `StyleSheet`.
- **Cross-platform flexbox engine:** A pure-Python, Yoga-style layout engine computes frames once and applies them to native views, so `flex`, `padding`, `aspect_ratio`, and `position: "absolute"` produce the same geometry on Android and iOS.
- **Virtual view tree + reconciler:** Element trees are diffed and patched with minimal native mutations, similar to React's reconciliation.
- **Direct native bindings:** Python calls platform APIs directly through Chaquopy and rubicon-objc, with no JavaScript bridge.
- **Custom-component SDK:** Wrap any platform widget as a first-class element with type-checked props via `pythonnative.sdk` (`Props`, `@native_component`, `element_factory`). Plugins distributed on PyPI auto-register through the `pythonnative.handlers` entry-point group.
- **CLI scaffolding:** `pn init` creates a ready-to-run project; `pn run android` and `pn run ios` build and launch your app.
- **Native-backed navigation:** Declarative `Stack`, `Tab`, and `Drawer` navigators inspired by React Navigation. The root stack drives the platform's native navigation controller (`UINavigationController` on iOS, AndroidX Navigation Component on Android), so transitions, back gestures, and the hardware back button match what users expect.
- **Fast Refresh hot reload:** `pn run --hot-reload` watches `app/` and patches edits into the running app on save, preserving component state across most changes.
- **Bundled templates:** Android Gradle and iOS Xcode templates are included, so scaffolding requires no network access.

## Quick Start

### Installation

```bash
pip install pythonnative
```

### Usage

```python
import pythonnative as pn


@pn.component
def App():
    count, set_count = pn.use_state(0)
    return pn.Column(
        pn.Text(f"Count: {count}", style=pn.style(font_size=24, bold=True)),
        pn.Button(
            "Tap me",
            on_click=lambda: set_count(count + 1),
        ),
        style=pn.style(spacing=12, padding=16),
    )
```

## Documentation

Visit [docs.pythonnative.com](https://docs.pythonnative.com/) for the full documentation, including getting started guides, platform-specific instructions for Android and iOS, API reference, and working examples.

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and guidelines for submitting pull requests.

## License

[MIT](LICENSE)
