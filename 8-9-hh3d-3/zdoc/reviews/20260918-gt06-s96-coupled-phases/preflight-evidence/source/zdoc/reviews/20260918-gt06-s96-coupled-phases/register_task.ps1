# Fixed S96 demand-only task. Register records pins; only start dispatches.
param(
  [ValidateSet('register','start','status','delete')][string]$Command='status',
  [string]$HelperSha256='',
  [string]$PythonExe=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$studio=Join-Path $root 'studio'
$entry=Join-Path $PSScriptRoot 'coupled_phases.py'
$launch=Join-Path $PSScriptRoot 'launch-01'
$runId='gt06-s96-coupled-phases-01'
$preflightId='gt06-s96-coupled-phases-preflight-01'
$sourceSha='564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752'
$profileSha='0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
$taskName='HHStudio.GT06.'+$runId
$arguments='-B "'+$entry+'" --observer'
$utf8=[Text.UTF8Encoding]::new($false)
function Need([bool]$ok,[string]$code){if(!$ok){throw $code}}
function Plain([string]$path){
  $cursor=[IO.Path]::GetFullPath($path)
  while($cursor){
    if(Test-Path -LiteralPath $cursor){Need (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'S96_TASK_REPARSE'}
    $parent=[IO.Directory]::GetParent($cursor);if($null -eq $parent){break};$cursor=$parent.FullName
  }
}
function Hash([string]$path){Plain $path;(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function WriteNew([string]$path,[string]$text){
  Plain $path;$bytes=$utf8.GetBytes($text)
  $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
  Need ([IO.File]::ReadAllText($path,$utf8) -ceq $text) 'S96_TASK_WRITE_READBACK'
}
function WriteJson([string]$path,$value){WriteNew $path (($value|ConvertTo-Json -Depth 30)+"`n")}
function Sid([string]$account){
  if($account -match '^S-'){return ([Security.Principal.SecurityIdentifier]::new($account)).Value}
  return ([Security.Principal.NTAccount]::new($account)).Translate([Security.Principal.SecurityIdentifier]).Value
}
function OwnTask($folder){
  try{return $folder.GetTask($taskName)}catch{
    $failure=$_.Exception
    while($null -ne $failure){if($failure.HResult -eq -2147024894){return $null};$failure=$failure.InnerException}
    throw
  }
}
function Describe([string]$python){
  $raw=& $python -B $entry --describe
  Need ($LASTEXITCODE -eq 0) 'S96_TASK_DESCRIBE_EXIT'
  $value=($raw -join "`n")|ConvertFrom-Json
  Need (!$value.launch_performed -and !$value.formal_acceptance -and !$value.eligible_for_dataset) 'S96_TASK_DESCRIBE_SCOPE'
  return $value.request
}
function CheckBinding($request){
  Need ($request.schema -ceq 'HH-GT06-S96-COUPLED-REQUEST-1' -and $request.run_id -ceq $runId -and $request.preflight_id -ceq $preflightId) 'S96_TASK_IDENTITY'
  Need ($request.source_sha256 -ceq $sourceSha -and $request.profile_sha256 -ceq $profileSha -and $request.wall_seconds -eq 7530 -and $request.outer_process_limit -eq 7) 'S96_TASK_PROFILE'
  Need (!$request.formal_acceptance -and !$request.eligible_for_dataset -and !$request.full_benchmark -and $request.working_directory -ieq $studio) 'S96_TASK_SCOPE'
}
function CheckPins($request){
  CheckBinding $request
  foreach($item in $request.helper_files.PSObject.Properties){Need ((Hash (Join-Path $root $item.Name)) -ceq $item.Value) ('S96_TASK_HELPER_DRIFT:'+ $item.Name)}
  $current=Describe $request.python
  Need ($current.source_sha256 -ceq $request.source_sha256 -and $current.helper_sha256 -ceq $request.helper_sha256 -and $current.python_sha256 -ceq $request.python_sha256 -and $current.pythonw_sha256 -ceq $request.pythonw_sha256 -and $current.godot_sha256 -ceq $request.godot_sha256) 'S96_TASK_PIN_DRIFT'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
try{$userSid=$identity.User.Value}finally{$identity.Dispose()}
function AssertTask($task,$request){
  CheckBinding $request
  $definition=$task.Definition;$settings=$definition.Settings
  Need ($task.Path -ceq ('\'+$taskName)) 'S96_TASK_PATH'
  Need ((Sid $definition.Principal.UserId) -ceq $userSid -and $definition.Principal.LogonType -eq 3 -and $definition.Principal.RunLevel -eq 0) 'S96_TASK_PRINCIPAL'
  [xml]$xml=[string]$task.Xml;$ns=[Xml.XmlNamespaceManager]::new($xml.NameTable)
  $ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
  $principal=$xml.SelectNodes('/t:Task/t:Principals/t:Principal',$ns)
  Need ($principal.Count -eq 1 -and $principal.Item(0).GetAttribute('id') -ceq 'HHStudioCurrentUser') 'S96_TASK_XML_PRINCIPAL'
  $users=$principal.Item(0).SelectNodes('t:UserId',$ns)
  Need ($users.Count -eq 1 -and $users.Item(0).InnerText -ceq $userSid) 'S96_TASK_XML_SID'
  Need ($definition.Triggers.Count -eq 0 -and $definition.Actions.Count -eq 1) 'S96_TASK_DEMAND_ONLY'
  $action=$definition.Actions.Item(1)
  Need ($action.Type -eq 0 -and $action.Path -ieq $request.pythonw -and $action.Arguments -ceq $arguments -and $action.WorkingDirectory -ieq $studio) 'S96_TASK_ACTION'
  Need ($settings.MultipleInstances -eq 2 -and $settings.RestartCount -eq 0 -and $settings.Priority -eq 6) 'S96_TASK_RESTART_OR_PRIORITY'
  Need ([Xml.XmlConvert]::ToTimeSpan($settings.ExecutionTimeLimit) -eq [TimeSpan]::FromMinutes(130)) 'S96_TASK_WALL'
  Need ($settings.AllowDemandStart -and $settings.AllowHardTerminate -and $settings.Enabled -and $settings.Hidden) 'S96_TASK_SETTINGS'
  Need (!$settings.StartWhenAvailable -and !$settings.WakeToRun -and !$settings.RunOnlyIfIdle -and !$settings.RunOnlyIfNetworkAvailable) 'S96_TASK_CONDITIONS'
  Need (!$settings.DisallowStartIfOnBatteries -and !$settings.StopIfGoingOnBatteries -and !$settings.IdleSettings.StopOnIdleEnd -and !$settings.IdleSettings.RestartOnIdle) 'S96_TASK_POWER'
}

Plain $studio;Plain $launch
$service=New-Object -ComObject 'Schedule.Service';$service.Connect();$folder=$service.GetFolder('\')
$task=OwnTask $folder
if($Command -eq 'register'){
  Need ($null -eq $task -and !(Test-Path -LiteralPath $launch)) 'S96_TASK_REGISTERED_OR_USED'
  Need ($HelperSha256 -cmatch '^[0-9a-f]{64}$') 'S96_TASK_REQUIRED_HELPER_PIN'
  Need (!(Test-Path -LiteralPath (Join-Path $studio ('.local\reviews\'+$runId))) -and !(Test-Path -LiteralPath (Join-Path $studio ('.local\reviews\'+$preflightId)))) 'S96_TASK_IDS_USED'
  if([string]::IsNullOrWhiteSpace($PythonExe)){$PythonExe=(Get-Command python.exe -CommandType Application -ErrorAction Stop|Select-Object -First 1).Source}
  $python=[IO.Path]::GetFullPath($PythonExe)
  Need ([IO.Path]::GetFileName($python) -ieq 'python.exe') 'S96_TASK_PYTHON_COMPANION'
  $request=Describe $python
  CheckBinding $request
  Need ($request.helper_sha256 -ceq $HelperSha256) 'S96_TASK_HELPER_PIN'
  $null=New-Item -ItemType Directory -Path $launch -ErrorAction Stop
  WriteJson (Join-Path $launch 'request.json') $request
  $definition=$service.NewTask(0)
  $definition.RegistrationInfo.Author=$userSid
  $definition.RegistrationInfo.Description='S96 coupled phase diagnostic; one use, explicit demand start, no acceptance'
  $definition.Principal.Id='HHStudioCurrentUser';$definition.Principal.UserId=$userSid;$definition.Principal.LogonType=3;$definition.Principal.RunLevel=0
  $definition.Actions.Context='HHStudioCurrentUser'
  $settings=$definition.Settings
  $settings.Compatibility=2;$settings.Enabled=$true;$settings.AllowDemandStart=$true;$settings.AllowHardTerminate=$true
  $settings.MultipleInstances=2;$settings.RestartCount=0;$settings.Priority=6;$settings.ExecutionTimeLimit='PT130M'
  $settings.Hidden=$true;$settings.StartWhenAvailable=$false;$settings.WakeToRun=$false;$settings.RunOnlyIfIdle=$false;$settings.RunOnlyIfNetworkAvailable=$false
  $settings.DisallowStartIfOnBatteries=$false;$settings.StopIfGoingOnBatteries=$false;$settings.IdleSettings.StopOnIdleEnd=$false;$settings.IdleSettings.RestartOnIdle=$false
  $action=$definition.Actions.Create(0);$action.Path=$request.pythonw;$action.Arguments=$arguments;$action.WorkingDirectory=$studio
  $task=$folder.RegisterTaskDefinition($taskName,$definition,2,$userSid,$null,3,$null)
  AssertTask $task $request
  WriteNew (Join-Path $launch 'task.xml') ([string]$task.Xml)
  $receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;registered_utc=[DateTime]::UtcNow.ToString('o');dispatch_performed=$false;request_sha256=(Hash (Join-Path $launch 'request.json'));formal_acceptance=$false}
  WriteJson (Join-Path $launch 'task-registered.json') $receipt
  $receipt|ConvertTo-Json -Depth 10
  exit 0
}

Need ($null -ne $task) 'S96_TASK_NOT_REGISTERED'
$request=Get-Content -LiteralPath (Join-Path $launch 'request.json') -Raw|ConvertFrom-Json
AssertTask $task $request
Need ([IO.File]::ReadAllText((Join-Path $launch 'task.xml'),$utf8) -ceq [string]$task.Xml) 'S96_TASK_DEFINITION_CHANGED'
$instances=$task.GetInstances(0)
if($Command -eq 'status'){
  [ordered]@{task_path='\'+$taskName;run_id=$runId;state=[int]$task.State;instances=$instances.Count;last_task_result=[long]$task.LastTaskResult;last_run_time=$task.LastRunTime.ToString('o');formal_acceptance=$false;status_scope='Scheduler observation only; external actual exits and owned cleanup remain required'}|ConvertTo-Json -Depth 10
  exit 0
}
if($Command -eq 'delete'){
  Need ($instances.Count -eq 0 -and $task.State -in @(1,3)) 'S96_TASK_ACTIVE_DELETE_REFUSED'
  $folder.DeleteTask($taskName,0);Need ($null -eq (OwnTask $folder)) 'S96_TASK_DELETE_UNPROVEN'
  $receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;deleted_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
  WriteJson (Join-Path $launch 'task-deleted.json') $receipt
  $receipt|ConvertTo-Json -Depth 10
  exit 0
}

CheckPins $request
Need (!(Test-Path -LiteralPath (Join-Path $studio ('.local\reviews\'+$runId)))) 'S96_TASK_RUN_USED'
Need (!(Test-Path -LiteralPath (Join-Path $launch 'dispatch-claim.json')) -and $instances.Count -eq 0) 'S96_TASK_ALREADY_DISPATCHED'
$preflight=Get-Content -LiteralPath (Join-Path $studio ('.local\reviews\'+$preflightId+'\preflight.json')) -Raw|ConvertFrom-Json
Need ($preflight.verified_import -and $preflight.base_source_closure_sha256 -ceq $sourceSha) 'S96_TASK_PREFLIGHT_REQUIRED'
foreach($item in $request.helper_files.PSObject.Properties){Need ($preflight.helper_files.($item.Name) -ceq $item.Value) 'S96_TASK_PREFLIGHT_HELPER_DRIFT'}
foreach($candidate in $folder.GetTasks(1)){
  if($candidate.Name -like 'HHStudio.GT06.*'){Need ($candidate.GetInstances(0).Count -eq 0 -and $candidate.State -in @(1,3)) 'S96_TASK_OTHER_GT06_ACTIVE'}
}
# Claim before the COM call: an uncertain dispatch cannot be silently retried.
WriteJson (Join-Path $launch 'dispatch-claim.json') ([ordered]@{run_id=$runId;claimed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false})
try{
  $running=$task.Run($null)
  Need ($null -ne $running -and ![string]::IsNullOrWhiteSpace($running.InstanceGuid)) 'S96_TASK_DISPATCH_UNPROVEN'
  $receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;requested_utc=[DateTime]::UtcNow.ToString('o');instance_guid=[string]$running.InstanceGuid;scheduler_state=[int]$running.State;dispatch_performed=$true;request_sha256=(Hash (Join-Path $launch 'request.json'));formal_acceptance=$false;status_scope='Dispatch only; no RUNNING, completion or acceptance claim'}
  WriteJson (Join-Path $launch 'task-start.json') $receipt
  $receipt|ConvertTo-Json -Depth 10
}catch{
  WriteJson (Join-Path $launch 'dispatch-failure.json') ([ordered]@{run_id=$runId;exception_class=$_.Exception.GetType().Name;hresult=$_.Exception.HResult;dispatch_uncertain=$true;formal_acceptance=$false})
  throw
}
