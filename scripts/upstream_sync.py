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


class SyncError(RuntimeError):
    """A redacted, user-actionable upstream synchronization failure."""


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
        for attempt in range(1, MAX_GITHUB_JSON_ATTEMPTS + 1):
            retry_after: float | None = None
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as error:
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
            raise SyncError(
                f"terminal {category} after {attempt} "
                f"attempt{'s' if attempt != 1 else ''}"
            )
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


def load_source_lock(path: Path = SOURCE_LOCK_PATH) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError("Unable to load source-lock.json") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise SyncError("source-lock.json has an invalid structure")
    return payload


def _compare_status(source: SourceConfig, base: str, head: str, client: JsonClient) -> str:
    payload = client.get_json(
        f"/repos/{source.owner}/{source.repository_name}/compare/{base}...{head}"
    )
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
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="Read-only upstream release check")
    check_parser.add_argument("--json", action="store_true", dest="as_json")
    check_parser.add_argument("--source", action="append", default=[])
    sync_parser = subparsers.add_parser("sync", help="Synchronize verified stable releases")
    selection = sync_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--source", action="append", default=[])
    sync_parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        sources = load_source_configs()
        selected_names = getattr(args, "source", [])
        if selected_names:
            selected = set(selected_names)
            sources = tuple(source for source in sources if source.name in selected)
            unknown = selected - {source.name for source in sources}
            if unknown:
                raise SyncError(f"Unknown upstream source: {sorted(unknown)[0]}")
        client = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
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
                        applied.append(asdict(sync_result))
                    else:
                        record_release_metadata(REPOSITORY_ROOT, source, release, checked_at)
            report = {
                "status": "PASS",
                "checked_at": checked_at,
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
