from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def safe_slug(value: str) -> str:
    raw = value.strip()
    if not raw or ".." in raw or any(char in raw for char in ("/", "\\", ":")):
        raise ValueError("Project name must be a simple slug, not a path")
    slug = re.sub(r"[-_\s]+", "-", raw.lower()).strip("-")
    if not _SLUG.fullmatch(slug):
        raise ValueError("Project name must contain only letters, digits, and hyphens")
    return slug


@dataclass(frozen=True)
class ProjectPaths:
    project: Path
    pptx: Path
    html: Path
    pdf: Path
    assets: Path
    temp: Path


def build_project_paths(output_root: Path, project_name: str) -> ProjectPaths:
    slug = safe_slug(project_name)
    project = output_root.resolve() / slug
    return ProjectPaths(
        project=project,
        pptx=project / f"{slug}.pptx",
        html=project / f"{slug}.html",
        pdf=project / f"{slug}.pdf",
        assets=project / "assets",
        temp=project / ".temp",
    )
