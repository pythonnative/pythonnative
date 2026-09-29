"""pytest plugin shipped with PythonNative (registered under the ``pytest11`` entry point).

Installing ``pythonnative`` activates it in every pytest session. It
provides:

- an autouse fixture that resets the framework between tests: the
  headless asyncio loop is shut down (cancelling leaked tasks), and the
  event registry, default query client, and recorded diagnostics
  warnings are cleared, so one test's leftovers never reach the next;
- ``pn_clock``, a [`FakeClock`][pythonnative.testing.FakeClock] installed
  on the framework loop for the test (see
  [`fake_clock`][pythonnative.testing.fake_clock]).

Nothing here needs to be imported by a ``conftest.py``; pytest loads the
plugin from the package metadata. Disable it with ``-p no:pythonnative``.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from .clock import FakeClock, fake_clock

__all__ = ["pn_clock"]


@pytest.fixture(autouse=True)
def _pn_fresh_runtime() -> Iterator[None]:
    """Reset the framework after every test so loops, listeners, caches, and warnings never leak."""
    yield
    from .. import diagnostics, query, runtime
    from ..events import get_event_registry

    runtime._shutdown_for_tests()
    get_event_registry().reset()
    query._reset_for_tests()
    diagnostics.clear_warnings()


@pytest.fixture
def pn_clock() -> Iterator[FakeClock]:
    """A [`FakeClock`][pythonnative.testing.FakeClock] driving the framework loop's timers for this test."""
    with fake_clock() as clock:
        yield clock
