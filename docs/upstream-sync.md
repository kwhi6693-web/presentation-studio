# Upstream Synchronization

Presentation Studio tracks the latest stable GitHub release of four upstream repositories while preserving local orchestration, adapters, security boundaries, and license obligations.

## Sources and policy

The canonical configuration is [scripts/upstream_sources.json](../scripts/upstream_sources.json); the installed-skill record is [presentation-studio/source-lock.json](../presentation-studio/source-lock.json).

Each source declares:

- `update_policy: latest-stable-release`;
- exact owner/repository identity;
- allowlisted import mappings;
- adapter paths that must be preserved;
- expected license family and vendored license destinations.

Draft and prerelease GitHub releases are ignored. A locked commit newer than the latest release is classified as `ahead_of_release` and is never downgraded automatically.

## Triggers and latency

The GitHub Actions workflow supports three triggers:

- `repository_dispatch`: the near-real-time path. An upstream release relay sends the `upstream_release` event immediately after an official release is published.
- `workflow_dispatch`: manual check or recovery from the Actions interface.
- `schedule`: an hourly polling fallback at minute 17 for missed or delayed events.

GitHub scheduled workflows are best-effort and may be delayed under load. Therefore “immediate” synchronization depends on the `repository_dispatch` relay; the schedule is a recovery mechanism, not a zero-latency guarantee.

## Safe update transaction

1. Select exactly one configured source for the run and resolve its latest non-draft, non-prerelease GitHub release.
2. Dereference the release tag to an immutable commit and classify the selected source as `current`, `update_available`, or `ahead_of_release`.
3. Download the release archive into a temporary staging directory.
4. Reject absolute paths, traversal, `.git` content, symbolic links, multiple archive roots, or unexpected repository identity.
5. Validate the upstream license before importing anything.
6. Copy only allowlisted paths and restore Presentation Studio-owned adapters.
7. Update source-lock and engine metadata atomically.
8. Run repository health before the update and again after the source update, then run unit/contract tests, example verification, two deterministic package builds in runner temporary storage, fresh-extraction package smoke verification, archive/parity verification, and the source-scope gate.
9. If all gates pass and an actual vendored change exists, commit only that source's mapped paths and provenance metadata to a source-specific `automation/sync-<source>-*` branch and open a pull request against `main`.

The transaction is fail-closed: a download, archive, path, license, test, packaging, or validation failure prevents any automated branch push or pull request. The matrix gives each source an independent runner, branch, report, and pull request; `fail-fast: false` prevents one source failure from contaminating the others, while job concurrency serializes only runs for the same source. If a same-source synchronization pull request is already open, the workflow checks out its branch, merges the current `main`, and updates that pull request with a normal non-force push instead of opening a duplicate. A current or ahead-of-release source produces no file changes, commit, or pull request. The diagnostic report is uploaded as a source-named Actions artifact, and the repository ruleset requires the pull request's `verify` check before merge.

Normal upstream pull requests never stage generated release outputs. The workflow stages only the selected source's allowlisted import roots plus `presentation-studio/source-lock.json` and `presentation-studio/engines/manifest.json`; the source-scope command rejects another engine, `dist/presentation-studio.zip`, or `checksums.sha256`.

## Package and release boundary

`build_package.py` and `verify_package.py` accept explicit `--archive` and `--checksum` paths. The synchronization workflow sends both files to `$RUNNER_TEMP`, builds twice, compares the bytes and checksum records, and runs archive/source parity verification before the branch is pushed. This keeps generated package output out of ordinary upstream diffs without weakening the package gate. The tracked `dist/presentation-studio.zip` and `checksums.sha256` remain the source-checkout/release baseline; a formal GitHub Release builds and uploads its colocated ZIP and `.sha256` asset separately.

The PR body records the source, previous and new release/tag/commit, changed-file count, additions/deletions, imported and preserved paths, license/provenance, and the validation workflow URL.

## Environment contract

The repository-wide runtime and dependency contract is maintained in
[docs/dependencies.md](dependencies.md). The synchronization workflow uses the
following runner-provided tools:

- Python 3.11 for the synchronization worker and repository checks;
- Node.js 20.9.0 for fresh-package smoke verification;
- Git for checkout, branch, staging, and push operations;
- Bash, `jq`, and `gh` on Ubuntu for the release transaction and PR update.

These are CI/system capabilities, not undeclared root Python dependencies. The
workflow keeps generated packages and reports under `$RUNNER_TEMP`, and stages only
the source-specific allowlist after all post-update gates pass.

## Commands

Read-only status check for all sources:

```bash
python scripts/upstream_sync.py check --json
```

Read-only status check for one source:

```bash
python scripts/upstream_sync.py check --source ppt-master --json
```

Synchronize exactly one source and write a machine-readable report:

```bash
python scripts/upstream_sync.py sync --source ppt-master --report artifacts/upstream-sync-report.json
```

Verify a changed-file list against one source's allowlist:

```bash
python scripts/upstream_sync.py verify-scope --source ppt-master --paths-file changed-paths.txt
```

Run the full local gate:

```bash
python -m unittest discover -s tests -v
python scripts/verify_examples.py
python scripts/build_package.py \
  --archive "$RUNNER_TEMP/presentation-studio-a.zip" \
  --checksum "$RUNNER_TEMP/presentation-studio-a.zip.sha256" \
  --compare-archive "$RUNNER_TEMP/presentation-studio-b.zip" \
  --compare-checksum "$RUNNER_TEMP/presentation-studio-b.zip.sha256"
python scripts/verify_package.py \
  --archive "$RUNNER_TEMP/presentation-studio-a.zip" \
  --checksum "$RUNNER_TEMP/presentation-studio-a.zip.sha256" \
  --smoke
```

## Event relay

The upstream release relay calls the repository dispatch endpoint with event type `upstream_release`. Store the relay credential only in the relay platform; do not commit it to this repository. Branch and pull-request mutations use a short-lived installation token from the dedicated trusted GitHub App, with only Metadata read, Contents read/write, and Pull requests read/write. The workflow's repository-scoped `GITHUB_TOKEN` is read-only. Neither identity can bypass the `main` ruleset. See [AUTOMATION.md](AUTOMATION.md) for bootstrap, classification, merge, release, and recovery details.

Example event body:

```json
{
  "event_type": "upstream_release",
  "client_payload": {
    "repository": "hugohe3/ppt-master",
    "tag": "v4.6.0"
  }
}
```

The event payload is advisory. The synchronizer still queries GitHub, verifies repository identity, resolves the current stable release, and enforces the local import policy.

## Recovery

- If the workflow fails, download `upstream-sync-report` from the failed Actions run.
- Correct the configuration or compatibility issue on a feature branch; do not bypass validation.
- Run `workflow_dispatch` after the fix.
- If an upstream release is incompatible with the preserved adapter, keep the previous locked commit and document the reason. Do not silently report the new version as synchronized.
