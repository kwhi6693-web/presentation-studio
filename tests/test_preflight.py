from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


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
    def test_python_module_probe_reports_each_module_independently(self) -> None:
        result = PREFLIGHT.python_module_availability(("json", "presentation_studio_missing_module"))
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
