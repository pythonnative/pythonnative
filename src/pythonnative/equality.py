"""Equality rules for immutable application snapshots.

Identity is equal. Scalar boolean equality is respected. Objects whose
comparison returns a nonboolean result (such as arrays) require a new
identity to signal a change. In-place mutations don't signal updates.
"""

from typing import Any


def equal(left: Any, right: Any) -> bool:
    """Compare values without coercing array expressions to booleans."""
    if left is right:
        return True
    try:
        result = left == right
        return result if isinstance(result, bool) else False
    except Exception:
        return False
