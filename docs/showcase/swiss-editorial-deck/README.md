# Swiss Editorial Deck

A 9-page typography-led editorial deck generated in a restrained Swiss system. It is intentionally image-free so the layout and reading rhythm remain inspectable.

## Outputs

- [PPTX](swiss-editorial-deck.pptx) — native text and shape companion with partial editability
- [HTML](swiss-editorial-deck.html) — the primary browsable artifact, fixed 16:9 and keyboard navigable
- [PDF](swiss-editorial-deck.pdf) — browser-rendered, print-ready preview
- [Prompt](prompt.md) · [Manifest](manifest.json) · [Preview](preview.png)

## Route and editability

`guizang → ppt-master → frontend-slides`. The HTML follows registered Swiss layout IDs (`S01`, `S03`, `S09`, `S04`, `S11`, `S15`, `S08`, `S18`, `S10`). The PPTX companion keeps text and geometry native but does not claim full template/master fidelity.

## Verification boundary

Static Swiss validation and browser rendering are run locally. PPTX package structure is inspected locally; desktop PowerPoint rendering is not available in this environment.
