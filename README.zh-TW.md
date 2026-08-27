# Presentation Studio

> 為相容 Agent 設計的簡報與視覺製作 Skill：支援可編輯 PPTX、HTML 投影片、PDF、視覺素材、精準資料路由與渲染驗收。

[![Validate package](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/validate.yml)
[![Sync upstreams](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml/badge.svg)](https://github.com/kwhi6693-web/presentation-studio/actions/workflows/sync-upstreams.yml)
[![Latest release](https://img.shields.io/github/v/release/kwhi6693-web/presentation-studio?display_name=tag&sort=semver)](https://github.com/kwhi6693-web/presentation-studio/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Product recipes: 13](https://img.shields.io/badge/Product%20recipes-13-2f855a)](presentation-studio/catalog/products.json)
[![Style profiles: 8](https://img.shields.io/badge/Style%20profiles-8-805ad5)](presentation-studio/catalog/styles.json)

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

## 專案定位

Presentation Studio 將自然語言 brief、精準資料與既有素材，轉換為可解釋的產品選擇與引擎路由。核心 Skill contract 在實作允許的範圍內與宿主無關：Agent/Harness 提供本機執行能力，Skill 提供目錄驅動的產品路由、資料契約、原生生成邊界、溯源紀錄與渲染品質門禁。

主要流程：

~~~
brief + 資料 + 素材
        → 正規化與 preflight
        → 從本機 Catalog 檢索產品與風格
        → 路由至單一引擎或混合引擎鏈
        → 產生原生/可編輯輸出
        → 驗證、渲染、逐頁檢查、修復、再次驗證
        → 交付檔案、證據與能力限制
~~~

目前儲存庫包含 13 個產品配方、8 個風格設定與 4 個整合上游引擎。輸出類型包括 PPTX、HTML、PDF、PNG 與 SVG，實際可用範圍取決於產品及宿主能力。

## 能力分層

| 能力層 | 實際涵蓋 | 結果 |
|---|---|---|
| 意圖與產品決策 | brief 正規化、preflight、13 產品檢索、風格推論、衝突識別 | 可解釋的產品/風格選擇 |
| 資料契約與路由 | 精準資料 manifest、型別/順序/單位保護、單引擎與混合路由 | 可稽核的引擎計畫 |
| 內容與視覺製作 | 敘事、版面、圖表、封面、插圖、資訊圖、示意圖 | 內容與素材計畫 |
| 多格式原生生成 | 可編輯 PPTX、獨立 HTML、PDF、PNG、SVG、簡報者導覽 | 原生或可發布檔案 |
| 渲染驗收與修復 | 溢出、碰撞、字型、對比、頁數、互動、列印、離線行為 | 通過品質門禁的結果 |
| 安全、溯源與狀態 | 不可信內容邊界、憑證保護、授權/來源紀錄、路由狀態 | 可重現的證據 |
| 上游持續同步 | 穩定版本發現、白名單匯入、授權檢查、驗證後同步 PR | 可維護的整合 |

完整 L0-L19 職責圖請見[架構說明](docs/architecture.md)。

## 產品、輸出與引擎

來源資料是 [products.json](presentation-studio/catalog/products.json)。以下是 13 個產品配方的公共索引。

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
| [Frontend Slides](https://github.com/zarazhangrui/frontend-slides) | 獨立 HTML、鍵盤導覽、簡報者行為、HTML 轉 PDF | 瀏覽器/PDF QA 需要 Chromium/Playwright |
| [Baoyu Skills](https://github.com/JimLiu/baoyu-skills) | 封面、插圖、資訊圖、示意圖、資料圖片與圖片投影片 | Provider 圖像是可選能力；SVG 示意圖不是原生 PowerPoint 物件 |

## 相容性模型

### 設計支援與已驗證分開記錄

以下相容性矩陣是目前宿主證據的公開來源。

Skill contract 與核心邏輯是為能提供所需本機能力的相容 Agent/Harness 設計。“設計支援”描述架構與契約目標；只有目前驗證證據實際執行過的宿主/route 才能寫“已驗證”。

| 宿主 / Agent 能力 | Skill contract | 核心路由 | 本機腳本 | 原生生成 | 渲染 QA | 驗證狀態 |
|---|---|---|---|---|---|---|
| Codex | Supported | Supported | Supported | 取決於能力 | 取決於執行時 | 已驗證目前主機上的核心/套件契約；可選渲染器與 Provider route 另行報告 |
| 其他具備能力的 Agent / Harness | Designed | Designed | 需要本機執行時 | 取決於宿主 | 取決於執行時 | 依能力設計，本次尚未獨立驗證 |

這不是“所有 Agent 都支援”的聲明。應依具體 route 與能力判斷。例如宿主有 Python 與原生 PPTX 核心，但沒有 Chromium 或 image provider 時：

| Route | 結果 | 意義 |
|---|---|---|
| 原生 PPTX 生成 | 所需引擎路徑成功時為 PASS | 缺少瀏覽器本身不會否定 PPTX route |
| HTML 渲染 QA / HTML 轉 PDF | PARTIAL 或 未執行 | 受影響的檢查需要 Chromium/Playwright |
| Provider 圖像生成 | 不可用 | 未設定 Provider，應選擇非 Provider route 或回報限制 |
| 必需執行時缺失或硬約束衝突 | FAIL | 選定 route 無法滿足必需契約 |

PASS、PARTIAL、FAIL 是 route 結果；NOT AVAILABLE（不可用）與 NOT EXECUTED（未執行）用來明確表達能力缺口，不能被解讀為整個 Skill 不相容。

presentation-studio/agents/openai.yaml 是可選的 OpenAI/Codex 宿主描述檔，不是核心 Skill 必需項。上游 Baoyu 可能包含可選的 baoyu-codex-imagegen 適配器；Provider 與 Codex CLI 都只是可選的上游能力路徑。

## 快速路徑與完整路徑

快速路徑使用已可用的原生 PPTX route：選擇產品，提供所需 payload，執行對應本機腳本，並檢查產生的可編輯檔案。完整路徑還會加入環境預檢、精準資料驗證、所選輸出格式的渲染 QA、套件驗證與證據報告。當交付物需要公開發布，或驗收條件包含渲染器、瀏覽器、Office 或圖像 Provider 時，應使用完整路徑。

## 能力限制

Presentation Studio 依 route 回報限制。缺少 Chromium、Office 渲染器或 Provider 圖像服務，可能使 HTML/PDF 或 Provider route 處於 PARTIAL、NOT AVAILABLE 或 NOT EXECUTED；這不會阻止原生 PPTX route 單獨通過。除非實際執行過相關 route 並保留證據，否則不應把宿主描述為“已完整驗證”。

## 安裝

安裝目錄由宿主決定。agents/skills/presentation-studio 是隨附安裝腳本使用的一種常見約定，不是所有 Agent 的統一目錄；其他 Agent/Harness 應依自身的發現/匯入機制放置 Skill。

### Release 套件

從同一個[最新 Release](https://github.com/kwhi6693-web/presentation-studio/releases/latest) 下載 presentation-studio.zip 與 presentation-studio.zip.sha256，解壓前先驗證：

~~~
sha256sum -c presentation-studio.zip.sha256
~~~

Windows PowerShell：

~~~
$expected = (Get-Content .\presentation-studio.zip.sha256 -Raw).Split()[0].ToLowerInvariant()
$actual = (Get-FileHash .\presentation-studio.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 不相符" }
"OK: $actual"
~~~

解壓後應只有一個 presentation-studio/ Skill 根目錄。使用明確的絕對 Python 與 Node 路徑執行 self-check：

~~~
python presentation-studio/scripts/self_check.py \
  --root presentation-studio \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node \
  --json
~~~

### 原始碼安裝

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

兩個安裝腳本都會先在 Skill 發現目錄外暫存、執行真實 self-check，再替換舊安裝。強制更新會把舊版本放在所選發現目錄旁的 agents/skill-backups/。安裝後請重新載入宿主 Agent/Harness 的 Skill registry。

### 執行時解析

通用 resolver 支援：

- PRESENTATION_STUDIO_RUNTIME_ROOT，並使用 dependencies/python/python.exe、dependencies/node/bin/node.exe、dependencies/native/git/cmd/git.exe；或
- PRESENTATION_STUDIO_PYTHON、PRESENTATION_STUDIO_NODE、PRESENTATION_STUDIO_GIT 三個明確的絕對檔案路徑。

它會拒絕 WindowsApps alias，也不會把偶然的 PATH 命中當作執行時證據。沒有通用設定時，可回退到目前 Codex App bundle，並在結果中標記為 Codex 適配器；其他宿主不需要依賴這個回退。詳見[依賴與可攜性契約](presentation-studio/references/dependencies.md)。

## 使用

以自然語言描述目標，並提供主題、目的、受眾、來源材料或精準資料、輸出格式、可編輯性、視覺方向、頁數/比例與 QA 要求。

~~~
為董事會製作一份 16:9 的 AI 產品策略簡報。
交付原生可編輯 PPTX、獨立 HTML 與 PDF。
使用提供的季度指標，不得改變任何數值、單位、列順序或缺失值。
PPTX 中的圖表與表格必須可編輯；交付前檢查每頁的溢出、對比度、資料保真、備註、
離線行為以及瀏覽器/PDF 準備情況，並回報 PASS/PARTIAL/FAIL。
~~~

需要診斷路由時，先執行 preflight，再執行推薦與 route：

~~~
python presentation-studio/scripts/preflight.py \
  --python /absolute/path/to/python \
  --node /absolute/path/to/node
python presentation-studio/scripts/recommend.py --json-file request.json
python presentation-studio/scripts/route.py --json-file route-request.json
~~~

preflight.py 預設輸出 JSON，不接受 --json。readiness 必須來自目前脫敏的 preflight；router 會保留明確的產品/風格約束並回報衝突，不會靜默替換。

## 精準資料與可編輯性

精準資料任務必須具備已驗證的 manifest、完整的所選引擎 payload，以及渲染後的 observed contract，並比較三者。缺失值、重複值、長度不一致或 observed contract 不完整時，資料結果最高只能是 PARTIAL。

需要原生可編輯時，圖表、表格、文字與形狀應使用 PowerPoint 原生物件。不能用整頁截圖取代可編輯 deck；圖片主導產品仍應準確描述為圖片主導，而不是物件可編輯的 PPTX。

## QA 與狀態

品質閉環為：

~~~
validate → render → inspect every page → repair → validate again
~~~

依產品檢查敘事、溢出、碰撞、邊距、層級、字級、對比度、裁切、圖表完整性、可編輯性、備註、鍵盤行為、列印/離線行為、頁數與溯源。

- PASS：目前環境中所有必需命令與適用品質檢查均成功，修復後結果再次通過。
- PARTIAL：核心結果可用，但某個請求的或可選能力不可用/未執行；必須指出受影響的 route 與證據缺口。
- FAIL：硬約束衝突、必需執行時缺失、生成失敗或必需品質門禁尚未關閉。
- NOT AVAILABLE：宿主沒有提供某項能力，例如 image provider。
- NOT EXECUTED：適用檢查尚未執行，不能視為通過。

詳見 [qa.md](presentation-studio/references/qa.md) 與 [error-system.md](presentation-studio/references/error-system.md)。

## 範例

儲存庫內六個檔案是驗收 fixture，用於驗證儲存庫契約。scripts/verify_examples.py 會執行結構化檢查；fixture 通過不代表每個宿主都已重新執行所有可選渲染器或 Provider。

<details>
<summary>中英文驗收檔案</summary>

- [English PPTX](examples/bilingual-acceptance/en/presentation-acceptance-en.pptx)
- [English HTML](examples/bilingual-acceptance/en/presentation-acceptance-en.html)
- [English PDF](examples/bilingual-acceptance/en/presentation-acceptance-en.pdf)
- [中文 PPTX](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pptx)
- [中文 HTML](examples/bilingual-acceptance/zh/presentation-acceptance-zh.html)
- [中文 PDF](examples/bilingual-acceptance/zh/presentation-acceptance-zh.pdf)

</details>

<details>
<summary>fixture 涵蓋範圍</summary>

每份 deck 有 5 頁，並檢查語言標記、原生圖表/表格/備註、HTML 鍵盤/列印/離線行為與 PDF 頁面尺寸等宣告契約。執行 python scripts/verify_examples.py 查看目前結構化結果。

</details>

## 開發與驗證

在原始碼目錄中使用已解析的絕對 Python 路徑（如需要）執行：

~~~
python scripts/verify_repository_health.py
python scripts/verify_examples.py
python -m unittest discover -s tests -v
python scripts/build_package.py
python scripts/verify_package.py
python scripts/upstream_sync.py check --json
git diff --check
~~~

build_package.py 產生確定性的 dist/presentation-studio.zip。[checksums.sha256](checksums.sha256) 面向原始碼儲存庫中的這個構建產物；Release 旁的 presentation-studio.zip.sha256 是另一份契約，不能混用。

## 上游同步

scripts/upstream_sync.py check --json 是唯讀檢查。維護工作流支援儲存庫事件、手動觸發與每小時排程兜底；只有穩定版本、來源、白名單、授權與完整儲存庫檢查通過後，才會建立或更新專用同步 PR。詳見[上游同步說明](docs/upstream-sync.md)與 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安全、授權與參與

不要在 issue 或日誌中提交憑證、私有來源內容或未脫敏的本機路徑。漏洞請依 [SECURITY.md](SECURITY.md) 私下回報。貢獻請遵守 [CONTRIBUTING.md](CONTRIBUTING.md) 與 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

Presentation Studio 採用 [AGPL-3.0](LICENSE)。上游引擎保留原授權與聲明；詳見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)、[CONTRIBUTORS.md](CONTRIBUTORS.md)、[source-lock.json](presentation-studio/source-lock.json) 與各引擎授權檔案。

## 發布與貢獻

Release 候選版本應在 Pull Request 中通過儲存庫健康度、範例、套件、安全以及適用的渲染 QA 檢查。受保護的 `main` 分支及其必要檢查是整合邊界；本機構建或尚未合併的分支不等於公開 Release。貢獻流程請見 [CONTRIBUTING.md](CONTRIBUTING.md)。
