# Diagrams and Infographics

Use `engines/baoyu/skills/baoyu-diagram` for architecture, flowchart, sequence, structure, mind map, timeline, and state-machine SVGs. Use `baoyu-infographic` for a visual composition that intentionally combines data, text, and imagery.

Prefer structured output. In editable PPTX, use native shapes/connectors for simple diagrams and native charts for data. Use SVG for complex but scalable geometry; keep labels readable and unclipped.

Create connectors before nodes when authoring native diagrams so edges remain behind entities. Keep connector semantics and hierarchy consistent. Do not add a diagram when prose or a simple table communicates the relationship more clearly.

Validate viewBox, clipping, label size, contrast, edge crossings, and integration crop. A rendered PNG is a preview/fallback, not proof that the SVG or native object remains editable.
