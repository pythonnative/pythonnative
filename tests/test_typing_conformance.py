"""Typing conformance: the public API accepts correct code and rejects common mistakes.

The files in ``tests/typing/`` are type-checked, never executed. Lines
that must be rejected carry ``# type: ignore[code]``; with
``--warn-unused-ignores`` an API that stops rejecting a mistake fails
here as surely as one that starts rejecting correct code.

This runs mypy in strict mode with no configuration file, as an
application with its own settings would, independently of the
repository's ``mypy.ini`` (which also checks these files).
"""

from __future__ import annotations

from pathlib import Path

from mypy import api

TYPING_DIR = Path(__file__).parent / "typing"
REPO_ROOT = Path(__file__).parent.parent


def test_conformance_files_exist() -> None:
    files = sorted(path.name for path in TYPING_DIR.glob("conformance_*.py"))
    assert files == [
        "conformance_components.py",
        "conformance_navigation.py",
        "conformance_state.py",
        "conformance_styles.py",
    ]


def test_public_api_type_checks_under_strict_mypy() -> None:
    stdout, stderr, status = api.run(
        [
            "--config-file=",
            "--strict",
            "--warn-unused-ignores",
            "--show-error-codes",
            "--no-pretty",
            "--follow-imports=silent",
            "--cache-dir",
            str(REPO_ROOT / ".mypy_cache" / "typing-conformance"),
            str(TYPING_DIR),
        ]
    )
    assert status == 0, f"mypy reported problems in tests/typing:\n{stdout}{stderr}"
