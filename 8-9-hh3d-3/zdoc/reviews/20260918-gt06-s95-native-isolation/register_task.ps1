# Fixed S95 native isolation task. Registration does NOT dispatch; start is explicit.
param(
  [ValidateSet('register','start','status','delete')][string]$Command='status',
  [string]$SourceSha256='',
  [string]$HelperSha256='',
  [string]$PythonExe=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$studio=Join-Path $root 'studio'
$owner=Join-Path $PSScriptRoot 'outer_owner.py'
$native=Join-Path $PSScriptRoot 'native_isolation.py'
$ownershipSource=Join-Path $root 'zdoc\reviews\20260918-gt06-s93-sparse-attribution\launch_observer.py'
$launch=Join-Path $PSScriptRoot 'launch-01'
$runId='gt06-s95-native-isolation-01'
$taskName='HHStudio.GT06.gt06-s95-native-isolation-01'
$arguments='-B "'+$owner+'" --observe'
$utf8=[Text.UTF8Encoding]::new($false)

function Need([bool]$ok,[string]$code){if(!$ok){throw $code}}
function Plain([string]$path){
  $cursor=[IO.Path]::GetFullPath($path)
  while($cursor){
    if(Test-Path -LiteralPath $cursor){Need (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'TASK_REPARSE'}
    $parent=[IO.Directory]::GetParent($cursor);if($null -eq $parent){break};$cursor=$parent.FullName
  }
}
function Hash([string]$path){Plain $path;(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function WriteNew([string]$path,[string]$text){
  Plain $path;$bytes=$utf8.GetBytes($text)
  $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
  Need ([IO.File]::ReadAllText($path,$utf8) -ceq $text) 'TASK_WRITE_READBACK'
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
  $raw=& $python -B $native --describe
  Need ($LASTEXITCODE -eq 0) 'TASK_DESCRIBE_EXIT'
  $value=($raw -join "`n")|ConvertFrom-Json
  Need (!$value.launch_performed -and !$value.formal_acceptance -and !$value.eligible_for_dataset) 'TASK_DESCRIBE_SCOPE'
  return $value.pins
}
function CheckFreshOutput(){
  Need (!(Test-Path -LiteralPath (Join-Path $studio ('.local\reviews\'+$runId)))) 'TASK_NATIVE_RUN_USED'
  Need (!(Test-Path -LiteralPath (Join-Path $studio ('.local\reviews\'+$runId+'-outer')))) 'TASK_OUTER_RUN_USED'
}
function CheckRequest($request){
  Need ($request.schema -ceq 'HH-GT06-S95-NATIVE-OUTER-1' -and $request.run_id -ceq $runId -and $request.wall_seconds -eq 2160 -and !$request.formal_acceptance) 'TASK_REQUEST_BINDING'
  Need ($request.working_directory -ieq $studio) 'TASK_WORKING_DIRECTORY'
  Need ((Hash $request.python) -ceq $request.python_sha256 -and (Hash $request.pythonw) -ceq $request.pythonw_sha256) 'TASK_PYTHON_DRIFT'
  Need ((Hash $ownershipSource) -ceq $request.ownership_source_sha256) 'TASK_OWNERSHIP_SOURCE_DRIFT'
  foreach($property in $request.outer_files.PSObject.Properties){Need ((Hash (Join-Path $PSScriptRoot $property.Name)) -ceq $property.Value) 'TASK_OUTER_SOURCE_DRIFT'}
  $pins=Describe $request.python
  Need ($pins.source_closure_sha256 -ceq $request.source_sha256 -and $pins.helper_closure_sha256 -ceq $request.helper_sha256 -and $pins.profile_sha256 -ceq $request.native_pins.profile_sha256) 'TASK_NATIVE_PINS_CHANGED'
}

$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
try{$userSid=$identity.User.Value}finally{$identity.Dispose()}
function AssertTask($task,$request){
  $definition=$task.Definition;$settings=$definition.Settings
  Need ($task.Path -ceq ('\'+$taskName)) 'TASK_PATH'
  Need ((Sid $definition.Principal.UserId) -ceq $userSid -and $definition.Principal.LogonType -eq 3 -and $definition.Principal.RunLevel -eq 0) 'TASK_INTERACTIVE_CURRENT_USER'
  Need ($definition.Triggers.Count -eq 0 -and $definition.Actions.Count -eq 1) 'TASK_DEMAND_ONLY'
  $action=$definition.Actions.Item(1)
  Need ($action.Type -eq 0 -and $action.Path -ieq $request.pythonw -and $action.Arguments -ceq $arguments -and $action.WorkingDirectory -ieq $studio) 'TASK_ACTION'
  Need ($settings.MultipleInstances -eq 2 -and $settings.RestartCount -eq 0 -and $settings.Priority -eq 6) 'TASK_NO_RESTART'
  Need ([Xml.XmlConvert]::ToTimeSpan($settings.ExecutionTimeLimit) -eq [TimeSpan]::FromMinutes(40)) 'TASK_FIXED_WALL'
  Need ($settings.AllowDemandStart -and $settings.AllowHardTerminate -and $settings.Enabled -and $settings.Hidden) 'TASK_SETTINGS'
  Need (!$settings.StartWhenAvailable -and !$settings.WakeToRun -and !$settings.RunOnlyIfIdle -and !$settings.RunOnlyIfNetworkAvailable) 'TASK_CONDITIONS'
  Need (!$settings.DisallowStartIfOnBatteries -and !$settings.StopIfGoingOnBatteries -and !$settings.IdleSettings.StopOnIdleEnd -and !$settings.IdleSettings.RestartOnIdle) 'TASK_POWER'
}

Plain $studio;Plain $launch
$service=New-Object -ComObject 'Schedule.Service';$service.Connect();$folder=$service.GetFolder('\')
$task=OwnTask $folder
if($Command -eq 'register'){
  Need ($null -eq $task -and !(Test-Path -LiteralPath $launch)) 'TASK_ALREADY_REGISTERED_OR_USED'
  Need ($SourceSha256 -cmatch '^[0-9a-f]{64}$' -and $HelperSha256 -cmatch '^[0-9a-f]{64}$') 'TASK_REQUIRED_PINS'
  CheckFreshOutput
  if([string]::IsNullOrWhiteSpace($PythonExe)){$PythonExe=(Get-Command python.exe -CommandType Application -ErrorAction Stop|Select-Object -First 1).Source}
  $python=[IO.Path]::GetFullPath($PythonExe)
  Need ([IO.Path]::GetFileName($python) -ieq 'python.exe') 'TASK_CONSOLE_COMPANION'
  $pythonw=Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
  $pins=Describe $python
  Need ($pins.source_closure_sha256 -ceq $SourceSha256 -and $pins.helper_closure_sha256 -ceq $HelperSha256) 'TASK_PIN_MISMATCH'
  $request=[ordered]@{schema='HH-GT06-S95-NATIVE-OUTER-1';run_id=$runId;source_sha256=$SourceSha256;helper_sha256=$HelperSha256;native_pins=$pins;outer_files=[ordered]@{'outer_owner.py'=(Hash $owner);'register_task.ps1'=(Hash $PSCommandPath)};ownership_source_sha256=(Hash $ownershipSource);python=$python;pythonw=$pythonw;python_sha256=(Hash $python);pythonw_sha256=(Hash $pythonw);working_directory=$studio;wall_seconds=2160;formal_acceptance=$false}
  $null=New-Item -ItemType Directory -Path $launch -ErrorAction Stop
  WriteJson (Join-Path $launch 'request.json') $request
  $definition=$service.NewTask(0)
  $definition.RegistrationInfo.Author=$userSid
  $definition.RegistrationInfo.Description='S95 native-only diagnostic; fixed one-use demand dispatch; no acceptance'
  $definition.Principal.Id='HHStudioCurrentUser';$definition.Principal.UserId=$userSid;$definition.Principal.LogonType=3;$definition.Principal.RunLevel=0
  $definition.Actions.Context='HHStudioCurrentUser'
  $settings=$definition.Settings
  $settings.Compatibility=2;$settings.Enabled=$true;$settings.AllowDemandStart=$true;$settings.AllowHardTerminate=$true
  $settings.MultipleInstances=2;$settings.RestartCount=0;$settings.Priority=6;$settings.ExecutionTimeLimit='PT40M'
  $settings.Hidden=$true;$settings.StartWhenAvailable=$false;$settings.WakeToRun=$false;$settings.RunOnlyIfIdle=$false;$settings.RunOnlyIfNetworkAvailable=$false
  $settings.DisallowStartIfOnBatteries=$false;$settings.StopIfGoingOnBatteries=$false;$settings.IdleSettings.StopOnIdleEnd=$false;$settings.IdleSettings.RestartOnIdle=$false
  $action=$definition.Actions.Create(0);$action.Path=$pythonw;$action.Arguments=$arguments;$action.WorkingDirectory=$studio
  $task=$folder.RegisterTaskDefinition($taskName,$definition,2,$userSid,$null,3,$null)
  $readRequest=Get-Content -LiteralPath (Join-Path $launch 'request.json') -Raw|ConvertFrom-Json
  AssertTask $task $readRequest
  WriteNew (Join-Path $launch 'task.xml') ([string]$task.Xml)
  $receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;registered_utc=[DateTime]::UtcNow.ToString('o');dispatch_performed=$false;status_scope='Registered only; explicit start remains required';request_sha256=(Hash (Join-Path $launch 'request.json'));formal_acceptance=$false}
  WriteJson (Join-Path $launch 'task-registered.json') $receipt
  $receipt|ConvertTo-Json -Depth 10
  exit 0
}

Need ($null -ne $task) 'TASK_NOT_REGISTERED'
$request=Get-Content -LiteralPath (Join-Path $launch 'request.json') -Raw|ConvertFrom-Json
AssertTask $task $request
Need ([IO.File]::ReadAllText((Join-Path $launch 'task.xml'),$utf8) -ceq [string]$task.Xml) 'TASK_DEFINITION_CHANGED'
$instances=$task.GetInstances(0)
if($Command -eq 'status'){
  [ordered]@{task_path='\'+$taskName;run_id=$runId;state=[int]$task.State;instances=$instances.Count;last_task_result=[long]$task.LastTaskResult;last_run_time=$task.LastRunTime.ToString('o');formal_acceptance=$false;status_scope='Scheduler observation only; terminal.json and actual supervisor/helper captures are required'}|ConvertTo-Json -Depth 10
  exit 0
}
if($Command -eq 'delete'){
  Need ($instances.Count -eq 0 -and $task.State -in @(1,3)) 'TASK_ACTIVE_DELETE_REFUSED'
  $folder.DeleteTask($taskName,0);Need ($null -eq (OwnTask $folder)) 'TASK_DELETE_UNPROVEN'
  $receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;deleted_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
  WriteJson (Join-Path $launch 'task-deleted.json') $receipt
  $receipt|ConvertTo-Json -Depth 10
  exit 0
}

# start: verify the current pin set immediately before the one demand dispatch.
CheckRequest $request
CheckFreshOutput
Need (!(Test-Path -LiteralPath (Join-Path $launch 'task-start.json')) -and $instances.Count -eq 0) 'TASK_ALREADY_DISPATCHED'
foreach($candidate in $folder.GetTasks(1)){
  if($candidate.Name -like 'HHStudio.GT06.*'){Need ($candidate.GetInstances(0).Count -eq 0 -and $candidate.State -in @(1,3)) 'TASK_OTHER_GT06_ACTIVE'}
}
$running=$task.Run($null)
Need ($null -ne $running -and ![string]::IsNullOrWhiteSpace($running.InstanceGuid)) 'TASK_DISPATCH_UNPROVEN'
$receipt=[ordered]@{task_path='\'+$taskName;run_id=$runId;requested_utc=[DateTime]::UtcNow.ToString('o');instance_guid=[string]$running.InstanceGuid;scheduler_state=[int]$running.State;dispatch_performed=$true;request_sha256=(Hash (Join-Path $launch 'request.json'));formal_acceptance=$false;status_scope='Dispatch receipt only; this does not claim RUNNING, completion or acceptance'}
WriteJson (Join-Path $launch 'task-start.json') $receipt
$receipt|ConvertTo-Json -Depth 10
