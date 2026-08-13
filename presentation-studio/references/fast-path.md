# Fast Path

Use Fast Path when the brief is complete or the user requests a short turnaround and the selected product does not require a complete-workflow escalation.

## Contract

1. Resolve runtimes, preflight, recommend, and route exactly as the root Skill requires. Fast Path never bypasses those stages.
2. Load only references and engines returned by the route. Do not preload unrelated provider, presenter, template, or Office manuals.
3. Build one narrative/content manifest and one asset manifest. Reuse them across PPTX, HTML, PDF, and image outputs; keep each renderer native.
4. Generate only requested products. Reuse accepted assets and avoid optional variants unless they materially improve acceptance.
5. Run the smallest real gate that proves each claim: structure plus native rendering for PPTX, browser interaction and print for HTML/PDF, provider output inspection for generated images.
6. Repair findings, rerun every affected gate, then report `PASS`, `PARTIAL`, or `FAIL` using the normal completion contract.

## Escalate to the complete workflow

Leave Fast Path when any of these is true:

- exact data requires manifest, engine payload, observed contract, or field-level comparison;
- an existing template or slide image must be reconstructed into native editable objects;
- advanced animation, transition timing, narration, audio, video, or live capture is required;
- provider selection, reference-image identity, licensing, or source research is unresolved;
- the brief contains a material conflict or ambiguity;
- a selected engine's own workflow requires additional confirmation or stages.

Escalation preserves completed preflight and routing evidence. It does not restart or discard valid manifests.

## Status boundary

Fast Path is an execution-scope optimization, not a quality downgrade. A missing PowerPoint/LibreOffice render, Chromium interaction check, provider call, font check, animation review, narration check, or exact-data comparison remains `PARTIAL / NOT EXECUTED`; it can never be converted to `PASS` by choosing Fast Path.
