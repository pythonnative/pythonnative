"""Persistent offline data and an incremental keyed collection."""

import asyncio
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable

import pythonnative as pn


@dataclass(frozen=True)
class Issue:
    id: str
    title: str
    body: str
    closed: bool = False


@dataclass(frozen=True)
class Snapshot:
    issues: tuple[Issue, ...] = ()
    loading: bool = True
    error: str = ""
    revision: int = 0


class Repository:
    """One shared repository survives screen pushes and recycled rows."""

    def __init__(self) -> None:
        self.snapshot = Snapshot()
        self.issues: pn.ListData[Issue] = pn.ListData(key=lambda issue: issue.id)
        self.listeners: set[Callable[[], None]] = set()
        self._write_lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self.listeners.add(callback)
        return lambda: self.listeners.discard(callback)

    def publish(self, **changes: Any) -> None:
        self.snapshot = replace(self.snapshot, revision=self.snapshot.revision + 1, **changes)
        for callback in tuple(self.listeners):
            callback()

    async def load(self) -> None:
        self.publish(loading=True, error="")
        try:
            async with asyncio.timeout(10):
                async with asyncio.TaskGroup() as group:
                    data = group.create_task(pn.AsyncStorage.get("inbox.issues"))
                    group.create_task(pn.AsyncStorage.get("inbox.last_opened"))
                if data.result():
                    issues = tuple(Issue(**item) for item in json.loads(data.result()))
                else:
                    issues = tuple(
                        Issue(
                            str(i),
                            f"Issue {i}: {('Review the interface', 'Improve search', 'Check accessibility')[i % 3]}",
                            "A variable-height issue description. " * (1 + i % 5),
                        )
                        for i in range(1, 2001)
                    )
                self.issues = pn.ListData(issues, key=lambda issue: issue.id)
                self.publish(issues=issues, loading=False)
        except Exception as error:
            import traceback

            traceback.print_exc()
            self.publish(loading=False, error=str(error))

    async def update(self, issue: Issue) -> None:
        # Serialize persistence so older writes can't overwrite newer changes.
        async with self._write_lock:
            previous = self.issues.get(issue.id)
            self.issues.update(issue.id, issue)
            self.publish(issues=tuple(self.issues), error="")
            try:
                await pn.AsyncStorage.set("inbox.issues", json.dumps([asdict(row) for row in self.issues]))
            except Exception as error:
                self.issues.update(issue.id, previous)
                self.publish(issues=tuple(self.issues), error=f"Save failed: {error}")
                raise
