"""Offline issue data: a store for the screens and a keyed list for the inbox."""

import asyncio
import json
import traceback
from dataclasses import asdict, dataclass, replace

import pythonnative as pn

STORAGE_KEY = "inbox.issues"
_TOPICS = ("Review the interface", "Improve search", "Check accessibility")


@dataclass(frozen=True)
class Issue:
    id: str
    title: str
    body: str
    closed: bool = False

    def matches(self, text: str, *, only_open: bool) -> bool:
        """Return whether a search for ``text`` (already case-folded) should show this issue."""
        return (not only_open or not self.closed) and text in (self.title + self.body).casefold()


@dataclass(frozen=True)
class Snapshot:
    """Everything the screens read. The store replaces it whole on every change."""

    issues: tuple[Issue, ...] = ()
    loading: bool = True
    error: str = ""

    def find(self, issue_id: str) -> Issue | None:
        return next((issue for issue in self.issues if issue.id == issue_id), None)


def _key(issue: Issue) -> str:
    return issue.id


def sample_issues() -> tuple[Issue, ...]:
    """The 2,000 issues a fresh install starts with."""
    return tuple(
        Issue(str(i), f"Issue {i}: {_TOPICS[i % 3]}", "A variable-height issue description. " * (1 + i % 5))
        for i in range(1, 2001)
    )


class Repository:
    """Loads, edits, and persists the issues.

    Screens read ``store`` through ``pn.use_store``. ``issues`` mirrors the
    same rows as a ``pn.ListData``, which tells the unfiltered list exactly
    which row changed instead of making it diff 2,000 items.
    """

    def __init__(self) -> None:
        self.store = pn.Store(Snapshot(), name="inbox")
        self.issues = pn.ListData[Issue](key=_key)
        self._write_lock = asyncio.Lock()

    async def load(self) -> None:
        """Read the saved issues, or start from the sample set."""
        self.store.update(lambda state: replace(state, loading=True, error=""))
        try:
            async with asyncio.timeout(10):
                saved = await pn.AsyncStorage.get(STORAGE_KEY)
            issues = tuple(Issue(**row) for row in json.loads(saved)) if saved else sample_issues()
        except Exception as error:
            traceback.print_exc()
            message = str(error)
            self.store.update(lambda state: replace(state, loading=False, error=message))
            return
        self.issues = pn.ListData(issues, key=_key)
        self.store.update(lambda state: replace(state, issues=issues, loading=False))

    async def save(self, issue: Issue) -> None:
        """Show ``issue`` right away, persist it, and roll back if the write fails.

        Raises:
            Exception: Whatever the storage write raised, after the rollback.
        """
        # Serialize writes so an older save can't overwrite a newer one.
        async with self._write_lock:
            previous = self.issues.get(issue.id)
            self._put(issue, error="")
            try:
                await pn.AsyncStorage.set(STORAGE_KEY, json.dumps([asdict(row) for row in self.issues]))
            except Exception as error:
                self._put(previous, error=f"Save failed: {error}")
                raise

    def _put(self, issue: Issue, *, error: str) -> None:
        self.issues.update(issue.id, issue)
        issues = tuple(self.issues)
        self.store.update(lambda state: replace(state, issues=issues, error=error))
