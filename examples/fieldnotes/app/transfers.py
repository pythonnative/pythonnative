"""Moves attachment files to and from the sync server over HTTP.

Sync messages only carry an attachment's metadata. A file goes up with a multipart
``pn.fetch`` that reports its progress, and comes down with a streamed one. Files
come down rather than being shown from the server's URL because a device in the
field is usually offline, and because Python's sockets aren't subject to the
cleartext rules that would block a native image view from a development server.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pythonnative as pn

from .journal import Journal, data_directory, extension_for
from .models import Attachment
from .protocol import http_base

_TRANSFER_ERRORS = (OSError, TimeoutError, pn.HTTPError)


class TransferQueue:
    """Runs one pass of uploads and downloads at a time.

    Args:
        journal: The journal whose attachments to move.
    """

    def __init__(self, journal: Journal) -> None:
        self.journal = journal
        self._running: Optional["asyncio.Task[int]"] = None

    async def run(self, url: str) -> int:
        """Upload and download everything outstanding.

        A pass that's already running is joined rather than doubled, because the
        sync client asks for one each time it hears about a change.

        Args:
            url: The server's WebSocket URL, from which the HTTP origin follows.

        Returns:
            How many files moved.
        """
        if self._running is None or self._running.done():
            self._running = asyncio.ensure_future(self._pass(url))
        return await asyncio.shield(self._running)

    async def _pass(self, url: str) -> int:
        base = http_base(url)
        uploads, downloads = await self.journal.repository.transfers_pending()
        moved = 0
        self.journal.publish(transfer_error="")
        for attachment in uploads:
            moved += await self._attempt(attachment, self.upload, base)
        for attachment in downloads:
            moved += await self._attempt(attachment, self.download, base)
        if moved:
            await self.journal.refresh()
            # Other devices need to hear where the new files are.
            self.journal.announce_change()
        return moved

    async def _attempt(
        self, attachment: Attachment, transfer: Callable[[str, Attachment], Awaitable[None]], base: str
    ) -> int:
        self.journal.set_transfer(attachment.id, 0.0)
        try:
            await transfer(base, attachment)
        except _TRANSFER_ERRORS as error:
            self.journal.publish(transfer_error=f"{attachment.name} didn't transfer: {error}")
            return 0
        finally:
            self.journal.set_transfer(attachment.id, None)
        return 1

    async def upload(self, base: str, attachment: Attachment) -> None:
        """Send one attachment's file to the server, and record where it landed.

        Args:
            base: The server's HTTP origin.
            attachment: What to send.

        Raises:
            OSError: If the connection fails or the file is gone.
            pythonnative.HTTPError: If the server refuses it.
        """
        path = Path(self.journal.file_path(attachment))

        def progress(sent: int, total: int) -> None:
            self.journal.set_transfer(attachment.id, sent / total if total else 1.0)

        response = await pn.fetch(
            f"{base}/attachments",
            method="POST",
            body={"id": attachment.id, "entry_id": attachment.entry_id, "kind": attachment.kind},
            files={"file": (attachment.name, path, attachment.mime_type)},
            on_upload_progress=progress,
            timeout=120.0,
        )
        response.raise_for_status()
        await self.journal.repository.mark_uploaded(attachment.id, str(response.json()["path"]))

    async def download(self, base: str, attachment: Attachment) -> None:
        """Fetch another device's attachment, writing to a temporary name until it's whole.

        Args:
            base: The server's HTTP origin.
            attachment: What to fetch.

        Raises:
            OSError: If the connection or the disk fails.
            pythonnative.HTTPError: If the server doesn't have it.
        """
        response = await pn.fetch(f"{base}{attachment.remote_path}", stream=True, timeout=120.0)
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or attachment.size or 0)
        extension = extension_for(attachment.mime_type, attachment.name)
        relative = f"attachments/{attachment.entry_id}/{attachment.id}{extension}"
        target = data_directory() / relative
        partial = target.with_name(f"{target.name}.{uuid.uuid4().hex}.part")
        target.parent.mkdir(parents=True, exist_ok=True)
        received = 0
        try:
            with partial.open("wb") as file:
                async for chunk in response.chunks():
                    await asyncio.to_thread(file.write, chunk)
                    received += len(chunk)
                    if total:
                        self.journal.set_transfer(attachment.id, min(1.0, received / total))
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        await self.journal.repository.mark_downloaded(attachment.id, relative, received)
