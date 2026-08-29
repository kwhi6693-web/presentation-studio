# Presentation Studio

> 讓 AI Agent 把提示詞和結構化資料轉成高品質、可編輯的 PPTX、HTML 演示與視覺內容。

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

[![最新 Release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-capability--based-2f855a?style=flat-square)](#相容性模型)
[![驗證套件](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg?branch=main&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![同步上游](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg?branch=main&style=flat-square)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a?style=flat-square)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5?style=flat-square)](presentation-studio/catalog/styles.json)
[![授權：AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg?style=flat-square)](LICENSE)

![Presentation Studio 展示：編輯型投影片、圖表與視覺版面](presentation-studio/engines/guizang/assets/ppt-skill-showcase.png)

## 為什麼使用 Presentation Studio

從 brief、結構化資料或既有素材開始。Presentation Studio 會選擇產品與引擎路由，明確保留資料契約，並在交付前檢查輸出。

| 可編輯 PPTX | 多格式輸出 | Agent 適配 | 品質門禁 |
|---|---|---|---|
| 在所選 route 支援時，使用原生文字、圖表、表格與形狀 | 支援 PPTX、HTML、PDF、PNG 與 SVG 路徑 | 基於 Catalog 的選擇會適配執行時實際可用的宿主能力 | 驗證、渲染、檢查、修復，再次驗證 |

## 展示案例

以下案例代表常見的簡報路線。標記為 **驗收 fixture** 的連結是儲存庫內可驗證的契約輸出；它們不被描述為生產基準，也不是生成式產品 Demo 的截圖。

| 案例 | Prompt | 預覽 / 輸出 | 引擎 / route 與可編輯性 |
|---|---|---|---|
| **AI 產業報告** | 「把產業 brief 轉成一份簡潔的 16:9 高階主管報告，並提供可編輯的摘要頁。」 | [英文 PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx) · [PDF 預覽](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)（驗收 fixture） | `executive-deck` → `ppt-master`；原生可編輯 PPTX 路徑 |
| **財務 / 資料報告** | 「使用提供的指標，不改變數值、單位、順序或缺失值；交付可編輯圖表與表格。」 | [英文 PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx) · [HTML](examples/bilingual-acceptance/en/presentation-acceptance-en.html)（驗收 fixture） | `native-data-deck` → `ppt-master`；原生圖表與表格 |
| **Swiss Editorial Deck** | 「以克制的排版、清晰的字體層級和編輯式節奏完成策略敘事，並提供適合 Web 閱讀的版本。」 | [現有 Swiss 視覺素材](presentation-studio/engines/guizang/assets/ppt-skill-showcase.png) | `swiss-editorial-deck` → `guizang` → `ppt-master` → `frontend-slides`；PPTX 可編輯性取決於 route，HTML 是發布型輸出 |
| **技術架構** | 「說清楚系統邊界、資料流與運行模型，形成適合評審的架構簡報。」 | [架構說明](docs/architecture.md) · [圖示參考](presentation-studio/references/diagrams-infographics.md) | `technical-deck` → `ppt-master` 生成可編輯 PPTX，或 `technical-diagram` → `baoyu` 生成可編輯 SVG |

儲存庫目前提供的是契約 fixture 與引擎參考視覺素材，而不是四套領域生產成品。這樣可以保持展示真實，同時明確每條路線的目標、輸出和可編輯性邊界。

## 快速開始

1. 下載[最新 Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest)，並使用對應的 `.sha256` 檔案校驗 `presentation-studio.zip`。
2. 解壓得到唯一的 `presentation-studio/` Skill 根目錄，並讓你的 Agent/Harness 發現它。
3. 從下面這樣的 brief 開始：

```text
根據提供的季度 CSV 製作一份 16:9 財務報告。
返回可編輯 PPTX，保留所有數值和單位，並在交付前檢查圖表、表格、溢出和資料保真度。
```

完整的[安裝](#安裝)、[使用](#使用)和按能力劃分的驗證說明見下文。

下面繼續保留面向實作與維護的工程模型、相容性邊界和驗證契約。

## 🧭 專案概覽

Presentation Studio 將自然語言 brief、精準資料與既有素材，轉換為可解釋的產品選擇與引擎路由。核心 Skill contract 在實作允許的範圍內保持與宿主無關：Agent/Harness 提供執行時能力，Presentation Studio 提供目錄驅動路由、資料契約、原生生成邊界、溯源紀錄與渲染品質門禁。

| 快速了解 | 目前契約 |
|---|---|
| 產品目錄 | 13 個產品配方與 8 個風格設定 |
| 整合引擎 | 4 個上游引擎，並透過白名單同步 |
| 輸出類型 | PPTX、HTML、PDF、PNG、SVG |
| 品質模型 | 驗證 → 渲染 → 檢查 → 修復 → 再次驗證 |
| 相容性模型 | 基於能力；分開記錄設計支援與已驗證狀態 |

## 💡 解決什麼問題？

從 brief 到最終檔案的過程中，簡報工作經常遺失資料保真度、可編輯性、視覺一致性或驗證證據。單一 prompt 也無法自動知道宿主是否提供 Python、Node、Chromium、Office 渲染或圖像 Provider。

Presentation Studio 將這些決策明確化：

- 正規化 brief 並執行宿主 preflight；
- 從本機 Catalog 檢索產品與風格；
- 路由至單一引擎或混合引擎鏈；
- 產生原生或可發布輸出；
- 回報 route 結果、檔案、證據與能力邊界。

## ✨ 核心能力

| 能力層 | 實際涵蓋 | 結果 |
|---|---|---|
| 意圖與產品決策 | brief 正規化、preflight、13 個產品檢索、風格推論、衝突識別 | 可解釋的產品/風格選擇 |
| 資料契約與路由 | 精準資料 manifest、型別/順序/單位保護、單引擎與混合路由 | 可稽核的引擎計畫 |
| 內容與視覺製作 | 敘事、版面、圖表、封面、插圖、資訊圖、示意圖 | 內容與素材計畫 |
| 多格式原生生成 | 可編輯 PPTX、獨立 HTML、PDF、PNG、SVG、簡報者導覽 | 原生或可發布檔案 |
| 渲染驗收與修復 | 溢出、碰撞、字型、對比、頁數、互動、列印、離線行為 | 通過品質門禁的結果 |
| 安全、溯源與狀態 | 不可信內容邊界、憑證保護、授權/來源紀錄、route 狀態 | 可重現的證據 |
| 上游持續同步 | 穩定版本發現、白名單匯入、授權檢查、驗證後同步 PR | 可維護的整合 |

完整 L0-L19 職責圖請見[架構說明](docs/architecture.md)。

## 🧩 產品、輸出與引擎

產品目錄的來源資料是 [products.json](presentation-studio/catalog/products.json)。公共索引包含 13 個產品配方：

| 產品 | 典型用途 | 輸出 | 引擎鏈 |
|---|---|---|---|
| native-editable-deck | 通用簡報與業務更新 | PPTX | ppt-master |
| native-data-deck | 財務報告與指標檢視 | PPTX | ppt-master |
| swiss-editorial-deck | Swiss/editorial 策略或年度敘事 | PPTX、HTML | guizang → ppt-master → frontend-slides |
| executive-deck | 董事會、投資人與決策簡報 | PPTX | ppt-master |
| technical-deck | 架構與工程評審 | PPTX | ppt-master |
| html-presenter | 單檔 Web 簡報與簡報者模式 | HTML、PDF | guizang → frontend-slides |
| dual-format-deck | 會議與 Web 共用內容 | PPTX、HTML、PDF | ppt-master → frontend-slides |
| cover-image | 文章、簡報與社群封面 | PNG | baoyu |
| article-illustration | 編輯插圖與概念視覺 | PNG | baoyu |
| infographic-image | 資料摘要與比較資訊圖 | PNG | baoyu |
| technical-diagram | 架構、系統與流程圖 | SVG | baoyu |
| data-image | 指標視覺與圖表圖片 | PNG | baoyu |
| image-slide-deck | 圖片主導的敘事簡報 | 含圖片頁面的 PPTX | baoyu → ppt-master |

| 引擎 | 適用範圍 | 邊界 |
|---|---|---|
| [PPT Master](https://github.com/hugohe3/ppt-master) | 原生 PPTX、圖表、表格、備註、動畫與範本 | 負責 PowerPoint 原生物件；Office 渲染另行檢查 |
| [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) | Swiss/editorial 設計系統、敘事與版面 | 提供設計權威，最終檔案由所選渲染器產生 |
| [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) | 獨立 HTML、鍵盤導覽、簡報者行為、HTML 轉 PDF | 瀏覽器/PDF QA 需要已解析的 Chromium/Playwright 能力 |
| [Baoyu Skills](https://github.com/JimLiu/baoyu-skills) | 封面、插圖、資訊圖、示意圖、資料圖片與圖片投影片 | Provider 圖像是可選能力；SVG 示意圖不是原生 PowerPoint 物件 |

## 🔍 相容性模型

### 設計支援與已驗證

下面的**相容性矩陣**是目前宿主證據的公開來源。

Skill contract 與核心邏輯是為能提供所需本機能力的相容 Agent/Harness 設計。「設計支援」描述架構與契約目標；「已驗證」只用於目前驗證證據實際執行過的宿主/route。

| 宿主 / Agent 能力 | Skill contract | 核心路由 | 本機腳本 | 原生生成 | 渲染 QA | 驗證狀態 |
|---|---|---|---|---|---|---|
| Codex | Supported | Supported | Supported | 取決於能力 | 取決於執行時 | 已驗證目前主機上的核心/套件契約；可選渲染器與 Provider route 另行報告 |
| 其他具備能力的 Agent / Harness | Designed | Designed | 需要本機執行時 | 取決於宿主 | 取決於執行時 | 依能力設計，本次未獨立驗證 |

這不是「所有 Agent 都支援」的聲明。應依具體 route 與能力判斷。例如宿主有 Python 與原生 PPTX 核心，但沒有 Chromium 或 image provider 時：

| Route | 結果 | 意義 |
|---|---|---|
| 原生 PPTX 生成 | 所需引擎路徑成功時為 PASS | 缺少瀏覽器本身不會否定 PPTX route |
| HTML 渲染 QA / HTML 轉 PDF | PARTIAL 或 NOT EXECUTED | 受影響的檢查需要 Chromium/Playwright |
| Provider 圖像生成 | NOT AVAILABLE | 未設定 Provider，應選擇非 Provider route 或回報限制 |
| 必需執行時缺失或硬約束衝突 | FAIL | 選定 route 無法滿足必需契約 |

PASS、PARTIAL、FAIL 是 route 結果；NOT AVAILABLE 與 NOT EXECUTED 用來明確表達能力缺口，不能被解讀為整個 Skill 不相容。

`presentation-studio/agents/openai.yaml` 是可選的 OpenAI/Codex 宿主描述檔，不是核心 Skill 必需項。上游 Baoyu 可能包含可選的 `baoyu-codex-imagegen` 適配器；Provider 與 Codex CLI 都只是可選的上游能力路徑。

## 🎯 範圍與保證

先使用滿足目標輸出的最小 route；當交付物或驗收條件需要時，再擴展驗證範圍。

| Route | 提供內容 | 不代表 |
|---|---|---|
| 快速原生路徑 | 產品選擇、payload 準備、本機生成與可編輯 PPTX route 檢查 | 不會自動證明瀏覽器、Office、Provider 或渲染 PDF 行為 |
| 完整路徑 | 環境 preflight、精準資料驗證、渲染 QA、套件驗證與證據報告 | 仍會回報宿主不可用或未執行的能力 |
| 圖片主導產品 | 圖片敘事或視覺素材，包括 PNG/SVG 輸出 | 不能把圖片主導的 deck 描述為物件可編輯 deck |

原生/可編輯邊界如下：

| 輸出類型 | 邊界 |
|---|---|
| PPTX | 要求可編輯時，圖表、表格、文字與形狀應使用原生 PowerPoint 物件；Office 渲染單獨檢查 |
| HTML | 獨立檔案可以提供鍵盤導覽與簡報者行為；瀏覽器/PDF 準備度取決於 Chromium/Playwright |
| PDF | 可發布輸出取決於所選渲染器及頁面尺寸/渲染檢查 |
| PNG / SVG | 視覺素材是原生圖像/向量輸出；SVG 示意圖不是原生 PowerPoint 物件 |

## 📐 精準資料與可編輯性

精準資料任務需要三份可比較的紀錄：

| 紀錄 | 契約 |
|---|---|
| 已驗證 manifest | 宣告來源資料的數值、型別、單位、順序、重複項與缺失值 |
| 所選引擎 payload | 將完整資料契約帶入路由後的引擎 |
| 渲染後的 observed contract | 確認最終渲染交付物實際包含的內容 |

在把資料結果標為 PASS 前，必須比較這三份紀錄。缺失值、重複值、長度不一致或 observed contract 不完整時，結果最高只能是 PARTIAL。

需要原生可編輯時，圖表、表格、文字與形狀應使用原生 PowerPoint 物件。不能用整頁截圖取代可編輯 deck；圖片主導產品仍應準確描述為圖片主導，而不是物件可編輯的 deck。

## 📋 執行要求

宿主 Agent/Harness 提供能力；Skill 回報每條 route 實際能使用什麼。

| 能力 | 用於 | 不可用時 |
|---|---|---|
| 視覺理解 | brief 解讀、基於來源的構圖與視覺檢查 | 相關視覺 route 可能為 PARTIAL 或 NOT EXECUTED |
| 本機檔案系統存取 | 讀取輸入、執行本機腳本、收集檔案 | 本機生成或驗證無法執行 |
| Python 3.10+ | preflight、驗證、打包與 Python 引擎步驟 | 相關 route 不符合執行時要求 |
| Node.js | Node 引擎與 HTML 工具 | 依賴 Node 的 route 不可用 |
| Git | 原始碼檢出、溯源與上游同步 | 原始碼/更新流程受限 |
| Chromium / Playwright | 瀏覽器行為、HTML 渲染與 HTML 轉 PDF QA | HTML/PDF QA 為 PARTIAL 或 NOT EXECUTED |
| Office 渲染器 | PPTX 渲染檢查 | 仍可產生原生 PPTX，但沒有 Office 渲染證據 |
| Image provider | Provider 圖像生成 | Provider route 為 NOT AVAILABLE，應選擇其他 route |

## 📦 安裝

安裝目錄由宿主決定。`.agents/skills/presentation-studio` 是隨附安裝腳本使用的一種常見約定，不是所有 Agent 的統一目錄；其他 Agent/Harness 應依自身的發現/匯入契約放置 Skill。

### Release 套件

從同一個[最新 Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) 下載 `presentation-studio.zip` 與 `presentation-studio.zip.sha256`，解壓前先驗證：

```sh
sha256sum -c presentation-studio.zip.sha256
```

Windows PowerShell：

```powershell
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 不相符" }
"OK: $actual"
```

解壓後應只有一個 `presentation-studio/` Skill 根目錄。使用明確的絕對 Python 與 Node 路徑執行 self-check：

```sh
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
```

### 原始碼安裝

Windows PowerShell：

```powershell
git clone https://github.com/kwhi6693-web/presentation-studio.git
Set-Location presentation-studio
.\scripts\install.ps1 -PythonExecutable C:\path\to\python.exe -NodeExecutable C:\path\to\node.exe
```

Linux 或 macOS：

```sh
git clone https://github.com/kwhi6693-web/presentation-studio.git
cd presentation-studio
PRESENTATION_STUDIO_PYTHON=/absolute/path/to/python PRESENTATION_STUDIO_NODE=/absolute/path/to/node PRESENTATION_STUDIO_GIT=/absolute/path/to/git ./scripts/install.sh
```

兩個安裝腳本都會先在 Skill 發現目錄外暫存、執行真實 self-check，再替換舊安裝。強制更新會把舊版本放在所選發現目錄旁的 `.agents/skill-backups/`。安裝後請重新載入宿主 Agent/Harness 的 Skill registry。

### 執行時解析

通用 resolver 支援：

- `PRESENTATION_STUDIO_RUNTIME_ROOT`，並使用 `dependencies/python/python.exe`、`dependencies/node/bin/node.exe` 與 `dependencies/native/git/cmd/git.exe`；或
- `PRESENTATION_STUDIO_PYTHON`、`PRESENTATION_STUDIO_NODE` 與 `PRESENTATION_STUDIO_GIT` 三個明確的絕對檔案路徑。

它會拒絕 WindowsApps alias，也不會把偶然的 PATH 命中當作執行時證據。沒有通用設定時，resolver 可以回退到目前 Codex App bundle，並在結果中明確標記為相容性 fallback；其他宿主不需要依賴這個回退。詳見[依賴與可攜性契約](presentation-studio/references/dependencies.md)。

## 🚀 使用

以自然語言描述目標，並提供主題、目的、受眾、來源材料或精準資料、輸出格式、可編輯性、視覺方向、頁數/比例與 QA 要求。

```text
為董事會製作一份 16:9 的 AI 產品策略簡報。
交付原生可編輯 PPTX、獨立 HTML 與 PDF。
使用提供的季度指標，不得改變任何數值、單位、列順序或缺失值。
PPTX 中的圖表與表格必須可編輯；交付前檢查每頁的溢出、對比度、資料保真、備註、
離線行為以及瀏覽器/PDF 準備情況，並回報 PASS/PARTIAL/FAIL。
```

需要診斷路由時，先執行 preflight，再執行推薦與 route：

```sh
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
python presentation-studio/scripts/recommend.py --json-file request.json
python presentation-studio/scripts/route.py --json-file route-request.json
```

`preflight.py` 預設輸出 JSON，不接受 `--json`。readiness 布林值必須來自目前脫敏的 preflight 結果。router 會保留明確的產品/風格約束並回報衝突，不會靜默替換。

## 🖼️ 輸入 → 輸出

```text
brief + 資料 + 素材
        → 正規化與 preflight
        → 從本機 Catalog 檢索產品與風格
        → 路由至單一引擎或混合引擎鏈
        → 產生原生/可編輯輸出
        → 驗證、渲染、檢查、修復、再次驗證
        → 交付檔案、證據與能力限制
```

| 輸入 | 決策層 | 輸出 |
|---|---|---|
| Brief、受眾、目的、約束 | 產品/風格檢索與衝突識別 | 可解釋的 route 計畫 |
| 精準資料與既有素材 | manifest、型別/順序/單位校驗、溯源 | 原生或視覺交付物 |
| 宿主能力報告 | 引擎選擇與渲染 QA 門禁 | 帶證據的 PASS / PARTIAL / FAIL |

## 🎞️ 真實範例

以下六個儲存庫內檔案是真實驗收 fixture，用於驗證儲存庫契約。它們由 `scripts/verify_examples.py` 進行結構化驗證；fixture 通過不代表每個宿主都重新執行了所有可選渲染器或 Provider。

| Fixture 集合 | 交付物 | 涵蓋內容 |
|---|---|---|
| English acceptance | PPTX、HTML、PDF | 語言身份、原生圖表/表格/備註、HTML 行為、PDF 頁面尺寸 |
| Chinese acceptance | PPTX、HTML、PDF | 語言身份、原生圖表/表格/備註、HTML 行為、PDF 頁面尺寸 |

<details>
<summary>驗收檔案</summary>

- [English PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx)
- [English HTML](examples/bilingual-acceptance/en/presentation-acceptance-en.html)
- [English PDF](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)
- [中文 PPTX](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx)
- [中文 HTML](examples/bilingual-acceptance/zh/presentation-acceptance-zh.html)
- [中文 PDF](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf)

</details>

<details>
<summary>Fixture 涵蓋範圍</summary>

每份 deck 有 5 頁，並檢查語言標記、原生圖表/表格/備註、HTML 鍵盤/列印/離線行為與 PDF 頁面尺寸等契約。執行 `python scripts/verify_examples.py` 查看目前結構化結果。

</details>

## ⚙️ 工作方式

1. **Preflight** — 解析宿主實際的 Python、Node、Git、瀏覽器、Office 與 Provider 能力。
2. **目錄選擇** — 從本機來源資料檢索產品配方與風格設定。
3. **精準資料契約** — 透過所選引擎 payload 保留數值、型別、單位、順序、重複項與缺失值。
4. **引擎路由** — 選擇原生引擎或混合鏈；遇到硬衝突時回報，不靜默替換。
5. **生成** — 建立可編輯 PPTX 物件，或所選 HTML/PDF/PNG/SVG 輸出。
6. **品質門禁** — 驗證、渲染、檢查所有適用頁面，依規則進行一次修復，再次驗證並回報證據邊界。

完整編排與職責圖見 [docs/architecture.md](docs/architecture.md)，上游維護契約見 [docs/upstream-sync.md](docs/upstream-sync.md)。

## ✅ 驗證

品質閉環為：

```text
validate → render → inspect every page → repair → validate again
```

依所選 route 檢查敘事、溢出、碰撞、邊距、層級、字級、對比度、裁切、圖表完整性、可編輯性、備註、鍵盤行為、列印/離線行為、頁數與溯源。

| 狀態 | 意義 |
|---|---|
| PASS | 所有必需命令與適用品質檢查均成功，修復後的交付物再次通過。 |
| PARTIAL | 核心結果可用，但某個請求的或可選能力不可用/未執行；必須指出受影響 route 與證據缺口。 |
| FAIL | 硬約束衝突、必需執行時缺失、生成失敗或必需品質門禁尚未關閉。 |
| NOT AVAILABLE | 宿主沒有提供某項能力，例如 image provider。 |
| NOT EXECUTED | 適用檢查尚未執行，不能視為通過。 |

## 🛠️ 開發與驗證

在原始碼目錄中使用已解析的絕對 Python 路徑（如需要）執行：

```sh
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python -m unittest discover -s tests -v
python scripts/verify_package.py
python scripts/upstream_sync.py check --json
git diff --check
```

`build_package.py` 會產生確定性的 `dist/presentation-studio.zip`；只有在明確重建原始碼套件時才執行它。上游同步 CI 會把明確的 `--archive` 與 `--checksum` 路徑指向 Runner 暫存目錄，執行兩次建置並驗證一致性，普通原始碼 PR 不會攜帶生成產物。[checksums.sha256](checksums.sha256) 面向原始碼儲存庫中的這個建置基線；正式 Release 會在發布 ZIP 旁生成 `presentation-studio.zip.sha256`，兩者屬於不同契約。

## ⚠️ 已知限制

- 宿主決定實際可用的引擎、渲染器、瀏覽器、Office 安裝與圖像 Provider。
- 缺少 Chromium、Office 渲染器或 Provider 圖像服務，可能使 HTML/PDF 或 Provider route 處於 PARTIAL、NOT AVAILABLE 或 NOT EXECUTED；原生 PPTX route 仍可能單獨通過。
- 除非實際執行過相關 route 並保留證據，否則不能把宿主稱為「已完整驗證」。
- 精準資料結果需要已驗證 manifest、完整的所選引擎 payload 與渲染後的 observed contract；缺失值、重複值、長度不一致或 observed contract 不完整時，資料結果最高只能是 PARTIAL。
- 原生可編輯性適用於原生 PowerPoint 物件。不能把整頁截圖描述為可編輯的圖表、表格、文字或形狀。
- 公共 fixture 驗證儲存庫結構與宣告契約，不取代針對具體 route 的視覺、瀏覽器、Office、Provider 或跨 Agent 驗證。

詳見 [qa.md](presentation-studio/references/qa.md) 與 [error-system.md](presentation-studio/references/error-system.md)。

## 🛡️ 安全與溯源

不要在 issue、prompt 或日誌中提交憑證、私有來源內容或未脫敏的本機路徑。漏洞請依 [SECURITY.md](SECURITY.md) 私下回報。

授權與來源紀錄屬於交付契約。上游引擎保留原授權與聲明；詳見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)、[CONTRIBUTORS.md](CONTRIBUTORS.md)、[source-lock.json](presentation-studio/source-lock.json) 與各引擎授權檔案。

`scripts/upstream_sync.py check --json` 是唯讀檢查。維護工作流發現穩定版本、驗證白名單與授權、執行儲存庫/套件檢查，並僅在驗證後建立或更新專用同步 PR。詳見 [docs/upstream-sync.md](docs/upstream-sync.md)。

## 🤝 貢獻與發布

貢獻請遵守 [CONTRIBUTING.md](CONTRIBUTING.md) 與 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。Release 候選版本應在 Pull Request 中通過儲存庫健康度、範例、套件、安全以及適用的渲染 QA 檢查。受保護的 `main` 分支及其必要檢查是整合邊界；本機構建或尚未合併的分支不等於公開 Release。

## 📄 授權

Presentation Studio 採用 [AGPL-3.0](LICENSE)。上游引擎保留其原授權與聲明。
