#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/compat.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string]$Repo = "",
    [string]$Project = "",
    [string]$Dest = "",
    [string]$Lock = "",
    [string]$OldLock = "",
    [string]$NewLock = "",
    [string]$Fixture = "",
    [string]$Suites = "",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "compat.py"
$pyArgs = @($Py, $Command)
if ($Repo) { $pyArgs += @("--repo", $Repo) }
if ($Project) { $pyArgs += @("--project", $Project) }
if ($Dest) { $pyArgs += @("--dest", $Dest) }
if ($Lock) { $pyArgs += @("--lock", $Lock) }
if ($OldLock) { $pyArgs += @("--old-lock", $OldLock) }
if ($NewLock) { $pyArgs += @("--new-lock", $NewLock) }
if ($Fixture) { $pyArgs += @("--fixture", $Fixture) }
if ($Suites) { $pyArgs += @("--suites", $Suites) }
if ($Apply) { $pyArgs += "--apply" }
& python @pyArgs
exit $LASTEXITCODE
