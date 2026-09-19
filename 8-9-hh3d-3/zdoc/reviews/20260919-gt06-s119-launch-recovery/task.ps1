# Fixed, one-use tasks. Scheduler owns launch; no repeat trigger or retry.
param(
 [ValidateSet('register','start','status','delete')][string]$Command='status',
 [ValidateSet('probe','diagnostic')][string]$Mode='probe'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$s119Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$s119Name='HHStudio.GT06.gt06-s119-'+$Mode+'-01'
$s119Dir=Join-Path $PSScriptRoot ('task-'+$Mode)
$s119Entry=Join-Path $PSScriptRoot 'launch.ps1'
$s119Helper=Join-Path $PSScriptRoot $(if($Mode -ceq 'probe'){'launcher_probe.py'}else{'lookup_boundary.py'})
$s119Arguments='-NoProfile -NonInteractive -WindowStyle Hidden -File "'+$s119Entry+'" -Mode '+$Mode
$s119Identity=[Security.Principal.WindowsIdentity]::GetCurrent()
try{$s119Sid=$s119Identity.User.Value}finally{$s119Identity.Dispose()}
function Need([bool]$value,[string]$code){if(!$value){throw $code}}
function Plain([string]$path){
 $cursor=[IO.Path]::GetFullPath($path)
 while($cursor){
  if(Test-Path -LiteralPath $cursor){Need (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'S119_REPARSE'}
  $parent=[IO.Directory]::GetParent($cursor);if($null -eq $parent){break};$cursor=$parent.FullName
 }
}
function Hash([string]$path){Plain $path;(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function NewJson($name,$value){
 $path=Join-Path $s119Dir $name;Plain $path
 $bytes=[Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Depth 16)+"`n")
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function ReadTask($folder){
 try{return $folder.GetTask($s119Name)}catch{
  $errorObject=$_.Exception
  while($null -ne $errorObject){if($errorObject.HResult -eq -2147024894){return $null};$errorObject=$errorObject.InnerException}
  throw
 }
}
function AssertTask($task,$request){
 $d=$task.Definition;$s=$d.Settings;$a=$d.Actions.Item(1)
 Need ($task.Path -ceq ('\'+$s119Name) -and $request.mode -ceq $Mode -and $request.task_name -ceq $s119Name) 'S119_TASK_BINDING'
 $sid=$d.Principal.UserId
 if($sid -notmatch '^S-1-'){$sid=([Security.Principal.NTAccount]::new($sid)).Translate([Security.Principal.SecurityIdentifier]).Value}
 Need ($sid -ceq $s119Sid -and $d.Principal.LogonType -eq 3 -and $d.Principal.RunLevel -eq 0) 'S119_TASK_PRINCIPAL'
 Need ($d.Triggers.Count -eq 0 -and $d.Actions.Count -eq 1 -and $a.Type -eq 0) 'S119_TASK_DEMAND_ONLY'
 Need ($a.Path -ieq $request.shell -and $a.Arguments -ceq $s119Arguments -and $a.WorkingDirectory -ieq $PSScriptRoot) 'S119_TASK_ACTION'
 Need ($s.MultipleInstances -eq 2 -and $s.RestartCount -eq 0 -and $s.Priority -eq 6) 'S119_TASK_RETRY_OR_PRIORITY'
 $minutes=if($Mode -ceq 'probe'){2}else{24}
 Need ([Xml.XmlConvert]::ToTimeSpan($s.ExecutionTimeLimit) -eq [TimeSpan]::FromMinutes($minutes)) 'S119_TASK_WALL'
 Need ($s.AllowDemandStart -and $s.AllowHardTerminate -and $s.Enabled -and $s.Hidden) 'S119_TASK_ENABLE'
 Need (!$s.StartWhenAvailable -and !$s.WakeToRun -and !$s.RunOnlyIfIdle -and !$s.RunOnlyIfNetworkAvailable) 'S119_TASK_CONDITIONS'
 Need (!$s.DisallowStartIfOnBatteries -and !$s.StopIfGoingOnBatteries -and !$s.IdleSettings.StopOnIdleEnd -and !$s.IdleSettings.RestartOnIdle) 'S119_TASK_POWER'
}
Plain $s119Dir;Plain $s119Root
$svc=New-Object -ComObject 'Schedule.Service';$svc.Connect();$folder=$svc.GetFolder('\')
$task=ReadTask $folder
if($Command -ceq 'register'){
 Need ($null -eq $task -and !(Test-Path -LiteralPath $s119Dir)) 'S119_TASK_ALREADY_USED'
 $shell=(Get-Process -Id $PID).Path
 Need ([IO.Path]::GetFileName($shell) -ieq 'pwsh.exe') 'S119_REQUIRES_PWSH'
 $python=(Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
 $pins=[ordered]@{}
 foreach($path in @($shell,$python,$s119Entry,$PSCommandPath,$s119Helper)){$pins[$path]=Hash $path}
 if($Mode -ceq 'diagnostic'){
  foreach($relative in @('zdoc/reviews/20260919-gt06-s102-observability/preflight.py','zdoc/reviews/20260919-gt06-s114-history-replay/history_replay.py')){
   $path=Join-Path $s119Root $relative;$pins[$path]=Hash $path
  }
 }
 [void][IO.Directory]::CreateDirectory($s119Dir)
 $request=[ordered]@{schema='S119_DEMAND_TASK_1';mode=$Mode;task_name=$s119Name;shell=$shell;python=$python;helper=$s119Helper;pins=$pins;formal_acceptance=$false;eligible_for_dataset=$false}
 NewJson 'request.json' $request
 $d=$svc.NewTask(0);$d.RegistrationInfo.Author=$s119Sid;$d.RegistrationInfo.Description='HH3D one-use diagnostic launcher; no acceptance'
 $d.Principal.Id='HHStudioCurrentUser';$d.Principal.UserId=$s119Sid;$d.Principal.LogonType=3;$d.Principal.RunLevel=0;$d.Actions.Context='HHStudioCurrentUser'
 $s=$d.Settings;$s.Compatibility=2;$s.Enabled=$true;$s.AllowDemandStart=$true;$s.AllowHardTerminate=$true
 $s.MultipleInstances=2;$s.RestartCount=0;$s.Priority=6;$s.ExecutionTimeLimit=$(if($Mode -ceq 'probe'){'PT2M'}else{'PT24M'})
 $s.Hidden=$true;$s.StartWhenAvailable=$false;$s.WakeToRun=$false;$s.RunOnlyIfIdle=$false;$s.RunOnlyIfNetworkAvailable=$false
 $s.DisallowStartIfOnBatteries=$false;$s.StopIfGoingOnBatteries=$false;$s.IdleSettings.StopOnIdleEnd=$false;$s.IdleSettings.RestartOnIdle=$false
 $a=$d.Actions.Create(0);$a.Path=$shell;$a.Arguments=$s119Arguments;$a.WorkingDirectory=$PSScriptRoot
 $task=$folder.RegisterTaskDefinition($s119Name,$d,2,$s119Sid,$null,3,$null)
 $request=Get-Content (Join-Path $s119Dir 'request.json') -Raw|ConvertFrom-Json
 AssertTask $task $request
 NewJson 'registered.json' @{task_path=$task.Path;xml=[string]$task.Xml;observed_utc=[DateTime]::UtcNow.ToString('o');dispatch_performed=$false}
 Write-Output 'S119_REGISTERED_NOT_DISPATCHED'
 exit 0
}
Need ($null -ne $task) 'S119_TASK_NOT_REGISTERED'
$request=Get-Content (Join-Path $s119Dir 'request.json') -Raw|ConvertFrom-Json
AssertTask $task $request
$registered=Get-Content (Join-Path $s119Dir 'registered.json') -Raw|ConvertFrom-Json
Need ([string]$task.Xml -ceq $registered.xml) 'S119_TASK_DEFINITION_CHANGED'
if($Command -ceq 'status'){
 [ordered]@{task_path=$task.Path;state=[int]$task.State;instances=$task.GetInstances(0).Count;last_result=[long]$task.LastTaskResult;last_run=$task.LastRunTime.ToString('o');observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}|ConvertTo-Json
 exit 0
}
if($Command -ceq 'delete'){
 Need ($task.GetInstances(0).Count -eq 0 -and $task.State -in @(1,3)) 'S119_ACTIVE_DELETE'
 $folder.DeleteTask($s119Name,0);Need ($null -eq (ReadTask $folder)) 'S119_DELETE_UNPROVEN'
 NewJson 'deleted.json' @{task_path='\'+$s119Name;observed_utc=[DateTime]::UtcNow.ToString('o')}
 exit 0
}
foreach($pin in $request.pins.PSObject.Properties){Need ((Hash $pin.Name) -ceq $pin.Value) 'S119_TASK_PIN_DRIFT'}
foreach($candidate in $folder.GetTasks(1)){
 if($candidate.Name -like 'HHStudio.GT06.*'){Need ($candidate.GetInstances(0).Count -eq 0 -and $candidate.State -in @(1,3)) 'S119_OTHER_GT06_ACTIVE'}
}
if($Mode -ceq 'diagnostic'){
 $proof=Get-Content (Join-Path $PSScriptRoot 'task-probe/supervisor-exit.json') -Raw|ConvertFrom-Json
 Need ($proof.actual_process_wait -and !$proof.forced_by_wrapper -and $proof.exit_code -eq 0) 'S119_PROBE_EXIT_REQUIRED'
 Need (!(Test-Path -LiteralPath (Join-Path $s119Root 'studio/.local/reviews/gt06-s119-lookup-boundary-01'))) 'S119_RUN_ALREADY_USED'
 $preflight=& $request.python -B $s119Helper --check
 Need ($LASTEXITCODE -eq 0) 'S119_SOURCE_CHECK_FAILED'
 NewJson 'source-check.json' (($preflight -join "`n")|ConvertFrom-Json)
}
NewJson 'dispatch-claim.json' @{task_path='\'+$s119Name;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
$instance=$task.Run($null)
Need ($null -ne $instance -and ![string]::IsNullOrWhiteSpace($instance.InstanceGuid)) 'S119_DISPATCH_UNKNOWN_NO_RETRY'
NewJson 'dispatch.json' @{task_path='\'+$s119Name;instance_guid=[string]$instance.InstanceGuid;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false;scope='Dispatch only, not liveness or success'}
Write-Output 'S119_DISPATCHED_CHECK_ACTUAL_LIVENESS'
