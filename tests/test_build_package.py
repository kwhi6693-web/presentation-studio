from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    from scripts.build_package import build_archive
except ModuleNotFoundError:
    build_archive = None


class DeterministicPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="presentation-studio-build-test-")
        self.root = Path(self.temporary.name)
        self.skill = self.root / "presentation-studio"
        (self.skill / "nested").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("hello\n", encoding="utf-8")
        (self.skill / "nested" / "中文.txt").write_text("ok\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_build_archive_is_byte_reproducible(self) -> None:
        self.assertIsNotNone(build_archive, "scripts.build_package is missing")
        first = self.root / "first.zip"
        second = self.root / "second.zip"

        first_sha = build_archive(self.skill, first)
        second_sha = build_archive(self.skill, second)

        self.assertEqual(first_sha, second_sha)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(first_sha, hashlib.sha256(first.read_bytes()).hexdigest())

    def test_build_archive_uses_one_safe_root_and_sorted_members(self) -> None:
        self.assertIsNotNone(build_archive, "scripts.build_package is missing")
        archive_path = self.root / "package.zip"
        build_archive(self.skill, archive_path)

        with zipfile.ZipFile(archive_path) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
            timestamps = {info.date_time for info in archive.infolist() if not info.is_dir()}

        self.assertEqual(names, sorted(names))
        self.assertEqual(
            names,
            ["presentation-studio/SKILL.md", "presentation-studio/nested/中文.txt"],
        )
        self.assertEqual(timestamps, {(1980, 1, 1, 0, 0, 0)})

    def test_build_archive_excludes_python_cache_files(self) -> None:
        self.assertIsNotNone(build_archive, "scripts.build_package is missing")
        cache = self.skill / "__pycache__"
        cache.mkdir()
        (cache / "bad.pyc").write_bytes(b"cache")
        (self.skill / "bad.pyo").write_bytes(b"cache")
        archive_path = self.root / "package.zip"

        build_archive(self.skill, archive_path)

        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
        self.assertFalse(any("__pycache__" in name for name in names))
        self.assertFalse(any(name.endswith((".pyc", ".pyo")) for name in names))

    def test_build_archive_excludes_generated_dependencies_and_secrets(self) -> None:
        self.assertIsNotNone(build_archive, "scripts.build_package is missing")
        (self.skill / ".git").mkdir()
        (self.skill / ".git" / "index").write_bytes(b"git metadata")
        (self.skill / "node_modules" / "package").mkdir(parents=True)
        (self.skill / "node_modules" / "package" / "index.js").write_text("bad\n", encoding="utf-8")
        (self.skill / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.skill / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
        (self.skill / "debug.log").write_text("noise\n", encoding="utf-8")
        (self.skill / "staging.tmp").write_text("noise\n", encoding="utf-8")
        archive_path = self.root / "package.zip"

        build_archive(self.skill, archive_path)

        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("presentation-studio/.env.example", names)
        self.assertNotIn("presentation-studio/.env", names)
        self.assertFalse(any("/.git/" in name for name in names))
        self.assertFalse(any("/node_modules/" in name for name in names))
        self.assertFalse(any(name.endswith((".log", ".tmp")) for name in names))


if __name__ == "__main__":
    unittest.main()
