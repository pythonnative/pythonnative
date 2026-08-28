"""Present the system share sheet.

[`Share.share`][pythonnative.Share] is a coroutine that opens
``UIActivityViewController`` (iOS) or an ``ACTION_SEND`` chooser
(Android) and resolves to ``True`` once the user completes a share or
``False`` if they dismiss it.

Example:
    ```python
    import pythonnative as pn

    async def share_link():
        await pn.Share.share(
            message="Check out PythonNative!",
            url="https://example.com",
        )
    ```
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

from .. import diagnostics
from ..runtime import resolve_future
from ..utils import IS_ANDROID, IS_IOS

# Retain pool so iOS completion handlers aren't collected early.
_pending: Dict[int, Any] = {}


class Share:
    """System share-sheet interface."""

    @staticmethod
    async def share(
        *,
        message: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Open the share sheet with ``message`` / ``url``.

        Args:
            message: Text body to share.
            url: A URL to share (combined with ``message`` on Android).
            title: Chooser title (Android) / subject (iOS mail).

        Returns:
            ``True`` if the user completed a share, ``False`` if they
            cancelled or no share UI is available.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()

        def _done(ok: bool) -> None:
            resolve_future(future, ok)

        if IS_IOS:
            _ios_share(_done, message=message, url=url, title=title)
        elif IS_ANDROID:
            _android_share(_done, message=message, url=url, title=title)
        else:
            _done(False)

        return await future


# ======================================================================
# iOS: UIActivityViewController
# ======================================================================


def _ios_share(
    on_done: Callable[[bool], None],
    message: Optional[str],
    url: Optional[str],
    title: Optional[str],
) -> None:
    del title
    try:
        from rubicon.objc import Block, ObjCClass

        items = ObjCClass("NSMutableArray").alloc().init()
        if message:
            items.addObject_(message)
        if url:
            nsurl = ObjCClass("NSURL").URLWithString_(url)
            if nsurl is not None:
                items.addObject_(nsurl)

        controller = (
            ObjCClass("UIActivityViewController").alloc().initWithActivityItems_applicationActivities_(items, None)
        )

        token = id(controller)
        _pending[token] = controller

        def _completion(activity: Any, completed: bool, items_: Any, error: Any) -> None:
            del activity, items_, error
            _pending.pop(token, None)
            try:
                on_done(bool(completed))
            except Exception:
                diagnostics.swallowed("share._ios_share._completion")

        controller.setCompletionWithItemsHandler_(
            Block(_completion, None, ObjCClass("NSString"), Block, ObjCClass("NSArray"), ObjCClass("NSError"))
        )

        app = ObjCClass("UIApplication").sharedApplication
        top = app.keyWindow.rootViewController
        while top is not None and top.presentedViewController is not None:
            top = top.presentedViewController
        if top is not None:
            top.presentViewController_animated_completion_(controller, True, None)
        else:
            _pending.pop(token, None)
            on_done(False)
    except Exception:
        on_done(False)


# ======================================================================
# Android: ACTION_SEND chooser
# ======================================================================


def _android_share(
    on_done: Callable[[bool], None],
    message: Optional[str],
    url: Optional[str],
    title: Optional[str],
) -> None:
    try:
        from java import jclass

        from ..utils import get_android_context

        Intent = jclass("android.content.Intent")
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("text/plain")
        body = "\n".join(part for part in (message, url) if part)
        intent.putExtra(Intent.EXTRA_TEXT, body)
        if title:
            intent.putExtra(Intent.EXTRA_SUBJECT, title)

        chooser = Intent.createChooser(intent, title or "Share")
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        get_android_context().startActivity(chooser)
        # ACTION_SEND chooser gives no completion callback; report
        # success once the chooser has been launched.
        on_done(True)
    except Exception:
        on_done(False)
