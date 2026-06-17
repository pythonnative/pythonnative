"""Tests for pythonnative._ios_log (iOS stdout/stderr redirection).

These tests exercise the module's behavior directly without requiring
an actual iOS runtime: ``_StderrStream`` writes via ``os.write(2, ...)``,
and ``install()`` is idempotent and swaps the ``sys`` streams in place.
"""

import io
import os
import sys
from typing import Generator, List, Tuple

import pytest

from pythonnative import _ios_log
from pythonnative._ios_log import _StderrStream, install


class TestStderrStream:
    def test_write_sends_utf8_bytes_to_fd_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: List[Tuple[int, bytes]] = []

        def fake_write(fd: int, data: bytes) -> int:
            captured.append((fd, data))
            return len(data)

        monkeypatch.setattr(os, "write", fake_write)

        stream = _StderrStream()
        written = stream.write("hello\n")

        assert captured == [(2, b"hello\n")]
        assert written == len(b"hello\n")

    def test_write_handles_non_ascii(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: List[bytes] = []

        def fake_write(fd: int, data: bytes) -> int:
            captured.append(data)
            return len(data)

        monkeypatch.setattr(os, "write", fake_write)

        _StderrStream().write("héllo ✓\n")

        assert captured == ["héllo ✓\n".encode("utf-8")]

    def test_write_empty_string_is_no_op(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Tuple[int, bytes]] = []

        def fake_write(fd: int, data: bytes) -> int:
            calls.append((fd, data))
            return len(data)

        monkeypatch.setattr(os, "write", fake_write)

        assert _StderrStream().write("") == 0
        assert calls == []

    def test_write_swallows_oserror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(fd: int, data: bytes) -> int:
            raise OSError("nope")

        monkeypatch.setattr(os, "write", boom)

        assert _StderrStream().write("x") == 0

    def test_writelines_iterates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: List[bytes] = []

        def fake_write(fd: int, data: bytes) -> int:
            captured.append(data)
            return len(data)

        monkeypatch.setattr(os, "write", fake_write)

        _StderrStream().writelines(["a\n", "b\n", "c\n"])

        assert captured == [b"a\n", b"b\n", b"c\n"]

    def test_stream_metadata(self) -> None:
        stream = _StderrStream()
        assert stream.encoding == "utf-8"
        assert stream.errors == "replace"
        assert stream.fileno() == 2
        assert stream.closed is False
        # flush() and close() are deliberate no-ops; just exercise them.
        stream.flush()
        stream.close()

    def test_isatty_reflects_fd_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(os, "isatty", lambda fd: fd == 2)
        assert _StderrStream().isatty() is True

        def raiser(fd: int) -> bool:
            raise OSError("bad fd")

        monkeypatch.setattr(os, "isatty", raiser)
        assert _StderrStream().isatty() is False


class TestInstall:
    @pytest.fixture(autouse=True)
    def _reset_install_flag(self) -> Generator[None, None, None]:
        """Ensure each test starts with a fresh, un-installed state."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        original_installed = _ios_log._installed
        _ios_log._installed = False
        try:
            yield
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            _ios_log._installed = original_installed

    def test_install_replaces_streams(self) -> None:
        assert not isinstance(sys.stdout, _StderrStream)
        assert not isinstance(sys.stderr, _StderrStream)

        install()

        assert isinstance(sys.stdout, _StderrStream)
        assert isinstance(sys.stderr, _StderrStream)

    def test_install_is_idempotent(self) -> None:
        install()
        first_stdout = sys.stdout
        first_stderr = sys.stderr

        install()
        install()

        # Second+ install() calls must be no-ops; the same objects remain.
        assert sys.stdout is first_stdout
        assert sys.stderr is first_stderr

    def test_install_does_not_raise_when_streams_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Replace stdout/stderr with something odd before install to confirm
        # install() doesn't care about the prior stream.
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", io.StringIO())

        install()

        assert isinstance(sys.stdout, _StderrStream)
        assert isinstance(sys.stderr, _StderrStream)
