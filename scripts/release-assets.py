"""Preserve the exact distribution bytes across retries of a PyPI upload."""

import argparse
import json
import subprocess
from pathlib import Path


def sync_assets(tag: str, directory: Path) -> None:
    """Upload new assets and reuse existing ones without overwriting releases.

    Build timestamps can change archive hashes. Store files on the GitHub
    release before publishing to PyPI, then reuse those same bytes on recovery.
    The workflow validates the resulting directory again before publishing.
    """
    result = subprocess.run(
        ["gh", "release", "view", tag, "--json", "assets"],
        check=True,
        capture_output=True,
        text=True,
    )
    existing = {asset["name"] for asset in json.loads(result.stdout)["assets"]}
    for path in sorted(directory.iterdir()):
        if path.name in existing:
            subprocess.run(
                ["gh", "release", "download", tag, "--pattern", path.name, "--dir", str(directory), "--clobber"],
                check=True,
            )
        else:
            subprocess.run(["gh", "release", "upload", tag, str(path)], check=True)


def main() -> None:
    """Synchronize the selected release's distribution assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    sync_assets(args.tag, args.directory)


if __name__ == "__main__":
    main()
