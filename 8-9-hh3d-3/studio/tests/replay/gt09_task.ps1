# Demand-only GT-09 final launcher.  The task action is fixed to the trusted
# supervisor and one prepared run id; it has no trigger and no arbitrary argv.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('register-run','start-run','status','delete')]
    [string]$Command,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^gt09-matrix-(final|probe)-20\d{6}-[a-z0-9-]{1,24}$')]
    [string]$RunId
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$studio = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$script = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'run_gt09_task.py'))
$python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
$pythonw = Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
$taskName = 'HHStudio.GT09.' + $RunId
$supervisor = Join-Path $studio ('.local\reviews\' + $RunId + '-task')
$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
function Require([bool]$value,[string]$code) { if(-not $value){throw $code} }
function Get-Task {
    try { return $folder.GetTask($taskName) } catch {
        $e=$_.Exception
        while($null -ne $e){if($e.HResult -eq -2147024894){return $null};$e=$e.InnerException}
        throw
    }
}
function Hash-File([string]$path) {
    Plain $path; $algo=[Security.Cryptography.SHA256]::Create(); $stream=$null
    try { $stream=[IO.File]::OpenRead($path); return ([BitConverter]::ToString($algo.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { if($null -ne $stream){$stream.Dispose()};$algo.Dispose() }
}
function Sid-Of([string]$account) {
    if($account -match '^S-1-'){return $account}
    return (New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier]).Value
}
function Assert-Task([object]$task) {
    Require ($null -ne $task) 'GT09_TASK_NOT_FOUND'
    $definition=$task.Definition
    Require ($task.Path -eq ('\'+$taskName)) 'GT09_TASK_PATH_BINDING'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent();try{$sid=$identity.User.Value}finally{$identity.Dispose()}
    Require ((Sid-Of $definition.Principal.UserId) -eq $sid) 'GT09_TASK_PRINCIPAL_BINDING'
    Require ($definition.Principal.LogonType -eq 3 -and $definition.Principal.RunLevel -eq 0) 'GT09_TASK_SECURITY_BINDING'
    Require ($definition.Principal.Id -ceq 'HHStudioCurrentUser') 'GT09_TASK_PRINCIPAL_ID'
    Require ($definition.Triggers.Count -eq 0 -and $definition.Actions.Count -eq 1) 'GT09_TASK_TRIGGER_ACTION_BINDING'
    $action=$definition.Actions.Item(1)
    Require ($action.Type -eq 0 -and $action.Id -ceq 'gt09-final-supervisor') 'GT09_TASK_ACTION_BINDING'
    Require ([IO.Path]::GetFullPath($action.Path).Equals([IO.Path]::GetFullPath($pythonw),[StringComparison]::OrdinalIgnoreCase)) 'GT09_TASK_INTERPRETER_BINDING'
    Require ($action.Arguments -ceq ('-B "{0}" --run-id {1}' -f $script,$RunId)) 'GT09_TASK_ARGUMENT_BINDING'
    Require ([IO.Path]::GetFullPath($action.WorkingDirectory).Equals([IO.Path]::GetFullPath($studio),[StringComparison]::OrdinalIgnoreCase)) 'GT09_TASK_CWD_BINDING'
    Require ($definition.Settings.Compatibility -eq 2 -and [Xml.XmlConvert]::ToTimeSpan($definition.Settings.ExecutionTimeLimit) -eq [TimeSpan]::FromHours(24)) 'GT09_TASK_SETTINGS_BINDING'
    Require ($definition.Settings.Enabled -and $definition.Settings.AllowDemandStart -and $definition.Settings.AllowHardTerminate) 'GT09_TASK_START_BINDING'
    Require ($definition.Settings.MultipleInstances -eq 2 -and $definition.Settings.RestartCount -eq 0 -and $definition.Settings.Priority -eq 6) 'GT09_TASK_RESTART_BINDING'
    Require (-not $definition.Settings.Hidden -and -not $definition.Settings.StartWhenAvailable -and -not $definition.Settings.WakeToRun -and -not $definition.Settings.RunOnlyIfIdle -and -not $definition.Settings.RunOnlyIfNetworkAvailable) 'GT09_TASK_CONDITION_BINDING'
}
function Write-NewJson([string]$path,[object]$value) {
    Plain ([IO.Path]::GetDirectoryName($path));Require (-not (Test-Path -LiteralPath $path)) 'GT09_TASK_RECEIPT_REUSED'
    $bytes=[Text.Encoding]::UTF8.GetBytes((ConvertTo-Json $value -Depth 12)+"`n")
    $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Assert-Registration($task) {
    Assert-Task $task
    Plain $supervisor
    $reg=Get-Content -LiteralPath (Join-Path $supervisor 'task-registration.json') -Raw | ConvertFrom-Json
    Require ($reg.run_id -ceq $RunId -and $reg.task_path -ceq ('\'+$taskName)) 'GT09_TASK_REGISTRATION_BINDING'
    Require ($reg.request_sha256 -ceq (Hash-File (Join-Path $supervisor 'request.json'))) 'GT09_TASK_REQUEST_CHANGED'
    $algo=[Security.Cryptography.SHA256]::Create()
    try{$xmlHash=([BitConverter]::ToString($algo.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]$task.Xml)))).Replace('-','').ToLowerInvariant()}finally{$algo.Dispose()}
    Require ($reg.task_definition_sha256 -ceq $xmlHash -and $reg.task_definition_sha256 -ceq (Hash-File (Join-Path $supervisor 'task-definition.xml'))) 'GT09_TASK_DEFINITION_CHANGED'
}
function Task-Status($task) {
    return [ordered]@{schema='HH-GT09-TASK-STATUS-1';task_path=('\'+$taskName);run_id=$RunId;state=[int]$task.State;last_task_result=[long]$task.LastTaskResult;last_run_time=$task.LastRunTime.ToString('o');instances=[int]$task.GetInstances(0).Count;formal_acceptance=$false;scope='Scheduler observation only; child exit and matrix evidence required separately'}
}
function Plain([string]$p) {
    $full = [IO.Path]::GetFullPath($p)
    while ($full) {
        if (Test-Path -LiteralPath $full) {
            $item = Get-Item -LiteralPath $full -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'GT09_TASK_REPARSE' }
        }
        $parent = [IO.Directory]::GetParent($full)
        if ($null -eq $parent) { break }
        $full = $parent.FullName
    }
}
if ($Command -eq 'register-run') {
    if ($null -ne (Get-Task)) { throw 'GT09_TASK_ALREADY_EXISTS' }
    Plain $studio; Plain (Join-Path $studio '.local\reviews')
    if (Test-Path -LiteralPath $supervisor) { throw 'GT09_TASK_OUTPUT_ALREADY_EXISTS' }
    & $python -B $script --prepare --run-id $RunId | Out-Null
    Require ($LASTEXITCODE -eq 0) 'GT09_TASK_PREPARE_FAILED'
    $definition = $service.NewTask(0)
    $definition.RegistrationInfo.Description = 'HH Studio GT-09 final matrix (demand-only, pinned source)'
    $definition.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $definition.Principal.Id = 'HHStudioCurrentUser'
    $definition.Principal.LogonType = 3
    $definition.Principal.RunLevel = 0
    $definition.Actions.Context = 'HHStudioCurrentUser'
    $definition.Settings.Compatibility = 2
    $definition.Settings.Priority = 6
    $definition.Settings.IdleSettings.StopOnIdleEnd = $false
    $definition.Settings.IdleSettings.RestartOnIdle = $false
    $definition.Settings.Enabled = $true
    $definition.Settings.AllowDemandStart = $true
    $definition.Settings.AllowHardTerminate = $true
    $definition.Settings.MultipleInstances = 2
    $definition.Settings.RestartCount = 0
    $definition.Settings.ExecutionTimeLimit = 'PT24H'
    $definition.Settings.Hidden = $false
    $definition.Settings.StartWhenAvailable = $false
    $definition.Settings.WakeToRun = $false
    $definition.Settings.RunOnlyIfIdle = $false
    $definition.Settings.RunOnlyIfNetworkAvailable = $false
    $definition.Settings.DisallowStartIfOnBatteries = $false
    $definition.Settings.StopIfGoingOnBatteries = $false
    $action = $definition.Actions.Create(0)
    $action.Id = 'gt09-final-supervisor'
    $action.Path = $pythonw
    $action.Arguments = ('-B "{0}" --run-id {1}' -f $script,$RunId)
    $action.WorkingDirectory = $studio
    $task = $folder.RegisterTaskDefinition($taskName,$definition,2,$null,$null,3,$null)
    Assert-Task $task
    $xml = Join-Path $supervisor 'task-definition.xml'
    [IO.File]::WriteAllText($xml,$task.Xml,(New-Object Text.UTF8Encoding($false)))
    $reg = [ordered]@{schema='HH-GT09-TASK-REGISTRATION-1';task_path=('\'+$taskName);run_id=$RunId;supervisor=$supervisor;task_definition_sha256=(Hash-File $xml);request_sha256=(Hash-File (Join-Path $supervisor 'request.json'));formal_acceptance=$false}
    Write-NewJson (Join-Path $supervisor 'task-registration.json') $reg
    Write-Output ($reg | ConvertTo-Json -Compress)
    exit 0
}
$task = Get-Task
if ($Command -eq 'start-run') {
    Assert-Registration $task
    if ($task.GetInstances(0).Count -ne 0) { throw 'GT09_TASK_ALREADY_RUNNING' }
    $request = Join-Path $supervisor 'request.json'
    if (-not (Test-Path -LiteralPath $request)) { throw 'GT09_TASK_REQUEST_MISSING' }
    Write-NewJson (Join-Path $supervisor 'task-start-intent.json') @{run_id=$RunId;requested_utc=[DateTime]::UtcNow.ToString('o');request_sha256=(Hash-File $request)}
    $instance = $task.Run($null)
    if ($null -eq $instance) { throw 'GT09_TASK_START_UNPROVEN' }
    $start = [ordered]@{schema='HH-GT09-TASK-SCHEDULER-START-1';task_path=('\'+$taskName);run_id=$RunId;instance_guid=[string]$instance.InstanceGuid;started_utc=[DateTime]::UtcNow.ToString('o');formal_acceptance=$false}
    Write-NewJson (Join-Path $supervisor 'task-start.json') $start
    Write-Output ($start | ConvertTo-Json -Compress)
    exit 0
}
if ($Command -eq 'status') {
    Assert-Registration $task
    $returnPath = Join-Path $supervisor 'return.json'
    $return = if (Test-Path -LiteralPath $returnPath) { Get-Content -Raw $returnPath | ConvertFrom-Json } else { $null }
    $status=Task-Status $task
    $status.return_receipt=$return
    $status | ConvertTo-Json -Depth 12
    exit 0
}
Assert-Registration $task
if ($task.GetInstances(0).Count -ne 0 -or $task.State -notin @(1,3)) { throw 'GT09_TASK_RUNNING_DELETE_REFUSED' }
if(-not (Test-Path -LiteralPath (Join-Path $supervisor 'task-terminal.json'))){Write-NewJson (Join-Path $supervisor 'task-terminal.json') (Task-Status $task)}
$task=Get-Task
Assert-Registration $task
Require ($task.GetInstances(0).Count -eq 0 -and $task.State -in @(1,3)) 'GT09_TASK_RUNNING_DELETE_REFUSED'
$folder.DeleteTask($taskName,0)
if ($null -ne (Get-Task)) { throw 'GT09_TASK_DELETE_UNPROVEN' }
$deleted=@{schema='HH-GT09-TASK-DELETED-1';task_path=('\'+$taskName);run_id=$RunId;terminal_sha256=(Hash-File (Join-Path $supervisor 'task-terminal.json'));formal_acceptance=$false}
Write-NewJson (Join-Path $supervisor 'task-deleted.json') $deleted
Write-Output ($deleted | ConvertTo-Json -Compress)
