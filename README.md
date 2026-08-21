# Presentation Studio

> 面向 Codex 的双语演示与视觉产品 Skill：把自然语言需求、精确数据和现有素材路由到合适的原生引擎，并通过真实渲染与质量门禁交付可验证的 PPTX、HTML、PDF、PNG 或 SVG。
>
> A bilingual Codex Skill for presentation and visual production: it routes natural-language briefs, exact data, and existing assets to the right native engines, then applies rendered quality gates before delivering verifiable PPTX, HTML, PDF, PNG, or SVG outputs.

[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5)](presentation-studio/catalog/styles.json)

[中文](#中文说明) · [English](#english-guide) · [安装 / Installation](#安装) · [使用 / Usage](#使用方法) · [输入输出示例 / I/O examples](#输入输出示例) · [架构 / Architecture](docs/architecture.md) · [贡献 / Contributing](CONTRIBUTING.md) · [安全 / Security](SECURITY.md) · [Latest Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest)

---

## 中文说明

### 项目解决什么问题

制作一套可靠的演示产品，不只是“生成几张好看的幻灯片”。真实交付通常同时涉及内容结构、格式选择、数据准确性、原生可编辑性、视觉资产、演讲者行为、跨平台导出和最终验收。Presentation Studio 把这些工作统一为一个可路由、可降级、可验证的 Codex Skill。

它重点解决以下问题：

- **产品选择困难**：通过智能检索，根据受众、用途、输出格式、可编辑性、数据形式、演示方式和运行时能力，从 13 种产品配方与 8 种风格中做可解释选择。
- **单一引擎能力有限**：按任务调用 PPT Master、Guizang、Frontend Slides、Baoyu，或组合多个引擎，而不是强迫所有需求走同一条生成路径。
- **数据在视觉化过程中失真**：对 CSV、XLSX、JSON、Markdown 表格等精准数据建立 manifest、引擎 payload 和渲染后 observed contract；三者未完成精确比对时，不把数据保真标为 `PASS`。
- **“可编辑”名不副实**：需要原生编辑时保留 PowerPoint 图表、表格、文本和形状，不用整页截图冒充可编辑 PPTX；图像型幻灯片会明确标注其编辑性限制。
- **只生成、不验收**：执行 `validate → render → inspect every page → repair → validate again`，检查溢出、裁切、碰撞、字号、对比度、图表完整性、备注、动画、键盘操作、打印与离线行为。
- **依赖缺失导致静默降级**：预检 Python、Node、Office renderer、Chromium、图像 Provider 和模块级能力；只禁用受影响功能，并用 `PASS`、`PARTIAL`、`FAIL` 表达实际完成状态。
- **上游能力难以安全跟进**：固定四个上游来源、版本、许可证和允许导入路径；同步后必须通过完整门禁并创建 PR，不能直接绕过受保护的 `main`。

它不是在线 PowerPoint 编辑器，也不是一个“输入一句话即可保证所有运行时都可用”的单体生成器。它是 Codex 中的编排与质量控制层：生成工作仍由被选中的原生引擎和当前环境中真实可用的运行时完成。

### 主要方法

```text
自然语言、数据、模板或素材
          │
          ▼
1. 标准化 brief：受众、目的、格式、可编辑性、风格、比例、期限
          │
          ▼
2. 环境预检：Python、Node、Office、Chromium、Provider、模块能力
          │
          ▼
3. Catalog 检索：13 种产品 + 8 种风格 + 冲突与降级判断
          │
          ▼
4. 引擎路由：PPT Master / Guizang / Frontend Slides / Baoyu / 混合链
          │
          ▼
5. 原生生产：PPTX / HTML / PDF / PNG / SVG
          │
          ▼
6. 质量闭环：validate → render → inspect → repair → validate
          │
          ▼
7. 状态化交付：PASS / PARTIAL / FAIL + 未执行项 + 来源记录
```

需求完整、风险较低时使用 **Fast Path**，直接执行必要的预检、推荐、路由、生成和针对性验收。涉及精确数据、格式冲突、动画、旁白、多引擎或高风险交付时自动升级到 **Complete Path**。Fast Path 省略的是重复决策，不省略必需质量门禁；详细规则见 [Fast Path contract](presentation-studio/references/fast-path.md)。

### 主要大功能层

| 主要能力 | 实际覆盖 | 代表结果 |
|---|---|---|
| **智能理解与产品决策** | brief 标准化、环境预检、13 种产品检索、8 种风格推断、硬约束冲突 | 可解释的产品与风格选择 |
| **数据契约与引擎编排** | 精确数据清单、类型/顺序/单位保护、四引擎与混合链路由 | 不可变数据合同与引擎计划 |
| **内容与视觉生产** | 叙事结构、版式、图表、封面、插图、信息图、技术图 | 内容计划与视觉资产 |
| **多格式原生生成** | 可编辑 PPTX、独立 HTML、PDF、PNG、SVG、演讲者导航 | 原生或可直接发布的交付物 |
| **渲染验收与自动修复** | 数据保真、溢出、碰撞、字体、页数、交互、打印、离线和修复循环 | 通过质量门禁的产品 |
| **安全、溯源与状态** | 不可信内容隔离、凭据保护、来源/许可证记录、三态结果 | 可审计的执行证据 |
| **上游持续同步** | 稳定版发现、允许路径导入、许可证检查、完整测试后创建 PR | 可维护的上游能力更新 |

这七层映射到底层 L0–L19 的完整职责，详见 [架构文档](docs/architecture.md)。

### 支持的产品与引擎

当前 [产品 Catalog](presentation-studio/catalog/products.json) 包含 13 种产品配方：

| 产品 ID | 典型用途 | 原生输出 | 主要引擎 |
|---|---|---|---|
| `native-editable-deck` | 通用汇报、业务更新 | PPTX | PPT Master |
| `native-data-deck` | 财务报告、指标复盘、数据评审 | PPTX | PPT Master |
| `swiss-editorial-deck` | Swiss/editorial 策略或年度叙事 | PPTX、HTML | Guizang + PPT Master + Frontend Slides |
| `executive-deck` | 董事会、投资人、决策简报 | PPTX | PPT Master |
| `technical-deck` | 技术架构、工程评审、系统讲解 | PPTX | PPT Master |
| `html-presenter` | 单文件 Web 演示、演讲者模式 | HTML、PDF | Guizang + Frontend Slides |
| `dual-format-deck` | 同一内容同时用于会议和 Web | PPTX、HTML、PDF | PPT Master + Frontend Slides |
| `cover-image` | 文章、演示或社交封面 | PNG | Baoyu |
| `article-illustration` | 文章插图、概念视觉 | PNG | Baoyu |
| `infographic-image` | 数据总结、比较型信息图 | PNG | Baoyu |
| `technical-diagram` | 架构图、系统图、流程图 | SVG | Baoyu |
| `data-image` | 指标图、图表图像 | PNG | Baoyu |
| `image-slide-deck` | 图像驱动的故事型演示 | PPTX（图像型页面） | Baoyu + PPT Master |

四个引擎的职责边界：

| 引擎 | 适用场景 | 真实性边界 |
|---|---|---|
| **PPT Master** | 原生 PPTX、图表、表格、备注、动画、模板 | 负责 PowerPoint 原生对象与容器；需要真实渲染器时会显式报告可用性 |
| **Guizang** | Swiss/editorial 视觉系统、叙事与演示布局 | 提供设计权威，最终文件由所选 renderer 生成 |
| **Frontend Slides** | 独立 HTML、键盘导航、演讲者行为、HTML→PDF | PDF 导出与浏览器 QA 需要已解析的 Chromium/Playwright 能力 |
| **Baoyu** | 封面、插图、信息图、技术图、数据图和图像幻灯片 | 生成式图像需要可用 Provider；SVG 技术图不等同于原生 PowerPoint 对象 |

### 安装

#### 方法一：从 GitHub Release 安装

1. 从 [Latest Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) 下载 `presentation-studio.zip` 和 `presentation-studio.zip.sha256` 到同一目录。
2. 校验 ZIP。Release 专用清单使用文件 basename，可直接运行标准校验命令。

Linux：

```bash
sha256sum -c presentation-studio.zip.sha256
```

macOS：

```bash
shasum -a 256 -c presentation-studio.zip.sha256
```

Windows PowerShell：

```powershell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: expected $expected, got $actual" }
"OK: $actual"
```

3. 解压后应只有一个 `presentation-studio/` Skill 根目录。使用已明确解析的 Python 和 Node 运行自检：

```bash
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
```

4. 只有自检返回 `PASS` 后，才把该目录放入当前用户的 Codex Skills 发现目录。

> 不要把 Microsoft Store 的 WindowsApps Python alias 当成真实运行时。Codex App 环境应优先使用 bundled dependency loader；手动解析方法见 [dependencies.md](presentation-studio/references/dependencies.md)。

#### 方法二：从源码安装

Windows PowerShell：

```powershell
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1
```

Linux 或 macOS：

```bash
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
./scripts/install.sh
```

安装器先在 Skill 发现目录外暂存完整包、统计文件并运行真实自检，再激活新版本。强制更新时，旧版本会进入 `.agents/skill-backups/presentation-studio/`，避免被 Codex 发现为重复 Skill；Windows 下过深、可能超过可移植路径上限的目标会在写入前失败。

仓库内的 [checksums.sha256](checksums.sha256) 专供源码检出目录使用，因而引用 `dist/presentation-studio.zip`；它与下载到同一目录即可运行的 Release 专用 `presentation-studio.zip.sha256` 是两个不同合同，请勿混用。

### 使用方法

#### 在 Codex 中使用

安装后，直接用自然语言描述目标。建议至少提供：

- 主题与目的；
- 受众；
- 输入材料或数据；
- 需要的格式；
- 是否要求原生可编辑；
- 风格或品牌约束；
- 页面比例、页数和截止时间；
- 是否需要备注、动画、演讲者模式或离线 HTML。

示例请求：

```text
使用 Presentation Studio，为董事会制作一套 16:9 的“AI 产品战略”演示。
受众是公司高管，语气专业、克制，输出原生可编辑 PPTX、独立 HTML 和 PDF。
使用我提供的季度指标表，数值、单位和排序必须保持不变；PPTX 中的图表和表格必须可编辑。
交付前检查每一页的溢出、裁切、对比度、数据保真、备注和离线行为，并报告 PASS/PARTIAL/FAIL。
```

Codex 会先加载 Skill，解析明确的 Python/Node 运行时，执行 preflight，再根据 Catalog 推荐产品与风格，路由到引擎并完成生成和质量闭环。缺少可选 renderer 或 Provider 时，应报告受影响能力，而不是假装对应验收已经执行。

#### 诊断推荐与路由

以下 CLI 是 Skill 的诊断和编排入口，**不会单独生成完整演示文件**。真正的生成仍由路由结果指定的引擎完成。

先运行环境预检。`preflight.py` 默认直接输出 JSON；它没有 `--json` 参数：

```bash
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
```

然后创建任务本地的 `request.json`：

```json
{
  "kind": "presentation",
  "outputs": ["pptx", "html", "pdf"],
  "topic": "AI product strategy",
  "audience": "executives",
  "purpose": "decision-brief",
  "tone": "professional",
  "density": "medium",
  "aspect_ratio": "16:9",
  "readiness": {
    "python": true,
    "node": true,
    "pptx_core": true,
    "office_renderer": false,
    "chromium": false,
    "image_provider": false,
    "baoyu_core": true
  }
}
```

`readiness` 必须来自本次真实 preflight 的脱敏布尔值，不能照抄示例或凭 PATH 猜测。执行推荐：

```bash
python presentation-studio/scripts/recommend.py --json-file request.json
```

把推荐结果中的 `product` 和 `style.selected` 写入路由请求，再执行：

```bash
python presentation-studio/scripts/route.py --json-file route-request.json
```

完整自动化、安全的 PowerShell handoff 见 [运行时依赖说明](presentation-studio/references/dependencies.md)，产品检索规则见 [product-retrieval.md](presentation-studio/references/product-retrieval.md)，引擎路由规则见 [router.md](presentation-studio/references/router.md)。

### 输入输出示例

#### 示例 1：同一内容交付 PPTX、HTML 和 PDF

输入：上面的董事会 brief，以及真实 preflight readiness。

当前 Catalog 对该 JSON 的真实推荐关键字段为：

```json
{
  "product": "dual-format-deck",
  "deliverables": ["pptx", "html", "pdf"],
  "style": {
    "selected": "executive-minimal",
    "source": "inferred",
    "confidence": "medium"
  },
  "engine_chain": ["ppt-master", "frontend-slides"],
  "status": "PARTIAL",
  "missing_prerequisites": ["office_renderer", "chromium"]
}
```

这里的 `PARTIAL` 是预期且诚实的：示例 readiness 明确没有 Office renderer 和 Chromium。它不表示路由失败，而表示相关真实渲染/浏览器验收尚不能宣称执行完成。在能力齐全的环境中，状态由本次实际 preflight 和后续质量门禁决定。

把推荐的产品和风格加入请求后，真实路由结果为：

```json
{
  "outputs": ["pptx", "html", "pdf"],
  "engines": ["ppt-master", "frontend-slides"],
  "capabilities": {
    "ppt-master": ["native-pptx"],
    "frontend-slides": ["html-slides", "html-pdf"]
  },
  "references": [
    "native-pptx",
    "html-presenter",
    "product-retrieval",
    "qa",
    "error-system"
  ]
}
```

完成生成后的约定目录形态：

```text
<output-root>/ai-product-strategy/
├── ai-product-strategy.pptx
├── ai-product-strategy.html
├── ai-product-strategy.pdf
├── assets/
└── .temp/
```

最终文件是否全部存在、是否达到 `PASS`，取决于被选引擎实际运行和最终质量检查，不能仅凭上述路由 JSON 推断。

#### 示例 2：精确数据驱动的可编辑 PPTX

```text
输入：quarterly-metrics.xlsx；要求保留指标名称、数值、单位、季度顺序和缺失值。
目标：投资人指标复盘，16:9，输出可编辑 PPTX，图表和表格必须为原生对象。

典型路由：native-data-deck → ppt-master
典型输出：metrics-review.pptx
验收：manifest == engine payload == observed contract，并检查原生图表、表格、页数和渲染结果。
```

如果缺少完整 manifest、引擎 payload 或渲染后 observed contract，数据结果最高只能是 `PARTIAL`。

#### 示例 3：可编辑 SVG 技术架构图

```text
输入：服务清单、调用方向、信任边界和部署区域。
目标：用于工程设计文档的 16:9 技术架构图，输出 SVG。

典型路由：technical-diagram → baoyu diagram
典型输出：service-architecture.svg
验收：节点与连线语义、文字可读性、边界、对比度、SVG 结构与来源记录。
```

#### 已验证的双语示例产品

仓库包含中英文各一套 5 页验收产品，每套提供 PPTX、HTML 和 PDF。PPTX 验证备注、原生图表、原生表格和淡入动画；HTML 验证键盘导航、可编辑文本、打印样式和离线资源；PDF 验证页数与 16:9 页面尺寸。

<details>
<summary><strong>展开中文示例（PPTX / HTML / PDF）</strong></summary>

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

### 运行时与状态

| 运行时或能力 | 用途 | 必需性 | Preflight 证据 |
|---|---|---|---|
| Python 3.11+（已测试；优先 bundled runtime） | 推荐、路由、验证、PPTX 工作流 | 核心 | `runtimes.python`, `readiness.pptx_core` |
| 已解析的 Node.js | Frontend Slides 与 Baoyu | 对相应引擎为核心 | `runtimes.node`, `readiness.baoyu_core` |
| Office renderer | 原生 Office 渲染检查 | 可选 | `readiness.office_renderer` |
| Chromium + Playwright | HTML/PDF 导出、浏览器测量与 QA | 可选 | `readiness.chromium`, `capabilities.node.browser_qa` |
| 图像 Provider 凭据 | 生成式封面、插图和图像资产 | 可选 | 脱敏后的 `readiness.image_provider` |
| 可选 Python/Node 模块 | 摄取、旁白、高级 SVG、Web 抽取 | 可选 | 逐模块布尔值；一个缺失模块不会污染其他模块 |

状态语义：

- `PASS`：当前环境中所有必需命令都已真实成功执行，所需交付物存在，最终修复后重新通过质量门禁。
- `PARTIAL`：核心结果可用，但一个或多个可选/要求能力未执行或不可用；必须明确列出限制。
- `FAIL`：硬约束冲突、必需运行时缺失、生成失败或质量门禁未通过。

### 故障排查

- 不要先运行裸 `python`、`py`、`node` 或依赖偶然 PATH 命中；先解析并保存绝对路径。
- 对安装目录执行 `self_check.py --json`，确认文件、Catalog、四个引擎入口和最小推荐/路由链能够加载。
- `preflight.py` 默认输出 JSON，不接受 `--json`；只把实际输出的脱敏 readiness 写入请求。
- Office renderer 或 Chromium 缺失不必自动导致整个任务失败，但涉及的渲染、PDF 或浏览器 QA 不能标为 `PASS`。
- 图像 Provider 不可用时不要安装无关依赖掩盖问题；选择不依赖生成式图像的产品，或明确报告限制。
- 提交 Bug 前移除凭据、私有文件内容和本机绝对路径，并附上脱敏 preflight、自检、版本与最小复现。
- 安全漏洞不要提交公开 Issue；请遵循 [SECURITY.md](SECURITY.md) 私下报告。

### 开发、验证与仓库结构

仓库验收命令：

```bash
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
python -m unittest discover -s tests -v
```

`build_package.py` 生成确定性 `dist/presentation-studio.zip`；`verify_package.py` 验证文件夹、Catalog、来源和 ZIP parity。Release 专用 checksum 可用纯标准库生成：

```bash
python scripts/build_release_checksum.py \
  dist/presentation-studio.zip \
  presentation-studio.zip.sha256
```

仓库结构：

```text
presentation-studio/
├── SKILL.md                 # Skill 入口、执行合同和路由权威
├── catalog/                 # 13 种产品配方与 8 种风格
├── core/                    # 请求标准化、检索、数据绑定、路由、验证
├── engines/                 # 四个上游引擎及适配层
├── references/              # Fast Path、依赖、QA、路由等运行合同
├── scripts/                 # Skill 内部 preflight/recommend/route/self-check
└── source-lock.json         # 固定来源、版本、许可证与导入规则
examples/                    # 六个已验证的中英文 PPTX/HTML/PDF 产品
scripts/                     # 安装、打包、仓库健康、示例验证与上游同步
tests/                       # 单元、合同、安装、渲染与安全回归测试
docs/                        # 架构、同步操作、设计、计划与验收证据
```

上游只读检查：

```bash
python scripts/upstream_sync.py check --json
```

维护者的安全同步：

```bash
python scripts/upstream_sync.py sync --all \
  --report artifacts/upstream-sync-report.json
```

自动工作流支持 upstream event、`workflow_dispatch` 和每小时第 17 分钟的 schedule 回退。只有稳定版本、来源、允许路径、许可证与完整仓库门禁全部通过后，才会创建或更新独立同步 PR。详见 [上游同步指南](docs/upstream-sync.md) 和 [验收证据](docs/evidence/acceptance-2026-08-13.md)。

---

## English Guide

### What the project solves

A dependable presentation deliverable requires more than attractive slide images. Real work combines narrative structure, format selection, exact data, native editability, visual assets, presenter behavior, cross-platform export, and final acceptance. Presentation Studio packages those concerns as a routable, degradable, and verifiable Codex Skill.

It addresses these recurring problems:

- **Choosing the right product**: Intelligent retrieval selects explainably from 13 product recipes and eight style profiles using audience, purpose, formats, editability, data forms, delivery behavior, and actual runtime readiness.
- **Avoiding a one-engine compromise**: invoke PPT Master, Guizang, Frontend Slides, Baoyu, or a hybrid chain according to the requested product.
- **Protecting exact data**: preserve values, types, order, units, missing values, and duplicates across a manifest, full engine payload, and post-render observed contract. Exact-data status is not `PASS` until all three compare exactly.
- **Keeping editability honest**: use native PowerPoint text, shapes, charts, and tables when native editability is required; never describe full-slide screenshots as an editable object deck.
- **Validating the rendered result**: run `validate → render → inspect every page → repair → validate again` for overflow, clipping, collisions, typography, contrast, chart integrity, notes, animation, keyboard controls, print behavior, and offline behavior.
- **Making capability gaps explicit**: preflight Python, Node.js, Office rendering, Chromium, image providers, and module-level features; disable only affected capabilities and report `PASS`, `PARTIAL`, or `FAIL` truthfully.
- **Updating vendored engines safely**: pin upstream sources, stable versions, licenses, and import allowlists; require the complete repository gate and a pull request before changes can reach protected `main`.

Presentation Studio is not an online PowerPoint editor or a single generator that guarantees every renderer is available. It is the orchestration and quality-control layer inside Codex; native generation is performed by the selected engines using runtimes that are actually available in the current environment.

### Core method

```text
Natural-language brief, data, template, or assets
                    │
                    ▼
1. Normalize: audience, purpose, formats, editability, style, ratio, deadline
                    │
                    ▼
2. Preflight: Python, Node.js, Office, Chromium, providers, module capabilities
                    │
                    ▼
3. Retrieve: 13 products + 8 styles + constraint and fallback evaluation
                    │
                    ▼
4. Route: PPT Master / Guizang / Frontend Slides / Baoyu / hybrid chain
                    │
                    ▼
5. Produce natively: PPTX / HTML / PDF / PNG / SVG
                    │
                    ▼
6. Close the quality loop: validate → render → inspect → repair → validate
                    │
                    ▼
7. Deliver with evidence: PASS / PARTIAL / FAIL + unexecuted checks + provenance
```

A complete, low-risk brief can use the **Fast Path** while retaining every mandatory preflight, routing, rendering, data, and quality gate. Exact data, format conflicts, animation, narration, multi-engine composition, or high-risk delivery escalates to the **Complete Path**. See the [Fast Path contract](presentation-studio/references/fast-path.md).

### Major capability layers

| Major capability | Actual coverage | Representative result |
|---|---|---|
| **Intent understanding and product decisions** | Brief normalization, preflight, 13-product retrieval, eight-style inference, hard-constraint detection | Explainable product and style selection |
| **Data contracts and engine orchestration** | Exact-data manifests, type/order/unit protection, four-engine and hybrid routing | Immutable data contract and engine plan |
| **Content and visual production** | Narrative structure, layouts, charts, covers, illustrations, infographics, diagrams | Content plan and visual assets |
| **Native multi-format generation** | Editable PPTX, standalone HTML, PDF, PNG, SVG, presenter navigation | Native or publication-ready deliverables |
| **Rendered acceptance and repair** | Fidelity, overflow, collisions, fonts, page count, interaction, print, offline behavior | Quality-gated products |
| **Safety, provenance, and status** | Untrusted-content boundaries, credential protection, source/license records, tri-state results | Auditable execution evidence |
| **Continuous upstream synchronization** | Stable-release discovery, allowlisted imports, license checks, PR after complete validation | Maintainable upstream updates |

These seven layers retain every L0–L19 responsibility described in the [architecture guide](docs/architecture.md).

### Supported products and engines

The current [product catalog](presentation-studio/catalog/products.json) contains 13 recipes:

| Product ID | Typical use | Native outputs | Primary engines |
|---|---|---|---|
| `native-editable-deck` | General presentations and business updates | PPTX | PPT Master |
| `native-data-deck` | Financial reports and metric reviews | PPTX | PPT Master |
| `swiss-editorial-deck` | Swiss/editorial strategy or annual narratives | PPTX, HTML | Guizang + PPT Master + Frontend Slides |
| `executive-deck` | Board, investor, and decision briefs | PPTX | PPT Master |
| `technical-deck` | Architecture and engineering reviews | PPTX | PPT Master |
| `html-presenter` | Single-file web presentation and presenter mode | HTML, PDF | Guizang + Frontend Slides |
| `dual-format-deck` | Shared content for meetings and the web | PPTX, HTML, PDF | PPT Master + Frontend Slides |
| `cover-image` | Article, presentation, or social covers | PNG | Baoyu |
| `article-illustration` | Editorial illustrations and concept visuals | PNG | Baoyu |
| `infographic-image` | Data summaries and comparison infographics | PNG | Baoyu |
| `technical-diagram` | Architecture, system, and process diagrams | SVG | Baoyu |
| `data-image` | Metric visuals and chart images | PNG | Baoyu |
| `image-slide-deck` | Image-led narrative presentations | PPTX with image-based pages | Baoyu + PPT Master |

Engine boundaries:

| Engine | Best fit | Truthfulness boundary |
|---|---|---|
| **PPT Master** | Native PPTX, charts, tables, notes, animation, templates | Owns native PowerPoint objects and containers; real Office rendering is reported separately |
| **Guizang** | Swiss/editorial design systems, narrative, presentation layouts | Supplies design authority; the selected renderer creates the final file |
| **Frontend Slides** | Standalone HTML, keyboard navigation, presenter behavior, HTML→PDF | PDF export and browser QA require resolved Chromium/Playwright capability |
| **Baoyu** | Covers, illustrations, infographics, diagrams, data images, image slides | Generative imagery needs a provider; an SVG diagram is not a native PowerPoint object |

### Installation

#### Option 1: install from a GitHub Release

1. Download `presentation-studio.zip` and `presentation-studio.zip.sha256` from the same [Latest Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest).
2. Verify the ZIP. The Release checksum uses the ZIP basename and works directly with standard tools.

Linux:

```bash
sha256sum -c presentation-studio.zip.sha256
```

macOS:

```bash
shasum -a 256 -c presentation-studio.zip.sha256
```

Windows PowerShell:

```powershell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch: expected $expected, got $actual" }
"OK: $actual"
```

3. Extraction should produce one `presentation-studio/` Skill root. Run its self-check with explicitly resolved Python and Node.js executables:

```bash
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
```

4. Activate the directory in the current user's Codex Skills discovery location only after the self-check returns `PASS`.

Do not treat a Microsoft Store WindowsApps Python alias as runtime evidence. In Codex App, prefer the bundled dependency loader; see [dependencies.md](presentation-studio/references/dependencies.md) for the explicit fallback resolver.

#### Option 2: install from source

Windows PowerShell:

```powershell
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1
```

Linux or macOS:

```bash
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
./scripts/install.sh
```

Both installers stage the complete package outside Skill discovery, count it, run a real self-check, and only then activate it. Forced updates move the previous copy to `.agents/skill-backups/presentation-studio/`, where Codex will not discover it as a duplicate Skill. Unsafe deep Windows destinations fail before any write.

The repository [checksums.sha256](checksums.sha256) is for a source checkout and intentionally names `dist/presentation-studio.zip`. It is a different contract from the Release-only `presentation-studio.zip.sha256`; do not interchange them.

### Usage

#### Use it in Codex

After installation, describe the desired result in natural language. A strong brief includes:

- topic and purpose;
- audience;
- source material or exact data;
- required formats;
- native editability requirements;
- style or brand constraints;
- aspect ratio, page count, and deadline;
- notes, animation, presenter mode, or offline HTML requirements.

Example request:

```text
Use Presentation Studio to create a 16:9 “AI Product Strategy” presentation for our board.
Use a professional, restrained tone and deliver a native editable PPTX, standalone HTML, and PDF.
Use the supplied quarterly metrics table without changing any value, unit, or row order; charts and tables in the PPTX must remain editable.
Before delivery, inspect every page for overflow, clipping, contrast, data fidelity, notes, and offline behavior, then report PASS/PARTIAL/FAIL.
```

Codex loads the Skill, resolves explicit Python and Node.js runtimes, runs preflight, retrieves a product and style from the catalog, routes the request, and executes the selected production and quality workflows. Missing optional renderers or providers must be reported; their checks cannot be presented as completed.

#### Diagnose recommendation and routing

The following CLIs are diagnostic and orchestration entry points. They **do not generate a complete presentation by themselves**; generation happens later in the selected engines.

Run preflight first. `preflight.py` emits JSON by default and does not accept a `--json` flag:

```bash
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
```

Create a task-local `request.json` using the schema shown in the Chinese [input/output example](#输入输出示例). Populate `readiness` only from the current redacted preflight result. Then run:

```bash
python presentation-studio/scripts/recommend.py --json-file request.json
```

Copy the returned `product` and `style.selected` into a route request:

```bash
python presentation-studio/scripts/route.py --json-file route-request.json
```

The verified example returns `dual-format-deck`, `executive-minimal`, and the `ppt-master + frontend-slides` engine chain. Its exact input, abbreviated recommendation, route output, and expected directory shape are shown above. See [dependencies.md](presentation-studio/references/dependencies.md) for the safe PowerShell handoff, [product-retrieval.md](presentation-studio/references/product-retrieval.md) for retrieval, and [router.md](presentation-studio/references/router.md) for route authority.

### Input and output examples

#### Example 1: deliver the same content as PPTX, HTML, and PDF

Input: the board brief above and readiness booleans from a real preflight run.

```json
{
  "kind": "presentation",
  "outputs": ["pptx", "html", "pdf"],
  "topic": "AI product strategy",
  "audience": "executives",
  "purpose": "decision-brief",
  "tone": "professional",
  "density": "medium",
  "aspect_ratio": "16:9",
  "readiness": {
    "python": true,
    "node": true,
    "pptx_core": true,
    "office_renderer": false,
    "chromium": false,
    "image_provider": false,
    "baoyu_core": true
  }
}
```

The current catalog produces these verified recommendation fields:

```json
{
  "product": "dual-format-deck",
  "deliverables": ["pptx", "html", "pdf"],
  "style": {
    "selected": "executive-minimal",
    "source": "inferred",
    "confidence": "medium"
  },
  "engine_chain": ["ppt-master", "frontend-slides"],
  "status": "PARTIAL",
  "missing_prerequisites": ["office_renderer", "chromium"]
}
```

`PARTIAL` is deliberate and truthful: this example declares that Office rendering and Chromium are unavailable. The route is usable, but those rendered/browser checks cannot be claimed. With the recommended product and style copied into the route request, the verified route is:

```json
{
  "outputs": ["pptx", "html", "pdf"],
  "engines": ["ppt-master", "frontend-slides"],
  "capabilities": {
    "ppt-master": ["native-pptx"],
    "frontend-slides": ["html-slides", "html-pdf"]
  },
  "references": [
    "native-pptx",
    "html-presenter",
    "product-retrieval",
    "qa",
    "error-system"
  ]
}
```

Expected directory convention after the selected engines actually run:

```text
<output-root>/ai-product-strategy/
├── ai-product-strategy.pptx
├── ai-product-strategy.html
├── ai-product-strategy.pdf
├── assets/
└── .temp/
```

The route does not prove that these files exist or passed QA. Final status depends on actual engine execution and the final validation loop.

#### Example 2: exact-data editable PPTX

```text
Input: quarterly-metrics.xlsx, preserving metric names, values, units, quarter order, and missing values.
Goal: a 16:9 investor metric review with native editable PowerPoint charts and tables.

Typical route: native-data-deck → ppt-master
Typical output: metrics-review.pptx
Acceptance: manifest == engine payload == observed contract, plus native-object, page-count, and rendered checks.
```

If the complete manifest, full engine payload, or post-render observed contract is absent, exact-data status is capped at `PARTIAL`.

#### Example 3: editable SVG technical architecture

```text
Input: service inventory, call directions, trust boundaries, and deployment regions.
Goal: a 16:9 technical architecture diagram for engineering documentation, delivered as SVG.

Typical route: technical-diagram → baoyu diagram
Typical output: service-architecture.svg
Acceptance: node/edge semantics, text legibility, boundaries, contrast, SVG structure, and provenance.
```

The repository also provides six binary acceptance artifacts in the two expandable sections above. They are validated by `scripts/verify_examples.py` and repository contract tests.

### Runtime and status model

| Runtime or capability | Used for | Requirement | Preflight evidence |
|---|---|---|---|
| Python 3.11+ (tested; bundled runtime preferred) | Retrieval, routing, validation, PPTX workflows | Core | `runtimes.python`, `readiness.pptx_core` |
| Resolved Node.js | Frontend Slides and Baoyu | Core for those engines | `runtimes.node`, `readiness.baoyu_core` |
| Office renderer | Native Office rendering checks | Optional | `readiness.office_renderer` |
| Chromium + Playwright | HTML/PDF export, browser measurement, QA | Optional | `readiness.chromium`, `capabilities.node.browser_qa` |
| Image-provider credentials | Generated covers, illustrations, image assets | Optional | Redacted `readiness.image_provider` |
| Optional Python/Node modules | Ingestion, narration, advanced SVG, web extraction | Optional | Per-module booleans; one missing module does not contaminate another |

Status semantics:

- `PASS`: every required command ran successfully in the current environment, required deliverables exist, and the final repaired output passed validation again.
- `PARTIAL`: a usable core result exists, but one or more requested or optional capabilities were unavailable or not executed; every limitation must be named.
- `FAIL`: a hard constraint conflicts, a required runtime is unavailable, production fails, or the quality gate remains open.

### Troubleshooting

- Do not start with bare `python`, `py`, or `node`, or trust an accidental PATH hit. Resolve and retain absolute executable paths first.
- Run `self_check.py --json` against the installed Skill root to verify files, catalogs, four engine entries, and the minimal recommendation/routing path.
- Remember that `preflight.py` emits JSON by default and has no `--json` option.
- Missing Office or Chromium capability need not fail an unrelated product, but affected rendering, PDF, or browser QA cannot be `PASS`.
- Do not install unrelated providers to hide a capability probe failure. Select a product that does not require the provider or report the limitation.
- Remove credentials, private source content, and local absolute paths from bug reports; attach only redacted preflight, self-check, version, and minimal reproduction evidence.
- Report vulnerabilities privately according to [SECURITY.md](SECURITY.md), not in a public issue.

### Development, verification, and repository map

Repository gates:

```bash
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python scripts/build_package.py
python scripts/verify_package.py
python -m unittest discover -s tests -v
```

`build_package.py` creates deterministic `dist/presentation-studio.zip`; `verify_package.py` checks the folder, catalogs, provenance, and ZIP parity. Build the Release-only checksum with the Python standard library:

```bash
python scripts/build_release_checksum.py \
  dist/presentation-studio.zip \
  presentation-studio.zip.sha256
```

Repository map:

```text
presentation-studio/
├── SKILL.md                 # Entry point, execution contract, route authority
├── catalog/                 # 13 product recipes and 8 style profiles
├── core/                    # Normalization, retrieval, data binding, routing, validation
├── engines/                 # Four upstream engines and integration adapters
├── references/              # Fast Path, dependencies, QA, routing, and operating contracts
├── scripts/                 # Skill-local preflight/recommend/route/self-check tools
└── source-lock.json         # Pinned sources, versions, licenses, import policy
examples/                    # Six verified Chinese/English PPTX, HTML, and PDF products
scripts/                     # Install, package, repository health, examples, upstream sync
tests/                       # Unit, contract, installation, rendering, and security regressions
docs/                        # Architecture, sync operations, designs, plans, acceptance evidence
```

Read-only upstream check:

```bash
python scripts/upstream_sync.py check --json
```

Maintainer synchronization:

```bash
python scripts/upstream_sync.py sync --all \
  --report artifacts/upstream-sync-report.json
```

Automation supports upstream events, `workflow_dispatch`, and an hourly schedule fallback at minute 17. It opens or updates a dedicated synchronization PR only after stable-version, source, allowlist, license, and full repository checks pass. See the [upstream synchronization guide](docs/upstream-sync.md) and [acceptance evidence](docs/evidence/acceptance-2026-08-13.md).

## Credits, licensing, and participation

Presentation Studio integrates four upstream specialties:

- [PPT Master](https://github.com/hugohe3/ppt-master) for native editable PowerPoint production;
- [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) for Swiss/editorial design and presentation narrative;
- [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) for standalone HTML presentations and browser/PDF delivery;
- [Baoyu Skills](https://github.com/JimLiu/baoyu-skills) for covers, illustrations, infographics, diagrams, and image-led slides.

Presentation Studio is licensed under [AGPL-3.0](LICENSE). Vendored components retain their original licenses and notices. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [CONTRIBUTORS.md](CONTRIBUTORS.md), `presentation-studio/source-lock.json`, and `presentation-studio/engines/*/LICENSE*`.

Contributions follow the verified workflow in [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately under [SECURITY.md](SECURITY.md), and follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

The integration adds the product catalog, style catalog, Fast Path, preflight, exact-data contracts, routing, safety boundaries, acceptance semantics, deterministic packaging, and protected upstream synchronization around the four upstream projects. It does not replace or obscure their authorship.
