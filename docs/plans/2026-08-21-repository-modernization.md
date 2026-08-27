# Repository Modernization Implementation Plan

> Historical planning record from 2026-08-21. Its initial Codex-first metadata wording is superseded by the current Agent-compatible contract in the three root README entry points; retained here as an audit trail.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Inline execution is selected; no subagents are authorized.

**Goal:** Modernize Presentation Studio's public documentation, community surface, GitHub Actions references, Dependabot scope, security intake, and repository metadata without changing product behavior or publishing a Release.

**Architecture:** A standard-library repository-health verifier provides an executable boundary for local README links, required community files, Issue Form structure, immutable official-action pins, and the GitHub-Actions-only Dependabot policy. Human prose is reviewed directly. Versioned changes travel through one protected PR; remote metadata changes occur only after merge and main CI.

**Tech Stack:** Python 3.11+ standard library, Markdown, GitHub Issue Form YAML, GitHub Actions YAML, Git, GitHub CLI/API.

**Spec:** `docs/designs/2026-08-21-repository-modernization.md`

## Global constraints

- Preserve the seven existing README capability markers and exactly two example `<details>` blocks.
- Preserve the `verify` status-check name, workflow triggers, permissions, and sync-through-PR safety behavior.
- Do not change product code, vendored engines, source locks, `dist/presentation-studio.zip`, or `checksums.sha256`.
- Do not merge Dependabot PR #4, rewrite vendored npm alerts, enable CodeQL, or publish a tag/Release.
- Pin official actions to the reviewed full commit SHAs listed below with readable release comments.
- Configure Dependabot for `github-actions` only.
- Use explicit path staging, noreply authorship, normal pushes, and ruleset-compliant PR merge.

## Reviewed official action releases

```text
actions/checkout v7.0.1
3d3c42e5aac5ba805825da76410c181273ba90b1

actions/setup-python v7.0.0
5fda3b95a4ea91299a34e894583c3862153e4b97

actions/upload-artifact v7.0.1
043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
```

## File map

- Create `scripts/verify_repository_health.py`: executable repository boundary validator.
- Create `tests/test_repository_health.py`: fixture-driven validator tests.
- Modify `README.md`: bilingual release-first onboarding and documentation router.
- Create `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`: public policies.
- Create `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`: ownership and PR policy.
- Create `.github/ISSUE_TEMPLATE/*.yml`: structured public intake.
- Modify `.github/workflows/*.yml`: immutable Node.js 24-generation action pins and health-verifier step.
- Create `.github/dependabot.yml`: weekly GitHub Actions updates only.

---

### Task 1: Repository-health verifier core, RED to GREEN

**Files:**
- Create: `tests/test_repository_health.py`
- Create: `scripts/verify_repository_health.py`

**Interfaces:**
- `validate_repository(root: pathlib.Path) -> list[str]`
- CLI: `python scripts/verify_repository_health.py [--root PATH]`; exit 0 with `PASS`, exit 1 with one `ERROR:` line per issue.

- [ ] **Step 1: Write failing tests for observable validation behavior**

Create a temporary minimal repository fixture in `setUp` containing a README with local links, all required community files, three Issue Forms, config, two workflow files with reviewed pins, and a GitHub-Actions-only Dependabot file. Tests:

```python
def test_complete_repository_passes(self):
    self.assertEqual(health.validate_repository(self.root), [])

def test_missing_local_readme_target_and_community_file_fail(self):
    (self.root / "SECURITY.md").unlink()
    (self.root / "README.md").write_text("[Missing](docs/missing.md)\n", encoding="utf-8")
    issues = health.validate_repository(self.root)
    self.assertIn("missing required community file: SECURITY.md", issues)
    self.assertIn("README local link target does not exist: docs/missing.md", issues)

def test_malformed_issue_form_floating_action_and_npm_dependabot_fail(self):
    self.issue_form.write_text("name: Bug\nbody: []\n", encoding="utf-8")
    self.workflow.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
    self.dependabot.write_text('version: 2\nupdates:\n  - package-ecosystem: "npm"\n', encoding="utf-8")
    issues = health.validate_repository(self.root)
    self.assertIn("issue form missing top-level description: .github/ISSUE_TEMPLATE/bug_report.yml", issues)
    self.assertIn("official action is not pinned to a full reviewed commit: actions/checkout@v4", issues)
    self.assertIn("Dependabot may update github-actions only", issues)
```

Load `scripts/verify_repository_health.py` with `importlib.util.spec_from_file_location`, matching existing test patterns and exercising the real module without mocks.

- [ ] **Step 2: Run RED**

```powershell
& $taskPython -B -m unittest tests.test_repository_health -v
```

Expected: import fails because `scripts/verify_repository_health.py` does not exist. This is the correct RED boundary.

- [ ] **Step 3: Implement the minimal verifier**

Implement with standard-library `argparse`, `json`, `re`, `urllib.parse`, and `pathlib`.

Validation behavior:

- Report every missing required community file.
- Extract non-image Markdown links from README; skip external, mail, and anchor targets; remove fragment/query; URL-decode; require each local target to exist under the repository root.
- Require zero-indented `name:`, `description:`, and `body:` plus at least one `validations:` in each Issue Form.
- Require every `uses: actions/` line to match the reviewed action name, 40-hex SHA, and release comment above.
- Require exactly one root, weekly `github-actions` Dependabot entry with limit 3 and `ci` prefix; reject every other ecosystem.
- Return a stable sorted list of unique issue strings.
- CLI emits JSON containing `status`, `root`, and `issues`, then returns 0 only when issues are empty.

- [ ] **Step 4: Run GREEN and real-repository failure behavior**

Run the test module, then run the CLI against the real repository. Fixture tests must pass; the real repository must fail only because community/configuration files and reviewed pins are not yet present.

- [ ] **Step 5: Commit verifier deliverable**

Stage only `scripts/verify_repository_health.py` and `tests/test_repository_health.py`; run cached diff check; commit `test: add repository health verifier`.

---

### Task 2: README and community surface

**Files:** `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, and `.github/ISSUE_TEMPLATE/*.yml`.

- [ ] **Step 1: Add README release-first onboarding**

Preserve existing content/contracts. Add a Latest Release badge and top actions, `60 秒快速开始 / 60-second quick start`, runtime/capability matrix, product/engine selection, troubleshooting, and contribution/security links. Keep checksum commands, seven layer markers, exactly two details blocks, six examples, repository map, architecture links, and upstream credits.

- [ ] **Step 2: Add policies**

`CONTRIBUTING.md` covers tested setup, branch/draft-PR flow, explicit staging, unit/example/two-build/package verification, vendored boundaries, deterministic evidence, credential/path scanning, and licensing. `SECURITY.md` supports current main/latest stable, uses `privately report`, links the private advisory form, requests actionable evidence, forbids secrets/public undisclosed exploits, and promises no SLA. `CODE_OF_CONDUCT.md` adopts Contributor Covenant 2.1 with the repository owner's GitHub profile as contact.

- [ ] **Step 3: Add ownership and structured intake**

CODEOWNERS uses `@kwhi6693-web` globally and for workflows, scripts, tests, engines, and source lock. The PR template covers scope, tests, examples, deterministic builds, package verification, docs, secrets/paths, vendored evidence, and release impact. Add structured Bug, Feature, and Upstream Sync Issue Forms plus config disabling blank issues and routing security reports to SECURITY.md.

- [ ] **Step 4: Run verifier and manual prose review**

The health verifier may still report only action pins and missing Dependabot. Run existing repository contract tests and `git diff --check`; manually check bilingual parity, commands, links, no local paths/secrets, no SLA, and retained architecture/examples.

- [ ] **Step 5: Commit**

Stage exactly the README/community/template files; commit `docs: modernize repository onboarding and governance`.

---

### Task 3: Immutable Actions and narrow Dependabot, RED to GREEN

**Files:** `tests/test_repository_health.py`, `scripts/verify_repository_health.py` if required, `.github/workflows/validate.yml`, `.github/workflows/sync-upstreams.yml`, `.github/dependabot.yml`.

- [ ] **Step 1: Add mutation tests first**

Mutate a valid fixture one item at a time and assert exact issues for wrong reviewed SHA, missing release comment, a second ecosystem, wrong schedule, and missing Issue Form validations.

- [ ] **Step 2: Run RED**

Run `tests.test_repository_health`. At least one mutation must fail until missing validator behavior is implemented. If Task 1 already covers a mutation, retain that passing test and use an uncovered mutation for RED.

- [ ] **Step 3: Complete validator behavior to GREEN**

Make only minimal validator changes, rerun all health tests.

- [ ] **Step 4: Replace action references and add CI health step**

Use the three reviewed immutable references above. Add `python scripts/verify_repository_health.py` as `Verify repository health` after Python setup in both workflows. Change no trigger, permission, job/status name, timeout, or sync/PR logic.

- [ ] **Step 5: Add Dependabot configuration**

Version 2; one root `github-actions` entry; weekly Monday 03:17 Asia/Shanghai; open PR limit 3; `ci` scoped prefix; `dependencies` and `github-actions` labels; no npm.

- [ ] **Step 6: Run GREEN and commit**

Run health tests, real health CLI, and repository contract tests. Stage only workflow, Dependabot, and any health test/verifier changes; commit `ci: pin current actions and scope Dependabot`.

---

### Task 4: Full verification and package invariance

- [ ] Record `origin/main` Git object IDs for ZIP and checksum.
- [ ] Run complete unit suite; count must exceed 105.
- [ ] Run health verifier and six-example verifier.
- [ ] Build twice and require identical SHA-256.
- [ ] Run package verifier.
- [ ] Require ZIP/checksum Git object IDs to equal `origin/main`.
- [ ] Run diff check, path/secret scans, and inspect status/diff.

---

### Task 5: Review, draft PR, CI, and protected merge

- [ ] Independent read-only review of `origin/main..HEAD`; fix every Critical/Important finding without amend.
- [ ] Normal push and draft PR with RED/GREEN, verification, package invariance, reviewed action sources, and deferred dependency/CodeQL scope.
- [ ] Wait for all checks and inspect authoritative GraphQL review threads.
- [ ] Mark ready and merge with normal merge only when clean; no branch deletion or bypass.
- [ ] Fast-forward main and wait for push-triggered main CI at the merge SHA.

---

### Task 6: Remote metadata, private reporting, and final audit

- [ ] Capture current description, homepage, topics, and private-reporting state.
- [ ] Set description to `Agent-compatible presentation and visual production Skill for editable PPTX, HTML slides, exact-data routing, and rendered QA.`
- [ ] Set homepage to `https://github.com/kwhi6693-web/presentation-studio/releases/latest`.
- [ ] Set topics to a focused capability set including `agent-skill`, `ai-agent`, `codex-skill`, `presentation-automation`, `presentation-generator`, `pptx`, `html-slides`, `infographics`, and `diagrams`.
- [ ] Enable private vulnerability reporting and require API readback `enabled: true`.
- [ ] Read back Community Profile, ruleset, security settings, open PRs, Releases, and Dependabot alerts.
- [ ] Confirm v1.1.1 remains Latest, PR #4 remains independent, CodeQL remains deferred, ruleset remains active/no bypass, Release digest remains `c2ca5be5c68d7530f2b724189192284e2bea8b5c9d28b0a77e16314950e40b8d`, and original workspace remains untouched.
- [ ] Report changed files, commits, RED/GREEN/full evidence, PR/merge/main CI, metadata, Community Profile, action pins, package invariance, and deferred risks.
