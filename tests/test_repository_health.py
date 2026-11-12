from __future__ import annotations

import importlib.util
import json
import os
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


REVIEWED_ACTIONS_FIXTURE = {
    "actions/checkout": {
        "commit": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "release": "v7.0.1",
        "uses": 6
    },
    "actions/setup-python": {
        "commit": "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
        "release": "v7.1.0",
        "uses": 5
    },
    "actions/setup-node": {
        "commit": "949feb2413d6458794dcd2491c4babbbce0c15c1",
        "release": "v7.1.0",
        "uses": 3
    },
    "actions/upload-artifact": {
        "commit": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
        "release": "v7.0.2",
        "uses": 2
    },
    "actions/create-github-app-token": {
        "commit": "64ab729a6294000f5aa4a4bc0b73d1f32bc45510",
        "release": "v3.3.0",
        "uses": 3
    }
}


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
    def test_missing_language_readme_entry_point_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            (root / "README.zh-TW.md").unlink()

            issues = health.validate_repository(root)

            self.assertIn("missing required community file: README.zh-TW.md", issues)

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

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_missing_required_action_usage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            sync_workflow = root / ".github" / "workflows" / "sync-upstreams.yml"
            text = sync_workflow.read_text(encoding="utf-8")
            text = "\n".join(
                line for line in text.splitlines() if "actions/setup-python@" not in line
            )
            sync_workflow.write_text(text + "\n", encoding="utf-8")

            issues = health.validate_repository(root)

            self.assertIn(
                "reviewed action usage count mismatch: "
                "actions/setup-python expected 5 got 4",
                issues,
            )

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_wrong_action_sha_and_missing_release_comment_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            workflow = root / ".github" / "workflows" / "validate.yml"
            text = workflow.read_text(encoding="utf-8")
            text = text.replace(
                "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
                "0000000000000000000000000000000000000000 # v7.0.1",
            ).replace(
                "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0",
                "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
            )
            workflow.write_text(text, encoding="utf-8")

            issues = health.validate_repository(root)

            self.assertIn(
                "official action pin does not match reviewed release: "
                "actions/checkout@0000000000000000000000000000000000000000 "
                "# v7.0.1",
                issues,
            )
            self.assertIn(
                "official action pin does not match reviewed release: "
                "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
                issues,
            )

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_dependabot_second_ecosystem_and_wrong_schedule_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            dependabot = root / ".github" / "dependabot.yml"
            text = dependabot.read_text(encoding="utf-8").replace(
                'interval: "monthly"', 'interval: "daily"'
            ).replace("groups:", "ungrouped:")
            text += '  - package-ecosystem: "npm"\n    directory: "/"\n'
            dependabot.write_text(text, encoding="utf-8")

            issues = health.validate_repository(root)

            self.assertIn("Dependabot may update github-actions only", issues)
            self.assertIn(
                "Dependabot github-actions interval must be monthly", issues
            )
            self.assertIn("Dependabot github-actions updates must be grouped", issues)

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_issue_form_without_validations_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            issue_form = root / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
            issue_form.write_text(
                "name: Bug\n"
                "description: Details\n"
                "body:\n"
                "  - type: textarea\n"
                "    id: details\n",
                encoding="utf-8",
            )

            issues = health.validate_repository(root)

            self.assertIn(
                "issue form has no validations: "
                ".github/ISSUE_TEMPLATE/bug_report.yml",
                issues,
            )

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_undeclared_repository_python_import_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            (root / "scripts").mkdir()
            (root / "scripts" / "unexpected.py").write_text(
                "import definitely_not_a_declared_dependency\n", encoding="utf-8"
            )

            issues = health.validate_repository(root)

            self.assertIn(
                "undeclared Python import: definitely_not_a_declared_dependency in scripts/unexpected.py",
                issues,
            )

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_repository_hygiene_rejects_cache_and_private_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "bad.pyc").write_bytes(b"cache")
            private_path = f"/home/{health.PRIVATE_USER}/Documents/private.md"
            (root / "notes.md").write_text(
                f"machine path: {private_path}\n",
                encoding="utf-8",
            )

            issues = health.validate_repository(root)

            self.assertIn("repository hygiene forbids generated/cache path: __pycache__", issues)
            self.assertIn("repository hygiene found a private absolute path: notes.md", issues)

    @unittest.skipIf(health is None, "repository health verifier is missing")
    def test_repository_hygiene_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_complete_repository(root)
            target = root / "outside.txt"
            target.write_text("outside\n", encoding="utf-8")
            link = root / "linked.txt"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable in this test environment")

            issues = health.validate_repository(root)

            self.assertIn("repository hygiene forbids symbolic link: linked.txt", issues)

    def _write_complete_repository(self, root: Path) -> None:
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        (root / "docs" / "dependencies.md").write_text(
            "# Dependencies\n"
            "## RUNTIME DEPENDENCIES\n"
            "## DEV/TEST DEPENDENCIES\n"
            "## BUILD DEPENDENCIES\n"
            "## SYSTEM DEPENDENCIES\n"
            "## HOST/AGENT CAPABILITIES\n"
            "## CI-ONLY DEPENDENCIES\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "[English](README.md)\n"
            "[简体中文](README.zh-CN.md)\n"
            "[繁體中文](README.zh-TW.md)\n"
            "[Contributing](CONTRIBUTING.md)\n"
            "[Security](SECURITY.md)\n"
            "[Guide](docs/guide.md#start)\n"
            "[Release](https://example.com/release)\n",
            encoding="utf-8",
        )
        (root / "README.zh-CN.md").write_text(
            "[English](README.md)\n[简体中文](README.zh-CN.md)\n[繁體中文](README.zh-TW.md)\n",
            encoding="utf-8",
        )
        (root / "README.zh-TW.md").write_text(
            "[English](README.md)\n[简体中文](README.zh-CN.md)\n[繁體中文](README.zh-TW.md)\n",
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
        (root / ".github" / "reviewed-actions.json").write_text(
            json.dumps(REVIEWED_ACTIONS_FIXTURE), encoding="utf-8"
        )
        (workflows / "validate.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n"
            "  - uses: actions/setup-node@"
            "949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n",
            encoding="utf-8",
        )
        (workflows / "sync-upstreams.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n"
            "  - uses: actions/setup-node@"
            "949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n"
            "  - uses: actions/upload-artifact@"
            "cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2\n"
            "  - uses: actions/create-github-app-token@"
            "64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0\n",
            encoding="utf-8",
        )
        (workflows / "auto-merge-upstream.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n"
            "  - uses: actions/create-github-app-token@"
            "64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0\n",
            encoding="utf-8",
        )
        (workflows / "auto-release.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n"
            "  - uses: actions/setup-node@"
            "949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0\n"
            "  - uses: actions/create-github-app-token@"
            "64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0\n",
            encoding="utf-8",
        )
        (workflows / "portability-pilot.yml").write_text(
            "steps:\n"
            "  - uses: actions/checkout@"
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "  - uses: actions/setup-python@"
            "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n"
            "  - uses: actions/upload-artifact@"
            "cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2\n",
            encoding="utf-8",
        )
        (root / ".github" / "dependabot.yml").write_text(
            "version: 2\n"
            "updates:\n"
            '  - package-ecosystem: "github-actions"\n'
            '    directory: "/"\n'
            "    schedule:\n"
            '      interval: "monthly"\n'
            "    open-pull-requests-limit: 3\n"
            "    groups:\n"
            "      github-actions:\n"
            "        patterns:\n"
            '          - "*"\n'
            "    commit-message:\n"
            '      prefix: "ci"\n',
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
