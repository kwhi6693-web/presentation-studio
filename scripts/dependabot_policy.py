#!/usr/bin/env python3
"""Fail-closed policy for merging Dependabot pull requests without a person.

Dependabot may only change what this repository lets it change:

* ``github_actions`` updates: ``uses: actions/<name>@<sha> # <release>`` lines in
  workflow files.  Every new pin must be an action that is already approved in
  ``.github/reviewed-actions.json`` and its SHA must equal the commit that the
  upstream release tag points to.  The automation then records the verified pin
  in ``.github/reviewed-actions.json`` (a commit authored by the trusted App).
* ``npm_and_yarn`` updates for the baoyu engine: only version values of existing
  dependency/override keys in ``package.json`` plus the two lockfiles.

Everything else is blocked.  Merging also requires the ``verify`` check to be
green and the branch to be up to date with ``main``.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import dataclasses
import json
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.automation_policy import GitHubApi, PolicyError  # noqa: E402

DEPENDABOT_LOGIN = "dependabot[bot]"
GITHUB_WEB_FLOW_LOGIN = "web-flow"
REQUIRED_CHECK = "verify"
REVIEWED_ACTIONS_PATH = ".github/reviewed-actions.json"
BAOYU_ROOT = "presentation-studio/engines/baoyu"
BAOYU_PACKAGE_JSON = f"{BAOYU_ROOT}/package.json"
BAOYU_FILES = frozenset(
    {BAOYU_PACKAGE_JSON, f"{BAOYU_ROOT}/package-lock.json", f"{BAOYU_ROOT}/pnpm-lock.yaml"}
)
DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "overrides",
)
WORKFLOW_RE = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
USES_LINE_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s*(actions/[A-Za-z0-9_.-]+)@([0-9a-f]{40})\s+#\s+(v[0-9]+(?:\.[0-9]+){0,2})\s*$"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PENDING_STATES = {"", "queued", "in_progress", "pending", "waiting", "requested"}
GREEN_STATES = {"success", "neutral", "skipped"}

WAIT_CHECKS = "check runs are still running"
WAIT_MERGEABILITY = "GitHub mergeability is still being computed"


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str
    patch: str | None
    previous_path: str | None = None


@dataclass(frozen=True)
class DependabotSnapshot:
    number: int
    state: str
    draft: bool
    base_ref: str
    base_repository: str
    head_repository: str
    head_ref: str
    head_sha: str
    author_login: str
    files: tuple[ChangedFile, ...]
    commit_identities: tuple[tuple[str, str], ...]
    check_runs: tuple[tuple[str, str], ...]
    mergeable: bool | None
    mergeable_state: str
    # Text at the PR head and on main for the files the policy inspects.
    head_texts: Mapping[str, str | None]
    base_texts: Mapping[str, str | None]


@dataclass(frozen=True)
class Decision:
    action: str  # ignore | block | wait | record-pins | update | merge
    reason: str
    reviewed_actions: str | None = None


TagResolver = Callable[[str, str], str | None]


def _is_dependabot_pr(pr: DependabotSnapshot, repository: str) -> bool:
    return (
        pr.author_login == DEPENDABOT_LOGIN
        and pr.head_ref.startswith("dependabot/")
        and pr.head_repository.lower() == repository.lower()
        and pr.base_repository.lower() == repository.lower()
        and pr.base_ref == "main"
    )


def _changed_lines(patch: str) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    added: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---", "@@", "\\")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return removed, added


def _actions_targets(pr: DependabotSnapshot) -> dict[str, tuple[str, str]] | str:
    """Return {action: (sha, release)} from workflow diffs, or a blocker reason."""

    targets: dict[str, tuple[str, str]] = {}
    for item in pr.files:
        if item.path == REVIEWED_ACTIONS_PATH:
            continue
        if WORKFLOW_RE.fullmatch(item.path) is None:
            return f"Dependabot actions update changed a non-workflow file: {item.path}"
        if item.status != "modified" or item.previous_path or not item.patch:
            return f"Dependabot actions update must only modify workflow lines: {item.path}"
        removed, added = _changed_lines(item.patch)
        if not added or len(removed) != len(added):
            return f"Dependabot actions update changed an unexpected number of lines: {item.path}"
        removed_actions: list[str] = []
        added_actions: list[str] = []
        for line in removed:
            match = USES_LINE_RE.fullmatch(line)
            if match is None:
                return f"Dependabot actions update removed a non-pin line: {item.path}"
            removed_actions.append(match.group(1))
        for line in added:
            match = USES_LINE_RE.fullmatch(line)
            if match is None:
                return f"Dependabot actions update added a non-pin line: {item.path}"
            action, sha, release = match.groups()
            added_actions.append(action)
            if targets.setdefault(action, (sha, release)) != (sha, release):
                return f"Dependabot actions update uses two different pins for {action}"
        if sorted(removed_actions) != sorted(added_actions):
            return f"Dependabot actions update changed which actions are used: {item.path}"
    if not targets:
        return "Dependabot actions update has no workflow pin changes"
    return targets


def _expected_reviewed_actions(
    base_text: str | None, targets: Mapping[str, tuple[str, str]]
) -> dict | str:
    try:
        reviewed = json.loads(base_text or "")
    except json.JSONDecodeError:
        return f"{REVIEWED_ACTIONS_PATH} on main is not valid JSON"
    if not isinstance(reviewed, dict):
        return f"{REVIEWED_ACTIONS_PATH} on main is not an object"
    expected = json.loads(json.dumps(reviewed))
    for action, (sha, release) in targets.items():
        entry = expected.get(action)
        if not isinstance(entry, dict):
            return f"Dependabot proposes an action that is not approved: {action}"
        entry["commit"] = sha
        entry["release"] = release
    return expected


def render_reviewed_actions(data: Mapping) -> str:
    return json.dumps(data, indent=2) + "\n"


def _evaluate_actions(pr: DependabotSnapshot, resolve_tag: TagResolver) -> Decision | None:
    targets = _actions_targets(pr)
    if isinstance(targets, str):
        return Decision("block", targets)
    for action, (sha, release) in sorted(targets.items()):
        resolved = resolve_tag(action, release)
        if resolved is None:
            return Decision("block", f"could not resolve {action} {release} to a commit")
        if resolved != sha:
            return Decision(
                "block",
                f"{action} pin {sha} does not match the {release} tag commit {resolved}",
            )
    expected = _expected_reviewed_actions(pr.base_texts.get(REVIEWED_ACTIONS_PATH), targets)
    if isinstance(expected, str):
        return Decision("block", expected)
    head_text = pr.head_texts.get(REVIEWED_ACTIONS_PATH)
    try:
        head = json.loads(head_text or "")
    except json.JSONDecodeError:
        return Decision("block", f"{REVIEWED_ACTIONS_PATH} on the PR head is not valid JSON")
    if head == expected:
        return None
    base = json.loads(pr.base_texts.get(REVIEWED_ACTIONS_PATH) or "{}")
    if head == base:
        return Decision(
            "record-pins",
            "verified pins must be recorded in " + REVIEWED_ACTIONS_PATH,
            reviewed_actions=render_reviewed_actions(expected),
        )
    return Decision("block", f"{REVIEWED_ACTIONS_PATH} on the PR head has unexpected content")


def _strip_versions(package: object) -> object:
    if not isinstance(package, dict):
        return package
    stripped = json.loads(json.dumps(package))
    sections: list[dict] = [stripped]
    if isinstance(stripped.get("pnpm"), dict):
        sections.append(stripped["pnpm"])
    for holder in sections:
        for name in DEPENDENCY_SECTIONS:
            values = holder.get(name)
            if isinstance(values, dict):
                holder[name] = {key: None for key in values}
    return stripped


def _evaluate_npm(pr: DependabotSnapshot) -> Decision | None:
    paths = {item.path for item in pr.files}
    if not paths <= BAOYU_FILES:
        unexpected = sorted(paths - BAOYU_FILES)[0]
        return Decision("block", f"Dependabot npm update changed an unexpected file: {unexpected}")
    if any(item.status != "modified" or item.previous_path for item in pr.files):
        return Decision("block", "Dependabot npm update added, removed or renamed a file")
    if BAOYU_PACKAGE_JSON in paths:
        try:
            head = json.loads(pr.head_texts.get(BAOYU_PACKAGE_JSON) or "")
            base = json.loads(pr.base_texts.get(BAOYU_PACKAGE_JSON) or "")
        except json.JSONDecodeError:
            return Decision("block", "baoyu package.json could not be parsed")
        if _strip_versions(head) != _strip_versions(base):
            return Decision(
                "block",
                "Dependabot npm update changed package.json beyond dependency versions",
            )
    return None


def evaluate(
    pr: DependabotSnapshot,
    *,
    repository: str,
    app_login: str,
    expected_head_sha: str,
    resolve_tag: TagResolver,
) -> Decision:
    if not _is_dependabot_pr(pr, repository):
        return Decision("ignore", "not a same-repository Dependabot PR into main")
    if pr.head_sha != expected_head_sha:
        return Decision("ignore", "PR head changed after validation; a newer run decides")
    if pr.state.lower() != "open" or pr.draft:
        return Decision("ignore", "PR is not open and ready")
    if not SHA_RE.fullmatch(pr.head_sha):
        return Decision("block", "PR has an invalid head SHA")
    app = app_login.lower()
    for author, committer in pr.commit_identities:
        author, committer = author.lower(), committer.lower()
        if author == DEPENDABOT_LOGIN and committer in {DEPENDABOT_LOGIN, GITHUB_WEB_FLOW_LOGIN}:
            continue
        if author == app and committer in {app, GITHUB_WEB_FLOW_LOGIN}:
            continue
        return Decision("block", "PR contains a commit not made by Dependabot or the trusted App")
    if not pr.files:
        return Decision("block", "PR has no changed files")

    if pr.head_ref.startswith("dependabot/github_actions/"):
        decision = _evaluate_actions(pr, resolve_tag)
    elif pr.head_ref.startswith("dependabot/npm_and_yarn/"):
        decision = _evaluate_npm(pr)
    else:
        decision = Decision("block", f"unsupported Dependabot ecosystem branch: {pr.head_ref}")
    if decision is not None:
        return decision

    states = [conclusion.lower() for _, conclusion in pr.check_runs]
    failed = [name for name, conclusion in pr.check_runs if conclusion.lower() not in GREEN_STATES | PENDING_STATES]
    if failed:
        return Decision("block", f"PR has a failed check run: {failed[0]}")
    if any(state in PENDING_STATES for state in states):
        return Decision("wait", WAIT_CHECKS)
    required = [conclusion.lower() for name, conclusion in pr.check_runs if name == REQUIRED_CHECK]
    if not required or any(state != "success" for state in required):
        return Decision("block", f"required check {REQUIRED_CHECK} is not successful")

    state = pr.mergeable_state.lower()
    if state == "behind":
        return Decision("update", "PR branch is behind main")
    if pr.mergeable is None or state == "unknown":
        return Decision("wait", WAIT_MERGEABILITY)
    if pr.mergeable is False or state == "dirty":
        return Decision("block", "PR has merge conflicts")
    if state not in {"clean", "has_hooks", "unstable"}:
        return Decision("block", f"PR mergeable state is not clean (actual: {pr.mergeable_state})")
    return Decision("merge", "Dependabot update verified and all checks are green")


# --------------------------------------------------------------------------- API


def _file_text(api: GitHubApi, repository: str, path: str, ref: str) -> str | None:
    quoted = urllib.parse.quote(path, safe="/")
    try:
        payload = api.request(f"/repos/{repository}/contents/{quoted}?ref={ref}")
    except PolicyError:
        return None
    if not isinstance(payload, dict) or payload.get("type") != "file":
        return None
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        return None
    try:
        return base64.b64decode(payload["content"]).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None


def make_tag_resolver(api: GitHubApi) -> TagResolver:
    def resolve(action: str, release: str) -> str | None:
        try:
            ref = api.request(f"/repos/{action}/git/ref/tags/{urllib.parse.quote(release)}")
            obj = ref["object"]
            for _ in range(3):
                if obj["type"] == "commit":
                    sha = obj["sha"]
                    return sha if SHA_RE.fullmatch(sha) else None
                if obj["type"] != "tag":
                    return None
                obj = api.request(f"/repos/{action}/git/tags/{obj['sha']}")["object"]
        except (PolicyError, KeyError, TypeError):
            return None
        return None

    return resolve


def fetch_snapshot(api: GitHubApi, repository: str, number: int) -> DependabotSnapshot:
    pr = api.request(f"/repos/{repository}/pulls/{number}")
    if not isinstance(pr, dict):
        raise PolicyError("GitHub pull request response is not an object")
    files_payload = api.paginate(f"/repos/{repository}/pulls/{number}/files")
    if len(files_payload) != pr.get("changed_files"):
        raise PolicyError("GitHub pull request files are incomplete")
    files = tuple(
        ChangedFile(
            path=str(item["filename"]),
            status=str(item.get("status") or ""),
            patch=item.get("patch") if isinstance(item.get("patch"), str) else None,
            previous_path=item.get("previous_filename") or None,
        )
        for item in files_payload
    )
    commits = api.paginate(f"/repos/{repository}/pulls/{number}/commits")
    if len(commits) != pr.get("commits"):
        raise PolicyError("GitHub pull request commits are incomplete")
    identities = []
    for item in commits:
        author = (item.get("author") or {}).get("login")
        committer = (item.get("committer") or {}).get("login")
        if not isinstance(author, str) or not isinstance(committer, str):
            raise PolicyError("GitHub pull request commit identity is missing")
        identities.append((author, committer))
    head_sha = pr["head"]["sha"]
    checks = api.request(f"/repos/{repository}/commits/{head_sha}/check-runs?per_page=100")
    check_runs = tuple(
        (str(item.get("name", "")), str(item.get("conclusion") or item.get("status") or ""))
        for item in checks.get("check_runs", [])
    )
    inspected = (REVIEWED_ACTIONS_PATH, BAOYU_PACKAGE_JSON)
    return DependabotSnapshot(
        number=int(pr["number"]),
        state=str(pr["state"]),
        draft=bool(pr.get("draft")),
        base_ref=str(pr["base"]["ref"]),
        base_repository=str(pr["base"]["repo"]["full_name"]),
        head_repository=str((pr["head"].get("repo") or {}).get("full_name", "")),
        head_ref=str(pr["head"]["ref"]),
        head_sha=str(head_sha),
        author_login=str(pr["user"]["login"]),
        files=files,
        commit_identities=tuple(identities),
        check_runs=check_runs,
        mergeable=pr.get("mergeable"),
        mergeable_state=str(pr.get("mergeable_state") or "unknown"),
        head_texts={path: _file_text(api, repository, path, head_sha) for path in inspected},
        base_texts={path: _file_text(api, repository, path, "main") for path in inspected},
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--app-login", required=True)
    parser.add_argument("--reviewed-actions-output", type=Path)
    args = parser.parse_args(argv)

    api = GitHubApi(os.environ.get("GH_TOKEN", ""))
    resolver = make_tag_resolver(api)
    attempts = max(1, int(os.environ.get("POLICY_TRANSIENT_ATTEMPTS", "12")))
    delay = float(os.environ.get("POLICY_TRANSIENT_DELAY_SECONDS", "15"))
    decision = Decision("block", "policy did not run")
    for attempt in range(attempts):
        snapshot = fetch_snapshot(api, args.repository, args.pr)
        decision = evaluate(
            snapshot,
            repository=args.repository,
            app_login=args.app_login,
            expected_head_sha=args.head_sha,
            resolve_tag=resolver,
        )
        if decision.action != "wait":
            break
        if attempt + 1 < attempts:
            time.sleep(delay)
    if decision.action == "wait":
        decision = dataclasses.replace(
            decision, action="ignore", reason=f"{decision.reason}; the next validation run decides"
        )
    if decision.reviewed_actions is not None and args.reviewed_actions_output:
        args.reviewed_actions_output.write_text(decision.reviewed_actions, encoding="utf-8")
    print(json.dumps({"action": decision.action, "reason": decision.reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
