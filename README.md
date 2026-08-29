# 🎬 Presentation Studio

> Agent-compatible presentation and visual production Skill for editable PPTX, HTML slides, PDF, visual assets, exact-data routing, and rendered QA.

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-capability--based-2f855a?style=flat-square)](#compatibility-model)
[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg?branch=main&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg?branch=main&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a?style=flat-square)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5?style=flat-square)](presentation-studio/catalog/styles.json)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg?style=flat-square)](LICENSE)

## 🧭 Overview

Presentation Studio turns a natural-language brief, exact data, and existing assets into an explainable product and engine route. The Skill contract is designed to stay host-independent where the implementation permits it: the Agent/Harness supplies runtime capabilities, while Presentation Studio supplies catalog-backed routing, data contracts, native-generation boundaries, provenance, and rendered quality gates.

| At a glance | Current contract |
|---|---|
| Product catalog | 13 product recipes and 8 style profiles |
| Integrated engines | 4 upstream engines with allowlisted synchronization |
| Output families | PPTX, HTML, PDF, PNG, and SVG |
| Quality model | Validate → render → inspect → repair → validate again |
| Compatibility model | Capability-based; designed and validated states are reported separately |

## 💡 What problem does this solve?

Presentation work often loses data fidelity, editability, visual consistency, or evidence between a brief and a finished file. A single prompt also cannot know whether the host has Python, Node, Chromium, Office rendering, or an image provider.

Presentation Studio makes those decisions explicit:

- normalize the brief and preflight the host;
- retrieve a product and style from a local catalog;
- route to one engine or a hybrid chain;
- generate native or publication-ready outputs; and
- report route results, artifacts, evidence, and capability limits.

## ✨ Core capabilities

| Capability layer | Coverage | Result |
|---|---|---|
| Intent and product decisions | Brief normalization, preflight, 13-product retrieval, style inference, conflict detection | Explainable product/style choice |
| Data contracts and routing | Exact-data manifests, type/order/unit protection, engine and hybrid routing | Auditable engine plan |
| Content and visual production | Narrative, layouts, charts, covers, illustrations, infographics, diagrams | Content and asset plan |
| Native multi-format generation | Editable PPTX, standalone HTML, PDF, PNG, SVG, presenter navigation | Native or publication-ready files |
| Rendered acceptance and repair | Overflow, collision, fonts, contrast, page count, interaction, print, offline behavior | Quality-gated output |
| Safety, provenance, and status | Untrusted-content boundaries, credential protection, license/source records, route status | Reproducible evidence |
| Upstream synchronization | Stable-release discovery, allowlisted imports, license checks, validated sync PRs | Maintainable integration |

The complete L0-L19 responsibility map is in the [architecture guide](docs/architecture.md).

## 🧩 Products, outputs, and engines

The source of truth for the product catalog is [products.json](presentation-studio/catalog/products.json). The public index contains 13 product recipes:

| Product | Typical use | Outputs | Engine chain |
|---|---|---|---|
| native-editable-deck | General presentations and business updates | PPTX | ppt-master |
| native-data-deck | Financial reports and metric reviews | PPTX | ppt-master |
| swiss-editorial-deck | Swiss/editorial strategy or annual narratives | PPTX, HTML | guizang → ppt-master → frontend-slides |
| executive-deck | Board, investor, and decision briefs | PPTX | ppt-master |
| technical-deck | Architecture and engineering reviews | PPTX | ppt-master |
| html-presenter | Single-file web presentation and presenter mode | HTML, PDF | guizang → frontend-slides |
| dual-format-deck | Shared content for meetings and the web | PPTX, HTML, PDF | ppt-master → frontend-slides |
| cover-image | Article, presentation, and social covers | PNG | baoyu |
| article-illustration | Editorial illustrations and concept visuals | PNG | baoyu |
| infographic-image | Data summaries and comparison infographics | PNG | baoyu |
| technical-diagram | Architecture, system, and process diagrams | SVG | baoyu |
| data-image | Metric visuals and chart images | PNG | baoyu |
| image-slide-deck | Image-led narrative presentations | PPTX with image pages | baoyu → ppt-master |

| Engine | Best fit | Boundary |
|---|---|---|
| [PPT Master](https://github.com/hugohe3/ppt-master) | Native PPTX, charts, tables, notes, animation, templates | Owns native PowerPoint objects; Office rendering is a separate capability check |
| [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) | Swiss/editorial design systems, narrative, presentation layouts | Supplies design authority; the selected renderer creates the final file |
| [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) | Standalone HTML, keyboard navigation, presenter behavior, HTML-to-PDF | Browser/PDF QA requires resolved Chromium/Playwright capability |
| [Baoyu Skills](https://github.com/JimLiu/baoyu-skills) | Covers, illustrations, infographics, diagrams, data images, image slides | Provider-backed imagery is optional; an SVG diagram is not a native PowerPoint object |

## 🔍 Compatibility model

### Designed versus validated

The **Compatibility matrix** below is the source of truth for the current host evidence.

The Skill contract and core logic are designed for compatible Agents/Harnesses that can provide the required local capabilities. “Designed” describes architecture and contract intent. “Validated” is reserved for a host/route actually exercised by current verification evidence.

| Host / Agent capability | Skill contract | Core routing | Local scripts | Native generation | Render QA | Validation status |
|---|---|---|---|---|---|---|
| Codex | Supported | Supported | Supported | Capability-dependent | Runtime-dependent | Validated for checked-in local core/package contracts; optional renderer/provider routes remain separately reported |
| Other capable Agents / Harnesses | Designed | Designed | Requires local runtime | Host-dependent | Runtime-dependent | Designed for capability-compatible hosts; not independently validated in this repository run |

This is not a universal-support claim. A host is evaluated by route and capability. For example, a host with Python and the native PPTX core but no Chromium or image provider can report:

| Route | Result | Meaning |
|---|---|---|
| Native PPTX production | PASS when its required engine path runs | Missing browser capability does not invalidate native PPTX by itself |
| HTML rendered QA / HTML-to-PDF | PARTIAL or NOT EXECUTED | Chromium/Playwright is required for the affected checks |
| Provider-backed image generation | NOT AVAILABLE | No provider is configured; choose a non-provider route or report the limit |
| A required missing runtime or hard constraint | FAIL | The selected route cannot satisfy its required contract |

PASS, PARTIAL, and FAIL are route results. NOT AVAILABLE and NOT EXECUTED make capability gaps explicit; they are not evidence that the whole Skill is unsupported.

The checked-in `presentation-studio/agents/openai.yaml` is an optional OpenAI/Codex host descriptor, not a core Skill requirement. The vendored Baoyu source may contain an optional `baoyu-codex-imagegen` adapter; provider and Codex CLI use remain optional upstream capability paths.

## 🎯 Scope and guarantees

Use the smallest route that meets the requested output, then expand verification when the deliverable or acceptance criteria require it.

| Route | What it provides | What it does not imply |
|---|---|---|
| Fast native path | Product selection, payload preparation, local generation, and inspection of an editable PPTX route | It does not automatically prove browser, Office, provider, or rendered-PDF behavior |
| Complete path | Environment preflight, exact-data validation, rendered QA, package verification, and evidence reporting | It still reports any unavailable or unexecuted host capability |
| Image-led product | Image-led narrative or visual assets, including PNG/SVG outputs | An image-led deck must not be described as an object-editable deck |

Native/editable boundaries are explicit:

| Output family | Boundary |
|---|---|
| PPTX | Charts, tables, text, and shapes should use native PowerPoint objects when editability is requested; Office rendering is checked separately |
| HTML | Standalone files can provide keyboard navigation and presenter behavior; browser/PDF readiness depends on Chromium/Playwright |
| PDF | Publication output depends on the selected renderer and its page-size/rendering checks |
| PNG / SVG | Visual assets are native image/vector outputs; an SVG diagram is not a native PowerPoint object |

## 📐 Exact-data and editability

Exact-data work requires three comparable records:

| Record | Contract |
|---|---|
| Validated manifest | Declares the source values, types, units, order, duplicates, and missing values |
| Selected-engine payload | Carries the complete data contract into the routed engine |
| Post-render observed contract | Confirms what the rendered deliverable actually contains |

Compare all three before calling the data result PASS. Missing values, duplicates, length mismatches, or an incomplete observed contract cap the result at PARTIAL.

When native editability is requested, use native PowerPoint objects for charts, tables, text, and shapes. Do not replace an editable deck with full-slide screenshots. Image-led products remain image-led and should not be described as object-editable decks.

## 📋 Requirements

The host Agent/Harness provides capabilities; the Skill reports what each route can actually use.

| Capability | Used for | If unavailable |
|---|---|---|
| Visual understanding | Brief interpretation, source-aware composition, and visual inspection | The affected visual route may be PARTIAL or NOT EXECUTED |
| Local filesystem access | Reading inputs, running local scripts, and collecting artifacts | Local generation or verification cannot run |
| Python 3.10+ | Preflight, validation, packaging, and Python-based engine steps | The affected route fails its runtime requirement |
| Node.js | Node-based engines and HTML tooling | Node-dependent routes are unavailable |
| Git | Source checkout, provenance, and upstream synchronization | Source/update workflows are limited |
| Chromium / Playwright | Browser behavior, HTML rendering, and HTML-to-PDF QA | HTML/PDF QA is PARTIAL or NOT EXECUTED |
| Office renderer | Rendered PPTX inspection | Native PPTX can still be produced, but Office-render evidence is unavailable |
| Image provider | Provider-backed image generation | Provider route is NOT AVAILABLE; choose another route |

## 📦 Installation

Installation directories are host-specific. `.agents/skills/presentation-studio` is a common convention used by the included installers, not a universal Agent directory. Other Agents/Harnesses should place or import the Skill according to their own discovery contract.

### Release package

Download `presentation-studio.zip` and `presentation-studio.zip.sha256` from the same [latest release](https://github.com/kwhi6693-web/presentation-studio/releases/latest). Verify the ZIP before extraction:

```sh
sha256sum -c presentation-studio.zip.sha256
```

Windows PowerShell:

```powershell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch" }
"OK: $actual"
```

Extraction should produce one `presentation-studio/` Skill root. Run its self-check with explicit absolute Python and Node paths:

```sh
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
```

### Source checkout

Windows PowerShell:

```powershell
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1 -PythonExecutable C:\path\to\python.exe -NodeExecutable C:\path\to\node.exe
```

Linux or macOS:

```sh
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
PRESENTATION_STUDIO_PYTHON=/absolute/path/to/python PRESENTATION_STUDIO_NODE=/absolute/path/to/node PRESENTATION_STUDIO_GIT=/absolute/path/to/git ./scripts/install.sh
```

Both installers stage the package outside discovery, run a real self-check, and only then replace an existing installation. A forced update stores the previous copy under `.agents/skill-backups/` next to the chosen discovery directory. Reload the host Agent/Harness Skill registry after installation.

### Runtime resolution

The generic resolver accepts either:

- `PRESENTATION_STUDIO_RUNTIME_ROOT`, using `dependencies/python/python.exe`, `dependencies/node/bin/node.exe`, and `dependencies/native/git/cmd/git.exe`; or
- `PRESENTATION_STUDIO_PYTHON`, `PRESENTATION_STUDIO_NODE`, and `PRESENTATION_STUDIO_GIT` as explicit absolute files.

It rejects WindowsApps aliases and does not treat an accidental PATH hit as runtime evidence. When no generic configuration is supplied, the resolver can use the current Codex App bundle as an explicitly labeled compatibility fallback; that fallback is not a requirement for other hosts. See [dependencies.md](presentation-studio/references/dependencies.md).

## 🚀 Usage

Describe the desired result naturally. Include the topic, purpose, audience, source material or exact data, formats, editability, visual direction, page/aspect constraints, and QA requirements.

```text
Create a 16:9 AI product strategy presentation for our board.
Deliver a native editable PPTX, standalone HTML, and PDF.
Use the supplied quarterly metrics without changing values, units, row order, or missing values.
Keep PPTX charts and tables editable. Inspect every page for overflow, contrast, data fidelity,
notes, offline behavior, and browser/PDF readiness, then report PASS/PARTIAL/FAIL.
```

For diagnostic routing, run preflight before recommendation and routing:

```sh
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
python presentation-studio/scripts/recommend.py --json-file request.json
python presentation-studio/scripts/route.py --json-file route-request.json
```

`preflight.py` emits JSON by default and has no `--json` flag. Readiness booleans must come from the current redacted preflight result. The router preserves explicit product/style constraints and reports conflicts instead of silently replacing them.

## 🖼️ Input → output

```text
brief + source data + assets
        → normalize and preflight
        → retrieve a product/style from the local catalog
        → route to one engine or a hybrid chain
        → generate native/editable outputs
        → validate, render, inspect, repair, validate again
        → report artifacts, evidence, and capability limits
```

| Input | Decision layer | Output |
|---|---|---|
| Brief, audience, purpose, constraints | Product/style retrieval and conflict detection | Explainable route plan |
| Exact data and existing assets | Manifest, type/order/unit checks, provenance | Native or visual deliverables |
| Host capability report | Engine selection and rendered-QA gate | PASS / PARTIAL / FAIL with evidence |

## 🎞️ Real examples

The six checked-in artifacts below are real acceptance fixtures for the repository contract. They are structurally verified by `scripts/verify_examples.py`; a fixture pass is not a claim that every optional renderer or provider was freshly exercised on every host.

| Fixture set | Deliverables | Coverage |
|---|---|---|
| English acceptance | PPTX, HTML, PDF | Language identity, native chart/table/notes, HTML behavior, PDF page size |
| Chinese acceptance | PPTX, HTML, PDF | Language identity, native chart/table/notes, HTML behavior, PDF page size |

<details>
<summary>Acceptance artifacts</summary>

- [English PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx)
- [English HTML](examples/bilingual-acceptance/en/presentation-acceptance-en.html)
- [English PDF](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)
- [Chinese PPTX](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx)
- [Chinese HTML](examples/bilingual-acceptance/zh/presentation-acceptance-zh.html)
- [Chinese PDF](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf)

</details>

<details>
<summary>Fixture coverage</summary>

Each deck contains five pages with language, native chart/table/notes, HTML keyboard/print/offline, and PDF page-size checks where applicable. Run `python scripts/verify_examples.py` for the current structural contract.

</details>

## ⚙️ How it works

1. **Preflight** — resolve the host's actual Python, Node, Git, browser, Office, and provider capabilities.
2. **Catalog selection** — retrieve a product recipe and style profile from the local source of truth.
3. **Exact-data contract** — preserve values, types, units, order, duplicates, and missing values through the selected engine payload.
4. **Engine routing** — choose a native engine or a hybrid chain and report hard conflicts instead of silently substituting.
5. **Generation** — create editable PPTX objects or the selected HTML/PDF/PNG/SVG output family.
6. **Quality gate** — validate, render, inspect every applicable page, repair once when allowed, validate again, and report the evidence boundary.

The full orchestration and responsibility map is in [docs/architecture.md](docs/architecture.md). The upstream maintenance contract is in [docs/upstream-sync.md](docs/upstream-sync.md).

## ✅ Validation

The required quality loop is:

```text
validate → render → inspect every page → repair → validate again
```

Check narrative, overflow, collision, margins, hierarchy, font size, contrast, crops, chart integrity, editability, notes, keyboard behavior, print/offline behavior, page count, and provenance as applicable to the selected route.

| Status | Meaning |
|---|---|
| PASS | Every required command and applicable quality check ran successfully, and the deliverables passed again after repair. |
| PARTIAL | A usable result exists, but a requested or optional capability was unavailable or not executed; name the affected route and evidence gap. |
| FAIL | A hard constraint conflicts, a required runtime is missing, production fails, or a required quality gate remains open. |
| NOT AVAILABLE | The host does not supply a capability, such as an image provider. |
| NOT EXECUTED | An applicable check was not run; it is not a pass. |

## 🛠️ Development and verification

Run from a source checkout with a resolved absolute Python executable where required:

```sh
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python -m unittest discover -s tests -v
python scripts/verify_package.py
python scripts/upstream_sync.py check --json
git diff --check
```

`build_package.py` creates deterministic `dist/presentation-studio.zip`; run it only when intentionally rebuilding the source-checkout package. Upstream synchronization CI passes explicit `--archive` and `--checksum` paths under runner temporary storage, builds twice, verifies parity, and keeps generated outputs out of the normal source PR. The repository [checksums.sha256](checksums.sha256) names the tracked source-checkout artifact; a formal Release generates the colocated `presentation-studio.zip.sha256` beside its release ZIP as a different contract.

## ⚠️ Known limitations

- The host controls which engines, renderers, browsers, Office installations, and image providers are actually available.
- Missing Chromium, an Office renderer, or a provider-backed image service can leave HTML/PDF or provider routes at PARTIAL, NOT AVAILABLE, or NOT EXECUTED while a native PPTX route still passes.
- A host must not be called fully validated unless the relevant route was exercised and its evidence was retained.
- Exact-data results require a validated manifest, the complete selected-engine payload, and a post-render observed contract. Missing values, duplicates, length mismatches, or an incomplete observed contract cap the data result at PARTIAL.
- Native editability applies to native PowerPoint objects. Full-slide screenshots must not be presented as editable charts, tables, text, or shapes.
- The public fixtures verify repository structure and declared checks; they do not replace route-specific visual, browser, Office, provider, or cross-Agent verification.

See [qa.md](presentation-studio/references/qa.md) and [error-system.md](presentation-studio/references/error-system.md) for the detailed QA and failure model.

## 🛡️ Security and provenance

Do not put credentials, private source content, or unredacted local paths in issues, prompts, or logs. Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).

License and source records are part of the delivery contract. Vendored engines retain their original licenses and notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [CONTRIBUTORS.md](CONTRIBUTORS.md), [source-lock.json](presentation-studio/source-lock.json), and the engine license files.

`scripts/upstream_sync.py check --json` is read-only. The maintainer workflow discovers stable releases, validates allowlists and licenses, runs repository/package checks, and opens or updates a dedicated synchronization PR only after verification. See [docs/upstream-sync.md](docs/upstream-sync.md).

## 🤝 Contributing and releases

Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Release candidates should pass repository health, example, package, security, and applicable rendered-QA checks in a pull request. The protected `main` branch and its required checks are the integration boundary; a local build or an unmerged branch is not a public Release.

## 📄 License

Presentation Studio is licensed under [AGPL-3.0](LICENSE). Upstream engines retain their original licenses and notices.
