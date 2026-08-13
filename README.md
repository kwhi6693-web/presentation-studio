# Presentation Studio

> 轻量、快速、可验证的 PPT 与视觉产品工作流。在短时间内交付高质量结果，同时保留完整的 20 层能力架构。
>
> A lightweight, fast, and verifiable workflow for high-quality presentations and visual products, backed by the complete 20-layer capability architecture.

[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5)](presentation-studio/catalog/styles.json)

[中文说明](#中文说明) · [English Guide](#english-guide) · [示例产品](#双语示例产品) · [安装](#安装与验证) · [完整架构](docs/architecture.md) · [上游同步](docs/upstream-sync.md)

## 中文说明

Presentation Studio 将四个上游作者项目的优势统一为一个产品层：

- [PPT Master](https://github.com/hugohe3/ppt-master)：原生可编辑 PPTX、结构化文本、图表和表格。
- [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill)：Swiss / editorial 视觉体系、演示叙事与高质量排版。
- [Frontend Slides](https://github.com/zarazhangrui/frontend-slides)：独立 HTML 演示、浏览器交互与 PDF 路径。
- [Baoyu Skills](https://github.com/JimLiu/baoyu-skills)：封面、插图、信息图、技术图和图像型幻灯片。

它不是简单复制四个项目，也不是只做一种 PPT。统一的输入契约会先理解目标，再进行智能检索、精准数据保护、引擎编排、原生生成、实际验收与明确降级。

### 两种执行路径

- **Fast Path**：需求完整且产品路由明确时，跳过重复分析，直接执行“预检 → 生成 → 针对性验收 → 交付”，适合短时间产出。
- **Complete Path**：数据精确、格式冲突、动画/演讲者运行时、多引擎或高风险交付时，自动升级到完整流程。

轻量化减少的是重复决策与无效上下文，不会删减任何功能层。详细升级条件见 [Fast Path 说明](presentation-studio/references/fast-path.md)。

### 主要大功能层

| 主要能力 | 覆盖内容 | 代表输出 |
|---|---|---|
| **智能理解与产品决策** | 意图识别、输入标准化、环境预检、13 种产品智能检索、8 种风格推断、冲突检测 | 可解释的产品与风格选择 |
| **数据契约与引擎编排** | 精准数据清单、类型/顺序/单位保护、PPT Master / Guizang / Frontend Slides / Baoyu 路由 | 不可变数据契约与引擎链 |
| **内容与视觉生产** | 叙事结构、版式系统、图表、封面、插图、信息图、技术图和图像幻灯片 | 结构化内容与视觉资产 |
| **多格式原生生成** | 原生可编辑 PPTX、独立 HTML、PDF、PNG、SVG；演示者导航与打印样式 | 可编辑或可直接发布的产品 |
| **渲染验收与自动修复** | 数据保真、溢出/裁切/碰撞、字体、页数、交互、动画、离线行为、修复回路 | 经过质量门禁的交付物 |
| **安全、溯源与状态** | 不可信代码隔离、凭据保护、来源与许可证追踪、`PASS / PARTIAL / FAIL` 状态语义 | 可审计的生产与验收记录 |
| **上游持续同步** | 最新稳定版发现、只导入允许路径、许可证校验、适配器保留、全量验收后提交 | 保持能力更新且防止架构回退 |

以上 7 个主要层映射到底层 L0–L19 的全部能力；完整职责、输入、输出和门禁见 [完整架构](docs/architecture.md)。

### 双语示例产品

每个版本均包含 5 页内容，提供 PPTX、HTML、PDF 三种产品。PPTX 验证了演讲者备注、原生图表、原生表格与淡入动画；HTML 验证了键盘导航、可编辑文本、打印样式和离线资源；PDF 验证了页数与 16:9 页面尺寸。

<details>
<summary><strong>展开查看中文示例（PPTX / HTML / PDF）</strong></summary>

- [原生可编辑 PPTX](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx)
- [独立 HTML 演示](examples/bilingual-acceptance/zh/presentation-acceptance-zh.html)
- [PDF 交付版](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf)

</details>

<details>
<summary><strong>Expand the English examples (PPTX / HTML / PDF)</strong></summary>

- [Native editable PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx)
- [Standalone HTML presentation](examples/bilingual-acceptance/en/presentation-acceptance-en.html)
- [PDF deliverable](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)

</details>

## 安装与验证

从源码安装到当前用户的 Codex Skills 目录：

```powershell
.\scripts\install.ps1
```

```bash
./scripts/install.sh
```

也可以下载 [确定性构建包](dist/presentation-studio.zip)，并使用 [checksums.sha256](checksums.sha256) 核对 SHA-256。

仓库验收：

```bash
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
python -m unittest discover -s tests -v
```

上游状态检查不会修改文件：

```bash
python scripts/upstream_sync.py check --json
```

安全同步四个上游的最新稳定版本：

```bash
python scripts/upstream_sync.py sync --all --report artifacts/upstream-sync-report.json
```

自动同步支持上游事件触发、手动触发和 5 分钟轮询回退。只有来源、稳定版本、路径和许可证均通过校验，并且仓库全部门禁通过时才会提交。操作说明见 [上游持续同步](docs/upstream-sync.md)。

本次真实同步、示例哈希与仓库门禁记录见 [2026-08-13 验收证据](docs/evidence/acceptance-2026-08-13.md)。

## English Guide

Presentation Studio combines four upstream specialties behind one product-oriented workflow. A complete brief can take the Fast Path for rapid delivery; exact data, format conflicts, animation, narration, multi-engine composition, or high-risk output automatically escalates to the complete workflow.

### Major capability layers

| Major capability | Coverage | Representative output |
|---|---|---|
| **Intent understanding and product decisions** | Intent parsing, normalized briefs, preflight, Intelligent retrieval across 13 products, style inference across 8 profiles, conflict detection | Explainable product and style choice |
| **Data contracts and engine orchestration** | Exact-data manifests, type/order/unit preservation, routing across all four engines | Immutable data contract and engine chain |
| **Content and visual production** | Narrative structure, layout systems, charts, covers, illustrations, infographics, diagrams, and image slides | Structured content and visual assets |
| **Native multi-format generation** | Editable PPTX, standalone HTML, PDF, PNG, SVG, presenter navigation, and print behavior | Editable or publication-ready products |
| **Rendered acceptance and repair** | Data fidelity, overflow, clipping, collision, fonts, page count, interaction, animation, offline behavior, repair loops | Quality-gated deliverables |
| **Safety, provenance, and status** | Untrusted-code isolation, credential protection, source/license traceability, `PASS / PARTIAL / FAIL` semantics | Auditable production evidence |
| **Continuous upstream synchronization** | Stable-release discovery, allowlisted imports, license validation, adapter preservation, full validation before commit | Current capabilities without architecture regression |

The seven major capabilities retain every L0–L19 responsibility. See the [full architecture](docs/architecture.md), [Fast Path contract](presentation-studio/references/fast-path.md), and [upstream synchronization guide](docs/upstream-sync.md).

The live synchronization result, example hashes, and repository gates are recorded in the [2026-08-13 acceptance evidence](docs/evidence/acceptance-2026-08-13.md).

### Product scope

- Native editable and data-driven PPTX
- Swiss/editorial, executive, technical, and narrative decks
- Standalone HTML presentations and dual-format delivery
- Cover images, article illustrations, infographics, technical diagrams, data images, and image slide decks
- Exact-data preservation, structural validation, real rendering when runtimes are available, and explicit degradation when they are not

## Repository map

```text
presentation-studio/
├── SKILL.md                 # Entry point and routing policy
├── catalog/                 # Product recipes and style profiles
├── core/                    # Retrieval, data binding, routing, validation
├── engines/                 # Four vendored upstream engines and adapters
├── references/              # Fast Path and detailed operating contracts
├── scripts/                 # Skill-local execution helpers
└── source-lock.json         # Pinned sources, releases, licenses, import rules
examples/                    # Six verified bilingual example products
scripts/                     # Packaging, repository verification, upstream sync
docs/                        # Architecture, sync operations, evidence, plans
```

## Credits and licensing

Presentation Studio is licensed under [AGPL-3.0](LICENSE). Vendored components retain their original licenses and notices. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [CONTRIBUTORS.md](CONTRIBUTORS.md), the upstream repositories above, and `presentation-studio/engines/*/LICENSE*`.

This integration adds the product catalog, style catalog, Fast Path, environment preflight, exact-data binding, engine routing, safety boundaries, acceptance semantics, deterministic packaging, and upstream synchronization around the four upstream projects. It does not replace or obscure their authorship.
