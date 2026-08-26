#Requires -Version 5.1
<#
.SYNOPSIS
  Thin Windows wrapper around tools/godot/package.py.
#>
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Version = "",
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "package.py"
$pyArgs = @($Py, "--out", $Out)
if ($Version) { $pyArgs += @("--version", $Version) }
if ($Sign) { $pyArgs += "--sign" }
& python @pyArgs
exit $LASTEXITCODE
