#!/usr/bin/env python3
"""Dependency-free structural and archive verifier for Presentation Studio."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

try:
    from scripts.verify_examples import verify_all as verify_all_examples
except ModuleNotFoundError:
    from verify_examples import verify_all as verify_all_examples


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPOSITORY_ROOT / "presentation-studio"
ARCHIVE_PATH = REPOSITORY_ROOT / "dist" / "presentation-studio.zip"
EXPECTED_PRODUCT_IDS = {
    "native-editable-deck",
    "native-data-deck",
    "swiss-editorial-deck",
    "executive-deck",
    "technical-deck",
    "html-presenter",
    "dual-format-deck",
    "cover-image",
    "article-illustration",
    "infographic-image",
    "technical-diagram",
    "data-image",
    "image-slide-deck",
}
EXPECTED_STYLE_IDS = {
    "swiss-editorial",
    "executive-minimal",
    "data-analytical",
    "technical-systems",
    "narrative-cinematic",
    "warm-educational",
    "bold-promotional",
    "visual-infographic",
}
EXPECTED_SOURCES = {
    "https://github.com/hugohe3/ppt-master.git",
    "https://github.com/op7418/guizang-ppt-skill.git",
    "https://github.com/zarazhangrui/frontend-slides.git",
    "https://github.com/JimLiu/baoyu-skills.git",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def load_json(relative_path: str):
    path = SKILL_ROOT / relative_path
    if not path.is_file():
        fail(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def verify_structure() -> dict[str, int]:
    required = [
        "SKILL.md",
        "catalog/products.json",
        "catalog/styles.json",
        "core/retrieval.py",
        "core/data_binding.py",
        "core/router.py",
        "engines/manifest.json",
        "references/product-retrieval.md",
        "references/data-binding.md",
        "scripts/recommend.py",
        "scripts/preflight.py",
        "scripts/route.py",
        "scripts/self_check.py",
        "source-lock.json",
    ]
    for relative_path in required:
        if not (SKILL_ROOT / relative_path).is_file():
            fail(f"Missing required file: presentation-studio/{relative_path}")

    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8-sig")
    if not skill_text.startswith("---\n") or "name: presentation-studio" not in skill_text:
        fail("SKILL.md frontmatter is invalid or has the wrong skill name")

    products = load_json("catalog/products.json")
    styles = load_json("catalog/styles.json")
    engines = load_json("engines/manifest.json")
    source_lock = load_json("source-lock.json")

    product_ids = {item.get("id") for item in products}
    style_ids = {item.get("id") for item in styles}
    if product_ids != EXPECTED_PRODUCT_IDS:
        fail(f"Product catalog mismatch: {sorted(product_ids ^ EXPECTED_PRODUCT_IDS)}")
    if style_ids != EXPECTED_STYLE_IDS:
        fail(f"Style catalog mismatch: {sorted(style_ids ^ EXPECTED_STYLE_IDS)}")
    if set(engines) != {"ppt-master", "guizang", "frontend-slides", "baoyu"}:
        fail("Engine manifest must contain exactly the four integrated engines")

    source_urls = {item.get("repository") for item in source_lock.get("sources", [])}
    if source_urls != EXPECTED_SOURCES:
        fail("source-lock.json does not contain the four expected upstream repositories")

    files = [path for path in SKILL_ROOT.rglob("*") if path.is_file()]
    forbidden = [
        path
        for path in files
        if any(
            part in {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
            for part in path.relative_to(SKILL_ROOT).parts
        )
        or path.name in {".DS_Store", ".env", "Thumbs.db"}
        or path.suffix.lower() in {".bak", ".log", ".pyc", ".pyo", ".swp", ".tmp"}
    ]
    if forbidden:
        fail(f"Generated, secret, or dependency artifact found: {forbidden[0]}")
    return {"files": len(files), "products": len(products), "styles": len(styles), "engines": len(engines)}


def verify_readme() -> None:
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8-sig")
    normalized_readme = readme.replace("\\", "/")
    required_fragments = [
        "中文说明",
        "English Guide",
        "Intelligent retrieval",
        "智能检索",
        "Exact-data",
        "精准数据",
        "hugohe3/ppt-master",
        "op7418/guizang-ppt-skill",
        "zarazhangrui/frontend-slides",
        "JimLiu/baoyu-skills",
        "scripts/install.ps1",
        "scripts/install.sh",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in normalized_readme]
    if missing:
        fail(f"README is missing required bilingual documentation: {missing}")


def verify_repository_assets() -> dict[str, int]:
    required_paths = (
        "docs/architecture.md",
        "docs/upstream-sync.md",
        ".github/workflows/validate.yml",
        ".github/workflows/sync-upstreams.yml",
        "scripts/upstream_sources.json",
        "scripts/upstream_sync.py",
        "scripts/verify_examples.py",
    )
    for relative_path in required_paths:
        if not (REPOSITORY_ROOT / relative_path).is_file():
            fail(f"Missing required repository asset: {relative_path}")

    example_summary = verify_all_examples(REPOSITORY_ROOT)
    if example_summary.get("status") != "PASS":
        fail("Bilingual examples did not pass structural acceptance")
    products = example_summary.get("products", [])
    if len(products) != 6:
        fail("Expected exactly six bilingual example products")
    return {"example_products": len(products)}


def verify_local_markdown_links() -> None:
    for document_name in [
        "README.md",
        "CONTRIBUTORS.md",
        "THIRD_PARTY_NOTICES.md",
        "docs/architecture.md",
        "docs/upstream-sync.md",
    ]:
        document_path = REPOSITORY_ROOT / document_name
        text = document_path.read_text(encoding="utf-8-sig")
        for raw_target in re.findall(r"\]\(([^)]+)\)", text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            # pathlib on Windows accepts forward-slash repository links directly.
            relative_target = unquote(target.split("#", 1)[0])
            if not (document_path.parent / relative_target).exists():
                fail(f"Broken local Markdown link in {document_name}: {target}")


def verify_archive(skill_file_count: int) -> dict[str, object]:
    if not ARCHIVE_PATH.is_file():
        fail(f"Missing release archive: {ARCHIVE_PATH}")

    disk_paths = {
        path.relative_to(SKILL_ROOT).as_posix(): path
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            fail("Archive contains duplicate file names")
        if len(infos) != skill_file_count:
            fail(f"Archive file count {len(infos)} does not match folder count {skill_file_count}")

        archive_paths: dict[str, zipfile.ZipInfo] = {}
        non_ascii_count = 0
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if "\\" in name or pure.is_absolute() or ".." in pure.parts:
                fail(f"Unsafe archive path: {name}")
            if not name.startswith("presentation-studio/"):
                fail(f"Unexpected archive root: {name}")
            relative_name = name.removeprefix("presentation-studio/")
            if "__pycache__" in pure.parts or relative_name.lower().endswith((".pyc", ".pyo")):
                fail(f"Cache artifact in archive: {name}")
            if not name.isascii():
                non_ascii_count += 1
                if not (info.flag_bits & 0x800):
                    fail(f"Non-ASCII path is not UTF-8 flagged: {name}")
            archive_paths[relative_name] = info

        if set(archive_paths) != set(disk_paths):
            missing = sorted(set(disk_paths) - set(archive_paths))[:5]
            extra = sorted(set(archive_paths) - set(disk_paths))[:5]
            fail(f"Archive path mismatch; missing={missing}, extra={extra}")

        # Extract only after every member path has passed traversal/root checks.
        # Hashing two filesystem trees in parallel is substantially faster than
        # performing thousands of random seeks inside a ZIP on Windows.
        with tempfile.TemporaryDirectory(prefix="presentation-studio-verify-") as temp_directory:
            extracted_root = Path(temp_directory)
            archive.extractall(extracted_root)
            extracted_skill_root = extracted_root / "presentation-studio"

            def compare_one(item: tuple[str, Path]) -> str | None:
                relative_name, disk_path = item
                extracted_path = extracted_skill_root / Path(relative_name)
                if sha256_file(disk_path) != sha256_file(extracted_path):
                    return relative_name
                return None

            with ThreadPoolExecutor(max_workers=8) as pool:
                mismatches = [name for name in pool.map(compare_one, disk_paths.items()) if name]
            if mismatches:
                fail(f"Archive content mismatch: {mismatches[0]}")

    archive_sha256 = sha256_file(ARCHIVE_PATH)
    checksum_path = REPOSITORY_ROOT / "checksums.sha256"
    checksum_line = checksum_path.read_text(encoding="ascii").strip()
    expected_checksum, expected_name = checksum_line.split(maxsplit=1)
    if expected_name.replace("\\", "/") != "dist/presentation-studio.zip":
        fail("checksums.sha256 points to an unexpected archive path")
    if archive_sha256 != expected_checksum.lower():
        fail("Archive SHA-256 does not match checksums.sha256")

    return {
        "archive_sha256": archive_sha256,
        "archive_files": len(disk_paths),
        "non_ascii_utf8_paths": non_ascii_count,
    }


def main() -> int:
    try:
        summary = verify_structure()
        verify_readme()
        repository_assets = verify_repository_assets()
        verify_local_markdown_links()
        archive = verify_archive(summary["files"])
    except (AssertionError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("PASS: Presentation Studio package is structurally complete.")
    print(json.dumps({**summary, **repository_assets, **archive}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
