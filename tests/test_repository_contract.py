from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

try:
    from scripts.verify_examples import ExampleError, expected_example_paths, verify_all, verify_html
except ImportError:
    ExampleError = None
    expected_example_paths = None
    verify_all = None
    verify_html = None


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
    def test_third_party_notice_has_one_nonduplicated_version_source(self) -> None:
        notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8-sig")
        self.assertIn("presentation-studio/source-lock.json", notice)
        self.assertIsNone(
            re.search(r"\b[0-9a-f]{40}\b", notice),
            "Third-party notice duplicates drift-prone commit values from source-lock.json",
        )

    def test_operational_documentation_is_split_by_audience(self) -> None:
        architecture = ROOT / "docs" / "architecture.md"
        upstream_sync = ROOT / "docs" / "upstream-sync.md"
        self.assertTrue(architecture.is_file(), "Detailed architecture guide is missing")
        self.assertTrue(upstream_sync.is_file(), "Upstream synchronization guide is missing")
        architecture_text = architecture.read_text(encoding="utf-8-sig")
        sync_text = upstream_sync.read_text(encoding="utf-8-sig")
        for layer in range(20):
            self.assertIn(f"L{layer}", architecture_text)
        for term in (
            "repository_dispatch",
            "workflow_dispatch",
            "schedule",
            "latest-stable-release",
            "ahead_of_release",
            "fail-closed",
        ):
            with self.subTest(term=term):
                self.assertIn(term, sync_text)

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
            'cron: "17 * * * *"',
            "contents: write",
            "concurrency",
        ):
            with self.subTest(term=term):
                self.assertTrue(term in workflow, f"Sync workflow is missing: {term}")

    def test_sync_workflow_routes_verified_changes_through_a_pull_request(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "sync-upstreams.yml").read_text(
            encoding="utf-8"
        )

        for term in (
            "pull-requests: write",
            "cancel-in-progress: false",
            'sync_branch="automation/sync-stable-upstreams-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"',
            "--limit 100",
            "isCrossRepository",
            ".isCrossRepository == false",
            'test("^automation/sync-stable-upstreams-[0-9]+-[0-9]+$")',
            'git fetch origin "$sync_branch"',
            'git switch --create "$sync_branch" --track "origin/$sync_branch"',
            "git merge --no-edit origin/main",
            "SYNC_BRANCH: ${{ steps.sync_pr.outputs.branch }}",
            "EXISTING_PR: ${{ steps.sync_pr.outputs.url }}",
            'gh pr view "$existing_pr"',
            'git push --set-upstream origin "$sync_branch"',
            "gh pr create",
            "--base main",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertNotIn("          git push\n", workflow)
        self.assertNotIn("--force", workflow)
        self.assertNotIn('sync_branch="${{ steps.sync_pr.outputs.branch }}"', workflow)
        self.assertEqual(workflow.count("ensure_existing_pr_open"), 3)
        self.assertLess(workflow.index("Verify package and archive parity"), workflow.index("git push"))

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


class ExampleContractTests(unittest.TestCase):
    def test_exact_six_product_roster_exists(self) -> None:
        self.assertIsNotNone(expected_example_paths, "example verifier is missing")
        paths = expected_example_paths(ROOT)
        self.assertEqual(len(paths), 6)
        self.assertEqual(
            {path.relative_to(ROOT).as_posix() for path in paths},
            set(SIX_EXAMPLE_PATHS),
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"Example product is missing: {path}")

    def test_bilingual_products_pass_structural_acceptance(self) -> None:
        self.assertIsNotNone(verify_all, "example verifier is missing")
        summary = verify_all(ROOT)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(len(summary["products"]), 6)
        for product in summary["products"]:
            with self.subTest(path=product["path"]):
                self.assertEqual(product["status"], "PASS")
                self.assertEqual(product["pages"], 5)

    def test_chinese_html_rejects_english_content_with_a_zh_language_tag(self) -> None:
        self.assertIsNotNone(ExampleError, "example verifier is missing")
        self.assertIsNotNone(verify_html, "HTML example verifier is missing")
        source = (
            ROOT
            / "examples"
            / "bilingual-acceptance"
            / "en"
            / "presentation-acceptance-en.html"
        )
        original = source.read_text(encoding="utf-8-sig")
        mislabeled = original.replace('<html lang="en">', '<html lang="zh">', 1)
        self.assertNotEqual(mislabeled, original, "English fixture language tag was not replaced")

        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "presentation-acceptance-zh.html"
            candidate.write_text(mislabeled, encoding="utf-8")
            with self.assertRaises(ExampleError):
                verify_html(candidate, "zh")

    def test_english_html_rejects_chinese_content_with_an_en_language_tag(self) -> None:
        self.assertIsNotNone(ExampleError, "example verifier is missing")
        self.assertIsNotNone(verify_html, "HTML example verifier is missing")
        source = (
            ROOT
            / "examples"
            / "bilingual-acceptance"
            / "zh"
            / "presentation-acceptance-zh.html"
        )
        original = source.read_text(encoding="utf-8-sig")
        mislabeled = original.replace('<html lang="zh-CN">', '<html lang="en">', 1)
        self.assertNotEqual(mislabeled, original, "Chinese fixture language tag was not replaced")

        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "presentation-acceptance-en.html"
            candidate.write_text(mislabeled, encoding="utf-8")
            with self.assertRaises(ExampleError):
                verify_html(candidate, "en")


if __name__ == "__main__":
    unittest.main()
