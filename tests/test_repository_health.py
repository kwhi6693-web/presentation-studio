from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEALTH_SCRIPT = ROOT / "scripts" / "verify_repository_health.py"

health = None
if HEALTH_SCRIPT.is_file():
    spec = importlib.util.spec_from_file_location("verify_repository_health", HEALTH_SCRIPT)
    if spec is not None and spec.loader is not None:
        health = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(health)


class RepositoryHealthVerifierTests(unittest.TestCase):
    def test_repository_health_verifier_exists(self) -> None:
        self.assertIsNotNone(health, "repository health verifier is missing")

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_complete_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)

            self.assertEqual(health.validate_repository(root), [])

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_missing_local_readme_target_and_community_file_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            (root / "SECURITY.md").unlink()
            (root / "README.md").write_text(
                "[Missing](docs/missing.md)\n", encoding="utf-8"
            )

            issues = health.validate_repository(root)

            self.assertIn("missing required community file: SECURITY.md", issues)
            self.assertIn(
                "README local link target does not exist: docs/missing.md", issues
            )

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_malformed_issue_form_floating_action_and_npm_dependabot_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            issue_form = root / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
            workflow = root / ".github" / "workflows" / "validate.yml"
            dependabot = root / ".github" / "dependabot.yml"
            issue_form.write_text("name: Bug\nbody: []\n", encoding="utf-8")
            workflow.write_text(
                "steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8"
            )
            dependabot.write_text(
                'version: 2\nupdates:\n  - package-ecosystem: "npm"\n',
                encoding="utf-8",
            )

            issues = health.validate_repository(root)

            self.assertIn(
                "issue form missing top-level description: "
                ".github/ISSUE_TEMPLATE/bug_report.yml",
                issues,
            )
            self.assertIn(
                "official action is not pinned to a full reviewed commit: "
                "actions/checkout@v4",
                issues,
            )
            self.assertIn("Dependabot may update github-actions only", issues)

    def _write_complete_repository(self, root: Path) -> None:
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (root / "README.md").write_text(
            "[Contributing](CONTRIBUTING.md)\n"
            "[Security](SECURITY.md)\n"
            "[Guide](docs/guide.md#start)\n"
            "[Release](https://example.com/release)\n",
            encoding="utf-8",
        )

        for relative_path in (
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            ".github/CODEOWNERS",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/config.yml",
        ):
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("present\n", encoding="utf-8")

        issue_form_text = (
            "name: Report\n"
            "description: Structured report\n"
            "title: \"[Report]: \"\n"
            "labels: []\n"
            "body:\n"
            "  - type: textarea\n"
            "    id: details\n"
            "    attributes:\n"
            "      label: Details\n"
            "    validations:\n"
            "      required: true\n"
        )
        for name in ("bug_report.yml", "feature_request.yml", "upstream_sync.yml"):
            (root / ".github" / "ISSUE_TEMPLATE" / name).write_text(
                issue_form_text, encoding="utf-8"
            )

        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "validate.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0\n",
            encoding="utf-8",
        )
        (workflows / "sync-upstreams.yml").write_text(
            "steps:\n"
            "  - uses: actions/upload-artifact@"
            "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1\n",
            encoding="utf-8",
        )
        (root / ".github" / "dependabot.yml").write_text(
            "version: 2\n"
            "updates:\n"
            '  - package-ecosystem: "github-actions"\n'
            '    directory: "/"\n'
            "    schedule:\n"
            '      interval: "weekly"\n'
            "    open-pull-requests-limit: 3\n"
            "    commit-message:\n"
            '      prefix: "ci"\n',
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
