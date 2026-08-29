#!/usr/bin/env python3
"""Discover and safely synchronize Presentation Studio upstream releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().with_name("upstream_sources.json")
SOURCE_LOCK_PATH = REPOSITORY_ROOT / "presentation-studio" / "source-lock.json"
GITHUB_API = "https://api.github.com"
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_GITHUB_JSON_ATTEMPTS = 3
GITHUB_RETRY_BACKOFF_SECONDS = 1.0
MAX_GITHUB_RETRY_DELAY_SECONDS = 5.0
GIT_ANCESTRY_DEEPEN_STEPS = (32, 128, 512)
GIT_COMMAND_TIMEOUT_SECONDS = 120


class SyncError(RuntimeError):
    """A redacted, user-actionable upstream synchronization failure."""


class GitHubApiError(SyncError):
    """A redacted terminal GitHub API failure with machine-readable context."""

    def __init__(
        self,
        message: str,
        status: int,
        response_message: str | None,
        status_history: tuple[int, ...],
    ) -> None:
        super().__init__(message)
        self.status = status
        self.response_message = response_message
        self.status_history = status_history


class JsonClient(Protocol):
    def get_json(self, path: str) -> dict: ...


@dataclass(frozen=True)
class ImportRule:
    source: str
    destination: str
    mode: str


@dataclass(frozen=True)
class SourceConfig:
    name: str
    owner: str
    repository_name: str
    repository: str
    expected_license: str
    imports: tuple[ImportRule, ...]
    preserve: tuple[str, ...]
    license_candidates: tuple[str, ...] = ("LICENSE",)

    @classmethod
    def from_mapping(cls, payload: dict) -> "SourceConfig":
        try:
            imports = tuple(ImportRule(**item) for item in payload["imports"])
            return cls(
                name=str(payload["name"]),
                owner=str(payload["owner"]),
                repository_name=str(payload["repository_name"]),
                repository=str(payload["repository"]),
                expected_license=str(payload["expected_license"]),
                imports=imports,
                preserve=tuple(str(item) for item in payload.get("preserve", [])),
                license_candidates=tuple(
                    str(item) for item in payload.get("license_candidates", ["LICENSE"])
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SyncError("Invalid upstream source configuration") from error


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    commit: str
    url: str
    published_at: str


@dataclass(frozen=True)
class SyncResult:
    source: str
    old_commit: str | None
    new_commit: str
    old_tree_hash: str
    new_tree_hash: str
    changed_paths: tuple[str, ...]
    preserved_paths: tuple[str, ...]
    managed_paths: tuple[str, ...] = ()


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        timeout: int = 30,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._sleeper = sleeper

    @staticmethod
    def _is_release_discovery_path(path: str) -> bool:
        return (
            path.endswith("/releases/latest")
            or "/git/ref/tags/" in path
            or "/git/tags/" in path
        )

    @staticmethod
    def _retry_after(error: urllib.error.HTTPError) -> float | None:
        value = error.headers.get("Retry-After") if error.headers else None
        try:
            delay = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(delay) or delay < 0:
            return None
        return min(delay, MAX_GITHUB_RETRY_DELAY_SECONDS)

    @staticmethod
    def _retry_delay(attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return retry_after
        return min(
            GITHUB_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)),
            MAX_GITHUB_RETRY_DELAY_SECONDS,
        )

    @staticmethod
    def _response_message(error: urllib.error.HTTPError) -> str | None:
        try:
            payload = json.loads(error.read(4096).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        message = payload.get("message") if isinstance(payload, dict) else None
        return message if isinstance(message, str) else None

    def get_json(self, path: str) -> dict:
        if not path.startswith("/"):
            raise SyncError("GitHub API path must be absolute")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "presentation-studio-upstream-sync",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(f"{GITHUB_API}{path}", headers=headers)
        http_status_history: list[int] = []
        for attempt in range(1, MAX_GITHUB_JSON_ATTEMPTS + 1):
            retry_after: float | None = None
            api_status: int | None = None
            response_message: str | None = None
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as error:
                api_status = error.code
                http_status_history.append(error.code)
                response_message = self._response_message(error)
                category = f"HTTP {error.code}"
                retryable = error.code == 429 or error.code >= 500 or (
                    error.code == 404 and self._is_release_discovery_path(path)
                )
                retry_after = self._retry_after(error) if retryable else None
            except (urllib.error.URLError, TimeoutError, OSError):
                category = "transport error"
                retryable = True
            except (json.JSONDecodeError, UnicodeError):
                category = "invalid JSON response"
                retryable = True
            else:
                if isinstance(payload, dict):
                    return payload
                category = "unexpected JSON payload"
                retryable = True

            if retryable and attempt < MAX_GITHUB_JSON_ATTEMPTS:
                self._sleeper(self._retry_delay(attempt, retry_after))
                continue
            message = (
                f"terminal {category} after {attempt} "
                f"attempt{'s' if attempt != 1 else ''}"
            )
            if api_status is not None:
                raise GitHubApiError(
                    message,
                    api_status,
                    response_message,
                    tuple(http_status_history),
                )
            raise SyncError(message)
        raise AssertionError("GitHub retry loop exited unexpectedly")

    def download(self, path: str, destination: Path) -> None:
        if not path.startswith("/"):
            raise SyncError("GitHub download path must be absolute")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "presentation-studio-upstream-sync",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(f"{GITHUB_API}{path}", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response, destination.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output)
        except urllib.error.HTTPError as error:
            raise SyncError(f"GitHub archive download failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SyncError("GitHub archive download failed") from error


def _valid_commit(value: object) -> bool:
    return isinstance(value, str) and COMMIT_PATTERN.fullmatch(value) is not None


def parse_release(payload: dict, resolved_commit: str) -> ReleaseInfo:
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise SyncError("Latest GitHub release is not a stable published release")
    tag = payload.get("tag_name")
    url = payload.get("html_url")
    published_at = payload.get("published_at")
    if not all(isinstance(value, str) and value.strip() for value in (tag, url, published_at)):
        raise SyncError("GitHub release metadata is incomplete")
    if not _valid_commit(resolved_commit):
        raise SyncError("GitHub release tag did not resolve to an immutable commit")
    return ReleaseInfo(tag=tag, commit=resolved_commit.lower(), url=url, published_at=published_at)


def _discovery_json(source: SourceConfig, operation: str, client: JsonClient, path: str) -> dict:
    try:
        return client.get_json(path)
    except SyncError as error:
        raise SyncError(f"source {source.name}; {operation}; {error}") from error


def _tag_commit(source: SourceConfig, tag: str, client: JsonClient) -> str:
    encoded_tag = urllib.parse.quote(tag, safe="")
    reference = _discovery_json(
        source,
        "resolve release tag",
        client,
        f"/repos/{source.owner}/{source.repository_name}/git/ref/tags/{encoded_tag}"
    )
    obj = reference.get("object") if isinstance(reference, dict) else None
    for _ in range(5):
        if not isinstance(obj, dict):
            break
        object_type = obj.get("type")
        sha = obj.get("sha")
        if object_type == "commit" and _valid_commit(sha):
            return str(sha).lower()
        if object_type != "tag" or not _valid_commit(sha):
            break
        tag_object = _discovery_json(
            source,
            "resolve annotated release tag",
            client,
            f"/repos/{source.owner}/{source.repository_name}/git/tags/{sha}"
        )
        obj = tag_object.get("object") if isinstance(tag_object, dict) else None
    raise SyncError(f"Release tag for {source.name} did not resolve to a commit")


def discover_latest_release(source: SourceConfig, client: JsonClient) -> ReleaseInfo:
    payload = _discovery_json(
        source,
        "discover latest release",
        client,
        f"/repos/{source.owner}/{source.repository_name}/releases/latest",
    )
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or not tag.strip():
        raise SyncError(f"Latest release for {source.name} has no tag")
    return parse_release(payload, _tag_commit(source, tag, client))


def classify_update(
    locked_commit: str,
    release: ReleaseInfo,
    compare: Callable[[str, str], str],
) -> str:
    if not _valid_commit(locked_commit):
        raise SyncError("Locked source commit is invalid")
    if locked_commit.lower() == release.commit.lower():
        return "current"
    relation = compare(release.commit, locked_commit.lower())
    if relation in {"ahead", "identical"}:
        return "ahead_of_release"
    if relation in {"behind", "diverged"}:
        return "update_available"
    raise SyncError(f"Unsupported GitHub comparison status: {relation}")


def load_source_configs(path: Path = CONFIG_PATH) -> tuple[SourceConfig, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        sources = tuple(SourceConfig.from_mapping(item) for item in payload["sources"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SyncError("Unable to load upstream source configuration") from error
    if len(sources) != 4 or len({source.name for source in sources}) != len(sources):
        raise SyncError("Upstream source configuration must contain four unique sources")
    return sources


def select_sources(
    sources: tuple[SourceConfig, ...],
    names: list[str],
    *,
    require_single: bool = False,
) -> tuple[SourceConfig, ...]:
    """Return the requested sources, optionally enforcing one-source execution."""

    if require_single and len(names) != 1:
        raise SyncError("Synchronization requires exactly one upstream source")
    if len(names) != len(set(names)):
        raise SyncError("Upstream source selection contains duplicates")
    if not names:
        return sources

    configured = {source.name: source for source in sources}
    unknown = sorted(set(names) - set(configured))
    if unknown:
        raise SyncError(f"Unknown upstream source: {unknown[0]}")
    return tuple(configured[name] for name in names)


def _normalized_repository_path(path: str) -> str:
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise SyncError(f"Invalid repository path in upstream configuration: {path}")
    return pure.as_posix()


def source_managed_paths(source: SourceConfig) -> tuple[str, ...]:
    """Return the only repository path roots a source synchronization may change."""

    paths = {
        "presentation-studio/source-lock.json",
        "presentation-studio/engines/manifest.json",
    }
    for rule in source.imports:
        paths.add(f"presentation-studio/{_normalized_repository_path(rule.destination)}")
    for preserved in source.preserve:
        paths.add(f"presentation-studio/{_normalized_repository_path(preserved)}")
    return tuple(sorted(paths))


def validate_source_paths(source: SourceConfig, paths: list[str] | tuple[str, ...]) -> None:
    """Fail closed when a diff contains another source or a generated release output."""

    managed = source_managed_paths(source)
    prohibited = {"dist/presentation-studio.zip", "checksums.sha256"}
    for raw_path in paths:
        path = _normalized_repository_path(raw_path)
        if path in prohibited:
            raise SyncError(f"Generated release output is not allowed in an upstream PR: {path}")
        if not any(path == root or path.startswith(f"{root}/") for root in managed):
            raise SyncError(
                f"Path outside the managed paths for {source.name}: {path}"
            )


def source_pr_title(source: SourceConfig, release: ReleaseInfo) -> str:
    return f"chore(upstream): update {source.name} to {release.tag}"


def render_pr_body(
    report: dict,
    *,
    changed_file_count: int,
    additions: int,
    deletions: int,
    workflow_url: str,
) -> str:
    """Render factual, source-specific evidence for an upstream synchronization PR."""

    if report.get("status") != "PASS" or not report.get("changed"):
        raise SyncError("Cannot render a PR body for a non-changing synchronization report")
    sources = report.get("sources")
    applied = report.get("applied")
    if not isinstance(sources, list) or len(sources) != 1:
        raise SyncError("A synchronization PR report must contain exactly one source result")
    if not isinstance(applied, list) or len(applied) != 1:
        raise SyncError("A synchronization PR report must contain exactly one applied result")

    source_result = sources[0]
    applied_result = applied[0]
    if not isinstance(source_result, dict) or not isinstance(applied_result, dict):
        raise SyncError("Synchronization PR report has an invalid source result")
    source_name = source_result.get("name")
    release = source_result.get("release")
    if not isinstance(source_name, str) or not isinstance(release, dict):
        raise SyncError("Synchronization PR report is missing release identity")
    old_commit = source_result.get("locked_commit")
    old_tag = source_result.get("locked_release_tag") or "not recorded"
    new_tag = release.get("tag")
    new_commit = release.get("commit")
    release_url = release.get("url")
    if not all(isinstance(value, str) and value for value in (old_commit, new_tag, new_commit, release_url)):
        raise SyncError("Synchronization PR report has incomplete release provenance")

    changed_paths = applied_result.get("changed_paths", [])
    preserved_paths = applied_result.get("preserved_paths", [])
    repository = applied_result.get("repository")
    license_name = applied_result.get("license")
    if not isinstance(changed_paths, list) or not isinstance(preserved_paths, list):
        raise SyncError("Synchronization PR report has invalid path evidence")
    if not isinstance(repository, str) or not isinstance(license_name, str):
        raise SyncError("Synchronization PR report is missing license or repository evidence")

    def path_lines(paths: list[str]) -> str:
        return "\n".join(f"- `{path}`" for path in paths) or "- None"

    return "\n".join(
        [
            "## Verified upstream synchronization",
            "",
            f"- Source: `{source_name}`",
            f"- Upstream repository: {repository}",
            f"- Previous release/tag: `{old_tag}` (`{old_commit}`)",
            f"- New release/tag: [`{new_tag}`]({release_url}) (`{new_commit}`)",
            f"- Changed files: {changed_file_count} files (+{additions} / -{deletions})",
            "",
            "### Imported and preserved paths",
            "",
            "Imported/updated:",
            path_lines(changed_paths),
            "",
            "Presentation Studio adapters preserved:",
            path_lines(preserved_paths),
            "",
            "### Verification",
            "",
            "- Repository health, unit/contract tests, bilingual examples, deterministic package build, archive parity, and source scope gate: PASS",
            f"- License: `{license_name}` (verified before import)",
            "- Provenance recorded in `presentation-studio/source-lock.json` and `presentation-studio/engines/manifest.json`.",
            f"- Workflow evidence: {workflow_url}",
            "",
            "The pull request contains only this source's allowlisted upstream content and provenance metadata. Generated release ZIP/checksum files are intentionally excluded; a formal Release builds them separately.",
            "",
        ]
    )


def load_source_lock(path: Path = SOURCE_LOCK_PATH) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError("Unable to load source-lock.json") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise SyncError("source-lock.json has an invalid structure")
    return payload


def _github_api_error(error: SyncError) -> GitHubApiError | None:
    cause = error.__cause__
    return cause if isinstance(cause, GitHubApiError) else None


def _is_no_common_ancestor_error(error: SyncError, base: str, head: str) -> bool:
    cause = _github_api_error(error)
    return (
        cause is not None
        and cause.status == 404
        and cause.response_message == f"No common ancestor between {base} and {head}."
    )


def _is_exhausted_server_error(error: SyncError) -> bool:
    cause = _github_api_error(error)
    return (
        cause is not None
        and len(cause.status_history) == MAX_GITHUB_JSON_ATTEMPTS
        and all(500 <= status < 600 for status in cause.status_history)
    )


def _confirm_repository_commit(
    source: SourceConfig,
    operation: str,
    commit: str,
    client: JsonClient,
) -> None:
    payload = _discovery_json(
        source,
        operation,
        client,
        f"/repos/{source.owner}/{source.repository_name}/commits/{commit}",
    )
    resolved = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(resolved, str) or resolved.lower() != commit.lower():
        raise SyncError(
            f"source {source.name}; {operation}; "
            "GitHub commit response did not match requested commit"
        )


def _confirm_compare_commits(
    source: SourceConfig,
    base: str,
    head: str,
    client: JsonClient,
) -> None:
    _confirm_repository_commit(
        source,
        "confirm latest release commit exists",
        base,
        client,
    )
    _confirm_repository_commit(
        source,
        "confirm locked commit exists",
        head,
        client,
    )


def _git_subprocess_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
        and key.upper()
        not in {
            "GITHUB_TOKEN",
            "UPSTREAM_GITHUB_TOKEN",
            "SSH_ASKPASS",
            "SSH_AUTH_SOCK",
        }
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "SSH_ASKPASS_REQUIRE": "never",
        }
    )
    return environment


def _run_git(
    repository: Path,
    arguments: list[str],
    *,
    initialized: bool = True,
) -> subprocess.CompletedProcess[str]:
    repository_arguments = (
        ["--git-dir", str(repository / ".git"), "--work-tree", str(repository)]
        if initialized
        else ["-C", str(repository)]
    )
    return subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "core.askPass=",
            *repository_arguments,
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_git_subprocess_environment(),
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def _require_git_success(
    source: SourceConfig,
    result: subprocess.CompletedProcess[str],
    operation: str,
) -> None:
    if result.returncode != 0:
        raise SyncError(f"source {source.name}; local Git ancestry fallback; {operation}")


def _git_repository_is_shallow(source: SourceConfig, repository: Path) -> bool:
    result = _run_git(repository, ["rev-parse", "--is-shallow-repository"])
    _require_git_success(source, result, "unable to inspect shallow repository state")
    state = result.stdout.strip()
    if state not in {"true", "false"}:
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; "
            "invalid shallow repository state"
        )
    return state == "true"


def _git_ancestry_relation(
    source: SourceConfig,
    repository: Path,
    base: str,
    head: str,
) -> str | None:
    release_ancestor = _run_git(repository, ["merge-base", "--is-ancestor", base, head])
    if release_ancestor.returncode == 0:
        return "ahead"
    if release_ancestor.returncode != 1:
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; "
            "release ancestry check failed"
        )

    locked_ancestor = _run_git(repository, ["merge-base", "--is-ancestor", head, base])
    if locked_ancestor.returncode == 0:
        return "behind"
    if locked_ancestor.returncode != 1:
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; "
            "locked ancestry check failed"
        )

    merge_base = _run_git(repository, ["merge-base", base, head])
    if merge_base.returncode == 0:
        return "diverged"
    if merge_base.returncode != 1:
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; merge-base check failed"
        )
    if not _git_repository_is_shallow(source, repository):
        return "diverged"
    return None


def _fetch_git_commits(
    source: SourceConfig,
    repository: Path,
    base: str,
    head: str,
    depth_argument: str,
) -> None:
    result = _run_git(
        repository,
        [
            "fetch",
            "--quiet",
            "--no-tags",
            "--filter=blob:none",
            depth_argument,
            "upstream",
            base,
            head,
        ],
    )
    _require_git_success(source, result, "git fetch failed")


def _local_git_compare_status(source: SourceConfig, base: str, head: str) -> str:
    if not _valid_commit(base) or not _valid_commit(head):
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; invalid commit SHA"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="presentation-upstream-git-") as temporary:
            repository = Path(temporary)
            _require_git_success(
                source,
                _run_git(repository, ["init", "--quiet"], initialized=False),
                "git init failed",
            )
            _require_git_success(
                source,
                _run_git(repository, ["remote", "add", "upstream", source.repository]),
                "git remote setup failed",
            )
            _fetch_git_commits(source, repository, base, head, "--depth=1")
            for commit in (base, head):
                _require_git_success(
                    source,
                    _run_git(repository, ["cat-file", "-e", f"{commit}^{{commit}}"]),
                    "fetched commit validation failed",
                )

            relation = _git_ancestry_relation(source, repository, base, head)
            for deepen_by in GIT_ANCESTRY_DEEPEN_STEPS:
                if relation is not None:
                    return relation
                _fetch_git_commits(
                    source,
                    repository,
                    base,
                    head,
                    f"--deepen={deepen_by}",
                )
                relation = _git_ancestry_relation(source, repository, base, head)
            if relation is not None:
                return relation

            _fetch_git_commits(source, repository, base, head, "--unshallow")
            relation = _git_ancestry_relation(source, repository, base, head)
            if relation is None:
                raise SyncError(
                    f"source {source.name}; local Git ancestry fallback; "
                    "unable to determine ancestry"
                )
            return relation
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as error:
        raise SyncError(
            f"source {source.name}; local Git ancestry fallback; git execution failed"
        ) from error


def _compare_status(source: SourceConfig, base: str, head: str, client: JsonClient) -> str:
    try:
        payload = _discovery_json(
            source,
            "compare latest release with locked commit",
            client,
            f"/repos/{source.owner}/{source.repository_name}/compare/{base}...{head}"
        )
    except SyncError as error:
        no_common_ancestor = _is_no_common_ancestor_error(error, base, head)
        exhausted_server_error = _is_exhausted_server_error(error)
        if not no_common_ancestor and not exhausted_server_error:
            raise
        _confirm_compare_commits(source, base, head, client)
        if no_common_ancestor:
            return "diverged"
        return _local_git_compare_status(source, base, head)
    status = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(status, str):
        raise SyncError(f"GitHub comparison for {source.name} has no status")
    return status


def check_sources(
    sources: tuple[SourceConfig, ...],
    source_lock: dict,
    client: JsonClient,
) -> list[dict]:
    locks = {item.get("name"): item for item in source_lock["sources"] if isinstance(item, dict)}
    results: list[dict] = []
    for source in sources:
        locked = locks.get(source.name)
        if not isinstance(locked, dict):
            raise SyncError(f"Missing source lock for {source.name}")
        locked_commit = locked.get("commit")
        if not isinstance(locked_commit, str):
            raise SyncError(f"Missing locked commit for {source.name}")
        release = discover_latest_release(source, client)
        status = classify_update(
            locked_commit,
            release,
            lambda base, head, current=source: _compare_status(current, base, head, client),
        )
        results.append(
            {
                "name": source.name,
                "status": status,
                "locked_commit": locked_commit,
                "locked_release_tag": locked.get("release_tag"),
                "locked_release_commit": locked.get("release_commit"),
                "repository": source.repository,
                "expected_license": source.expected_license,
                "release": asdict(release),
            }
        )
    return results


def tree_hash(root: Path) -> str:
    """Return a stable hash of every file path and byte in a tree."""

    if not root.is_dir():
        raise SyncError(f"Tree does not exist: {root}")
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_members(archive: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    infos = archive.infolist()
    if not infos:
        raise SyncError("Upstream archive is empty")
    roots: set[str] = set()
    accepted: list[zipfile.ZipInfo] = []
    for info in infos:
        name = info.filename
        pure = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or pure.is_absolute()
            or ".." in pure.parts
            or not pure.parts
            or ".git" in pure.parts
        ):
            raise SyncError(f"Unsafe upstream archive path: {name}")
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and (unix_mode & 0o170000) == 0o120000:
            raise SyncError(f"Symbolic links are not allowed in upstream archives: {name}")
        roots.add(pure.parts[0])
        accepted.append(info)
    if len(roots) != 1:
        raise SyncError("Upstream archive must have exactly one root directory")
    return next(iter(roots)), accepted


def _extract_archive(archive_path: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            root_name, infos = _safe_archive_members(archive)
            for info in infos:
                pure = PurePosixPath(info.filename)
                target = destination.joinpath(*pure.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except (OSError, zipfile.BadZipFile) as error:
        raise SyncError("Unable to read upstream release archive") from error
    return destination / root_name


def _license_matches(expected: str, text: str) -> bool:
    normalized = " ".join(text.upper().split())
    expected_upper = expected.upper()
    if expected_upper == "MIT":
        return "MIT LICENSE" in normalized
    if expected_upper == "AGPL-3.0":
        return "GNU AFFERO GENERAL PUBLIC LICENSE" in normalized
    return expected_upper in normalized


def _verify_upstream_license(upstream_root: Path, source: SourceConfig) -> None:
    for candidate in source.license_candidates:
        path = upstream_root / Path(candidate)
        if path.is_file():
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if not _license_matches(source.expected_license, text):
                raise SyncError(f"License changed for {source.name}")
            return
    raise SyncError(f"License file is missing for {source.name}")


def _copy_item(source_path: Path, destination_path: Path) -> None:
    if source_path.is_dir():
        shutil.copytree(source_path, destination_path, copy_function=shutil.copy2)
    elif source_path.is_file():
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
    else:
        raise SyncError(f"Declared upstream import path is missing: {source_path}")


def _remove_item(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _locked_commit(repository_root: Path, source_name: str) -> str | None:
    path = repository_root / "presentation-studio" / "source-lock.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    for item in payload.get("sources", []):
        if isinstance(item, dict) and item.get("name") == source_name:
            commit = item.get("commit")
            return commit if isinstance(commit, str) else None
    return None


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _release_metadata(source: SourceConfig, release: ReleaseInfo, checked_at: str) -> dict:
    return {
        "update_policy": "latest-stable-release",
        "release_tag": release.tag,
        "release_url": release.url,
        "release_commit": release.commit,
        "release_published_at": release.published_at,
        "checked_at": checked_at,
        "import_rules": [asdict(rule) for rule in source.imports],
    }


def _update_staged_metadata(
    staged_skill: Path,
    source: SourceConfig,
    release: ReleaseInfo,
    synchronized_at: str,
) -> None:
    lock_path = staged_skill / "source-lock.json"
    manifest_path = staged_skill / "engines" / "manifest.json"
    if not lock_path.is_file() or not manifest_path.is_file():
        return
    try:
        source_lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError("Unable to update staged provenance metadata") from error

    matched_lock = False
    for item in source_lock.get("sources", []):
        if isinstance(item, dict) and item.get("name") == source.name:
            item.update(_release_metadata(source, release, synchronized_at))
            item["commit"] = release.commit
            item["commit_date"] = release.published_at
            item["synced_at"] = synchronized_at
            matched_lock = True
            break
    if not matched_lock:
        raise SyncError(f"Staged source lock is missing {source.name}")

    matched_manifest = False
    for item in manifest.values():
        if isinstance(item, dict) and item.get("source_name") == source.name:
            item["commit"] = release.commit
            item["release_tag"] = release.tag
            matched_manifest = True
            break
    if not matched_manifest:
        raise SyncError(f"Engine manifest is missing {source.name}")

    _write_json(lock_path, source_lock)
    _write_json(manifest_path, manifest)


def record_release_metadata(
    repository_root: Path,
    source: SourceConfig,
    release: ReleaseInfo,
    checked_at: str,
) -> None:
    lock_path = repository_root / "presentation-studio" / "source-lock.json"
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError("Unable to record release metadata") from error
    for item in payload.get("sources", []):
        if isinstance(item, dict) and item.get("name") == source.name:
            metadata = _release_metadata(source, release, checked_at)
            stable_metadata = {
                key: value for key, value in metadata.items() if key != "checked_at"
            }
            if all(item.get(key) == value for key, value in stable_metadata.items()):
                return
            item.update(metadata)
            _write_json(lock_path, payload)
            return
    raise SyncError(f"Source lock is missing {source.name}")


def stage_source_update(
    repository_root: Path,
    source: SourceConfig,
    release: ReleaseInfo,
    archive_path: Path,
) -> SyncResult:
    """Stage, validate, and atomically apply one source update."""

    repository_root = repository_root.resolve()
    skill_root = repository_root / "presentation-studio"
    if not skill_root.is_dir() or not (skill_root / "SKILL.md").is_file():
        raise SyncError("Repository has no installable presentation-studio tree")
    if not source.imports:
        raise SyncError(f"No import rules are declared for {source.name}")

    old_hash = tree_hash(skill_root)
    old_commit = _locked_commit(repository_root, source.name)
    # Keep the staging root short. Repository worktrees can already be close to
    # Win32 MAX_PATH, and nesting the complete upstream archive below them makes
    # otherwise valid release members impossible to extract on Windows.
    with tempfile.TemporaryDirectory(prefix="presentation-upstream-stage-") as temporary:
        temporary_root = Path(temporary)
        upstream_root = _extract_archive(archive_path, temporary_root / "upstream")
        _verify_upstream_license(upstream_root, source)

        staged_skill = temporary_root / "presentation-studio"
        shutil.copytree(skill_root, staged_skill, copy_function=shutil.copy2)
        preserved: dict[str, Path] = {}
        for relative_name in source.preserve:
            existing = staged_skill / Path(relative_name)
            if not existing.exists():
                raise SyncError(f"Declared adapter path is missing: {relative_name}")
            preserved_path = temporary_root / "preserved" / Path(relative_name)
            _copy_item(existing, preserved_path)
            preserved[relative_name] = preserved_path

        changed_paths: list[str] = []
        for rule in source.imports:
            if rule.mode != "replace":
                raise SyncError(f"Unsupported import mode for {source.name}: {rule.mode}")
            source_path = upstream_root / Path(rule.source)
            destination_path = staged_skill / Path(rule.destination)
            if not source_path.exists():
                raise SyncError(f"Declared upstream import path is missing: {rule.source}")
            _remove_item(destination_path)
            _copy_item(source_path, destination_path)
            changed_paths.append(f"presentation-studio/{Path(rule.destination).as_posix()}")

        for relative_name, preserved_path in preserved.items():
            destination_path = staged_skill / Path(relative_name)
            _remove_item(destination_path)
            _copy_item(preserved_path, destination_path)

        synchronized_at = _timestamp()
        _update_staged_metadata(staged_skill, source, release, synchronized_at)
        changed_paths.extend(
            [
                "presentation-studio/source-lock.json",
                "presentation-studio/engines/manifest.json",
            ]
        )

        if not (staged_skill / "SKILL.md").is_file():
            raise SyncError("Staged update removed the root Skill entry")
        new_hash = tree_hash(staged_skill)

        backup = repository_root / ".presentation-studio.sync-backup"
        if backup.exists():
            raise SyncError("A previous synchronization backup still exists")
        try:
            skill_root.rename(backup)
            staged_skill.rename(skill_root)
        except OSError as error:
            if not skill_root.exists() and backup.exists():
                backup.rename(skill_root)
            raise SyncError("Unable to apply staged upstream update atomically") from error
        try:
            shutil.rmtree(backup)
        except OSError as error:
            raise SyncError("Update applied but the temporary backup could not be removed") from error

    return SyncResult(
        source=source.name,
        old_commit=old_commit,
        new_commit=release.commit,
        old_tree_hash=old_hash,
        new_tree_hash=new_hash,
        changed_paths=tuple(dict.fromkeys(changed_paths)),
        preserved_paths=source.preserve,
        managed_paths=source_managed_paths(source),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="Read-only upstream release check")
    check_parser.add_argument("--json", action="store_true", dest="as_json")
    check_parser.add_argument("--source", action="append", default=[])
    sync_parser = subparsers.add_parser("sync", help="Synchronize verified stable releases")
    sync_parser.add_argument("--source", action="append", required=True)
    sync_parser.add_argument("--report", type=Path)
    scope_parser = subparsers.add_parser(
        "verify-scope", help="Verify that a source diff stays within its allowlist"
    )
    scope_parser.add_argument("--source", required=True)
    scope_parser.add_argument("--paths-file", type=Path, required=True)
    render_parser = subparsers.add_parser(
        "render-pr-body", help="Render source-specific synchronization PR evidence"
    )
    render_parser.add_argument("--report", type=Path, required=True)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--changed-files", type=int, required=True)
    render_parser.add_argument("--additions", type=int, required=True)
    render_parser.add_argument("--deletions", type=int, required=True)
    render_parser.add_argument("--workflow-url", required=True)
    args = parser.parse_args(argv)

    try:
        sources = load_source_configs()
        if args.command == "verify-scope":
            source = select_sources(sources, [args.source], require_single=True)[0]
            try:
                paths = [
                    line.strip()
                    for line in args.paths_file.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except OSError as error:
                raise SyncError("Unable to read changed-path list") from error
            validate_source_paths(source, paths)
            print(f"PASS: {source.name} changed paths are within the source allowlist")
            return 0
        if args.command == "render-pr-body":
            try:
                report = json.loads(args.report.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as error:
                raise SyncError("Unable to read synchronization report") from error
            body = render_pr_body(
                report,
                changed_file_count=args.changed_files,
                additions=args.additions,
                deletions=args.deletions,
                workflow_url=args.workflow_url,
            )
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(body, encoding="utf-8", newline="\n")
            except OSError as error:
                raise SyncError("Unable to write synchronization PR body") from error
            print(f"PASS: rendered synchronization PR body to {args.output}")
            return 0

        selected_names = getattr(args, "source", [])
        sources = select_sources(
            sources,
            selected_names,
            require_single=args.command == "sync",
        )
        client = GitHubClient(token=os.environ.get("UPSTREAM_GITHUB_TOKEN"))
        results = check_sources(sources, load_source_lock(), client)
        if args.command == "sync":
            source_map = {source.name: source for source in sources}
            applied: list[dict] = []
            checked_at = _timestamp()
            with tempfile.TemporaryDirectory(prefix="presentation-upstream-download-") as temporary:
                download_root = Path(temporary)
                for result in results:
                    source = source_map[result["name"]]
                    release = ReleaseInfo(**result["release"])
                    if result["status"] == "update_available":
                        archive = download_root / f"{source.name}-{release.commit}.zip"
                        client.download(
                            f"/repos/{source.owner}/{source.repository_name}/zipball/{release.commit}",
                            archive,
                        )
                        sync_result = stage_source_update(REPOSITORY_ROOT, source, release, archive)
                        applied_record = asdict(sync_result)
                        applied_record.update(
                            {
                                "release": asdict(release),
                                "repository": source.repository,
                                "license": source.expected_license,
                                "staging_paths": list(sync_result.changed_paths),
                            }
                        )
                        applied.append(applied_record)
            report = {
                "status": "PASS",
                "checked_at": checked_at,
                "source": sources[0].name,
                "changed": bool(applied),
                "sources": results,
                "applied": applied,
            }
            if args.report:
                _write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
    except SyncError as error:
        report_path = getattr(args, "report", None)
        if report_path:
            failure_report = {
                "status": "FAIL",
                "checked_at": _timestamp(),
                "error": str(error),
            }
            try:
                _write_json(report_path, failure_report)
            except OSError as report_error:
                print(f"FAIL: unable to write diagnostic report: {report_error}", file=sys.stderr)
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps({"status": "PASS", "sources": results}, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"{result['name']}: {result['status']} ({result['release']['tag']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
