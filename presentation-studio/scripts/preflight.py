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


def provider_availability(env: dict[str, str]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for name, keys in PROVIDER_ENV.items():
        if name == "azure":
            result[name] = all(bool(env.get(key)) for key in keys)
        else:
            result[name] = any(bool(env.get(key)) for key in keys)
    return result


def safe_executable_available(value: str | None) -> bool:
    if value is None:
        return False
    path = Path(value)
    return (
        path.is_absolute()
        and "windowsapps" not in {part.lower() for part in path.parts}
        and path.is_file()
    )


def python_module_availability(names: tuple[str, ...]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for name in names:
        try:
            result[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            result[name] = False
    return result


def node_module_availability(
    node_executable: str,
    package_root: Path,
    names: tuple[str, ...],
) -> dict[str, bool]:
    result = {name: False for name in names}
    if not safe_executable_available(node_executable):
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
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            return {name: bool(payload.get(name)) for name in names}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
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
    runtimes = {
        "python": safe_executable_available(args.python),
        "node": safe_executable_available(args.node),
        "office_renderer": safe_executable_available(args.office_renderer),
        "chromium": safe_executable_available(args.chromium),
    }
    providers = provider_availability(dict(os.environ))
    python_modules = python_module_availability(PYTHON_MODULES)
    node_package_root = resolve_node_modules(args.node, args.node_modules)
    node_modules = (
        node_module_availability(args.node, node_package_root, NODE_MODULES)
        if node_package_root
        else {name: False for name in NODE_MODULES}
    )
    capabilities = summarize_capabilities(python_modules, node_modules)
    capabilities["node"]["browser_qa"] = capabilities["node"]["browser_qa"] and runtimes["chromium"]
    required_runtimes = (runtimes["python"], runtimes["node"])
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
            "image_provider": any(providers.values()),
        },
        "notes": [
            "Provider values are redacted; booleans indicate credential presence only.",
            "Optional capability booleans report module availability without installing packages.",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(required_runtimes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
