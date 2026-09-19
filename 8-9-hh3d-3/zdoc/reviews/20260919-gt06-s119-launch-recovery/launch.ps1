param([ValidateSet('probe','diagnostic')][string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$s119Dir=Join-Path $PSScriptRoot ('task-'+$Mode)
$s119Request=Get-Content -LiteralPath (Join-Path $s119Dir 'request.json') -Raw|ConvertFrom-Json
function WriteNew($name,$value){
    $bytes=[Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Depth 10)+"`n")
    $stream=[IO.File]::Open((Join-Path $s119Dir $name),[IO.FileMode]::CreateNew)
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
foreach($pin in $s119Request.pins.PSObject.Properties){
    if((Get-FileHash -LiteralPath $pin.Name -Algorithm SHA256).Hash.ToLowerInvariant() -cne $pin.Value){throw 'S119_LAUNCH_PIN_DRIFT'}
}
if($s119Request.mode -cne $Mode){throw 'S119_MODE_BINDING'}
WriteNew 'wrapper-start.json' @{pid=$PID;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
$s119Process=$null
try{
    $s119Args=@('-B',('"'+$s119Request.helper+'"'))
    if($Mode -ceq 'diagnostic'){$s119Args+='--launch'}
    $s119Process=Start-Process -FilePath $s119Request.python -ArgumentList $s119Args -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $s119Dir 'stdout.txt') -RedirectStandardError (Join-Path $s119Dir 'stderr.txt')
    WriteNew 'supervisor-start.json' @{pid=$s119Process.Id;executable=$s119Request.python;process_start_utc=$s119Process.StartTime.ToUniversalTime().ToString('o');observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
    $s119Limit=if($Mode -ceq 'probe'){60000}else{1260000}
    $s119TimedOut=-not $s119Process.WaitForExit($s119Limit)
    if($s119TimedOut){$s119Process.Kill($true);$s119Process.WaitForExit()}
    $s119Exit=$s119Process.ExitCode
    WriteNew 'supervisor-exit.json' @{pid=$s119Process.Id;exit_code=$s119Exit;observed_utc=[DateTime]::UtcNow.ToString('o');actual_process_wait=$true;forced_by_wrapper=$s119TimedOut;formal_acceptance=$false;scope='Actual supervisor exit only; nested target/Job/handle evidence stays separate'}
    if($s119TimedOut){exit 124}
    exit $s119Exit
}catch{
    WriteNew 'wrapper-failure.json' @{exception_class=$_.Exception.GetType().Name;hresult=$_.Exception.HResult;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
    throw
}finally{
    if($null -ne $s119Process){$s119Process.Dispose()}
}
