[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Test-CodexRuntimeCandidates {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RuntimeRoot,
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Candidates
    )

    $required = @("python", "node", "git")
    $resolved = [ordered]@{python = $null; node = $null; git = $null}
    $missing = @()
    $rejected = @()
    $schemaErrors = @()

    foreach ($name in $required) {
        if (-not $Candidates.Contains($name)) {
            $missing += $name
            $schemaErrors += "missing key: $name"
        }
    }
    foreach ($name in $Candidates.Keys) {
        if ($required -notcontains $name) {
            $schemaErrors += "unexpected key: $name"
        }
    }

    foreach ($name in $required) {
        if (-not $Candidates.Contains($name)) {
            continue
        }
        $candidate = $Candidates[$name]
        if ($candidate -isnot [string] -or [string]::IsNullOrWhiteSpace($candidate)) {
            if ($missing -notcontains $name) { $missing += $name }
            $schemaErrors += "$name must be a non-empty string"
            continue
        }
        if (-not [IO.Path]::IsPathRooted($candidate)) {
            if ($missing -notcontains $name) { $missing += $name }
            $rejected += "$name=$candidate"
            continue
        }
        try {
            $path = [IO.Path]::GetFullPath($candidate)
        } catch {
            if ($missing -notcontains $name) { $missing += $name }
            $rejected += "$name=$candidate"
            continue
        }
        if ($path -match "(?i)[\\/]WindowsApps[\\/]" -or
            -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            if ($missing -notcontains $name) { $missing += $name }
            if ($path -match "(?i)[\\/]WindowsApps[\\/]") {
                $rejected += "$name=$path"
            }
            continue
        }
        $resolved[$name] = $path
    }

    [pscustomobject][ordered]@{
        status = if ($missing.Count -eq 0 -and $schemaErrors.Count -eq 0) { "PASS" } else { "FAIL" }
        runtime_root = $RuntimeRoot
        python = $resolved.python
        node = $resolved.node
        git = $resolved.git
        missing = @($missing)
        rejected = @($rejected)
        schema_errors = @($schemaErrors)
    }
}

function Resolve-CodexRuntimeSet {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProfileRoot
    )

    $runtimeRoot = Join-Path $ProfileRoot ".cache\codex-runtimes\codex-primary-runtime"
    $candidates = [ordered]@{
        python = Join-Path $runtimeRoot "dependencies\python\python.exe"
        node = Join-Path $runtimeRoot "dependencies\node\bin\node.exe"
        git = Join-Path $runtimeRoot "dependencies\native\git\cmd\git.exe"
    }
    Test-CodexRuntimeCandidates -RuntimeRoot $runtimeRoot -Candidates $candidates
}

if ($MyInvocation.InvocationName -ne ".") {
    $profileRoot = [Environment]::GetFolderPath("UserProfile")
    if ([string]::IsNullOrWhiteSpace($profileRoot)) {
        [Console]::Error.WriteLine("Unable to determine the current user profile from the OS.")
        exit 2
    }

    $result = Resolve-CodexRuntimeSet -ProfileRoot $profileRoot
    $result | ConvertTo-Json -Compress
    if ($result.status -ne "PASS") {
        $evidence = "Missing required bundled runtimes: {0}. Schema errors: {1}. Checked only {2}." -f (
            $result.missing -join ", "
        ), ($result.schema_errors -join ", "), $result.runtime_root
        [Console]::Error.WriteLine($evidence)
        exit 2
    }
    exit 0
}
