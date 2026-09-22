param(
    [string]$Blender = "",
    # Kept for compatibility with the old wrapper. A plain Python interpreter
    # is accepted only when it can import bpy; otherwise use -Blender.
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
if (-not [string]::IsNullOrWhiteSpace($Blender)) {
    $runner = (Resolve-Path -LiteralPath $Blender -ErrorAction Stop).Path
    $runnerPrefix = @('--background', '--factory-startup', '--python-exit-code', '2', '--python')
    $runnerMode = 'blender'
} else {
    $runner = $Python
    $runnerPrefix = @()
    $runnerMode = 'python'
    $probe = & $runner -c 'import bpy' 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python runner does not provide bpy; pass -Blender <blender.exe>.`n$probe"
    }
}
function Invoke-BlenderStep([string]$name, [string]$script) {
    $stdout = Join-Path $verifyDir "$name.stdout.log"
    $stderr = Join-Path $verifyDir "$name.stderr.log"
    # Start-Process joins ArgumentList into one command line; quote the
    # script path so a checkout under a directory containing spaces survives.
    $arguments = @($runnerPrefix + @('"' + $script + '"'))
    $proc = Start-Process -FilePath $runner -ArgumentList $arguments -WorkingDirectory $projectDir -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "$name TIMEOUT after ${TimeoutSeconds}s"
    }
    $proc.Refresh()
    $processExitCode = [int]$proc.ExitCode
    $text = ((Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath $stderr -ErrorAction SilentlyContinue) | Out-String).Trim()
    if ($processExitCode -ne 0) { throw "$name failed exit=$processExitCode`n$text" }
    Write-Output "$name PASS exit=$processExitCode runner=$runnerMode"
    Write-Output $text
}
Invoke-BlenderStep "author" (Join-Path $PSScriptRoot "blender/generate_asset.py")
Invoke-BlenderStep "reopen_export" (Join-Path $PSScriptRoot "blender/reopen_export_asset.py")
$glb = Join-Path $PSScriptRoot "assets/pickup_original.glb"
if (-not (Test-Path -LiteralPath $glb)) { throw "GLB output missing" }
Write-Output ("GLB_SHA256=" + (Get-FileHash -Algorithm SHA256 -LiteralPath $glb).Hash.ToLower())
