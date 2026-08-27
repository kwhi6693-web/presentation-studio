# Presentation Studio Architecture

Presentation Studio exposes seven major capabilities in the README while preserving the complete L0–L19 workflow below. The Fast Path only skips work that is already resolved by a complete brief; it never removes a layer or weakens a quality gate.

## Major capability map

| Major capability | Detailed layers |
|---|---|
| Intent understanding and product decisions / 智能理解与产品决策 | L0–L7 |
| Data contracts and engine orchestration / 数据契约与引擎编排 | L8–L10 |
| Content and visual production / 内容与视觉生产 | L11–L13 |
| Native multi-format generation / 多格式原生生成 | L14–L15 |
| Rendered acceptance and repair / 渲染验收与自动修复 | L16–L18 |
| Safety, provenance, and status / 安全、溯源与状态 | L19 and cross-cutting controls |
| Continuous upstream synchronization / 上游持续同步 | Source lock, release discovery, staged imports, repository gates |

## Complete L0–L19 capability model

| Layer | Responsibility | Output or gate |
|---:|---|---|
| L0 | Skill invocation and intent recognition | Create, convert, redesign, edit, present, export, or validate intent |
| L1 | Input intake | Text, images, tables, CSV, XLSX, JSON, Markdown, existing PPTX/HTML/PDF |
| L2 | Request normalization | Output, editability, audience, goal, subject, tone, density, channel, aspect ratio, asset needs |
| L3 | Runtime resolution | Verified absolute paths for Python, Node.js, Git, renderers, and browsers supplied by the host |
| L4 | Environment preflight | Availability and readiness of runtimes, Office/LibreOffice, Chromium, fonts, and image providers |
| L5 | Product retrieval | Hard filters, multi-dimensional ranking, and readiness checks across 13 products |
| L6 | Style inference | Evidence-based choice across 8 style profiles when the user has not specified one |
| L7 | Constraint and conflict detection | Compatibility among output, editability, data form, ratio, product, style, capability, and prerequisites |
| L8 | Exact-data contract | Immutable source, field, type, order, unit, period, label, provenance, and permitted-transform manifest |
| L9 | Route orchestration | Product-to-engine chain, capability set, references, gates, and fallback product |
| L10 | Engine adaptation | Isolated responsibilities for PPT Master, Guizang, Frontend Slides, and Baoyu components |
| L11 | Narrative structure | Goal, audience, thesis, evidence, section rhythm, slide responsibility, and speaker notes |
| L12 | Visual and layout system | Typography, grid, whitespace, color, chart grammar, illustration strategy, and layout diversity |
| L13 | Asset generation and discovery | Covers, illustrations, infographics, charts, diagrams, icons, and licensed external assets |
| L14 | Product generation and export | Native PPTX, HTML, PDF, PNG, SVG; separate temporary and final-output boundaries |
| L15 | Presenter runtime | Keyboard navigation, focus, reduced motion, first/last boundaries, print CSS, and offline behavior |
| L16 | Post-render data observation | Extracted observations compared field-by-field, value-by-value, and label-by-label with the data contract |
| L17 | Quality assurance | Overflow, collision, clipping, margins, contrast, font size, charts, editability, page count, provenance, output consistency |
| L18 | Repair and fallback | Failure classification, explicit fallback, rerender, recheck, and prohibition on presenting failed intermediates as final |
| L19 | Safety, provenance, and status | Untrusted-code isolation, credential protection, scoped writes, source/license traceability, and `PASS / PARTIAL / FAIL` |

## Host compatibility boundary

Presentation Studio's core contract is Agent-compatible: catalogs, normalization, data
binding, routing, provenance, validation, and package checks do not require a particular
Agent API or discovery directory. The host supplies executable runtimes and optional
capabilities such as Python, Node.js, Chromium, Office rendering, fonts, and image
providers. The checked-in runtime resolver accepts generic configured roots or explicit
absolute executable paths and reports an optional Codex App bundle fallback with a source
label when that adapter is used.

`presentation-studio/agents/openai.yaml` is a host descriptor for OpenAI/Codex discovery,
not a core dependency. Upstream optional adapters are scoped to their corresponding
engine capability. Compatibility therefore follows the selected product route and the
available capabilities; a missing optional browser or provider produces a route-level
`PARTIAL`, `NOT AVAILABLE`, or `NOT EXECUTED` result rather than a whole-Skill verdict.

## Execution paths

### Fast Path

Use the Fast Path when the brief is complete, a single product route is obvious, no unresolved exact-data issue exists, and required runtimes are available. It performs normalization once, a bounded preflight, direct generation, route-specific validation, and delivery.

### Complete Path

Use the complete path when the request contains exact data, animation, narration, multiple engines, conflicting constraints, an incomplete brief, high-risk external assets, or a requested acceptance status that depends on real rendering.

Both paths enforce the same delivery truth: missing runtimes or unexecuted tests cannot be reported as `PASS`.

## Engine boundary

| Engine | Primary responsibility | Integration rule |
|---|---|---|
| PPT Master | Native editable PPTX and structured charts/tables | Imported as an upstream engine; license and provenance retained |
| Guizang | Editorial/Swiss design language and layout tooling | Upstream assets/scripts are vendored; Presentation Studio adapter remains authoritative |
| Frontend Slides | Standalone HTML runtime and browser-based layouts | Upstream files are allowlisted; safe export adapter remains authoritative |
| Baoyu | Covers, illustrations, infographics, diagrams, and image decks | Selected skills/packages are vendored behind a routing wrapper |

The engine adapters are preserved during upstream updates. Upstream content cannot overwrite the root routing contracts unless the import policy explicitly allows it.

## Quality and status semantics

- `PASS`: every required structural and runtime-dependent gate was actually executed and passed.
- `PARTIAL`: a usable product exists, but one or more required runtime-dependent checks could not be executed.
- `FAIL`: a required gate failed or the safe product cannot be produced.
- `NOT AVAILABLE` / `NOT EXECUTED`: capability-level results for an absent or unrun optional path; they are not compatibility claims about the complete Skill.

Structural checks do not impersonate visual rendering. PowerPoint/LibreOffice, Chromium/Playwright, image providers, fonts, and primary runtimes are reported separately so the result remains auditable.

## Related contracts

- [Fast Path](../presentation-studio/references/fast-path.md)
- [Product retrieval](../presentation-studio/references/product-retrieval.md)
- [Exact-data binding](../presentation-studio/references/data-binding.md)
- [Upstream synchronization](upstream-sync.md)
- [Source lock](../presentation-studio/source-lock.json)
