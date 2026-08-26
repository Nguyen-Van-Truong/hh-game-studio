#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/install.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string]$From = "",
    [string]$InstallRoot = "",
    [string]$Project = ""
)

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "install.py"
$pyArgs = @($Py, $Command)
if ($From) { $pyArgs += @("--from", $From) }
if ($InstallRoot) { $pyArgs += @("--install-root", $InstallRoot) }
if ($Project) { $pyArgs += @("--project", $Project) }
& python @pyArgs
exit $LASTEXITCODE
