#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path


PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "azure": ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL"),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY",),
    "dashscope": ("DASHSCOPE_API_KEY",),
    "zai": ("ZAI_API_KEY", "BIGMODEL_API_KEY"),
    "minimax": ("MINIMAX_API_KEY",),
    "replicate": ("REPLICATE_API_TOKEN",),
    "jimeng": ("JIMENG_ACCESS_KEY",),
    "seedream": ("ARK_API_KEY",),
    "agnes": ("AGNES_API_KEY",),
}
PYTHON_MODULES = (
    "pptx",
    "xlsxwriter",
    "openpyxl",
    "PIL",
    "numpy",
    "pathops",
    "uharfbuzz",
    "edge_tts",
    "fitz",
    "mammoth",
    "markdownify",
    "ebooklib",
    "nbconvert",
    "requests",
    "bs4",
    "google.genai",
    "flask",
)
NODE_MODULES = (
    "playwright",
    "pptxgenjs",
    "sharp",
    "pdf-lib",
    "tsx",
    "@mozilla/readability",
    "linkedom",
    "turndown",
)
CAPABILITY_PREREQUISITES = {
    "pptx_core": ("python", "pptx_core"),
    "baoyu_core": ("node", "baoyu_core"),
}
_PYTHON_PROBE_ARGS = (
    "-c",
    "import sys;sys.stdout.buffer.write(b'presentation-studio-python-probe\\n')",
)
_NODE_PROBE_ARGS = (
    "-e",
    "process.stdout.write(JSON.stringify({marker:'presentation-studio-node-probe',version:process.versions.node}))",
)
_PYTHON_PROBE_MARKER = b"presentation-studio-python-probe\n"
_NODE_PROBE_MARKER = "presentation-studio-node-probe"
_MIN_NODE_VERSION = (20, 9, 0)
_CHROMIUM_PROBE_MARKER = "PRESENTATION_STUDIO_CHROMIUM_OK"
_CHROMIUM_PROBE_TITLE = "presentation-studio-probe"
_CHROMIUM_PROBE_SCRIPT = (
    "const executablePath=process.argv[1];"
    "(async()=>{let browser;try{"
    "const{chromium}=require('playwright');"
    "browser=await chromium.launch({executablePath,headless:true,args:["
    "'--no-first-run','--no-default-browser-check','--disable-background-networking',"
    "'--disable-component-update']});"
    "const page=await browser.newPage();"
    "await page.setContent('<!doctype html><title>presentation-studio-probe</title>',"
    "{waitUntil:'load'});"
    "const title=await page.title();"
    "process.stdout.write(JSON.stringify({"
    "marker:'PRESENTATION_STUDIO_CHROMIUM_OK',title,version:browser.version()}));"
    "}finally{if(browser)await browser.close();}})().catch(error=>{"
    "process.stderr.write(String(error&&error.message||error));process.exitCode=1;});"
)


def provider_availability(env: dict[str, str]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for name, keys in PROVIDER_ENV.items():
        if name == "azure":
            result[name] = all(bool(env.get(key)) for key in keys)
        else:
            result[name] = any(bool(env.get(key)) for key in keys)
    return result


def _safe_executable_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not (
        path.is_absolute()
        and "windowsapps" not in {part.lower() for part in path.parts}
        and path.is_file()
    ):
        return None
    return path


def probe_executable(value: str | None, version_args: tuple[str, ...] = ("--version",)) -> bool:
    path = _safe_executable_path(value)
    if path is None:
        return False
    try:
        completed = subprocess.run(
            [str(path), *version_args],
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return False
    return completed.returncode == 0


def _probe_runtime(value: str | None, args: tuple[str, ...], marker: bytes) -> bool:
    path = _safe_executable_path(value)
    if path is None:
        return False
    try:
        completed = subprocess.run(
            [str(path), *args],
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return False
    return completed.returncode == 0 and completed.stdout == marker


def probe_python_executable(value: str | None) -> bool:
    return _probe_runtime(value, _PYTHON_PROBE_ARGS, _PYTHON_PROBE_MARKER)


def probe_node_executable(value: str | None) -> bool:
    path = _safe_executable_path(value)
    if path is None:
        return False
    try:
        completed = subprocess.run(
            [str(path), *_NODE_PROBE_ARGS],
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=5,
        )
        payload = json.loads(completed.stdout.decode("utf-8"))
        if type(payload) is not dict:
            return False
        marker = payload.get("marker")
        version = payload.get("version")
        parts = (
            tuple(int(part) for part in version.split("."))
            if type(version) is str
            else ()
        )
    except (
        OSError,
        subprocess.SubprocessError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        return False
    return (
        completed.returncode == 0
        and marker == _NODE_PROBE_MARKER
        and len(parts) == 3
        and parts >= _MIN_NODE_VERSION
    )


def safe_executable_available(value: str | None) -> bool:
    return probe_executable(value)


def probe_chromium(
    value: str | None,
    node_executable: str,
    package_root: Path | None,
    playwright_available: bool,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "probe": "playwright_local_render",
        "configured": value is not None,
        "playwright_available": playwright_available,
    }
    if value is None:
        return {"available": False, "state": "unknown", "evidence": evidence}
    chromium_path = _safe_executable_path(value)
    if chromium_path is None:
        evidence["executable_valid"] = False
        return {"available": False, "state": "unavailable", "evidence": evidence}
    evidence["executable_valid"] = True
    if (
        not playwright_available
        or _safe_executable_path(node_executable) is None
        or package_root is None
        or not package_root.is_dir()
    ):
        return {"available": False, "state": "unknown", "evidence": evidence}

    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(
        part for part in (str(package_root.resolve()), env.get("NODE_PATH", "")) if part
    )
    command = [node_executable, "-e", _CHROMIUM_PROBE_SCRIPT, str(chromium_path)]
    try:
        completed = subprocess.run(
            command,
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=15,
            env=env,
        )
    except subprocess.TimeoutExpired:
        evidence["reason"] = "probe_timeout"
        return {"available": False, "state": "unknown", "evidence": evidence}
    except (OSError, subprocess.SubprocessError, UnicodeError):
        evidence["reason"] = "probe_error"
        return {"available": False, "state": "unknown", "evidence": evidence}
    if completed.returncode != 0:
        evidence["reason"] = "launch_failed"
        return {"available": False, "state": "unavailable", "evidence": evidence}
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        evidence["reason"] = "invalid_response"
        return {"available": False, "state": "unavailable", "evidence": evidence}
    version = payload.get("version") if type(payload) is dict else None
    if not (
        type(payload) is dict
        and payload.get("marker") == _CHROMIUM_PROBE_MARKER
        and payload.get("title") == _CHROMIUM_PROBE_TITLE
        and type(version) is str
        and bool(version)
    ):
        evidence["reason"] = "invalid_response"
        return {"available": False, "state": "unavailable", "evidence": evidence}
    evidence.update(
        {
            "launch_succeeded": True,
            "local_render_succeeded": True,
            "version": version,
        }
    )
    return {"available": True, "state": "available", "evidence": evidence}


def python_module_availability(
    python_executable: str,
    names: tuple[str, ...],
) -> dict[str, bool]:
    result = {name: False for name in names}
    if _safe_executable_path(python_executable) is None:
        return result
    script = (
        "import importlib.util,json,sys\n"
        "names=json.loads(sys.argv[1])\n"
        "out={}\n"
        "for name in names:\n"
        "    try:\n"
        "        out[name]=importlib.util.find_spec(name) is not None\n"
        "    except (ImportError,AttributeError,ValueError):\n"
        "        out[name]=False\n"
        "print(json.dumps(out))\n"
    )
    try:
        completed = subprocess.run(
            [python_executable, "-c", script, json.dumps(names)],
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=5,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout.decode("utf-8"))
            return {name: bool(payload.get(name)) for name in names}
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError):
        pass
    return result


def node_module_availability(
    node_executable: str,
    package_root: Path,
    names: tuple[str, ...],
) -> dict[str, bool]:
    result = {name: False for name in names}
    if not probe_node_executable(node_executable):
        return result
    package_root = package_root.resolve()
    if not package_root.is_dir():
        return result
    script = (
        "const names=JSON.parse(process.argv[1]);const out={};"
        "for(const name of names){try{require.resolve(name);out[name]=true;}catch{out[name]=false;}}"
        "process.stdout.write(JSON.stringify(out));"
    )
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(
        part for part in (str(package_root), env.get("NODE_PATH", "")) if part
    )
    try:
        completed = subprocess.run(
            [node_executable, "-e", script, json.dumps(names)],
            check=False,
            shell=False,
            capture_output=True,
            text=False,
            timeout=20,
            env=env,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout.decode("utf-8"))
            return {name: bool(payload.get(name)) for name in names}
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError):
        pass
    return result


def summarize_capabilities(
    python_modules: dict[str, bool],
    node_modules: dict[str, bool],
) -> dict[str, dict[str, bool]]:
    def has_python(*names: str) -> bool:
        return all(python_modules.get(name, False) for name in names)

    def has_node(*names: str) -> bool:
        return all(node_modules.get(name, False) for name in names)

    return {
        "python": {
            "pptx_core": has_python("pptx", "xlsxwriter", "openpyxl", "PIL", "numpy"),
            "editable_svg_advanced": has_python("pathops", "uharfbuzz"),
            "narration": has_python("edge_tts"),
            "pdf_ingest": has_python("fitz"),
            "document_ingest": has_python("mammoth", "markdownify", "ebooklib", "nbconvert"),
            "web_ingest": has_python("requests", "bs4"),
            "google_image_backend": has_python("google.genai"),
            "svg_editor": has_python("flask"),
        },
        "node": {
            "browser_qa": has_node("playwright"),
            "baoyu_core": has_node("pptxgenjs", "sharp", "pdf-lib"),
            "baoyu_tsx_runner": has_node("tsx"),
            "web_ingest": has_node("@mozilla/readability", "linkedom", "turndown"),
        },
    }


def resolve_node_modules(node_executable: str | None, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path.resolve() if path.is_absolute() and path.is_dir() else None
    if not node_executable or not safe_executable_available(node_executable):
        return None
    candidate = Path(node_executable).resolve().parent.parent / "node_modules"
    return candidate if candidate.is_dir() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Presentation Studio runtime availability without exposing secrets")
    parser.add_argument("--python", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--node-modules")
    parser.add_argument("--office-renderer")
    parser.add_argument("--chromium")
    args = parser.parse_args(argv)
    runtime_inputs = {
        "python": args.python,
        "node": args.node,
        "office_renderer": args.office_renderer,
        "chromium": args.chromium,
    }
    runtimes: dict[str, bool] = {
        "python": probe_python_executable(args.python),
        "node": probe_node_executable(args.node),
        "office_renderer": safe_executable_available(args.office_renderer),
        "chromium": False,
    }
    providers = provider_availability(dict(os.environ))
    python_modules = (
        python_module_availability(args.python, PYTHON_MODULES)
        if runtimes["python"]
        else {name: False for name in PYTHON_MODULES}
    )
    node_package_root = resolve_node_modules(args.node, args.node_modules)
    node_modules = (
        node_module_availability(args.node, node_package_root, NODE_MODULES)
        if node_package_root
        else {name: False for name in NODE_MODULES}
    )
    chromium_probe = probe_chromium(
        args.chromium,
        args.node,
        node_package_root,
        node_modules.get("playwright", False),
    )
    runtimes["chromium"] = bool(chromium_probe["available"])
    capabilities = summarize_capabilities(python_modules, node_modules)
    capabilities["node"]["browser_qa"] = capabilities["node"]["browser_qa"] and runtimes["chromium"]
    required_runtimes = (runtimes["python"], runtimes["node"])
    provider_credentials_present = any(providers.values())
    capability_readiness = {
        prerequisite: runtimes[runtime] and capabilities[runtime][capability]
        for prerequisite, (runtime, capability) in CAPABILITY_PREREQUISITES.items()
    }
    readiness_detail = {
        name: {
            "state": (
                "available" if runtimes[name] else "unknown" if value is None else "unavailable"
            ),
            "evidence": {
                "runtime_probe": runtimes[name],
                **({"capabilities": capabilities[name]} if name in capabilities else {}),
            },
        }
        for name, value in runtime_inputs.items()
    }
    readiness_detail["chromium"] = {
        "state": chromium_probe["state"],
        "evidence": chromium_probe["evidence"],
    }
    readiness_detail["image_provider"] = {
        "state": "available" if provider_credentials_present else "unavailable",
        "credentials_present": provider_credentials_present,
    }
    for prerequisite, (runtime, capability) in CAPABILITY_PREREQUISITES.items():
        ready = capability_readiness[prerequisite]
        readiness_detail[prerequisite] = {
            "state": "available" if ready else "unavailable",
            "evidence": {"runtime": runtime, "capability": capability},
        }
    result = {
        "status": "PASS" if all(required_runtimes) else "FAIL",
        "runtimes": runtimes,
        "providers": providers,
        "modules": {"python": python_modules, "node": node_modules},
        "capabilities": capabilities,
        "node_package_root": str(node_package_root) if node_package_root else None,
        "environment_handoff": {
            "NODE_PATH": str(node_package_root) if node_package_root else None,
            "PRESENTATION_STUDIO_CHROMIUM": args.chromium if runtimes["chromium"] else None,
        },
        "readiness": {
            "python": runtimes["python"],
            "node": runtimes["node"],
            "office_renderer": runtimes["office_renderer"],
            "chromium": runtimes["chromium"],
            "image_provider": provider_credentials_present,
            **capability_readiness,
        },
        "readiness_detail": readiness_detail,
        "notes": [
            "Provider values are redacted; credentials_present indicates credential presence only.",
            "Optional capability booleans report module availability without installing packages.",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(required_runtimes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
