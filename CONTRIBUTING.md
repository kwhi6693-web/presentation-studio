# Contributing to Presentation Studio

感谢你帮助改进 Presentation Studio。Contributions are welcome when they preserve deterministic packaging, upstream provenance, explicit capability degradation, and the three-language documentation contract.

## Development requirements

- Git with a configured GitHub noreply identity.
- Python 3.10 through 3.13 for repository tests and packaging.
- Node.js 20.9.0 or newer when changing or validating a Node-based engine path.
- The optional runtimes and modules reported by `presentation-studio/scripts/preflight.py` for the capability being exercised.

Do not install optional providers merely to hide a failed capability probe. Missing optional modules must remain isolated and visible.

## Branch and pull-request workflow

1. Start from the latest `main` in an isolated clone or worktree.
2. Create one focused feature or fix branch. An automated upstream branch must contain exactly one source update.
3. Write a failing behavioral test before changing executable behavior.
4. Commit with a narrow message and explicitly stage only intended paths.
5. Open a draft pull request and wait for the `verify` status check.
6. Resolve authoritative review threads before marking the pull request ready.
7. Merge through the protected `main` ruleset. Do not force push, rewrite published history, or bypass required checks.

Use commands such as:

```bash
git add -- exact/path/one exact/path/two
git diff --cached --check
git commit -m "type: focused change"
```

Do not use broad staging commands when the worktree contains unrelated changes.

## Required verification

Run the repository-health boundary, full tests, checked-in examples, deterministic build, and package parity checks:

```bash
python scripts/verify_repository_health.py
python -m unittest discover -s tests -v
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
```

The runtime, dependency, system-tool, and CI matrix contract is maintained in
[docs/dependencies.md](docs/dependencies.md). The pull-request gate exercises
Python 3.10 through 3.13 on Ubuntu and Windows in a fresh environment.

When package inputs change, run `scripts/build_package.py` twice and record both SHA-256 values. They must be identical. The upstream synchronization workflow writes both validation packages to runner temporary storage and never stages `dist/presentation-studio.zip` or `checksums.sha256` in a normal source PR. Those tracked files remain the source-checkout baseline; formal release automation creates the colocated release ZIP and checksum assets.

## Vendored upstream boundaries

The following paths are governed by `presentation-studio/source-lock.json`, stable-release discovery, import allowlists, license verification, and adapter preservation. Automated updates stage only the mapped source roots and the required provenance metadata; do not use a broad `git add presentation-studio/engines`:

- `presentation-studio/engines/`
- `presentation-studio/source-lock.json`
- Vendored engine license files
- Integration adapters preserved by `scripts/upstream_sync.py`

Change them through the upstream synchronization workflow whenever possible. A manual exception must include an immutable upstream source, release/tag evidence, affected import paths, license impact, adapter impact, and the complete verification report. Do not let a general dependency bot silently become a second source of truth for vendored locks.

## Documentation and security

- Keep the English, Simplified Chinese, and Traditional Chinese entry points aligned where the README contract promises shared guidance.
- Preserve the seven capability layers and both expandable example showcases.
- Never commit credentials, tokens, passwords, private documents, machine-specific absolute paths, Python caches, or local planning artifacts.
- Follow [SECURITY.md](SECURITY.md) for vulnerabilities. Do not disclose an unpatched vulnerability in a public issue or pull request.

## Licensing and attribution

Contributions to the integration are accepted under [AGPL-3.0](LICENSE). Vendored components retain their upstream licenses and notices. Update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), source-lock provenance, and license copies whenever an approved upstream change requires it.
