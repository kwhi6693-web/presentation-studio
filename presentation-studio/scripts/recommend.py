#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from core.catalog import CatalogError
from core.retrieval import recommend_product


def load_json(raw: str) -> dict:
    if not raw.strip():
        raise ValueError("Invalid request JSON: input is empty")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid request JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError("Invalid request JSON: top-level value must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend a Presentation Studio product")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--json", help="Request object as JSON")
    group.add_argument("--json-file", type=Path, help="Path to a request JSON file")
    args = parser.parse_args(argv)
    try:
        raw = args.json if args.json is not None else (
            args.json_file.read_text(encoding="utf-8-sig") if args.json_file else sys.stdin.read()
        )
        request = load_json(raw)
        request.setdefault("kind", "presentation")
        result = recommend_product(request).as_dict()
    except (CatalogError, OSError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    result["product"] = result["product_id"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
