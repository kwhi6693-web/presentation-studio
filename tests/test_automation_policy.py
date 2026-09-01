from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from scripts.automation_policy import (
    PolicyError,
    PullRequestSnapshot,
    ReleaseRecord,
    SemVer,
    TagRecord,
    evaluate_main_release_candidate,
    evaluate_live_pull_request,
    evaluate_trusted_pull_request,
    fetch_pull_request_snapshot,
    plan_semver_release,
    render_release_notes,
    validate_provenance_payloads,
)


REPOSITORY = "kwhi6693-web/presentation-studio"
APP_LOGIN = "presentation-studio-upstream[bot]"
HEAD_SHA = "a" * 40


def trusted_snapshot(**overrides) -> PullRequestSnapshot:
    values = {
        "number": 42,
        "state": "open",
        "base_ref": "main",
        "base_repository": REPOSITORY,
        "head_ref": "automation/sync-ppt-master-123-1",
        "head_repository": REPOSITORY,
        "head_sha": HEAD_SHA,
        "author_login": APP_LOGIN,
        "draft": False,
        "labels": frozenset({"automation:upstream-sync", "release:patch"}),
        "changed_paths": (
            "presentation-studio/engines/ppt-master/SKILL.md",
            "presentation-studio/source-lock.json",
            "presentation-studio/engines/manifest.json",
        ),
        "check_runs": (("verify", "success"),),
        "mergeable": True,
        "mergeable_state": "clean",
        "reviews": (),
        "unresolved_review_threads": 0,
        "merged": False,
        "merge_commit_sha": None,
        "title": "chore(upstream): update ppt-master to v6.1.0",
    }
    values.update(overrides)
    return PullRequestSnapshot(**values)


class TrustedPullRequestPolicyTests(unittest.TestCase):
    def evaluate(self, snapshot: PullRequestSnapshot):
        return evaluate_trusted_pull_request(
            snapshot,
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
        )

    def test_trusted_same_repository_upstream_pr_with_successful_checks_can_merge(self) -> None:
        decision = self.evaluate(trusted_snapshot())

        self.assertEqual(decision.action, "merge")
        self.assertEqual(decision.source, "ppt-master")
        self.assertEqual(decision.release_level, "patch")

    def test_fork_pr_is_ignored(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(head_repository="someone/fork", author_login="someone")
        )

        self.assertEqual(decision.action, "ignore")
        self.assertIn("same repository", decision.reason)

    def test_human_pr_is_ignored(self) -> None:
        decision = self.evaluate(trusted_snapshot(author_login="kwhi6693-web"))

        self.assertEqual(decision.action, "ignore")
        self.assertIn("GitHub App", decision.reason)

    def test_wrong_branch_prefix_is_ignored(self) -> None:
        decision = self.evaluate(trusted_snapshot(head_ref="feature/not-automation"))

        self.assertEqual(decision.action, "ignore")
        self.assertIn("branch", decision.reason)

    def test_wrong_base_is_ignored(self) -> None:
        decision = self.evaluate(trusted_snapshot(base_ref="release"))

        self.assertEqual(decision.action, "ignore")
        self.assertIn("base", decision.reason)

    def test_missing_automation_label_blocks_a_genuine_app_pr(self) -> None:
        decision = self.evaluate(trusted_snapshot(labels=frozenset({"release:patch"})))

        self.assertEqual(decision.action, "block")
        self.assertIn("automation:upstream-sync", decision.reason)

    def test_non_app_commit_on_app_branch_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(
                commit_identities=((APP_LOGIN, APP_LOGIN), ("kwhi6693-web", "kwhi6693-web"))
            )
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("commit not authored", decision.reason)

    def test_failed_verify_blocks_merge(self) -> None:
        decision = self.evaluate(trusted_snapshot(check_runs=(("verify", "failure"),)))

        self.assertEqual(decision.action, "block")
        self.assertIn("verify", decision.reason)

    def test_duplicate_verify_runs_fail_closed_if_any_is_not_successful(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(check_runs=(("verify", "failure"), ("verify", "success")))
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("verify", decision.reason)

    def test_stale_workflow_run_is_ignored_when_live_head_has_advanced(self) -> None:
        decision = evaluate_live_pull_request(
            trusted_snapshot(head_sha="b" * 40),
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
            expected_head_sha=HEAD_SHA,
        )

        self.assertEqual(decision.action, "ignore")
        self.assertIn("stale", decision.reason)

    def test_merge_conflict_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(mergeable=False, mergeable_state="dirty")
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("conflict", decision.reason)

    def test_behind_branch_is_updated_instead_of_merged(self) -> None:
        decision = self.evaluate(trusted_snapshot(mergeable_state="behind"))

        self.assertEqual(decision.action, "update")
        self.assertEqual(decision.head_sha, HEAD_SHA)

    def test_protected_workflow_modification_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(changed_paths=(".github/workflows/validate.yml",))
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("protected", decision.reason)

    def test_unexpected_source_path_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(changed_paths=("presentation-studio/engines/baoyu/SKILL.md",))
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("managed paths", decision.reason)

    def test_preserved_adapter_path_blocks_merge_even_inside_an_imported_directory(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(
                head_ref="automation/sync-guizang-ppt-skill-123-1",
                changed_paths=(
                    "presentation-studio/engines/guizang/scripts/validate-swiss-deck.mjs",
                ),
            )
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("preserved adapter", decision.reason)

    def test_renamed_protected_path_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(
                changed_paths=(
                    "presentation-studio/engines/ppt-master/SKILL.md",
                    ".github/workflows/auto-release.yml",
                )
            )
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("protected", decision.reason)

    def test_unresolved_review_thread_blocks_merge(self) -> None:
        decision = self.evaluate(trusted_snapshot(unresolved_review_threads=1))

        self.assertEqual(decision.action, "block")
        self.assertIn("unresolved review", decision.reason)

    def test_requested_changes_blocks_merge(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(reviews=(("maintainer", "CHANGES_REQUESTED", "2026-09-01T01:00:00Z"),))
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("requested changes", decision.reason)

    def test_later_approval_clears_an_older_change_request_from_same_reviewer(self) -> None:
        decision = self.evaluate(
            trusted_snapshot(
                reviews=(
                    ("maintainer", "CHANGES_REQUESTED", "2026-09-01T01:00:00Z"),
                    ("maintainer", "APPROVED", "2026-09-01T02:00:00Z"),
                )
            )
        )

        self.assertEqual(decision.action, "merge")


class ProvenancePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_lock = {
            "sources": [
                {
                    "name": "ppt-master",
                    "repository": "https://github.com/hugohe3/ppt-master.git",
                    "commit": "1" * 40,
                    "release_commit": "1" * 40,
                    "release_tag": "v6.0.0",
                    "release_url": "https://github.com/hugohe3/ppt-master/releases/tag/v6.0.0",
                    "update_policy": "latest-stable-release",
                },
                {"name": "baoyu-skills", "commit": "2" * 40},
            ]
        }
        self.head_lock = {
            "sources": [
                {
                    "name": "ppt-master",
                    "repository": "https://github.com/hugohe3/ppt-master.git",
                    "commit": "3" * 40,
                    "release_commit": "3" * 40,
                    "release_tag": "v6.1.0",
                    "release_url": "https://github.com/hugohe3/ppt-master/releases/tag/v6.1.0",
                    "update_policy": "latest-stable-release",
                },
                {"name": "baoyu-skills", "commit": "2" * 40},
            ]
        }
        self.base_manifest = {
            "ppt-master": {"source_name": "ppt-master", "commit": "1" * 40, "release_tag": "v6.0.0"},
            "baoyu": {"source_name": "baoyu-skills", "commit": "2" * 40, "release_tag": "v2.0.0"},
        }
        self.head_manifest = {
            "ppt-master": {"source_name": "ppt-master", "commit": "3" * 40, "release_tag": "v6.1.0"},
            "baoyu": {"source_name": "baoyu-skills", "commit": "2" * 40, "release_tag": "v2.0.0"},
        }

    def test_selected_source_lock_and_manifest_provenance_pass(self) -> None:
        evidence = validate_provenance_payloads(
            "ppt-master",
            self.base_lock,
            self.head_lock,
            self.base_manifest,
            self.head_manifest,
        )

        self.assertEqual(evidence["old_tag"], "v6.0.0")
        self.assertEqual(evidence["new_tag"], "v6.1.0")
        self.assertEqual(evidence["new_commit"], "3" * 40)

    def test_other_source_provenance_change_fails(self) -> None:
        changed = {
            **self.head_lock,
            "sources": [self.head_lock["sources"][0], {"name": "baoyu-skills", "commit": "4" * 40}],
        }

        with self.assertRaisesRegex(PolicyError, "another source"):
            validate_provenance_payloads(
                "ppt-master", self.base_lock, changed, self.base_manifest, self.head_manifest
            )

    def test_manifest_mismatch_fails(self) -> None:
        mismatched = {
            **self.head_manifest,
            "ppt-master": {**self.head_manifest["ppt-master"], "commit": "4" * 40},
        }

        with self.assertRaisesRegex(PolicyError, "manifest"):
            validate_provenance_payloads(
                "ppt-master", self.base_lock, self.head_lock, self.base_manifest, mismatched
            )

    def test_selected_source_repository_must_match_configured_upstream(self) -> None:
        changed_source = {
            **self.head_lock["sources"][0],
            "repository": "https://github.com/attacker/repository.git",
            "release_url": "https://github.com/attacker/repository/releases/tag/v6.1.0",
        }
        changed_lock = {**self.head_lock, "sources": [changed_source, self.head_lock["sources"][1]]}

        with self.assertRaisesRegex(PolicyError, "configured upstream"):
            validate_provenance_payloads(
                "ppt-master", self.base_lock, changed_lock, self.base_manifest, self.head_manifest
            )

    def test_source_lock_invariant_fields_cannot_be_tampered(self) -> None:
        tampered_source = {
            **self.head_lock["sources"][0],
            "branch": "attacker",
            "license": "GPL-999",
            "import_rules": [{"source": "evil", "destination": "engines/ppt-master", "mode": "replace"}],
            "dependencies": ["malicious-package"],
        }
        tampered_lock = {**self.head_lock, "sources": [tampered_source, self.head_lock["sources"][1]]}

        with self.assertRaisesRegex(PolicyError, "invariant changed"):
            validate_provenance_payloads(
                "ppt-master", self.base_lock, tampered_lock, self.base_manifest, self.head_manifest
            )

    def test_selected_manifest_invariant_fields_cannot_be_tampered(self) -> None:
        tampered_manifest = {
            **self.head_manifest,
            "ppt-master": {**self.head_manifest["ppt-master"], "role": "attacker"},
        }

        with self.assertRaisesRegex(PolicyError, "manifest invariant"):
            validate_provenance_payloads(
                "ppt-master", self.base_lock, self.head_lock, self.base_manifest, tampered_manifest
            )

    def test_source_lock_top_level_schema_and_import_date_are_invariants(self) -> None:
        base_lock = {**self.base_lock, "schema_version": 2, "import_date": "2026-08-11"}
        head_lock = {**self.head_lock, "schema_version": 2, "import_date": "2026-08-11"}
        with self.assertRaisesRegex(PolicyError, "top-level invariant"):
            validate_provenance_payloads(
                "ppt-master",
                base_lock,
                {**head_lock, "schema_version": 3},
                self.base_manifest,
                self.head_manifest,
            )
        with self.assertRaisesRegex(PolicyError, "top-level invariant"):
            validate_provenance_payloads(
                "ppt-master",
                base_lock,
                {**head_lock, "import_date": "2026-08-12"},
                self.base_manifest,
                self.head_manifest,
            )

    def test_engine_manifest_schema_version_is_stable_and_supported(self) -> None:
        base_manifest = {**self.base_manifest, "schema_version": 1}
        head_manifest = {**self.head_manifest, "schema_version": 1}
        with self.assertRaisesRegex(PolicyError, "schema_version"):
            validate_provenance_payloads(
                "ppt-master",
                self.base_lock,
                self.head_lock,
                base_manifest,
                {**head_manifest, "schema_version": 2},
            )


class ReleasePolicyTests(unittest.TestCase):
    def test_semver_patch_minor_and_major_bumps_are_aware(self) -> None:
        version = SemVer.parse("v1.2.1")

        self.assertEqual(str(version.bump("patch")), "v1.2.2")
        self.assertEqual(str(version.bump("minor")), "v1.3.0")
        self.assertEqual(str(version.bump("major")), "v2.0.0")

    def test_patch_release_is_planned_from_highest_formal_semver(self) -> None:
        plan = plan_semver_release(
            commit_sha=HEAD_SHA,
            release_level="patch",
            releases=(
                ReleaseRecord("v1.2.0", "1" * 40, False, False),
                ReleaseRecord("nightly", "2" * 40, False, False),
                ReleaseRecord("v1.2.1", "3" * 40, False, False),
            ),
            tags=(TagRecord("v1.2.1", "3" * 40),),
        )

        self.assertEqual(plan.state, "new")
        self.assertEqual(plan.version, "v1.2.2")

    def test_release_tag_collision_fails_closed(self) -> None:
        with self.assertRaisesRegex(PolicyError, "collision"):
            plan_semver_release(
                commit_sha=HEAD_SHA,
                release_level="patch",
                releases=(ReleaseRecord("v1.2.1", "3" * 40, False, False),),
                tags=(
                    TagRecord("v1.2.1", "3" * 40),
                    TagRecord("v1.2.2", "4" * 40),
                ),
            )

    def test_existing_release_for_commit_is_idempotent(self) -> None:
        plan = plan_semver_release(
            commit_sha=HEAD_SHA,
            release_level="patch",
            releases=(ReleaseRecord("v1.2.2", HEAD_SHA, False, False),),
            tags=(TagRecord("v1.2.2", HEAD_SHA),),
        )

        self.assertEqual(plan.state, "complete")
        self.assertEqual(plan.version, "v1.2.2")

    def test_matching_draft_release_is_resumed_without_allocating_another_version(self) -> None:
        plan = plan_semver_release(
            commit_sha=HEAD_SHA,
            release_level="patch",
            releases=(
                ReleaseRecord("v1.2.1", "3" * 40, False, False),
                ReleaseRecord("v1.2.2", HEAD_SHA, True, False),
            ),
            tags=(
                TagRecord("v1.2.1", "3" * 40),
                TagRecord("v1.2.2", HEAD_SHA),
            ),
        )

        self.assertEqual(plan.state, "resume")
        self.assertEqual(plan.version, "v1.2.2")

    def test_matching_prerelease_is_resumed_for_formal_publication(self) -> None:
        plan = plan_semver_release(
            commit_sha=HEAD_SHA,
            release_level="patch",
            releases=(
                ReleaseRecord("v1.2.1", "3" * 40, False, False),
                ReleaseRecord("v1.2.2", HEAD_SHA, False, True),
            ),
            tags=(
                TagRecord("v1.2.1", "3" * 40),
                TagRecord("v1.2.2", HEAD_SHA),
            ),
        )

        self.assertEqual(plan.state, "resume")
        self.assertEqual(plan.version, "v1.2.2")

    def test_failed_main_validation_is_ignored(self) -> None:
        decision = evaluate_main_release_candidate(
            conclusion="failure",
            event="push",
            head_branch="main",
            head_sha=HEAD_SHA,
            pull_requests=(trusted_snapshot(merged=True, merge_commit_sha=HEAD_SHA),),
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
        )

        self.assertEqual(decision.action, "ignore")
        self.assertIn("successful main validation", decision.reason)

    def test_successful_main_validation_of_trusted_merged_pr_can_release(self) -> None:
        decision = evaluate_main_release_candidate(
            conclusion="success",
            event="push",
            head_branch="main",
            head_sha=HEAD_SHA,
            pull_requests=(trusted_snapshot(merged=True, merge_commit_sha=HEAD_SHA),),
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
        )

        self.assertEqual(decision.action, "release")
        self.assertEqual(decision.release_level, "patch")

    def test_draft_trusted_pr_cannot_be_a_main_release_candidate(self) -> None:
        decision = evaluate_main_release_candidate(
            conclusion="success",
            event="push",
            head_branch="main",
            head_sha=HEAD_SHA,
            pull_requests=(trusted_snapshot(draft=True, merged=True, merge_commit_sha=HEAD_SHA),),
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("draft", decision.reason)

    def test_ordinary_main_commit_does_not_release(self) -> None:
        decision = evaluate_main_release_candidate(
            conclusion="success",
            event="push",
            head_branch="main",
            head_sha=HEAD_SHA,
            pull_requests=(),
            repository=REPOSITORY,
            expected_app_login=APP_LOGIN,
        )

        self.assertEqual(decision.action, "ignore")

    def test_release_notes_include_version_pr_provenance_checksum_and_evidence(self) -> None:
        notes = render_release_notes(
            version="v1.2.2",
            pr_number=42,
            pr_title="chore(upstream): update ppt-master to v6.1.0",
            provenance={
                "source": "ppt-master",
                "repository": "https://github.com/hugohe3/ppt-master.git",
                "old_tag": "v6.0.0",
                "old_commit": "1" * 40,
                "new_tag": "v6.1.0",
                "new_commit": "2" * 40,
                "release_url": "https://github.com/hugohe3/ppt-master/releases/tag/v6.1.0",
            },
            artifact_sha256="3" * 64,
            evidence_url="https://github.com/kwhi6693-web/presentation-studio/actions/runs/99",
        )

        for term in (
            "Presentation Studio v1.2.2",
            "#42",
            "ppt-master",
            "v6.0.0",
            "v6.1.0",
            "3" * 64,
            "GitHub Actions evidence",
        ):
            with self.subTest(term=term):
                self.assertIn(term, notes)


class AutomationPolicyCliTests(unittest.TestCase):
    def test_direct_script_entrypoint_loads_repository_modules(self) -> None:
        root = Path(__file__).resolve().parents[1]

        process = subprocess.run(
            [sys.executable, str(root / "scripts" / "automation_policy.py"), "--help"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("evaluate-pr", process.stdout)


class PullRequestApiSnapshotTests(unittest.TestCase):
    class FakeApi:
        def __init__(self, *, graphql_errors: bool = False) -> None:
            self.graphql_errors = graphql_errors

        def request(self, path: str, **kwargs):
            if path == f"/repos/{REPOSITORY}/pulls/42":
                return {
                    "number": 42,
                    "state": "open",
                    "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
                    "head": {
                        "ref": "automation/sync-ppt-master-123-1",
                        "repo": {"full_name": REPOSITORY},
                        "sha": HEAD_SHA,
                    },
                    "changed_files": 1,
                    "commits": 1,
                    "user": {"login": APP_LOGIN},
                    "draft": False,
                    "labels": [],
                    "mergeable": True,
                    "mergeable_state": "clean",
                    "merged": False,
                    "merge_commit_sha": None,
                    "title": "test",
                }
            if path == "/graphql":
                if self.graphql_errors:
                    return {"errors": [{"message": "partial failure"}]}
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [],
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    }
                }
            if path.endswith("/check-runs"):
                return {"check_runs": [{"name": "verify", "conclusion": "success"}]}
            raise AssertionError(f"unexpected API path: {path}")

        def paginate(self, path: str):
            if path.endswith("/files"):
                return [
                    {
                        "filename": "presentation-studio/engines/ppt-master/SKILL.md",
                        "previous_filename": ".github/workflows/validate.yml",
                    }
                ]
            if path.endswith("/commits"):
                return [
                    {
                        "author": {"login": APP_LOGIN},
                        "committer": {"login": APP_LOGIN},
                    }
                ]
            if path.endswith("/reviews"):
                return []
            raise AssertionError(f"unexpected paginated API path: {path}")

    def test_snapshot_includes_previous_filename_for_rename_protection(self) -> None:
        api = self.FakeApi()
        # The pull request endpoint is intentionally handled by a small wrapper
        # so the fake can keep request() focused on the check/GraphQL responses.
        original_request = api.request

        def request(path: str, **kwargs):
            if path == "/repos/kwhi6693-web/presentation-studio/pulls/42":
                return {
                    "number": 42,
                    "state": "open",
                    "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
                    "head": {
                        "ref": "automation/sync-ppt-master-123-1",
                        "repo": {"full_name": REPOSITORY},
                        "sha": HEAD_SHA,
                    },
                    "changed_files": 1,
                    "commits": 1,
                    "user": {"login": APP_LOGIN},
                    "draft": False,
                    "labels": [],
                    "mergeable": True,
                    "mergeable_state": "clean",
                    "merged": False,
                    "merge_commit_sha": None,
                    "title": "test",
                }
            return original_request(path, **kwargs)

        api.request = request
        snapshot = fetch_pull_request_snapshot(api, REPOSITORY, 42)

        self.assertIn(".github/workflows/validate.yml", snapshot.changed_paths)

    def test_snapshot_rejects_truncated_pull_request_file_lists(self) -> None:
        api = self.FakeApi()
        original_request = api.request

        def request(path: str, **kwargs):
            payload = original_request(path, **kwargs)
            if path == f"/repos/{REPOSITORY}/pulls/42":
                payload = {**payload, "changed_files": 3001}
            return payload

        api.request = request
        with self.assertRaisesRegex(PolicyError, "safety cap"):
            fetch_pull_request_snapshot(api, REPOSITORY, 42)

    def test_snapshot_rejects_incomplete_pull_request_file_lists(self) -> None:
        api = self.FakeApi()
        original_request = api.request
        original_paginate = api.paginate

        def request(path: str, **kwargs):
            payload = original_request(path, **kwargs)
            if path == f"/repos/{REPOSITORY}/pulls/42":
                payload = {**payload, "changed_files": 2}
            return payload

        def paginate(path: str):
            if path.endswith("/files"):
                return []
            return original_paginate(path)

        api.request = request
        api.paginate = paginate
        with self.assertRaisesRegex(PolicyError, "files are incomplete"):
            fetch_pull_request_snapshot(api, REPOSITORY, 42)

    def test_graphql_partial_error_fails_closed(self) -> None:
        from scripts.automation_policy import _review_thread_count

        with self.assertRaisesRegex(PolicyError, "GraphQL"):
            _review_thread_count(self.FakeApi(graphql_errors=True), REPOSITORY, 42)


if __name__ == "__main__":
    unittest.main()
