from __future__ import annotations

import io
import json
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
    classify_update,
    discover_latest_release,
    main,
    parse_release,
    record_release_metadata,
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


def http_error(status: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return urllib.error.HTTPError(
        "https://api.github.com/test", status, "fixture error", headers, io.BytesIO()
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


if __name__ == "__main__":
    unittest.main()
