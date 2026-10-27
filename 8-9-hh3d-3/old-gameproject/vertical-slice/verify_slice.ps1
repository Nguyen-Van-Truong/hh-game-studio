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
$Only = @($Only | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$knownTests = @("smoke", "deterministic", "save_load", "gameplay", "asset_readback")
$unknownTests = @($Only | Where-Object { $knownTests -notcontains $_ })
if ($unknownTests.Count -gt 0) { throw "Unknown -Only test selection: $($unknownTests -join ', ')" }
$script:hh3dRanTests = @()
$verifyDir = Join-Path $env:TEMP ("hh3d-vertical-slice-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $verifyDir | Out-Null
$relocatedBlenderSources = @()
function Restore-BlenderSources {
    foreach ($entry in $relocatedBlenderSources) {
        if ((Test-Path -LiteralPath $entry.Hidden) -and -not (Test-Path -LiteralPath $entry.Source)) {
            Move-Item -LiteralPath $entry.Hidden -Destination $entry.Source
        }
    }
}
try {
    foreach ($sourceName in @("pickup_original.blend", "pickup_original.blend1")) {
        $sourcePath = Join-Path $projectDir (Join-Path "assets" $sourceName)
        if (Test-Path -LiteralPath $sourcePath) {
            $hiddenPath = Join-Path $verifyDir $sourceName
            Move-Item -LiteralPath $sourcePath -Destination $hiddenPath
            $relocatedBlenderSources += [pscustomobject]@{ Source = $sourcePath; Hidden = $hiddenPath }
        }
    }
} catch {
    Restore-BlenderSources
    throw
}
function Should-Run([string]$name) {
    return $Only.Count -eq 0 -or $Only -contains $name
}
function Invoke-Check([string]$name, [string]$arg) {
    if (-not (Should-Run $name)) { return }
    $script:hh3dRanTests += $name
    $stdout = Join-Path $verifyDir "$name.stdout.log"
    $stderr = Join-Path $verifyDir "$name.stderr.log"
    # Start-Process joins ArgumentList into one command line; quote the
    # project path so a checkout under a directory containing spaces survives.
    $proc = Start-Process -FilePath $Godot -ArgumentList @("--headless", "--path", ('"' + $projectDir + '"'), $arg) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
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
function Invoke-AssetImport {
    $stdout = Join-Path $verifyDir "godot_import.stdout.log"
    $stderr = Join-Path $verifyDir "godot_import.stderr.log"
    $proc = Start-Process -FilePath $Godot -ArgumentList @("--headless", "--editor", "--path", ('"' + $projectDir + '"'), "--quit") -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "godot_import TIMEOUT after ${TimeoutSeconds}s"
    }
    $proc.Refresh()
    $processExitCode = [int]$proc.ExitCode
    $text = ((Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue) | Out-String).Trim()
    if ($processExitCode -ne 0 -or $text -match "ERROR:|SCRIPT ERROR") {
        throw "godot_import failed exit=$processExitCode`n$text"
    }
    Write-Output "godot_import PASS exit=$processExitCode"
}
try {
    if (Test-Path (Join-Path $projectDir "assets/pickup_original.glb")) {
        Invoke-AssetImport
    }
    Invoke-Check "smoke" "--smoke-test"
    Invoke-Check "deterministic" "--deterministic-test"
    Invoke-Check "save_load" "--integration-test"
    Invoke-Check "gameplay" "--gameplay-test"
    if (Test-Path (Join-Path $projectDir "assets/pickup_original.glb")) {
        Invoke-Check "asset_readback" "--asset-test"
    } elseif (Should-Run "asset_readback") {
        throw "asset_readback BLOCKED_EXTERNAL blender_output_missing"
    }
    if ($Only.Count -gt 0) {
        $missingTests = @($Only | Where-Object { $script:hh3dRanTests -notcontains $_ })
        if ($missingTests.Count -gt 0) { throw "Requested test was skipped: $($missingTests -join ', ')" }
    }
    Write-Output "GODOT_SHA256=$godotHash"
    Write-Output "PROJECT=$projectDir"
} finally {
    Restore-BlenderSources
}
