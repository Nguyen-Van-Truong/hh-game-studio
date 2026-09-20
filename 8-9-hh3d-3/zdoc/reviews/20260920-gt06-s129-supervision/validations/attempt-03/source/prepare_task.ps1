# Demand-only S129 adapter based on S119 task.ps1. Defaults to prepare only.
# Registration and start are separate explicit commands; never retry/resume.
param(
 [ValidateSet('prepare','register','start','status')][string]$Command='prepare',
 [Parameter(Mandatory=$true)][ValidatePattern('^gt06-s129-[a-z0-9-]{1,45}$')][string]$RunId
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$s129Base=$PSScriptRoot
$s129RequestPath=Join-Path $s129Base ('request-'+$RunId+'.json')
$s129TaskName='HHStudio.GT06.'+$RunId
$s129TaskDir=Join-Path $s129Base ('tasks\'+$RunId)
function Need([bool]$Value,[string]$Code){if(!$Value){throw $Code}}
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function NewText([string]$Name,[string]$Value){
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($Value)
 $stream=[IO.File]::Open((Join-Path $s129TaskDir $Name),[IO.FileMode]::CreateNew)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function NewJson([string]$Name,$Value){NewText $Name (($Value|ConvertTo-Json -Depth 16)+"`n")}
function ReadTask($Folder){
 try{return $Folder.GetTask($s129TaskName)}catch{
  $failure=$_.Exception
  while($null -ne $failure){if($failure.HResult -eq -2147024894){return $null};$failure=$failure.InnerException}
  throw
 }
}
$s129Validation=Get-Content -LiteralPath (Join-Path $s129Base 'validation.json') -Raw|ConvertFrom-Json
Need ($s129Validation.status -ceq 'PASS' -and $s129Validation.engine_launched -eq $false) 'S129_VALIDATED_PROBES_REQUIRED'
foreach($pin in $s129Validation.source_pins.PSObject.Properties){Need ((Hash (Join-Path $s129Base $pin.Name)) -ceq $pin.Value) 'S129_VALIDATED_SOURCE_DRIFT'}
$s129Request=Get-Content -LiteralPath $s129RequestPath -Raw|ConvertFrom-Json
Need ($s129Request.run_id -ceq $RunId) 'S129_REQUEST_RUN_ID'
$s129Python=$s129Request.argv[0]
$s129Pythonw=Join-Path ([IO.Path]::GetDirectoryName($s129Python)) 'pythonw.exe'
$s129Observer=Join-Path $s129Base 'passive_observer.py'
$s129Check=& $s129Python -B $s129Observer --request $s129RequestPath --check
Need ($LASTEXITCODE -eq 0) 'S129_REQUEST_CHECK_FAILED'
$s129CheckValue=($s129Check -join "`n")|ConvertFrom-Json
Need ($s129CheckValue.checked -and !$s129CheckValue.launched) 'S129_REQUEST_CHECK_UNPROVEN'
$s129Identity=[Security.Principal.WindowsIdentity]::GetCurrent()
try{$s129Sid=$s129Identity.User.Value}finally{$s129Identity.Dispose()}
$s129Args='-B "'+$s129Observer+'" --request "'+$s129RequestPath+'"'
$s129Service=New-Object -ComObject 'Schedule.Service'
$s129Service.Connect()
$s129Folder=$s129Service.GetFolder('\')
$s129Task=ReadTask $s129Folder
function AssertTask($Task){
 $d=$Task.Definition;$s=$d.Settings;$a=$d.Actions.Item(1)
 $sid=$d.Principal.UserId
 if($sid -notmatch '^S-1-'){$sid=([Security.Principal.NTAccount]::new($sid)).Translate([Security.Principal.SecurityIdentifier]).Value}
 Need ($Task.Path -ceq ('\'+$s129TaskName) -and $sid -ceq $s129Sid -and $d.Principal.LogonType -eq 3 -and $d.Principal.RunLevel -eq 0) 'S129_TASK_IDENTITY'
 Need ($d.Triggers.Count -eq 0 -and $d.Actions.Count -eq 1 -and $a.Type -eq 0 -and $a.Path -ieq $s129Pythonw -and $a.Arguments -ceq $s129Args -and $a.WorkingDirectory -ieq $s129Base) 'S129_TASK_ACTION'
 Need ($s.MultipleInstances -eq 2 -and $s.RestartCount -eq 0 -and $s.Priority -eq 6 -and $s.Hidden -and $s.Enabled -and $s.AllowDemandStart) 'S129_TASK_SETTINGS'
 Need ([Xml.XmlConvert]::ToTimeSpan($s.ExecutionTimeLimit).TotalSeconds -eq $s129Request.scheduler_seconds) 'S129_TASK_BOUND'
 Need (!$s.StartWhenAvailable -and !$s.WakeToRun -and !$s.RunOnlyIfIdle -and !$s.RunOnlyIfNetworkAvailable -and !$s.DisallowStartIfOnBatteries -and !$s.StopIfGoingOnBatteries) 'S129_TASK_CONDITIONS'
}
if($Command -ceq 'prepare'){
 Need ($null -eq $s129Task -and !(Test-Path -LiteralPath $s129TaskDir)) 'S129_TASK_ALREADY_PREPARED'
 [void][IO.Directory]::CreateDirectory($s129TaskDir)
 $d=$s129Service.NewTask(0);$d.RegistrationInfo.Author=$s129Sid
 $d.RegistrationInfo.Description='S129 one-use passive launcher observer; no acceptance'
 $d.Principal.Id='HHStudioCurrentUser';$d.Principal.UserId=$s129Sid;$d.Principal.LogonType=3;$d.Principal.RunLevel=0;$d.Actions.Context='HHStudioCurrentUser'
 $s=$d.Settings;$s.Compatibility=2;$s.Enabled=$true;$s.AllowDemandStart=$true;$s.AllowHardTerminate=$true
 $s.MultipleInstances=2;$s.RestartCount=0;$s.Priority=6;$s.ExecutionTimeLimit=[Xml.XmlConvert]::ToString([TimeSpan]::FromSeconds($s129Request.scheduler_seconds))
 $s.Hidden=$true;$s.StartWhenAvailable=$false;$s.WakeToRun=$false;$s.RunOnlyIfIdle=$false;$s.RunOnlyIfNetworkAvailable=$false
 $s.DisallowStartIfOnBatteries=$false;$s.StopIfGoingOnBatteries=$false;$s.IdleSettings.StopOnIdleEnd=$false;$s.IdleSettings.RestartOnIdle=$false
 $a=$d.Actions.Create(0);$a.Path=$s129Pythonw;$a.Arguments=$s129Args;$a.WorkingDirectory=$s129Base
 NewText 'expected.xml' $d.XmlText
 NewJson 'prepared.json' @{request_sha256=Hash $s129RequestPath;xml_sha256=Hash (Join-Path $s129TaskDir 'expected.xml');pythonw_sha256=Hash $s129Pythonw;validation_sha256=Hash (Join-Path $s129Base 'validation.json');registered=$false;dispatched=$false;formal_acceptance=$false;observed_utc=[DateTime]::UtcNow.ToString('o')}
 Write-Output 'S129_PREPARED_ONLY_NOT_REGISTERED'
 exit 0
}
$s129Prepared=Get-Content -LiteralPath (Join-Path $s129TaskDir 'prepared.json') -Raw|ConvertFrom-Json
Need ((Hash $s129RequestPath) -ceq $s129Prepared.request_sha256 -and (Hash $s129Pythonw) -ceq $s129Prepared.pythonw_sha256 -and (Hash (Join-Path $s129Base 'validation.json')) -ceq $s129Prepared.validation_sha256) 'S129_PREPARED_PIN_DRIFT'
Need ((Hash (Join-Path $s129TaskDir 'expected.xml')) -ceq $s129Prepared.xml_sha256) 'S129_EXPECTED_XML_DRIFT'
if($Command -ceq 'register'){
 Need ($null -eq $s129Task) 'S129_TASK_ALREADY_REGISTERED'
 $xml=[IO.File]::ReadAllText((Join-Path $s129TaskDir 'expected.xml'))
 $s129Task=$s129Folder.RegisterTask($s129TaskName,$xml,2,$s129Sid,$null,3,$null)
 AssertTask $s129Task
 NewText 'registered.xml' ([string]$s129Task.Xml)
 NewJson 'registered.json' @{xml_sha256=Hash (Join-Path $s129TaskDir 'registered.xml');task_path=$s129Task.Path;registered=$true;dispatched=$false;observed_utc=[DateTime]::UtcNow.ToString('o')}
 Write-Output 'S129_REGISTERED_NOT_DISPATCHED'
 exit 0
}
Need ($null -ne $s129Task) 'S129_TASK_NOT_REGISTERED'
AssertTask $s129Task
$s129Registered=Get-Content -LiteralPath (Join-Path $s129TaskDir 'registered.json') -Raw|ConvertFrom-Json
Need ((Hash (Join-Path $s129TaskDir 'registered.xml')) -ceq $s129Registered.xml_sha256 -and [string]$s129Task.Xml -ceq [IO.File]::ReadAllText((Join-Path $s129TaskDir 'registered.xml'))) 'S129_REGISTERED_XML_DRIFT'
if($Command -ceq 'status'){
 [ordered]@{task_path=$s129Task.Path;state=[int]$s129Task.State;instances=$s129Task.GetInstances(0).Count;last_result=[long]$s129Task.LastTaskResult;last_run=$s129Task.LastRunTime.ToString('o');observed_utc=[DateTime]::UtcNow.ToString('o');scope='Scheduler state only; launcher exit requires retained-handle receipt; missing observer terminal remains UNKNOWN';formal_acceptance=$false}|ConvertTo-Json
 exit 0
}
foreach($candidate in $s129Folder.GetTasks(1)){
 if($candidate.Name -like 'HHStudio.GT06.*'){Need ($candidate.GetInstances(0).Count -eq 0 -and $candidate.State -in @(1,3)) 'S129_OTHER_GT06_ACTIVE'}
}
Need (!(Test-Path -LiteralPath (Join-Path $s129Base ('runs\'+$RunId)))) 'S129_RUN_ALREADY_USED'
NewJson 'dispatch-claim.json' @{task_path=$s129Task.Path;request_sha256=Hash $s129RequestPath;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
$instance=$s129Task.Run($null)
Need ($null -ne $instance -and ![string]::IsNullOrWhiteSpace($instance.InstanceGuid)) 'S129_DISPATCH_UNKNOWN_NO_RETRY'
NewJson 'dispatch.json' @{task_path=$s129Task.Path;instance_guid=[string]$instance.InstanceGuid;observed_utc=[DateTime]::UtcNow.ToString('o');scope='Dispatch only, not liveness or success';formal_acceptance=$false}
Write-Output 'S129_DISPATCHED_CHECK_RETAINED_HANDLE_RECEIPTS'
