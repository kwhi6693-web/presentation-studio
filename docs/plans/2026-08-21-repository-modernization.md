# Repository Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent execution is not selected for this task.

**Goal:** Modernize Presentation Studio's README, public contribution surface, GitHub Actions supply-chain references, Dependabot policy, and repository metadata without changing product behavior or publishing a release.

**Architecture:** Versioned repository changes are enforced through standard-library repository contract tests and delivered through one protected pull request. Remote-only repository metadata is updated after the PR merge so the README, community files, and CI policy are authoritative before the public repository profile changes.

**Tech Stack:** Markdown, GitHub Issue Form YAML, GitHub Actions YAML, Python 3.11+ standard-library `unittest`, Git, GitHub CLI/API.

**Spec:** `docs/designs/2026-08-21-repository-modernization.md`

## Global Constraints

- Preserve the existing seven README capability markers and exactly two `<details>` example showcases.
- Preserve the `verify` job/status-check name, workflow triggers, permissions, and sync-through-PR safety behavior.
- Do not change product code, vendored engine contents, source locks, `dist/presentation-studio.zip`, or `checksums.sha256`.
- Do not merge Dependabot PR #4, rewrite the 34 vendored npm alerts, enable CodeQL, or publish a new tag/Release.
- Pin official GitHub Actions to full immutable commit SHAs with readable version comments.
- Configure Dependabot for `github-actions` only; do not configure npm updates.
- Do not commit local absolute paths, credentials, tokens, generated caches, or internal planning artifacts in discovery paths.
- Use explicit `git add -- <paths>` staging and noreply authorship; never use force push or history rewriting.

## File map

- `README.md`: bilingual release-first landing page and documentation router.
- `CONTRIBUTING.md`: contributor workflow and verification contract.
- `SECURITY.md`: private vulnerability-reporting and supported-version policy.
- `CODE_OF_CONDUCT.md`: participation and enforcement expectations.
- `.github/CODEOWNERS`: repository ownership boundaries.
- `.github/PULL_REQUEST_TEMPLATE.md`: author verification checklist.
- `.github/ISSUE_TEMPLATE/bug_report.yml`: structured bug reports.
- `.github/ISSUE_TEMPLATE/feature_request.yml`: structured feature proposals.
- `.github/ISSUE_TEMPLATE/upstream_sync.yml`: structured upstream-update reports.
- `.github/ISSUE_TEMPLATE/config.yml`: blank-issue and contact-link policy.
- `.github/workflows/validate.yml`: immutable checkout/setup-python pins.
- `.github/workflows/sync-upstreams.yml`: immutable checkout/setup-python/upload-artifact pins.
- `.github/dependabot.yml`: weekly GitHub Actions maintenance only.
- `tests/test_repository_contract.py`: executable contracts for all new repository surfaces.

---

### Task 1: RED contracts for README and community health

**Files:**
- Modify: `tests/test_repository_contract.py`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: repository root constant `ROOT` and the existing README contract.
- Produces: `COMMUNITY_FILES`, `ISSUE_FORMS`, `read_text(relative_path)`, and three failing contract tests used by Task 2.

- [ ] **Step 1: Add the exact test helpers and failing contracts**

Add after `SIX_EXAMPLE_PATHS`:

```python
COMMUNITY_FILES = (
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
)

ISSUE_FORMS = (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/upstream_sync.yml",
)


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")
```

Add these methods to `RepositoryContractTests`:

```python
def test_readme_has_release_first_onboarding_and_maintenance_links(self) -> None:
    text = read_text("README.md")
    for term in (
        "https://github.com/kwhi6693-web/presentation-studio/releases/latest",
        "img.shields.io/github/v/release/kwhi6693-web/presentation-studio",
        "60 秒快速开始",
        "60-second quick start",
        "运行时与能力支持矩阵",
        "Runtime and capability matrix",
        "产品与引擎选择",
        "Product and engine selection",
        "故障排查",
        "Troubleshooting",
        "CONTRIBUTING.md",
        "SECURITY.md",
    ):
        with self.subTest(term=term):
            self.assertIn(term, text)

def test_repository_has_complete_community_health_surface(self) -> None:
    for relative_path in COMMUNITY_FILES:
        with self.subTest(path=relative_path):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)
    self.assertIn("privately report", read_text("SECURITY.md").lower())
    self.assertIn("deterministic", read_text("CONTRIBUTING.md").lower())
    self.assertIn("@kwhi6693-web", read_text(".github/CODEOWNERS"))

def test_issue_forms_are_structured_and_blank_issues_are_disabled(self) -> None:
    for relative_path in ISSUE_FORMS:
        text = read_text(relative_path)
        with self.subTest(path=relative_path):
            self.assertIn("name:", text)
            self.assertIn("description:", text)
            self.assertIn("body:", text)
            self.assertIn("validations:", text)
    config = read_text(".github/ISSUE_TEMPLATE/config.yml")
    self.assertIn("blank_issues_enabled: false", config)
    self.assertIn("SECURITY.md", config)
```

- [ ] **Step 2: Run the focused suite and record RED**

Run:

```powershell
& $taskPython -B -m unittest tests.test_repository_contract.RepositoryContractTests -v
```

Expected: the three new tests fail because README markers and community files are absent; pre-existing repository contract tests continue to pass.

- [ ] **Step 3: Confirm the failures name missing behavior rather than syntax errors**

Expected failure classes:

```text
AssertionError: '...releases/latest' not found
AssertionError: CONTRIBUTING.md
FileNotFoundError or AssertionError for .github/ISSUE_TEMPLATE/*.yml
```

Do not edit production/documentation files until this RED output has been observed.

---

### Task 2: GREEN README and community health surface

**Files:**
- Modify: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `.github/CODEOWNERS`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/upstream_sync.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: exact marker strings and file paths established in Task 1.
- Produces: a bilingual landing page, contribution/security policies, ownership policy, and structured issue/PR intake.

- [ ] **Step 1: Reorganize README with exact new sections**

Keep the title, product statement, existing seven-layer table, exactly two example `<details>` blocks, architecture explanation, repository map, credits, and license content. Add these headings and copy blocks before the detailed architecture content:

```markdown
[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)

[Download latest release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) · [Installation](#60-秒快速开始--60-second-quick-start) · [Examples](#双语示例产品) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## 60 秒快速开始 / 60-second quick start

### Release 安装 / Install from a Release

Download `presentation-studio.zip` and `presentation-studio.zip.sha256` from the latest Release, verify them in the same directory, extract the single `presentation-studio/` root, and run `scripts/self_check.py` before activation.

### 源码安装 / Install from source

Use `scripts/install.ps1` on Windows or `scripts/install.sh` on Linux/macOS. Both installers stage and self-check before activation.

## 运行时与能力支持矩阵 / Runtime and capability matrix

| Runtime or capability | Required for | Required? | Preflight evidence |
|---|---|---:|---|
| Python 3.11+ tested; bundled runtime preferred | Routing, validation, PPTX workflows | Core | `runtimes.python`, `readiness.pptx_core` |
| Resolved bundled Node.js runtime preferred | Browser and Baoyu workflows | Core for those engines | `runtimes.node`, `readiness.baoyu_core` |
| Office renderer | Native Office rendering | Optional | `readiness.office_renderer` |
| Chromium + Playwright | Browser rendering and QA | Optional | `readiness.chromium`, `capabilities.node.browser_qa` |
| Image provider credentials | Generated visual assets | Optional | redacted provider readiness only |
| Optional Python/Node modules | Ingest, narration, advanced SVG and web extraction | Optional | per-module booleans; one missing module does not affect another |

## 产品与引擎选择 / Product and engine selection

| Need | Preferred route |
|---|---|
| Native editable PPTX, charts, tables, speaker notes | PPT Master |
| Swiss/editorial presentation system | Guizang |
| Standalone HTML, keyboard navigation, browser PDF | Frontend Slides |
| Covers, illustrations, infographics, diagrams, image slides | Baoyu |
| PPTX plus standalone HTML/PDF | Dual-format product route |

## 故障排查 / Troubleshooting

- Run `presentation-studio/scripts/preflight.py` with explicit Python and Node executables.
- Run `presentation-studio/scripts/self_check.py --json` against the installed skill root.
- Treat `PASS`, `PARTIAL`, and `FAIL` as distinct delivery states; do not silently replace unavailable native output with a flattened image.
- Report reproducible defects with the bug form, after removing credentials and local absolute paths.
```

Preserve the existing Linux/macOS/PowerShell checksum commands and source-checkout versus Release-manifest distinction.

- [ ] **Step 2: Add contribution and security policies**

`CONTRIBUTING.md` must include:

- Python 3.11+ and Git requirements.
- Feature branch and draft PR process.
- Commands for unit tests, example verification, deterministic build twice, and package verification.
- Explicit staging guidance.
- A rule that `presentation-studio/engines`, `source-lock.json`, licenses, and adapters change only through the upstream synchronization contract or an evidence-backed reviewed exception.
- A rule that ZIP/checksum changes require deterministic rebuild evidence.

`SECURITY.md` must include:

- Supported version: latest published stable release and current `main`; older releases receive best-effort assessment only.
- Private reporting through GitHub Security Advisories at `https://github.com/kwhi6693-web/presentation-studio/security/advisories/new`.
- The literal phrase `privately report`.
- Evidence requested: affected version/commit, impact, minimal reproduction, mitigation ideas, and whether credentials or untrusted artifacts are involved.
- Never include tokens, passwords, private files, or undisclosed exploit details in public issues.
- No guaranteed response SLA.

Use the Contributor Covenant 2.1 text in `CODE_OF_CONDUCT.md`, with enforcement contact through the repository owner's GitHub profile rather than a private email address.

- [ ] **Step 3: Add ownership and pull-request policy**

`.github/CODEOWNERS`:

```text
* @kwhi6693-web
/.github/workflows/ @kwhi6693-web
/scripts/ @kwhi6693-web
/tests/ @kwhi6693-web
/presentation-studio/source-lock.json @kwhi6693-web
/presentation-studio/engines/ @kwhi6693-web
```

`.github/PULL_REQUEST_TEMPLATE.md` must contain unchecked boxes for focused scope, tests, examples, two deterministic hashes when package inputs change, package verification, docs, credential/path scan, vendored-source evidence, and explicit release impact.

- [ ] **Step 4: Add structured Issue Forms**

Every Issue Form must have top-level `name`, `description`, `title`, `labels`, and `body`; each required input must contain `validations: {required: true}` in valid expanded YAML form.

`bug_report.yml` fields: version/source commit, installation path category (Release/source/installed skill), operating system, Python/Node versions, redacted preflight output, reproduction, expected behavior, actual behavior, and credential-redaction checkbox.

`feature_request.yml` fields: problem, desired outcome, product/engine scope dropdown, alternatives, acceptance criteria, and compatibility impact.

`upstream_sync.yml` fields: upstream repository URL, stable release/tag, evidence URL, import paths, license impact, adapter impact, and verification plan.

`config.yml`:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security vulnerability / 安全漏洞
    url: https://github.com/kwhi6693-web/presentation-studio/blob/main/SECURITY.md
    about: Privately report vulnerabilities; do not disclose secrets in public issues.
```

- [ ] **Step 5: Run focused tests to GREEN**

Run:

```powershell
& $taskPython -B -m unittest tests.test_repository_contract.RepositoryContractTests -v
```

Expected: all repository contract tests pass, including the three tests added in Task 1.

- [ ] **Step 6: Commit the README/community deliverable**

Stage only:

```powershell
git add -- README.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md .github/CODEOWNERS .github/PULL_REQUEST_TEMPLATE.md .github/ISSUE_TEMPLATE/bug_report.yml .github/ISSUE_TEMPLATE/feature_request.yml .github/ISSUE_TEMPLATE/upstream_sync.yml .github/ISSUE_TEMPLATE/config.yml tests/test_repository_contract.py
git diff --cached --check
git commit -m "docs: modernize repository onboarding and governance"
```

---

### Task 3: RED contracts for immutable Actions and narrow Dependabot policy

**Files:**
- Modify: `tests/test_repository_contract.py`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: workflow files as UTF-8 text.
- Produces: one failing test for immutable official-action pins and one failing test for the GitHub-Actions-only Dependabot policy.

- [ ] **Step 1: Add exact failing tests**

Add imports:

```python
from collections import Counter
```

Add methods to `RepositoryContractTests`:

```python
def test_official_actions_are_pinned_to_reviewed_node24_commits(self) -> None:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    expected = {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1": 2,
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0": 2,
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1": 1,
    }
    counts = Counter(
        line.strip().removeprefix("- ").removeprefix("uses: ")
        for line in workflow_text.splitlines()
        if "uses: actions/" in line
    )
    self.assertEqual(counts, Counter(expected))
    for deprecated in ("actions/checkout@v4", "actions/setup-python@v5", "actions/upload-artifact@v4"):
        self.assertNotIn(deprecated, workflow_text)

def test_dependabot_updates_github_actions_only(self) -> None:
    text = read_text(".github/dependabot.yml")
    self.assertEqual(text.count('package-ecosystem: "github-actions"'), 1)
    self.assertNotIn('package-ecosystem: "npm"', text)
    for term in ('directory: "/"', 'interval: "weekly"', "open-pull-requests-limit: 3", 'prefix: "ci"'):
        with self.subTest(term=term):
            self.assertIn(term, text)
```

- [ ] **Step 2: Run and record RED**

Run:

```powershell
& $taskPython -B -m unittest tests.test_repository_contract.RepositoryContractTests.test_official_actions_are_pinned_to_reviewed_node24_commits tests.test_repository_contract.RepositoryContractTests.test_dependabot_updates_github_actions_only -v
```

Expected:

- Action-pin test fails because the workflows use `@v4`/`@v5`.
- Dependabot test fails because `.github/dependabot.yml` does not exist.

---

### Task 4: GREEN Actions and Dependabot maintenance policy

**Files:**
- Modify: `.github/workflows/validate.yml`
- Modify: `.github/workflows/sync-upstreams.yml`
- Create: `.github/dependabot.yml`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: exact pin strings required by Task 3.
- Produces: Node.js 24-generation action execution with immutable references and weekly GitHub Actions update proposals.

- [ ] **Step 1: Replace action references exactly**

In both workflow files replace checkout references with:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
```

Replace setup-python references with:

```yaml
- uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
```

Replace upload-artifact with:

```yaml
uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
```

Do not change any surrounding trigger, permission, input, condition, name, or command.

- [ ] **Step 2: Add the narrow Dependabot configuration**

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "03:17"
      timezone: "Asia/Shanghai"
    open-pull-requests-limit: 3
    commit-message:
      prefix: "ci"
      include: "scope"
    labels:
      - "dependencies"
      - "github-actions"
```

- [ ] **Step 3: Run focused tests to GREEN**

Run the two Task 3 tests, then the full repository contract class:

```powershell
& $taskPython -B -m unittest tests.test_repository_contract.RepositoryContractTests.test_official_actions_are_pinned_to_reviewed_node24_commits tests.test_repository_contract.RepositoryContractTests.test_dependabot_updates_github_actions_only -v
& $taskPython -B -m unittest tests.test_repository_contract.RepositoryContractTests -v
```

Expected: all pass.

- [ ] **Step 4: Commit the CI maintenance deliverable**

```powershell
git add -- .github/workflows/validate.yml .github/workflows/sync-upstreams.yml .github/dependabot.yml tests/test_repository_contract.py
git diff --cached --check
git commit -m "ci: pin current actions and scope Dependabot"
```

---

### Task 5: Full local verification and package invariance

**Files:**
- Verify only: all versioned changes

**Interfaces:**
- Consumes: Tasks 1-4 working tree.
- Produces: fresh evidence for the draft PR and proof that the product ZIP did not change.

- [ ] **Step 1: Record the baseline package hashes from `origin/main`**

```powershell
$baselineZip = git rev-parse 'origin/main:dist/presentation-studio.zip'
$baselineManifest = git rev-parse 'origin/main:checksums.sha256'
```

- [ ] **Step 2: Run the complete unit suite**

```powershell
& $taskPython -B -m unittest discover -s tests -v
```

Expected: all tests pass; the count is greater than the v1.1.1 baseline of 105 because new contract tests were added.

- [ ] **Step 3: Verify examples and deterministic package twice**

```powershell
& $taskPython -B scripts/verify_examples.py
& $taskPython -B scripts/build_package.py
$hashOne = (Get-FileHash -Algorithm SHA256 -LiteralPath dist/presentation-studio.zip).Hash.ToLowerInvariant()
& $taskPython -B scripts/build_package.py
$hashTwo = (Get-FileHash -Algorithm SHA256 -LiteralPath dist/presentation-studio.zip).Hash.ToLowerInvariant()
if ($hashOne -ne $hashTwo) { throw "Deterministic package mismatch" }
& $taskPython -B scripts/verify_package.py
```

Expected: six examples pass, hashes match, and package verification passes.

- [ ] **Step 4: Prove package files are unchanged**

```powershell
if ((git hash-object dist/presentation-studio.zip) -ne $baselineZip) { throw "ZIP changed unexpectedly" }
if ((git hash-object checksums.sha256) -ne $baselineManifest) { throw "Repository checksum changed unexpectedly" }
git status --short
git diff --check
```

Expected: ZIP and manifest object IDs match `origin/main`; only intended documentation, community, workflow, Dependabot, test, design, and plan files differ.

---

### Task 6: Independent review, protected PR, and merge

**Files:**
- Review only: `origin/main..HEAD`

**Interfaces:**
- Consumes: verified local commits.
- Produces: reviewed draft PR, green authoritative CI, empty/resolved review threads, and a ruleset-compliant merge commit.

- [ ] **Step 1: Request independent read-only review**

Review priorities: README accuracy, security-reporting safety, Issue Form usability, CODEOWNERS scope, immutable action pins, Dependabot npm exclusion, workflow behavior preservation, and absence of local paths/secrets.

Fix every Critical or Important finding through a new RED -> GREEN cycle and a new commit. Do not amend existing commits.

- [ ] **Step 2: Push and create a draft PR**

```powershell
git push --set-upstream origin chore/repository-modernization
$prBody = @'
## Summary

- reorganize the bilingual README around the latest Release, a 60-second quick start, runtime support, engine selection, and troubleshooting
- add contribution, security, conduct, ownership, PR, and structured issue-reporting policies
- pin current official GitHub Actions to immutable reviewed commits and configure weekly GitHub-Actions-only Dependabot updates

## TDD evidence

- RED: README/community contract tests failed while the required markers and files were absent
- GREEN: README/community repository contracts passed after the documented surface was added
- RED: action-pin and Dependabot policy tests failed on deprecated floating majors and the missing configuration
- GREEN: immutable Node.js 24-generation pins and the GitHub-Actions-only policy passed

## Verification

- complete unit suite
- six bilingual example products
- two byte-identical deterministic package builds
- package parity verification
- ZIP and repository checksum object IDs unchanged from `origin/main`

## Deliberately deferred

- Dependabot PR #4 and vendored npm alert remediation
- CodeQL activation and vendored/generated-source scoping
- new tag or Release
- repository metadata API update until after this PR is merged and main CI succeeds
'@
gh pr create --draft --base main --head chore/repository-modernization --title "chore: modernize repository documentation and governance" --body $prBody
```

The body must list RED/GREEN evidence, full verification, package invariance, action release sources, non-goals, and metadata changes deferred until after merge.

- [ ] **Step 3: Wait for CI and authoritative review threads**

```powershell
$prNumber = gh pr view chore/repository-modernization --json number --jq '.number'
gh pr checks $prNumber --watch --interval 10
gh api graphql -f query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved comments(first:20){nodes{author{login} body url}}}}}}}' -F owner=kwhi6693-web -F name=presentation-studio -F number=$prNumber
```

Expected: all checks successful; no unresolved authoritative thread.

- [ ] **Step 4: Mark ready and merge under the active ruleset**

```powershell
$prNumber = gh pr view chore/repository-modernization --json number --jq '.number'
gh pr ready $prNumber
gh pr merge $prNumber --merge
```

Do not delete the branch and do not use admin bypass.

- [ ] **Step 5: Verify `main` CI after merge**

Fetch and fast-forward local `main`, identify the push-triggered `Validate package` run at the merge SHA, and wait with `gh run watch <run-id> --exit-status`.

---

### Task 7: Repository metadata update and final audit

**Files:**
- Remote GitHub repository metadata only

**Interfaces:**
- Consumes: verified merged README and governance surface.
- Produces: accurate repository description, latest-release homepage, discovery topics, and final state report.

- [ ] **Step 1: Capture current metadata for rollback evidence**

```powershell
gh repo view kwhi6693-web/presentation-studio --json description,homepageUrl,repositoryTopics,url
```

- [ ] **Step 2: Update description and homepage**

```powershell
gh repo edit kwhi6693-web/presentation-studio --description "Bilingual Codex Skill for verified PPTX, HTML slides, PDF, infographics, diagrams, exact-data routing, and presentation QA." --homepage "https://github.com/kwhi6693-web/presentation-studio/releases/latest"
```

- [ ] **Step 3: Enable private vulnerability reporting**

The current API state is `enabled: false`. Enable the private advisory intake before the merged `SECURITY.md` sends reporters there:

```powershell
gh api --method PUT repos/kwhi6693-web/presentation-studio/private-vulnerability-reporting
gh api repos/kwhi6693-web/presentation-studio/private-vulnerability-reporting
```

Expected readback: `{"enabled":true}`.

- [ ] **Step 4: Replace topics with the approved focused set**

Use the GitHub topics API with exactly:

```json
{
  "names": [
    "codex-skill",
    "presentations",
    "pptx",
    "html-slides",
    "pdf",
    "infographics",
    "diagrams",
    "presentation-automation",
    "python",
    "github-actions"
  ]
}
```

- [ ] **Step 5: Verify public repository health and non-goals**

Read back repository metadata, Community Profile, ruleset, security settings, open PRs, releases, and open Dependabot alert counts. Confirm:

- Latest Release remains `v1.1.1`.
- Dependabot PR #4 remains independently open unless the user separately authorizes it.
- No CodeQL analysis was enabled.
- Ruleset remains active with no bypass actors.
- Private vulnerability reporting is enabled.
- `dist/presentation-studio.zip` digest remains `c2ca5be5c68d7530f2b724189192284e2bea8b5c9d28b0a77e16314950e40b8d`.
- Original local workspace remains untouched.

- [ ] **Step 6: Report final evidence**

Provide changed files, RED/GREEN/full verification, commits, PR URL, merge SHA, main CI URL, metadata values, Community Profile state, action pins, package invariance, and deliberately deferred Dependabot/CodeQL work.
