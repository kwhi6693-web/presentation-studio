#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


REQUIRED_READMES = (
    "README.md",
    "README.zh-CN.md",
    "README.zh-TW.md",
)

REQUIRED_COMMUNITY_FILES = REQUIRED_READMES + (
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/upstream_sync.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
)

ISSUE_FORMS = (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/upstream_sync.yml",
)

REVIEWED_ACTIONS = {
    "actions/checkout": (
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "v7.0.1",
    ),
    "actions/setup-python": (
        "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "v7.0.0",
    ),
    "actions/setup-node": (
        "820762786026740c76f36085b0efc47a31fe5020",
        "v7.0.0",
    ),
    "actions/upload-artifact": (
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "v7.0.1",
    ),
    "actions/create-github-app-token": (
        "bcd2ba49218906704ab6c1aa796996da409d3eb1",
        "v3.2.0",
    ),
}

EXPECTED_ACTION_COUNTS = {
    "actions/checkout": 5,
    "actions/setup-python": 4,
    "actions/setup-node": 3,
    "actions/upload-artifact": 1,
    "actions/create-github-app-token": 3,
}

PYTHON_CONTRACT_ROOTS = (
    "scripts",
    "tests",
    "presentation-studio/core",
    "presentation-studio/scripts",
)
LOCAL_IMPORT_ROOTS = {"core", "scripts"}
DEPENDENCY_CONTRACT_PATH = "docs/dependencies.md"
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}
HYGIENE_DIRECTORY_NAMES = {
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
HYGIENE_FILE_NAMES = {".coverage", ".DS_Store", ".env", "Thumbs.db"}
HYGIENE_SUFFIXES = {".log", ".pyc", ".pyo", ".swp", ".tmp"}
PRIVATE_USER = Path.home().name
PRIVATE_PATH_RE = re.compile(
    rf"(?i)(?:[A-Z]:[\\/]+Users[\\/]+{re.escape(PRIVATE_USER)}\b|"
    rf"/" + "Users" + rf"/{re.escape(PRIVATE_USER)}\b|"
    rf"/" + "home" + rf"/{re.escape(PRIVATE_USER)}\b)"
)
SECRET_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]+ PRIVATE KEY-----)"
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ACTION_RE = re.compile(
    r"uses:\s*(actions/[A-Za-z0-9_.-]+)@([^\s#]+)(?:\s+#\s+(\S+))?"
)


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    issues: list[str] = []
    issues.extend(_validate_required_files(root))
    issues.extend(_validate_readme_links(root))
    issues.extend(_validate_issue_forms(root))
    issues.extend(_validate_actions(root))
    issues.extend(_validate_dependabot(root))
    issues.extend(_validate_dependency_contract(root))
    issues.extend(_validate_python_imports(root))
    issues.extend(_validate_hygiene(root))
    return sorted(set(issues))


def _validate_required_files(root: Path) -> list[str]:
    return [
        f"missing required community file: {relative_path}"
        for relative_path in REQUIRED_COMMUNITY_FILES
        if not (root / relative_path).is_file()
    ]


def _validate_readme_links(root: Path) -> list[str]:
    issues: list[str] = []
    for readme_name in REQUIRED_READMES:
        readme = root / readme_name
        if not readme.is_file():
            continue
        text = readme.read_text(encoding="utf-8-sig")
        label = "README" if readme_name == "README.md" else readme_name
        for language_target in REQUIRED_READMES:
            if f"]({language_target})" not in text:
                issues.append(
                    f"{readme_name} is missing language switch target: {language_target}"
                )
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip().strip("<>")
            if target.startswith("#"):
                continue
            parsed = urlsplit(target)
            if parsed.scheme.lower() in {"http", "https", "mailto"} or parsed.netloc:
                continue
            relative_path = unquote(parsed.path)
            if not relative_path:
                continue
            resolved = (root / relative_path).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                issues.append(f"{label} local link escapes repository: {relative_path}")
                continue
            if not resolved.exists():
                issues.append(
                    f"{label} local link target does not exist: {relative_path}"
                )
    return issues


def _validate_issue_forms(root: Path) -> list[str]:
    issues: list[str] = []
    for relative_path in ISSUE_FORMS:
        path = root / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for key in ("name", "description", "body"):
            if re.search(rf"(?m)^{key}:\s*", text) is None:
                issues.append(
                    f"issue form missing top-level {key}: {relative_path}"
                )
        if re.search(r"(?m)^\s+validations:\s*$", text) is None:
            issues.append(f"issue form has no validations: {relative_path}")
    return issues


def _validate_actions(root: Path) -> list[str]:
    issues: list[str] = []
    action_counts: Counter[str] = Counter()
    workflow_root = root / ".github" / "workflows"
    if not workflow_root.is_dir():
        return ["GitHub Actions workflow directory is missing"]

    workflow_paths = sorted(workflow_root.glob("*.yml")) + sorted(
        workflow_root.glob("*.yaml")
    )
    for path in workflow_paths:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "uses: actions/" not in line:
                continue
            match = ACTION_RE.search(line)
            if match is None:
                reference = line.split("uses:", 1)[1].strip()
                issues.append(
                    "official action is not pinned to a full reviewed commit: "
                    f"{reference}"
                )
                continue
            action, revision, comment = match.groups()
            action_counts[action] += 1
            if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
                issues.append(
                    "official action is not pinned to a full reviewed commit: "
                    f"{action}@{revision}"
                )
                continue
            expected = REVIEWED_ACTIONS.get(action)
            if expected is None:
                issues.append(f"official action is not approved: {action}")
                continue
            expected_revision, expected_comment = expected
            if revision != expected_revision or comment != expected_comment:
                rendered_comment = f" # {comment}" if comment else ""
                issues.append(
                    "official action pin does not match reviewed release: "
                    f"{action}@{revision}{rendered_comment}"
                )
    for action, expected_count in EXPECTED_ACTION_COUNTS.items():
        actual_count = action_counts[action]
        if actual_count != expected_count:
            issues.append(
                "reviewed action usage count mismatch: "
                f"{action} expected {expected_count} got {actual_count}"
            )
    return issues


def _validate_dependabot(root: Path) -> list[str]:
    path = root / ".github" / "dependabot.yml"
    if not path.is_file():
        return ["Dependabot configuration is missing"]

    text = path.read_text(encoding="utf-8-sig")
    ecosystems = re.findall(
        r'(?m)^\s*-?\s*package-ecosystem:\s*["\']?([^"\'\s]+)', text
    )
    issues: list[str] = []
    if ecosystems != ["github-actions"]:
        issues.append("Dependabot may update github-actions only")

    required_terms = {
        'directory: "/"': "Dependabot github-actions directory must be repository root",
        'interval: "weekly"': "Dependabot github-actions interval must be weekly",
        "open-pull-requests-limit: 3": "Dependabot open pull request limit must be 3",
        'prefix: "ci"': "Dependabot commit prefix must be ci",
    }
    for term, issue in required_terms.items():
        if term not in text:
            issues.append(issue)
    return issues


def _validate_dependency_contract(root: Path) -> list[str]:
    path = root / DEPENDENCY_CONTRACT_PATH
    if not path.is_file():
        return [f"missing dependency contract: {DEPENDENCY_CONTRACT_PATH}"]
    text = path.read_text(encoding="utf-8-sig")
    required_sections = (
        "RUNTIME DEPENDENCIES",
        "DEV/TEST DEPENDENCIES",
        "BUILD DEPENDENCIES",
        "SYSTEM DEPENDENCIES",
        "HOST/AGENT CAPABILITIES",
        "CI-ONLY DEPENDENCIES",
    )
    return [
        f"dependency contract is missing section: {section}"
        for section in required_sections
        if section not in text
    ]


def _stdlib_module_names() -> set[str]:
    names = getattr(sys, "stdlib_module_names", None)
    if names is not None:
        return set(names)
    return {
        "argparse",
        "ast",
        "collections",
        "concurrent",
        "contextlib",
        "dataclasses",
        "datetime",
        "hashlib",
        "importlib",
        "io",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "typing",
        "unittest",
        "urllib",
        "zipfile",
    }


def _validate_python_imports(root: Path) -> list[str]:
    issues: list[str] = []
    stdlib = _stdlib_module_names()
    local_modules = set(LOCAL_IMPORT_ROOTS)
    script_root = root / "scripts"
    if script_root.is_dir():
        local_modules.update(path.stem for path in script_root.glob("*.py"))
    for relative_root in PYTHON_CONTRACT_ROOTS:
        source_root = root / relative_root
        if not source_root.is_dir():
            continue
        for path in sorted(source_root.rglob("*.py")):
            relative_path = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8-sig"),
                    filename=relative_path,
                )
            except (OSError, UnicodeError, SyntaxError) as error:
                issues.append(f"Python source cannot be parsed: {relative_path}: {error}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level or node.module is None:
                        continue
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    top_level = module.split(".", 1)[0]
                    if (
                        top_level == "__future__"
                        or top_level in stdlib
                        or top_level in local_modules
                    ):
                        continue
                    issues.append(
                        f"undeclared Python import: {top_level} in {relative_path}"
                    )
    return issues


def _validate_hygiene(root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            issues.append(
                "repository hygiene forbids symbolic link: "
                f"{relative.as_posix()}"
            )
            continue
        if any(part in HYGIENE_DIRECTORY_NAMES for part in relative.parts):
            offending = next(
                part for part in relative.parts if part in HYGIENE_DIRECTORY_NAMES
            )
            issues.append(f"repository hygiene forbids generated/cache path: {offending}")
            continue
        if path.is_file() and (
            path.name in HYGIENE_FILE_NAMES or path.suffix.lower() in HYGIENE_SUFFIXES
        ):
            issues.append(
                "repository hygiene forbids generated/sensitive file: "
                f"{relative.as_posix()}"
            )
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        if PRIVATE_PATH_RE.search(text):
            issues.append(
                "repository hygiene found a private absolute path: "
                f"{relative.as_posix()}"
            )
        if SECRET_RE.search(text):
            issues.append(
                "repository hygiene found a secret-like value: "
                f"{relative.as_posix()}"
            )
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify repository health contracts")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the script's parent repository)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    issues = validate_repository(root)
    payload = {
        "status": "PASS" if not issues else "FAIL",
        "root": str(root),
        "issues": issues,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
