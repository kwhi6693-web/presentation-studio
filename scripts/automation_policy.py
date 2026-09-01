#!/usr/bin/env python3
"""Fail-closed policy decisions for trusted PR merge and release automation."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.upstream_sync import load_source_configs, source_managed_paths


AUTOMATION_LABEL = "automation:upstream-sync"
MANUAL_REVIEW_LABEL = "manual-review"
RELEASE_LABELS = frozenset({"release:patch", "release:minor", "release:major"})
REQUIRED_CHECK = "verify"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(
    r"^v(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)$"
)
BRANCH_RE = re.compile(
    r"^automation/sync-(?P<source>ppt-master|guizang-ppt-skill|frontend-slides|baoyu-skills)-.+$"
)
PROTECTED_PATHS = frozenset(
    {
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "SECURITY.md",
        "scripts/automation_policy.py",
        "scripts/upstream_sync.py",
        "scripts/build_package.py",
        "scripts/build_release_checksum.py",
        "scripts/verify_package.py",
        "scripts/verify_examples.py",
        "scripts/verify_repository_health.py",
        "docs/AUTOMATION.md",
    }
)
PROTECTED_PREFIXES = (
    ".github/workflows/",
    ".github/ISSUE_TEMPLATE/",
    ".github/rulesets/",
)
SENSITIVE_FILE_RE = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\..*)?|[^/]*(?:secret|credential|token|password|passwd|private[-_]?key)[^/]*)$"
)


class PolicyError(RuntimeError):
    """A fail-closed policy or API error safe to show in workflow diagnostics."""


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = SEMVER_RE.fullmatch(value)
        if match is None:
            raise PolicyError(f"not a formal semver tag: {value}")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    def bump(self, level: str) -> "SemVer":
        if level == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        if level == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if level == "major":
            return SemVer(self.major + 1, 0, 0)
        raise PolicyError(f"unsupported release level: {level}")

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class PullRequestSnapshot:
    number: int
    state: str
    base_ref: str
    base_repository: str
    head_ref: str
    head_repository: str
    head_sha: str
    author_login: str
    draft: bool
    labels: frozenset[str]
    changed_paths: tuple[str, ...]
    check_runs: tuple[tuple[str, str], ...]
    mergeable: bool | None
    mergeable_state: str
    reviews: tuple[tuple[str, str, str], ...]
    unresolved_review_threads: int
    merged: bool
    merge_commit_sha: str | None
    title: str
    # ``None`` is reserved for in-process policy fixtures.  API snapshots must
    # carry at least one author/committer identity for every PR commit.
    commit_identities: tuple[tuple[str, str], ...] | None = None


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason: str
    source: str | None = None
    release_level: str | None = None
    pr_number: int | None = None
    head_sha: str | None = None


@dataclass(frozen=True)
class ReleaseRecord:
    tag_name: str
    commit_sha: str
    draft: bool
    prerelease: bool


@dataclass(frozen=True)
class TagRecord:
    name: str
    commit_sha: str


@dataclass(frozen=True)
class ReleasePlan:
    state: str
    version: str
    target_commit: str
    previous_version: str | None


def _normalized_path(value: str) -> str:
    candidate = value.replace("\\", "/").strip("/")
    parts = candidate.split("/") if candidate else []
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PolicyError(f"invalid changed path: {value}")
    return "/".join(parts)


def _is_protected_path(path: str) -> bool:
    return (
        path in PROTECTED_PATHS
        or path.startswith(PROTECTED_PREFIXES)
        or SENSITIVE_FILE_RE.search(path) is not None
        or path.endswith((".pem", ".key", ".p12", ".pfx"))
    )


def _allowed_paths(source: str) -> tuple[str, ...]:
    by_name = {item.name: item for item in load_source_configs()}
    try:
        return source_managed_paths(by_name[source])
    except KeyError as error:
        raise PolicyError(f"unknown upstream source: {source}") from error


def _preserved_paths(source: str) -> tuple[str, ...]:
    """Return adapter paths that synchronization deliberately restores unchanged."""

    by_name = {item.name: item for item in load_source_configs()}
    try:
        return tuple(
            f"presentation-studio/{_normalized_path(path)}"
            for path in by_name[source].preserve
        )
    except KeyError as error:
        raise PolicyError(f"unknown upstream source: {source}") from error


def _configured_repository(source: str) -> str:
    configured = {item.name: item.repository for item in load_source_configs()}.get(source)
    if not configured:
        raise PolicyError(f"unknown upstream source: {source}")
    return configured


def _repository_identity(value: str) -> str:
    return value.removesuffix(".git").rstrip("/").lower()


def _release_level(labels: Iterable[str]) -> str:
    matches = RELEASE_LABELS.intersection(labels)
    if len(matches) != 1:
        raise PolicyError("trusted automation PR must have exactly one release label")
    return next(iter(matches)).split(":", 1)[1]


def _source_from_branch(branch: str) -> str | None:
    match = BRANCH_RE.fullmatch(branch)
    return match.group("source") if match else None


def _latest_review_states(
    reviews: Sequence[tuple[str, str, str]],
) -> dict[str, str]:
    latest: dict[str, tuple[str, str]] = {}
    for login, state, submitted_at in reviews:
        current = latest.get(login)
        if current is None or submitted_at >= current[0]:
            latest[login] = (submitted_at, state.upper())
    return {login: state for login, (_, state) in latest.items()}


def _required_check_conclusion(
    check_runs: Sequence[tuple[str, str]], required_check: str
) -> str | None:
    conclusions = [conclusion.lower() for name, conclusion in check_runs if name == required_check]
    if not conclusions:
        return None
    if all(conclusion == "success" for conclusion in conclusions):
        return "success"
    return ",".join(conclusions)


def _identity_decision(
    pr: PullRequestSnapshot,
    *,
    repository: str,
    expected_app_login: str,
) -> PolicyDecision | tuple[str, str]:
    source = _source_from_branch(pr.head_ref)
    if pr.base_ref != "main" or pr.base_repository.lower() != repository.lower():
        return PolicyDecision("ignore", "PR base is not the protected main branch")
    if pr.head_repository.lower() != repository.lower():
        return PolicyDecision("ignore", "PR head is not from the same repository")
    if source is None:
        return PolicyDecision("ignore", "PR branch is not a trusted automation/sync-* branch")
    if pr.author_login.lower() != expected_app_login.lower():
        return PolicyDecision("ignore", "PR author is not the configured trusted GitHub App")
    if pr.commit_identities is not None:
        if not pr.commit_identities or any(
            author.lower() != expected_app_login.lower()
            or committer.lower() != expected_app_login.lower()
            for author, committer in pr.commit_identities
        ):
            return PolicyDecision(
                "block",
                "trusted automation PR contains a commit not authored and committed by the configured GitHub App",
                source=source,
                pr_number=pr.number,
                head_sha=pr.head_sha,
            )
    if AUTOMATION_LABEL not in pr.labels:
        return PolicyDecision(
            "block",
            f"trusted App PR is missing {AUTOMATION_LABEL}",
            source=source,
            pr_number=pr.number,
            head_sha=pr.head_sha,
        )
    if MANUAL_REVIEW_LABEL in pr.labels:
        return PolicyDecision(
            "block",
            f"PR has the fail-closed {MANUAL_REVIEW_LABEL} label",
            source=source,
            pr_number=pr.number,
            head_sha=pr.head_sha,
        )
    try:
        level = _release_level(pr.labels)
    except PolicyError as error:
        return PolicyDecision(
            "block", str(error), source=source, pr_number=pr.number, head_sha=pr.head_sha
        )
    return source, level


def _path_blocker(source: str, changed_paths: Iterable[str]) -> str | None:
    allowed = _allowed_paths(source)
    normalized = tuple(_normalized_path(path) for path in changed_paths)
    if not normalized:
        return "trusted automation PR has no changed files"
    for path in normalized:
        if _is_protected_path(path):
            return f"protected path modified: {path}"
        if any(path == preserved or path.startswith(f"{preserved}/") for preserved in _preserved_paths(source)):
            return f"preserved adapter path modified: {path}"
        if not any(path == root or path.startswith(f"{root}/") for root in allowed):
            return f"path is outside the managed paths for {source}: {path}"
    return None


def evaluate_trusted_pull_request(
    pr: PullRequestSnapshot,
    *,
    repository: str,
    expected_app_login: str,
    required_check: str = REQUIRED_CHECK,
) -> PolicyDecision:
    identity = _identity_decision(
        pr, repository=repository, expected_app_login=expected_app_login
    )
    if isinstance(identity, PolicyDecision):
        return identity
    source, release_level = identity
    common = {
        "source": source,
        "release_level": release_level,
        "pr_number": pr.number,
        "head_sha": pr.head_sha,
    }

    if pr.state.lower() != "open":
        return PolicyDecision("block", "trusted automation PR is not OPEN", **common)
    if pr.draft:
        return PolicyDecision("block", "trusted automation PR is a draft", **common)
    if not COMMIT_RE.fullmatch(pr.head_sha):
        return PolicyDecision("block", "trusted automation PR has an invalid head SHA", **common)
    path_blocker = _path_blocker(source, pr.changed_paths)
    if path_blocker:
        return PolicyDecision("block", path_blocker, **common)
    check = _required_check_conclusion(pr.check_runs, required_check)
    if check != "success":
        return PolicyDecision(
            "block", f"required check {required_check} is not SUCCESS (actual: {check})", **common
        )
    if pr.unresolved_review_threads:
        return PolicyDecision(
            "block",
            f"PR has {pr.unresolved_review_threads} unresolved review thread(s)",
            **common,
        )
    if "CHANGES_REQUESTED" in _latest_review_states(pr.reviews).values():
        return PolicyDecision("block", "PR has an active requested changes review", **common)
    if pr.mergeable_state.lower() == "behind":
        return PolicyDecision("update", "PR branch is behind main and must be updated", **common)
    if pr.mergeable is False or pr.mergeable_state.lower() == "dirty":
        return PolicyDecision("block", "PR has a merge conflict", **common)
    if pr.mergeable is not True:
        return PolicyDecision("block", "GitHub mergeability is unknown", **common)
    if pr.mergeable_state.lower() not in {"clean", "has_hooks"}:
        return PolicyDecision(
            "block", f"PR mergeable state is not clean (actual: {pr.mergeable_state})", **common
        )
    return PolicyDecision("merge", "all trusted upstream merge gates passed", **common)


def evaluate_live_pull_request(
    pr: PullRequestSnapshot,
    *,
    repository: str,
    expected_app_login: str,
    expected_head_sha: str,
    required_check: str = REQUIRED_CHECK,
) -> PolicyDecision:
    """Evaluate a live PR while treating a changed head as a stale event.

    A workflow_run is tied to the head SHA it validated. If a later synchronization
    has already advanced that PR, the old run must become a harmless no-op so the
    newer validation can make the next decision; it must never merge or label-review
    the newer head using stale evidence.
    """
    if pr.head_sha != expected_head_sha:
        return PolicyDecision(
            "ignore",
            "workflow validation is stale because the live PR head SHA has advanced",
            pr_number=pr.number,
            head_sha=pr.head_sha,
        )
    return evaluate_trusted_pull_request(
        pr,
        repository=repository,
        expected_app_login=expected_app_login,
        required_check=required_check,
    )


def _items_by_name(payload: Mapping, collection: str, name_key: str = "name") -> dict[str, dict]:
    items = payload.get(collection)
    if not isinstance(items, list):
        raise PolicyError(f"provenance payload is missing {collection}")
    result: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(name_key), str):
            raise PolicyError(f"provenance payload has an invalid {collection} entry")
        name = item[name_key]
        if name in result:
            raise PolicyError(f"provenance payload has duplicate source: {name}")
        result[name] = item
    return result


def _validate_source_lock_top_level(base_lock: Mapping, head_lock: Mapping) -> None:
    """Keep source-lock schema and import metadata outside the mutable roster."""

    if not isinstance(base_lock, Mapping) or not isinstance(head_lock, Mapping):
        raise PolicyError("source-lock payload is not an object")
    base_metadata = {key: value for key, value in base_lock.items() if key != "sources"}
    head_metadata = {key: value for key, value in head_lock.items() if key != "sources"}
    if base_metadata != head_metadata:
        changed = sorted(
            key
            for key in set(base_metadata) | set(head_metadata)
            if base_metadata.get(key) != head_metadata.get(key)
        )
        raise PolicyError(
            "source-lock top-level invariant changed: "
            + (changed[0] if changed else "metadata")
        )
    for payload in (base_lock, head_lock):
        schema_version = payload.get("schema_version")
        if schema_version is not None and (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 2
        ):
            raise PolicyError("source-lock schema_version is unsupported")
        import_date = payload.get("import_date")
        if import_date is not None and (
            not isinstance(import_date, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", import_date) is None
        ):
            raise PolicyError("source-lock import_date is invalid")


def _validate_manifest_top_level(base_manifest: Mapping, head_manifest: Mapping) -> None:
    """Reject a changed or unsupported engine-manifest top-level schema."""

    if not isinstance(base_manifest, Mapping) or not isinstance(head_manifest, Mapping):
        raise PolicyError("engine manifest payload is not an object")
    base_schema = base_manifest.get("schema_version")
    head_schema = head_manifest.get("schema_version")
    if base_schema != head_schema:
        raise PolicyError("engine manifest top-level schema_version changed")
    for schema_version in (base_schema, head_schema):
        if schema_version is not None and (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise PolicyError("engine manifest schema_version is unsupported")


def _manifest_by_source(payload: Mapping) -> dict[str, tuple[str, dict]]:
    result: dict[str, tuple[str, dict]] = {}
    for key, item in payload.items():
        if key == "schema_version":
            continue
        if not isinstance(key, str) or not isinstance(item, dict):
            raise PolicyError("engine manifest has an invalid entry")
        source = item.get("source_name")
        if not isinstance(source, str) or source in result:
            raise PolicyError("engine manifest has invalid or duplicate source identity")
        result[source] = (key, item)
    return result


def validate_provenance_payloads(
    source: str,
    base_lock: Mapping,
    head_lock: Mapping,
    base_manifest: Mapping,
    head_manifest: Mapping,
) -> dict[str, str]:
    _validate_source_lock_top_level(base_lock, head_lock)
    _validate_manifest_top_level(base_manifest, head_manifest)
    base_sources = _items_by_name(base_lock, "sources")
    head_sources = _items_by_name(head_lock, "sources")
    if set(base_sources) != set(head_sources) or source not in head_sources:
        raise PolicyError("source-lock source roster changed")
    for name in base_sources:
        if name != source and base_sources[name] != head_sources[name]:
            raise PolicyError(f"another source provenance changed: {name}")

    base_item = base_sources[source]
    head_item = head_sources[source]
    # Synchronization is allowed to advance only release identity and audit
    # timestamps.  Every adapter/inventory field is part of the source-lock
    # contract and must remain byte-for-byte stable; otherwise a PR could use
    # the allowed lock file to redirect imports or alter licensing/dependency
    # provenance while still looking like a release update.
    mutable_metadata = frozenset(
        {
            "commit",
            "commit_date",
            "release_commit",
            "release_tag",
            "release_url",
            "release_published_at",
            "checked_at",
            "synced_at",
        }
    )
    for key in sorted(set(base_item) | set(head_item)):
        if key in mutable_metadata or key == "repository":
            continue
        if base_item.get(key) != head_item.get(key):
            raise PolicyError(f"selected source-lock invariant changed: {key}")

    old_commit = base_item.get("commit")
    new_commit = head_item.get("commit")
    release_commit = head_item.get("release_commit")
    old_tag = base_item.get("release_tag")
    new_tag = head_item.get("release_tag")
    old_repository = base_item.get("repository")
    repository = head_item.get("repository")
    release_url = head_item.get("release_url")
    if not all(isinstance(value, str) and value for value in (
        old_commit,
        new_commit,
        release_commit,
        old_tag,
        new_tag,
        old_repository,
        repository,
        release_url,
    )):
        raise PolicyError("selected source provenance is incomplete")
    configured_repository = _configured_repository(source)
    if (
        old_repository != configured_repository
        or repository != configured_repository
        or _repository_identity(old_repository) != _repository_identity(configured_repository)
        or _repository_identity(repository) != _repository_identity(configured_repository)
    ):
        raise PolicyError("selected source provenance does not match the configured upstream")
    configured = {item.name: item for item in load_source_configs()}[source]
    expected_import_rules = [dataclasses.asdict(rule) for rule in configured.imports]
    if ("license" in base_item or "license" in head_item) and head_item.get("license") != configured.expected_license:
        raise PolicyError("selected source provenance license does not match configuration")
    if ("update_policy" in base_item or "update_policy" in head_item) and head_item.get("update_policy") != "latest-stable-release":
        raise PolicyError("selected source provenance update policy is not stable-release")
    if ("import_rules" in base_item or "import_rules" in head_item) and head_item.get("import_rules") != expected_import_rules:
        raise PolicyError("selected source provenance import rules do not match configuration")
    if not COMMIT_RE.fullmatch(old_commit):
        raise PolicyError("source-lock old commit is invalid")
    if not COMMIT_RE.fullmatch(new_commit) or new_commit != release_commit:
        raise PolicyError("source-lock commit and release_commit do not match")
    if ("branch" in base_item or "branch" in head_item) and head_item.get("branch") != "main":
        raise PolicyError("selected source provenance branch is not main")
    if new_commit == old_commit or new_tag == old_tag:
        raise PolicyError("selected source provenance did not advance")
    expected_release_url = f"{repository.removesuffix('.git')}/releases/tag/{new_tag}"
    if release_url != expected_release_url:
        raise PolicyError("source-lock release URL does not match repository and tag")

    base_engines = _manifest_by_source(base_manifest)
    head_engines = _manifest_by_source(head_manifest)
    if set(base_engines) != set(head_engines) or source not in head_engines:
        raise PolicyError("engine manifest source roster changed")
    for name in base_engines:
        if name != source and base_engines[name] != head_engines[name]:
            raise PolicyError(f"another source engine manifest changed: {name}")
    base_key, base_engine = base_engines[source]
    head_key, head_engine = head_engines[source]
    if head_key != base_key:
        raise PolicyError("selected source manifest key changed")
    for key in sorted(set(base_engine) | set(head_engine)):
        if key in {"commit", "release_tag"}:
            continue
        if base_engine.get(key) != head_engine.get(key):
            raise PolicyError(f"selected source manifest invariant changed: {key}")
    if head_engine.get("commit") != new_commit or head_engine.get("release_tag") != new_tag:
        raise PolicyError("selected source manifest does not match source-lock provenance")
    if head_engine.get("source_name") != source:
        raise PolicyError("selected source manifest identity mismatch")

    return {
        "source": source,
        "engine": head_key,
        "repository": repository,
        "old_tag": old_tag,
        "old_commit": old_commit,
        "new_tag": new_tag,
        "new_commit": new_commit,
        "release_url": release_url,
    }


def evaluate_main_release_candidate(
    *,
    conclusion: str,
    event: str,
    head_branch: str,
    head_sha: str,
    pull_requests: Sequence[PullRequestSnapshot],
    repository: str,
    expected_app_login: str,
) -> PolicyDecision:
    if conclusion.lower() != "success" or event != "push" or head_branch != "main":
        return PolicyDecision("ignore", "run is not a successful main validation")
    if not COMMIT_RE.fullmatch(head_sha):
        return PolicyDecision("block", "validated main commit SHA is invalid")
    associated = [
        pr for pr in pull_requests if pr.merged and pr.merge_commit_sha == head_sha
    ]
    if not associated:
        return PolicyDecision("ignore", "validated main commit has no merged pull request")
    if len(associated) != 1:
        return PolicyDecision("block", "validated main commit has ambiguous pull request association")
    pr = associated[0]
    identity = _identity_decision(
        pr, repository=repository, expected_app_login=expected_app_login
    )
    if isinstance(identity, PolicyDecision):
        if identity.action == "block":
            return identity
        return PolicyDecision("ignore", f"merged PR is not trusted automation: {identity.reason}")
    source, release_level = identity
    if pr.draft:
        return PolicyDecision(
            "block",
            "merged trusted automation PR is a draft",
            source,
            release_level,
            pr.number,
            pr.head_sha,
        )
    path_blocker = _path_blocker(source, pr.changed_paths)
    if path_blocker:
        return PolicyDecision(
            "block", path_blocker, source, release_level, pr.number, pr.head_sha
        )
    return PolicyDecision(
        "release",
        "validated main commit belongs to one trusted merged upstream PR",
        source,
        release_level,
        pr.number,
        pr.head_sha,
    )


def plan_semver_release(
    *,
    commit_sha: str,
    release_level: str,
    releases: Sequence[ReleaseRecord],
    tags: Sequence[TagRecord],
) -> ReleasePlan:
    if not COMMIT_RE.fullmatch(commit_sha):
        raise PolicyError("release target commit SHA is invalid")
    tag_map = {tag.name: tag.commit_sha for tag in tags}
    formal: list[tuple[SemVer, ReleaseRecord]] = []
    for release in releases:
        if release.draft or release.prerelease:
            continue
        try:
            version = SemVer.parse(release.tag_name)
        except PolicyError:
            continue
        formal.append((version, release))
        if release.commit_sha == commit_sha:
            if tag_map.get(release.tag_name) != commit_sha:
                raise PolicyError("release/tag target collision for the validated commit")
            return ReleasePlan("complete", release.tag_name, commit_sha, release.tag_name)
    if not formal:
        raise PolicyError("no formal semver Release exists as a version baseline")
    previous_version, previous_release = max(formal, key=lambda item: item[0])
    candidate = str(previous_version.bump(release_level))
    release_by_tag = {release.tag_name: release for release in releases}
    existing_release = release_by_tag.get(candidate)
    existing_tag_target = tag_map.get(candidate)
    if existing_release is not None and existing_release.commit_sha != commit_sha:
        raise PolicyError(f"release version collision: {candidate}")
    if existing_tag_target is not None and existing_tag_target != commit_sha:
        raise PolicyError(f"tag version collision: {candidate}")
    if existing_release is not None:
        if existing_tag_target != commit_sha:
            raise PolicyError(f"release/tag collision: {candidate}")
        state = "resume" if (existing_release.draft or existing_release.prerelease) else "complete"
        return ReleasePlan(state, candidate, commit_sha, str(previous_version))
    state = "resume" if existing_tag_target == commit_sha else "new"
    return ReleasePlan(state, candidate, commit_sha, str(previous_version))


def render_release_notes(
    *,
    version: str,
    pr_number: int,
    pr_title: str,
    provenance: Mapping[str, str],
    artifact_sha256: str,
    evidence_url: str,
) -> str:
    required = (
        "source",
        "repository",
        "old_tag",
        "old_commit",
        "new_tag",
        "new_commit",
        "release_url",
    )
    if any(not isinstance(provenance.get(key), str) or not provenance[key] for key in required):
        raise PolicyError("release notes provenance is incomplete")
    if SEMVER_RE.fullmatch(version) is None:
        raise PolicyError("release notes version is not formal semver")
    if re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None:
        raise PolicyError("release artifact SHA-256 is invalid")
    return "\n".join(
        [
            f"# Presentation Studio {version}",
            "",
            "## Automated upstream synchronization",
            "",
            f"- Merged PR: #{pr_number} — {pr_title}",
            f"- Synchronized source: `{provenance['source']}`",
            f"- Upstream repository: {provenance['repository']}",
            f"- Upstream release: `{provenance['old_tag']}` → [`{provenance['new_tag']}`]({provenance['release_url']})",
            f"- Upstream commit: `{provenance['old_commit']}` → `{provenance['new_commit']}`",
            "",
            "## Verification",
            "",
            "- Post-merge `main` validation: PASS",
            "- Repository health, unit/contract tests, bilingual examples, source provenance, engine manifests, and source lock: PASS",
            "- Two clean package builds were byte-identical and both passed `verify_package.py --smoke`.",
            f"- Artifact SHA-256: `{artifact_sha256}`",
            f"- [GitHub Actions evidence]({evidence_url})",
            "",
        ]
    )


class GitHubApi:
    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise PolicyError("GitHub API read token is missing")
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request(self, path: str, *, method: str = "GET", payload: dict | None = None):
        url = path if path.startswith("https://") else f"{self.api_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "presentation-studio-automation-policy",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise PolicyError(
                f"GitHub API {method} {urllib.parse.urlsplit(url).path} failed with HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise PolicyError(
                f"GitHub API {method} {urllib.parse.urlsplit(url).path} failed"
            ) from error

    def paginate(self, path: str) -> list:
        separator = "&" if "?" in path else "?"
        page = 1
        result: list = []
        while True:
            payload = self.request(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(payload, list):
                raise PolicyError(f"GitHub API pagination returned a non-list for {path}")
            result.extend(payload)
            if len(payload) < 100:
                return result
            page += 1


def _review_thread_count(api: GitHubApi, repository: str, number: int) -> int:
    owner, name = repository.split("/", 1)
    query = """
      query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
        repository(owner:$owner, name:$name) {
          pullRequest(number:$number) {
            reviewThreads(first:100, after:$cursor) {
              nodes { isResolved }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
      }
    """
    cursor: str | None = None
    unresolved = 0
    while True:
        payload = api.request(
            "/graphql",
            method="POST",
            payload={"query": query, "variables": {"owner": owner, "name": name, "number": number, "cursor": cursor}},
        )
        if not isinstance(payload, dict):
            raise PolicyError("GitHub GraphQL review-thread response is not an object")
        if payload.get("errors"):
            raise PolicyError("GitHub GraphQL review-thread query returned errors")
        try:
            threads = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
            nodes = threads["nodes"]
            page_info = threads["pageInfo"]
            if not isinstance(nodes, list) or not isinstance(page_info, dict):
                raise TypeError
            if any(
                not isinstance(node, dict) or not isinstance(node.get("isResolved"), bool)
                for node in nodes
            ):
                raise TypeError
            unresolved += sum(1 for node in nodes if not node["isResolved"])
            if not isinstance(page_info.get("hasNextPage"), bool):
                raise TypeError
        except (KeyError, TypeError) as error:
            raise PolicyError("GitHub GraphQL review-thread response is incomplete") from error
        if not page_info["hasNextPage"]:
            return unresolved
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise PolicyError("GitHub GraphQL review-thread pagination cursor is missing")


def fetch_pull_request_snapshot(
    api: GitHubApi,
    repository: str,
    number: int,
    *,
    include_checks: bool = True,
    include_reviews: bool = True,
) -> PullRequestSnapshot:
    pr = api.request(f"/repos/{repository}/pulls/{number}")
    if not isinstance(pr, dict):
        raise PolicyError("GitHub pull request response is not an object")
    if not isinstance(pr.get("head"), dict) or not isinstance(pr["head"].get("sha"), str):
        raise PolicyError("GitHub pull request response has an invalid head")
    files = api.paginate(f"/repos/{repository}/pulls/{number}/files")
    changed_files = pr.get("changed_files")
    if (
        isinstance(changed_files, bool)
        or not isinstance(changed_files, int)
        or changed_files < 0
    ):
        raise PolicyError("GitHub pull request response has an invalid changed_files count")
    # GitHub caps the pull-request files endpoint at roughly 3,000 entries.
    # Never evaluate a truncated allowlist and accidentally miss a protected
    # or unexpected path.
    if changed_files > 3000:
        raise PolicyError("pull request changed_files exceeds the GitHub files API safety cap")
    if len(files) != changed_files:
        raise PolicyError(
            "GitHub pull request files are incomplete: "
            f"API reports {changed_files}, endpoint returned {len(files)}"
        )
    if any(not isinstance(item, dict) for item in files):
        raise PolicyError("GitHub pull request file response is incomplete")
    if any(
        not isinstance(item.get("filename"), str)
        or not item.get("filename")
        or (item.get("previous_filename") is not None and not isinstance(item.get("previous_filename"), str))
        for item in files
    ):
        raise PolicyError("GitHub pull request file response has an invalid filename")
    commit_count = pr.get("commits")
    if isinstance(commit_count, bool) or not isinstance(commit_count, int) or commit_count < 1:
        raise PolicyError("GitHub pull request response has an invalid commits count")
    commits = api.paginate(f"/repos/{repository}/pulls/{number}/commits")
    if len(commits) != commit_count:
        raise PolicyError(
            "GitHub pull request commits are incomplete: "
            f"API reports {commit_count}, endpoint returned {len(commits)}"
        )
    commit_identities: tuple[tuple[str, str], ...] = ()
    identities: list[tuple[str, str]] = []
    for item in commits:
        if not isinstance(item, dict):
            raise PolicyError("GitHub pull request commit response is incomplete")
        author = item.get("author")
        committer = item.get("committer")
        if (
            not isinstance(author, dict)
            or not isinstance(committer, dict)
            or not isinstance(author.get("login"), str)
            or not author.get("login")
            or not isinstance(committer.get("login"), str)
            or not committer.get("login")
        ):
            raise PolicyError("GitHub pull request commit identity is missing")
        identities.append((author["login"], committer["login"]))
    commit_identities = tuple(identities)
    check_runs: tuple[tuple[str, str], ...] = ()
    reviews: tuple[tuple[str, str, str], ...] = ()
    unresolved = 0
    if include_checks:
        checks = api.request(f"/repos/{repository}/commits/{pr['head']['sha']}/check-runs")
        if not isinstance(checks, dict) or not isinstance(checks.get("check_runs"), list):
            raise PolicyError("GitHub check-run response is incomplete")
        if any(not isinstance(item, dict) for item in checks["check_runs"]):
            raise PolicyError("GitHub check-run response contains an invalid entry")
        ordered = sorted(
            checks.get("check_runs", []),
            key=lambda item: item.get("completed_at") or item.get("started_at") or "",
        )
        check_runs = tuple(
            (str(item.get("name", "")), str(item.get("conclusion") or item.get("status") or ""))
            for item in ordered
        )
    if include_reviews:
        review_payload = api.paginate(f"/repos/{repository}/pulls/{number}/reviews")
        if any(not isinstance(item, dict) for item in review_payload):
            raise PolicyError("GitHub pull request review response is incomplete")
        if any(not isinstance(item.get("user") or {}, dict) for item in review_payload):
            raise PolicyError("GitHub pull request review response has an invalid user")
        reviews = tuple(
            (
                str((item.get("user") or {}).get("login", "")),
                str(item.get("state", "")),
                str(item.get("submitted_at") or ""),
            )
            for item in review_payload
        )
        unresolved = _review_thread_count(api, repository, number)
    try:
        return PullRequestSnapshot(
            number=int(pr["number"]),
            state=str(pr["state"]),
            base_ref=str(pr["base"]["ref"]),
            base_repository=str(pr["base"]["repo"]["full_name"]),
            head_ref=str(pr["head"]["ref"]),
            head_repository=str(pr["head"]["repo"]["full_name"]),
            head_sha=str(pr["head"]["sha"]),
            author_login=str(pr["user"]["login"]),
            draft=bool(pr.get("draft")),
            labels=frozenset(str(item["name"]) for item in pr.get("labels", [])),
            changed_paths=tuple(
                path
                for item in files
                for path in (
                    str(item.get("filename", "")),
                    str(item.get("previous_filename", ""))
                    if item.get("previous_filename")
                    else "",
                )
                if path
            ),
            check_runs=check_runs,
            mergeable=pr.get("mergeable"),
            mergeable_state=str(pr.get("mergeable_state") or "unknown"),
            reviews=reviews,
            unresolved_review_threads=unresolved,
            merged=bool(pr.get("merged")),
            merge_commit_sha=pr.get("merge_commit_sha"),
            title=str(pr.get("title") or ""),
            commit_identities=commit_identities,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PolicyError("GitHub pull request response is incomplete") from error


def fetch_release_inputs(api: GitHubApi, repository: str) -> tuple[tuple[ReleaseRecord, ...], tuple[TagRecord, ...]]:
    tag_payload = api.paginate(f"/repos/{repository}/tags")
    if any(not isinstance(item, dict) for item in tag_payload):
        raise PolicyError("GitHub tag response is incomplete")
    if any(not isinstance(item.get("commit"), dict) for item in tag_payload):
        raise PolicyError("GitHub tag response has an invalid commit")
    tags = tuple(
        TagRecord(str(item.get("name", "")), str(item.get("commit", {}).get("sha", "")))
        for item in tag_payload
    )
    tag_map = {tag.name: tag.commit_sha for tag in tags}
    release_payload = api.paginate(f"/repos/{repository}/releases")
    if any(not isinstance(item, dict) for item in release_payload):
        raise PolicyError("GitHub release response is incomplete")
    releases = tuple(
        ReleaseRecord(
            str(item.get("tag_name", "")),
            tag_map.get(str(item.get("tag_name", "")), ""),
            bool(item.get("draft")),
            bool(item.get("prerelease")),
        )
        for item in release_payload
    )
    return releases, tags


def fetch_associated_pull_requests(
    api: GitHubApi, repository: str, commit_sha: str
) -> tuple[PullRequestSnapshot, ...]:
    associated = api.paginate(f"/repos/{repository}/commits/{commit_sha}/pulls")
    numbers: list[int] = []
    for item in associated:
        try:
            number = int(item["number"])
        except (KeyError, TypeError, ValueError) as error:
            raise PolicyError("associated pull request response is incomplete") from error
        if number not in numbers:
            numbers.append(number)
    return tuple(
        fetch_pull_request_snapshot(
            api, repository, number, include_checks=False, include_reviews=False
        )
        for number in numbers
    )


def _git_json(ref: str, path: str) -> dict:
    process = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if process.returncode != 0:
        raise PolicyError(f"unable to read provenance file from base ref: {path}")
    try:
        return json.loads(process.stdout.lstrip("\ufeff"))
    except json.JSONDecodeError as error:
        raise PolicyError(f"base provenance file is invalid JSON: {path}") from error


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"unable to read JSON: {path.as_posix()}") from error


def verify_checkout_provenance(source: str, base_ref: str, root: Path) -> dict[str, str]:
    lock_path = "presentation-studio/source-lock.json"
    manifest_path = "presentation-studio/engines/manifest.json"
    return validate_provenance_payloads(
        source,
        _git_json(base_ref, lock_path),
        _read_json(root / lock_path),
        _git_json(base_ref, manifest_path),
        _read_json(root / manifest_path),
    )


def _json_record(value) -> dict:
    return dataclasses.asdict(value)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate-pr")
    evaluate.add_argument("--repository", required=True)
    evaluate.add_argument("--pr", type=int, required=True)
    evaluate.add_argument("--expected-app-login", required=True)
    evaluate.add_argument("--expected-head-sha", required=True)
    release = subparsers.add_parser("evaluate-release")
    release.add_argument("--repository", required=True)
    release.add_argument("--expected-app-login", required=True)
    release.add_argument("--conclusion", required=True)
    release.add_argument("--event", required=True)
    release.add_argument("--head-branch", required=True)
    release.add_argument("--head-sha", required=True)
    release.add_argument("--release-target-sha")
    provenance = subparsers.add_parser("verify-provenance")
    provenance.add_argument("--source", required=True)
    provenance.add_argument("--base-ref", required=True)
    provenance.add_argument("--root", type=Path, default=Path.cwd())
    notes = subparsers.add_parser("release-notes")
    notes.add_argument("--version", required=True)
    notes.add_argument("--pr-number", type=int, required=True)
    notes.add_argument("--pr-title", required=True)
    notes.add_argument("--provenance", type=Path, required=True)
    notes.add_argument("--artifact-sha256", required=True)
    notes.add_argument("--evidence-url", required=True)
    notes.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "verify-provenance":
            print(json.dumps(verify_checkout_provenance(args.source, args.base_ref, args.root.resolve()), indent=2))
            return 0
        if args.command == "release-notes":
            notes = render_release_notes(
                version=args.version,
                pr_number=args.pr_number,
                pr_title=args.pr_title,
                provenance=_read_json(args.provenance),
                artifact_sha256=args.artifact_sha256,
                evidence_url=args.evidence_url,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(notes, encoding="utf-8", newline="\n")
            print(json.dumps({"status": "PASS", "output": str(args.output)}, indent=2))
            return 0
        token = os.environ.get("GH_TOKEN", "")
        api = GitHubApi(token)
        if args.command == "evaluate-release":
            pull_requests = fetch_associated_pull_requests(api, args.repository, args.head_sha)
            decision = evaluate_main_release_candidate(
                conclusion=args.conclusion,
                event=args.event,
                head_branch=args.head_branch,
                head_sha=args.head_sha,
                pull_requests=pull_requests,
                repository=args.repository,
                expected_app_login=args.expected_app_login,
            )
            output: dict = {"decision": _json_record(decision)}
            if decision.action == "release":
                release_target_sha = args.release_target_sha or args.head_sha
                if not COMMIT_RE.fullmatch(release_target_sha):
                    raise PolicyError("release target commit SHA is invalid")
                releases, tags = fetch_release_inputs(api, args.repository)
                plan = plan_semver_release(
                    commit_sha=release_target_sha,
                    release_level=decision.release_level or "",
                    releases=releases,
                    tags=tags,
                )
                pr = next(item for item in pull_requests if item.number == decision.pr_number)
                output["plan"] = _json_record(plan)
                output["pull_request"] = {
                    "number": pr.number,
                    "title": pr.title,
                    "head_ref": pr.head_ref,
                    "head_sha": pr.head_sha,
                }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        snapshot = fetch_pull_request_snapshot(api, args.repository, args.pr)
        decision = evaluate_live_pull_request(
            snapshot,
            repository=args.repository,
            expected_app_login=args.expected_app_login,
            expected_head_sha=args.expected_head_sha,
        )
        print(json.dumps(_json_record(decision), ensure_ascii=False, indent=2))
        return 0
    except PolicyError as error:
        print(json.dumps({"action": "error", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
