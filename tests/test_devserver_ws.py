"""RFC 6455 framing and handshake helpers in ``pythonnative.devserver.ws``."""

from __future__ import annotations

from typing import List, Tuple

import pytest

from pythonnative.devserver import ws


def _decode_all(data: bytes) -> list:
    decoder = ws.FrameDecoder()
    return list(decoder.feed(data))


def test_accept_key_matches_rfc_example() -> None:
    # The worked example from RFC 6455 section 1.3.
    assert ws.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_server_handshake_echoes_accept_header() -> None:
    response = ws.server_handshake(
        {"upgrade": "websocket", "connection": "Upgrade", "sec-websocket-key": "dGhlIHNhbXBsZSBub25jZQ=="}
    )
    text = response.decode("ascii")
    assert text.startswith("HTTP/1.1 101")
    assert "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in text
    assert text.endswith("\r\n\r\n")


def test_server_handshake_rejects_missing_key() -> None:
    with pytest.raises(ws.HandshakeError):
        ws.server_handshake({"upgrade": "websocket"})


def test_parse_http_headers_lowercases_names() -> None:
    raw = b"GET /ws?role=client HTTP/1.1\r\nHost: x\r\nSec-WebSocket-Key: abc\r\n\r\n"
    request_line, headers = ws.parse_http_headers(raw)
    assert request_line.startswith("GET /ws?role=client")
    assert headers["sec-websocket-key"] == "abc"
    assert headers["host"] == "x"


def test_client_handshake_request_carries_key_and_path() -> None:
    request, key = ws.client_handshake_request("localhost:8765", "/ws?role=client", key="dGhlIHNhbXBsZSBub25jZQ==")
    text = request.decode("ascii")
    assert key == "dGhlIHNhbXBsZSBub25jZQ=="
    assert text.startswith("GET /ws?role=client HTTP/1.1\r\n")
    assert "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" in text
    assert "Sec-WebSocket-Version: 13" in text


@pytest.mark.parametrize("size", [0, 1, 125, 126, 127, 65535, 65536, 70000])
def test_frame_round_trip_across_length_encodings(size: int) -> None:
    payload = bytes(i % 251 for i in range(size))
    for mask in (False, True):
        frame = ws.encode_frame(ws.BINARY, payload, mask=mask)
        messages = _decode_all(frame)
        assert messages == [(ws.BINARY, payload)]


def test_masked_frames_are_unreadable_on_the_wire() -> None:
    payload = b"hello hello hello"
    frame = ws.encode_frame(ws.TEXT, payload, mask=True)
    assert payload not in frame
    assert frame[1] & 0x80  # mask bit set
    assert _decode_all(frame) == [(ws.TEXT, payload)]


def test_decoder_reassembles_fragmented_messages_and_interleaved_control_frames() -> None:
    first = ws.encode_frame(ws.TEXT, b"hel", fin=False)
    ping = ws.encode_frame(ws.PING, b"p")
    middle = ws.encode_frame(ws.CONTINUATION, b"lo ", fin=False)
    last = ws.encode_frame(ws.CONTINUATION, b"world", fin=True)
    decoder = ws.FrameDecoder()
    out: List[Tuple[int, bytes]] = []
    # Deliver byte by byte to exercise partial buffering.
    for byte in first + ping + middle + last:
        out.extend(decoder.feed(bytes([byte])))
    assert out == [(ws.PING, b"p"), (ws.TEXT, b"hello world")]


def test_decoder_rejects_fragmented_control_frame() -> None:
    frame = ws.encode_frame(ws.PING, b"x", fin=False)
    with pytest.raises(ws.WebSocketError):
        _decode_all(frame)


def test_encode_close_carries_status_code_and_reason() -> None:
    frame = ws.encode_close(1001, "going away")
    [(opcode, payload)] = _decode_all(frame)
    assert opcode == ws.CLOSE
    assert payload[:2] == (1001).to_bytes(2, "big")
    assert payload[2:] == b"going away"


def test_websocket_client_rejects_non_ws_schemes() -> None:
    with pytest.raises(ValueError):
        ws.WebSocketClient("wss://example.com/ws")
    with pytest.raises(ValueError):
        ws.WebSocketClient("ws:///nohost")
    client = ws.WebSocketClient("ws://localhost:1234/ws?role=client")
    assert (client.host, client.port, client.path) == ("localhost", 1234, "/ws?role=client")
