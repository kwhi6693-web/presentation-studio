# Capability Router

## Taxonomy

- INPUT: PDF, PPTX, DOCX, Markdown, URL, text, images.
- CONTENT: summarize, outline, narrative, slide planning, speaker notes.
- DESIGN: style discovery, Swiss, editorial, corporate, minimal, technical, custom.
- ASSET: image, diagram, infographic, chart, icon, cover.
- LAYOUT: grid, hierarchy, spacing, rhythm, crop and safe-zone planning.
- RENDER: native PPTX, HTML, slide images, SVG.
- EXPORT: PPTX, HTML, PDF, PNG, JPG, SVG.
- PRESENT: keyboard, presenter view, rehearsal, timer, annotation, low-power mode.
- VALIDATE: package integrity, overflow, collision, crop, ratio, accessibility, output parity.

## Deterministic rules

1. Explicit output format wins.
2. “PPT/PowerPoint” without a format defaults to editable PPTX.
3. Editability always adds PPT Master; HTML or PDF never replaces its PPTX branch.
4. Swiss/editorial adds Guizang design guidance; presenter mode adds Guizang runtime.
5. Web/single-file adds Frontend Slides.
6. Generated visual assets add only the matching Baoyu Skill.
7. Native diagrams/charts in editable PPTX use native PowerPoint objects when feasible; raster or SVG assets remain separate objects, not full-slide screenshots.

## Hybrid examples

- PDF → Swiss → AI images → editable PPTX: `guizang → baoyu-image-gen → ppt-master`.
- Markdown → diagrams → HTML → PDF: `baoyu-diagram → frontend-slides`.
- Existing PPTX → redesign → editable PPTX: `ppt-master`; add Guizang only for requested style.
- Article → infographic → presentation: `baoyu-infographic → requested renderer`.
- Technical SVG diagram → PPTX: `baoyu-diagram → ppt-master`.

## Context rule

Route first. Load only the selected reference IDs and engine entrypoints returned by `scripts/route.py`. Do not read PowerPoint OOXML material for image-only work or presenter/WebGL material for native-PPTX-only work.
