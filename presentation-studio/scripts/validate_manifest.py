#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.qa import Issue, ValidationReport, validate_manifest


class _ArgumentParseError(ValueError):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentParseError(message)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(description="Validate a Presentation Studio layout manifest", allow_abbrev=False)
    parser.add_argument("--json", required=True, help="Manifest object as JSON")
    try:
        args = parser.parse_args(argv)
    except _ArgumentParseError as error:
        report = ValidationReport("FAIL", (Issue("INVALID_ARGUMENT", f"invalid arguments: {error}"),))
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 2
    invalid_json = False
    try:
        report = validate_manifest(json.loads(args.json, parse_constant=_reject_constant))
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        report = ValidationReport("FAIL", (Issue("INVALID_JSON", f"invalid manifest JSON: {error}"),))
        invalid_json = True
    print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if report.status == "PASS" else (2 if invalid_json else 1)


if __name__ == "__main__":
    raise SystemExit(main())
