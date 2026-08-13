from __future__ import annotations

import unittest

try:
    from scripts.upstream_sync import (
        ReleaseInfo,
        SourceConfig,
        SyncError,
        classify_update,
        discover_latest_release,
        parse_release,
    )
except ModuleNotFoundError:
    ReleaseInfo = None
    SourceConfig = None
    SyncError = RuntimeError
    classify_update = None
    discover_latest_release = None
    parse_release = None


class FakeClient:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def get_json(self, path: str) -> dict:
        self.requested.append(path)
        if path not in self.responses:
            raise AssertionError(f"Unexpected GitHub API path: {path}")
        return self.responses[path]


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


if __name__ == "__main__":
    unittest.main()
