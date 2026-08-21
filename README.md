# Presentation Studio

> 轻量、快速、可验证的 PPT 与视觉产品工作流。在短时间内交付高质量结果，同时保留完整的 20 层能力架构。
>
> A lightweight, fast, and verifiable workflow for high-quality presentations and visual products, backed by the complete 20-layer capability architecture.

[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5)](presentation-studio/catalog/styles.json)

[下载最新版](https://github.com/kwhi6693-web/presentation-studio/releases/latest) · [60 秒快速开始](#60-秒快速开始--60-second-quick-start) · [中文说明](#中文说明) · [English Guide](#english-guide) · [示例产品](#双语示例产品) · [安装与验证](#安装与验证) · [贡献](CONTRIBUTING.md) · [安全](SECURITY.md)

## 60 秒快速开始 / 60-second quick start

### Release 安装 / Install from a Release

1. 从 [Latest Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) 下载 `presentation-studio.zip` 和 `presentation-studio.zip.sha256`。Download both assets into the same directory.
2. 使用下方[安装与验证](#安装与验证)中的 Linux、macOS 或 PowerShell 命令校验 SHA-256。Verify the ZIP before extraction.
3. 解压后应只有一个 `presentation-studio/` 根目录；使用已解析的 Python 和 Node 可执行文件运行自检：

   ```bash
   python presentation-studio/scripts/self_check.py \
     --root presentation-studio \
     --python <resolved-python> \
     --node <resolved-node> \
     --json
   ```

4. 自检返回 `PASS` 后，将该根目录安装到 Codex Skills 目录。Do not activate a package that fails its self-check or checksum validation.

### 源码安装 / Install from source

```powershell
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1
```

```bash
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
./scripts/install.sh
```

两个安装器都会先在 Skill 发现目录外暂存、计数并运行真实自检，再进行激活。Both installers stage and self-check outside the discovery directory before activation.

## 运行时与能力支持矩阵 / Runtime and capability matrix

| 运行时或能力 / Runtime or capability | 用途 / Required for | 必需性 / Requirement | Preflight evidence |
|---|---|---|---|
| Python 3.11+（已测试；优先使用 bundled runtime） | 路由、验证、PPTX 工作流 | 核心 | `runtimes.python`, `readiness.pptx_core` |
| 已解析的 bundled Node.js runtime | 浏览器与 Baoyu 工作流 | 对相应引擎为核心 | `runtimes.node`, `readiness.baoyu_core` |
| Office renderer | 原生 Office 渲染 | 可选 | `readiness.office_renderer` |
| Chromium + Playwright | 浏览器渲染、测量与 QA | 可选 | `readiness.chromium`, `capabilities.node.browser_qa` |
| 图像 Provider 凭据 | 生成式视觉资产 | 可选 | 仅报告脱敏后的 provider readiness |
| 可选 Python / Node 模块 | 摄取、旁白、高级 SVG、Web 抽取 | 可选 | 逐模块布尔值；一个缺失模块不会污染其他模块 |

在 Codex App 中优先调用 bundled dependency loader；否则使用 [dependencies.md](presentation-studio/references/dependencies.md) 中的固定解析流程。不要把 WindowsApps alias 或偶然命中的 PATH 程序当作运行时证据。

## 产品与引擎选择 / Product and engine selection

| 需求 / Need | 推荐路径 / Preferred route |
|---|---|
| 原生可编辑 PPTX、图表、表格、演讲者备注 | PPT Master |
| Swiss / editorial 视觉体系和演示叙事 | Guizang |
| 独立 HTML、键盘导航、浏览器 PDF | Frontend Slides |
| 封面、插图、信息图、技术图、图像幻灯片 | Baoyu |
| 同时交付 PPTX 与独立 HTML / PDF | Dual-format product route |

最终选择由标准化 brief、环境 preflight、产品 Catalog、硬约束和降级策略共同决定。指定产品与请求格式冲突时，系统应明确返回冲突，而不是静默换成另一种交付物。

## 故障排查 / Troubleshooting

- 使用明确解析的 Python、Node 和 Node-package 路径运行 `presentation-studio/scripts/preflight.py`，不要先探测裸 `python`、`node` 或 PATH alias。
- 对已安装的 Skill 根目录运行 `presentation-studio/scripts/self_check.py --json`，确认文件、Catalog、引擎和最小路由都能加载。
- 区分 `PASS`、`PARTIAL` 和 `FAIL`：可选能力缺失可以导致明确降级，但不可把需要原生编辑的数据交付静默扁平化成图片。
- 提交 Bug 前移除凭据、私有文件内容和本机绝对路径，并附上脱敏后的 preflight、自检、版本和最小复现。
- 安全漏洞不要提交公开 Issue；请遵循 [SECURITY.md](SECURITY.md) 私下报告。

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

安装器会在发现目录外完成暂存、文件计数与真实自检；强制更新时，旧版本进入 `.agents/skill-backups/presentation-studio/`，不会再形成重复 Skill。Windows 自定义目标若会超过可移植路径上限，会在写入前明确拒绝。The installers stage, count, and self-check the complete package before activation; forced updates keep the previous version outside the Skill discovery directory, and unsafe deep Windows destinations fail before writes.

也可以下载 [确定性构建包](dist/presentation-studio.zip)，并使用 [checksums.sha256](checksums.sha256) 核对 SHA-256。仓库内的清单引用 `dist/presentation-studio.zip`，供源码检出目录使用；GitHub Release 则同时提供 `presentation-studio.zip` 和专用的 `presentation-studio.zip.sha256`，两者下载到同一目录后可直接校验：

```bash
# Linux
sha256sum -c presentation-studio.zip.sha256

# macOS
shasum -a 256 -c presentation-studio.zip.sha256
```

```powershell
# Windows PowerShell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: expected $expected, got $actual" }
"OK: $actual"
```

发布者可用纯 Python 标准库生成 Release 专用清单：

```bash
python scripts/build_release_checksum.py dist/presentation-studio.zip presentation-studio.zip.sha256
```

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

自动同步支持上游事件触发、手动触发和每小时第 17 分钟轮询回退。只有来源、稳定版本、路径和许可证均通过校验，并且仓库全部门禁通过时，才会向独立自动化分支提交并创建或更新同步 PR；`main` 仍要求 PR 和 `verify` 门禁。操作说明见 [上游持续同步](docs/upstream-sync.md)。

本次真实同步、示例哈希与仓库门禁记录见 [2026-08-13 验收证据](docs/evidence/acceptance-2026-08-13.md)。

## English Guide

Presentation Studio combines four upstream specialties behind one product-oriented workflow. A complete brief can take the Fast Path for rapid delivery; exact data, format conflicts, animation, narration, multi-engine composition, or high-risk output automatically escalates to the complete workflow.

### Verify a downloaded Release

Download `presentation-studio.zip` and `presentation-studio.zip.sha256` from the same GitHub Release into one directory. The Release checksum asset uses the ZIP basename, so it works directly with standard tools. (`checksums.sha256` is the separate source-checkout manifest and intentionally refers to `dist/presentation-studio.zip`.)

```bash
# Linux
sha256sum -c presentation-studio.zip.sha256

# macOS
shasum -a 256 -c presentation-studio.zip.sha256
```

```powershell
# Windows PowerShell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: expected $expected, got $actual" }
"OK: $actual"
```

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
docs/                        # Architecture, sync operations, and evidence
```

## Credits and licensing

Presentation Studio is licensed under [AGPL-3.0](LICENSE). Vendored components retain their original licenses and notices. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [CONTRIBUTORS.md](CONTRIBUTORS.md), the upstream repositories above, and `presentation-studio/engines/*/LICENSE*`.

Contributions are welcome through the verified workflow in [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately according to [SECURITY.md](SECURITY.md), and follow the participation standards in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

This integration adds the product catalog, style catalog, Fast Path, environment preflight, exact-data binding, engine routing, safety boundaries, acceptance semantics, deterministic packaging, and upstream synchronization around the four upstream projects. It does not replace or obscure their authorship.
