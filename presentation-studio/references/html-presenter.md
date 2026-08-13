# HTML and Presenter Authority

Use `engines/frontend-slides/SKILL.md` for HTML stage, style discovery, single-file delivery, PPTX semantic extraction, keyboard behavior, and PDF export. Use `engines/guizang/SKILL.md` only when Swiss/editorial design or presenter runtime is active.

Keep a 16:9 stage, explicit active-slide visibility, first/last navigation boundaries, visible focus, reduced-motion behavior, and print CSS. Single-file output must not depend on unapproved runtime network requests.

PPTX→HTML is semantic extraction/redesign unless a separate fidelity check proves otherwise. Preserve content/order/images/notes, but do not claim native chart, master, animation, or transition fidelity.

For presenter mode, keep slide IDs and speaker-note IDs aligned; validate rehearsal timing, timer, auto-advance, pointer/annotation, audience sync, screen controls, and low-power mode. Run Guizang's presenter and runtime-sync validators.

Use the cross-platform `engines/frontend-slides/scripts/export-pdf.mjs`. It must resolve Playwright from an existing dependency root and must never install packages during export.
