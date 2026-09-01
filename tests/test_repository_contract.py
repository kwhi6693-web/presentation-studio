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

README_EXPECTATIONS = {
        "README.md": (
            "Agent-compatible",
            "Compatibility matrix",
            "Designed",
            "Validated",
            "Native PPTX",
            "Python 3.10–3.13",
            "Node.js 20.9+",
            "docs/dependencies.md",
            "NOT EXECUTED",
        "presentation-acceptance-en.pptx",
    ),
        "README.zh-CN.md": (
            "兼容性矩阵",
            "设计支持",
            "已验证",
            "原生 PPTX",
            "Python 3.10–3.13",
            "Node.js 20.9+",
            "docs/dependencies.md",
            "未执行",
        "presentation-acceptance-zh.pptx",
    ),
        "README.zh-TW.md": (
            "相容性矩陣",
            "設計支援",
            "已驗證",
            "原生 PPTX",
            "Python 3.10–3.13",
            "Node.js 20.9+",
            "docs/dependencies.md",
            "未執行",
        "presentation-acceptance-zh.pptx",
    ),
}

README_PATHS = tuple(README_EXPECTATIONS)

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
        dependencies = ROOT / "docs" / "dependencies.md"
        upstream_sync = ROOT / "docs" / "upstream-sync.md"
        self.assertTrue(architecture.is_file(), "Detailed architecture guide is missing")
        self.assertTrue(dependencies.is_file(), "Dependency contract is missing")
        self.assertTrue(upstream_sync.is_file(), "Upstream synchronization guide is missing")
        architecture_text = architecture.read_text(encoding="utf-8-sig")
        dependencies_text = dependencies.read_text(encoding="utf-8-sig")
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
        for term in (
            "RUNTIME DEPENDENCIES",
            "DEV/TEST DEPENDENCIES",
            "BUILD DEPENDENCIES",
            "SYSTEM DEPENDENCIES",
            "HOST/AGENT CAPABILITIES",
            "CI-ONLY DEPENDENCIES",
        ):
            with self.subTest(dependency_section=term):
                self.assertIn(term, dependencies_text)

    def test_autonomous_automation_maintainer_contract_is_documented(self) -> None:
        automation = ROOT / "docs" / "AUTOMATION.md"
        self.assertTrue(automation.is_file(), "Autonomous automation guide is missing")
        text = automation.read_text(encoding="utf-8-sig")
        for term in (
            "UPSTREAM_SYNC_APP_ID",
            "UPSTREAM_SYNC_APP_PRIVATE_KEY",
            "Metadata: read",
            "Contents: read and write",
            "Pull requests: read and write",
            "automation:upstream-sync",
            "release:patch",
            "manual-review",
            "workflow_run",
            "behind",
            "squash",
            "main validation",
            "semantic version",
            "presentation-studio.zip.sha256",
            "GitHub Actions evidence",
            "PR #21",
            "action_required",
            "rotate",
        ):
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_three_readmes_are_standalone_and_separate_designed_from_validated(self) -> None:
        for relative_path, terms in README_EXPECTATIONS.items():
            text = (ROOT / relative_path).read_text(encoding="utf-8-sig")
            with self.subTest(readme=relative_path):
                for term in terms:
                    self.assertIn(term, text, f"{relative_path} is missing contract term: {term}")
                self.assertEqual(text.count("<details>"), 2)
                self.assertEqual(text.count("</details>"), 2)
                for example_path in SIX_EXAMPLE_PATHS:
                    self.assertIn(example_path, text, f"{relative_path} is missing example link: {example_path}")
                self.assertNotRegex(text, r"(?i)\bBilingual Codex Skill\b|\bCodex-only\b")

    def test_readme_language_switches_cover_all_entry_points(self) -> None:
        for relative_path in README_PATHS:
            text = (ROOT / relative_path).read_text(encoding="utf-8-sig")
            for target in README_PATHS:
                with self.subTest(readme=relative_path, target=target):
                    self.assertIn(f"]({target})", text)

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
            "persist-credentials: false",
        ):
            with self.subTest(term=term):
                self.assertTrue(term in workflow, f"Sync workflow is missing: {term}")

    def test_sync_workflow_routes_each_verified_source_through_an_isolated_pull_request(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "sync-upstreams.yml").read_text(
            encoding="utf-8"
        )

        for term in (
            "fail-fast: false",
            "group: upstream-release-sync-${{ matrix.source }}",
            "- ppt-master",
            "- guizang-ppt-skill",
            "- frontend-slides",
            "- baoyu-skills",
            "pull-requests: write",
            "cancel-in-progress: false",
            "--limit 100",
            "isCrossRepository",
            ".isCrossRepository == false",
            'startswith(("automation/sync-" + $source + "-"))',
            'git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $auth_header" fetch origin "$sync_branch"',
            'git switch --create "$sync_branch" --track "origin/$sync_branch"',
            "git merge --no-edit origin/main",
            'sync_branch="automation/sync-${SOURCE}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"',
            "SYNC_BRANCH: ${{ steps.sync_pr.outputs.branch }}",
            "EXISTING_PR: ${{ steps.sync_pr.outputs.url }}",
            'gh pr view "$EXISTING_PR"',
            'gh pr edit "$EXISTING_PR"',
            'git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $auth_header" push --set-upstream origin "$SYNC_BRANCH"',
            "gh pr create",
            "--base main",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertIn('python scripts/upstream_sync.py sync --source "$SOURCE"', workflow)
        self.assertIn("verify-scope --source \"$SOURCE\"", workflow)
        self.assertNotIn("sync --all", workflow)
        self.assertNotIn("          git add -- \\\n            presentation-studio/engines", workflow)
        self.assertNotIn("dist/presentation-studio.zip", workflow)
        self.assertNotIn("checksums.sha256", workflow)
        self.assertNotIn("--force", workflow)
        self.assertEqual(workflow.count("gh pr edit"), 1)
        self.assertLess(
            workflow.index("Verify package and archive parity"),
            workflow.index('push --set-upstream origin "$SYNC_BRANCH"'),
        )

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
