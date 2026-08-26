#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/launch.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Project,
    [string]$InstallRoot = "",
    [switch]$Godot,
    [switch]$SidecarOnly
)

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "launch.py"
$pyArgs = @($Py, "--project", $Project)
if ($InstallRoot) { $pyArgs += @("--install-root", $InstallRoot) }
if ($Godot) { $pyArgs += "--godot" }
if ($SidecarOnly) { $pyArgs += "--sidecar-only" }
& python @pyArgs
exit $LASTEXITCODE
