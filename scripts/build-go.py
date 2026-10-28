#!/usr/bin/env python3
"""Build PythonNative Go and package it as release assets.

The release workflow runs this once per platform on a runner with the
platform's toolchain, then once more with ``--checksums`` over the
downloaded assets:

    python scripts/build-go.py --platform ios --out go-dist
    python scripts/build-go.py --platform android --out go-dist
    python scripts/build-go.py --checksums go-dist

``pn go`` downloads these assets from the GitHub release whose tag
matches the installed ``pythonnative`` version; see
``pythonnative.project.go``.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from pythonnative.project import go


def main() -> int:
    """Build one platform's asset, or write the checksum file for a directory of assets."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--platform", choices=["ios", "android"], help="Build and package Go for this platform")
    parser.add_argument("--out", type=Path, default=Path("go-dist"), help="Where release assets are written")
    parser.add_argument("--checksums", type=Path, help="Write the .sha256 file for the assets in this directory")
    args = parser.parse_args()

    if args.checksums is not None:
        assets = sorted(path for path in args.checksums.iterdir() if path.name.startswith("pythonnative-go-"))
        assets = [path for path in assets if not path.name.endswith(".sha256")]
        if not assets:
            print(f"No Go assets in {args.checksums}", file=sys.stderr)
            return 1
        print(go.write_checksums(assets, args.checksums))
        return 0
    if args.platform is None:
        parser.error("pass --platform or --checksums")
    with tempfile.TemporaryDirectory() as scratch:
        try:
            artifact = go.build(args.platform, out_dir=Path(scratch), log=print)
        except go.GoError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(go.package(args.platform, artifact, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
