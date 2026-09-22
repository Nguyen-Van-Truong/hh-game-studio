param(
    [string]$Python = "python",
    [string]$Project,
    [int]$TimeoutSeconds = 60
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Project)) { $Project = Join-Path $PSScriptRoot "project.godot" }
$projectDir = Split-Path -Parent $Project
if ($TimeoutSeconds -lt 1) { throw "TimeoutSeconds must be positive" }
$verifyDir = Join-Path $env:TEMP ("hh3d-blender-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $verifyDir | Out-Null
function Invoke-BlenderStep([string]$name, [string]$script) {
    $stdout = Join-Path $verifyDir "$name.stdout.log"
    $stderr = Join-Path $verifyDir "$name.stderr.log"
    $proc = Start-Process -FilePath $Python -ArgumentList @($script) -WorkingDirectory $projectDir -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "$name TIMEOUT after ${TimeoutSeconds}s"
    }
    $proc.Refresh()
    $processExitCode = [int]$proc.ExitCode
    $text = ((Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue) | Out-String).Trim()
    if ($processExitCode -ne 0) { throw "$name failed exit=$processExitCode`n$text" }
    Write-Output "$name PASS exit=$processExitCode"
    Write-Output $text
}
Invoke-BlenderStep "author" (Join-Path $PSScriptRoot "blender/generate_asset.py")
Invoke-BlenderStep "reopen_export" (Join-Path $PSScriptRoot "blender/reopen_export_asset.py")
$glb = Join-Path $PSScriptRoot "assets/pickup_original.glb"
if (-not (Test-Path -LiteralPath $glb)) { throw "GLB output missing" }
Write-Output ("GLB_SHA256=" + (Get-FileHash -Algorithm SHA256 -LiteralPath $glb).Hash.ToLower())
