# Networking

`pn.fetch` and `pn.WebSocket` run on standard `asyncio`, in pure Python, so they behave the same on a device, in tests, and in the browser preview. Neither needs a plugin or a
dependency. Use them from an effect or `use_query` so a component's unmounting cancels the work.

## HTTP

```python
import pythonnative as pn


async def load_user(user_id: int) -> dict:
    response = await pn.fetch(f"https://api.example.com/users/{user_id}", params={"expand": "team"})
    response.raise_for_status()
    return response.json()
```

A `dict` body is sent as JSON. Failures to connect raise `OSError` and timeouts raise `TimeoutError`, while an error status is a normal `Response` until you call `raise_for_status`.

### Uploads

`files=` sends `multipart/form-data`. Each value is a `Path`, raw `bytes`, or a `(filename, content, content_type)` tuple, and a mapping `body` supplies the form's other fields. `on_upload_progress`
runs on the application thread, so it can set state directly.

```python
from pathlib import Path


@pn.component
def Uploader(path: str) -> pn.Node:
    percent, set_percent = pn.use_state(0)

    async def upload() -> None:
        response = await pn.fetch(
            "https://api.example.com/photos",
            method="POST",
            body={"caption": "Trailhead"},
            files={"photo": Path(path)},
            on_upload_progress=lambda sent, total: set_percent(sent * 100 // total),
        )
        response.raise_for_status()

    return pn.Button(f"Upload ({percent}%)", on_press=lambda: pn.run_async(upload()))
```

### Downloads

`stream=True` returns when the headers arrive. Read the body as it comes, and it closes when the iteration ends.

```python
async def download(url: str, destination: str) -> None:
    response = await pn.fetch(url, stream=True)
    response.raise_for_status()
    with open(destination, "wb") as out:
        async for chunk in response.chunks():
            out.write(chunk)
```

`await response.read()` collects the rest into `content`, and `await response.close()` abandons it.

## WebSockets

```python
async def follow_feed(on_message) -> None:
    async with pn.WebSocket("wss://example.com/feed", headers={"Authorization": "Bearer ..."}) as socket:
        await socket.send_json({"subscribe": "news"})
        async for message in socket:
            on_message(message)


@pn.component
def Feed() -> pn.Node:
    messages, set_messages = pn.use_state(())
    pn.use_effect(lambda: follow_feed(lambda m: set_messages(lambda old: (*old, m))), [])
    return pn.Column(*(pn.Text(str(message)) for message in messages))
```

Text arrives as `str` and binary as `bytes`. Iteration ends on a normal close. Anything else raises `WebSocketClosed`, whose `code` and `reason` say why; a dropped connection is 1006. A
ping goes out every 30 seconds by default (`heartbeat=`), which also detects a dead connection. Reconnecting is your app's policy: wrap the block in a loop with whatever backoff suits it.

## TLS

Both use the platform's certificates by default. Tested on the iOS simulator and an Android emulator; test your own server on a real device, too. ``set_default_ssl_context``
(from `pythonnative.net`) replaces the context, for example to pin a certificate or trust a development CA.

## What's not here

There's no HTTP/2, connection pooling, or background transfer that outlives the app. `httpx` and `aiohttp` work when you need more, as long as their wheels resolve for your targets, but their requests don't appear in DevTools' Network panel.
