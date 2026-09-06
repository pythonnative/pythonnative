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
  <a href="https://pythonnative.com/"><img src="https://img.shields.io/website?url=https%3A%2F%2Fpythonnative.com&label=docs" alt="Docs" /></a>
</p>

<p align="center">
  <a href="https://pythonnative.com/">Documentation</a> ·
  <a href="https://pythonnative.com/getting-started/">Getting Started</a> ·
  <a href="https://pythonnative.com/examples/">Examples</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Overview

PythonNative is a cross-platform toolkit for building native Android and iOS apps in Python. It provides a **declarative, React-like component model** with hooks and automatic reconciliation on top of a **native rendering core** written in Swift and Kotlin. Write function components with `use_state`, `use_effect`, and friends, just like React, and let PythonNative handle creating and updating native views.

## Features

- **Declarative components and hooks:** Describe native UI with Python functions, immutable elements, and typed styles. State, effects, context, and suspense boundaries follow one logical application tree across screens, overlays, and mounted list rows.
- **Native widgets and layout:** Swift and Kotlin component managers own UIKit and Android widgets. The shared Yoga C++ engine computes layout beside the controls, using platform measurements for text and intrinsic sizes.
- **Standard asyncio:** Components, effects, event handlers, and tasks run on a dedicated Python application thread. Native UI threads handle widgets, scrolling, and animation frames. Component-owned tasks are canceled on unmount.
- **Incremental reconciliation:** State changes update affected component subtrees. Versioned bridge commits validate operations and acknowledge revisions; events and controlled text inputs carry identities that prevent stale updates.
- **Native lists and navigation:** UIKit collection views and Android recycler views recycle cells for fixed or variable row sizes, grids, sections, and horizontal lists. Native navigation containers present logical screen roots while providers and component state remain in the shared Python tree.
- **Animation and gestures:** Serialized animation graphs support timing, springs, decay, arithmetic, interpolation, and native scroll and gesture bindings. Swift and Kotlin recognize mobile gestures and update supported animation bindings without Python work on every frame.
- **Device APIs:** Python facades expose camera, location, notifications, storage, permissions, and other native services. Test permissions and platform behavior on your deployment targets.
- **Native extension SDK:** Python dataclasses and protocols define contracts; `pn codegen` generates props and module adapters for Swift and Kotlin. Plugins package native sources and resources, and builds verify matching contracts at startup.
- **Development tools:** `pn start` serves the browser preview and connected mobile dev clients. Fast Refresh preserves compatible component state, while diagnostics report errors and invalid hook usage. Changes to native inputs trigger a rebuild.
- **Browser preview:** `pn preview` runs your Python application against a browser renderer with DOM widgets, Yoga WebAssembly layout, and JavaScript animation graphs. It supports iteration on application logic and UI; fonts, platform controls, and device APIs require mobile testing.
- **App packaging and dependency locks:** `pn run` and `pn build` stage bundled app templates, native libraries, and Python sources. Target-specific wheel locks record dependency versions and hashes for mobile builds. Binary dependencies need compatible mobile wheels; `pn deps` reports target resolution.

## Quick Start

### Installation

Requires Python 3.13 or newer.

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
            on_press=lambda: set_count(count + 1),
        ),
        style=pn.style(spacing=12, padding=16),
    )
```

### Develop

```bash
pn init my-app && cd my-app
pn preview          # dev server + browser preview with Fast Refresh
pn run ios          # in another terminal: debug build that connects to the same server
pn run android
pn build ios        # standalone release artifacts
```

## Documentation

Visit [pythonnative.com](https://pythonnative.com/) for the full documentation, including getting started guides, platform-specific instructions for Android and iOS, API reference, and working examples.

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding standards, and guidelines for submitting pull requests.

## License

[MIT](LICENSE)
