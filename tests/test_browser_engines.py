from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "presentation-studio"


def _existing_path(candidates: tuple[str | None, ...], label: str) -> str:
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise unittest.SkipTest(f"{label} is required for rendered browser integration tests")


def _node_executable() -> str:
    runtime_root = os.environ.get("PRESENTATION_STUDIO_RUNTIME_ROOT")
    bundled = (
        Path(runtime_root) / "dependencies" / "node" / "bin" / "node.exe"
        if runtime_root
        else None
    )
    return _existing_path(
        (
            os.environ.get("PRESENTATION_STUDIO_NODE"),
            str(bundled) if bundled else None,
            r"C:\Program Files\nodejs\node.exe",
            shutil.which("node"),
        ),
        "Node.js",
    )


def _chromium_executable() -> str:
    return _existing_path(
        (
            os.environ.get("PRESENTATION_STUDIO_CHROMIUM"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            shutil.which("google-chrome"),
        ),
        "Chromium or Microsoft Edge",
    )


def _node_package_root() -> Path:
    configured = os.environ.get("PRESENTATION_STUDIO_NODE_MODULES")
    runtime_root = os.environ.get("PRESENTATION_STUDIO_RUNTIME_ROOT")
    bundled = (
        Path(runtime_root) / "dependencies" / "node" / "node_modules"
        if runtime_root
        else None
    )
    candidates = (configured, str(bundled) if bundled else None)
    for candidate in candidates:
        if candidate and (Path(candidate) / "playwright").is_dir():
            return Path(candidate).resolve()
    raise unittest.SkipTest("Playwright package root is required for rendered browser integration tests")


def _browser_env() -> dict[str, str]:
    env = dict(os.environ)
    env["NODE_PATH"] = str(_node_package_root())
    env["PRESENTATION_STUDIO_CHROMIUM"] = _chromium_executable()
    return env


class BrowserEngineIntegrationTests(unittest.TestCase):
    def test_frontend_example_has_five_slides_keyboard_navigation_and_edit_mode(self) -> None:
        source = ROOT / "examples" / "bilingual-acceptance" / "en" / "presentation-acceptance-en.html"
        script = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PRESENTATION_STUDIO_CHROMIUM });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
    await page.goto(process.argv[1], { waitUntil: 'domcontentloaded' });
    const snapshot = () => page.evaluate(() => ({
      slides: document.querySelectorAll('.slide').length,
      active: [...document.querySelectorAll('.slide')].findIndex((slide) => slide.classList.contains('active')),
      editable: document.querySelectorAll('[contenteditable="true"]').length,
    }));
    const initial = await snapshot();
    await page.keyboard.press('ArrowRight');
    const advanced = await snapshot();
    await page.keyboard.press('e');
    const editing = await snapshot();
    process.stdout.write(JSON.stringify({ initial, advanced, editing }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            [_node_executable(), "-e", script, source.resolve().as_uri()],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_browser_env(),
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["initial"]["slides"], 5)
        self.assertEqual(payload["initial"]["active"], 0)
        self.assertEqual(payload["advanced"]["active"], 1)
        self.assertGreater(payload["editing"]["editable"], 0)

    def test_guizang_uses_the_preflighted_system_chromium_for_measurements(self) -> None:
        result = subprocess.run(
            [
                _node_executable(),
                str(SKILL_ROOT / "engines" / "guizang" / "scripts" / "validate-swiss-deck.mjs"),
                str(SKILL_ROOT / "engines" / "guizang" / "assets" / "template-swiss.html"),
                "--allow-experimental",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_browser_env(),
            timeout=60,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("Rendered measurement skipped", output)
        self.assertIn("Swiss deck validation passed", output)

    def test_frontend_export_uses_the_preflighted_system_chromium(self) -> None:
        source = ROOT / "examples" / "bilingual-acceptance" / "en" / "presentation-acceptance-en.html"
        with tempfile.TemporaryDirectory(prefix="presentation-studio-browser-") as temp:
            output = Path(temp) / "presentation.pdf"
            result = subprocess.run(
                [
                    _node_executable(),
                    str(SKILL_ROOT / "engines" / "frontend-slides" / "scripts" / "export-pdf.mjs"),
                    str(source),
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=_browser_env(),
                timeout=90,
            )
            payload = output.read_bytes() if output.is_file() else b""

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertTrue(payload.startswith(b"%PDF-"))
        self.assertGreater(len(payload), 10_000)


if __name__ == "__main__":
    unittest.main()
