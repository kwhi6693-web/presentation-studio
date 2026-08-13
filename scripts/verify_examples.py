#!/usr/bin/env python3
"""Verify the six bilingual example products without third-party packages."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SLIDE_NAME = re.compile(r"^ppt/slides/slide\d+\.xml$")
NOTES_NAME = re.compile(r"^ppt/notesSlides/notesSlide\d+\.xml$")
REMOTE_ASSET = re.compile(r"(?:src|href)\s*=\s*['\"]https?://", re.IGNORECASE)
HTML_SLIDE = re.compile(r"<section\b[^>]*\bclass=['\"][^'\"]*\bslide\b", re.IGNORECASE)
PDF_PAGE = re.compile(rb"/Type\s*/Page(?!s)")
PDF_MEDIA_BOX = re.compile(rb"/MediaBox\s*\[([^\]]+)\]")


class ExampleError(AssertionError):
    """An example product violated its checked-in acceptance contract."""


def expected_example_paths(repository_root: Path = REPOSITORY_ROOT) -> tuple[Path, ...]:
    base = repository_root / "examples" / "bilingual-acceptance"
    return tuple(
        base / language / f"presentation-acceptance-{language}.{suffix}"
        for language in ("zh", "en")
        for suffix in ("pptx", "html", "pdf")
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExampleError(message)


def verify_pptx(path: Path, language: str) -> dict:
    _require(path.is_file(), f"Missing PPTX example: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            _require(corrupt is None, f"Corrupt PPTX member: {corrupt}")
            names = set(archive.namelist())
            slides = sorted(name for name in names if SLIDE_NAME.fullmatch(name))
            notes = sorted(name for name in names if NOTES_NAME.fullmatch(name))
            charts = sorted(name for name in names if name.startswith("ppt/charts/chart"))
            slide_xml = [archive.read(name) for name in slides]
    except (OSError, zipfile.BadZipFile) as error:
        raise ExampleError(f"Unreadable PPTX example: {path}") from error

    _require(len(slides) == 5, f"PPTX must contain five slides: {path}")
    _require(len(notes) == 5, f"PPTX must contain five notes pages: {path}")
    _require(bool(charts), f"PPTX must contain a native chart: {path}")
    _require(any(b"<a:tbl" in xml for xml in slide_xml), f"PPTX must contain a native table: {path}")
    _require(
        any(b"<p:animEffect" in xml and b'filter="fade"' in xml for xml in slide_xml),
        f"PPTX must contain a native fade animation: {path}",
    )
    combined = b"\n".join(slide_xml).decode("utf-8", errors="ignore")
    if language == "zh":
        _require(re.search(r"[\u4e00-\u9fff]", combined) is not None, "Chinese PPTX has no Chinese text")
    else:
        _require(
            "Presentation Capability Acceptance Report" in combined,
            "English PPTX identity text is missing",
        )
    return {
        "path": path.as_posix(),
        "status": "PASS",
        "kind": "pptx",
        "language": language,
        "pages": len(slides),
        "notes": len(notes),
        "native_charts": len(charts),
        "native_table": True,
        "fade_animation": True,
    }


def verify_html(path: Path, language: str) -> dict:
    _require(path.is_file(), f"Missing HTML example: {path}")
    text = path.read_text(encoding="utf-8-sig")
    slides = len(HTML_SLIDE.findall(text))
    _require(slides == 5, f"HTML must contain five slides: {path}")
    expected_lang = "zh" if language == "zh" else "en"
    language_match = re.search(r"<html\b[^>]*\blang=['\"]([^'\"]+)", text, re.IGNORECASE)
    _require(
        language_match is not None and language_match.group(1).lower().startswith(expected_lang),
        f"HTML language does not match {language}: {path}",
    )
    for token in ("keydown", "ArrowRight", "ArrowLeft", "contenteditable", "@media print", "data:image"):
        _require(token in text, f"HTML contract token is missing ({token}): {path}")
    _require(REMOTE_ASSET.search(text) is None, f"Standalone HTML has a remote asset: {path}")
    return {
        "path": path.as_posix(),
        "status": "PASS",
        "kind": "html",
        "language": language,
        "pages": slides,
        "keyboard": True,
        "editable": True,
        "print_css": True,
        "offline_assets": True,
    }


def verify_pdf(path: Path, language: str) -> dict:
    _require(path.is_file(), f"Missing PDF example: {path}")
    payload = path.read_bytes()
    _require(payload.startswith(b"%PDF-"), f"Invalid PDF header: {path}")
    pages = len(PDF_PAGE.findall(payload))
    _require(pages == 5, f"PDF must contain five pages: {path}")
    boxes = PDF_MEDIA_BOX.findall(payload)
    _require(bool(boxes), f"PDF has no MediaBox: {path}")
    for raw_box in boxes:
        try:
            values = [float(value) for value in raw_box.split()]
        except ValueError as error:
            raise ExampleError(f"PDF has an invalid MediaBox: {path}") from error
        _require(values == [0.0, 0.0, 960.0, 540.0], f"PDF is not 16:9 at 960x540 pt: {path}")
    return {
        "path": path.as_posix(),
        "status": "PASS",
        "kind": "pdf",
        "language": language,
        "pages": pages,
        "media_box": [0, 0, 960, 540],
    }


def verify_all(repository_root: Path = REPOSITORY_ROOT) -> dict:
    products: list[dict] = []
    for path in expected_example_paths(repository_root):
        language = path.parent.name
        if path.suffix.lower() == ".pptx":
            products.append(verify_pptx(path, language))
        elif path.suffix.lower() == ".html":
            products.append(verify_html(path, language))
        elif path.suffix.lower() == ".pdf":
            products.append(verify_pdf(path, language))
        else:
            raise ExampleError(f"Unexpected example product type: {path}")
    return {"status": "PASS", "products": products}


def main() -> int:
    try:
        summary = verify_all()
    except (ExampleError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: six bilingual example products satisfy their structural contracts.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
