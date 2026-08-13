#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.router import route_request
from core.catalog import CatalogError


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
    parser = argparse.ArgumentParser(description="Route a normalized Presentation Studio request")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--json", help="Request object as JSON")
    group.add_argument("--json-file", type=Path, help="Path to a request JSON file")
    args = parser.parse_args(argv)
    try:
        if args.json_file is not None:
            try:
                raw = args.json_file.read_text(encoding="utf-8-sig")
            except OSError as error:
                raise ValueError(f"Unable to read request JSON: {error}") from error
        else:
            raw = args.json if args.json is not None else sys.stdin.read()
        request = load_json(raw)
        plan = route_request(request)
    except (CatalogError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
