# Presentation Studio Lightweight Production and Upstream Sync Design

Date: 2026-08-13
Status: approved in conversation on 2026-08-13

## Objective

Keep every existing Presentation Studio capability and all 20 detailed functional layers while making the normal generation path faster, easier to understand, and cheaper in context. Add an automated GitHub update path that detects new formal releases from the four upstream authors, synchronizes the selected source material, reruns the complete release gate, and publishes only a verified update.

The repository README will describe the system through seven major capability layers. The detailed L0-L19 architecture remains authoritative in a separate technical document.

## Evidence and packaging decision

The following work is recurrent and worth extending in the existing Skill:

| Repeated workflow | Evidence | Decision |
|---|---|---|
| Bilingual PPTX, HTML, and PDF production | Integrated system work on 2026-08-11 and real Chinese/English artifact acceptance on 2026-08-13 | Extend Presentation Studio with a lightweight fast path and reusable examples |
| Native PowerPoint plus browser QA | Structural audit on 2026-08-11 and PowerPoint/Edge acceptance on 2026-08-13 | Preserve as the release-quality gate |
| Folder, ZIP, installed copy, and provenance parity | Repeated release and installation verification on 2026-08-11 and 2026-08-13 | Extend the verifier and CI |
| Upstream version review and import | Four source locks already exist; PPT Master advanced beyond its locked source before this design | Add automated release detection and guarded synchronization |

A separate new Skill would duplicate existing routing and provenance logic. A custom subagent would not provide the persistent GitHub behavior required. A GitHub automation plus an extension to the existing Skill is the smallest complete form.

## Preserved architecture

The implementation must not remove products, style profiles, engines, exact-data contracts, presenter behavior, animations, images, or QA rules. The L0-L19 architecture remains intact:

- L0-L7: invocation, intake, normalization, runtime resolution, preflight, product retrieval, style inference, and compatibility;
- L8-L10: exact-data contracts, routing, and engine adaptation;
- L11-L13: narrative, visual systems, and assets;
- L14-L15: native generation, export, and presenter runtime;
- L16-L18: observation, QA, repair, and fallback;
- L19: security, provenance, and status.

Upstream release synchronization is repository maintenance around these layers, not a replacement layer and not a fifth rendering engine.

## README information architecture

The README will lead with the short-time-to-quality value proposition and show these seven major capability layers:

1. Intelligent understanding and product decisions.
2. Data contracts and four-engine orchestration.
3. Content and visual production.
4. Native multi-format generation.
5. Rendered acceptance and repair loops.
6. Security, provenance, and honest status.
7. Continuous upstream synchronization.

Each layer receives a concise explanation of its purpose, key inputs, outputs, and responsible upstream strengths. The README will not repeat all 20 implementation rows. A linked architecture document will retain that detail.

The README will contain two collapsible product showcases, Chinese and English. Each contains exactly three user-facing example products:

- editable PPTX;
- standalone interactive HTML;
- portable PDF exported from the native PowerPoint path.

The existing acceptance report remains repository evidence but is not counted as a showcase product. The HTML files are offered as downloads because GitHub does not execute repository HTML inside the README.

## Lightweight execution path

The root Skill will expose a deterministic Fast Path for complete briefs and short-deadline requests. It will:

1. run the mandatory runtime resolution, preflight, recommendation, and route stages;
2. load only references and engines selected by the route;
3. reuse one content manifest and one asset manifest across formats;
4. generate only requested deliverables;
5. run the smallest real quality gate capable of supporting the final status;
6. escalate to the complete workflow whenever exact data, template reconstruction, advanced animation, narration, complex provider work, or unresolved ambiguity requires it.

Fast Path changes context and execution scope, not output truthfulness. It cannot skip a required renderer, data comparison, or selected-engine validator and still report PASS.

## Upstream release policy

The source of update truth is the latest non-draft, non-prerelease GitHub Release for each upstream repository. Tags are used to resolve the immutable commit for that release. Default-branch commits are reported as available development changes but are not automatically vendored unless a source explicitly changes to a branch-tracking policy in `source-lock.json`.

This distinction prevents unpublished work on an upstream default branch from silently entering the stable Skill while satisfying the requirement to synchronize immediately after an author publishes a formal latest version.

Every source-lock entry will record:

- update policy and upstream repository;
- release tag and release URL;
- immutable commit;
- discovery and synchronization timestamps;
- selected import paths;
- license and vendored license paths;
- adapter or transformation applied by Presentation Studio.

## Detection and synchronization

GitHub Actions will provide three triggers:

- `repository_dispatch` for immediate webhook-style release notification;
- `workflow_dispatch` for manual recovery or a targeted source update;
- a five-minute schedule as the fastest native GitHub Actions polling fallback.

Scheduled workflows can be delayed by GitHub. Therefore “immediate” means event-driven when an upstream or relay sends `repository_dispatch`; otherwise detection occurs at the next available five-minute poll.

The update workflow will use repository-standard Python because the repository already uses dependency-free Python for package verification and all required filesystem, ZIP, JSON, hashing, and GitHub API operations are available without introducing another runtime dependency. GitHub Actions YAML will provide orchestration.

The update pipeline is:

1. query the four upstream release endpoints;
2. compare release tags and commits with `source-lock.json`;
3. exit successfully without changes when every source is current;
4. clone changed sources at immutable release commits into a temporary directory;
5. import only each source's declared module paths;
6. preserve Presentation Studio adapters and reapply declared deterministic transformations;
7. update provenance, notices, release metadata, and the source lock;
8. rebuild the distributable ZIP and checksum;
9. run the full repository and package gate;
10. publish one atomic synchronization commit only when all gates pass.

Concurrent runs will share one cancellation group so an older run cannot overwrite a newer release. A failed update leaves the default branch unchanged and uploads a diagnostic artifact containing the source, old and new versions, import phase, and failing gate.

## Update safety and rollback

Automatic synchronization is fail-closed. It must stop on:

- missing or renamed declared import paths;
- license changes or missing license files;
- unsupported release metadata;
- adapter patch failures;
- unexpected executable or repository metadata;
- unresolved route/reference changes;
- test, package, archive, or example verification failures;
- a dirty generated tree after rebuilding.

The stable repository is updated only after validation succeeds. Each source update remains traceable to an immutable upstream commit, so rollback is a normal Git revert of the atomic synchronization commit. No updater is allowed to edit an installed local Skill during a GitHub run.

## Local update behavior

The repository will include a read-only check command and an explicit synchronization command. Check mode performs no writes and reports `current`, `update_available`, or `error` per source. Sync mode uses the same importer and release gates as CI.

The installed local Skill is updated through the existing recoverable installer after the repository package passes. The installer continues to move the previous installation to a timestamped sibling backup before replacement.

## Verification

Implementation follows test-driven development. Required test groups are:

- release response parsing, including draft, prerelease, missing release, rate-limit, and malformed response cases;
- version and commit comparison for all four sources;
- update-policy and source-lock schema validation;
- selected-path import and adapter preservation;
- license and provenance failure cases;
- no-change idempotence and concurrent-run safety;
- README major-layer and six-product showcase checks;
- PPTX package, notes, animation, chart, and table checks for both languages;
- standalone HTML, keyboard, offline, browser-console, and print checks for both languages;
- PDF page-count and geometry checks for both languages;
- complete folder-to-ZIP hash parity and installer smoke tests.

Native rendering and browser checks remain PASS only when their real commands run. Motion video regression may remain PARTIAL when no animation capture is produced, and that boundary must be reported rather than hidden.

## Publishing boundary

Human-authored implementation changes will be developed on a feature branch, reviewed through the full gate, then pushed to GitHub under the user's existing authorization. The completed repository update will include the updated Skill, automation, documentation, examples, release archive, checksum, and local installed copy.

Future automated upstream updates may write one atomic commit to the default branch only after every declared gate passes. If repository protection or token policy prevents that write, the workflow must preserve the tested update branch and report PARTIAL rather than bypass protection.
