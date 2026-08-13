# Provenance and Licenses

`source-lock.json` is the source of truth for repository URL, commit, import date, license, dependencies, and selected modules. `engines/manifest.json` maps runtime engine names to those locked sources.

- PPT Master: MIT; keep its attribution guard, LICENSE, sponsor files, and official repository metadata intact.
- Guizang: AGPL-3.0; copied and modified files retain the license and corresponding source availability obligations.
- Frontend Slides: MIT; keep its LICENSE notice with the engine.
- Baoyu Skills: MIT; keep its LICENSE notice with the selected visual Skills/packages.

Never modify the four source clones. Perform updates by importing a new commit into a new optimized copy, rerunning before/after capability tests, then replacing the vendored engine only after regression checks pass.
