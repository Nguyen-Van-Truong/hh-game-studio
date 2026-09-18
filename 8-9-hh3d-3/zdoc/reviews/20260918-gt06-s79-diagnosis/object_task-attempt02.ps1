# Fixed disposable diagnostic, demand-only. No arbitrary command or credentials.
param([ValidateSet('run','status','delete')][string]$Command = 'status')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$name = 'HHStudio.GT06.gt06-s79-object-diagnostic-02'
$scriptPath = Join-Path $PSScriptRoot 'diagnose_objects.py'
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$pythonLines = @(& python -B -c 'import sys; print(sys.executable)')
if ($LASTEXITCODE -ne 0 -or $pythonLines.Count -ne 1) { throw 'DIAGNOSTIC_PYTHON_RESOLUTION' }
$pythonPath = [System.IO.Path]::GetFullPath($pythonLines[0])
$pythonwPath = Join-Path ([System.IO.Path]::GetDirectoryName($pythonPath)) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath) -or -not (Test-Path -LiteralPath $scriptPath)) { throw 'DIAGNOSTIC_EXECUTABLE_MISSING' }
$actionArguments = '-B "' + $scriptPath + '"'
$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')
$task = $null
try { $task = $folder.GetTask($name) }
catch {
    $errorObject = $_.Exception
    $missing = $false
    while ($null -ne $errorObject) {
        if ($errorObject.HResult -eq -2147024894) { $missing = $true; break }
        $errorObject = $errorObject.InnerException
    }
    if (-not $missing) { throw }
}
if ($null -ne $task) {
    $action = $task.Definition.Actions.Item(1)
    if ($task.Definition.Actions.Count -ne 1 -or $action.Path -ne $pythonwPath -or $action.Arguments -ne $actionArguments) { throw 'DIAGNOSTIC_TASK_IDENTITY' }
}
if ($Command -eq 'run') {
    if ($null -ne $task -or (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'object-owner-02'))) { throw 'DIAGNOSTIC_ALREADY_EXISTS' }
    $definition = $service.NewTask(0)
    $definition.RegistrationInfo.Description = 'HH3D S79 supplemental6x100 native object attribution plus120s idle diagnostic; not full campaign or acceptance.'
    $definition.Principal.UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $definition.Principal.LogonType = 3
    $definition.Principal.RunLevel = 0
    $definition.Settings.ExecutionTimeLimit = 'PT12M'
    $definition.Settings.MultipleInstances = 2
    $definition.Settings.Priority = 6
    $definition.Settings.RestartCount = 0
    $definition.Settings.AllowDemandStart = $true
    $definition.Settings.StartWhenAvailable = $false
    $definition.Settings.WakeToRun = $false
    $definition.Settings.DisallowStartIfOnBatteries = $false
    $definition.Settings.StopIfGoingOnBatteries = $false
    $definition.Settings.Hidden = $false
    $action = $definition.Actions.Create(0)
    $action.Path = $pythonwPath
    $action.Arguments = $actionArguments
    $action.WorkingDirectory = $sourceRoot
    $task = $folder.RegisterTaskDefinition($name, $definition, 2, $definition.Principal.UserId, $null, 3, $null)
    $instance = $task.Run($null)
    $record = [ordered]@{ task=$name; instance_guid=$instance.InstanceGuid; started_utc=[DateTime]::UtcNow.ToString('o'); pythonw=$pythonwPath; arguments=$actionArguments; script_sha256=(Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLowerInvariant(); probe_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'object_probe.gd') -Algorithm SHA256).Hash.ToLowerInvariant(); no_acceptance_claim=$true; timeout_inner=540; timeout_owner=600; scheduler_timeout=720 }
    $record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'object-launch-02.json') -Encoding utf8
}
if ($null -eq $task) { throw 'DIAGNOSTIC_TASK_MISSING' }
$instances = $task.GetInstances(0)
$status = [ordered]@{ task=$name; observed_utc=[DateTime]::UtcNow.ToString('o'); state=$task.State; last_result=$task.LastTaskResult; instances=$instances.Count; scheduler_zero_is_not_acceptance=$true }
$status | ConvertTo-Json -Depth 4
if ($Command -eq 'delete') {
    if ($task.State -eq 4 -or $instances.Count -ne 0) { throw 'DIAGNOSTIC_TASK_STILL_RUNNING' }
    $folder.DeleteTask($name,0)
}
