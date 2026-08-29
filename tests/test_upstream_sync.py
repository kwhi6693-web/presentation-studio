from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.upstream_sync import (
    GitHubClient,
    ImportRule,
    ReleaseInfo,
    SourceConfig,
    SyncError,
    check_sources,
    classify_update,
    discover_latest_release,
    main,
    parse_release,
    record_release_metadata,
    select_sources,
    source_managed_paths,
    source_pr_title,
    validate_source_paths,
)

try:
    from scripts.upstream_sync import stage_source_update, tree_hash
except ImportError:
    stage_source_update = None
    tree_hash = None


class FakeClient:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def get_json(self, path: str) -> dict:
        self.requested.append(path)
        if path not in self.responses:
            raise AssertionError(f"Unexpected GitHub API path: {path}")
        return self.responses[path]


class JsonResponse(io.BytesIO):
    def __enter__(self) -> "JsonResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


class CloseFailureResponse:
    def __init__(self, payload: bytes) -> None:
        self._stream = io.BytesIO(payload)

    def __enter__(self) -> io.BytesIO:
        return self._stream

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._stream.close()
        raise OSError("socket close failed")


def http_error(
    status: int,
    retry_after: str | None = None,
    message: str | None = None,
) -> urllib.error.HTTPError:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    body = b"" if message is None else json.dumps({"message": message}).encode("utf-8")
    return urllib.error.HTTPError(
        "https://api.github.com/test", status, "fixture error", headers, io.BytesIO(body)
    )


class GitHubClientRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(),
            preserve=(),
        )

    def test_retries_release_discovery_404_then_returns_response(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[http_error(404), JsonResponse(b'{"tag_name": "v1.2.3"}')],
        ) as urlopen:
            payload = client.get_json("/repos/author/skill/releases/latest")

        self.assertEqual(payload, {"tag_name": "v1.2.3"})
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleeps, [1.0])

    def test_retries_rate_limit_and_server_errors_with_capped_backoff(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[
                http_error(429, retry_after="999"),
                http_error(500),
                JsonResponse(b'{"status": "ahead"}'),
            ],
        ) as urlopen:
            payload = client.get_json("/repos/author/skill/compare/base...head")

        self.assertEqual(payload, {"status": "ahead"})
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleeps, [5.0, 2.0])

    def test_respects_retry_after_on_a_retryable_server_error(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[http_error(503, retry_after="3"), JsonResponse(b'{"ok": true}')],
        ):
            payload = client.get_json("/repos/author/skill/releases/latest")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(sleeps, [3.0])

    def test_retries_transient_transport_error_then_returns_response(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[urllib.error.URLError("temporary DNS failure"), JsonResponse(b'{"ok": true}')],
        ) as urlopen:
            payload = client.get_json("/repos/author/skill/releases/latest")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleeps, [1.0])

    def test_retries_invalid_utf8_json_then_returns_response(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[JsonResponse(b"\xff"), JsonResponse(b'{"ok": true}')],
        ) as urlopen:
            payload = client.get_json("/repos/author/skill/releases/latest")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleeps, [1.0])

    def test_exhausted_invalid_utf8_discovery_error_is_redacted_and_contextual(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=lambda *args, **kwargs: JsonResponse(b"\xff"),
        ) as urlopen, self.assertRaisesRegex(
            SyncError,
            r"source sample; discover latest release; terminal invalid JSON response after 3 attempts",
        ):
            discover_latest_release(self.source, client)

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_retries_response_close_error_then_returns_response(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[CloseFailureResponse(b'{"ok": true}'), JsonResponse(b'{"ok": true}')],
        ) as urlopen:
            payload = client.get_json("/repos/author/skill/releases/latest")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(sleeps, [1.0])

    def test_exhausted_close_error_is_a_contextual_transport_failure(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=lambda *args, **kwargs: CloseFailureResponse(b'{"ok": true}'),
        ) as urlopen, self.assertRaisesRegex(
            SyncError,
            r"source sample; discover latest release; terminal transport error after 3 attempts",
        ):
            discover_latest_release(self.source, client)

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_does_not_retry_an_ordinary_not_found_response(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen", side_effect=http_error(404)
        ) as urlopen, self.assertRaisesRegex(
            SyncError, r"terminal HTTP 404 after 1 attempt"
        ):
            client.get_json("/repos/author/skill/compare/base...head")

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(sleeps, [])

    def test_exhausted_discovery_error_names_source_and_operation(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen", side_effect=[http_error(500)] * 3
        ) as urlopen, self.assertRaisesRegex(
            SyncError, r"source sample; discover latest release; terminal HTTP 500 after 3 attempts"
        ):
            discover_latest_release(self.source, client)

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_malformed_release_metadata_is_not_retried(self) -> None:
        sleeps: list[float] = []
        client = GitHubClient(sleeper=sleeps.append)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            return_value=JsonResponse(b'{"tag_name": ""}'),
        ) as urlopen, self.assertRaisesRegex(SyncError, r"has no tag"):
            discover_latest_release(self.source, client)

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(sleeps, [])


class UpstreamAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(),
            preserve=(),
        )
        self.release_commit = "a" * 40
        self.release_payload = {
            "draft": False,
            "prerelease": False,
            "tag_name": "v1.2.3",
            "html_url": "https://github.com/author/skill/releases/tag/v1.2.3",
            "published_at": "2026-08-13T00:00:00Z",
        }
        self.source_lock = {
            "sources": [{"name": self.source.name, "commit": self.release_commit}]
        }

    def cli_authorization_headers(self, environment: dict[str, str]) -> list[str | None]:
        responses = [
            JsonResponse(json.dumps(self.release_payload).encode("utf-8")),
            JsonResponse(
                json.dumps(
                    {"object": {"type": "commit", "sha": self.release_commit}}
                ).encode("utf-8")
            ),
        ]
        with (
            patch.dict("os.environ", environment, clear=True),
            patch("scripts.upstream_sync.load_source_configs", return_value=(self.source,)),
            patch("scripts.upstream_sync.load_source_lock", return_value=self.source_lock),
            patch(
                "scripts.upstream_sync.urllib.request.urlopen", side_effect=responses
            ) as urlopen,
            patch("sys.stdout", new=io.StringIO()),
        ):
            self.assertEqual(main(["check", "--json"]), 0)

        return [
            request.args[0].get_header("Authorization")
            for request in urlopen.call_args_list
        ]

    def test_missing_upstream_token_uses_unauthenticated_requests(self) -> None:
        self.assertEqual(self.cli_authorization_headers({}), [None, None])

    def test_repository_token_is_not_used_for_upstream_requests(self) -> None:
        self.assertEqual(
            self.cli_authorization_headers({"GITHUB_TOKEN": "repository-token"}),
            [None, None],
        )

    def test_explicit_upstream_token_authenticates_upstream_requests(self) -> None:
        self.assertEqual(
            self.cli_authorization_headers(
                {
                    "GITHUB_TOKEN": "repository-token",
                    "UPSTREAM_GITHUB_TOKEN": "test-token",
                }
            ),
            ["Bearer test-token", "Bearer test-token"],
        )

    def test_compare_404_names_source_operation_and_http_status(self) -> None:
        client = GitHubClient(sleeper=lambda _: None)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[
                JsonResponse(json.dumps(self.release_payload).encode("utf-8")),
                JsonResponse(
                    json.dumps(
                        {"object": {"type": "commit", "sha": self.release_commit}}
                    ).encode("utf-8")
                ),
                http_error(404),
            ],
        ), self.assertRaisesRegex(
            SyncError,
            r"source sample; compare latest release with locked commit; terminal HTTP 404 after 1 attempt",
        ):
            check_sources(
                (self.source,),
                {"sources": [{"name": self.source.name, "commit": "b" * 40}]},
                client,
            )


class UnrelatedHistoryFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(),
            preserve=(),
        )
        self.release_commit = "a" * 40
        self.locked_commit = "b" * 40
        self.release_response = JsonResponse(
            json.dumps(
                {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v2.0.0",
                    "html_url": "https://github.com/author/skill/releases/tag/v2.0.0",
                    "published_at": "2026-08-24T00:00:00Z",
                }
            ).encode("utf-8")
        )
        self.tag_response = JsonResponse(
            json.dumps(
                {"object": {"type": "commit", "sha": self.release_commit}}
            ).encode("utf-8")
        )

    def source_lock(self) -> dict:
        return {
            "sources": [{"name": self.source.name, "commit": self.locked_commit}]
        }

    def no_common_ancestor_error(
        self,
        base: str | None = None,
        head: str | None = None,
    ) -> urllib.error.HTTPError:
        return http_error(
            404,
            message=(
                f"No common ancestor between {base or self.release_commit} "
                f"and {head or self.locked_commit}."
            ),
        )

    def commit_response(self, commit: str) -> JsonResponse:
        return JsonResponse(json.dumps({"sha": commit}).encode("utf-8"))

    def test_confirmed_no_common_ancestor_is_an_update(self) -> None:
        client = GitHubClient(sleeper=lambda _: None)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[
                self.release_response,
                self.tag_response,
                self.no_common_ancestor_error(),
                self.commit_response(self.release_commit),
                self.commit_response(self.locked_commit),
            ],
        ) as urlopen:
            results = check_sources((self.source,), self.source_lock(), client)

        self.assertEqual(results[0]["status"], "update_available")
        self.assertEqual(
            [request.args[0].full_url for request in urlopen.call_args_list[-2:]],
            [
                f"https://api.github.com/repos/author/skill/commits/{self.release_commit}",
                f"https://api.github.com/repos/author/skill/commits/{self.locked_commit}",
            ],
        )

    def test_no_common_ancestor_for_other_commits_is_not_reclassified(self) -> None:
        client = GitHubClient(sleeper=lambda _: None)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[
                self.release_response,
                self.tag_response,
                self.no_common_ancestor_error("c" * 40, "d" * 40),
            ],
        ), self.assertRaisesRegex(
            SyncError,
            r"source sample; compare latest release with locked commit; terminal HTTP 404 after 1 attempt",
        ):
            check_sources((self.source,), self.source_lock(), client)

    def test_no_common_ancestor_requires_both_commits_in_configured_repository(self) -> None:
        scenarios = (
            (
                "release",
                [http_error(404)],
                r"source sample; confirm latest release commit exists; terminal HTTP 404 after 1 attempt",
            ),
            (
                "locked",
                [self.commit_response(self.release_commit), http_error(404)],
                r"source sample; confirm locked commit exists; terminal HTTP 404 after 1 attempt",
            ),
        )
        for missing, confirmation_responses, expected_error in scenarios:
            with self.subTest(missing=missing):
                client = GitHubClient(sleeper=lambda _: None)
                with patch(
                    "scripts.upstream_sync.urllib.request.urlopen",
                    side_effect=[
                        JsonResponse(self.release_response.getvalue()),
                        JsonResponse(self.tag_response.getvalue()),
                        self.no_common_ancestor_error(),
                        *confirmation_responses,
                    ],
                ), self.assertRaisesRegex(SyncError, expected_error):
                    check_sources((self.source,), self.source_lock(), client)

    def test_mismatched_commit_confirmation_is_not_reclassified(self) -> None:
        client = GitHubClient(sleeper=lambda _: None)
        with patch(
            "scripts.upstream_sync.urllib.request.urlopen",
            side_effect=[
                self.release_response,
                self.tag_response,
                self.no_common_ancestor_error(),
                self.commit_response("c" * 40),
            ],
        ), self.assertRaisesRegex(
            SyncError,
            r"source sample; confirm latest release commit exists; GitHub commit response did not match requested commit",
        ):
            check_sources((self.source,), self.source_lock(), client)


class GitAncestryFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="presentation-upstream-git-test-")
        self.root = Path(self.temporary.name)
        self.remote = self.root / "upstream.git"
        self.git_environment = dict(os.environ)
        self.git_environment.update(
            {
                "GIT_AUTHOR_NAME": "Upstream Test",
                "GIT_AUTHOR_EMAIL": "upstream-test@example.invalid",
                "GIT_COMMITTER_NAME": "Upstream Test",
                "GIT_COMMITTER_EMAIL": "upstream-test@example.invalid",
            }
        )
        self.run_git("init", "--bare", str(self.remote))
        tree = self.run_git("--git-dir", str(self.remote), "mktree", input_text="")
        self.root_commit = self.run_git(
            "--git-dir", str(self.remote), "commit-tree", tree, "-m", "root"
        )
        self.descendant_commit = self.run_git(
            "--git-dir",
            str(self.remote),
            "commit-tree",
            tree,
            "-p",
            self.root_commit,
            "-m",
            "descendant",
        )
        self.unrelated_commit = self.run_git(
            "--git-dir", str(self.remote), "commit-tree", tree, "-m", "unrelated"
        )
        self.run_git(
            "--git-dir",
            str(self.remote),
            "update-ref",
            "refs/heads/linear",
            self.descendant_commit,
        )
        self.run_git(
            "--git-dir",
            str(self.remote),
            "update-ref",
            "refs/heads/unrelated",
            self.unrelated_commit,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_git(self, *arguments: str, input_text: str | None = None) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=input_text,
            env=self.git_environment,
        )
        return completed.stdout.strip()

    def source(self, repository: str | None = None) -> SourceConfig:
        return SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository=repository or self.remote.as_uri(),
            expected_license="MIT",
            imports=(),
            preserve=(),
        )

    @staticmethod
    def response(payload: dict) -> JsonResponse:
        return JsonResponse(json.dumps(payload).encode("utf-8"))

    def check_after_compare_failures(
        self,
        release_commit: str,
        locked_commit: str,
        *,
        source: SourceConfig | None = None,
        compare_failures: list[object] | None = None,
        confirmation_responses: list[object] | None = None,
    ) -> list[dict]:
        current = source or self.source()
        failures = compare_failures or [http_error(504), http_error(504), http_error(504)]
        confirmations = confirmation_responses or [
            self.response({"sha": release_commit}),
            self.response({"sha": locked_commit}),
        ]
        responses = [
            self.response(
                {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v2.0.0",
                    "html_url": "https://github.com/author/skill/releases/tag/v2.0.0",
                    "published_at": "2026-08-24T00:00:00Z",
                }
            ),
            self.response({"object": {"type": "commit", "sha": release_commit}}),
            *failures,
            *confirmations,
        ]
        with patch("scripts.upstream_sync.urllib.request.urlopen", side_effect=responses):
            return check_sources(
                (current,),
                {"sources": [{"name": current.name, "commit": locked_commit}]},
                GitHubClient(sleeper=lambda _: None),
            )

    def test_three_504s_use_git_when_release_descends_from_lock(self) -> None:
        results = self.check_after_compare_failures(
            self.descendant_commit,
            self.root_commit,
        )
        self.assertEqual(results[0]["status"], "update_available")

    def test_three_504s_use_git_when_lock_descends_from_release(self) -> None:
        results = self.check_after_compare_failures(
            self.root_commit,
            self.descendant_commit,
        )
        self.assertEqual(results[0]["status"], "ahead_of_release")

    def test_three_504s_use_git_when_commits_have_no_common_ancestor(self) -> None:
        results = self.check_after_compare_failures(
            self.unrelated_commit,
            self.descendant_commit,
        )
        self.assertEqual(results[0]["status"], "update_available")

    def test_three_504s_require_both_commits_in_configured_repository(self) -> None:
        scenarios = (
            (
                "release",
                [http_error(404)],
                r"source sample; confirm latest release commit exists; terminal HTTP 404 after 1 attempt",
            ),
            (
                "locked",
                [self.response({"sha": self.descendant_commit}), http_error(404)],
                r"source sample; confirm locked commit exists; terminal HTTP 404 after 1 attempt",
            ),
        )
        for missing, confirmations, expected_error in scenarios:
            with self.subTest(missing=missing), self.assertRaisesRegex(SyncError, expected_error):
                self.check_after_compare_failures(
                    self.descendant_commit,
                    self.root_commit,
                    confirmation_responses=confirmations,
                )

    def test_git_fetch_failure_remains_an_error(self) -> None:
        missing_remote = (self.root / "missing.git").as_uri()
        with self.assertRaisesRegex(
            SyncError,
            r"source sample; local Git ancestry fallback; git fetch failed",
        ):
            self.check_after_compare_failures(
                self.descendant_commit,
                self.root_commit,
                source=self.source(missing_remote),
            )

    def test_git_fallback_isolated_from_hostile_git_environment(self) -> None:
        sentinel_config_before = self.run_git(
            "--git-dir", str(self.remote), "config", "--list"
        )
        sentinel_refs_before = self.run_git(
            "--git-dir", str(self.remote), "show-ref"
        )
        hostile_environment = {
            "GIT_DIR": str(self.remote),
            "GIT_WORK_TREE": str(self.root / "sentinel-worktree"),
            "GIT_COMMON_DIR": str(self.remote),
            "GIT_INDEX_FILE": str(self.root / "sentinel-index"),
            "GIT_OBJECT_DIRECTORY": str(self.remote / "objects"),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(self.remote / "objects"),
            "GIT_CONFIG_PARAMETERS": "",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "store",
            "GIT_ASKPASS": str(self.root / "must-not-run-askpass"),
            "SSH_ASKPASS": str(self.root / "must-not-run-ssh-askpass"),
            "SSH_AUTH_SOCK": str(self.root / "must-not-use-agent"),
        }
        real_subprocess_run = subprocess.run
        fallback_environments: list[dict[str, str]] = []

        def inspect_fallback_environment(*args: object, **kwargs: object):
            fallback_environments.append(dict(kwargs["env"]))
            return real_subprocess_run(*args, **kwargs)

        with patch.dict(os.environ, hostile_environment, clear=False), patch(
            "scripts.upstream_sync.subprocess.run",
            side_effect=inspect_fallback_environment,
        ):
            results = self.check_after_compare_failures(
                self.descendant_commit,
                self.root_commit,
            )

        self.assertEqual(results[0]["status"], "update_available")
        self.assertTrue(fallback_environments)
        for environment in fallback_environments:
            for variable in hostile_environment:
                self.assertNotIn(variable, environment)
            self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(environment["GCM_INTERACTIVE"], "Never")
        self.assertEqual(
            self.run_git("--git-dir", str(self.remote), "config", "--list"),
            sentinel_config_before,
        )
        self.assertEqual(
            self.run_git("--git-dir", str(self.remote), "show-ref"),
            sentinel_refs_before,
        )

    def test_mixed_retry_failures_ending_in_504_do_not_use_git(self) -> None:
        with self.assertRaisesRegex(
            SyncError,
            r"source sample; compare latest release with locked commit; terminal HTTP 504 after 3 attempts",
        ):
            self.check_after_compare_failures(
                self.descendant_commit,
                self.root_commit,
                compare_failures=[
                    http_error(504),
                    urllib.error.URLError("transport failed"),
                    http_error(504),
                ],
                confirmation_responses=[],
            )

    def test_ordinary_compare_404_does_not_use_git(self) -> None:
        with self.assertRaisesRegex(
            SyncError,
            r"source sample; compare latest release with locked commit; terminal HTTP 404 after 1 attempt",
        ):
            self.check_after_compare_failures(
                self.descendant_commit,
                self.root_commit,
                compare_failures=[http_error(404)],
                confirmation_responses=[],
            )


class ReleaseDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(ReleaseInfo, "scripts.upstream_sync is missing")
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(),
            preserve=(),
        )
        self.release = ReleaseInfo(
            tag="v1.2.3",
            commit="a" * 40,
            url="https://github.com/author/skill/releases/tag/v1.2.3",
            published_at="2026-08-13T00:00:00Z",
        )

    def test_parse_release_accepts_stable_release(self) -> None:
        payload = {
            "draft": False,
            "prerelease": False,
            "tag_name": "v1.2.3",
            "html_url": "https://github.com/author/skill/releases/tag/v1.2.3",
            "published_at": "2026-08-13T00:00:00Z",
        }
        self.assertEqual(parse_release(payload, "a" * 40), self.release)

    def test_draft_and_prerelease_are_rejected(self) -> None:
        base = {
            "tag_name": "v9.0.0",
            "html_url": "https://example.invalid/v9.0.0",
            "published_at": "2026-08-13T00:00:00Z",
        }
        for field in ("draft", "prerelease"):
            payload = {**base, "draft": False, "prerelease": False, field: True}
            with self.subTest(field=field), self.assertRaises(SyncError):
                parse_release(payload, "b" * 40)

    def test_malformed_release_is_rejected(self) -> None:
        with self.assertRaises(SyncError):
            parse_release(
                {"draft": False, "prerelease": False, "tag_name": ""},
                "not-a-commit",
            )

    def test_discovery_resolves_lightweight_tag_to_immutable_commit(self) -> None:
        client = FakeClient(
            {
                "/repos/author/skill/releases/latest": {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v1.2.3",
                    "html_url": self.release.url,
                    "published_at": self.release.published_at,
                },
                "/repos/author/skill/git/ref/tags/v1.2.3": {
                    "object": {"type": "commit", "sha": self.release.commit}
                },
            }
        )

        discovered = discover_latest_release(self.source, client)

        self.assertEqual(discovered, self.release)
        self.assertEqual(
            client.requested,
            [
                "/repos/author/skill/releases/latest",
                "/repos/author/skill/git/ref/tags/v1.2.3",
            ],
        )

    def test_discovery_dereferences_annotated_tag(self) -> None:
        tag_object = "b" * 40
        client = FakeClient(
            {
                "/repos/author/skill/releases/latest": {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v1.2.3",
                    "html_url": self.release.url,
                    "published_at": self.release.published_at,
                },
                "/repos/author/skill/git/ref/tags/v1.2.3": {
                    "object": {"type": "tag", "sha": tag_object}
                },
                f"/repos/author/skill/git/tags/{tag_object}": {
                    "object": {"type": "commit", "sha": self.release.commit}
                },
            }
        )

        self.assertEqual(discover_latest_release(self.source, client), self.release)

    def test_equal_lock_is_current(self) -> None:
        status = classify_update(self.release.commit, self.release, lambda base, head: "identical")
        self.assertEqual(status, "current")

    def test_locked_descendant_is_not_downgraded(self) -> None:
        status = classify_update("c" * 40, self.release, lambda base, head: "ahead")
        self.assertEqual(status, "ahead_of_release")

    def test_release_not_contained_by_lock_is_an_update(self) -> None:
        for relation in ("behind", "diverged"):
            with self.subTest(relation=relation):
                status = classify_update(
                    "c" * 40,
                    self.release,
                    lambda base, head, result=relation: result,
                )
                self.assertEqual(status, "update_available")


class StagingImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(stage_source_update, "staging importer is missing")
        self.temporary = tempfile.TemporaryDirectory(prefix="presentation-upstream-stage-")
        self.root = Path(self.temporary.name)
        self.skill = self.root / "presentation-studio"
        self.engine = self.skill / "engines" / "sample"
        self.engine.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("root\n", encoding="utf-8")
        (self.engine / "SKILL.md").write_text("adapter\n", encoding="utf-8")
        (self.engine / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (self.engine / "old.txt").write_text("old\n", encoding="utf-8")
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(
                ImportRule(source="package", destination="engines/sample", mode="replace"),
            ),
            preserve=("engines/sample/SKILL.md",),
            license_candidates=("LICENSE",),
        )
        self.release = ReleaseInfo(
            tag="v2.0.0",
            commit="d" * 40,
            url="https://github.com/author/skill/releases/tag/v2.0.0",
            published_at="2026-08-13T00:00:00Z",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_archive(self, members: dict[str, bytes | str]) -> Path:
        archive_path = self.root / f"fixture-{len(list(self.root.glob('fixture-*.zip')))}.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for name, content in members.items():
                data = content.encode("utf-8") if isinstance(content, str) else content
                archive.writestr(name, data)
        return archive_path

    def test_successful_stage_replaces_import_and_restores_adapter(self) -> None:
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "MIT License\n",
                "author-skill-release/package/LICENSE": "MIT License\n",
                "author-skill-release/package/new.txt": "new\n",
                "author-skill-release/package/SKILL.md": "upstream entry\n",
            }
        )

        result = stage_source_update(self.root, self.source, self.release, archive)

        self.assertEqual((self.engine / "new.txt").read_text(encoding="utf-8"), "new\n")
        self.assertFalse((self.engine / "old.txt").exists())
        self.assertEqual((self.engine / "SKILL.md").read_text(encoding="utf-8"), "adapter\n")
        self.assertEqual(result.old_commit, None)
        self.assertEqual(result.new_commit, self.release.commit)
        self.assertIn("presentation-studio/engines/sample", result.changed_paths)

    def test_successful_stage_updates_and_reports_provenance_metadata(self) -> None:
        (self.skill / "source-lock.json").write_text(
            json.dumps({"sources": [{"name": "sample"}]}) + "\n", encoding="utf-8"
        )
        (self.skill / "engines" / "manifest.json").write_text(
            json.dumps({"sample": {"source_name": "sample"}}) + "\n", encoding="utf-8"
        )
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "MIT License\n",
                "author-skill-release/package/new.txt": "new\n",
            }
        )

        result = stage_source_update(self.root, self.source, self.release, archive)

        self.assertIn("presentation-studio/source-lock.json", result.changed_paths)
        self.assertIn("presentation-studio/engines/manifest.json", result.changed_paths)
        lock = json.loads((self.skill / "source-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["sources"][0]["release_tag"], self.release.tag)
        manifest = json.loads((self.skill / "engines" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sample"]["commit"], self.release.commit)

    def test_missing_declared_import_path_leaves_destination_unchanged(self) -> None:
        archive = self.make_archive(
            {"author-skill-release/LICENSE": "MIT License\n", "author-skill-release/other.txt": "x"}
        )
        before = tree_hash(self.skill)

        with self.assertRaises(SyncError):
            stage_source_update(self.root, self.source, self.release, archive)

        self.assertEqual(tree_hash(self.skill), before)

    def test_path_traversal_is_rejected_before_any_write(self) -> None:
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "MIT License\n",
                "author-skill-release/package/new.txt": "new\n",
                "../escape.txt": "unsafe\n",
            }
        )
        before = tree_hash(self.skill)

        with self.assertRaises(SyncError):
            stage_source_update(self.root, self.source, self.release, archive)

        self.assertEqual(tree_hash(self.skill), before)
        self.assertFalse((self.root.parent / "escape.txt").exists())

    def test_license_mismatch_is_rejected_atomically(self) -> None:
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "Apache License 2.0\n",
                "author-skill-release/package/new.txt": "new\n",
            }
        )
        before = tree_hash(self.skill)

        with self.assertRaises(SyncError):
            stage_source_update(self.root, self.source, self.release, archive)

        self.assertEqual(tree_hash(self.skill), before)

    def test_same_archive_is_idempotent(self) -> None:
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "MIT License\n",
                "author-skill-release/package/LICENSE": "MIT License\n",
                "author-skill-release/package/new.txt": "new\n",
            }
        )

        first = stage_source_update(self.root, self.source, self.release, archive)
        after_first = tree_hash(self.skill)
        second = stage_source_update(self.root, self.source, self.release, archive)

        self.assertEqual(tree_hash(self.skill), after_first)
        self.assertEqual(first.new_tree_hash, second.new_tree_hash)

    def test_long_repository_path_does_not_break_staging(self) -> None:
        long_root = (
            self.root
            / ("repository-path-segment-" + "a" * 55)
            / ("nested-segment-" + "b" * 35)
        )
        long_engine = long_root / "presentation-studio" / "engines" / "sample"
        long_engine.mkdir(parents=True)
        (long_root / "presentation-studio" / "SKILL.md").write_text(
            "root\n", encoding="utf-8"
        )
        (long_engine / "SKILL.md").write_text("adapter\n", encoding="utf-8")
        archive = self.make_archive(
            {
                "author-skill-release/LICENSE": "MIT License\n",
                "author-skill-release/package/LICENSE": "MIT License\n",
                "author-skill-release/package/new.txt": "new\n",
            }
        )

        result = stage_source_update(long_root, self.source, self.release, archive)

        self.assertEqual(result.new_commit, self.release.commit)
        self.assertEqual((long_engine / "new.txt").read_text(encoding="utf-8"), "new\n")


class MetadataAndReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="presentation-upstream-metadata-")
        self.root = Path(self.temporary.name)
        (self.root / "presentation-studio").mkdir()
        self.source = SourceConfig(
            name="sample",
            owner="author",
            repository_name="skill",
            repository="https://github.com/author/skill.git",
            expected_license="MIT",
            imports=(ImportRule(source="package", destination="engines/sample", mode="replace"),),
            preserve=(),
        )
        self.release = ReleaseInfo(
            tag="v1.2.3",
            commit="a" * 40,
            url="https://github.com/author/skill/releases/tag/v1.2.3",
            published_at="2026-08-13T00:00:00Z",
        )
        self.lock_path = self.root / "presentation-studio" / "source-lock.json"
        self.lock_path.write_text(
            json.dumps({"sources": [{"name": "sample"}]}, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_unchanged_release_metadata_does_not_create_timestamp_churn(self) -> None:
        record_release_metadata(self.root, self.source, self.release, "2026-08-13T01:00:00Z")
        first = self.lock_path.read_bytes()
        self.assertNotIn(b"\r\n", first)
        record_release_metadata(self.root, self.source, self.release, "2026-08-13T01:05:00Z")
        self.assertEqual(self.lock_path.read_bytes(), first)

    def test_sync_cli_writes_failure_report_before_returning_nonzero(self) -> None:
        report = self.root / "artifacts" / "failure.json"
        exit_code = main(["sync", "--source", "does-not-exist", "--report", str(report)])
        self.assertEqual(exit_code, 1)
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "FAIL")
        self.assertIn("Unknown upstream source", payload["error"])

    def test_sync_no_update_is_a_true_noop_and_reports_no_pr_change(self) -> None:
        report = self.root / "artifacts" / "current.json"
        release = {
            "tag": "v1.2.3",
            "commit": "a" * 40,
            "url": "https://github.com/author/skill/releases/tag/v1.2.3",
            "published_at": "2026-08-13T00:00:00Z",
        }
        check_result = [
            {
                "name": "sample",
                "status": "current",
                "locked_commit": "a" * 40,
                "locked_release_tag": "v1.2.3",
                "release": release,
            }
        ]
        with patch("scripts.upstream_sync.load_source_configs", return_value=(self.source,)), patch(
            "scripts.upstream_sync.load_source_lock", return_value={"sources": []}
        ), patch("scripts.upstream_sync.check_sources", return_value=check_result), patch(
            "scripts.upstream_sync.record_release_metadata"
        ) as record_metadata:
            exit_code = main(["sync", "--source", "sample", "--report", str(report)])

        self.assertEqual(exit_code, 0)
        record_metadata.assert_not_called()
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(payload["changed"])
        self.assertEqual(payload["source"], "sample")
        self.assertEqual(payload["applied"], [])


class SourceIsolationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = (
            SourceConfig(
                name="alpha",
                owner="author",
                repository_name="alpha",
                repository="https://github.com/author/alpha.git",
                expected_license="MIT",
                imports=(ImportRule("package", "engines/alpha", "replace"),),
                preserve=("engines/alpha/SKILL.md",),
            ),
            SourceConfig(
                name="beta",
                owner="author",
                repository_name="beta",
                repository="https://github.com/author/beta.git",
                expected_license="MIT",
                imports=(ImportRule("package", "engines/beta", "replace"),),
                preserve=(),
            ),
        )
        self.release = ReleaseInfo(
            tag="v2.0.0",
            commit="d" * 40,
            url="https://github.com/author/alpha/releases/tag/v2.0.0",
            published_at="2026-08-13T00:00:00Z",
        )

    def test_sync_source_selection_requires_exactly_one_source(self) -> None:
        self.assertEqual(
            select_sources(self.sources, ["alpha"], require_single=True),
            (self.sources[0],),
        )
        with self.assertRaisesRegex(SyncError, "exactly one"):
            select_sources(self.sources, [], require_single=True)
        with self.assertRaisesRegex(SyncError, "exactly one"):
            select_sources(self.sources, ["alpha", "beta"], require_single=True)

    def test_source_managed_paths_exclude_release_outputs_and_include_provenance(self) -> None:
        paths = set(source_managed_paths(self.sources[0]))
        self.assertIn("presentation-studio/engines/alpha", paths)
        self.assertIn("presentation-studio/engines/alpha/SKILL.md", paths)
        self.assertIn("presentation-studio/source-lock.json", paths)
        self.assertIn("presentation-studio/engines/manifest.json", paths)
        self.assertNotIn("dist/presentation-studio.zip", paths)
        self.assertNotIn("checksums.sha256", paths)

    def test_source_scope_rejects_a_second_upstream_engine(self) -> None:
        validate_source_paths(
            self.sources[0],
            [
                "presentation-studio/engines/alpha/SKILL.md",
                "presentation-studio/source-lock.json",
            ],
        )
        with self.assertRaisesRegex(SyncError, "outside the managed paths"):
            validate_source_paths(
                self.sources[0],
                ["presentation-studio/engines/beta/SKILL.md"],
            )

    def test_source_pr_title_names_the_exact_release(self) -> None:
        self.assertEqual(
            source_pr_title(self.sources[0], self.release),
            "chore(upstream): update alpha to v2.0.0",
        )


if __name__ == "__main__":
    unittest.main()
