#!/usr/bin/env python3
"""Build the installable Presentation Studio archive reproducibly."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL_ROOT = REPOSITORY_ROOT / "presentation-studio"
DEFAULT_ARCHIVE_PATH = REPOSITORY_ROOT / "dist" / "presentation-studio.zip"
DEFAULT_CHECKSUM_PATH = REPOSITORY_ROOT / "checksums.sha256"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
}
EXCLUDED_NAMES = {".DS_Store", ".env", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".bak", ".log", ".pyc", ".pyo", ".swp", ".tmp"}


def _is_included(path: Path, skill_root: Path) -> bool:
    relative = path.relative_to(skill_root)
    return (
        not any(part in EXCLUDED_DIRECTORIES for part in relative.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
    )


def _skill_files(skill_root: Path) -> list[Path]:
    return sorted(
        (path for path in skill_root.rglob("*") if path.is_file() and _is_included(path, skill_root)),
        key=lambda path: path.relative_to(skill_root).as_posix(),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(skill_root: Path, archive_path: Path) -> str:
    """Write a byte-reproducible ZIP and return its lowercase SHA-256."""

    skill_root = skill_root.resolve()
    archive_path = archive_path.resolve()
    if not skill_root.is_dir():
        raise FileNotFoundError(f"Skill root does not exist: {skill_root}")
    if not (skill_root / "SKILL.md").is_file():
        raise ValueError(f"Skill root is missing SKILL.md: {skill_root}")
    if archive_path == skill_root or skill_root in archive_path.parents:
        raise ValueError("Archive path must be outside the Skill tree")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.", suffix=".tmp", dir=archive_path.parent
    )
    os.close(temporary_fd)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source_path in _skill_files(skill_root):
                relative = source_path.relative_to(skill_root).as_posix()
                member_name = f"presentation-studio/{relative}"
                info = zipfile.ZipInfo(member_name, date_time=FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source_path.read_bytes(), compresslevel=9)
        os.replace(temporary_path, archive_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return sha256_file(archive_path)


def build_repository_package(
    skill_root: Path = DEFAULT_SKILL_ROOT,
    archive_path: Path = DEFAULT_ARCHIVE_PATH,
    checksum_path: Path = DEFAULT_CHECKSUM_PATH,
) -> str:
    digest = build_archive(skill_root, archive_path)
    checksum_path = checksum_path.resolve()
    archive_path = archive_path.resolve()
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_name = (
        "dist/presentation-studio.zip"
        if checksum_path == DEFAULT_CHECKSUM_PATH.resolve()
        else archive_path.name
    )
    checksum_path.write_text(f"{digest}  {checksum_name}\n", encoding="ascii")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, default=DEFAULT_SKILL_ROOT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE_PATH)
    parser.add_argument("--checksum", type=Path, default=DEFAULT_CHECKSUM_PATH)
    args = parser.parse_args()

    digest = build_repository_package(args.skill_root, args.archive, args.checksum)
    print(f"PASS: built {args.archive} ({digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
