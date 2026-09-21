"""User locales, layout direction, and time zone.

[`Localization`][pythonnative.Localization] reads the user's preferred
languages and time zone from the native ``Localization`` module
(``Locale.preferredLanguages`` and ``TimeZone.current`` on iOS,
``LocaleList.getDefault()`` and ``TimeZone.getDefault()`` on Android,
``navigator.languages`` in the browser preview). Both readers answer
from state the OS already holds, so they are synchronous. Native pushes
a ``change`` event with ``{"locales": [...], "timezone": str}`` when the
user changes either setting; off device, tests drive the same path
through
[`dispatch_localization`][pythonnative.native_modules.localization.dispatch_localization].

Prefer the [`use_locales`][pythonnative.use_locales] hook inside
components; use the imperative API for non-UI code.

Example:
    ```python
    import pythonnative as pn

    @pn.component
    def Greeting():
        locale = pn.use_locales()[0]
        text = "Hola" if locale.language_code == "es" else "Hello"
        return pn.Text(text, style=pn.style(text_align="right" if locale.is_rtl else "left"))
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from .. import diagnostics
from ..hooks import use_subscription
from .registry import native_module, on_event


@dataclass(frozen=True)
class Locale:
    """One entry of the user's preferred-language list.

    Attributes:
        language_tag: BCP 47 tag (``"en-US"``, ``"ar-EG"``).
        language_code: ISO 639 language (``"en"``, ``"ar"``).
        region_code: ISO 3166 region (``"US"``), or ``""`` when the tag
            has none.
        is_rtl: Whether the language is written right to left.
    """

    language_tag: str
    language_code: str
    region_code: str = ""
    is_rtl: bool = False


_locales: Optional[List[Locale]] = None
_timezone: Optional[str] = None
_listeners: List[Callable[[List[Locale]], None]] = []


def _locale(record: Any) -> Optional[Locale]:
    if not isinstance(record, dict):
        return None
    tag = str(record.get("language_tag") or "")
    if not tag:
        return None
    return Locale(
        language_tag=tag,
        language_code=str(record.get("language_code") or tag.split("-")[0]),
        region_code=str(record.get("region_code") or ""),
        is_rtl=bool(record.get("is_rtl", False)),
    )


def _locales_from(records: Any) -> List[Locale]:
    if not isinstance(records, Sequence) or isinstance(records, str):
        return []
    return [locale for locale in (_locale(record) for record in records) if locale is not None]


def _fetch_locales() -> List[Locale]:
    global _locales
    if _locales is None:
        _locales = _locales_from(native_module("Localization").call("get_locales"))
    return list(_locales)


class Localization:
    """Locale and time-zone interface (synchronous).

    Raises:
        NativeModuleError: If the native module fails.
    """

    @staticmethod
    def get_locales() -> List[Locale]:
        """Return the user's preferred locales, most preferred first.

        The list is empty only when the platform reports no locale at all.
        """
        return _fetch_locales()

    @staticmethod
    def get_timezone() -> str:
        """Return the device time zone as an IANA name (``"America/New_York"``)."""
        global _timezone
        if _timezone is None:
            _timezone = str(native_module("Localization").call("get_timezone") or "UTC")
        return _timezone

    @staticmethod
    def is_rtl() -> bool:
        """Return whether the preferred locale is written right to left."""
        locales = _fetch_locales()
        return bool(locales) and locales[0].is_rtl

    @staticmethod
    def add_listener(callback: Callable[[List[Locale]], None]) -> Callable[[], None]:
        """Subscribe to locale changes; returns an unsubscribe function.

        Each callback receives the new preferred-locale list. Read
        [`get_timezone`][pythonnative.native_modules.localization.Localization.get_timezone]
        inside the callback for the matching time zone.
        """
        _listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                _listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe


def dispatch_localization(locales: Sequence[Locale], timezone: Optional[str] = None) -> None:
    """Record new locales (and optionally a time zone) and notify listeners."""
    global _locales, _timezone
    new_locales = list(locales)
    if timezone is not None:
        _timezone = str(timezone)
    if new_locales == _locales:
        return
    _locales = new_locales
    for listener in list(_listeners):
        try:
            listener(list(new_locales))
        except Exception:
            diagnostics.swallowed("localization.dispatch_localization")


def _on_native_change(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    records: Dict[str, Any] = payload
    timezone = records.get("timezone")
    locales = _locales_from(records.get("locales"))
    if "locales" not in records:
        locales = _locales or []
    dispatch_localization(locales, None if timezone is None else str(timezone))


on_event("Localization", "change", _on_native_change)


def _subscribe(notify: Callable[[], None]) -> Callable[[], None]:
    return Localization.add_listener(lambda _locales: notify())


def use_locales() -> List[Locale]:
    """Return the preferred locales and re-render when the user changes them.

    Raises:
        RuntimeError: If called outside a ``@component`` function.
    """
    return use_subscription(_subscribe, _fetch_locales)
