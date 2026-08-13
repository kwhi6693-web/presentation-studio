# Lightweight Production and Upstream Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve all Presentation Studio capabilities while adding a route-scoped Fast Path, bilingual expandable product examples, and guarded near-real-time synchronization of four upstream GitHub releases.

**Architecture:** Keep the current 20-layer Skill and four vendored engines. Add dependency-free repository tools for release discovery, policy-driven staging imports, deterministic package building, example verification, and GitHub Actions orchestration; updates enter the stable branch only after the same package and artifact gates used for human releases.

**Tech Stack:** Python 3 standard library, Git, GitHub REST API, GitHub Actions YAML, Markdown, PowerPoint Open XML, standalone HTML, PDF.

## Global Constraints

- Preserve L0-L19, all 13 products, all 8 styles, and all four engines.
- Do not introduce a Python or Node dependency for repository maintenance.
- Treat the latest non-draft, non-prerelease GitHub Release as the stable upstream update signal.
- Never downgrade a vendored commit that already contains the latest release commit.
- Poll every five minutes and accept `repository_dispatch` plus `workflow_dispatch`.
- Fail closed on license, import-path, adapter, test, archive, or provenance errors.
- Keep examples outside the installable `presentation-studio/` tree.
- Use the resolved absolute local runtimes; GitHub Actions may use its configured `python` executable.
- Stage explicit repository paths only; do not stage unrelated work.
- Report renderer-dependent work as PASS only after its real command runs.

---

## File structure

- `scripts/upstream_sync.py`: release discovery, comparison, staging import, lock updates, and CLI.
- `scripts/upstream_sources.json`: declarative source repositories, release policy, import mappings, and preserved adapters.
- `scripts/build_package.py`: deterministic Skill ZIP and checksum builder.
- `scripts/verify_examples.py`: dependency-free PPTX, HTML, PDF, and README example verifier.
- `scripts/verify_package.py`: repository-wide contract gate invoking new metadata and example checks.
- `tests/test_upstream_sync.py`: release and import behavior.
- `tests/test_build_package.py`: deterministic package behavior.
- `tests/test_repository_contract.py`: README, Fast Path, workflow, source-lock, and examples.
- `.github/workflows/sync-upstreams.yml`: five-minute, dispatch, guarded sync, validation, and atomic publish.
- `.github/workflows/validate.yml`: package, unit-test, and example gate.
- `presentation-studio/references/fast-path.md`: route-scoped fast-production contract.
- `presentation-studio/SKILL.md`: Fast Path selection and progressive-loading rules.
- `presentation-studio/source-lock.json`: stable release and importer metadata.
- `presentation-studio/engines/manifest.json`: synchronized immutable engine commits.
- `docs/architecture.md`: detailed L0-L19 architecture.
- `docs/upstream-sync.md`: operator and failure-recovery guide.
- `examples/bilingual-acceptance/{zh,en}/`: three products per language.
- `README.md`: concise bilingual project entry with seven major layers and two expandable showcases.

---

### Task 1: Repository contract tests

**Files:**
- Create: `tests/test_repository_contract.py`
- Modify later: `README.md`, `presentation-studio/SKILL.md`, `.github/workflows/sync-upstreams.yml`

**Interfaces:**
- Consumes: repository-relative paths only.
- Produces: a standard-library `unittest` suite that defines the public repository contract.

- [ ] **Step 1: Write the failing contract tests**

```python
class RepositoryContractTests(unittest.TestCase):
    def test_readme_shows_seven_major_layers_and_two_expandable_showcases(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        for marker in MAJOR_LAYER_MARKERS:
            self.assertIn(marker, text)
        self.assertEqual(text.count("<details>"), 2)
        for relative_path in SIX_EXAMPLE_PATHS:
            self.assertIn(relative_path, text)

    def test_fast_path_preserves_complete_workflow_escalations(self):
        skill = (ROOT / "presentation-studio" / "SKILL.md").read_text(encoding="utf-8-sig")
        fast_path = (ROOT / "presentation-studio" / "references" / "fast-path.md").read_text(encoding="utf-8-sig")
        for term in ["Fast Path", "exact data", "animation", "narration", "PASS"]:
            self.assertIn(term, skill + fast_path)

    def test_sync_workflow_has_all_triggers_and_fail_closed_permissions(self):
        workflow = (ROOT / ".github" / "workflows" / "sync-upstreams.yml").read_text(encoding="utf-8")
        for term in ["repository_dispatch", "workflow_dispatch", "schedule", "2/5", "contents: write", "concurrency"]:
            self.assertIn(term, workflow)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_repository_contract -v`

Expected: FAIL because the examples, Fast Path reference, and sync workflow do not exist and the README still exposes the old 20-row structure.

- [ ] **Step 3: Commit the failing tests**

```bash
git add -- tests/test_repository_contract.py
git commit -m "test: define lightweight repository contract"
```

---

### Task 2: Deterministic package builder

**Files:**
- Create: `tests/test_build_package.py`
- Create: `scripts/build_package.py`
- Modify: `scripts/verify_package.py`

**Interfaces:**
- Produces: `build_archive(skill_root: Path, archive_path: Path) -> str`, returning a lowercase SHA-256 digest.
- Produces: CLI `python scripts/build_package.py` that writes `dist/presentation-studio.zip` and `checksums.sha256`.

- [ ] **Step 1: Write failing deterministic-package tests**

```python
def test_build_archive_is_reproducible(tmp_path):
    skill = tmp_path / "presentation-studio"
    (skill / "nested").mkdir(parents=True)
    (skill / "SKILL.md").write_text("hello\n", encoding="utf-8")
    (skill / "nested" / "中文.txt").write_text("ok\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    first_sha = build_archive(skill, first)
    second_sha = build_archive(skill, second)
    assert first_sha == second_sha
    assert first.read_bytes() == second.read_bytes()
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_build_package -v`

Expected: ERROR importing `scripts.build_package`.

- [ ] **Step 3: Implement the deterministic builder**

Use sorted POSIX member names, fixed ZIP timestamp `(1980, 1, 1, 0, 0, 0)`, explicit UTF-8 filenames, `ZIP_DEFLATED`, and exclusion of `__pycache__`, `.pyc`, and `.pyo`. Write the checksum as:

```text
<lowercase sha256>  dist/presentation-studio.zip
```

- [ ] **Step 4: Run package tests and the current package verifier**

Run:

```bash
python -m unittest tests.test_build_package -v
python scripts/build_package.py
python scripts/verify_package.py
```

Expected: PASS and identical hashes across two consecutive builds.

- [ ] **Step 5: Commit**

```bash
git add -- tests/test_build_package.py scripts/build_package.py scripts/verify_package.py dist/presentation-studio.zip checksums.sha256
git commit -m "build: add deterministic presentation package"
```

---

### Task 3: Release discovery and update classification

**Files:**
- Create: `scripts/upstream_sources.json`
- Create: `scripts/upstream_sync.py`
- Create: `tests/test_upstream_sync.py`
- Modify: `presentation-studio/source-lock.json`

**Interfaces:**
- Produces: `ReleaseInfo(tag: str, commit: str, url: str, published_at: str)`.
- Produces: `discover_latest_release(source: SourceConfig, opener: Callable) -> ReleaseInfo`.
- Produces: `classify_update(locked_commit: str, release: ReleaseInfo, compare: Callable) -> str`, returning `current`, `update_available`, or `ahead_of_release`.
- Produces: CLI `check --json`, with one status object per source and exit 0 for current/update-available states, nonzero only for discovery errors.

- [ ] **Step 1: Write failing discovery tests**

Cover latest stable release selection, draft/prerelease rejection, malformed payloads, rate-limit errors, equal commits, later release commits, and locked commits that are descendants of the released commit.

```python
def test_draft_and_prerelease_are_rejected():
    with self.assertRaises(SyncError):
        parse_release({"draft": True, "prerelease": False, "tag_name": "v9", "target_commitish": "abc"})

def test_locked_descendant_is_not_downgraded():
    result = classify_update("newer-lock", RELEASE, lambda base, head: "ahead")
    self.assertEqual(result, "ahead_of_release")
```

- [ ] **Step 2: Run discovery tests and verify RED**

Run: `python -m unittest tests.test_upstream_sync.ReleaseDiscoveryTests -v`

Expected: ERROR because `scripts.upstream_sync` does not exist.

- [ ] **Step 3: Implement discovery and check mode**

Use `urllib.request`, GitHub API version headers, optional `GITHUB_TOKEN`, a 30-second timeout, and redacted exceptions. Resolve tag commits through `git ls-remote` or the GitHub Git-ref endpoint; do not trust a branch-like `target_commitish` as the immutable commit.

- [ ] **Step 4: Extend the source lock schema**

For every source add `update_policy`, `release_tag`, `release_url`, `release_commit`, `checked_at`, `synced_at`, `import_rules`, and `vendored_license_paths`. Preserve the current `commit` as the vendored truth.

- [ ] **Step 5: Run discovery tests and live read-only check**

Run:

```bash
python -m unittest tests.test_upstream_sync.ReleaseDiscoveryTests -v
python scripts/upstream_sync.py check --json
```

Expected: tests PASS; live output identifies PPT Master v4.6.0 as an update and does not propose downgrading an already-ahead source.

- [ ] **Step 6: Commit**

```bash
git add -- tests/test_upstream_sync.py scripts/upstream_sync.py scripts/upstream_sources.json presentation-studio/source-lock.json
git commit -m "feat: detect stable upstream releases"
```

---

### Task 4: Guarded staging importer

**Files:**
- Modify: `tests/test_upstream_sync.py`
- Modify: `scripts/upstream_sync.py`
- Modify: `scripts/upstream_sources.json`
- Modify: `presentation-studio/engines/manifest.json`
- Modify on actual sync: declared engine paths under `presentation-studio/engines/`

**Interfaces:**
- Produces: `stage_source_update(repository_root: Path, source: SourceConfig, release: ReleaseInfo, archive: Path) -> SyncResult`.
- Produces: `SyncResult` with changed paths, preserved adapter paths, old/new commits, licenses, and validation findings.
- Produces: CLI `sync --source <name>|--all --report <path>`.

- [ ] **Step 1: Write failing importer tests**

Use temporary ZIP fixtures and real filesystem assertions for path traversal rejection, missing import paths, replace/merge mappings, adapter preservation, license mismatch, no-change idempotence, and atomic failure.

```python
def test_missing_declared_import_path_leaves_destination_unchanged(self):
    before = tree_hash(self.destination)
    with self.assertRaises(SyncError):
        stage_source_update(self.root, self.source, self.release, self.bad_archive)
    self.assertEqual(tree_hash(self.destination), before)
```

- [ ] **Step 2: Run importer tests and verify RED**

Run: `python -m unittest tests.test_upstream_sync.StagingImporterTests -v`

Expected: FAIL because staging import is not implemented.

- [ ] **Step 3: Implement safe extraction and staging**

Reject absolute paths, `..`, backslashes, symlinks, repository metadata, and members outside the single GitHub archive root. Apply declared mappings to a temporary copy of `presentation-studio/`; preserve adapter paths from that copy; validate all mapped sources before replacing the working tree.

- [ ] **Step 4: Implement atomic application and metadata updates**

Only after the staged tree passes structure, license, route/reference, and source-lock checks, replace declared destination paths and update both engine manifest and source lock. Write the report before returning.

- [ ] **Step 5: Run all upstream tests**

Run: `python -m unittest tests.test_upstream_sync -v`

Expected: PASS with the working tree unchanged by fixture tests.

- [ ] **Step 6: Commit**

```bash
git add -- tests/test_upstream_sync.py scripts/upstream_sync.py scripts/upstream_sources.json presentation-studio/engines/manifest.json
git commit -m "feat: stage upstream updates safely"
```

---

### Task 5: Fast Path Skill behavior

**Files:**
- Create: `presentation-studio/references/fast-path.md`
- Modify: `presentation-studio/SKILL.md`
- Modify: `presentation-studio/agents/openai.yaml`
- Test: `tests/test_repository_contract.py`
- Evidence: `docs/evidence/fast-path-baseline.md`, `docs/evidence/fast-path-forward.md`

**Interfaces:**
- Consumes: existing preflight, recommend, exact-data, route, engine, and QA stages.
- Produces: an observable Fast Path decision and explicit escalation predicates.

- [ ] **Step 1: Run a fresh-context baseline without the new guidance**

Scenario: “Create a five-slide bilingual strategy deck as editable PPTX, standalone HTML, and PDF within a short deadline; the brief is complete; use one generated hero image; do not ask routine questions.” Record whether the worker loads unrelated manuals, duplicates manifests, skips a renderer gate, or claims completion without real checks.

- [ ] **Step 2: Verify the existing contract test remains RED**

Run: `python -m unittest tests.test_repository_contract.RepositoryContractTests.test_fast_path_preserves_complete_workflow_escalations -v`

Expected: FAIL because `fast-path.md` does not exist.

- [ ] **Step 3: Write the minimum Fast Path guidance**

Define entry predicates, the six-stage route-scoped sequence, exact escalation predicates, one-manifest reuse, and truthful PASS/PARTIAL/FAIL semantics. Keep root guidance concise and put details in `references/fast-path.md`.

- [ ] **Step 4: Run the same fresh-context scenario with the updated Skill**

Expected: the worker resolves runtimes first, selects the dual-format route, loads only Guizang/Baoyu/PPT Master/Frontend references required for the request, shares manifests, and retains both native and browser QA.

- [ ] **Step 5: Run the repository contract test**

Run: `python -m unittest tests.test_repository_contract.RepositoryContractTests.test_fast_path_preserves_complete_workflow_escalations -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -- presentation-studio/SKILL.md presentation-studio/references/fast-path.md presentation-studio/agents/openai.yaml docs/evidence/fast-path-baseline.md docs/evidence/fast-path-forward.md tests/test_repository_contract.py
git commit -m "feat: add route-scoped presentation fast path"
```

---

### Task 6: Bilingual examples and artifact verifier

**Files:**
- Create: `examples/bilingual-acceptance/zh/presentation-acceptance-zh.{pptx,html,pdf}`
- Create: `examples/bilingual-acceptance/en/presentation-acceptance-en.{pptx,html,pdf}`
- Create: `scripts/verify_examples.py`
- Modify: `tests/test_repository_contract.py`

**Interfaces:**
- Produces: `verify_pptx`, `verify_html`, `verify_pdf`, and `verify_all` returning structured findings and a process exit status.

- [ ] **Step 1: Add failing example-verifier tests**

Assert exact six-product roster; PPTX ZIP integrity, five slides, notes, native chart/table, and transition; HTML single-file structure, five slides, language, keyboard/edit/offline tokens, and no remote asset URLs; PDF five-page count and 16:9 media box.

- [ ] **Step 2: Run and verify RED**

Run: `python -m unittest tests.test_repository_contract.ExampleContractTests -v`

Expected: FAIL because examples and verifier do not exist.

- [ ] **Step 3: Copy the six accepted products**

Copy only the native PowerPoint PDF, editable PPTX, and standalone HTML for each language from the 2026-08-13 acceptance outputs. Do not copy web PDFs into the product showcase.

- [ ] **Step 4: Implement the dependency-free verifier**

Use `zipfile` and XML parsing for PPTX; text/URL scanning for HTML; PDF object scanning for `/Type /Page` and `/MediaBox`. Print one JSON summary and fail on any missing product or contract mismatch.

- [ ] **Step 5: Run example tests and verifier**

Run:

```bash
python -m unittest tests.test_repository_contract.ExampleContractTests -v
python scripts/verify_examples.py
```

Expected: six products PASS; motion video remains outside this six-file contract.

- [ ] **Step 6: Commit**

```bash
git add -- examples/bilingual-acceptance scripts/verify_examples.py tests/test_repository_contract.py
git commit -m "docs: add verified bilingual presentation examples"
```

---

### Task 7: README and technical documentation

**Files:**
- Modify: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/upstream-sync.md`
- Modify: `scripts/verify_package.py`

**Interfaces:**
- Produces: a concise bilingual entry page, detailed architecture reference, and update operator guide.

- [ ] **Step 1: Confirm README contract test is RED**

Run: `python -m unittest tests.test_repository_contract.RepositoryContractTests.test_readme_shows_seven_major_layers_and_two_expandable_showcases -v`

Expected: FAIL.

- [ ] **Step 2: Rewrite the README around major layers**

Lead with rapid high-quality production, show the seven-layer table and a compact flow, keep upstream attribution visible, add two `<details>` showcases with exact six links, then installation, Fast Path, update status, boundaries, and licensing. Avoid duplicating L0-L19 rows.

- [ ] **Step 3: Add detailed architecture and sync guides**

Move the L0-L19 definitions to `docs/architecture.md`. Document check, sync, failure artifact, permissions, dispatch, polling latency, no-downgrade behavior, and rollback in `docs/upstream-sync.md`.

- [ ] **Step 4: Extend package verification**

Require the two docs, Fast Path reference, upstream policy, six examples, and two expandable showcases. Invoke the example verifier from the package gate.

- [ ] **Step 5: Run documentation and package gates**

Run:

```bash
python -m unittest tests.test_repository_contract -v
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -- README.md docs/architecture.md docs/upstream-sync.md scripts/verify_package.py dist/presentation-studio.zip checksums.sha256
git commit -m "docs: present major capabilities and update operations"
```

---

### Task 8: GitHub synchronization automation

**Files:**
- Create: `.github/workflows/sync-upstreams.yml`
- Modify: `.github/workflows/validate.yml`
- Modify: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: `upstream_sync.py`, `build_package.py`, `verify_package.py`, and the standard-library tests.
- Produces: scheduled/manual/event-driven upstream maintenance and one atomic verified commit.

- [ ] **Step 1: Confirm workflow contract test is RED**

Run: `python -m unittest tests.test_repository_contract.RepositoryContractTests.test_sync_workflow_has_all_triggers_and_fail_closed_permissions -v`

Expected: FAIL because the workflow does not exist.

- [ ] **Step 2: Add the sync workflow**

Use `cron: "2/5 * * * *"`, `repository_dispatch` type `upstream_release`, manual source input, `concurrency` with cancellation, `contents: write`, read-only checkout before sync, full tests and package build before commit, explicit staged paths, and an uploaded diagnostic artifact on failure.

- [ ] **Step 3: Enhance validation workflow**

Run `python -m unittest discover -s tests -v`, `python scripts/verify_examples.py`, and `python scripts/verify_package.py` on push and pull request.

- [ ] **Step 4: Run workflow contract and YAML text checks**

Run: `python -m unittest tests.test_repository_contract -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -- .github/workflows/sync-upstreams.yml .github/workflows/validate.yml tests/test_repository_contract.py
git commit -m "ci: synchronize verified upstream releases"
```

---

### Task 9: Synchronize current upstream releases

**Files:**
- Modify: changed declared engine paths under `presentation-studio/engines/`
- Modify: `presentation-studio/source-lock.json`
- Modify: `presentation-studio/engines/manifest.json`
- Modify: `THIRD_PARTY_NOTICES.md` when release metadata changes
- Modify: `dist/presentation-studio.zip`, `checksums.sha256`

**Interfaces:**
- Consumes: the completed guarded importer and live GitHub release metadata.
- Produces: a source-locked release tree with no downgrade and full provenance.

- [ ] **Step 1: Run live check and archive the report**

Run: `python scripts/upstream_sync.py check --json > docs/evidence/upstream-check-2026-08-13.json`

Expected: a valid status for all four sources; PPT Master reports v4.6.0 update availability.

- [ ] **Step 2: Run guarded synchronization**

Run: `python scripts/upstream_sync.py sync --all --report docs/evidence/upstream-sync-2026-08-13.json`

Expected: changed released sources update; already-ahead sources remain unchanged and record the latest release metadata.

- [ ] **Step 3: Rebuild and run complete local gates**

Run:

```bash
python -m unittest discover -s tests -v
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
```

Expected: PASS; any engine regression stops the update for repair instead of publishing partial engine bytes.

- [ ] **Step 4: Commit the atomic upstream update**

```bash
git add -- presentation-studio/engines presentation-studio/source-lock.json THIRD_PARTY_NOTICES.md docs/evidence/upstream-check-2026-08-13.json docs/evidence/upstream-sync-2026-08-13.json dist/presentation-studio.zip checksums.sha256
git commit -m "chore: synchronize verified upstream releases"
```

---

### Task 10: Repository audit, local installation, and GitHub publication

**Files:**
- Modify only files with evidenced findings from the final audit.
- Install from: `presentation-studio/`
- Publish branch: `codex/lightweight-upstream-sync`

**Interfaces:**
- Produces: clean verified Git history, recoverable installed Skill, pushed GitHub branch, and remote CI evidence.

- [ ] **Step 1: Run the full verification ledger**

Run unit discovery, example verification, two consecutive deterministic builds, package verification, Python compile checks for repository-owned scripts, `git diff --check`, local Markdown-link checks, secret-pattern scan, unsafe archive scan, and Git status inspection.

- [ ] **Step 2: Inspect every changed file and repository-level finding**

Confirm no accidental upstream deletions, license drift, generated cache, untracked build output, unrelated edits, broken README links, or example mismatch. Make only finding-backed repairs and rerun the affected gate.

- [ ] **Step 3: Install with recoverable backup**

Run the existing Windows installer with `-Force`, then compare every installed non-cache file by path and SHA-256 against `presentation-studio/`.

- [ ] **Step 4: Re-run installed Fast Path probes**

Run resolver, preflight, recommend, and route probes for a quick bilingual dual-format deck, an exact-data PPTX, an HTML presenter, and an image product. Confirm the expected engine chains and truthful readiness status.

- [ ] **Step 5: Commit any final audit repairs**

Stage only the named repaired paths, run cached diff checks, and commit with an audit-specific message.

- [ ] **Step 6: Push the feature branch**

Run: `git push -u origin codex/lightweight-upstream-sync`

Expected: one new remote branch at the locally verified commit.

- [ ] **Step 7: Verify remote repository and Actions**

Read the remote branch, workflow runs, commit tree, README example links, and downloadable six products. Report a remote limitation as PARTIAL rather than claiming publication succeeded.

---

## Plan self-review

- Spec coverage: every objective, major layer, Fast Path rule, update trigger, no-downgrade rule, safe importer, examples, documentation, local installation, and GitHub publication has a task.
- Placeholder scan: the plan contains no deferred implementation markers.
- Type consistency: release, source configuration, status, staging, and archive interfaces use the same names across producing and consuming tasks.
- Scope: one integrated repository release; no unrelated engine redesign or speculative automation is included.
