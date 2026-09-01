# Autonomous PR → Merge → Release Design

## Objective

Replace the recursive `GITHUB_TOKEN` upstream-PR identity with a repository-scoped
GitHub App installation identity, then add fail-closed automation that merges only
freshly validated, same-repository upstream synchronization pull requests and releases
only their freshly validated `main` commits.

The active `main` ruleset remains unchanged: changes require a pull request, the
strict `verify` check, and resolved review threads. No workflow may bypass it, push
directly to `main`, auto-approve reviews, or execute untrusted pull-request code with
secrets.

## Audited baseline

- `.github/workflows/sync-upstreams.yml` authenticates branch fetch/push and PR
  create/update with `secrets.GITHUB_TOKEN`. GitHub therefore places the resulting
  `pull_request` runs in `action_required`.
- `.github/workflows/validate.yml` performs the full Python 3.10–3.13 and Windows/Linux
  matrix and exposes the required aggregate check as `verify` for pull requests and
  pushes, including `main`.
- Ruleset `21126467` is active, has no bypass actors, requires strict `verify`, requires
  pull requests, forbids deletion/non-fast-forward updates, and requires resolution of
  review threads.
- The current formal semver series is `v1.0.0` through `v1.2.1`; release assets are a
  deterministic `presentation-studio.zip` and a colocated
  `presentation-studio.zip.sha256`.
- `scripts/upstream_sync.py` already owns the four-source import allowlist, source-lock
  updates, engine-manifest provenance, and `verify-scope` enforcement.
- Open PR #21 was created by `github-actions[bot]`, has no trusted labels, and has two
  `Validate package` runs with conclusion `action_required`. It is legacy identity and
  must not be auto-merged.

## Architecture

### Trusted identity

All privileged repository automation uses a short-lived installation token generated
by `actions/create-github-app-token` pinned to commit
`bcd2ba49218906704ab6c1aa796996da409d3eb1` (`v3.2.0`). The action is restricted to the
current repository and requests only:

- Metadata: read
- Contents: read/write
- Pull requests: read/write

The repository stores `UPSTREAM_SYNC_APP_ID` as an Actions variable and
`UPSTREAM_SYNC_APP_PRIVATE_KEY` as an Actions secret. Every privileged workflow checks
for both before token creation and fails with a redacted diagnostic when either is
missing. The token supplies the git HTTP credential and `GH_TOKEN` for PR mutations.

### Policy boundary

`scripts/automation_policy.py` is a standard-library policy engine with pure functions
for unit tests and a GitHub API adapter for workflows. It validates live PR state,
identity, labels, base/head repository, branch prefix, draft state, required check,
mergeability, review state, review-thread resolution, changed-path scope, source-lock
and engine-manifest provenance, release association, semver bumping, and collision
handling.

The privileged `workflow_run` jobs execute the policy from the trusted default-branch
checkout. They do not checkout PR code until the API-only identity and protected-path
gate passes. A trusted candidate is then checked out at its exact head SHA for the
existing repository-health and upstream source/provenance checks. Fork and ordinary
human PRs are ignored without mutation.

### Merge state machine

`auto-merge-upstream.yml` handles only completed successful `Validate package` runs.
It re-queries the associated PR and check runs. A candidate must be open, non-draft,
same-repository, based on `main`, named `automation/sync-<source>-...`, authored by the
configured App bot, and labeled `automation:upstream-sync` plus exactly one release
label.

Protected workflow/governance/security/identity files and every path outside the
selected source allowlist block merging. Source scope, source-lock and manifest
provenance, repository health, requested-change reviews, unresolved threads, conflicts,
and the live `verify` check all fail closed.

If `mergeable_state` is `behind`, the workflow updates the branch with
`expected_head_sha`, reads back the new head, and exits without merging. The resulting
App-authored synchronization event starts a new `Validate package` run. Once current,
the workflow performs a squash merge, reads the merged PR back, deletes the automation
branch, and confirms the ref is gone.

### Release state machine

`auto-release.yml` handles only successful `Validate package` workflow runs whose event
is `push` and whose head branch is `main`. It resolves pull requests associated with
the exact validated commit and requires one just-merged trusted automation PR. Ordinary
commits and non-release PRs exit without publishing.

The policy resolves formal `vMAJOR.MINOR.PATCH` releases and tags, first detecting an
existing release for the current commit, then applying the PR's `release:patch`,
`release:minor`, or `release:major` label to the highest formal semver release. The
workflow uses a repository-wide concurrency group. Existing matching tag/release state
is idempotent; a matching draft or prerelease is resumed and promoted, while a
tag/release pointing elsewhere is a blocking collision. A workflow run whose live PR
head has advanced beyond its validated SHA is a stale no-op and waits for the newer
validation event.

On a clean runner at the exact validated main SHA, release verification repeats
repository health, the complete unit/contract suite, bilingual examples, two package
builds, byte/checksum equality, and `verify_package.py --smoke` for both archives. It
then writes the basename-only checksum asset, creates the release at the validated SHA,
uploads exactly the ZIP and checksum, and reads back the tag, release, assets, and
server-reported digest.

### Failure behavior

Trusted candidates that fail a merge/release policy gate receive an idempotent
`manual-review` label and a marker-based comment containing the specific blocker and
Actions evidence URL. API or credential failures fail the job. Ordinary contributor
and fork PRs are ignored and never receive privileged comments or labels.

## Test strategy

Tests exercise policy behavior rather than grep-only implementation details. Fixtures
cover trusted success, fork/human/wrong base/wrong branch/missing label, failed verify,
conflict, behind update, protected and unexpected paths, requested changes, unresolved
threads, semver patch/minor/major, tag collision, failed main validation, release
association, idempotency, and deterministic ZIP mismatch. Existing repository health,
package, provenance, source scope, and workflow contract suites remain required.

## Owner bootstrap boundary

Repository code cannot create or install the GitHub App or manufacture its private key.
The only owner bootstrap is: create a private App, grant the three permissions above,
install it only on `kwhi6693-web/presentation-studio`, add the numeric App ID variable and
private-key secret, then run `Sync stable upstream releases` once. No App token or key
is committed.
