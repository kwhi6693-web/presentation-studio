# Repository Acceptance Evidence — 2026-08-13

## Scope

This acceptance run covers the lightweight Fast Path, the complete L0–L19 architecture, six bilingual example products, stable upstream synchronization, deterministic packaging, provenance, and repository safety checks.

## Live upstream result

| Source | Locked result | Latest stable release | Decision |
|---|---|---|---|
| PPT Master | `bc421012d054fde6e8d0581a192cf75c0f9eb9a0` | `v4.6.0` / same commit | Updated from `ef0d585d5dc693d65be0b2aee5e8723b6264c367` |
| Guizang PPT Skill | `c91369c449d34755d320a8b81d0734000d99d1ab` | `v1.1.0` / `3652b3c7aa21492717945b6063ae278030101dd8` | `ahead_of_release`; no downgrade |
| Frontend Slides | `9906a34d640d2111f724544cbc50f7f130569ae1` | `v2.1.0` / `24e420e4acef9850505142c449415ac867e43633` | `ahead_of_release`; no downgrade |
| Baoyu Skills | `6b7a2e417500561a5ecdd0b168332f4142584617` | `v2.5.2` / `f490f7e5e347a356cbce30fee193766b7de792cf` | `ahead_of_release`; no downgrade |

The applied PPT Master transaction produced old tree hash `1bbba8ab8903e9664de1d0440a0e575b528cff6b63eb05f4960136e5cd8396b4` and new tree hash `a8b7848807e26a1d6cc4bcf805a763045d6e00a1727306e444782243c7f15646`.

The first Windows run exposed a long-path extraction failure. The release archive itself was complete: 14,516 members, 14,226 files, 720,342,215 uncompressed bytes, and a successful ZIP CRC test. A regression test now verifies staging from a long repository path, and synchronization uses a short system staging root before the same-volume atomic replacement.

A second live `sync --all` run returned `PASS`; a third run left both `source-lock.json` and `engines/manifest.json` byte-identical, proving no-op idempotency.

## Repository gates

- 26 unit and repository-contract tests: `PASS`.
- 240 Python source files compiled in-memory without syntax errors or cache output: `PASS`.
- Skill structure: 13 products, 8 styles, 4 engines, and complete Fast Path escalation terms: `PASS`.
- Package parity: every on-disk skill file is present exactly once under the single `presentation-studio/` ZIP root: `PASS`.
- Deterministic package: 65,014,711 bytes; two consecutive builds produced SHA-256 `aa50dfb5fae086f011bcfd18563e404dbb66fbf964ae52e414fdd40189933410`.
- Six bilingual example contracts: `PASS`.
- Secret-pattern scan for private keys, GitHub tokens, OpenAI-style keys, and AWS access keys: no matches.
- Largest vendored file: approximately 3.6 MB; no GitHub 100 MB file-limit violation.
- Upstream archive safety: traversal, absolute paths, backslashes, `.git` members, multiple roots, and symbolic links are rejected.
- License checks: PPT Master, Frontend Slides, and Baoyu are verified as MIT; Guizang is verified as AGPL-3.0.

Upstream v4.6.0 contains existing trailing whitespace in a small set of vendored source/SVG files. These files are intentionally kept byte-faithful to the official release. Presentation Studio-owned metadata is normalized to LF and covered by a regression test.

## Bilingual example hashes

| Product | SHA-256 |
|---|---|
| English HTML | `552ca34a6b51fc0ff09acbe95583f3705869c6827840c64a94c5b483ed444370` |
| English PDF | `0b130efb81f5126e96fb2a018020ef4bd158061bf1fb62f2ede67ba8437d7dad` |
| English PPTX | `4b91a9e05795988f11177ee26fa9eb29504d39c53e88cde5bafd6e6550c2b955` |
| Chinese HTML | `4c24b633b97b1d82f621d015ddb4d2f5e32d519874b61aef5501480963c4a721` |
| Chinese PDF | `a9d7d66a4997fff9c4ed2d2ed1dbe65b9cabce4e223fa37c963ce5a99bfcfb30` |
| Chinese PPTX | `dbe211050c27e49c80461de221e9c65ff0055c619a5847b2833b199d18215f12` |

Each PPTX has 5 slides, 5 notes pages, a native chart, a native table, and a native fade animation. Each standalone HTML file has 5 slides, keyboard navigation, editable text, print CSS, and offline assets. Each PDF has 5 pages with a 960 × 540 point media box.

## Status

Repository-level structural, synchronization, provenance, package, and example-product acceptance status: `PASS`.
