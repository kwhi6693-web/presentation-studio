# Financial / Data Report

A 9-page quarterly review that demonstrates exact structured-data binding, a native editable chart, and a native editable table. All values are public illustrative demo data, not a real company report.

## Outputs

- [PPTX](financial-data-report.pptx) — native editable chart, table, text, and shapes
- [HTML](financial-data-report.html) — offline, fixed 16:9 browser companion
- [PDF](financial-data-report.pdf) — browser-rendered, print-ready preview
- [CSV source](financial-data.csv) · [Exact-data manifest](exact-data-manifest.json) · [Binding manifest](binding-manifest.json) · [Engine payload](engine-payload.json) · [Observed contract](observed-contract.json) · [Prompt](prompt.md)
- [Preview](preview.png) — selected pages for repository display

## Route and data boundary

`ppt-master → native-data-deck` is the selected route. The manifest preserves field order, concrete values, units, and the labeled derived-margin transformation. The PPTX chart and table are native objects, not screenshots.

## Verification boundary

The canonical binding manifest, engine payload, and observed contract pass the repository's exact-data verifier. The PPTX package also contains native chart/table parts and the expected visible values. Visual previews are rendered from the companion HTML because no PowerPoint/LibreOffice desktop renderer is installed in this environment.
