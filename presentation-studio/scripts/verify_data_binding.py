#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.data_binding import build_data_manifest, compare_bound_values, validate_engine_payload_evidence


class _ArgumentParseError(ValueError):
    pass


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentParseError(message)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def _load_json(path_text: str, label: str) -> Any:
    try:
        return json.loads(Path(path_text).read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{label}: invalid JSON: {error}") from None


def _emit(status: str, mismatches: list[str], findings: list[str]) -> int:
    print(json.dumps({"status": status, "mismatches": mismatches, "findings": findings}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return {"PASS": 0, "PARTIAL": 1, "FAIL": 2}[status]


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(description="Verify exact Presentation Studio data binding evidence", allow_abbrev=False)
    parser.add_argument("--manifest")
    parser.add_argument("--engine-payload")
    parser.add_argument("--observed-contract")
    try:
        args = parser.parse_args(argv)
    except _ArgumentParseError as error:
        return _emit("FAIL", [f"invalid arguments: {error}"], [])
    missing = [
        label for label, value in (
            ("manifest", args.manifest),
            ("engine-payload", args.engine_payload),
            ("observed-contract", args.observed_contract),
        ) if not value
    ]
    if missing:
        return _emit("FAIL", [f"invalid arguments: missing required evidence: {label}" for label in missing], [])
    try:
        manifest = build_data_manifest(_load_json(args.manifest, "manifest"))
        payload_mismatches = validate_engine_payload_evidence(
            manifest, _load_json(args.engine_payload, "engine-payload")
        )
        comparison = compare_bound_values(
            manifest, _load_json(args.observed_contract, "observed-contract")
        )
    except (TypeError, ValueError) as error:
        return _emit("FAIL", [str(error)], [])
    mismatches = list(payload_mismatches) + list(comparison.mismatches)
    return _emit("FAIL" if mismatches else comparison.status, mismatches, list(comparison.findings))


if __name__ == "__main__":
    raise SystemExit(main())
