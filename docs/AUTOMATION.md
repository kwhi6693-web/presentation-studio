# Autonomous Upstream Pull Requests and Releases

Presentation Studio uses a fail-closed automation chain:

```text
upstream detection
  -> source-scoped synchronization
  -> trusted GitHub App pull request
  -> Validate package
  -> live trusted classification
  -> squash merge
  -> Validate package on main
  -> semantic version selection
  -> clean deterministic package build
  -> verified GitHub Release
```

The chain does not bypass the `main` ruleset, remove the required `verify` status,
approve reviews, run untrusted fork code with secrets, or push directly to `main`.

## Why a GitHub App is required

A pull request created or updated with the repository `GITHUB_TOKEN` does not cause
the normal `pull_request` validation chain to run without the GitHub
`action_required` approval state. The upstream synchronizer therefore uses a
dedicated GitHub App installation token for every branch and pull-request mutation.
The App is restricted to this trusted repository automation and is not a general
developer credential.

The App requires only these repository permissions:

- Metadata: read
- Contents: read and write
- Pull requests: read and write

Do not grant Administration, Actions, Workflows, Secrets, Members, or other
permissions. The workflow's ordinary `GITHUB_TOKEN` remains read-only and is used
for GitHub API inspection. The short-lived App installation token is used only for
the authorized writes.

## One-time owner bootstrap

This is the only owner-only setup that repository code cannot perform:

1. In GitHub, create a private GitHub App dedicated to Presentation Studio upstream
   synchronization. Disable webhooks unless the organization separately needs one.
2. Assign exactly the repository permissions listed above and install the App only
   on the `presentation-studio` repository.
3. Generate one private key and store its complete PEM value as the repository
   Actions secret `UPSTREAM_SYNC_APP_PRIVATE_KEY`. Never commit or paste the key into
   an issue, pull request, log, artifact, or variable.
4. Store the App's numeric App ID as the repository Actions variable
   `UPSTREAM_SYNC_APP_ID`.
5. Confirm the repository has the labels `automation:upstream-sync`,
   `release:patch`, `release:minor`, `release:major`, and `manual-review`. The sync
   workflow idempotently creates a missing label with the expected name and then
   reads it back; a failed create/readback stops the run before any branch or PR
   mutation.
6. Run **Sync upstream releases** with `workflow_dispatch` and confirm that its
   credential preflight and GitHub App token steps pass.
7. After a successful bootstrap run, delete the downloaded local private-key file if
   it is no longer needed, or store it in the owner's approved secret manager. Use the
   GitHub App settings to rotate the key immediately if it may have been exposed.

If either value is missing, the workflow fails closed before it changes a branch or
pull request and emits a redacted diagnostic. It never substitutes `GITHUB_TOKEN`, a
PAT, or a fabricated secret.

## Trusted pull-request identity

The synchronizer creates one source-specific branch named
`automation/sync-<source>-<run>-<attempt>` and applies both
`automation:upstream-sync` and `release:patch`. A pull request is eligible for the
trusted path only when current GitHub API state proves all of the following:

- it is open and not a draft;
- its base is `main`;
- its head is in this repository, not a fork;
- its branch starts with `automation/sync-` and identifies one configured source;
- it was created by the configured GitHub App bot;
- every commit in the live PR has the configured App as both API author and
  committer;
- synchronization commits use the App bot user ID-based noreply address
  `<bot-user-id>+<app-slug>[bot]@users.noreply.github.com` so GitHub can attribute
  both identities deterministically;
- it has `automation:upstream-sync` and exactly one semantic-release label;
- its changed paths are limited to that source's allowlist and provenance files;
- the GitHub-reported changed-file count exactly matches the paginated file list
  (large/truncated PRs are rejected), and no symbolic link is present in the
  checked-out tree;
- source lock, engine manifest, release tag, commit, URL, and unchanged-source
  provenance agree; source-lock top-level schema/import date and any manifest
  schema version remain immutable;
- the required `verify` check has succeeded for the exact current head SHA.

The title and body are evidence for maintainers, not trust signals. Human, fork,
ordinary contributor, wrong-base, wrong-branch, or unlabeled pull requests are
ignored by auto merge.

## Merge policy

`.github/workflows/auto-merge-upstream.yml` uses the `workflow_run` event and runs
only after **Validate package** finishes successfully. It queries fresh pull-request,
checks, reviews, review-thread,
mergeability, file, and provenance state instead of trusting an old event payload.

The policy fails closed and applies `manual-review` with a blocker comment when an
otherwise trusted automation pull request has a failed or missing check, conflict,
requested changes, unresolved review thread, unexpected source path, provenance
mismatch, or protected-path change. Protected paths include workflows, repository
governance/rules, security-sensitive automation, token or identity configuration,
and the automation policy itself.

When `main` has advanced and the pull request is behind, the App requests an update
branch operation with the expected head SHA, verifies that the head changed, then
exits. A fresh **Validate package** run must pass before the pull request is evaluated
again. This allows the four independently synchronized sources to converge without
merging a stale validation result.

Immediately before merge, the workflow repeats live policy evaluation and local
source-scope, provenance, and repository-health checks. It then performs an
expected-SHA squash merge through the GitHub API, verifies the merged state and merge
commit, and deletes only the merged automation branch. It never auto-approves.

## Main validation and release policy

Every squash merge creates a new `main` commit, which triggers **Validate package**
again. This main validation is independent of the pull-request result.
`.github/workflows/auto-release.yml` considers a release only after that exact
`main` push run succeeds. It uses the GitHub API to associate the validated commit
with exactly one merged trusted automation pull request; ordinary documentation,
human, direct, ambiguous, or non-release commits are ignored.

Exactly one label controls the semantic version increment:

- `release:patch` increments PATCH and is the upstream-sync default;
- `release:minor` increments MINOR;
- `release:major` increments MAJOR.

The highest published, non-prerelease `vMAJOR.MINOR.PATCH` GitHub Release is the
version baseline. A tag or release collision at a different commit fails closed. A
repeated event for the same commit safely exits, while an interrupted matching draft
or prerelease at the same commit is resumed and promoted to the formal release.
Concurrency is keyed by validated main commit so rapid independent merges do not
replace one another's pending `workflow_run` event. Each run re-queries the latest
formal Release/tag set immediately before publication; bounded collision retries let
the next commit advance to the next semantic version instead of losing its Release.

The release job checks out the exact validated `main` commit on a clean runner and
reruns repository health, unit and contract tests, bilingual examples, source scope,
and provenance. It calls `build_package.py` twice into separate runner-temporary
paths, requires byte-identical ZIPs and checksum records, and runs
`verify_package.py --smoke` against both archives. Package structure, engine
manifests, source lock, licenses, provenance, examples, and archive/source parity are
therefore verified from the release commit rather than from an old tracked ZIP.
Before packaging it also requires `git status --porcelain --untracked-files=all` to be
empty, so generated or untracked runner files cannot enter the public archive. A
repeated event whose formal Release already exists performs a read-only tag, notes,
two-asset, digest, checksum, and package readback; it does not silently skip a
damaged or incomplete existing Release.

The draft Release receives exactly:

- `presentation-studio.zip`
- `presentation-studio.zip.sha256`

Before publication the workflow verifies the tag points to the validated commit,
the two asset names and sizes are exact, and downloaded asset SHA-256 values match
the newly built files. Release notes include the Presentation Studio version, merged
PR number/title, synchronized source, old and new upstream tags/commits, source
provenance, verification summary, artifact checksum, and a GitHub Actions evidence
link.

## Failure and recovery

Any CI, GitHub API, mergeability, review, path, provenance, deterministic-build,
checksum, tag, asset, or publication ambiguity stops the relevant operation. No
failed state is converted into a warning with `continue-on-error`.

For a blocked trusted pull request, inspect its `manual-review` comment and the linked
Actions run. Correct the issue on the automation branch through the trusted sync
workflow or handle it as a normal maintainer-reviewed change. Do not remove the label
and manually rerun with weaker checks.

The legacy automation PR #21 was created with `GITHUB_TOKEN`, had no trusted App
identity labels, and its validation was in `action_required`. It was closed rather than
inherited by this framework. After the App bootstrap succeeds, run a fresh source
synchronization so the GitHub App creates a new trusted PR from current upstream state;
do not reopen or merge the legacy PR.

## Maintainer evidence checklist

For each production change retain or link:

- the pull request and exact head SHA;
- the successful PR **Validate package** run and required `verify` check;
- the auto-merge run, live decision, and squash merge commit;
- the successful post-merge `main` **Validate package** run;
- the auto-release run and GitHub Actions evidence link;
- the Release URL, tag target SHA, two asset names, and verified SHA-256;
- the current active Ruleset showing required `verify`, strict update, and resolved
  review-thread enforcement.
