#!/usr/bin/env python3
"""Discover and safely synchronize Presentation Studio upstream releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().with_name("upstream_sources.json")
SOURCE_LOCK_PATH = REPOSITORY_ROOT / "presentation-studio" / "source-lock.json"
GITHUB_API = "https://api.github.com"
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


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


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: int = 30) -> None:
        self._token = token
        self._timeout = timeout

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
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 403:
                raise SyncError("GitHub API refused the request or rate limit was reached") from error
            if error.code == 404:
                raise SyncError("GitHub release or tag was not found") from error
            raise SyncError(f"GitHub API request failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise SyncError("GitHub API request failed") from error
        if not isinstance(payload, dict):
            raise SyncError("GitHub API returned an unexpected payload")
        return payload


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


def _tag_commit(source: SourceConfig, tag: str, client: JsonClient) -> str:
    encoded_tag = urllib.parse.quote(tag, safe="")
    reference = client.get_json(
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
        tag_object = client.get_json(
            f"/repos/{source.owner}/{source.repository_name}/git/tags/{sha}"
        )
        obj = tag_object.get("object") if isinstance(tag_object, dict) else None
    raise SyncError(f"Release tag for {source.name} did not resolve to a commit")


def discover_latest_release(source: SourceConfig, client: JsonClient) -> ReleaseInfo:
    payload = client.get_json(f"/repos/{source.owner}/{source.repository_name}/releases/latest")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="Read-only upstream release check")
    check_parser.add_argument("--json", action="store_true", dest="as_json")
    check_parser.add_argument("--source", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        sources = load_source_configs()
        if args.source:
            selected = set(args.source)
            sources = tuple(source for source in sources if source.name in selected)
            unknown = selected - {source.name for source in sources}
            if unknown:
                raise SyncError(f"Unknown upstream source: {sorted(unknown)[0]}")
        client = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
        results = check_sources(sources, load_source_lock(), client)
    except SyncError as error:
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
