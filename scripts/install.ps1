[CmdletBinding()]
param(
    [string]$Destination,
    [switch]$Force
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

New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
$backupPath = $null

if (Test-Path -LiteralPath $destinationPath) {
    if (-not $Force) {
        throw "Destination already exists. Re-run with -Force to move it to a timestamped backup first: $destinationPath"
    }
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $destinationParent ($destinationLeaf + ".backup-" + $timestamp)
    if (Test-Path -LiteralPath $backupPath) {
        throw "Backup path already exists: $backupPath"
    }
    Move-Item -LiteralPath $destinationPath -Destination $backupPath
}

try {
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Recurse
    $requiredFiles = @(
        "SKILL.md",
        "catalog\products.json",
        "catalog\styles.json",
        "engines\manifest.json",
        "source-lock.json"
    )
    foreach ($requiredFile in $requiredFiles) {
        $requiredPath = Join-Path $destinationPath $requiredFile
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Installed package is incomplete: $requiredFile"
        }
    }
}
catch {
    if (Test-Path -LiteralPath $destinationPath) {
        $failedPath = $destinationPath + ".failed-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $destinationPath -Destination $failedPath
        Write-Warning "Incomplete copy moved to: $failedPath"
    }
    if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
        Move-Item -LiteralPath $backupPath -Destination $destinationPath
        Write-Warning "Previous installation restored."
    }
    throw
}

$installedCount = (Get-ChildItem -LiteralPath $destinationPath -Recurse -File).Count
Write-Output "Presentation Studio installed successfully."
Write-Output "Destination: $destinationPath"
Write-Output "Files: $installedCount"
if ($backupPath) {
    Write-Output "Previous installation backup: $backupPath"
}
Write-Output "Restart Codex, then invoke `$presentation-studio or describe a presentation/image request naturally."

