from __future__ import annotations

import os
from pathlib import Path

from pythonnative.project.fingerprint import hash_tree


def _write_tree(root: Path, files: dict[str, bytes]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_identical_trees_under_different_roots_hash_equal(tmp_path: Path) -> None:
    files = {
        "src/app.py": b"print('hello')
",
        "readme.txt": b"notes
",
    }
    a = tmp_path / "a"
    b = tmp_path / "b"
    _write_tree(a, files)
    # Different creation order under a different root.
    _write_tree(b, dict(reversed(list(files.items()))))

    assert hash_tree(a) == hash_tree(b)


def test_changing_bytes_or_renaming_changes_hash(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _write_tree(root, {"src/app.py": b"one
", "src/util.py": b"two
"})
    original = hash_tree(root)

    (root / "src" / "app.py").write_bytes(b"changed
")
    assert hash_tree(root) != original

    (root / "src" / "app.py").write_bytes(b"one
")
    assert hash_tree(root) == original

    (root / "src" / "app.py").rename(root / "src" / "main.py")
    assert hash_tree(root) != original


def test_mtime_change_does_not_change_hash(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    target = root / "src" / "app.py"
    _write_tree(root, {"src/app.py": b"stable
"})
    original = hash_tree(root)

    os.utime(target, (1_700_000_000, 1_700_000_000))
    assert hash_tree(root) == original


def test_ignored_paths_do_not_change_hash(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _write_tree(root, {"src/app.py": b"code
"})
    original = hash_tree(root)

    _write_tree(
        root,
        {
            "build/out.bin": b"artifact
",
            "__pycache__/app.cpython-313.pyc": b"bytecode
",
            ".git/HEAD": b"ref: refs/heads/main
",
            "src/app.pyc": b"bytecode-file
",
            "src/.DS_Store": b"finder
",
        },
    )
    assert hash_tree(root) == original

    (root / "src" / "extra.py").write_bytes(b"new
")
    assert hash_tree(root) != original


def test_missing_root_and_empty_directory_share_empty_digest(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    empty = tmp_path / "empty"
    empty.mkdir()

    assert hash_tree(missing) == hash_tree(empty)


def test_hashing_a_single_file(tmp_path: Path) -> None:
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "other" / "a.txt"
    file_a.write_bytes(b"same-bytes
")
    file_b.parent.mkdir()
    file_b.write_bytes(b"same-bytes
")

    assert hash_tree(file_a) == hash_tree(file_b)

    file_b.write_bytes(b"different
")
    assert hash_tree(file_a) != hash_tree(file_b)
