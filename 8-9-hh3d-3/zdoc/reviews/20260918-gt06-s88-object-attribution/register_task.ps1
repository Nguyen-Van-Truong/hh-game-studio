param([ValidateSet('register','status','delete')][string]$Command='register')
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$studio=Join-Path $root 'studio'
$wrapper=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'diagnose_sequence_s88.py'))
$python=(Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$python=[IO.Path]::GetFullPath($python)
$pythonw=Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
$taskName='HHStudio.GT06.gt06-s88-object-attribution-01'
$launch=Join-Path $PSScriptRoot 'launch'
$taskReceipt=Join-Path $launch 'task-start.json'
$taskXml=Join-Path $launch 'task.xml'
function Hash([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
if(!(Test-Path -LiteralPath $launch)){New-Item -ItemType Directory -Path $launch|Out-Null}
$service=New-Object -ComObject 'Schedule.Service';$service.Connect();$folder=$service.GetFolder('\')
$task=$null;try{$task=$folder.GetTask($taskName)}catch{}
if($Command -eq 'status'){
  if($null -eq $task){throw 'TASK_NOT_REGISTERED'}
  [pscustomobject]@{task_path='\'+$taskName;state=[int]$task.State;instances=$task.GetInstances(0).Count;xml_sha256=(Get-FileHash -LiteralPath $taskXml -Algorithm SHA256).Hash.ToLowerInvariant()}|ConvertTo-Json -Depth 5
  exit 0
}
if($Command -eq 'delete'){
  if($null -ne $task){$folder.DeleteTask($taskName,0)}
  [pscustomobject]@{task_path='\'+$taskName;deleted=($null -ne $task);formal_acceptance=$false}|ConvertTo-Json -Depth 5
  exit 0
}
if($null -ne $task){throw 'TASK_ALREADY_EXISTS'}
$request=[ordered]@{schema='HH-GT06-S88-RECOVERY-TASK-1';task_path='\'+$taskName;run_id='gt06-s88-object-attribution-01';wrapper_sha256=(Hash $wrapper);pythonw_sha256=(Hash $pythonw);command='--supervisor';working_directory=$studio;formal_acceptance=$false}
$request|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $launch 'request.json') -Encoding utf8
$identity=[Security.Principal.WindowsIdentity]::GetCurrent();try{$sid=$identity.User.Value}finally{$identity.Dispose()}
$definition=$service.NewTask(0);$definition.RegistrationInfo.Author=$sid;$definition.RegistrationInfo.Description='HH Studio bounded GT06 S88 recovery';$definition.Principal.Id='HHStudioCurrentUser';$definition.Principal.UserId=$sid;$definition.Principal.LogonType=3;$definition.Principal.RunLevel=0;$definition.Settings.Enabled=$true;$definition.Settings.AllowDemandStart=$true;$definition.Settings.AllowHardTerminate=$true;$definition.Settings.RestartCount=0;$definition.Settings.ExecutionTimeLimit='PT24H';$definition.Settings.StartWhenAvailable=$false;$definition.Settings.RunOnlyIfIdle=$false;$definition.Settings.RunOnlyIfNetworkAvailable=$false;$definition.Settings.DisallowStartIfOnBatteries=$false;$definition.Settings.StopIfGoingOnBatteries=$false;$action=$definition.Actions.Create(0);$action.Id='s88-supervisor';$action.Path=$pythonw;$action.Arguments='-B "'+$wrapper+'" --supervisor';$action.WorkingDirectory=$studio
$task=$folder.RegisterTaskDefinition($taskName,$definition,2,$sid,$null,3,$null);$xml=[string]$task.Xml;$xml|Set-Content -LiteralPath $taskXml -Encoding utf8
$xmlHash=Hash $taskXml;$request.task_definition_sha256=$xmlHash;$request|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $launch 'request.json') -Encoding utf8
$running=$task.Run($null);if($null -eq $running){throw 'TASK_RUN_UNPROVEN'}
[ordered]@{schema='HH-GT06-S88-RECOVERY-START-1';task_path='\'+$taskName;instance_guid=[string]$running.InstanceGuid;state=[int]$running.State;requested_utc=[DateTime]::UtcNow.ToString('o');request_sha256=(Hash (Join-Path $launch 'request.json'));task_definition_sha256=$xmlHash;wrapper_sha256=(Hash $wrapper);pythonw_sha256=(Hash $pythonw);formal_acceptance=$false;status_scope='Scheduler dispatch only; supervisor return and actual exits required'}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $taskReceipt -Encoding utf8
Get-Content $taskReceipt -Raw
