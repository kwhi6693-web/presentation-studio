[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

function Test-PresentationStudioRuntimeCandidates {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RuntimeRoot,
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Candidates,
        [string]$Source = "configured-runtime-root"
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
        source = $Source
        runtime_root = $RuntimeRoot
        python = $resolved.python
        node = $resolved.node
        git = $resolved.git
        missing = @($missing)
        rejected = @($rejected)
        schema_errors = @($schemaErrors)
    }
}

function Resolve-PresentationStudioRuntimeSet {
    [CmdletBinding()]
    param(
        [string]$RuntimeRoot,
        [string]$ProfileRoot,
        [string]$PythonExecutable,
        [string]$NodeExecutable,
        [string]$GitExecutable
    )

    $configuredRoot = $RuntimeRoot
    if ([string]::IsNullOrWhiteSpace($configuredRoot)) {
        $configuredRoot = [Environment]::GetEnvironmentVariable("PRESENTATION_STUDIO_RUNTIME_ROOT")
    }
    $configuredPython = if ($PythonExecutable) { $PythonExecutable } else { [Environment]::GetEnvironmentVariable("PRESENTATION_STUDIO_PYTHON") }
    $configuredNode = if ($NodeExecutable) { $NodeExecutable } else { [Environment]::GetEnvironmentVariable("PRESENTATION_STUDIO_NODE") }
    $configuredGit = if ($GitExecutable) { $GitExecutable } else { [Environment]::GetEnvironmentVariable("PRESENTATION_STUDIO_GIT") }

    $source = "configured-runtime-root"
    if (-not [string]::IsNullOrWhiteSpace($configuredRoot)) {
        $runtimeRoot = [IO.Path]::GetFullPath($configuredRoot)
        $candidates = [ordered]@{
            python = if ($configuredPython) { $configuredPython } else { Join-Path $runtimeRoot "dependencies\python\python.exe" }
            node = if ($configuredNode) { $configuredNode } else { Join-Path $runtimeRoot "dependencies\node\bin\node.exe" }
            git = if ($configuredGit) { $configuredGit } else { Join-Path $runtimeRoot "dependencies\native\git\cmd\git.exe" }
        }
        return Test-PresentationStudioRuntimeCandidates -RuntimeRoot $runtimeRoot -Candidates $candidates -Source $source
    }

    if ($configuredPython -or $configuredNode -or $configuredGit) {
        $source = "configured-runtime-paths"
        $candidates = [ordered]@{
            python = $configuredPython
            node = $configuredNode
            git = $configuredGit
        }
        return Test-PresentationStudioRuntimeCandidates -RuntimeRoot "configured executable paths" -Candidates $candidates -Source $source
    }

    if ([string]::IsNullOrWhiteSpace($ProfileRoot)) {
        $ProfileRoot = [Environment]::GetFolderPath("UserProfile")
    }
    if ([string]::IsNullOrWhiteSpace($ProfileRoot)) {
        return [pscustomobject][ordered]@{
            status = "FAIL"
            source = "os-profile"
            runtime_root = $null
            python = $null
            node = $null
            git = $null
            missing = @("python", "node", "git")
            rejected = @()
            schema_errors = @("Unable to determine the current user profile")
        }
    }

    # This is a compatibility adapter for the Codex App bundle, not the core runtime
    # contract. Generic hosts should set PRESENTATION_STUDIO_RUNTIME_ROOT or the three
    # explicit executable variables instead of relying on this fallback.
    $runtimeRoot = Join-Path $ProfileRoot ".cache\codex-runtimes\codex-primary-runtime"
    $candidates = [ordered]@{
        python = Join-Path $runtimeRoot "dependencies\python\python.exe"
        node = Join-Path $runtimeRoot "dependencies\node\bin\node.exe"
        git = Join-Path $runtimeRoot "dependencies\native\git\cmd\git.exe"
    }
    Test-PresentationStudioRuntimeCandidates -RuntimeRoot $runtimeRoot -Candidates $candidates -Source "codex-app-bundle"
}

if ($MyInvocation.InvocationName -ne ".") {
    $result = Resolve-PresentationStudioRuntimeSet
    $result | ConvertTo-Json -Compress
    if ($result.status -ne "PASS") {
        $evidence = "Missing required runtimes: {0}. Schema errors: {1}. Checked source {2} at {3}." -f (
            $result.missing -join ", "
        ), ($result.schema_errors -join ", "), $result.source, $result.runtime_root
        [Console]::Error.WriteLine($evidence)
        exit 2
    }
    exit 0
}
