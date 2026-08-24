"""Shared test fixtures: framework-loop isolation between tests.

The framework runs one asyncio loop for the whole process. Tests
create tasks, resources, and timers on it; without cleanup those leak
into the next test. This autouse fixture closes the guest loop after
every test (cancelling pending work) so each test starts with a fresh
loop.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from pythonnative import hooks, runtime


@pytest.fixture(autouse=True)
def _fresh_framework_loop() -> Iterator[None]:
    yield
    runtime._shutdown_for_tests()
    # Transition flushes scheduled on the closed loop never ran; drop
    # them so they can't leak into the next test.
    hooks._deferred_triggers.clear()
    hooks._post_transition_callbacks.clear()
    hooks._transition_flush_scheduled = False
