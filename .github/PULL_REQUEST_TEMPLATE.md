## Summary

Describe the user-visible outcome and the smallest scope that achieves it.

## Verification checklist

- [ ] The change is focused and unrelated work is excluded.
- [ ] New executable behavior or bug fixes followed a witnessed RED → GREEN test cycle.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python scripts/verify_repository_health.py` passes.
- [ ] `python scripts/verify_examples.py` passes for all six bilingual products.
- [ ] `python scripts/verify_package.py` passes.
- [ ] If package inputs changed, two deterministic builds produced the same SHA-256.
- [ ] Documentation and examples reflect the final behavior.
- [ ] No credentials, private data, local absolute paths, caches, or internal planning artifacts are included.
- [ ] Vendored engine/source-lock changes include immutable upstream, license, import-path, and adapter evidence.
- [ ] Release impact is explicit: no Release required, or the required tag/assets/notes are described.

## Evidence

Provide RED/GREEN output, test counts, build hashes, package verification, screenshots or rendered evidence when relevant, and links to upstream sources or GitHub Actions runs.

## Security and compatibility

Describe trust-boundary changes, runtime requirements, capability degradation, data compatibility, and any unresolved risk. Use private vulnerability reporting instead of this pull request for undisclosed vulnerabilities.
