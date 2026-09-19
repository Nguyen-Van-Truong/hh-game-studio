# Passive outer Python exit observer. The S106 runner owns/bounds engine Jobs.
param(
  [Parameter(Mandatory=$true)][ValidateSet('preflight','prefix')][string]$Mode,
  [Parameter(Mandatory=$true)][ValidatePattern('^gt06-s106-handles-[a-z0-9][a-z0-9-]{0,30}$')][string]$RunId,
  [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedHelperSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$taskHelper=Join-Path $taskRoot 'zdoc\reviews\20260919-gt06-s106-handle-boundary\owned_handles.py'
$taskObservedHash=(Get-FileHash -LiteralPath $taskHelper -Algorithm SHA256).Hash.ToLowerInvariant()
if($taskObservedHash -cne $ExpectedHelperSha256){throw 'S106_OUTER_HELPER_HASH'}
$taskPython=[string](Get-Command python -CommandType Application | Select-Object -First 1 -ExpandProperty Source)
if([string]::IsNullOrWhiteSpace($taskPython) -or !(Test-Path -LiteralPath $taskPython -PathType Leaf)){throw 'S106_OUTER_PYTHON_UNRESOLVED'}
$taskOutput=Join-Path $taskRoot ('studio\.local\reviews\'+$RunId+'-outer')
if(Test-Path -LiteralPath $taskOutput){throw 'S106_OUTER_OUTPUT_EXISTS'}
$null=New-Item -ItemType Directory -Path $taskOutput
function Write-NewReceipt([string]$Name,$Value){
  $receipt=Join-Path $taskOutput $Name
  $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 12)+"`n")
  $stream=[IO.File]::Open($receipt,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
  try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
$taskArgs=@('-B',('"'+$taskHelper+'"'),('--'+$Mode),'--run-id',$RunId)
Write-NewReceipt 'request.json' @{
  run_id=$RunId; mode=$Mode; observed_utc=[DateTime]::UtcNow.ToString('o');
  helper_sha256=$taskObservedHash; observer_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
  python=$taskPython; python_sha256=(Get-FileHash -LiteralPath $taskPython -Algorithm SHA256).Hash.ToLowerInvariant();
  formal_acceptance=$false; eligible_for_dataset=$false
}
$taskProcess=$null
$taskExit=$null
try{
  $taskProcess=Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'stdout.txt') -RedirectStandardError (Join-Path $taskOutput 'stderr.txt')
  # Retain this Process object and its handle; never reopen a numeric PID.
  $taskHandle=$taskProcess.Handle
  $taskStart=$taskProcess.StartTime.ToUniversalTime().ToString('o')
  Write-NewReceipt 'process-start.json' @{run_id=$RunId;pid=$taskProcess.Id;start_utc=$taskStart;executable=$taskPython;handle_retained=$true}
  $taskProcess.WaitForExit()
  $taskProcess.Refresh()
  $taskExit=$taskProcess.ExitCode
  Write-NewReceipt 'process-exit.json' @{run_id=$RunId;pid=$taskProcess.Id;start_utc=$taskStart;exit_code=$taskExit;observed_utc=[DateTime]::UtcNow.ToString('o');source='retained System.Diagnostics.Process after WaitForExit';forced_by_outer_observer=$false}
}catch{
  Write-NewReceipt 'observer-error.json' @{run_id=$RunId;error_type=$_.Exception.GetType().FullName;actual_exit=$taskExit;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
  throw
}finally{
  if($null -ne $taskProcess){
    $taskProcess.Dispose()
    Write-NewReceipt 'observer-close.json' @{run_id=$RunId;managed_process_disposed=$true;native_close_bool_observed=$false;formal_acceptance=$false}
  }
}
Write-Output ('S106_OUTER_ACTUAL_EXIT='+$taskExit+' RUN='+$RunId)
exit $taskExit
