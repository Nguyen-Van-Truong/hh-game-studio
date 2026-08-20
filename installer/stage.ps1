# Copy release binaries into installer\dist\ for ISCC (SourceRoot=dist).
# Does not build. Run cargo --release first. Not invoked by CI.

$ErrorActionPreference = "Stop"

$InstallerDir = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $InstallerDir "..")).Path
$ReleaseDir = Join-Path $RepoRoot "target\release"
$DistDir = Join-Path $InstallerDir "dist"

$Names = @(
    "gs-editor.exe",
    "gs-player.exe",
    "gs-cli.exe",
    "gs-mcp.exe"
)

if (-not (Test-Path -LiteralPath $ReleaseDir)) {
    throw "Missing $ReleaseDir — run: cargo build -p gs-editor -p gs-player -p gs-cli -p gs-mcp --release"
}

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

foreach ($Name in $Names) {
    $Src = Join-Path $ReleaseDir $Name
    if (-not (Test-Path -LiteralPath $Src)) {
        throw "Missing $Src — build that crate in release, then re-run stage.ps1"
    }
    Copy-Item -LiteralPath $Src -Destination (Join-Path $DistDir $Name) -Force
    Write-Host "staged $Name"
}

Write-Host "OK: $DistDir"
Write-Host "Compile: ISCC.exe `"$InstallerDir\hh-game-studio.iss`""
