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

from pythonnative import runtime
from pythonnative.events import get_event_registry


@pytest.fixture(autouse=True)
def _fresh_framework_loop() -> Iterator[None]:
    yield
    runtime._shutdown_for_tests()
    get_event_registry().reset()
