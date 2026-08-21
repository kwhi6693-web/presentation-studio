from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"
VALIDATE_PATH = SKILL_ROOT / "scripts" / "validate_manifest.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.qa import validate_manifest  # noqa: E402


def _manifest() -> dict[str, object]:
    return {
        "canvas": {"width": 1200, "height": 675, "safe_margin": 24},
        "objects": [
            {
                "id": "title",
                "page_id": "page-1",
                "role": "text",
                "x": 40,
                "y": 40,
                "width": 500,
                "height": 60,
                "font_size": 24,
                "z_index": 1,
                "allowed_overlap": [],
            }
        ],
        "image_slots": [],
    }


class LayoutQaTests(unittest.TestCase):
    def test_valid_manifest_passes(self) -> None:
        self.assertEqual(validate_manifest(_manifest()).as_dict(), {"status": "PASS", "issues": []})

    def test_schema_is_checked_before_geometry_and_reports_structured_issues(self) -> None:
        malformed = {
            "canvas": [],
            "objects": [
                {"id": "", "page_id": "", "role": "unknown", "x": "not-a-number"}
            ],
            "image_slots": {},
        }

        report = validate_manifest(malformed)

        self.assertEqual(report.status, "FAIL")
        self.assertTrue(report.issues)
        self.assertTrue(all(issue.code.startswith("SCHEMA_") for issue in report.issues))
        self.assertNotIn("SAFE_MARGIN", {issue.code for issue in report.issues})

    def test_non_finite_or_invalid_dimensions_fail_without_traceback(self) -> None:
        cases = (
            ("canvas", {"canvas": {"width": float("nan"), "height": 10, "safe_margin": 0}}),
            ("object", {"objects": [{**_manifest()["objects"][0], "width": float("inf")}]}),
            ("image", {"image_slots": [{"id": "hero", "width": 100, "height": 100, "generated_width": 100, "generated_height": float("nan")}]}),
        )
        for name, replacement in cases:
            with self.subTest(name=name):
                value = _manifest()
                value.update(replacement)
                report = validate_manifest(value)
                self.assertEqual(report.status, "FAIL")
                self.assertTrue(any(issue.code.startswith("SCHEMA_") for issue in report.issues))

    def test_huge_json_integers_return_schema_issues_without_core_or_cli_exceptions(self) -> None:
        huge = 10 ** 400
        cases = (
            ("canvas", {"canvas": {"width": huge, "height": 675, "safe_margin": 24}}),
            ("object", {"objects": [{**_manifest()["objects"][0], "x": huge}]}),
            ("image", {"image_slots": [{"id": "hero", "width": huge, "height": 100, "generated_width": 100, "generated_height": 100}]}),
        )
        spec = importlib.util.spec_from_file_location("validate_manifest_huge", VALIDATE_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, replacement in cases:
            with self.subTest(name=name):
                manifest = _manifest()
                manifest.update(replacement)
                report = validate_manifest(manifest)
                self.assertEqual(report.status, "FAIL")
                self.assertTrue(any(issue.code.startswith("SCHEMA_") for issue in report.issues))
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = module.main(["--json", json.dumps(manifest)])
                response = json.loads(output.getvalue())
                self.assertEqual(exit_code, 1)
                self.assertEqual(response["status"], "FAIL")
                self.assertTrue(any(issue["code"].startswith("SCHEMA_") for issue in response["issues"]))

    def test_page_group_z_order_and_authorized_overlap_are_deterministic(self) -> None:
        manifest = _manifest()
        manifest["objects"] = [
            {
                "id": "overlay", "page_id": "page-1", "role": "shape",
                "x": 100, "y": 100, "width": 200, "height": 200,
                "z_index": 2, "group_id": "hero", "allowed_overlap": ["copy"],
            },
            {
                "id": "copy", "page_id": "page-1", "role": "text",
                "x": 120, "y": 120, "width": 200, "height": 100,
                "font_size": 16, "z_index": 1, "group_id": "hero", "allowed_overlap": [],
            },
            {
                "id": "other-page", "page_id": "page-2", "role": "shape",
                "x": 120, "y": 120, "width": 200, "height": 100,
                "z_index": 1, "allowed_overlap": [],
            },
        ]
        self.assertEqual(validate_manifest(manifest).status, "PASS")

        unauthorized = json.loads(json.dumps(manifest))
        unauthorized["objects"][0]["allowed_overlap"] = []
        report = validate_manifest(unauthorized)
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.issues[0].code, "OVERLAP")
        self.assertEqual(report.issues[0].objects, ("copy", "overlay"))

    def test_overlap_references_must_be_unique_real_same_page_and_not_self(self) -> None:
        cases = (
            ("duplicate", ["title", "title"]),
            ("self", ["title"]),
            ("unknown", ["missing"]),
        )
        for name, allowed in cases:
            with self.subTest(name=name):
                manifest = _manifest()
                manifest["objects"][0]["allowed_overlap"] = allowed
                report = validate_manifest(manifest)
                self.assertEqual(report.status, "FAIL")
                self.assertTrue(any(issue.code == "SCHEMA_ALLOWED_OVERLAP" for issue in report.issues))

        cross_page = _manifest()
        cross_page["objects"].append({
            "id": "other", "page_id": "page-2", "role": "shape", "x": 40, "y": 40,
            "width": 50, "height": 50, "z_index": 0, "allowed_overlap": [],
        })
        cross_page["objects"][0]["allowed_overlap"] = ["other"]
        report = validate_manifest(cross_page)
        self.assertTrue(any(issue.code == "SCHEMA_ALLOWED_OVERLAP" for issue in report.issues))

    def test_role_specific_font_floors_are_text_16_caption_12_footnote_10(self) -> None:
        cases = (
            ("text", 15, "MIN_FONT"),
            ("caption", 11, "MIN_FONT"),
            ("footnote", 9, "MIN_FONT"),
            ("shape", None, None),
        )
        for role, font_size, expected_issue in cases:
            with self.subTest(role=role):
                manifest = _manifest()
                obj = manifest["objects"][0]
                obj["role"] = role
                if font_size is None:
                    obj.pop("font_size")
                else:
                    obj["font_size"] = font_size
                report = validate_manifest(manifest)
                self.assertEqual(
                    "MIN_FONT" in {issue.code for issue in report.issues},
                    expected_issue == "MIN_FONT",
                )

    def test_validate_manifest_cli_returns_stable_json_for_invalid_json_and_invalid_schema(self) -> None:
        spec = importlib.util.spec_from_file_location("validate_manifest", VALIDATE_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for raw, expected_status, expected_exit in (
            ("{not json", "FAIL", 2),
            (json.dumps({"canvas": {}, "objects": [], "image_slots": []}), "FAIL", 1),
            (json.dumps(_manifest()), "PASS", 0),
        ):
            with self.subTest(raw=raw):
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = module.main(["--json", raw])
                response = json.loads(output.getvalue())
                self.assertEqual(exit_code, expected_exit)
                self.assertEqual(response["status"], expected_status)
                self.assertIn("issues", response)

    def test_validate_manifest_cli_argument_errors_are_structured_stdout_only(self) -> None:
        for arguments in ([], ["--json"], ["--unknown"]):
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    [sys.executable, str(VALIDATE_PATH), *arguments],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    check=False,
                )
                response = json.loads(completed.stdout)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(response["status"], "FAIL")
                self.assertEqual(response["issues"][0]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
