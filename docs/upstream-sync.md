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

1. Resolve the latest non-draft, non-prerelease GitHub release and dereference its tag to a commit.
2. Classify each source as `current`, `update_available`, or `ahead_of_release`.
3. Download the release archive into a temporary staging directory.
4. Reject absolute paths, traversal, `.git` content, symbolic links, multiple archive roots, or unexpected repository identity.
5. Validate the upstream license before importing anything.
6. Copy only allowlisted paths and restore Presentation Studio-owned adapters.
7. Update source-lock and engine metadata atomically.
8. Run unit tests, example verification, deterministic package build, archive verification, and repository checks.
9. Commit and push only if all gates pass and an actual vendored change exists.

The transaction is fail-closed: a download, archive, path, license, test, packaging, or validation failure prevents all automated commits. The diagnostic report is uploaded as an Actions artifact.

## Commands

Read-only status check:

```bash
python scripts/upstream_sync.py check --json
```

Synchronize all sources and write a machine-readable report:

```bash
python scripts/upstream_sync.py sync --all --report artifacts/upstream-sync-report.json
```

Synchronize one source:

```bash
python scripts/upstream_sync.py sync --source ppt-master --report artifacts/upstream-sync-report.json
```

Run the full local gate:

```bash
python -m unittest discover -s tests -v
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
```

## Event relay

The upstream release relay calls the repository dispatch endpoint with event type `upstream_release`. Store the target repository token only in the relay platform; do not commit it to this repository. The target workflow uses the repository-scoped `GITHUB_TOKEN` and declares only `contents: write`.

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
