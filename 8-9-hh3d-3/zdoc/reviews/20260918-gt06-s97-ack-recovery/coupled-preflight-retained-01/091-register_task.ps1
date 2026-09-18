# Binding adapter only. Retained S96 implementation keeps demand-only dispatch.
param(
  [ValidateSet('register','start','status','delete')][string]$Command='status',
  [string]$HelperSha256='',
  [string]$PythonExe=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$s97Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
$s97Original=Join-Path $s97Root 'zdoc\reviews\20260918-gt06-s96-coupled-phases\register_task.ps1'
$s97Map=Join-Path $PSScriptRoot 'source-current.json'
function S97Need([bool]$ok,[string]$code){if(!$ok){throw $code}}
function S97Plain([string]$path){
  $cursor=[IO.Path]::GetFullPath($path)
  while($cursor){
    if(Test-Path -LiteralPath $cursor){S97Need (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'S97_TASK_REPARSE'}
    $parent=[IO.Directory]::GetParent($cursor);if($null -eq $parent){break};$cursor=$parent.FullName
  }
}
function S97Replace([string]$text,[string]$old,[string]$new,[int]$count){
  S97Need (([regex]::Matches($text,[regex]::Escape($old))).Count -eq $count) 'S97_TASK_ADAPTER_ANCHOR'
  return $text.Replace($old,$new)
}
S97Plain $s97Map;S97Plain $s97Original
S97Need (Test-Path -LiteralPath $s97Map -PathType Leaf) 'S97_TASK_SOURCE_MAP_PENDING'
$s97Freeze=Get-Content -LiteralPath $s97Map -Raw|ConvertFrom-Json
S97Need ($s97Freeze.freeze_status -ceq 'ROOT_FROZEN') 'S97_TASK_SOURCE_MAP_PENDING'
S97Need ($s97Freeze.source_closure_sha256 -cmatch '^[0-9a-f]{64}$' -and @($s97Freeze.source_files.PSObject.Properties).Count -eq 51) 'S97_TASK_SOURCE_MAP_INVALID'
S97Need ((Get-FileHash -LiteralPath $s97Original -Algorithm SHA256).Hash.ToLowerInvariant() -ceq '691ea6b4cf3fffc3859ec5cf2522fad1338f6e43e71b89dbc889ae8f594fa859') 'S97_TASK_RETAINED_SCRIPT'
$s97Script=[IO.File]::ReadAllText($s97Original)
$s97Script=S97Replace $s97Script '$PSScriptRoot' ("'"+$PSScriptRoot.Replace("'","''")+"'") 3
$s97Script=S97Replace $s97Script "'..\..\..'" "'..\..\..\..'" 1
$s97Script=S97Replace $s97Script 'gt06-s96-coupled-phases-01' 'gt06-s97-coupled-phases-01' 1
$s97Script=S97Replace $s97Script 'gt06-s96-coupled-phases-preflight-01' 'gt06-s97-coupled-phases-preflight-01' 1
$s97Script=S97Replace $s97Script '564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752' $s97Freeze.source_closure_sha256 1
$s97Script=S97Replace $s97Script 'HH-GT06-S96-COUPLED-REQUEST-1' 'HH-GT06-S97-COUPLED-REQUEST-1' 1
$s97Script=S97Replace $s97Script 'S96 coupled phase diagnostic;' 'S97 coupled phase diagnostic;' 1
& ([ScriptBlock]::Create($s97Script)) -Command $Command -HelperSha256 $HelperSha256 -PythonExe $PythonExe
