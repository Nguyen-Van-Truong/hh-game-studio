#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/doctor.py (frozen Godot 4.7.1-stable).
#>
param(
    [switch]$Install,
    [string]$RequestedVersion = "",
    [switch]$SkipTemplates,
    [switch]$PrintBin,
    [switch]$PrintGui
)

$ErrorActionPreference = "Stop"
$DoctorPy = Join-Path $PSScriptRoot "doctor.py"
if (-not (Test-Path -LiteralPath $DoctorPy)) {
    Write-Error "doctor.py missing next to doctor.ps1"
    exit 1
}

$pyArgs = @($DoctorPy)
if ($Install) { $pyArgs += "--install" }
if ($RequestedVersion) { $pyArgs += @("--requested-version", $RequestedVersion) }
if ($SkipTemplates) { $pyArgs += "--skip-templates" }
if ($PrintBin) { $pyArgs += "--print-bin" }
if ($PrintGui) { $pyArgs += "--print-gui" }

& python @pyArgs
exit $LASTEXITCODE
