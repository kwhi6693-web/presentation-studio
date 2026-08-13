---
name: guizang-presentation-engine
description: Use when a presentation needs Swiss or editorial web composition, Guizang presenter mode, rehearsal controls, annotation, WebGL, or low-power browser behavior.
---

# Guizang Presentation Engine

Use this copy as a specialized design/runtime engine. Preserve its AGPL-3.0 license and do not use it as the native editable PPTX renderer.

## Route

1. Choose `assets/template-swiss.html` for Swiss requests; choose `assets/template.html` for editorial/e-ink requests.
2. Load only the active design authority:
   - Swiss: `references/layouts-swiss.md`, `references/themes-swiss.md`, and `references/swiss-layout-lock.md`.
   - Editorial: `references/layouts.md`, `references/themes.md`, and `references/components.md`.
3. Load `references/image-prompts.md` only when the deck needs generated imagery.
4. Load `references/presenter-mode.md` only when presenter/rehearsal/timer/pointer/annotation behavior is requested.
5. Read `references/upstream-skill.md` only when the concise route above does not cover an upstream-specific workflow detail.

## Construction contract

- Keep every slide on a 16:9 stage and assign a registered semantic layout.
- Bind local imagery to an explicit `data-image-slot` and generate to that slot ratio.
- Preserve the presenter CSS/JavaScript boundary markers in both templates.
- Keep speaker-note IDs aligned with slide IDs.
- Do not flatten Guizang design rules into a generic card grid.
- When native editable PPTX is also required, contribute design and presenter semantics while another engine performs native rendering.

## Validation

Run the relevant commands from this engine directory:

```text
node scripts/check-presenter-runtime-sync.mjs
node scripts/validate-presenter-mode.mjs <deck.html>
node scripts/validate-swiss-deck.mjs <deck.html>
```

Treat skipped Playwright measurements as `PARTIAL`, not `PASS`. Validate a generated deck or a registered fixture; the upstream blank Swiss template is not itself a passing locked-layout deck.

## Recovery

- Missing Playwright: keep static validation, report rendered inspection as partial, and use the configured browser runtime when available.
- Overflow/collision: repair the owning layout and revalidate; do not delete content reflexively.
- Image failure: use another provider or a deliberate typographic/no-image layout.
- Presenter drift: repair the optimized copy, then rerun the byte-sync check.
