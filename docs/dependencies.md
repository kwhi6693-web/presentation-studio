# Environment and Dependency Contract

This document is the source of truth for the runtimes, tools, and host capabilities
used by repository verification. A missing optional capability must remain visible as
`PARTIAL` or `NOT EXECUTED`; it must not be disguised as a successful check.

## RUNTIME DEPENDENCIES

- Python 3.10, 3.11, 3.12, and 3.13 are supported for repository scripts and tests.
- Node.js 20.9.0 or newer is required for Node-based engines and HTML tooling.
- Git is required for source checkout, provenance, and upstream synchronization.

## DEV/TEST DEPENDENCIES

- Repository health, unit tests, example verification, packaging, and package
  verification use Python's standard library and `unittest`.
- The repository intentionally has no root Python dependency manifest. Vendored
  engine-specific dependencies remain inside their documented engine boundaries.
- Browser and rendered-output checks are optional capability checks and must report
  their actual availability.

## BUILD DEPENDENCIES

- `scripts/build_package.py` uses Python's standard library to create a deterministic
  ZIP and SHA-256 record.
- `scripts/verify_package.py` uses Python's standard library to validate structure,
  archive safety, extraction parity, checksum parity, and the optional fresh-package
  smoke check.

## SYSTEM DEPENDENCIES

- GitHub-hosted Ubuntu runners provide Bash, `jq`, and the GitHub CLI (`gh`) for the
  upstream synchronization workflow.
- Windows runners provide PowerShell for the cross-platform repository gate.
- Chromium/Playwright, Office rendering, and image-provider credentials are host
  capabilities used only by the routes that need them.

## HOST/AGENT CAPABILITIES

- The host Agent/Harness supplies filesystem access, runtime resolution, and any
  optional renderer, browser, or provider capability.
- `presentation-studio/scripts/preflight.py` reports resolved executable paths and
  optional module availability; it does not install missing providers.
- Capability absence is an explicit boundary of the affected route, not a reason to
  add undeclared root dependencies.

## CI-ONLY DEPENDENCIES

- The validation matrix uses GitHub-hosted Ubuntu and Windows runners, Python 3.10
  through 3.13, and Node.js 20.9.0.
- CI provisions a clean Python virtual environment with `python -m venv --without-pip`
  in the runner temporary directory; the repository gate requires no package install.
- Official GitHub Actions are pinned to reviewed full commit SHAs. Dependabot updates
  only those GitHub Actions; it does not manage vendored engine lockfiles.
