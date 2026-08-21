#!/usr/bin/env python3
"""Build a colocated-download SHA-256 asset for a release archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_checksum(archive_path: Path, checksum_path: Path) -> str:
    """Write a checksum asset that refers to the archive by basename."""

    archive_path = archive_path.resolve()
    checksum_path = checksum_path.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Release archive does not exist: {archive_path}")
    if archive_path == checksum_path:
        raise ValueError("Checksum output must not overwrite the release archive")

    digest = _sha256_file(archive_path)
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{checksum_path.name}.", suffix=".tmp", dir=checksum_path.parent
    )
    os.close(temporary_fd)
    temporary_path = Path(temporary_name)
    try:
        temporary_path.write_text(
            f"{digest}  {archive_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        os.replace(temporary_path, checksum_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Release archive to hash")
    parser.add_argument("output", type=Path, help="Checksum asset to write")
    args = parser.parse_args(argv)

    digest = build_release_checksum(args.archive, args.output)
    print(f"PASS: wrote {args.output} ({digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
