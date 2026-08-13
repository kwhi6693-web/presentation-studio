# Presentation QA

## Pipeline

Run `validate → render → inspect → repair → validate again`.

## Required checks

- Narrative: opening, problem, point of view, evidence, progression, conclusion.
- Layout: overflow, collision, safe margins, alignment, hierarchy, grid, spacing, title/footer zones, minimum type, density, whitespace, rhythm.
- Images: slot ratio, focal point, crop, resolution, distortion, consistency, provenance.
- Charts/data: chart choice, labels, scale, axis, contrast, legend, data integrity, editability.
- PPTX: OPC integrity, native object editability, masters/layouts, notes, transitions/animations, template preservation.
- HTML: keyboard boundaries, focus, console, reduced motion, low-power mode, offline/single-file behavior, print/PDF page count.
- Outputs: names, formats, links, page/slide parity, no unresolved placeholders.

Use `scripts/validate_manifest.py` for deterministic geometry/ratio checks, plus selected engine validators. Render every final page and inspect individually at full size; use a montage only for deck-level rhythm.

Record each check as PASS, PARTIAL, or FAIL with its command and prerequisite. After any repair, rerun the responsible validator and the final suite.
