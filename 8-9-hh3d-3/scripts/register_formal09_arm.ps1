[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RequestPath,
      [string]$TaskName = 'HHStudio.GT06.arm-formal09-20261002')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$arm = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'arm_formal_window.py'))
$name = $TaskName
$python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
$pythonw = Join-Path ([IO.Path]::GetDirectoryName($python)) 'pythonw.exe'
$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
$existing = $null
try { $existing = $folder.GetTask($name) } catch { $existing = $null }
if ($null -ne $existing) { throw 'ARM_TASK_ALREADY_EXISTS' }
$definition = $service.NewTask(0)
$definition.RegistrationInfo.Author = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$definition.RegistrationInfo.Description = 'HH Studio O8 one-shot formal09 arm'
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
$trigger = $definition.Triggers.Create(1)
$trigger.StartBoundary = ([DateTimeOffset]::Parse($request.start)).ToLocalTime().ToString('yyyy-MM-ddTHH:mm:ss')
$trigger.Enabled = $true
$action = $definition.Actions.Create(0)
$action.Id = 'formal09-arm'
$action.Path = $pythonw
$action.Arguments = ('-B "{0}" --run "{1}"' -f $arm, [IO.Path]::GetFullPath($RequestPath))
$action.WorkingDirectory = $root
$task = $folder.RegisterTaskDefinition($name, $definition, 2, $definition.Principal.UserId, $null, 3, $null)
if ($task.Path -ne ('\' + $name) -or $task.GetInstances(0).Count -ne 0 -or -not $task.Definition.Settings.WakeToRun) { throw 'ARM_TASK_BINDING' }
[ordered]@{ task_path='\'+$name; start_boundary=$trigger.StartBoundary; request=$RequestPath; pythonw=$pythonw; arm=$arm; wake_to_run=$true } | ConvertTo-Json
