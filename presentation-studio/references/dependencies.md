# Dependency and Portability Contract

The repository installers stage a copy outside the Skill discovery directory and run `scripts/self_check.py` before replacing an existing installation. A forced update stores the previous version under `.agents/skill-backups/presentation-studio/`, so a host does not discover backup copies as duplicate Skills. The self-check requires real absolute Python and Node executables, validates all four engine entries, and exercises the product recommendation and routing path without third-party Python dependencies.

Resolve workspace runtimes first and pass absolute executable paths. If the host provides a dependency loader, use its documented API and retain its returned paths. If no loader is available or it fails, use this PowerShell 5.1-compatible fallback handoff. Run it from the task or project root. It assumes `$skillRoot` is already the absolute root of the invoked Skill and `$normalizedRequest` is an already-constructed PowerShell object; neither value is interpolated into PowerShell source. A Codex App loader and bundle are optional host adapters, not requirements for other Agents/Harnesses:

```powershell
if (-not [IO.Path]::IsPathRooted([string]$skillRoot)) { throw '$skillRoot must be absolute' }
if ($null -eq $normalizedRequest) { throw '$normalizedRequest is required' }
$taskRoot = (Get-Location).Path
$tempRoot = Join-Path $taskRoot '.temp/presentation-studio-retrieval'
if (-not (Test-Path -LiteralPath $tempRoot -PathType Container)) {
    [IO.Directory]::CreateDirectory($tempRoot) | Out-Null
}
$invocationId = [Guid]::NewGuid().ToString('N')
$requestPath = Join-Path $tempRoot ("request-{0}.json" -f $invocationId)
$routePath = Join-Path $tempRoot ("route-{0}.json" -f $invocationId)

$resolverPath = Join-Path $skillRoot 'scripts/resolve-runtimes.ps1'
$runtimeJson = & $resolverPath
if ($LASTEXITCODE -ne 0) { throw "Runtime resolver failed with exit $LASTEXITCODE" }
$runtimeJson = $runtimeJson -join [Environment]::NewLine
$runtime = $runtimeJson | ConvertFrom-Json
if ($runtime.status -ne 'PASS') { throw 'Runtime resolver did not return PASS' }
foreach ($name in @('python', 'node', 'git')) {
    $path = [string]$runtime.$name
    if (-not [IO.Path]::IsPathRooted($path) -or
        -not (Test-Path -LiteralPath $path -PathType Leaf) -or
        $path -match '(?i)[\\/]WindowsApps[\\/]') {
        throw "Invalid resolved runtime: $name=$path"
    }
}

# Optional renderers remain false unless their independently resolved absolute paths are
# added as --office-renderer <absolute-file> and --chromium <absolute-file>. Never use PATH.
$preflightJson = & $runtime.python (Join-Path $skillRoot 'scripts/preflight.py') --python $runtime.python --node $runtime.node
if ($LASTEXITCODE -ne 0) { throw "preflight.py failed with exit $LASTEXITCODE" }
$preflight = ($preflightJson -join [Environment]::NewLine) | ConvertFrom-Json
if ($preflight.status -ne 'PASS') { throw 'preflight.py did not return PASS' }

$recommendRequest = ($normalizedRequest | ConvertTo-Json -Depth 10) | ConvertFrom-Json
if ($null -eq $recommendRequest.PSObject.Properties['readiness']) {
    $recommendRequest | Add-Member -NotePropertyName readiness -NotePropertyValue $preflight.readiness
} else {
    $recommendRequest.readiness = $preflight.readiness
}
$recommendRequest | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $requestPath -Encoding UTF8
$recommendationJson = & $runtime.python (Join-Path $skillRoot 'scripts/recommend.py') --json-file $requestPath
if ($LASTEXITCODE -ne 0) { throw "recommend.py failed with exit $LASTEXITCODE" }
$recommendationJson = $recommendationJson -join [Environment]::NewLine
$recommendation = $recommendationJson | ConvertFrom-Json
if (-not $recommendation.style.selected -or $recommendation.status -eq 'FAIL') {
    throw 'recommend.py returned an unusable recommendation'
}
if (-not $recommendation.product_id) {
    if ($recommendation.status -eq 'PARTIAL' -and $recommendation.fallback) {
        $recommendationJson
        return
    }
    throw 'recommend.py returned no routable product'
}

$routeRequest = ($normalizedRequest | ConvertTo-Json -Depth 10) | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$routeRequest.product)) {
    if ($null -eq $routeRequest.PSObject.Properties['product']) {
        $routeRequest | Add-Member -NotePropertyName product -NotePropertyValue $recommendation.product_id
    } else {
        $routeRequest.product = $recommendation.product_id
    }
}
if ([string]::IsNullOrWhiteSpace([string]$routeRequest.style)) {
    if ($null -eq $routeRequest.PSObject.Properties['style']) {
        $routeRequest | Add-Member -NotePropertyName style -NotePropertyValue $recommendation.style.selected
    } else {
        $routeRequest.style = $recommendation.style.selected
    }
}
$routeRequest | ConvertTo-Json -Depth 10 |
    Set-Content -LiteralPath $routePath -Encoding UTF8
$routeJson = & $runtime.python (Join-Path $skillRoot 'scripts/route.py') --json-file $routePath
if ($LASTEXITCODE -ne 0) { throw "route.py failed with exit $LASTEXITCODE" }
$route = ($routeJson -join [Environment]::NewLine) | ConvertFrom-Json
```

The two task-local files keep request data out of executable source and preserve nonblank explicit `product` or `style` constraints so the router can report conflicts. Preflight-derived booleans overwrite any untrusted request readiness before the final recommendation, and no credential value is copied. Preflight always returns explicit `office_renderer` and `chromium` booleans; omission means `false`, so a catalog product that declares either prerequisite cannot receive an unearned `PASS`. Renderer arguments, when supplied, must be independently resolved absolute files and must not be WindowsApps aliases. The resolver accepts `PRESENTATION_STUDIO_RUNTIME_ROOT` or explicit `PRESENTATION_STUDIO_PYTHON`, `PRESENTATION_STUDIO_NODE`, and `PRESENTATION_STUDIO_GIT` paths, does not recursively search or consult PATH, and returns a source label. When no generic configuration is present, its final fallback is the optional Codex App bundle and is labeled `codex-app-bundle`; another host must not infer support from that fallback. WindowsApps and bare/PATH aliases are invalid. Runtime is `PARTIAL / NOT EXECUTED` only when both the host loader and checked-in resolver fail with recorded evidence.

| Capability | Required | Optional |
|---|---|---|
| Shared router/QA | Python 3 standard library | none |
| Native PPTX | PPT Master Python dependencies | PowerPoint, LibreOffice, Pandoc, fonts, TTS/image providers |
| Guizang static validation | Node.js | Playwright + installed Chromium for rendered measurements |
| Frontend HTML | browser | Playwright + Chromium for PDF/render tests, Vercel only on explicit publish request |
| Baoyu visual assets | Node.js + tsx or supported Bun path | provider credentials, Codex CLI, sharp/pdf-lib/pptxgenjs by capability |

Run `scripts/preflight.py` before construction. When the dependency loader returns a Node-package directory, pass it as `--node-modules <absolute-directory>`; otherwise the preflight derives the bundled sibling directory when possible. Read `capabilities.python` and `capabilities.node` before selecting advanced SVG, narration, ingestion, browser-QA, or Baoyu TypeScript paths. Missing optional dependencies must disable only the affected feature. Keep secrets in environment variables, caches versioned and invalidatable, and temporary files inside the project `.temp/` boundary.

On Windows, prefer the bundled Node/Python implementations. Treat `.sh`, `mktemp`, `open`, `xdg-open`, and `/usr/local` assumptions as optional compatibility paths, not primary instructions.
