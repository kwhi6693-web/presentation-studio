[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$Force,
    [string]$PythonExecutable,
    [string]$NodeExecutable
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent $scriptRoot
$sourcePath = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot "presentation-studio"))

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $userProfilePath = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    $Destination = Join-Path $userProfilePath ".agents\skills\presentation-studio"
}

$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$destinationParent = Split-Path -Parent $destinationPath
$destinationLeaf = Split-Path -Leaf $destinationPath
$destinationContainer = Split-Path -Parent $destinationParent
$driveRoot = [System.IO.Path]::GetPathRoot($destinationPath)
$userProfileRoot = [System.IO.Path]::GetFullPath([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile))

if (-not (Test-Path -LiteralPath (Join-Path $sourcePath "SKILL.md") -PathType Leaf)) {
    throw "Invalid package: presentation-studio/SKILL.md is missing."
}
if ($destinationPath -eq $driveRoot -or $destinationPath -eq $userProfileRoot -or $destinationPath -eq $sourcePath) {
    throw "Unsafe destination: $destinationPath"
}
if ([string]::IsNullOrWhiteSpace($destinationLeaf)) {
    throw "Destination must name a skill directory."
}
if ([string]::IsNullOrWhiteSpace($destinationContainer)) {
    throw "Destination must have a safe parent directory."
}
$sourceFiles = @(Get-ChildItem -LiteralPath $sourcePath -Recurse -File)
$longestRelativePath = $sourceFiles |
    ForEach-Object { $_.FullName.Substring($sourcePath.Length + 1).Length } |
    Measure-Object -Maximum
$longestDestinationPath = $destinationPath.Length + 1 + [int]$longestRelativePath.Maximum
if ($longestDestinationPath -ge 260) {
    throw "Destination path is too deep for a portable Windows install (longest file path: $longestDestinationPath characters; limit: 259): $destinationPath"
}

function Resolve-SafeExecutable {
    param(
        [string]$ProvidedPath,
        [string[]]$CommandNames
    )

    if (-not [string]::IsNullOrWhiteSpace($ProvidedPath)) {
        $candidate = [System.IO.Path]::GetFullPath($ProvidedPath)
        if ($candidate -notmatch "(?i)[\\/]WindowsApps[\\/]" -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
        throw "Unsafe or missing executable: $ProvidedPath"
    }
    foreach ($commandName in $CommandNames) {
        $command = Get-Command $commandName -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source -notmatch "(?i)[\\/]WindowsApps[\\/]" -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
            return [System.IO.Path]::GetFullPath($command.Source)
        }
    }
    return $null
}

function Remove-EmptyDirectory {
    param([string]$Path)
    if ((Test-Path -LiteralPath $Path -PathType Container) -and @(Get-ChildItem -LiteralPath $Path -Force).Count -eq 0) {
        [System.IO.Directory]::Delete([System.IO.Path]::GetFullPath($Path))
    }
}

function Copy-SkillTree {
    param(
        [string]$Source,
        [string]$Destination
    )
    $robocopy = Get-Command "robocopy.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($robocopy) {
        & $robocopy.Source $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
        $robocopyExit = $LASTEXITCODE
        if ($robocopyExit -ge 8) {
            throw "robocopy failed with exit code $robocopyExit"
        }
        return
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
}

function Move-Directory {
    param(
        [string]$Source,
        [string]$Destination
    )
    [System.IO.Directory]::Move(
        [System.IO.Path]::GetFullPath($Source),
        [System.IO.Path]::GetFullPath($Destination)
    )
}

function Remove-StagedTree {
    param(
        [string]$Path,
        [string]$AllowedRoot
    )
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedRoot = [System.IO.Path]::GetFullPath($AllowedRoot)
    if (-not $resolvedPath.StartsWith($resolvedRoot + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to clean an unexpected staging path: $resolvedPath"
    }
    if (Test-Path -LiteralPath $resolvedPath -PathType Container) {
        $longPath = if ($resolvedPath.StartsWith("\\?\")) { $resolvedPath } else { "\\?\" + $resolvedPath }
        [System.IO.Directory]::Delete($longPath, $true)
    }
}

if ([string]::IsNullOrWhiteSpace($PythonExecutable) -or [string]::IsNullOrWhiteSpace($NodeExecutable)) {
    $resolverPath = Join-Path $sourcePath "scripts\resolve-runtimes.ps1"
    if (Test-Path -LiteralPath $resolverPath -PathType Leaf) {
        . $resolverPath
        $resolvedRuntimes = Resolve-PresentationStudioRuntimeSet -ProfileRoot $userProfileRoot
        if ($resolvedRuntimes.status -eq "PASS") {
            if ([string]::IsNullOrWhiteSpace($PythonExecutable)) { $PythonExecutable = $resolvedRuntimes.python }
            if ([string]::IsNullOrWhiteSpace($NodeExecutable)) { $NodeExecutable = $resolvedRuntimes.node }
        }
    }
}
$PythonExecutable = Resolve-SafeExecutable -ProvidedPath $PythonExecutable -CommandNames @("python3.exe", "python.exe", "python3", "python")
$NodeExecutable = Resolve-SafeExecutable -ProvidedPath $NodeExecutable -CommandNames @("node.exe", "node")
if (-not $PythonExecutable -or -not $NodeExecutable) {
    throw "Python and Node.js are required. Pass absolute paths with -PythonExecutable and -NodeExecutable."
}

$backupRoot = Join-Path (Join-Path $destinationContainer "skill-backups") $destinationLeaf
$stagingContainer = Join-Path ([System.IO.Path]::GetTempPath()) "presentation-studio-install"
$stagingRoot = Join-Path $stagingContainer $destinationLeaf
$stagingPath = Join-Path $stagingRoot ([Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
$backupPath = $null

if (Test-Path -LiteralPath $destinationPath) {
    if (-not $Force) {
        throw "Destination already exists. Re-run with -Force to preserve it outside the skill discovery directory first: $destinationPath"
    }
}

try {
    Copy-SkillTree -Source $sourcePath -Destination $stagingPath
    $stagedFileCount = @(Get-ChildItem -LiteralPath $stagingPath -Recurse -File).Count
    if ($stagedFileCount -ne $sourceFiles.Count) {
        throw "Installed package copy is incomplete: expected $($sourceFiles.Count) files, found $stagedFileCount."
    }
    $requiredFiles = @(
        "SKILL.md",
        "catalog\products.json",
        "catalog\styles.json",
        "engines\manifest.json",
        "scripts\self_check.py",
        "source-lock.json"
    )
    foreach ($requiredFile in $requiredFiles) {
        $requiredPath = Join-Path $stagingPath $requiredFile
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Installed package is incomplete: $requiredFile"
        }
    }

    $selfCheckPath = Join-Path $stagingPath "scripts\self_check.py"
    $selfCheckOutput = & $PythonExecutable $selfCheckPath --root $stagingPath --python $PythonExecutable --node $NodeExecutable --json
    if ($LASTEXITCODE -ne 0) {
        throw "Installed package self-check failed: $($selfCheckOutput -join [Environment]::NewLine)"
    }
    $selfCheckResult = ($selfCheckOutput -join [Environment]::NewLine) | ConvertFrom-Json
    if ($selfCheckResult.status -ne "PASS") {
        throw "Installed package self-check status is $($selfCheckResult.status)."
    }

    if (Test-Path -LiteralPath $destinationPath) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupPath = Join-Path $backupRoot $timestamp
        if (Test-Path -LiteralPath $backupPath) {
            $backupPath = Join-Path $backupRoot ($timestamp + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
        }
        Move-Directory -Source $destinationPath -Destination $backupPath
    }
    Move-Directory -Source $stagingPath -Destination $destinationPath
    Remove-EmptyDirectory -Path $stagingRoot
    Remove-EmptyDirectory -Path $stagingContainer
}
catch {
    $installError = $_
    try { Remove-StagedTree -Path $stagingPath -AllowedRoot $stagingRoot } catch { Write-Warning "Staging cleanup failed: $($_.Exception.Message)" }
    Remove-EmptyDirectory -Path $stagingRoot
    Remove-EmptyDirectory -Path $stagingContainer
    if ($backupPath -and (Test-Path -LiteralPath $backupPath) -and -not (Test-Path -LiteralPath $destinationPath)) {
        Move-Directory -Source $backupPath -Destination $destinationPath
        Write-Warning "Previous installation restored."
    }
    throw $installError
}

$installedCount = (Get-ChildItem -LiteralPath $destinationPath -Recurse -File).Count
Write-Output "Presentation Studio installed successfully."
Write-Output "Destination: $destinationPath"
Write-Output "Files: $installedCount"
Write-Output "Self-check: PASS"
Write-Output "Python: $PythonExecutable"
Write-Output "Node.js: $NodeExecutable"
if ($backupPath) {
    Write-Output "Previous installation backup: $backupPath"
}
Write-Output "Reload your Agent/Harness Skill registry, then invoke `$presentation-studio or describe a presentation/image request naturally."

