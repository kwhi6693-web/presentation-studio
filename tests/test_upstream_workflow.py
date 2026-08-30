from __future__ import annotations

import unittest
from pathlib import Path

from scripts.upstream_sync import render_pr_body


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sync-upstreams.yml"
VALIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"


class UpstreamWorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_matrix_isolates_all_four_upstream_sources(self) -> None:
        matrix_start = self.workflow.index("matrix:")
        matrix_section = self.workflow[matrix_start : self.workflow.index("runs-on:", matrix_start)]
        for source in ("ppt-master", "guizang-ppt-skill", "frontend-slides", "baoyu-skills"):
            with self.subTest(source=source):
                self.assertIn(f"- {source}", matrix_section)
        self.assertIn("fail-fast: false", self.workflow)

    def test_concurrency_is_keyed_by_source_and_parallel_failures_are_isolated(self) -> None:
        self.assertIn("group: upstream-release-sync-${{ matrix.source }}", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)
        self.assertIn("fail-fast: false", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_workflow_requires_single_source_sync_and_exact_staging(self) -> None:
        self.assertIn('python scripts/upstream_sync.py sync --source "$SOURCE"', self.workflow)
        self.assertIn("verify-scope --source \"$SOURCE\"", self.workflow)
        self.assertIn(
            'git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $auth_header" fetch origin "$sync_branch"',
            self.workflow,
        )
        self.assertNotIn("sync --all", self.workflow)
        self.assertNotIn("git add -- \\\n            presentation-studio/engines", self.workflow)
        self.assertNotIn("dist/presentation-studio.zip", self.workflow)
        self.assertNotIn("checksums.sha256", self.workflow)

    def test_package_is_built_in_runner_temp_and_verified_before_push(self) -> None:
        self.assertIn("$RUNNER_TEMP", self.workflow)
        self.assertIn("build_package.py", self.workflow)
        self.assertIn("--archive", self.workflow)
        self.assertIn("verify_package.py", self.workflow)
        self.assertLess(
            self.workflow.index("verify_package.py"),
            self.workflow.index("push --set-upstream origin \"$SYNC_BRANCH\""),
        )
        self.assertIn("--compare-archive", self.workflow)
        self.assertIn("--compare-checksum", self.workflow)
        self.assertIn("--smoke", self.workflow)
        self.assertGreaterEqual(self.workflow.count("verify_package.py"), 2)

    def test_triggers_permissions_and_existing_pr_update_are_preserved(self) -> None:
        for term in (
            "repository_dispatch",
            "workflow_dispatch",
            "schedule",
            'cron: "17 * * * *"',
            "contents: write",
            "pull-requests: write",
            "gh pr list",
            "gh pr edit",
            "gh pr create",
            "--base main",
            "--title \"$PR_TITLE\"",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.workflow)

    def test_pr_body_contains_source_provenance_scope_and_verification_evidence(self) -> None:
        report = {
            "status": "PASS",
            "source": "ppt-master",
            "changed": True,
            "sources": [
                {
                    "name": "ppt-master",
                    "status": "update_available",
                    "locked_commit": "a" * 40,
                    "locked_release_tag": "v5.0.0",
                    "release": {
                        "tag": "v5.1.0",
                        "commit": "b" * 40,
                        "url": "https://github.com/hugohe3/ppt-master/releases/tag/v5.1.0",
                    },
                }
            ],
            "applied": [
                {
                    "source": "ppt-master",
                    "changed_paths": ["presentation-studio/engines/ppt-master"],
                    "preserved_paths": [],
                    "staging_paths": [
                        "presentation-studio/engines/ppt-master",
                        "presentation-studio/source-lock.json",
                        "presentation-studio/engines/manifest.json",
                    ],
                    "repository": "https://github.com/hugohe3/ppt-master.git",
                    "license": "MIT",
                }
            ],
        }

        body = render_pr_body(
            report,
            changed_file_count=3,
            additions=12,
            deletions=4,
            workflow_url="https://github.com/kwhi6693-web/presentation-studio/actions/runs/1",
        )

        for term in (
            "ppt-master",
            "v5.0.0",
            "v5.1.0",
            "a" * 40,
            "b" * 40,
            "3 files",
            "+12 / -4",
            "License: `MIT`",
            "source-lock.json",
            "https://github.com/kwhi6693-web/presentation-studio/actions/runs/1",
            "deterministic package",
        ):
            with self.subTest(term=term):
                self.assertIn(term, body)

    def test_validate_workflow_keeps_generated_package_outputs_transient(self) -> None:
        workflow = VALIDATE_WORKFLOW.read_text(encoding="utf-8")

        for term in (
            "${{ runner.temp }}",
            "schedule:",
            "ubuntu-latest",
            "windows-latest",
            'python-version: "3.10"',
            'python-version: "3.11"',
            'python-version: "3.12"',
            'python-version: "3.13"',
            "python -m venv --without-pip",
            "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0",
            "needs: checks",
            "name: verify",
            "build_package.py",
            "--compare-archive",
            "--compare-checksum",
            "verify_package.py",
            "--smoke",
            "git diff --exit-code -- dist/presentation-studio.zip checksums.sha256",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertNotIn("run: python scripts/build_package.py\n", workflow)

    def test_validate_checkout_does_not_persist_credentials(self) -> None:
        self.assertIn("persist-credentials: false", VALIDATE_WORKFLOW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
