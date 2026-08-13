#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from core.qa import validate_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Presentation Studio layout manifest")
    parser.add_argument("--json", required=True, help="Manifest object as JSON")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.json)
        if not isinstance(manifest, dict):
            raise ValueError("top-level value must be an object")
    except (json.JSONDecodeError, ValueError) as error:
        print(f"Invalid manifest JSON: {error}", file=sys.stderr)
        return 2
    report = validate_manifest(manifest)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
