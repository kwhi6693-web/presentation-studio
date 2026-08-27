# Presentation Studio

> 面向兼容 Agent 的演示文稿与视觉生产 Skill：支持可编辑 PPTX、HTML 幻灯片、PDF、视觉素材、精准数据路由与渲染验收。

[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5)](presentation-studio/catalog/styles.json)

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

## 项目定位

Presentation Studio 将自然语言 brief、精准数据和已有素材，转化为可解释的产品选择与引擎路由。它的核心 Skill contract 在实现允许的范围内与宿主无关：Agent/Harness 提供本地运行时能力，Skill 提供目录驱动的产品路由、数据契约、原生生成边界、溯源记录和渲染质量门禁。

核心流程：

~~~
brief + 数据 + 素材
        → 规范化与 preflight
        → 从本地 Catalog 检索产品与风格
        → 路由到单一引擎或混合引擎链
        → 生成原生/可编辑输出
        → 校验、渲染、逐页检查、修复、再次校验
        → 交付文件、证据与能力限制
~~~

当前仓库包含 13 个产品配方、8 个风格配置和 4 个集成上游引擎。输出类型包括 PPTX、HTML、PDF、PNG 和 SVG，实际可用范围取决于产品与宿主能力。

## 能力分层

| 能力层 | 实际覆盖 | 结果 |
|---|---|---|
| 意图与产品决策 | brief 规范化、preflight、13 产品检索、风格推断、冲突识别 | 可解释的产品/风格选择 |
| 数据契约与路由 | 精准数据 manifest、类型/顺序/单位保护、单引擎与混合路由 | 可审计的引擎计划 |
| 内容与视觉生产 | 叙事、布局、图表、封面、插图、信息图、示意图 | 内容与素材计划 |
| 多格式原生生成 | 可编辑 PPTX、独立 HTML、PDF、PNG、SVG、演示者导航 | 原生或可发布文件 |
| 渲染验收与修复 | 溢出、碰撞、字体、对比度、页数、交互、打印、离线行为 | 经过质量门禁的结果 |
| 安全、溯源与状态 | 不可信内容边界、凭据保护、许可证/来源记录、路由状态 | 可复现的证据 |
| 上游持续同步 | 稳定版本发现、白名单导入、许可证检查、验证后同步 PR | 可维护的集成 |

完整的 L0-L19 职责图见[架构说明](docs/architecture.md)。

## 产品、输出与引擎

源数据是 products.json。以下是 13 个产品配方的公共索引。

| 产品 | 典型用途 | 输出 | 引擎链 |
|---|---|---|---|
| native-editable-deck | 通用汇报与业务更新 | PPTX | ppt-master |
| native-data-deck | 财务报告与指标复盘 | PPTX | ppt-master |
| swiss-editorial-deck | Swiss/editorial 策略或年度叙事 | PPTX、HTML | guizang → ppt-master → frontend-slides |
| executive-deck | 董事会、投资人与决策简报 | PPTX | ppt-master |
| technical-deck | 架构与工程评审 | PPTX | ppt-master |
| html-presenter | 单文件 Web 演示与演示者模式 | HTML、PDF | guizang → frontend-slides |
| dual-format-deck | 会议与 Web 共用内容 | PPTX、HTML、PDF | ppt-master → frontend-slides |
| cover-image | 文章、演示与社交媒体封面 | PNG | baoyu |
| article-illustration | 编辑插图与概念视觉 | PNG | baoyu |
| infographic-image | 数据摘要与对比信息图 | PNG | baoyu |
| technical-diagram | 架构、系统与流程图 | SVG | baoyu |
| data-image | 指标视觉与图表图片 | PNG | baoyu |
| image-slide-deck | 图片主导的叙事演示 | 带图片页面的 PPTX | baoyu → ppt-master |

| 引擎 | 适用范围 | 边界 |
|---|---|---|
| [PPT Master](https://github.com/hugohe3/ppt-master) | 原生 PPTX、图表、表格、备注、动画与模板 | 负责 PowerPoint 原生对象；Office 渲染另行检查 |
| [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) | Swiss/editorial 设计系统、叙事与版式 | 提供设计权威，最终文件由所选渲染器生成 |
| [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) | 独立 HTML、键盘导航、演示者行为、HTML 转 PDF | 浏览器/PDF QA 需要 Chromium/Playwright |
| [Baoyu Skills](https://github.com/JimLiu/baoyu-skills) | 封面、插图、信息图、示意图、数据图片与图片页 | Provider 图像是可选能力；SVG 示意图不是原生 PowerPoint 对象 |

## 兼容性模型

### 设计支持与已验证分开记录

下面的兼容性矩阵是当前宿主证据的公开来源。

Skill contract 和核心逻辑面向能够提供所需本地能力的兼容 Agent/Harness 设计。“设计支持”描述架构和契约目标；只有当前验证证据实际执行过的宿主/route 才能写“已验证”。

| 宿主 / Agent 能力 | Skill contract | 核心路由 | 本地脚本 | 原生生成 | 渲染 QA | 验证状态 |
|---|---|---|---|---|---|---|
| Codex | Supported | Supported | Supported | 取决于能力 | 取决于运行时 | 已验证当前主机上的核心/包契约；可选渲染器与 Provider route 另行报告 |
| 其他具备能力的 Agent / Harness | Designed | Designed | 需要本地运行时 | 取决于宿主 | 取决于运行时 | 已按能力设计，本次未独立验证 |

这不是“所有 Agent 都支持”的声明。应按具体 route 与能力判断。例如宿主有 Python 和原生 PPTX 核心，但没有 Chromium 或 image provider 时：

| Route | 结果 | 含义 |
|---|---|---|
| 原生 PPTX 生成 | 所需引擎路径成功时为 PASS | 缺少浏览器不会自动否定 PPTX route |
| HTML 渲染 QA / HTML 转 PDF | PARTIAL 或 未执行 | 受影响检查需要 Chromium/Playwright |
| Provider 图像生成 | 不可用 | 未配置 Provider，应选择非 Provider route 或报告限制 |
| 必需运行时缺失或硬约束冲突 | FAIL | 选定 route 无法满足必需契约 |

PASS、PARTIAL、FAIL 是 route 结果；NOT AVAILABLE（不可用）和 NOT EXECUTED（未执行）用于明确能力缺口，不能被解释为整个 Skill 不兼容。

presentation-studio/agents/openai.yaml 是可选的 OpenAI/Codex 宿主描述文件，不是核心 Skill 必需项。上游 Baoyu 中可能存在可选的 baoyu-codex-imagegen 适配器；Provider 与 Codex CLI 都只属于可选上游能力路径。

## 快速路径与完整路径

快速路径使用已经可用的原生 PPTX route：选择产品，提供所需 payload，运行对应本地脚本，并检查生成的可编辑文件。完整路径还会加入环境预检、精准数据校验、所选输出格式的渲染 QA、包校验和证据报告。当交付物需要公开发布，或验收条件包含渲染器、浏览器、Office 或图像 Provider 时，应使用完整路径。

## 能力限制

Presentation Studio 按 route 报告限制。缺少 Chromium、Office 渲染器或 Provider 图像服务，可能使 HTML/PDF 或 Provider route 处于 PARTIAL、NOT AVAILABLE 或 NOT EXECUTED；这不妨碍原生 PPTX route 单独通过。除非实际执行过相关 route 并保留证据，否则不应把宿主描述为“已完整验证”。

## 安装

安装目录由宿主决定。agents/skills/presentation-studio 是随附安装脚本使用的一种常见约定，不是所有 Agent 的统一目录；其他 Agent/Harness 应按照自身的发现/导入机制放置 Skill。

### Release 包

从同一个[最新 Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) 下载 presentation-studio.zip 和 presentation-studio.zip.sha256，解压前校验：

~~~
sha256sum -c presentation-studio.zip.sha256
~~~

Windows PowerShell：

~~~
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 不匹配" }
"OK: $actual"
~~~

解压后应只有一个 presentation-studio/ Skill 根目录。使用明确的绝对 Python 和 Node 路径运行 self-check：

~~~
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
~~~

### 源码安装

Windows PowerShell：

~~~
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1 -PythonExecutable C:\path\to\python.exe -NodeExecutable C:\path\to\node.exe
~~~

Linux 或 macOS：

~~~
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
PRESENTATION_STUDIO_PYTHON=/absolute/path/to/python PRESENTATION_STUDIO_NODE=/absolute/path/to/node ./scripts/install.sh
~~~

两个安装脚本都会先在 Skill 发现目录之外暂存、执行真实 self-check，再替换旧安装。强制更新会把旧版本放到所选发现目录旁的 agents/skill-backups/。安装后请重新加载宿主 Agent/Harness 的 Skill registry。

### 运行时解析

通用 resolver 支持：

- PRESENTATION_STUDIO_RUNTIME_ROOT，并使用 dependencies/python/python.exe、dependencies/node/bin/node.exe、dependencies/native/git/cmd/git.exe；或
- PRESENTATION_STUDIO_PYTHON、PRESENTATION_STUDIO_NODE、PRESENTATION_STUDIO_GIT 三个明确的绝对文件路径。

它会拒绝 WindowsApps alias，也不会把偶然的 PATH 命中当作运行时证据。没有通用配置时，可回退到当前 Codex App bundle，并在结果中明确标记为 Codex 适配器；其他宿主不需要依赖这个回退。详见[依赖与可移植性契约](presentation-studio/references/dependencies.md)。

## 使用

用自然语言说明目标，并提供主题、目的、受众、源材料或精准数据、输出格式、可编辑性、视觉方向、页数/比例与 QA 要求。

~~~
为董事会制作一份 16:9 的 AI 产品战略演示。
交付原生可编辑 PPTX、独立 HTML 和 PDF。
使用提供的季度指标，不得改变任何数值、单位、行顺序或缺失值。
PPTX 中的图表与表格必须可编辑；交付前检查每页的溢出、对比度、数据保真、备注、
离线行为以及浏览器/PDF 准备情况，并报告 PASS/PARTIAL/FAIL。
~~~

需要诊断路由时，先运行 preflight，再运行推荐和 route：

~~~
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
python presentation-studio/scripts/recommend.py --json-file request.json
python presentation-studio/scripts/route.py --json-file route-request.json
~~~

preflight.py 默认输出 JSON，不接受 --json。readiness 必须来自当前脱敏 preflight；router 会保留显式的产品/风格约束并报告冲突，不会静默替换。

## 精准数据与可编辑性

精准数据任务必须有已校验的 manifest、完整的所选引擎 payload，以及渲染后的 observed contract，并对三者进行比较。缺失值、重复值、长度不一致或 observed contract 不完整时，数据结果最高只能是 PARTIAL。

需要原生可编辑时，图表、表格、文本和形状应使用 PowerPoint 原生对象。不能用整页截图替代可编辑 deck；图片主导产品仍应准确描述为图片主导，而不是对象可编辑的 PPTX。

## QA 与状态

质量闭环为：

~~~
validate → render → inspect every page → repair → validate again
~~~

按产品检查叙事、溢出、碰撞、边距、层级、字号、对比度、裁切、图表完整性、可编辑性、备注、键盘行为、打印/离线行为、页数和溯源。

- PASS：当前环境中所有必需命令和适用质量检查均成功，修复后的结果再次通过。
- PARTIAL：核心结果可用，但某个请求的或可选能力不可用/未执行；必须指出受影响的 route 与证据缺口。
- FAIL：硬约束冲突、必需运行时缺失、生产失败或必需质量门禁未关闭。
- NOT AVAILABLE：宿主没有提供某项能力，例如 image provider。
- NOT EXECUTED：适用检查尚未执行，不能算通过。

详见 [qa.md](presentation-studio/references/qa.md) 与 [error-system.md](presentation-studio/references/error-system.md)。

## 示例

仓库内六个文件是验收 fixture，用于验证仓库契约。scripts/verify_examples.py 会做结构化检查；fixture 通过不代表每个宿主都已重新执行所有可选渲染器或 Provider。

<details>
<summary>中英文验收文件</summary>

- [English PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx)
- [English HTML](examples/bilingual-acceptance/en/presentation-acceptance-en.html)
- [English PDF](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)
- [中文 PPTX](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx)
- [中文 HTML](examples/bilingual-acceptance/zh/presentation-acceptance-zh.html)
- [中文 PDF](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf)

</details>

<details>
<summary>fixture 覆盖范围</summary>

每份 deck 有 5 页，并检查语言标记、原生图表/表格/备注、HTML 键盘/打印/离线行为和 PDF 页面尺寸等声明契约。运行 python scripts/verify_examples.py 查看当前结构化结果。

</details>

## 开发与验证

在源码目录中使用已解析的绝对 Python 路径（如有需要）运行：

~~~
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python -m unittest discover -s tests -v
python scripts/build_package.py
python scripts/verify_package.py
python scripts/upstream_sync.py check --json
git diff --check
~~~

build_package.py 生成确定性的 dist/presentation-studio.zip。[checksums.sha256](checksums.sha256) 面向源码仓库中的这个构建产物；Release 旁的 presentation-studio.zip.sha256 是另一份契约，不能混用。

## 上游同步

scripts/upstream_sync.py check --json 是只读检查。维护工作流支持仓库事件、手动触发与每小时定时兜底；只有稳定版本、来源、白名单、许可证和完整仓库检查通过后，才会创建或更新专用同步 PR。详见[上游同步说明](docs/upstream-sync.md)和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安全、许可证与参与

不要在 issue 或日志中提交凭据、私有源内容或未脱敏的本地路径。漏洞请按 [SECURITY.md](SECURITY.md) 私下报告。贡献请遵守 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

Presentation Studio 采用 [AGPL-3.0](LICENSE)。上游引擎保留原许可证与声明；详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)、[CONTRIBUTORS.md](CONTRIBUTORS.md)、[source-lock.json](presentation-studio/source-lock.json) 和各引擎许可证文件。

## 发布与贡献

Release 候选版本应在 Pull Request 中通过仓库健康度、示例、包、安全以及适用的渲染 QA 检查。受保护的 `main` 分支及其必需检查是集成边界；本地构建或尚未合并的分支不等于公开 Release。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
