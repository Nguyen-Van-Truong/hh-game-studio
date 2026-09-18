# Fixed S91 demand-only scheduler dispatch. No periodic triggers or auto retry.
param([ValidateSet('register','status','delete')][string]$Command='status')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$studio=Join-Path $root 'studio'
$observer=Join-Path $PSScriptRoot 'launch_observer.py'
$launch=Join-Path $PSScriptRoot 'launch-02'
$taskName='HHStudio.GT06.gt06-s91-sparse-attribution-01'
$utf8=New-Object Text.UTF8Encoding($false)
function Need([bool]$ok,[string]$code){if(!$ok){throw $code}}
function CanonicalSid([string]$account){
  Need (![string]::IsNullOrWhiteSpace($account)) 'TASK_PRINCIPAL_EMPTY'
  if($account -match '^S-'){
    return ([Security.Principal.SecurityIdentifier]::new($account)).Value
  }
  return ([Security.Principal.NTAccount]::new($account)).Translate([Security.Principal.SecurityIdentifier]).Value
}
function Plain([string]$path){
  $cursor=[IO.Path]::GetFullPath($path)
  while($cursor){
    if(Test-Path -LiteralPath $cursor){Need (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'TASK_REPARSE'}
    $parent=[IO.Directory]::GetParent($cursor);if($null -eq $parent){break};$cursor=$parent.FullName
  }
}
function Hash([string]$path){Plain $path;(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function WriteNew([string]$path,[string]$value){
  Plain $path;$bytes=$utf8.GetBytes($value)
  $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
  Need ([IO.File]::ReadAllText($path,$utf8) -ceq $value) 'TASK_WRITE_READBACK'
}
function WriteJson([string]$path,$value){WriteNew $path (($value|ConvertTo-Json -Depth 15)+"`n")}
function GetOwnTask($folder){
  try{return $folder.GetTask($taskName)}catch{
    $failure=$_.Exception
    while($null -ne $failure){if($failure.HResult -eq -2147024894){return $null};$failure=$failure.InnerException}
    throw
  }
}
$python=[IO.Path]::GetFullPath((Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source)
$pythonw=Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
$arguments='-B "'+$observer+'" --observer'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
try{$sid=$identity.User.Value}finally{$identity.Dispose()}
function AssertTask($task){
  $def=$task.Definition;$settings=$def.Settings
  Need ($task.Path -ceq ('\'+$taskName)) 'TASK_PATH'
  Need ((CanonicalSid $def.Principal.UserId) -ceq $sid -and $def.Principal.LogonType -eq 3 -and $def.Principal.RunLevel -eq 0) 'TASK_PRINCIPAL'
  [xml]$taskXml=[string]$task.Xml
  $namespaces=[Xml.XmlNamespaceManager]::new($taskXml.NameTable)
  $namespaces.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
  $principals=$taskXml.SelectNodes('/t:Task/t:Principals/t:Principal',$namespaces)
  Need ($principals.Count -eq 1 -and $principals.Item(0).GetAttribute('id') -ceq 'HHStudioCurrentUser') 'TASK_XML_PRINCIPAL'
  $xmlUsers=$principals.Item(0).SelectNodes('t:UserId',$namespaces)
  Need ($xmlUsers.Count -eq 1 -and $xmlUsers.Item(0).InnerText -ceq $sid) 'TASK_XML_PRINCIPAL_SID'
  Need ($def.Triggers.Count -eq 0 -and $def.Actions.Count -eq 1) 'TASK_TRIGGERS'
  $action=$def.Actions.Item(1)
  Need ($action.Type -eq 0 -and $action.Path -ieq $pythonw -and $action.Arguments -ceq $arguments -and $action.WorkingDirectory -ieq $studio) 'TASK_ACTION'
  Need ($settings.MultipleInstances -eq 2 -and $settings.RestartCount -eq 0 -and $settings.Priority -eq 6) 'TASK_RESTART_OR_PRIORITY'
  Need ([Xml.XmlConvert]::ToTimeSpan($settings.ExecutionTimeLimit) -eq [TimeSpan]::FromMinutes(130)) 'TASK_WALL'
  Need ($settings.AllowDemandStart -and $settings.AllowHardTerminate -and $settings.Enabled) 'TASK_DEMAND'
  Need (!$settings.StartWhenAvailable -and !$settings.WakeToRun -and !$settings.RunOnlyIfIdle -and !$settings.RunOnlyIfNetworkAvailable) 'TASK_CONDITIONS'
  Need (!$settings.DisallowStartIfOnBatteries -and !$settings.StopIfGoingOnBatteries -and !$settings.IdleSettings.StopOnIdleEnd -and !$settings.IdleSettings.RestartOnIdle) 'TASK_IDLE_POWER'
}
Plain $studio;Plain $launch
$service=New-Object -ComObject 'Schedule.Service';$service.Connect();$folder=$service.GetFolder('\')
$task=GetOwnTask $folder
if($Command -ne 'register'){
  Need ($null -ne $task) 'TASK_NOT_REGISTERED'
  AssertTask $task
  Need ([IO.File]::ReadAllText((Join-Path $launch 'task.xml'),$utf8) -ceq [string]$task.Xml) 'TASK_XML_CHANGED'
  $instances=$task.GetInstances(0)
  if($Command -eq 'delete'){
    Need ($instances.Count -eq 0 -and $task.State -in @(1,3)) 'TASK_RUNNING_DELETE_REFUSED'
    $folder.DeleteTask($taskName,0);Need ($null -eq (GetOwnTask $folder)) 'TASK_DELETE_UNPROVEN'
    $receipt=[ordered]@{task_path='\'+$taskName;deleted_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
    WriteJson (Join-Path $launch 'task-deleted.json') $receipt
  }else{
    $receipt=[ordered]@{task_path='\'+$taskName;state=[int]$task.State;instances=$instances.Count;last_task_result=[long]$task.LastTaskResult;last_run_time=$task.LastRunTime.ToString('o');task_definition_sha256=(Hash (Join-Path $launch 'task.xml'));formal_acceptance=$false;status_scope='Scheduler state only; retained-handle actual exit receipts are required'}
  }
  $receipt|ConvertTo-Json -Depth 10
  exit 0
}
Need ($null -eq $task) 'TASK_ALREADY_EXISTS'
Need (!(Test-Path -LiteralPath $launch)) 'TASK_LAUNCH_EVIDENCE_EXISTS'
Need (!(Test-Path -LiteralPath (Join-Path $studio '.local\reviews\gt06-s91-sparse-attribution-01'))) 'TASK_RUN_ID_ALREADY_USED'
# Fixed HHStudio scope only; coordinator still serializes launches across IDs.
foreach($candidate in $folder.GetTasks(0)){
  if($candidate.Name -like 'HHStudio.GT06.*'){Need ($candidate.GetInstances(0).Count -eq 0 -and $candidate.State -in @(1,3)) 'TASK_OTHER_GT06_ACTIVE'}
}
$helperFiles=[ordered]@{}
foreach($name in @('launch_observer.py','register_task.ps1','diagnose_sequence_s91.py','test_launch_observer.py')){$helperFiles[$name]=Hash (Join-Path $PSScriptRoot $name)}
$lock=Get-Content -LiteralPath (Join-Path $studio 'toolchain.lock.json') -Raw|ConvertFrom-Json
$godot=Join-Path (Join-Path $studio '.local\tooling\godot-4.7.2-stable') $lock.godot.gui_executable
Need ((Hash $godot) -ceq $lock.godot.gui_sha256) 'TASK_GODOT_PIN'
$request=[ordered]@{schema='HH-GT06-S91-OBSERVER-REQUEST-1';run_id='gt06-s91-sparse-attribution-01';helper_files=$helperFiles;python_sha256=(Hash $python);pythonw_sha256=(Hash $pythonw);godot_sha256=$lock.godot.gui_sha256;working_directory=$studio;wall_seconds=7530;outer_process_limit=7}
$null=New-Item -ItemType Directory -Path $launch -ErrorAction Stop
WriteJson (Join-Path $launch 'request.json') $request
$definition=$service.NewTask(0)
$definition.RegistrationInfo.Author=$sid
$definition.RegistrationInfo.Description='HH Studio S91 diagnostic observer; demand-only, one use, actual exit evidence'
$definition.Principal.Id='HHStudioCurrentUser';$definition.Principal.UserId=$sid;$definition.Principal.LogonType=3;$definition.Principal.RunLevel=0
$definition.Actions.Context='HHStudioCurrentUser'
$settings=$definition.Settings
$settings.Compatibility=2;$settings.Enabled=$true;$settings.AllowDemandStart=$true;$settings.AllowHardTerminate=$true
$settings.MultipleInstances=2;$settings.RestartCount=0;$settings.Priority=6;$settings.ExecutionTimeLimit='PT130M'
$settings.Hidden=$false;$settings.StartWhenAvailable=$false;$settings.WakeToRun=$false;$settings.RunOnlyIfIdle=$false;$settings.RunOnlyIfNetworkAvailable=$false
$settings.DisallowStartIfOnBatteries=$false;$settings.StopIfGoingOnBatteries=$false;$settings.IdleSettings.StopOnIdleEnd=$false;$settings.IdleSettings.RestartOnIdle=$false
$action=$definition.Actions.Create(0);$action.Id='s91-observer';$action.Path=$pythonw;$action.Arguments=$arguments;$action.WorkingDirectory=$studio
$stage='register';$invoked=$false
try{
  $task=$folder.RegisterTaskDefinition($taskName,$definition,2,$sid,$null,3,$null)
  AssertTask $task
  WriteNew (Join-Path $launch 'task.xml') ([string]$task.Xml)
  $stage='pre-run';$task=$folder.GetTask($taskName);AssertTask $task
  Need ([IO.File]::ReadAllText((Join-Path $launch 'task.xml'),$utf8) -ceq [string]$task.Xml) 'TASK_XML_CHANGED'
  foreach($name in $helperFiles.Keys){Need ((Hash (Join-Path $PSScriptRoot $name)) -ceq $helperFiles[$name]) 'TASK_HELPER_CHANGED'}
  Need ((Hash $python) -ceq $request.python_sha256 -and (Hash $pythonw) -ceq $request.pythonw_sha256) 'TASK_PYTHON_CHANGED'
  Need ($task.GetInstances(0).Count -eq 0) 'TASK_ALREADY_RUNNING'
  $stage='run';$invoked=$true;$running=$task.Run($null)
  Need ($null -ne $running -and ![string]::IsNullOrWhiteSpace($running.InstanceGuid)) 'TASK_RUN_UNPROVEN'
  $receipt=[ordered]@{schema='HH-GT06-S91-OBSERVER-TASK-START-1';task_path='\'+$taskName;run_id=$request.run_id;instance_guid=[string]$running.InstanceGuid;state=[int]$running.State;scheduler_engine_pid=[int]$running.EnginePID;requested_utc=[DateTime]::UtcNow.ToString('o');request_sha256=(Hash (Join-Path $launch 'request.json'));task_definition_sha256=(Hash (Join-Path $launch 'task.xml'));formal_acceptance=$false;status_scope='Dispatch only; observer terminal and actual process exits remain required'}
  WriteJson (Join-Path $launch 'task-start.json') $receipt
  $receipt|ConvertTo-Json -Depth 12
}catch{
  WriteJson (Join-Path $launch 'launcher-failure.json') ([ordered]@{stage=$stage;run_invoked=$invoked;error=$_.Exception.Message;hresult=$_.Exception.HResult;observed_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false})
  throw
}
