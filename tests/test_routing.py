from __future__ import annotations

import sys
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT))

from core.retrieval import recommend_product
from core.router import route_request


class PartialEditabilityTests(unittest.TestCase):
    def test_cli_entrypoints_do_not_create_bytecode_cache_in_skill_tree(self) -> None:
        scripts = ("recommend.py", "route.py", "validate_manifest.py")
        for script in scripts:
            with self.subTest(script=script):
                subprocess.run(
                    [sys.executable, str(SKILL_ROOT / "scripts" / script), "--help"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
        cache_directories = tuple(SKILL_ROOT.rglob("__pycache__"))
        self.assertEqual(cache_directories, ())

    def setUp(self) -> None:
        self.request = {
            "kind": "presentation",
            "outputs": ["pptx", "html", "pdf"],
            "editable": True,
            "has_exact_data": False,
            "topic": "AI product strategy",
            "audience": "executives",
            "purpose": "strategy briefing",
            "tone": "confident",
            "channel": "boardroom",
            "density": "medium",
            "assets": [],
            "data_forms": [],
            "readiness": {
                "python": True,
                "node": True,
                "office_renderer": True,
                "chromium": True,
                "image_provider": False,
            },
        }

    def test_dual_format_product_satisfies_editability_via_pptx_output(self) -> None:
        recommendation = recommend_product(self.request)
        self.assertEqual(recommendation.status, "PASS")
        self.assertEqual(recommendation.product_id, "dual-format-deck")

        plan = route_request(
            {
                **self.request,
                "product": recommendation.product_id,
                "style": recommendation.style["selected"],
            }
        )
        self.assertEqual(plan.outputs, ("pptx", "html", "pdf"))
        self.assertEqual(plan.engines, ("ppt-master", "frontend-slides"))

    def test_editable_request_without_an_editable_requested_output_is_rejected(self) -> None:
        request = {**self.request, "outputs": ["html", "pdf"]}
        recommendation = recommend_product(request)
        self.assertEqual(recommendation.status, "FAIL")
        self.assertIsNone(recommendation.product_id)


if __name__ == "__main__":
    unittest.main()
