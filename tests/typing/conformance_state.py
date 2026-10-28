"""Typing conformance: stores and persisted state (checked by mypy, never executed)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pythonnative as pn


@dataclass(frozen=True)
class Session:
    user: str | None = None
    count: int = 0


session = pn.Store(Session(), name="session")


def sign_in(user: str) -> None:
    session.update(lambda state: replace(state, user=user))
    session.set(Session(user=user))
    session.set(1)  # type: ignore[arg-type]
    with session.batch():
        session.update(lambda state: replace(state, count=state.count + 1))


@pn.component
def Badge() -> pn.Node:
    whole: Session = pn.use_store(session)
    count: int = pn.use_store(session, lambda state: state.count)
    wrong: str = pn.use_store(session, lambda state: state.count)  # type: ignore[assignment]
    pn.use_store(session, lambda state: state.missing)  # type: ignore[attr-defined]
    theme, set_theme = pn.use_persisted_state("settings.theme", "light")
    set_theme("dark")
    set_theme(lambda current: current.upper())
    set_theme(3)  # type: ignore[arg-type]
    unsubscribe = session.subscribe(lambda: None)
    unsubscribe()
    return pn.Text(f"{whole.user} {count} {wrong} {theme}")
