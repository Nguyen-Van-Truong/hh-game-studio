# HH Game Studio CLI (MASTER 10.1). Thin wrapper around the editor bus.
# Dot-source to get gsopen/gssend/... or run: .\tools\gs.ps1 open D:\proj
# Never prints the bus token (I8).

$script:GsToolsDir = $PSScriptRoot
$script:GsRepoRoot = Split-Path -Parent $PSScriptRoot
$script:DotSourced = $MyInvocation.InvocationName -eq '.'
$script:GsExitCode = 0

function Set-GsExitCode {
    param([int]$Code)
    $script:GsExitCode = $Code
    $global:LASTEXITCODE = $Code
}

function Get-GsRoot {
    if ($env:GS_ROOT) {
        return [System.IO.Path]::GetFullPath($env:GS_ROOT)
    }
    return [System.IO.Path]::GetFullPath((Get-Location).Path)
}

function Test-GsProcessAlive {
    param([uint32]$ProcessId)
    if ($ProcessId -eq 0) { return $false }
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-GsEndpointInfo {
    param([string]$Root)
    $path = Join-Path $Root '.gs\runtime\endpoint.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $obj = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $processId = [uint32]$obj.pid
    [pscustomobject]@{
        Host  = [string]$obj.host
        Port  = [int]$obj.port
        Pid   = $processId
        Path  = $path
        Alive = (Test-GsProcessAlive -ProcessId $processId)
    }
}

function Resolve-GsBinary {
    param([string]$Name)
    $envKey = if ($Name -eq 'gs-editor') { 'GS_EDITOR' } else { 'GS_CLI' }
    $fromEnv = [Environment]::GetEnvironmentVariable($envKey)
    if ($fromEnv -and (Test-Path -LiteralPath $fromEnv)) {
        return $fromEnv
    }
    $candidates = @(
        (Join-Path $script:GsRepoRoot "$Name.exe"),
        (Join-Path $script:GsRepoRoot "target\release\$Name.exe"),
        (Join-Path $script:GsRepoRoot "target\debug\$Name.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ }
    if (-not $candidates) { return $null }
    return @($candidates | Sort-Object LastWriteTimeUtc -Descending)[0]
}

function Resolve-GsEditor {
    Resolve-GsBinary -Name 'gs-editor'
}

function Resolve-GsCli {
    Resolve-GsBinary -Name 'gs-cli'
}

function Invoke-GsCli {
    param([string[]]$CliArgs)
    $exe = Resolve-GsCli
    if ($exe) {
        & $exe @CliArgs
        Set-GsExitCode -Code $(if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE })
        return
    }
    Push-Location $script:GsRepoRoot
    try {
        & cargo run -q -p gs-cli -- @CliArgs
        Set-GsExitCode -Code $(if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE })
    }
    finally {
        Pop-Location
    }
}

function Start-GsEditorProcess {
    param([string]$Root)
    $editor = Resolve-GsEditor
    if ($editor) {
        Start-Process -FilePath $editor -ArgumentList @($Root) -WindowStyle Hidden | Out-Null
        return
    }
    Start-Process -FilePath 'cargo' -ArgumentList @('run', '-q', '-p', 'gs-editor', '--', $Root) `
        -WorkingDirectory $script:GsRepoRoot -WindowStyle Hidden | Out-Null
}

function Wait-GsEndpoint {
    param([string]$Root, [int]$TimeoutSec = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $info = Get-GsEndpointInfo -Root $Root
        if ($info -and $info.Alive) { return $info }
        Start-Sleep -Milliseconds 200
    }
    throw "gs-editor did not publish a live endpoint under $Root (waited ${TimeoutSec}s)"
}

function Show-GsHelp {
    @'
HH Game Studio CLI — thin bus wrapper (MASTER 10.1)

  .\tools\gs.ps1 open <path>              start editor if needed, hello, print actor_id
  .\tools\gs.ps1 send <method> <json>     RPC call; prints command_id then result JSON
  .\tools\gs.ps1 txn <file.jsonl>         transaction.execute from JSONL
  .\tools\gs.ps1 events [-Play id]        subscribe (or obs.events when -Play)
  .\tools\gs.ps1 shot [json]
  .\tools\gs.ps1 play [-Record tape] [-Scene id] [-Headless]
  .\tools\gs.ps1 stop [-Force]
  .\tools\gs.ps1 step [n]
  .\tools\gs.ps1 dump [scene_id]
  .\tools\gs.ps1 judge [json | path.gtest.json]
  .\tools\gs.ps1 doctor                    imagegen preflight (gs-cli doctor; MASTER 8.5)

Dot-source to get functions:  . .\tools\gs.ps1 ; gsopen D:\proj ; gssend entity.spawn '{...}'
Default root: $env:GS_ROOT or the current directory. gsopen sets GS_ROOT.
command_id is printed as:  command_id: 01J...
The bus token is never printed.
'@ | Write-Output
}

function gsopen {
    param([Parameter(Position = 0)][string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { $Path = Get-GsRoot }
    $Path = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
    $env:GS_ROOT = $Path
    $info = Get-GsEndpointInfo -Root $Path
    if (-not ($info -and $info.Alive)) {
        Start-GsEditorProcess -Root $Path
        Wait-GsEndpoint -Root $Path | Out-Null
    }
    Invoke-GsCli -CliArgs @('--root', $Path, 'hello')
}

function gssend {
    param(
        [Parameter(Position = 0, Mandatory = $true)][string]$Method,
        [Parameter(Position = 1)][string]$Params = '{}'
    )
    if ([string]::IsNullOrWhiteSpace($Params)) { $Params = '{}' }
    # Windows PowerShell strips quotes when invoking a native exe; pass JSON via file.
    $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ("gs-params-{0}.json" -f [guid]::NewGuid().ToString('N')))
    try {
        [System.IO.File]::WriteAllText($tmp, $Params)
        Invoke-GsCli -CliArgs @('--root', (Get-GsRoot), '--params-file', $tmp, 'send', $Method)
    }
    finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function gstxn {
    param([Parameter(Position = 0, Mandatory = $true)][string]$File)
    $resolved = (Resolve-Path -LiteralPath $File).Path
    Invoke-GsCli -CliArgs @('--root', (Get-GsRoot), 'txn', $resolved)
}

function gsevents {
    param(
        [string]$Play,
        [int]$After = 0,
        [int]$WaitMs = 1500
    )
    if ($Play) {
        $payload = @{ play_id = $Play; after_seq = $After } | ConvertTo-Json -Compress
        gssend 'obs.events' $payload
        return
    }
    Invoke-GsCli -CliArgs @('--root', (Get-GsRoot), '--wait-ms', "$WaitMs", 'events')
}

function gsshot {
    param([Parameter(Position = 0)][string]$Params = '{}')
    gssend 'obs.screenshot' $Params
}

function gsplay {
    param(
        [string]$Record,
        [string]$Scene,
        [switch]$Headless
    )
    $o = [ordered]@{}
    if ($Record) { $o['record_tape'] = $Record }
    if ($Scene) { $o['scene_id'] = $Scene }
    if ($Headless) { $o['headless'] = $true }
    $json = if ($o.Count -eq 0) { '{}' } else { $o | ConvertTo-Json -Compress }
    gssend 'play.start' $json
}

function gsstop {
    param([switch]$Force)
    $json = if ($Force) { '{"force":true}' } else { '{}' }
    gssend 'play.stop' $json
}

function gsstep {
    param([Parameter(Position = 0)][int]$N = 1)
    $json = @{ n = $N } | ConvertTo-Json -Compress
    gssend 'play.step_frames' $json
}

function gsdump {
    param([Parameter(Position = 0)][string]$SceneId)
    $json = if ($SceneId) { @{ scene_id = $SceneId } | ConvertTo-Json -Compress } else { '{}' }
    gssend 'scene.dump' $json
}

function gsjudge {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
    if ($Rest -and $Rest.Count -eq 1 -and ($Rest[0] -match '\.gtest(\.json)?$')) {
        $payload = @{ gtest_rel = $Rest[0] } | ConvertTo-Json -Compress
        gssend 'judge.run_test' $payload
        return
    }
    if ($Rest -and $Rest.Count -ge 1 -and $Rest[0].Trim().StartsWith('{')) {
        gssend 'judge.run_until_event' $Rest[0]
        return
    }
    gssend 'judge.run_until_event' '{}'
}

function gsdoctor {
    Invoke-GsCli -CliArgs @('--root', (Get-GsRoot), 'doctor')
}

function Invoke-GsMain {
    param([string[]]$ArgList)
    Set-GsExitCode -Code 0
    if (-not $ArgList -or $ArgList.Count -eq 0) {
        Show-GsHelp
        return
    }
    $cmd = $ArgList[0]
    $tail = @()
    if ($ArgList.Count -gt 1) {
        $tail = $ArgList[1..($ArgList.Count - 1)]
    }
    switch -Regex ($cmd) {
        '^(gs)?open$' { gsopen @tail }
        '^(gs)?send$' { gssend @tail }
        '^(gs)?txn$' { gstxn @tail }
        '^(gs)?events$' { gsevents @tail }
        '^(gs)?shot$' { gsshot @tail }
        '^(gs)?play$' { gsplay @tail }
        '^(gs)?stop$' { gsstop @tail }
        '^(gs)?step$' { gsstep @tail }
        '^(gs)?dump$' { gsdump @tail }
        '^(gs)?judge$' { gsjudge @tail }
        '^(gs)?doctor$' { gsdoctor }
        '^(help|-h|--help)$' { Show-GsHelp; Set-GsExitCode -Code 0 }
        default {
            Write-Error "unknown command '$cmd' (try help)"
            Set-GsExitCode -Code 2
        }
    }
}

if (-not $script:DotSourced) {
    try {
        Invoke-GsMain -ArgList ([string[]]$args)
    }
    catch {
        Write-Error $_
        Set-GsExitCode -Code 1
    }
    exit $script:GsExitCode
}
