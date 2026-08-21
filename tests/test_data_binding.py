from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"
VERIFY_PATH = SKILL_ROOT / "scripts" / "verify_data_binding.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.data_binding import (  # noqa: E402
    ObservedDataContract,
    build_data_manifest,
    build_engine_payload,
    compare_bound_values,
)


def _manifest() -> dict[str, object]:
    return {
        "source": "finance-q2.csv",
        "source_form": "csv",
        "provenance": "finance-team/2026-q2",
        "fields": [
            {
                "name": "revenue",
                "type": "number",
                "values": [1, -0.0],
                "unit": "USDm",
                "period": "2026-Q2",
                "label": "Revenue",
            },
            {
                "name": "region",
                "type": "string",
                "values": ["APAC", "EMEA"],
                "unit": "",
                "period": "2026-Q2",
                "label": "Region",
            },
        ],
        "transformations": [
            {
                "name": "currency-normalization",
                "documentation": "Finance-approved USD millions conversion.",
                "approved": True,
                "parameters": {"scale": 1},
            }
        ],
        "findings": [],
        "record_ids": ["row-a", "row-b"],
    }


def _observed(manifest: dict[str, object]) -> dict[str, object]:
    result = json.loads(json.dumps(manifest))
    fields = result["fields"]
    assert isinstance(fields, list)
    for field in fields:
        assert isinstance(field, dict)
        values = field["values"]
        assert isinstance(values, list)
        field["concrete_types"] = [type(value).__name__ for value in values]
        field["missing_positions"] = []
    result["duplicate_record_ids"] = []
    return result


def _payload_evidence(manifest: dict[str, object]) -> dict[str, object]:
    payload = build_engine_payload(build_data_manifest(manifest), "native-data-deck")
    return {
        "product_id": payload.product_id,
        "engine": payload.engine,
        "target_types": list(payload.target_types),
        "render_mode": payload.render_mode,
        "manual_redraw_allowed": payload.manual_redraw_allowed,
        "provenance": payload.provenance,
        "labels": list(payload.labels),
        "binding_targets": [
            {"field": field_name, "target_type": target_type}
            for field_name, target_type in payload.binding_targets
        ],
    }


class ExactDataBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_manifest = _manifest()

    def test_matching_triplet_passes_and_exact_api_preserves_signed_zero(self) -> None:
        manifest = build_data_manifest(self.raw_manifest)

        report = compare_bound_values(manifest, _observed(self.raw_manifest))

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.mismatches, ())
        self.assertTrue(math.copysign(1.0, manifest.fields[0].values[1]) < 0)

    def test_comparison_rejects_type_unit_label_value_and_order_tampering(self) -> None:
        manifest = build_data_manifest(self.raw_manifest)
        cases = {
            "type": lambda value: value["fields"][0].__setitem__("type", "string"),
            "unit": lambda value: value["fields"][0].__setitem__("unit", "EURm"),
            "label": lambda value: value["fields"][0].__setitem__("label", "Sales"),
            "concrete-type": lambda value: value["fields"][0].__setitem__(
                "concrete_types", ["float", "float"]
            ),
            "integer-versus-float": lambda value: value["fields"][0].__setitem__(
                "values", [1.0, -0.0]
            ),
            "signed-zero": lambda value: value["fields"][0].__setitem__(
                "values", [1, 0.0]
            ),
            "field-order": lambda value: value.__setitem__(
                "fields", list(reversed(value["fields"]))
            ),
            "provenance": lambda value: value.__setitem__("provenance", "tampered"),
        }
        for name, tamper in cases.items():
            with self.subTest(name=name):
                observed = _observed(self.raw_manifest)
                tamper(observed)
                report = compare_bound_values(manifest, observed)
                self.assertEqual(report.status, "FAIL")
                self.assertTrue(report.mismatches)

    def test_non_finite_manifest_observed_and_transformation_parameters_fail_closed(self) -> None:
        cases = (
            ("manifest", lambda value: value["fields"][0].__setitem__("values", [float("nan"), 1])),
            ("parameters", lambda value: value["transformations"][0].__setitem__("parameters", {"scale": float("inf")})),
        )
        for name, tamper in cases:
            with self.subTest(name=name):
                raw = _manifest()
                tamper(raw)
                with self.assertRaisesRegex(ValueError, "finite|JSON-compatible"):
                    build_data_manifest(raw)

        with self.assertRaisesRegex(ValueError, "finite"):
            compare_bound_values(
                build_data_manifest(self.raw_manifest),
                {**_observed(self.raw_manifest), "record_ids": [float("nan"), "row-b"]},
            )

        raw_observed = _observed(self.raw_manifest)
        fields = raw_observed["fields"]
        assert isinstance(fields, list) and isinstance(fields[0], dict)
        fields[0]["values"] = [float("inf"), -0.0]
        direct_contract = ObservedDataContract(
            source=raw_observed["source"],
            source_form=raw_observed["source_form"],
            provenance=raw_observed["provenance"],
            fields=raw_observed["fields"],
            transformations=raw_observed["transformations"],
            findings=raw_observed["findings"],
            record_ids=raw_observed["record_ids"],
            duplicate_record_ids=raw_observed["duplicate_record_ids"],
        )
        with self.assertRaisesRegex(ValueError, "finite"):
            compare_bound_values(build_data_manifest(self.raw_manifest), direct_contract)

    def test_raw_manifest_rejects_non_finite_numbers_in_unused_nested_members_and_keys(self) -> None:
        cases = (
            ("dict-value", lambda value: {"extension": {"nested": [value]}}),
            ("tuple-value", lambda value: {"extension": ({"nested": value},)}),
            ("dict-key", lambda value: {"extension": {value: "unused"}}),
        )
        for number in (float("nan"), float("inf"), float("-inf")):
            for name, extension in cases:
                with self.subTest(number=repr(number), name=name):
                    raw = _manifest()
                    raw.update(extension(number))
                    with self.assertRaisesRegex(ValueError, r"manifest\.extension"):
                        build_data_manifest(raw)

    def test_verify_cli_requires_full_triplet_and_validates_payload_provenance(self) -> None:
        spec = importlib.util.spec_from_file_location("verify_data_binding", VERIFY_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="presentation-studio-exact-data-") as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            payload_path = root / "payload.json"
            observed_path = root / "observed.json"
            manifest_path.write_text(json.dumps(self.raw_manifest), encoding="utf-8")
            payload_path.write_text(json.dumps(_payload_evidence(self.raw_manifest)), encoding="utf-8")
            observed_path.write_text(json.dumps(_observed(self.raw_manifest)), encoding="utf-8")

            for missing in ("manifest", "engine-payload", "observed-contract"):
                args = [
                    "--manifest", str(manifest_path),
                    "--engine-payload", str(payload_path),
                    "--observed-contract", str(observed_path),
                ]
                del args[args.index(f"--{missing}") : args.index(f"--{missing}") + 2]
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = module.main(args)
                response = json.loads(output.getvalue())
                self.assertEqual(exit_code, 2)
                self.assertEqual(response["status"], "FAIL")
                self.assertIn("missing", response["mismatches"][0])

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = module.main([
                    "--manifest", str(manifest_path),
                    "--engine-payload", str(payload_path),
                    "--observed-contract", str(observed_path),
                ])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue()), {
                "status": "PASS", "mismatches": [], "findings": []
            })

            tampered = _payload_evidence(self.raw_manifest)
            tampered["binding_targets"] = list(reversed(tampered["binding_targets"]))
            payload_path.write_text(json.dumps(tampered), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = module.main([
                    "--manifest", str(manifest_path),
                    "--engine-payload", str(payload_path),
                    "--observed-contract", str(observed_path),
                ])
            response = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(response["status"], "FAIL")
            self.assertIn("binding_targets", response["mismatches"][0])

    def test_verify_cli_rejects_nonstandard_json_constants_with_stable_json(self) -> None:
        spec = importlib.util.spec_from_file_location("verify_data_binding_constants", VERIFY_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="presentation-studio-exact-data-") as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            payload_path = root / "payload.json"
            observed_path = root / "observed.json"
            manifest_path.write_text('{"fields": [NaN]}', encoding="utf-8")
            payload_path.write_text("{}", encoding="utf-8")
            observed_path.write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = module.main([
                    "--manifest", str(manifest_path),
                    "--engine-payload", str(payload_path),
                    "--observed-contract", str(observed_path),
                ])
            response = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(response["status"], "FAIL")
            self.assertIn("invalid JSON", response["mismatches"][0])

    def test_verify_cli_argument_errors_are_compact_json_on_stdout_only(self) -> None:
        cases = ([], ["--manifest"], ["--unknown"])
        for arguments in cases:
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    [sys.executable, str(VERIFY_PATH), *arguments],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    check=False,
                )
                response = json.loads(completed.stdout)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(response["status"], "FAIL")
                self.assertTrue(response["mismatches"][0].startswith("invalid arguments:"))


if __name__ == "__main__":
    unittest.main()
