"""The one equality rule the framework applies to application values.

Hook dependencies, state setters, ``memo`` props, native prop diffing, and
context values all decide "did this change?" with
[`equal`][pythonnative.equality.equal]:

1. The same object is equal to itself.
2. Callables (handlers, closures, components) are equal only by identity;
   a fresh closure always counts as a change, which is why
   [`use_callback`][pythonnative.use_callback] exists.
3. Everything else compares with ``==``, and only a plain ``bool``
   result counts. Objects whose comparison returns something else (NumPy
   arrays) or raises are treated as changed, so a new identity is the
   way to signal an update.

Consequences worth knowing: mutating a list, dict, or set in place and
passing the same object back never re-renders (the setter sees the same
identity), and two equal-but-distinct dataclass instances do not.
"""

from typing import Any, Mapping

__all__ = ["equal", "equal_props"]


def equal(left: Any, right: Any) -> bool:
    """Return whether two values are equal under the framework rule (see the module docstring)."""
    if left is right:
        return True
    if callable(left) or callable(right):
        return False
    try:
        result = left == right
    except Exception:
        return False
    return result if isinstance(result, bool) else False


def equal_props(old: Mapping[str, Any], new: Mapping[str, Any]) -> bool:
    """Return whether two prop mappings have the same keys and [`equal`][pythonnative.equality.equal] values.

    This is the default comparator behind [`memo`][pythonnative.memo].
    """
    if old is new:
        return True
    if old.keys() != new.keys():
        return False
    return all(equal(value, new[key]) for key, value in old.items())
