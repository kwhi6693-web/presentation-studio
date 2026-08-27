from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"


def _node_executable() -> str:
    configured = os.environ.get("PRESENTATION_STUDIO_NODE")
    runtime_root = os.environ.get("PRESENTATION_STUDIO_RUNTIME_ROOT")
    bundled = (
        Path(runtime_root)
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
        if runtime_root
        else None
    )
    candidates = [
        configured,
        str(bundled) if bundled else None,
        r"C:\Program Files\nodejs\node.exe",
        shutil.which("node"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise unittest.SkipTest("A real Node.js executable is required for installation smoke testing")


def _powershell_executable() -> str:
    candidate = shutil.which("pwsh") or shutil.which("powershell")
    if candidate:
        return candidate
    system_candidate = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if system_candidate.is_file():
        return str(system_candidate)
    raise unittest.SkipTest("PowerShell is required for the Windows installer smoke test")


def _bash_executable() -> str:
    runtime_root = os.environ.get("PRESENTATION_STUDIO_RUNTIME_ROOT")
    bundled = (
        Path(runtime_root)
        / "dependencies"
        / "native"
        / "git"
        / "usr"
        / "bin"
        / "bash.exe"
        if runtime_root
        else None
    )
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
        str(bundled) if bundled else None,
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            resolved = str(Path(candidate).resolve())
            if os.name == "nt":
                probe = subprocess.run(
                    [resolved, "-lc", "command -v cygpath"],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                if probe.returncode != 0:
                    continue
            return resolved
    raise unittest.SkipTest("Bash is required for the POSIX installer smoke test")


def _bash_path(bash: str, path: Path) -> str:
    if os.name != "nt":
        return str(path)
    result = subprocess.run(
        [bash, "-lc", 'cygpath -u "$1"', "presentation-studio-test", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class InstalledSkillSelfCheckTests(unittest.TestCase):
    def test_self_check_executes_from_an_isolated_skill_copy(self) -> None:
        script = SKILL_ROOT / "scripts" / "self_check.py"
        self.assertTrue(script.is_file(), "The installable skill has no self-check entry point")

        with tempfile.TemporaryDirectory(prefix="presentation-studio-self-check-") as temp:
            installed_root = Path(temp) / "presentation-studio"
            shutil.copytree(SKILL_ROOT, installed_root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(installed_root / "scripts" / "self_check.py"),
                    "--root",
                    str(installed_root),
                    "--python",
                    str(Path(sys.executable).resolve()),
                    "--node",
                    _node_executable(),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["package"]["engines"], 4)
        self.assertEqual(payload["smoke"]["product"], "dual-format-deck")
        self.assertEqual(payload["smoke"]["engines"], ["ppt-master", "frontend-slides"])


class RuntimeResolverTests(unittest.TestCase):
    def test_resolver_accepts_a_configured_generic_runtime_root(self) -> None:
        powershell = _powershell_executable()
        resolver = SKILL_ROOT / "scripts" / "resolve-runtimes.ps1"

        with tempfile.TemporaryDirectory(prefix="presentation-studio-runtime-") as temp:
            runtime_root = Path(temp) / "runtime"
            for relative_path in (
                "dependencies/python/python.exe",
                "dependencies/node/bin/node.exe",
                "dependencies/native/git/cmd/git.exe",
            ):
                executable = runtime_root / relative_path
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_text("placeholder", encoding="utf-8")

            env = dict(os.environ)
            env["PRESENTATION_STUDIO_RUNTIME_ROOT"] = str(runtime_root)
            command = (
                "$ErrorActionPreference = 'Stop'; "
                f". '{resolver}'; "
                "$result = Resolve-PresentationStudioRuntimeSet "
                "-RuntimeRoot $env:PRESENTATION_STUDIO_RUNTIME_ROOT; "
                "$result | ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["source"], "configured-runtime-root")
        self.assertNotEqual(payload["source"], "codex-app-bundle")


class PowerShellInstallerTests(unittest.TestCase):
    def test_force_install_moves_backup_outside_the_skill_discovery_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-install-") as temp:
            agents_root = Path(temp) / ".agents"
            skills_root = agents_root / "skills"
            destination = skills_root / "presentation-studio"
            destination.mkdir(parents=True)
            marker = destination / "previous-install.txt"
            marker.write_text("preserve me", encoding="utf-8")

            result = subprocess.run(
                [
                    _powershell_executable(),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts" / "install.ps1"),
                    "-Destination",
                    str(destination),
                    "-Force",
                    "-PythonExecutable",
                    str(Path(sys.executable).resolve()),
                    "-NodeExecutable",
                    _node_executable(),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            discoverable_backups = tuple(skills_root.glob("presentation-studio.backup-*"))
            backup_root = agents_root / "skill-backups" / "presentation-studio"
            backups = tuple(path for path in backup_root.iterdir() if path.is_dir()) if backup_root.is_dir() else ()

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertEqual(discoverable_backups, ())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / marker.name).read_text(encoding="utf-8"), "preserve me")
            self.assertIn("Self-check: PASS", result.stdout)
            self.assertFalse((agents_root / ".skill-staging").exists())

    def test_rejects_a_destination_too_deep_for_a_portable_windows_install(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-deep-install-") as temp:
            destination = Path(temp) / ("x" * 180) / "presentation-studio"
            result = subprocess.run(
                [
                    _powershell_executable(),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts" / "install.ps1"),
                    "-Destination",
                    str(destination),
                    "-PythonExecutable",
                    str(Path(sys.executable).resolve()),
                    "-NodeExecutable",
                    _node_executable(),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Destination path is too deep", output)


class PosixInstallerTests(unittest.TestCase):
    def test_force_install_moves_backup_outside_the_skill_discovery_directory(self) -> None:
        bash = _bash_executable()
        with tempfile.TemporaryDirectory(prefix="presentation-studio-install-sh-") as temp:
            agents_root = Path(temp) / ".agents"
            skills_root = agents_root / "skills"
            destination = skills_root / "presentation-studio"
            destination.mkdir(parents=True)
            marker = destination / "previous-install.txt"
            marker.write_text("preserve me", encoding="utf-8")

            env = dict(os.environ)
            env.update(
                {
                    "FORCE": "1",
                    "PRESENTATION_STUDIO_PYTHON": _bash_path(bash, Path(sys.executable).resolve()),
                    "PRESENTATION_STUDIO_NODE": _bash_path(bash, Path(_node_executable())),
                }
            )
            result = subprocess.run(
                [
                    bash,
                    _bash_path(bash, ROOT / "scripts" / "install.sh"),
                    _bash_path(bash, destination),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )

            discoverable_backups = tuple(skills_root.glob("presentation-studio.backup-*"))
            backup_root = agents_root / "skill-backups" / "presentation-studio"
            backups = tuple(path for path in backup_root.iterdir() if path.is_dir()) if backup_root.is_dir() else ()

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertEqual(discoverable_backups, ())
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / marker.name).read_text(encoding="utf-8"), "preserve me")
            self.assertIn("Self-check: PASS", result.stdout)
            self.assertFalse((agents_root / ".skill-staging").exists())


if __name__ == "__main__":
    unittest.main()
