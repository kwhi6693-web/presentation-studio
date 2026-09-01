from __future__ import annotations

import unittest
from pathlib import Path

from scripts.upstream_sync import render_pr_body


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sync-upstreams.yml"
VALIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
AUTO_MERGE_WORKFLOW = ROOT / ".github" / "workflows" / "auto-merge-upstream.yml"
AUTO_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "auto-release.yml"
APP_TOKEN_PIN = "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0"


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

    def test_sync_uses_repository_scoped_github_app_identity_for_every_pr_mutation(self) -> None:
        for term in (
            "UPSTREAM_SYNC_APP_ID",
            "UPSTREAM_SYNC_APP_PRIVATE_KEY",
            APP_TOKEN_PIN,
            "permission-metadata: read",
            "permission-contents: write",
            "permission-pull-requests: write",
            "repositories: ${{ github.event.repository.name }}",
            "steps.app-token.outputs.token",
            "steps.app-token.outputs.app-slug",
            "Resolve trusted App bot commit identity",
            "users/${APP_SLUG}%5Bbot%5D",
            "users.noreply.github.com",
            "automation:upstream-sync",
            "release:patch",
            "release:minor",
            "release:major",
            "manual-review",
            "Verify trusted automation labels are provisioned",
            "Required repository label is missing or mismatched",
            "if length == 0 then {} elif length == 1 then .[0] else error",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.workflow)
        self.assertNotIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", self.workflow)
        self.assertIn("Trusted GitHub App ID is missing", self.workflow)
        self.assertIn("Trusted GitHub App private key is missing", self.workflow)

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

    def test_auto_merge_requeries_and_gates_live_pr_before_privileged_checkout(self) -> None:
        workflow = AUTO_MERGE_WORKFLOW.read_text(encoding="utf-8")
        for term in (
            "workflow_run:",
            "Validate package",
            "types: [completed]",
            "github.event.workflow_run.conclusion == 'success'",
            APP_TOKEN_PIN,
            "evaluate-pr",
            "expected-head-sha",
            "expected-app-login",
            "automation_policy.py verify-provenance",
            "upstream_sync.py verify-scope",
            "verify_repository_health.py",
            "expected_head_sha",
            "final-policy.outputs.action == 'update'",
            "final-policy.outputs.action == 'merge'",
            "policy command failed",
            "workflow validation is stale",
            "candidate_count",
            "Multiple live trusted automation PRs",
            "TRIGGERED_PULL_REQUESTS",
            "pull_requests association is missing",
            "workflow validation is stale",
            "Recheck main before privileged merge gates",
            "Capture the trusted policy evaluator before untrusted checkout",
            "TRUSTED_POLICY_SCRIPT",
            "Re-query live policy after a local gate race",
            "local-gate-recovery",
            "Update a trusted branch after a local gate behind race",
            "find -P presentation-studio -type l",
            "merge-race-update.json",
            "Merge became stale",
            'merge_method:"squash"',
            "manual-review",
            "reviewThreads",
            "pulls/${PR_NUMBER}/merge",
            "git/refs/heads/${ENCODED_BRANCH}",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertLess(workflow.index("evaluate-pr"), workflow.index("ref: ${{ steps.policy.outputs.head_sha }}"))
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("gh pr review", workflow)
        job_env = workflow[workflow.index("    env:") : workflow.index("    steps:")]
        self.assertNotIn("READ_TOKEN", job_env)
        self.assertNotIn("python scripts/automation_policy.py evaluate-pr", workflow)

    def test_auto_release_requires_successful_main_validation_and_rebuilds_clean_assets(self) -> None:
        workflow = AUTO_RELEASE_WORKFLOW.read_text(encoding="utf-8")
        for term in (
            "workflow_run:",
            "Validate package",
            "types: [completed]",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
            "concurrency:",
            "cancel-in-progress: false",
            "head_sha }}",
            "concurrent Release owns the current candidate version",
            "bounded retries",
            APP_TOKEN_PIN,
            "evaluate-release",
            "github.event.workflow_run.head_sha",
            "python scripts/verify_repository_health.py",
            "python -m unittest discover -s tests -v",
            "python scripts/verify_examples.py",
            "--compare-archive",
            "--compare-checksum",
            "verify_package.py",
            "--smoke",
            "presentation-studio.zip.sha256",
            "gh release create",
            "--target \"$RELEASE_SHA\"",
            "gh release view",
            ".assets | map(.name) | sort",
            "published_tag_sha",
            'repos/$GITHUB_REPOSITORY/commits/$RELEASE_VERSION',
            'gh release download "$RELEASE_VERSION"',
            'sha256sum "$readback_dir/presentation-studio.zip"',
            'sha256sum "$readback_dir/presentation-studio.zip.sha256"',
            "ARTIFACT_SIZE",
            "CHECKSUM_SIZE",
            ".size == $zip_size",
            "prerelease == true",
            "release-notes.md",
            "--method PATCH",
            "Existing release notes",
            "Verify an existing formal Release contract",
            "two-asset artifact contract",
            "untracked_or_modified",
            "git status --porcelain --untracked-files=all",
            "find -P presentation-studio -type l",
            "--evidence-url",
        ):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertGreaterEqual(workflow.count("verify_package.py"), 2)
        self.assertNotIn("dist/presentation-studio.zip", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("continue-on-error", workflow)


if __name__ == "__main__":
    unittest.main()
