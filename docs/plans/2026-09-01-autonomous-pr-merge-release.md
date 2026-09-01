# Autonomous PR → Merge → Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed GitHub App–authenticated upstream PR, merge, main-validation, and semver Release pipeline without weakening the active main ruleset.

**Architecture:** A repository-owned Python policy engine separates deterministic policy decisions from GitHub API transport. Three pinned workflows use a short-lived repository-scoped App token for writes, while privileged `workflow_run` jobs classify live API state before checking out any candidate SHA.

**Tech Stack:** Python 3.10+ standard library, GitHub Actions, GitHub REST/GraphQL APIs, GitHub CLI, existing deterministic package scripts.

**Spec:** `docs/designs/2026-09-01-autonomous-pr-merge-release.md`

## Global Constraints

- Preserve active Ruleset `21126467`, strict required `verify`, and PR-only main changes.
- Never use `pull_request_target`, direct main push, auto-approval, force push, secrets in fork PRs, or unpinned Actions.
- App permissions are limited to Metadata read, Contents read/write, and Pull requests read/write.
- Every privileged mutation is followed by destination-state readback.
- GitHub App bootstrap is the only permitted owner-only blocker.

---

### Task 1: Trusted automation policy engine

**Files:**
- Create: `scripts/automation_policy.py`
- Create: `tests/test_automation_policy.py`

**Interfaces:**
- Produces `PullRequestSnapshot`, `PolicyDecision`, `ReleasePlan`,
  `evaluate_trusted_pull_request(...)`, `plan_semver_release(...)`, and CLI commands
  `evaluate-pr`, `evaluate-release`, and `release-notes`.
- Consumes the existing `load_source_configs`, `source_managed_paths`, and source-lock /
  engine-manifest contracts.

- [ ] Write table-driven failing tests for all PASS/FAIL/UPDATE/IGNORE cases named in
  the design, using literal expected decisions.
- [ ] Run `python -m unittest tests.test_automation_policy -v` and confirm failures are
  caused by the absent policy module.
- [ ] Implement strict semver parsing/bumping, source extraction from branch names,
  path classification, review/check evaluation, provenance comparison, release
  association, collision handling, API redaction, and JSON CLI output.
- [ ] Re-run the focused suite until all cases pass, then mutation-check wrong actor,
  wrong check, wrong branch, and wrong tag-target branches.

### Task 2: GitHub App upstream synchronization identity

**Files:**
- Modify: `.github/workflows/sync-upstreams.yml`
- Modify: `scripts/verify_repository_health.py`
- Modify: `tests/test_upstream_workflow.py`
- Modify: `tests/test_repository_health.py`

**Interfaces:**
- Consumes `UPSTREAM_SYNC_APP_ID` and `UPSTREAM_SYNC_APP_PRIVATE_KEY`.
- Produces App-authored same-repository PRs with labels
  `automation:upstream-sync` and `release:patch`.

- [ ] Add failing contract tests requiring a redacted credential preflight, the pinned
  official token action, repository restriction, requested token permissions, App
  token use for every fetch/push/PR mutation, App bot author identity, and trusted
  labels; reject `secrets.GITHUB_TOKEN` from mutation steps.
- [ ] Run focused tests and confirm the old workflow fails the new expectations.
- [ ] Extend the reviewed-action registry/counts for
  `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0`.
- [ ] Modify the workflow, preserving four-source isolation, source scope, deterministic
  builds, existing-PR update, normal pushes, and transient packages.
- [ ] Re-run focused tests and repository health.

### Task 3: Fail-closed auto merge

**Files:**
- Create: `.github/workflows/auto-merge-upstream.yml`
- Modify: `tests/test_automation_policy.py`
- Modify: `tests/test_upstream_workflow.py`
- Modify: `scripts/verify_repository_health.py`

**Interfaces:**
- Trigger: completed `workflow_run` for `Validate package`.
- Decision: `ignore`, `block`, `update`, or `merge` bound to live PR/head SHA.
- Mutations: update branch, squash merge, delete head ref, manual-review label/comment;
  each followed by API readback.

- [ ] Add failing tests for workflow trigger/permissions and all required decision
  branches, including protected paths, review threads, requested changes, behind, and
  failed `verify`.
- [ ] Run focused tests and confirm RED.
- [ ] Implement API-only preflight on trusted default-branch code, exact-head checkout
  only after identity/path PASS, repository/source/provenance verification, update and
  merge state machines, blocker reporting, and readback.
- [ ] Re-run focused tests, repository health, and a YAML parse/static expression check.

### Task 4: Post-main automatic release

**Files:**
- Create: `.github/workflows/auto-release.yml`
- Modify: `tests/test_automation_policy.py`
- Modify: `tests/test_upstream_workflow.py`
- Modify: `scripts/verify_repository_health.py`

**Interfaces:**
- Trigger: successful `Validate package` `workflow_run` for a `main` push.
- Produces a formal semver tag and Release at the exact validated commit plus
  `presentation-studio.zip` and `presentation-studio.zip.sha256`.

- [ ] Add failing tests for main-run filtering, trusted merged-PR association, patch /
  minor / major planning, collision and idempotency, clean deterministic builds,
  `--smoke`, release notes fields, exact target SHA, two assets, concurrency, and
  release readback.
- [ ] Run focused tests and confirm RED.
- [ ] Implement release planning and workflow verification/build/publish/readback.
- [ ] Re-run focused tests and deterministic package tests.

### Task 5: Maintainer operations and legacy PR transition

**Files:**
- Create: `docs/AUTOMATION.md`
- Modify: `docs/upstream-sync.md`
- Modify: `tests/test_repository_contract.py`

**Interfaces:**
- Documents detection → sync → PR → validation → classification → merge → main
  validation → semver → build → Release and the single owner bootstrap.

- [ ] Add failing documentation-contract tests for the App credentials, permissions,
  labels, fail-closed state machine, release evidence, rotation/recovery, and legacy PR
  replacement procedure.
- [ ] Write the maintainer guide and update the legacy synchronization guide.
- [ ] Re-run documentation/repository contract tests.
- [ ] After the framework PR is merged and the App is bootstrapped, close legacy
  App-ineligible automation PRs and dispatch a fresh source synchronization; do not
  merge or close them before the replacement identity is operational.

### Task 6: Full verification and GitHub delivery

**Files:**
- Evidence only; no new production interface.

- [ ] Run `python scripts/verify_repository_health.py`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python scripts/verify_examples.py`.
- [ ] Build two packages under `D:\Codex\builds\presentation-studio-autonomous-release`
  and verify both with `scripts/verify_package.py --smoke`.
- [ ] Run `git diff --check`, inspect the full diff, verify no secrets, and verify every
  Action is immutable-SHA pinned.
- [ ] Commit and push the feature branch, create a PR, and read back the PR, workflow
  runs, checks, changed paths, and active Ruleset.
- [ ] Report the GitHub App bootstrap as `BLOCKED` until owner configuration exists;
  do not claim end-to-end merge/release evidence before a real App-authored run.
