from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = ROOT / "presentation-studio" / "scripts" / "preflight.py"
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("presentation_studio_preflight", PREFLIGHT_PATH)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


def _node_executable() -> str:
    configured = os.environ.get("PRESENTATION_STUDIO_NODE")
    bundled = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    for candidate in (configured, str(bundled), shutil.which("node")):
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise unittest.SkipTest("Node.js is required for capability probing")


class CapabilityPreflightTests(unittest.TestCase):
    def test_runtime_probe_rejects_an_arbitrary_existing_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-runtime-probe-") as temp:
            arbitrary_file = Path(temp) / "not-a-runtime.txt"
            arbitrary_file.write_text("not executable\n", encoding="utf-8")

            self.assertFalse(PREFLIGHT.probe_executable(str(arbitrary_file)))

    def test_runtime_probe_uses_a_bounded_shell_free_argument_list(self) -> None:
        executable = str(Path(sys.executable).resolve())
        completed = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch.object(PREFLIGHT.subprocess, "run", return_value=completed) as run:
            self.assertTrue(PREFLIGHT.probe_executable(executable, ("--version",)))

        args, kwargs = run.call_args
        self.assertEqual(args[0], [executable, "--version"])
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["text"])
        self.assertLessEqual(kwargs["timeout"], 10)

    def test_runtime_identity_rejects_node_as_python_and_python_as_node(self) -> None:
        modules = {name: False for name in PREFLIGHT.PYTHON_MODULES}
        node_modules = {name: False for name in PREFLIGHT.NODE_MODULES}
        cases = (
            ("node-as-python", _node_executable(), _node_executable(), "python"),
            ("python-as-node", sys.executable, sys.executable, "node"),
        )
        for name, python_executable, node_executable, unavailable_runtime in cases:
            with self.subTest(name=name), mock.patch.object(
                PREFLIGHT, "python_module_availability", return_value=modules
            ), mock.patch.object(
                PREFLIGHT, "node_module_availability", return_value=node_modules
            ), redirect_stdout(io.StringIO()) as output:
                exit_code = PREFLIGHT.main(
                    ["--python", python_executable, "--node", node_executable]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["status"], "FAIL")
            self.assertFalse(payload["readiness"][unavailable_runtime])
            self.assertEqual(
                payload["readiness_detail"][unavailable_runtime]["state"], "unavailable"
            )

    def test_runtime_identity_rejects_whitespace_wrapped_marker(self) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout=b" \tpresentation-studio-python-probe\r\n ",
            stderr=b"",
        )
        with mock.patch.object(PREFLIGHT.subprocess, "run", return_value=completed):
            self.assertFalse(PREFLIGHT.probe_python_executable(sys.executable))

    def test_preflight_preserves_boolean_readiness_and_adds_tri_state_evidence(self) -> None:
        modules = {name: False for name in PREFLIGHT.PYTHON_MODULES}
        node_modules = {name: False for name in PREFLIGHT.NODE_MODULES}
        output = io.StringIO()
        with (
            mock.patch.object(PREFLIGHT, "python_module_availability", return_value=modules),
            mock.patch.object(PREFLIGHT, "node_module_availability", return_value=node_modules),
            redirect_stdout(output),
        ):
            exit_code = PREFLIGHT.main(["--python", sys.executable, "--node", _node_executable()])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        legacy_keys = {"python", "node", "office_renderer", "chromium", "image_provider"}
        self.assertTrue(legacy_keys.issubset(payload["readiness"]))
        self.assertTrue(
            all(isinstance(payload["readiness"][key], bool) for key in legacy_keys)
        )
        self.assertEqual(payload["readiness_detail"]["python"]["state"], "available")
        self.assertEqual(payload["readiness_detail"]["office_renderer"]["state"], "unknown")
        self.assertIn(
            payload["readiness_detail"]["image_provider"]["state"],
            {"available", "unavailable"},
        )
        self.assertIsInstance(
            payload["readiness_detail"]["image_provider"]["credentials_present"], bool
        )

    def test_chromium_readiness_uses_playwright_render_when_version_probe_would_timeout(self) -> None:
        python_executable = str(Path(sys.executable).resolve())
        node_executable = _node_executable()
        completed_commands: list[list[str]] = []
        with tempfile.TemporaryDirectory(prefix="presentation-studio-chromium-probe-") as temp:
            root = Path(temp)
            package_root = root / "node_modules"
            package_root.mkdir()
            chromium = root / "msedge.exe"
            chromium.write_bytes(b"test browser placeholder")

            def completed(stdout: bytes = b"", *, returncode: int = 0) -> mock.Mock:
                return mock.Mock(returncode=returncode, stdout=stdout, stderr=b"")

            def run(command: list[str], **_kwargs: object) -> mock.Mock:
                completed_commands.append(command)
                if command == [python_executable, *PREFLIGHT._PYTHON_PROBE_ARGS]:
                    return completed(PREFLIGHT._PYTHON_PROBE_MARKER)
                if command == [node_executable, *PREFLIGHT._NODE_PROBE_ARGS]:
                    return completed(PREFLIGHT._NODE_PROBE_MARKER)
                if command[0] == python_executable and "importlib.util.find_spec" in command[2]:
                    return completed(b"{}")
                if command[0] == node_executable and "require.resolve" in command[2]:
                    return completed(b'{"playwright":true}')
                if command == [str(chromium), "--version"]:
                    raise PREFLIGHT.subprocess.TimeoutExpired(command, 5)
                if command[0] == node_executable and str(chromium) in command:
                    return completed(
                        b'{"marker":"PRESENTATION_STUDIO_CHROMIUM_OK",'
                        b'"title":"presentation-studio-probe","version":"151.0.4129.93"}'
                    )
                raise AssertionError(f"unexpected command: {command!r}")

            output = io.StringIO()
            with mock.patch.object(PREFLIGHT.subprocess, "run", side_effect=run), redirect_stdout(
                output
            ):
                exit_code = PREFLIGHT.main(
                    [
                        "--python",
                        python_executable,
                        "--node",
                        node_executable,
                        "--node-modules",
                        str(package_root),
                        "--chromium",
                        str(chromium),
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["runtimes"]["chromium"])
        self.assertTrue(payload["capabilities"]["node"]["browser_qa"])
        self.assertEqual(
            payload["environment_handoff"]["PRESENTATION_STUDIO_CHROMIUM"],
            str(chromium),
        )
        self.assertEqual(
            payload["readiness_detail"]["chromium"]["evidence"]["probe"],
            "playwright_local_render",
        )
        self.assertFalse(any(command[0] == str(chromium) for command in completed_commands))

    def test_python_module_probe_uses_selected_interpreter_with_bounded_shell_free_call(self) -> None:
        executable = str(Path(sys.executable).resolve())
        completed = mock.Mock(
            returncode=0,
            stdout=b'{"json": true, "presentation_studio_missing_module": false}',
            stderr=b"",
        )
        with mock.patch.object(PREFLIGHT.subprocess, "run", return_value=completed) as run:
            result = PREFLIGHT.python_module_availability(
                executable, ("json", "presentation_studio_missing_module")
            )

        self.assertEqual(result, {"json": True, "presentation_studio_missing_module": False})
        args, kwargs = run.call_args
        self.assertEqual(args[0][0:2], [executable, "-c"])
        self.assertIn("importlib.util.find_spec", args[0][2])
        self.assertEqual(args[0][3], '["json", "presentation_studio_missing_module"]')
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["text"])
        self.assertLessEqual(kwargs["timeout"], 10)

    def test_python_module_probe_returns_all_false_for_wrong_runtime_and_decode_error(self) -> None:
        names = ("json", "presentation_studio_missing_module")
        self.assertEqual(
            PREFLIGHT.python_module_availability(_node_executable(), names),
            {"json": False, "presentation_studio_missing_module": False},
        )
        with mock.patch.object(PREFLIGHT.subprocess, "run", side_effect=UnicodeDecodeError(
            "utf-8", b"\xff", 0, 1, "invalid"
        )):
            self.assertFalse(PREFLIGHT.probe_executable(sys.executable))

    def test_capability_readiness_blocks_pptx_product_until_selected_python_has_core_modules(self) -> None:
        node = _node_executable()
        empty_python_modules = {name: False for name in PREFLIGHT.PYTHON_MODULES}
        empty_node_modules = {name: False for name in PREFLIGHT.NODE_MODULES}

        def preflight_payload(python_modules: dict[str, bool]) -> dict[str, object]:
            output = io.StringIO()
            with (
                mock.patch.object(
                    PREFLIGHT, "python_module_availability", return_value=python_modules
                ),
                mock.patch.object(
                    PREFLIGHT, "node_module_availability", return_value=empty_node_modules
                ),
                redirect_stdout(output),
            ):
                self.assertEqual(PREFLIGHT.main(["--python", sys.executable, "--node", node]), 0)
            return json.loads(output.getvalue())

        missing_core = preflight_payload(empty_python_modules)
        self.assertTrue(missing_core["readiness"]["python"])
        self.assertFalse(missing_core["readiness"]["pptx_core"])

        sys.path.insert(0, str(ROOT / "presentation-studio"))
        try:
            from core.retrieval import recommend_product

            recommendation = recommend_product(
                {
                    "kind": "presentation",
                    "outputs": ["pptx"],
                    "topic": "technical architecture",
                    "readiness": missing_core["readiness"],
                }
            )
        finally:
            sys.path.pop(0)
        self.assertEqual(recommendation.status, "FAIL")

        complete_python_modules = {name: True for name in PREFLIGHT.PYTHON_MODULES}
        available_core = preflight_payload(complete_python_modules)
        self.assertTrue(available_core["readiness"]["pptx_core"])
        self.assertEqual(available_core["readiness_detail"]["pptx_core"]["state"], "available")

    def test_python_module_probe_reports_each_module_independently(self) -> None:
        result = PREFLIGHT.python_module_availability(
            sys.executable, ("json", "presentation_studio_missing_module")
        )
        self.assertEqual(result, {"json": True, "presentation_studio_missing_module": False})

    def test_node_module_probe_uses_the_explicit_package_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="presentation-studio-node-modules-") as temp:
            package_root = Path(temp) / "node_modules"
            module_root = package_root / "presentation-studio-probe"
            module_root.mkdir(parents=True)
            (module_root / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")

            result = PREFLIGHT.node_module_availability(
                _node_executable(),
                package_root,
                ("presentation-studio-probe", "presentation-studio-missing-module"),
            )

        self.assertEqual(
            result,
            {"presentation-studio-probe": True, "presentation-studio-missing-module": False},
        )

    def test_capability_summary_distinguishes_core_and_optional_features(self) -> None:
        python_modules = {
            "pptx": True,
            "xlsxwriter": True,
            "openpyxl": True,
            "PIL": True,
            "numpy": True,
            "pathops": False,
            "uharfbuzz": False,
        }
        node_modules = {"playwright": True, "pptxgenjs": True, "sharp": True, "pdf-lib": True, "tsx": False}

        capabilities = PREFLIGHT.summarize_capabilities(python_modules, node_modules)

        self.assertTrue(capabilities["python"]["pptx_core"])
        self.assertFalse(capabilities["python"]["editable_svg_advanced"])
        self.assertTrue(capabilities["node"]["browser_qa"])
        self.assertTrue(capabilities["node"]["baoyu_core"])
        self.assertFalse(capabilities["node"]["baoyu_tsx_runner"])


if __name__ == "__main__":
    unittest.main()
