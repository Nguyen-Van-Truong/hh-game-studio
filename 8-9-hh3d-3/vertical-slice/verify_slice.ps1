param(
    [Parameter(Mandatory=$true)][string]$Godot,
    [string]$Project,
    [int]$TimeoutSeconds = 30,
    [string[]]$Only = @()
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Project)) { $Project = Join-Path $PSScriptRoot "project.godot" }
$projectDir = Split-Path -Parent $Project
if (-not (Test-Path -LiteralPath $Godot)) { throw "Godot executable missing: $Godot" }
$godotHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Godot).Hash.ToLower()
if ($TimeoutSeconds -lt 1) { throw "TimeoutSeconds must be positive" }
$verifyDir = Join-Path $env:TEMP ("hh3d-vertical-slice-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $verifyDir | Out-Null
function Should-Run([string]$name) {
    return $Only.Count -eq 0 -or $Only -contains $name
}
function Invoke-Check([string]$name, [string]$arg) {
    if (-not (Should-Run $name)) { return }
    $stdout = Join-Path $verifyDir "$name.stdout.log"
    $stderr = Join-Path $verifyDir "$name.stderr.log"
    $proc = Start-Process -FilePath $Godot -ArgumentList @("--headless", "--path", $projectDir, $arg) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "$name TIMEOUT after ${TimeoutSeconds}s"
    }
    $proc.Refresh()
    $processExitCode = [int]$proc.ExitCode
    $text = ((Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue) | Out-String).Trim()
    if ($processExitCode -ne 0) { throw "$name failed exit=$processExitCode`n$text" }
    $markers = @{
        smoke = "SMOKE_PASS"
        deterministic = "DETERMINISTIC_PASS"
        save_load = "SAVE_LOAD_PASS"
        gameplay = "GAMEPLAY_PASS"
        asset_readback = "ASSET_RUNTIME_PASS"
    }
    if ($text -match "FAIL|ERROR" -or $text -notmatch $markers[$name]) { throw "$name failed postcondition exit=$processExitCode`n$text" }
    Write-Output "$name PASS exit=$processExitCode"
    Write-Output $text
}
Invoke-Check "smoke" "--smoke-test"
Invoke-Check "deterministic" "--deterministic-test"
Invoke-Check "save_load" "--integration-test"
Invoke-Check "gameplay" "--gameplay-test"
if (Test-Path (Join-Path $projectDir "assets/pickup_original.glb")) {
    Invoke-Check "asset_readback" "--asset-test"
} elseif (Should-Run "asset_readback") {
    Write-Output "asset_readback BLOCKED_EXTERNAL blender_output_missing"
    exit 2
}
Write-Output "GODOT_SHA256=$godotHash"
Write-Output "PROJECT=$projectDir"
