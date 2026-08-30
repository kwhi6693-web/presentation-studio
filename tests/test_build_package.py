from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

try:
    from scripts.build_package import build_archive, build_repository_package
except ModuleNotFoundError:
    build_archive = None
    build_repository_package = None

try:
    from scripts.verify_package import verify_archive
except ModuleNotFoundError:
    verify_archive = None

try:
    from scripts.build_release_checksum import build_release_checksum
except ModuleNotFoundError:
    build_release_checksum = None


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

    def test_release_checksum_uses_the_archive_basename_for_colocated_downloads(self) -> None:
        self.assertIsNotNone(
            build_release_checksum, "scripts.build_release_checksum is missing"
        )
        archive_path = self.root / "dist" / "presentation-studio.zip"
        checksum_path = self.root / "release" / "presentation-studio.zip.sha256"
        archive_path.parent.mkdir()
        archive_path.write_bytes(b"release archive bytes")

        digest = build_release_checksum(archive_path, checksum_path)

        expected_digest = hashlib.sha256(b"release archive bytes").hexdigest()
        self.assertEqual(digest, expected_digest)
        self.assertEqual(
            checksum_path.read_text(encoding="ascii"),
            f"{expected_digest}  presentation-studio.zip\n",
        )

    def test_release_checksum_cli_writes_the_requested_asset(self) -> None:
        archive_path = self.root / "presentation-studio.zip"
        checksum_path = self.root / "downloads" / "presentation-studio.zip.sha256"
        archive_path.write_bytes(b"cli release archive")

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "build_release_checksum.py"),
                str(archive_path),
                str(checksum_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("PASS: wrote", result.stdout)
        expected_digest = hashlib.sha256(b"cli release archive").hexdigest()
        self.assertEqual(
            checksum_path.read_text(encoding="ascii"),
            f"{expected_digest}  presentation-studio.zip\n",
        )

    def test_repository_package_uses_the_explicit_checksum_contract(self) -> None:
        self.assertIsNotNone(build_repository_package, "repository package builder is missing")
        archive_path = self.root / "ci" / "presentation-studio.zip"
        checksum_path = self.root / "ci" / "presentation-studio.zip.sha256"

        digest = build_repository_package(self.skill, archive_path, checksum_path)

        self.assertEqual(
            checksum_path.read_text(encoding="ascii"),
            f"{digest}  presentation-studio.zip\n",
        )

    def test_package_verifier_accepts_explicit_archive_and_checksum_paths(self) -> None:
        self.assertIsNotNone(verify_archive, "package verifier is missing")
        archive_path = self.root / "ci" / "presentation-studio.zip"
        checksum_path = self.root / "ci" / "presentation-studio.zip.sha256"
        digest = build_archive(self.skill, archive_path)
        checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")

        with patch("scripts.verify_package.SKILL_ROOT", self.skill):
            summary = verify_archive(2, archive_path, checksum_path)

        self.assertEqual(summary["archive_sha256"], digest)
        self.assertEqual(summary["archive_files"], 2)

    def test_build_cli_compares_two_requested_archives(self) -> None:
        builder = Path(__file__).resolve().parents[1] / "scripts" / "build_package.py"
        first = self.root / "ci" / "presentation-studio-a.zip"
        first_checksum = self.root / "ci" / "presentation-studio-a.zip.sha256"
        second = self.root / "ci" / "presentation-studio-b.zip"
        second_checksum = self.root / "ci" / "presentation-studio-b.zip.sha256"

        result = subprocess.run(
            [
                sys.executable,
                str(builder),
                "--skill-root",
                str(self.skill),
                "--archive",
                str(first),
                "--checksum",
                str(first_checksum),
                "--compare-archive",
                str(second),
                "--compare-checksum",
                str(second_checksum),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        first_digest = first_checksum.read_text(encoding="ascii").split()[0]
        second_digest = second_checksum.read_text(encoding="ascii").split()[0]
        self.assertEqual(first_digest, second_digest)
        self.assertIn("PASS: deterministic comparison", result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for package smoke validation")
    def test_package_verifier_smokes_a_fresh_extraction(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        builder = repository_root / "scripts" / "build_package.py"
        verifier = repository_root / "scripts" / "verify_package.py"
        archive = self.root / "ci" / "presentation-studio.zip"
        checksum = self.root / "ci" / "presentation-studio.zip.sha256"

        build_repository_package(repository_root / "presentation-studio", archive, checksum)
        result = subprocess.run(
            [
                sys.executable,
                str(verifier),
                "--archive",
                str(archive),
                "--checksum",
                str(checksum),
                "--smoke",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('"smoke":', result.stdout)


if __name__ == "__main__":
    unittest.main()
