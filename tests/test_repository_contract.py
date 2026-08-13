from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MAJOR_LAYER_MARKERS = (
    "智能理解与产品决策",
    "数据契约与引擎编排",
    "内容与视觉生产",
    "多格式原生生成",
    "渲染验收与自动修复",
    "安全、溯源与状态",
    "上游持续同步",
)

SIX_EXAMPLE_PATHS = (
    "examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx",
    "examples/bilingual-acceptance/zh/presentation-acceptance-zh.html",
    "examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf",
    "examples/bilingual-acceptance/en/presentation-acceptance-en.pptx",
    "examples/bilingual-acceptance/en/presentation-acceptance-en.html",
    "examples/bilingual-acceptance/en/presentation-acceptance-en.pdf",
)


class RepositoryContractTests(unittest.TestCase):
    def test_readme_shows_seven_major_layers_and_two_expandable_showcases(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        for marker in MAJOR_LAYER_MARKERS:
            with self.subTest(marker=marker):
                self.assertTrue(marker in text, f"README is missing major layer: {marker}")

        self.assertEqual(text.count("<details>"), 2)
        self.assertEqual(text.count("</details>"), 2)
        for relative_path in SIX_EXAMPLE_PATHS:
            with self.subTest(example=relative_path):
                self.assertTrue(
                    relative_path in text,
                    f"README is missing example link: {relative_path}",
                )

    def test_fast_path_preserves_complete_workflow_escalations(self) -> None:
        skill_path = ROOT / "presentation-studio" / "SKILL.md"
        fast_path_path = ROOT / "presentation-studio" / "references" / "fast-path.md"
        self.assertTrue(fast_path_path.is_file(), "Fast Path reference is missing")
        combined = skill_path.read_text(encoding="utf-8-sig") + fast_path_path.read_text(
            encoding="utf-8-sig"
        )
        for term in ("Fast Path", "exact data", "animation", "narration", "PASS"):
            with self.subTest(term=term):
                self.assertTrue(term in combined, f"Fast Path contract is missing: {term}")

    def test_sync_workflow_has_all_triggers_and_fail_closed_permissions(self) -> None:
        workflow_path = ROOT / ".github" / "workflows" / "sync-upstreams.yml"
        self.assertTrue(workflow_path.is_file(), "Upstream sync workflow is missing")
        workflow = workflow_path.read_text(encoding="utf-8")
        for term in (
            "repository_dispatch",
            "workflow_dispatch",
            "schedule",
            'cron: "2/5 * * * *"',
            "contents: write",
            "concurrency",
        ):
            with self.subTest(term=term):
                self.assertTrue(term in workflow, f"Sync workflow is missing: {term}")

    def test_source_lock_declares_stable_update_policy(self) -> None:
        lock_path = ROOT / "presentation-studio" / "source-lock.json"
        payload = json.loads(lock_path.read_text(encoding="utf-8-sig"))
        self.assertEqual(len(payload["sources"]), 4)
        for source in payload["sources"]:
            with self.subTest(source=source["name"]):
                self.assertIn("update_policy", source)
                self.assertIn("import_rules", source)
                self.assertIn("vendored_license_paths", source)
                self.assertEqual(source["update_policy"], "latest-stable-release")
                self.assertTrue(source["import_rules"])
                self.assertTrue(source["vendored_license_paths"])


if __name__ == "__main__":
    unittest.main()
