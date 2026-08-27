# Repository Modernization Design

> Historical design record from 2026-08-21. The original bilingual/Codex-first proposal is superseded by the current three-entry-point, Agent-compatible public contract; this file remains for traceability.

Date: 2026-08-21

Status: Approved for implementation

Target repository: `kwhi6693-web/presentation-studio`

## Purpose

Modernize the public repository around the already released `v1.1.1` without changing Presentation Studio's product behavior or publishing another release. The update should make installation, verification, contribution, security reporting, repository discovery, and CI maintenance easier to understand and safer to operate.

## Current evidence

- The README documents the architecture and examples well, but it does not provide a compact release-first quick start, runtime support matrix, troubleshooting index, or prominent contribution and security entry points.
- GitHub reports a Community Profile score of 42%. The repository has a license and README but lacks contributing guidance, a security policy, a code of conduct, issue templates, and a pull-request template.
- Repository topics are empty and the homepage is unset.
- The two workflows still use Node.js 20 generations of `actions/checkout` and `actions/setup-python`, which now emit deprecation annotations on GitHub-hosted runners.
- Dependabot security alerts are enabled. The 34 open npm alerts are confined to Baoyu engine lockfiles managed by the stable-upstream synchronization contract.
- Dependabot PR #4 proposes a separate `sharp` upgrade and already has green checks, but it changes vendored dependency state and is outside this maintenance change.
- Code scanning has no analysis. A useful CodeQL configuration needs an explicit generated/vendored-source policy before activation.

## Scope

### 1. README information architecture

Keep three standalone README entry points (English, Simplified Chinese, and Traditional Chinese) aligned around the existing seven major capability layers and two expandable example sections. Reorganize them so a first-time user sees, in order:

1. Product statement and current release status.
2. Primary actions: download the latest release, verify the ZIP, install from source, and inspect examples.
3. A 60-second quick start with distinct Release and source-checkout paths.
4. A runtime and capability support matrix for Python, Node.js, Office rendering, Chromium, image providers, and optional modules.
5. A concise product/engine selection guide.
6. Existing architecture, exact-data, validation, safety, provenance, and synchronization explanations.
7. Troubleshooting and documentation navigation.
8. Contribution, security, licensing, and upstream-credit links.

The README will link to the stable `releases/latest` route instead of embedding a version-specific download URL. Static product/style counts remain protected by repository contract tests.

### 2. Community health files

Add narrow, repository-specific files:

- `CONTRIBUTING.md`: development setup, branch and PR process, strict test commands, deterministic package rules, vendored-upstream boundaries, commit hygiene, and license expectations.
- `SECURITY.md`: private vulnerability-reporting path, supported release policy, what evidence to include, credential-redaction rules, and a statement that public issues must not contain secrets or undisclosed vulnerabilities.
- `CODE_OF_CONDUCT.md`: Contributor Covenant-based participation expectations with a repository-owner enforcement contact.
- `.github/CODEOWNERS`: default ownership by `@kwhi6693-web`, with explicit ownership for workflows, packaging scripts, and source-lock/synchronization paths.
- `.github/PULL_REQUEST_TEMPLATE.md`: scope, verification, deterministic-build, security, vendored-source, documentation, and release-impact checks.
- `.github/ISSUE_TEMPLATE/bug_report.yml`: reproducible bug reports with version, installation path, runtime/preflight output, expected/actual behavior, and redaction confirmation.
- `.github/ISSUE_TEMPLATE/feature_request.yml`: problem, desired outcome, product/engine scope, alternatives, and acceptance criteria.
- `.github/ISSUE_TEMPLATE/upstream_sync.yml`: upstream project, release/tag, source evidence, import-path impact, licensing impact, and adapter-risk fields.
- `.github/ISSUE_TEMPLATE/config.yml`: disable blank issues and provide security/reporting contact links.

Templates will not promise response times that the repository cannot guarantee.

### 3. GitHub Actions modernization

Upgrade official actions to the current supported Node.js 24 generations verified from the official GitHub release APIs at implementation time:

- `actions/checkout`
- `actions/setup-python`
- `actions/upload-artifact`

Each action reference will be pinned to a full immutable commit SHA with a trailing version comment. Workflow permissions, job names, triggers, timeouts, and the existing pull-request synchronization safety contract will remain unchanged unless a failing test proves a compatibility adjustment is required.

Repository contract tests will require:

- Full-length SHA pins for every `uses: actions/...` reference.
- Human-readable version comments.
- No reintroduction of the deprecated `checkout@v4`, `setup-python@v5`, or `upload-artifact@v4` references.
- Preservation of the current `verify` status-check name and sync-PR behavior.

### 4. Dependabot policy

Add `.github/dependabot.yml` for the `github-actions` ecosystem only, on a low-noise weekly schedule with a small open-PR limit and conventional commit prefix.

Do not add a general npm update rule for `presentation-studio/engines/baoyu`. Those files are managed by the upstream synchronization and provenance contract, and an independent npm bot would create two competing sources of truth.

### 5. Repository metadata

After the versioned maintenance PR is merged and verified, update GitHub repository metadata through the API:

- Description: a concise bilingual or English discovery-oriented summary within GitHub's length limit.
- Homepage: `https://github.com/kwhi6693-web/presentation-studio/releases/latest`.
- Topics: a focused capability set including `agent-skill`, `ai-agent`, `codex-skill`, `presentation-automation`, `presentation-generator`, `pptx`, `html-slides`, `infographics`, and `diagrams`.
- Private vulnerability reporting: enable it before the security policy directs external reporters to the private advisory form.

Issues remain enabled. Wiki and Discussions are not changed because there is no evidence that either needs migration or activation as part of this update.

## Explicit non-goals

- No `v1.1.2` tag or Release.
- No history rewriting, force push, tag deletion, Release deletion, or branch-rule bypass.
- No merge of Dependabot PR #4 in the documentation/governance PR.
- No manual rewrite of the 34 vendored npm alerts.
- No CodeQL workflow until a separate design defines language selection and vendored/generated exclusions.
- No LFS or package-history migration.
- No internal planning artifacts in repository discovery paths.
- No locally absolute paths, credentials, tokens, or machine-specific runtime paths in committed files.

## Testing strategy

Changes with repository behavior will follow strict RED -> GREEN:

1. Add failing behavioral tests for a standard-library `verify_repository_health.py` boundary validator.
2. Exercise that validator against complete and deliberately broken temporary repository fixtures, covering missing local README link targets, missing community files, malformed Issue Form structure, floating/deprecated official actions, and an over-broad Dependabot ecosystem.
3. Implement the smallest validator that makes those fixture-driven tests pass, then use it against the real repository after the documentation and configuration files are added.
4. Review human-facing README and policy prose directly instead of coupling tests to exact wording.
5. Run the complete unit suite, repository-health verifier, bilingual example verifier, deterministic package build twice, and package verifier.
6. Confirm documentation-only/community files do not change `dist/presentation-studio.zip` or `checksums.sha256`; if workflow/test changes alter the package unexpectedly, stop and diagnose before commit.

Issue Forms will receive deterministic structural validation from the repository-health verifier and full platform validation from GitHub on the draft PR.

## Delivery workflow

1. Work on `chore/repository-modernization` from the verified `v1.1.1` main commit.
2. Commit the approved design separately.
3. After written-spec approval, create an implementation plan under `docs/plans/`.
4. Implement via strict TDD, with explicit path staging and noreply commit authorship.
5. Perform an independent read-only review.
6. Push the branch and create a draft PR targeting `main`.
7. Wait for all authoritative checks and inspect GraphQL review threads.
8. Mark ready and merge only after tests and review are clean under the active main ruleset.
9. Re-run main CI/verification and then update repository metadata through the GitHub API.
10. Report the separate status of Dependabot PR #4 and CodeQL without merging or enabling them in this change.

## Acceptance criteria

- README provides a clear release-first quick start while retaining all existing architecture and example contracts.
- Community Profile recognizes the newly added health files and templates.
- All official actions use current full-SHA pins with readable version comments and no Node.js 20 deprecation annotations.
- Dependabot is configured only for GitHub Actions.
- Repository description, homepage, and topics reflect the project accurately.
- Full tests, six examples, deterministic builds, and package verification pass.
- The packaged ZIP remains deterministic and unchanged unless a scoped product-source change is explicitly approved.
- The maintenance PR contains no vendored npm upgrade, CodeQL activation, new Release, machine path, or secret.
