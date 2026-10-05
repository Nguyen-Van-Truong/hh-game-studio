[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RequestPath,
      [string]$TaskName,
      [switch]$ValidateOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$requestFile = (Resolve-Path -LiteralPath $RequestPath).Path
if ($requestFile.Contains('"')) { throw 'ARM_REQUEST_PATH' }
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$arm = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'arm_formal_window.py'))
$python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
$pythonw = Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'ARM_PYTHONW_MISSING' }
# This validates the current helper/request hash and the successful dry-run receipt.
# It performs no probe, dispatch, or task registration.
$validationJson = & $python -B $arm --validate $requestFile
if ($LASTEXITCODE -ne 0) { throw 'ARM_REQUEST_OR_DRY_RUN_INVALID' }
$validated = $validationJson | ConvertFrom-Json
$name = [string]$validated.arm_task_name
if ($TaskName -and $TaskName -cne $name) { throw 'ARM_TASK_NAME_BINDING' }
$start = [DateTimeOffset]::Parse($validated.start)
if ($start -le [DateTimeOffset]::Now) { throw 'ARM_START_NOT_FUTURE' }
if ($ValidateOnly) { $validated | ConvertTo-Json; return }

function Write-NewUtf8([string]$Path, [string]$Content) {
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($Content)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
$existing = $null
try { $existing = $folder.GetTask($name) } catch {
    $errorObject = $_.Exception
    while ($null -ne $errorObject.InnerException) { $errorObject = $errorObject.InnerException }
    if ($errorObject.HResult -ne -2147024894) { throw }
}
if ($null -ne $existing) { throw 'ARM_TASK_ALREADY_EXISTS' }
$definition = $service.NewTask(0)
$definition.RegistrationInfo.Author = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$definition.RegistrationInfo.Description = 'HH Studio O8 one-shot arm: ' + $validated.campaign_id
$definition.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$definition.Principal.LogonType = 3
$definition.Principal.RunLevel = 0
$settings = $definition.Settings
$settings.Enabled = $true
$settings.AllowDemandStart = $true
$settings.AllowHardTerminate = $true
$settings.MultipleInstances = 2
$settings.RestartCount = 0
$settings.Priority = 6
$settings.ExecutionTimeLimit = 'PT6H'
$settings.WakeToRun = $true
$settings.StartWhenAvailable = $false
$settings.DisallowStartIfOnBatteries = $false
$settings.StopIfGoingOnBatteries = $false
$settings.RunOnlyIfIdle = $false
$settings.IdleSettings.StopOnIdleEnd = $false
$settings.IdleSettings.RestartOnIdle = $false
$trigger = $definition.Triggers.Create(1)
$trigger.StartBoundary = $start.ToLocalTime().ToString('yyyy-MM-ddTHH:mm:ss')
$trigger.Enabled = $true
$action = $definition.Actions.Create(0)
$action.Id = 'formal-arm'
$action.Path = $pythonw
$action.Arguments = ('-B "{0}" --run "{1}"' -f $arm, $requestFile)
$action.WorkingDirectory = $root
$receiptRoot = [IO.Path]::GetDirectoryName($requestFile)
Write-NewUtf8 (Join-Path $receiptRoot 'registration-request.json') ($validated | ConvertTo-Json)
Write-NewUtf8 (Join-Path $receiptRoot 'task-request.xml') $definition.XmlText
try {
    # TASK_CREATE (2), never overwrite an existing task. An uncertain result is not retried.
    $task = $folder.RegisterTaskDefinition($name, $definition, 2, $definition.Principal.UserId, $null, 3, $null)
    Write-NewUtf8 (Join-Path $receiptRoot 'task-registered.xml') $task.Xml
    $readback = $task.Definition
    if ($task.Path -cne ('\' + $name) -or $task.GetInstances(0).Count -ne 0 -or
        $readback.Actions.Count -ne 1 -or $readback.Actions.Item(1).Path -cne $pythonw -or
        $readback.Actions.Item(1).Arguments -cne $action.Arguments -or
        $readback.Actions.Item(1).WorkingDirectory -cne $root -or
        $readback.Triggers.Count -ne 1 -or $readback.Triggers.Item(1).StartBoundary -ne $trigger.StartBoundary -or
        $readback.Principal.UserId -ne $definition.Principal.UserId -or $readback.Principal.LogonType -ne 3 -or
        -not $readback.Settings.WakeToRun -or $readback.Settings.RestartCount -ne 0 -or
        $readback.Settings.MultipleInstances -ne 2 -or $readback.Settings.StartWhenAvailable) { throw 'ARM_TASK_BINDING' }
    $receipt = [ordered]@{ task_path='\'+$name; start_boundary=$trigger.StartBoundary; request=$requestFile;
        request_sha256=$validated.request_sha256; pythonw=$pythonw; arm=$arm; wake_to_run=$true; registered=$true }
    Write-NewUtf8 (Join-Path $receiptRoot 'registration-receipt.json') ($receipt | ConvertTo-Json)
    $receipt | ConvertTo-Json
} catch {
    Write-NewUtf8 (Join-Path $receiptRoot 'registration-failure.json') ([ordered]@{
        task_path='\'+$name; error=$_.Exception.Message; no_retry=$true; inspect_scheduler_required=$true } | ConvertTo-Json)
    throw
}
