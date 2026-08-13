---
name: frontend-slides-engine
description: Use when a presentation needs single-file HTML delivery, browser-native slides, visual style discovery, responsive 16:9 staging, keyboard navigation, PPTX content extraction, or HTML-to-PDF export.
---

# Frontend Slides Engine

Use this copy as the HTML renderer and visual-discovery engine. It does not preserve native editable PowerPoint objects.

## Route

- New HTML deck: load `html-template.md`, `viewport-base.css`, and `animation-patterns.md`.
- Style discovery: load `STYLE_PRESETS.md` and `bold-template-pack/selection-index.json`, then only the shortlisted template recipes.
- PPTX intake: run `scripts/extract-pptx.py`; label the result semantic extraction/redesign rather than fidelity conversion.
- PDF export: run `scripts/export-pdf.mjs`; use the legacy `.sh` exporter only on a compatible Unix shell.
- Load `references/upstream-skill.md` only for a detail not covered here.

## Output contract

- Keep one fixed 16:9 stage and use visibility/opacity/pointer-events for slide switching.
- Produce one HTML file when single-file delivery is requested; inline local CSS, JavaScript, fonts, and images, and reject unexpected runtime network dependencies.
- Provide keyboard navigation, visible focus, reduced-motion behavior, and print styles.
- Preserve source order, text, images, and notes during PPTX semantic redesign; do not claim chart/master/animation fidelity.

## QA

Open the deck in the configured browser, test first/last slide boundaries and every navigation key, inspect console errors, render all slides, and export a PDF whose page count matches the deck. Treat accessibility and offline delivery as partial until they are tested.

## Recovery

- Missing Playwright/browser: deliver verified HTML and mark PDF/render checks partial.
- Broken external font: use a bundled or system fallback and recheck wrapping.
- Oversized content: shorten copy or select a higher-capacity layout before reducing type below the quality floor.
