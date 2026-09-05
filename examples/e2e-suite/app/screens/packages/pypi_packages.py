"""Demo screen for third-party PyPI packages running on the device.

The suite's ``pythonnative.toml`` declares ``[requirements].packages =
["httpx", "numpy"]``: one pure-Python package and one with compiled
extension modules. This screen imports both at render time and prints
what it finds, so the flow proves the whole pipeline end to end:

- ``pn`` resolved the requirements for the device platform (``pn deps``
  logic in ``pythonnative.project.deps``),
- the wheels were staged into the app bundle (``app_packages`` on iOS,
  Chaquopy's pip step on Android),
- and the embedded interpreter can import them, including loading a
  compiled extension module (numpy's ``_multiarray_umath``), which on
  iOS means the ``.so`` -> framework conversion plus the ``.fwork``
  import hook worked.

The two platforms resolve different numpy release lines (BeeWare
publishes 2.x for iOS, Chaquopy ships 1.26 for Android), so the probe
accepts either package layout: ``numpy._core`` (2.x) or ``numpy.core``
(1.x).

Imports are deferred into the component (not module level) so a broken
package surfaces as a readable ``Error:`` line on this one screen
instead of taking down the whole app at startup.
"""

from __future__ import annotations

import importlib
import sys
from typing import Tuple

import pythonnative as pn
from app.screens.scaffold import demo_screen, hint, result_text, section


def _import_version(module_name: str) -> Tuple[str, str]:
    """Import ``module_name`` and return ``(version, error)``; one of them is empty."""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - the demo reports every failure mode
        return "", f"{type(exc).__name__}: {exc}"
    return str(getattr(module, "__version__", "unknown")), ""


# numpy 2.x moved the C core from ``numpy.core`` to ``numpy._core``.
_NUMPY_CORE_MODULES = ("numpy._core._multiarray_umath", "numpy.core._multiarray_umath")


def _numpy_probe() -> Tuple[str, str]:
    """Run a small computation through numpy's C core; return ``(result, error)``."""
    try:
        import numpy as np

        total = float(np.arange(4, dtype=np.float64).sum())
        loaded = any(name in sys.modules for name in _NUMPY_CORE_MODULES)
        binary = "yes" if loaded else "no"
        return f"{total:g} (binary module loaded: {binary})", ""
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"


@pn.component
def PyPIPackagesDemo() -> pn.Element:
    """Import the suite's declared PyPI packages and show their versions."""
    httpx_version, httpx_error = _import_version("httpx")
    numpy_version, numpy_error = _import_version("numpy")
    numpy_sum, numpy_sum_error = _numpy_probe()

    return demo_screen(
        "PyPI packages",
        "[requirements].packages resolved for this device and imported on it.",
        section(
            "Pure Python (httpx)",
            result_text("httpx", httpx_version or "missing"),
            *([result_text("Error", httpx_error)] if httpx_error else []),
            hint("A py3-none-any wheel; the same file ships to every platform."),
        ),
        section(
            "Binary wheel (numpy)",
            result_text("numpy", numpy_version or "missing"),
            *([result_text("Error", numpy_error)] if numpy_error else []),
            result_text("numpy sum", numpy_sum or "failed"),
            *([result_text("Error", numpy_sum_error)] if numpy_sum_error else []),
            hint("A platform-specific wheel with compiled extension modules loaded by the embedded CPython."),
        ),
        section(
            "Interpreter",
            result_text("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            result_text("sys.platform", sys.platform),
            hint("Maestro asserts both version lines and that the numpy sum is 6."),
        ),
    )
