# Technical Architecture

A 9-page technical presentation explaining agent-based presentation generation: one task context, capability routing, native output, quality gates, security boundaries, and checkpointed recovery. It contains four diagram-led pages built from native shapes and connectors in the PPTX companion.

## Outputs

- [PPTX](technical-architecture.pptx) — native editable text, shapes, connectors, and diagrams
- [HTML](technical-architecture.html) — offline, fixed 16:9 browser companion
- [PDF](technical-architecture.pdf) — browser-rendered, print-ready preview
- [Prompt](prompt.md) · [Architecture source](architecture.json) · [Manifest](manifest.json)
- [Preview](preview.png) — selected pages for repository display

## Route and editability

`ppt-master → technical-deck`. The diagrams are not flattened screenshots; native PPTX shapes remain editable. The HTML companion is a visual/browsable representation and does not claim native PowerPoint object fidelity.

## Verification boundary

Native package structure, slide count, and diagram object presence are inspected locally. Browser renders are used for visual inspection; desktop PowerPoint rendering is not available in this environment.
