#!/usr/bin/env python3
"""Dependency-free installed-package and runtime smoke check."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


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
EXPECTED_ENGINES = {"ppt-master", "guizang", "frontend-slides", "baoyu"}


def _load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _probe_runtime(raw_path: str | None) -> dict[str, object]:
    if not raw_path:
        return {"available": False, "path": None, "reason": "not provided"}
    path = Path(raw_path).expanduser()
    if not path.is_absolute() or not path.is_file():
        return {"available": False, "path": str(path), "reason": "not an absolute executable file"}
    if "windowsapps" in {part.lower() for part in path.parts}:
        return {"available": False, "path": str(path), "reason": "WindowsApps alias rejected"}
    try:
        result = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "path": str(path), "reason": str(error)}
    version = (result.stdout or result.stderr).strip().splitlines()
    return {
        "available": result.returncode == 0,
        "path": str(path.resolve()),
        "version": version[0] if version else "",
        "reason": "" if result.returncode == 0 else f"exit {result.returncode}",
    }


def _verify_structure(root: Path) -> dict[str, object]:
    required = (
        "SKILL.md",
        "catalog/products.json",
        "catalog/styles.json",
        "core/retrieval.py",
        "core/router.py",
        "engines/manifest.json",
        "scripts/preflight.py",
        "scripts/recommend.py",
        "scripts/route.py",
        "scripts/self_check.py",
        "source-lock.json",
    )
    missing = [relative for relative in required if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"missing required files: {missing}")

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8-sig")
    if not skill_text.startswith("---\n") or "name: presentation-studio" not in skill_text:
        raise ValueError("invalid SKILL.md frontmatter")

    products = _load_json(root / "catalog" / "products.json")
    styles = _load_json(root / "catalog" / "styles.json")
    engines = _load_json(root / "engines" / "manifest.json")
    source_lock = _load_json(root / "source-lock.json")
    if {item.get("id") for item in products} != EXPECTED_PRODUCT_IDS:
        raise ValueError("product catalog does not match the supported product contract")
    if {item.get("id") for item in styles} != EXPECTED_STYLE_IDS:
        raise ValueError("style catalog does not match the supported style contract")
    if set(engines) != EXPECTED_ENGINES:
        raise ValueError("engine manifest must contain the four integrated engines")
    if len(source_lock.get("sources", [])) != 4:
        raise ValueError("source lock must contain four upstream sources")

    for engine_name, engine in engines.items():
        engine_root = root / engine["path"]
        for key in ("entry", "license_file"):
            if not (engine_root / engine[key]).is_file():
                raise ValueError(f"{engine_name} is missing {key}: {engine[key]}")

    files = tuple(path for path in root.rglob("*") if path.is_file())
    forbidden = [
        path
        for path in files
        if any(
            part in {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
            for part in path.relative_to(root).parts
        )
        or path.name in {".DS_Store", ".env", "Thumbs.db"}
        or path.suffix.lower() in {".bak", ".log", ".pyc", ".pyo", ".swp", ".tmp"}
    ]
    if forbidden:
        raise ValueError(f"generated, secret, or dependency artifact found: {forbidden[0]}")
    return {
        "root": str(root),
        "files": len(files),
        "products": len(products),
        "styles": len(styles),
        "engines": len(engines),
    }


def _run_router_smoke(root: Path) -> dict[str, object]:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    try:
        from core.retrieval import recommend_product
        from core.router import route_request
    finally:
        if sys.path and sys.path[0] == str(root):
            sys.path.pop(0)

    request = {
        "kind": "presentation",
        "outputs": ["pptx", "html", "pdf"],
        "editable": True,
        "has_exact_data": False,
        "topic": "installation smoke check",
        "audience": "executives",
        "purpose": "briefing",
        "tone": "confident",
        "channel": "boardroom",
        "density": "medium",
        "assets": [],
        "data_forms": [],
        "readiness": {
            "python": True,
            "node": True,
            "pptx_core": True,
            "office_renderer": False,
            "chromium": False,
            "image_provider": False,
        },
    }
    recommendation = recommend_product(request)
    if recommendation.status not in {"PASS", "PARTIAL"} or recommendation.product_id != "dual-format-deck":
        raise ValueError("recommendation smoke check did not select dual-format-deck")
    plan = route_request(
        {
            **request,
            "product": recommendation.product_id,
            "style": recommendation.style["selected"],
        }
    )
    if tuple(plan.engines) != ("ppt-master", "frontend-slides"):
        raise ValueError("routing smoke check did not select both native renderers")
    return {
        "product": recommendation.product_id,
        "style": recommendation.style["selected"],
        "engines": list(plan.engines),
        "outputs": list(plan.outputs),
    }


def run(root: Path, python_path: str | None, node_path: str | None) -> dict[str, object]:
    root = root.resolve()
    package = _verify_structure(root)
    smoke = _run_router_smoke(root)
    runtimes = {
        "python": _probe_runtime(python_path),
        "node": _probe_runtime(node_path),
    }
    status = "PASS" if all(item["available"] for item in runtimes.values()) else "PARTIAL"
    return {"status": status, "package": package, "runtimes": runtimes, "smoke": smoke}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an installed Presentation Studio skill")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--python")
    parser.add_argument("--node")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(args.root, args.python, args.node)
    except (ImportError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {"status": "FAIL", "error": str(error)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Self-check: {result['status']}")
        if result["status"] == "FAIL":
            print(result["error"], file=sys.stderr)
    return 0 if result["status"] == "PASS" else (2 if result["status"] == "PARTIAL" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
