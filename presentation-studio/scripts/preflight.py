#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Presentation Studio runtime availability without exposing secrets")
    parser.add_argument("--python", required=True)
    parser.add_argument("--node", required=True)
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
    required_runtimes = (runtimes["python"], runtimes["node"])
    result = {
        "status": "PASS" if all(required_runtimes) else "FAIL",
        "runtimes": runtimes,
        "providers": providers,
        "readiness": {
            "python": runtimes["python"],
            "node": runtimes["node"],
            "office_renderer": runtimes["office_renderer"],
            "chromium": runtimes["chromium"],
            "image_provider": any(providers.values()),
        },
        "notes": ["Provider values are redacted; booleans indicate credential presence only."],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(required_runtimes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
