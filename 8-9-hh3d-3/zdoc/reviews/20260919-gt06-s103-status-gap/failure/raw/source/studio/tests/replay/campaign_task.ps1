# Bounded, demand-only GT06 task launcher; no periodic triggers.
# Registers one demand-only task owned by the current interactive user.
# No arbitrary executable, argument, output, task path, trigger or credential input.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('register-run', 'status', 'delete')]
    [string]$Command,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^gt06-[a-z0-9-]{1,25}$')]
    [string]$CampaignId,

    [ValidateSet('probe', 'campaign')]
    [string]$Mode,

    [ValidateRange(1, 99)]
    [int]$LaunchNumber = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$stage = 'derive'
$runInvoked = $false
$createdOutput = $false
$outputDirectory = $null

function Require([bool]$Condition, [string]$Code) {
    if (-not $Condition) { throw $Code }
}

function Assert-PlainPath([string]$Path, [bool]$MustExist = $true) {
    $cursor = [System.IO.Path]::GetFullPath($Path)
    if ($MustExist) { Require (Test-Path -LiteralPath $cursor) 'TASK_PATH_MISSING' }
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            Require (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) 'TASK_REPARSE'
        }
        $parent = [System.IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
}

function Hash-File([string]$Path) {
    Assert-PlainPath $Path
    Require ([System.IO.File]::Exists($Path)) 'TASK_NOT_REGULAR_FILE'
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Hash-Text([string]$Value) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($utf8.GetBytes($Value)))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}

function Write-NewText([string]$Path, [string]$Value) {
    Assert-PlainPath ([System.IO.Path]::GetDirectoryName($Path))
    $bytes = $utf8.GetBytes($Value)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    Require ((Hash-File $Path) -eq (Hash-Text $Value)) 'TASK_WRITE_READBACK'
}

function Write-NewJson([string]$Path, $Value) {
    Write-NewText $Path (($Value | ConvertTo-Json -Depth 12) + "`n")
}

function Read-Json([string]$Path) {
    Assert-PlainPath $Path
    $info = Get-Item -LiteralPath $Path
    Require ($info.Length -gt 0 -and $info.Length -le 65536) 'TASK_JSON_SIZE'
    return ([System.IO.File]::ReadAllText($Path, $utf8) | ConvertFrom-Json)
}

function Sid-Of([string]$Account) {
    if ($Account -match '^S-1-') { return $Account }
    $identity = New-Object System.Security.Principal.NTAccount($Account)
    return $identity.Translate([System.Security.Principal.SecurityIdentifier]).Value
}

function Get-OwnTask($Folder, [string]$Name) {
    try { return $Folder.GetTask($Name) }
    catch {
        # HRESULT_FROM_WIN32(ERROR_FILE_NOT_FOUND). No access-denied masking.
        # PowerShell can wrap COMException in MethodInvocationException.
        $failureException = $_.Exception
        while ($null -ne $failureException) {
            # PowerShell 7 may translate this HRESULT to FileNotFoundException
            # instead of COMException. Match only the exact not-found code.
            if ($failureException.HResult -eq -2147024894) { return $null }
            $failureException = $failureException.InnerException
        }
        throw
    }
}

function Launch-Suffix([int]$Number) {
    if ($Number -eq 1) { return '' }
    return ('-launch-{0:D2}' -f $Number)
}

function Assert-CampaignIdle($Folder) {
    # Fixed slots only. The coordinator must serialize manual launch commands;
    # these scheduler readbacks are not an atomic cross-task launch lock.
    for ($number = 1; $number -le 99; $number++) {
        $candidateName = $baseTaskName + (Launch-Suffix $number)
        $candidate = Get-OwnTask $Folder $candidateName
        if ($null -ne $candidate) {
            Require ((Sid-Of $candidate.Definition.Principal.UserId) -eq $userSid) 'TASK_CAMPAIGN_PRINCIPAL'
            Require ($candidate.GetInstances(0).Count -eq 0 -and
                $candidate.State -in @(1, 3)) 'TASK_CAMPAIGN_ALREADY_ACTIVE'
        }
    }
}

function Assert-Definition($Task, [string]$ExpectedMode) {
    $definition = $Task.Definition
    Require ($Task.Path -eq ('\' + $taskName)) 'TASK_PATH_BINDING'
    Require ((Sid-Of $definition.Principal.UserId) -eq $userSid) 'TASK_PRINCIPAL_BINDING'
    Require ($definition.Principal.LogonType -eq 3 -and $definition.Principal.RunLevel -eq 0) 'TASK_SECURITY_LEVEL'
    Require ($definition.Principal.Id -ceq 'HHStudioCurrentUser' -and
        $definition.Actions.Context -ceq 'HHStudioCurrentUser') 'TASK_ACTION_PRINCIPAL'
    Require ($definition.Triggers.Count -eq 0 -and $definition.Actions.Count -eq 1) 'TASK_ACTION_OR_TRIGGER_COUNT'
    $action = $definition.Actions.Item(1)
    Require ($action.Type -eq 0 -and $action.Id -eq 'campaign-supervisor') 'TASK_ACTION_KIND'
    Require ([string]::Equals($action.Path, $pythonwPath, [StringComparison]::OrdinalIgnoreCase)) 'TASK_ACTION_PATH'
    Require ($action.Arguments -ceq (Action-Arguments $ExpectedMode)) 'TASK_ACTION_ARGUMENTS'
    Require ([string]::Equals($action.WorkingDirectory, $studio, [StringComparison]::OrdinalIgnoreCase)) 'TASK_ACTION_CWD'
    $settings = $definition.Settings
    Require ($settings.Compatibility -eq 2) 'TASK_COMPATIBILITY'
    $expectedLimit = if ($ExpectedMode -eq 'probe') { 'PT2M' } else { 'PT24H' }
    Require ([System.Xml.XmlConvert]::ToTimeSpan($settings.ExecutionTimeLimit) -eq
        [System.Xml.XmlConvert]::ToTimeSpan($expectedLimit)) 'TASK_WALL_LIMIT'
    Require ($settings.Enabled -and $settings.AllowDemandStart -and $settings.AllowHardTerminate) 'TASK_START_OR_TERMINATION_DISABLED'
    Require ($settings.MultipleInstances -eq 2 -and $settings.RestartCount -eq 0 -and $settings.Priority -eq 6) 'TASK_INSTANCE_RESTART_OR_PRIORITY'
    Require (-not $settings.Hidden -and -not $settings.StartWhenAvailable -and -not $settings.WakeToRun) 'TASK_VISIBILITY_OR_DELAYED_START'
    Require (-not $settings.RunOnlyIfIdle -and -not $settings.RunOnlyIfNetworkAvailable) 'TASK_UNDECLARED_CONDITION'
    Require (-not $settings.DisallowStartIfOnBatteries -and -not $settings.StopIfGoingOnBatteries) 'TASK_POWER_CONDITION'
    Require (-not $settings.IdleSettings.StopOnIdleEnd -and -not $settings.IdleSettings.RestartOnIdle) 'TASK_IDLE_RESTART'
}

function Action-Arguments([string]$SelectedMode) {
    $arguments = ('-B "{0}" --campaign-id {1} --mode {2}' -f $scriptPath, $CampaignId, $SelectedMode)
    if ($LaunchNumber -gt 1) { $arguments += (' --launch-number {0}' -f $LaunchNumber) }
    return $arguments
}

function Assert-Request($Request) {
    $keys = @($Request.PSObject.Properties.Name | Sort-Object)
    $expectedKeys = @('schema', 'campaign_id', 'mode', 'script_sha256', 'pythonw_sha256', 'python_sha256')
    if ($LaunchNumber -gt 1) {
        $expectedKeys += 'launch_number'
        Require (($Request.launch_number -is [int] -or $Request.launch_number -is [long]) -and
            $Request.launch_number -eq $LaunchNumber) 'TASK_REQUEST_LAUNCH_NUMBER'
    }
    $expectedKeys = @($expectedKeys | Sort-Object)
    Require (($keys -join ',') -ceq ($expectedKeys -join ',')) 'TASK_REQUEST_FIELDS'
    Require ($Request.schema -ceq 'HH-GT06-TASK-REQUEST-1' -and $Request.campaign_id -ceq $CampaignId) 'TASK_REQUEST_BINDING'
    Require ($Request.mode -cin @('probe', 'campaign')) 'TASK_REQUEST_MODE'
    foreach ($key in @('script_sha256', 'pythonw_sha256', 'python_sha256')) {
        Require ($Request.$key -cmatch '^[a-f0-9]{64}$') 'TASK_REQUEST_HASH'
    }
}

function Assert-SourcePins($Request) {
    Require ((Hash-File $scriptPath) -ceq $Request.script_sha256) 'TASK_SCRIPT_CHANGED'
    Require ((Hash-File $pythonwPath) -ceq $Request.pythonw_sha256) 'TASK_PYTHONW_CHANGED'
    Require ((Hash-File $pythonPath) -ceq $Request.python_sha256) 'TASK_PYTHON_CHANGED'
}

try {
    $scriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'run_campaign_task.py'))
    $studio = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    $pythonCommand = Get-Command python.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $pythonPath = [System.IO.Path]::GetFullPath($pythonCommand.Source)
    $pythonwPath = Join-Path ([System.IO.Path]::GetDirectoryName($pythonPath)) 'pythonw.exe'
    $userIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    try { $userSid = $userIdentity.User.Value } finally { $userIdentity.Dispose() }
    $baseTaskName = 'HHStudio.GT06.' + $CampaignId
    $launchSuffix = Launch-Suffix $LaunchNumber
    $taskName = $baseTaskName + $launchSuffix
    $reviews = Join-Path $studio '.local\reviews'
    $outputDirectory = Join-Path $reviews ($CampaignId + '-supervisor' + $launchSuffix)
    $requestPath = Join-Path $outputDirectory 'request.json'
    $xmlPath = Join-Path $outputDirectory 'task-definition.xml'
    $registrationPath = Join-Path $outputDirectory 'task-registration.json'
    Assert-PlainPath $studio
    Assert-PlainPath $reviews
    Assert-PlainPath $outputDirectory $false
    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $folder = $service.GetFolder('\')
    $task = Get-OwnTask $folder $taskName

    if ($Command -eq 'register-run') {
        $stage = 'prepare'
        Require ($Mode -cin @('probe', 'campaign')) 'TASK_MODE_REQUIRED'
        Require ($null -eq $task) 'TASK_ALREADY_EXISTS'
        Assert-CampaignIdle $folder
        Require (-not (Test-Path -LiteralPath $outputDirectory)) 'TASK_OUTPUT_ALREADY_EXISTS'
        $null = New-Item -ItemType Directory -Path $outputDirectory -ErrorAction Stop
        $createdOutput = $true
        $request = [ordered]@{
            schema = 'HH-GT06-TASK-REQUEST-1'
            campaign_id = $CampaignId
            mode = $Mode
            script_sha256 = Hash-File $scriptPath
            pythonw_sha256 = Hash-File $pythonwPath
            python_sha256 = Hash-File $pythonPath
        }
        if ($LaunchNumber -gt 1) { $request['launch_number'] = $LaunchNumber }
        Write-NewJson $requestPath $request
        $request = Read-Json $requestPath
        Assert-Request $request
        Assert-SourcePins $request

        $definition = $service.NewTask(0)
        $definition.RegistrationInfo.Author = $userSid
        $definition.RegistrationInfo.Description = 'HH Studio bounded GT06 supervisor: ' + $CampaignId
        $definition.Principal.Id = 'HHStudioCurrentUser'
        $definition.Principal.UserId = $userSid
        $definition.Principal.LogonType = 3
        $definition.Principal.RunLevel = 0
        $definition.Actions.Context = 'HHStudioCurrentUser'
        $settings = $definition.Settings
        $settings.Compatibility = 2
        $settings.Enabled = $true
        $settings.AllowDemandStart = $true
        $settings.AllowHardTerminate = $true
        $settings.MultipleInstances = 2
        $settings.RestartCount = 0
        $settings.Priority = 6
        $settings.ExecutionTimeLimit = if ($Mode -eq 'probe') { 'PT2M' } else { 'PT24H' }
        $settings.Hidden = $false
        $settings.StartWhenAvailable = $false
        $settings.WakeToRun = $false
        $settings.RunOnlyIfIdle = $false
        $settings.RunOnlyIfNetworkAvailable = $false
        $settings.DisallowStartIfOnBatteries = $false
        $settings.StopIfGoingOnBatteries = $false
        $settings.IdleSettings.StopOnIdleEnd = $false
        $settings.IdleSettings.RestartOnIdle = $false
        $action = $definition.Actions.Create(0)
        $action.Id = 'campaign-supervisor'
        $action.Path = $pythonwPath
        $action.Arguments = Action-Arguments $Mode
        $action.WorkingDirectory = $studio
        Write-NewText (Join-Path $outputDirectory 'task-definition.expected.xml') $definition.XmlText

        $stage = 'register'
        # TASK_CREATE only: an existing definition is never updated/replaced.
        $task = $folder.RegisterTaskDefinition($taskName, $definition, 2, $userSid, $null, 3, $null)
        Assert-Definition $task $Mode
        $registeredXml = [string]$task.Xml
        Write-NewText $xmlPath $registeredXml
        $xmlHash = Hash-File $xmlPath
        Write-NewText (Join-Path $outputDirectory 'task-definition.sha256') ($xmlHash + "`n")
        Write-NewJson $registrationPath ([ordered]@{
            schema = 'HH-GT06-TASK-REGISTRATION-1'; campaign_id = $CampaignId; mode = $Mode; launch_number = $LaunchNumber
            task_path = '\' + $taskName; principal_sid = $userSid
            script_path = $scriptPath; python_path = $pythonPath; pythonw_path = $pythonwPath
            request_sha256 = Hash-File $requestPath; task_definition_sha256 = $xmlHash
            registered_utc = [DateTime]::UtcNow.ToString('o'); formal_acceptance = $false
        })

        $stage = 'pre-run-readback'
        $task = $folder.GetTask($taskName)
        Assert-Definition $task $Mode
        Require ((Hash-Text ([string]$task.Xml)) -ceq $xmlHash) 'TASK_REGISTERED_XML_CHANGED'
        $registration = Read-Json $registrationPath
        Require ((Hash-File $requestPath) -ceq $registration.request_sha256) 'TASK_REQUEST_CHANGED'
        Assert-SourcePins (Read-Json $requestPath)
        Require ($task.GetInstances(0).Count -eq 0) 'TASK_ALREADY_RUNNING'
        Assert-CampaignIdle $folder
        $stage = 'run'
        $runInvoked = $true
        $running = $task.Run($null)
        Require ($null -ne $running -and -not [string]::IsNullOrWhiteSpace($running.InstanceGuid)) 'TASK_RUN_UNPROVEN'
        $receipt = [ordered]@{
            schema = 'HH-GT06-TASK-START-1'; campaign_id = $CampaignId; mode = $Mode; launch_number = $LaunchNumber
            task_path = '\' + $taskName; instance_guid = [string]$running.InstanceGuid
            state = [int]$running.State; scheduler_engine_pid = [int]$running.EnginePID
            requested_utc = [DateTime]::UtcNow.ToString('o')
            request_sha256 = $registration.request_sha256; task_definition_sha256 = $xmlHash
            output_directory = $outputDirectory; formal_acceptance = $false
            status_scope = 'Scheduler dispatch only; actual exits and cleanup require supervisor evidence'
        }
        Write-NewJson (Join-Path $outputDirectory 'task-start.json') $receipt
        $receipt | ConvertTo-Json -Depth 12
        exit 0
    }

    $stage = 'inspect-existing'
    Require ($null -ne $task) 'TASK_NOT_REGISTERED'
    $request = Read-Json $requestPath
    Assert-Request $request
    if ($PSBoundParameters.ContainsKey('Mode')) { Require ($Mode -ceq $request.mode) 'TASK_MODE_MISMATCH' }
    $Mode = $request.mode
    $registration = Read-Json $registrationPath
    $storedLaunch = $registration.PSObject.Properties['launch_number']
    if ($null -ne $storedLaunch) {
        Require (($storedLaunch.Value -is [int] -or $storedLaunch.Value -is [long]) -and
            $storedLaunch.Value -eq $LaunchNumber) 'TASK_REGISTRATION_LAUNCH_NUMBER'
    } else {
        Require ($LaunchNumber -eq 1) 'TASK_REGISTRATION_LAUNCH_NUMBER'
    }
    Require ($registration.schema -ceq 'HH-GT06-TASK-REGISTRATION-1' -and
        $registration.task_path -ceq ('\' + $taskName) -and $registration.campaign_id -ceq $CampaignId -and
        $registration.mode -ceq $Mode -and $registration.principal_sid -ceq $userSid) 'TASK_REGISTRATION_BINDING'
    Require ((Hash-File $requestPath) -ceq $registration.request_sha256) 'TASK_REQUEST_CHANGED'
    Require ((Hash-File $xmlPath) -ceq $registration.task_definition_sha256 -and
        (Hash-Text ([string]$task.Xml)) -ceq $registration.task_definition_sha256) 'TASK_XML_CHANGED'
    Assert-Definition $task $Mode
    $instances = $task.GetInstances(0)
    if ($Command -eq 'status') {
        $rows = @()
        foreach ($instance in $instances) {
            $rows += [ordered]@{ instance_guid = [string]$instance.InstanceGuid
                state = [int]$instance.State; scheduler_engine_pid = [int]$instance.EnginePID }
        }
        [ordered]@{ schema = 'HH-GT06-TASK-STATUS-1'; task_path = '\' + $taskName
            campaign_id = $CampaignId; mode = $Mode; launch_number = $LaunchNumber; state = [int]$task.State
            last_run_time = $task.LastRunTime.ToString('o'); last_task_result = [long]$task.LastTaskResult
            instances = $rows; output_directory = $outputDirectory; formal_acceptance = $false
            status_scope = 'Scheduler state only; not actual process exit or owned-tree proof'
        } | ConvertTo-Json -Depth 12
        exit 0
    }

    $stage = 'delete'
    Require ($instances.Count -eq 0) 'TASK_RUNNING_DELETE_REFUSED_USE_STOP_REQUEST'
    # Delete only this exact verified, nonrunning task. Evidence is retained.
    $folder.DeleteTask($taskName, 0)
    Require ($null -eq (Get-OwnTask $folder $taskName)) 'TASK_DELETE_UNPROVEN'
    $deleted = [ordered]@{ schema = 'HH-GT06-TASK-DELETED-1'; task_path = '\' + $taskName
        campaign_id = $CampaignId; launch_number = $LaunchNumber; deleted_utc = [DateTime]::UtcNow.ToString('o')
        task_definition_sha256 = $registration.task_definition_sha256; formal_acceptance = $false }
    Write-NewJson (Join-Path $outputDirectory 'task-deleted.json') $deleted
    $deleted | ConvertTo-Json -Depth 12
    exit 0
} catch {
    # A failed/uncertain Run call is never automatically retried or deleted.
    # Preserve the task for exact status inspection and the original exception.
    $failure = [ordered]@{ schema = 'HH-GT06-TASK-LAUNCHER-FAILURE-1'; campaign_id = $CampaignId
        command = $Command; launch_number = $LaunchNumber; stage = $stage; run_invoked = $runInvoked
        exception_type = $_.Exception.GetType().FullName; message = $_.Exception.Message
        hresult = $_.Exception.HResult; utc = [DateTime]::UtcNow.ToString('o'); formal_acceptance = $false }
    if ($Command -eq 'register-run' -and $createdOutput -and $outputDirectory -and [System.IO.Directory]::Exists($outputDirectory)) {
        try { Write-NewJson (Join-Path $outputDirectory 'launcher-failure.json') $failure } catch { }
    }
    $failure | ConvertTo-Json -Depth 12 | Write-Error
    exit 1
}
