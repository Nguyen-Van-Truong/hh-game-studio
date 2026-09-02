#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/ops.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string]$Home = "",
    [string]$Repo = "",
    [switch]$Sign,
    [switch]$Upload,
    [switch]$CleanVmProven,
    [switch]$HyperV,
    [switch]$Live
)

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "ops.py"
$pyArgs = @($Py, $Command)
if ($Home) { $pyArgs += @("--home", $Home) }
if ($Repo) { $pyArgs += @("--repo", $Repo) }
if ($Sign) { $pyArgs += "--sign" }
if ($Upload) { $pyArgs += "--upload" }
if ($CleanVmProven) { $pyArgs += "--clean-vm-proven" }
if ($HyperV) { $pyArgs += "--hyperv" }
if ($Live) { $pyArgs += "--live" }
& python @pyArgs
exit $LASTEXITCODE
