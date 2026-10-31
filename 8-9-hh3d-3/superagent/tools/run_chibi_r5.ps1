param(
    [ValidatePattern('^[a-zA-Z0-9_-]{1,64}$')][string]$RunId = 'chibi-r5-check',
    [ValidateSet('regression','temporal','pause','debris','capture','master','match','runtime','animation','all','r6pose','r6projectiles','r6hatches','r6pickups','r6integration','r6visual','r6hatchcapture','r6','r7geometry','r7style','r7visual','r7perf','r7perfbaseline','r7')][string]$Stage = 'regression',
    [string]$EnginePath = '',
    [switch]$Schedule
)
$ErrorActionPreference = 'Stop'
$productRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$studioRoot = Split-Path $productRoot
$engine = Join-Path $studioRoot 'studio/.local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe'
if (-not [string]::IsNullOrWhiteSpace($EnginePath)) { $engine = (Resolve-Path -LiteralPath $EnginePath).Path }
$reviewRoot = Join-Path $productRoot ('.local/reviews/' + $RunId)
if ($Schedule) {
    $taskName = 'HH-Chibi-R5-' + $RunId
    $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -RunId ' + $RunId + ' -Stage ' + $Stage
    $arguments += ' -EnginePath "' + $engine + '"'
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $productRoot
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 12)
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Write-Output ('SCHEDULED ' + $taskName + ' receipt=' + $reviewRoot)
    exit 0
}
if (Test-Path -LiteralPath (Join-Path $reviewRoot 'receipt.json')) { throw 'Run id already has a receipt; use a fresh RunId.' }
New-Item -ItemType Directory -Force -Path $reviewRoot | Out-Null
$active = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Godot*' -and $_.CommandLine -like ('*' + $productRoot + '*') })
if ($active.Count -gt 0) { throw 'Godot already running for this project.' }
# Capture the runtime closure, import settings, tests and authoring sources.
# docs/ contains generated captures; .godot/.local are generated engine/host state.
function Get-SourcePaths {
    $files = @('project.godot')
    foreach ($folder in @('game','data','scenes','assets','tests','tools','art/chibi_r5')) {
        $full = Join-Path $productRoot $folder
        if (Test-Path -LiteralPath $full) {
            $files += Get-ChildItem -LiteralPath $full -Recurse -File | ForEach-Object { $_.FullName.Substring($productRoot.Length + 1).Replace('\','/') }
        }
    }
    $paths = [string[]]@($files | Sort-Object -Unique)
    # Identical canonical order in Windows PowerShell 5.1 and PowerShell 7.
    [Array]::Sort($paths, [StringComparer]::Ordinal)
    return $paths
}
$changedFiles = Get-SourcePaths
$source = @{}
foreach ($rel in $changedFiles) { $source[$rel] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $productRoot $rel)).Hash }
$canonical = ($changedFiles | ForEach-Object { $_ + '=' + $source[$_] }) -join "`n"
$hasher = [System.Security.Cryptography.SHA256]::Create()
$closureHash = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-','')
$hasher.Dispose()
@{run_id=$RunId; closure_sha256=$closureHash; source_sha256=$source} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $reviewRoot 'source-freeze.json') -Encoding UTF8
$stages = if ($Stage -eq 'all') { @('regression','temporal','pause','debris','master','capture','match','runtime','animation') } else { @($Stage) }
if ($Stage -eq 'r6') { $stages = @('regression','temporal','pause','debris','master','r6pose','r6projectiles','r6hatches','r6pickups','r6integration','r6visual','r6hatchcapture','runtime') }
if ($Stage -eq 'r7') { $stages = @('regression','temporal','pause','debris','master','r6pose','r6projectiles','r6hatches','r6pickups','r6integration','r7geometry','r7style','r7visual','r7perf','runtime') }
$rows = @()
$ok = $true
$producedEvidence = @{}
$completionMarkers = @{
    regression = '\[CHIBI R5 REGRESSION\] PASS: \d+ checks'
    temporal = '\[CHIBI R5 TEMPORAL\] PASS checks=\d+ failures=0'
    pause = '\[CHIBI R5 PAUSE\].*PASS checks=\d+ failures=0'
    debris = '\[CHIBI R5 DEBRIS\].*PASS checks=\d+ failures=0'
    master = '\[MASTER TEST RUNNER\] ALL 148 CHECKS PASSED'
    capture = '\[CHIBI R5 CAPTURE\] PASS: wrote 4 diagnostic viewport contact sheets'
    match = '\[R5 LIVE\] complete: viewport-only integration diagnostics'
    runtime = '\[CHIBI R5 RUNTIME\] PASS checks=\d+ failures=0 cycles=20 '
    animation = '\[CHIBI R5 ANIMATION CAPTURE\] PASS: frames=36 '
    r6pose = '\[CHIBI R6 POSE\] PASS: \d+ checks'
    r6projectiles = '\[CHIBI R6 PROJECTILES\].*PASS checks=\d+ failures=0'
    r6hatches = '\[CHIBI R6 HATCH\].*PASS checks=\d+ failures=0'
    r6pickups = '\[CHIBI R6 PICKUPS\].*PASS checks=\d+ failures=0'
    r6integration = '\[CHIBI R6 INTEGRATION\].*PASS checks=\d+ failures=0'
    r6visual = '\[CHIBI R6 VISUAL\] PASS frames=36 sheets=1'
    r6hatchcapture = '\[CHIBI R6 HATCH CAPTURE\] PASS captures=3 failures=0'
    r7geometry = '\[CHIBI R7 GEOMETRY\] PASS checks=\d+ failures=0'
    r7visual = '\[CHIBI R7 VISUAL\] PASS frames=48 sheets=1'
    r7perf = '\[CHIBI R7 RENDER PERF\] PASS samples=120 '
    r7perfbaseline = '\[CHIBI R7 RENDER PERF\] PASS samples=120 '
    r7style = '\[CHIBI R7 STYLE\] PASS checks=\d+ failures=0'
}
$expectedOutputs = @{
    capture = @('01_punches_diagnostic.png','02_guns_diagnostic.png','03_actions_diagnostic.png','04_roster_diagnostic.png')
    match = @('05_menu.png','06_live_1280_f245.png','06_live_1280_f355.png','07_live_1280_f245.png','07_live_1280_f355.png','08_live_960_f245.png','08_live_960_f355.png')
    runtime = @('runtime_play.png','runtime_paused.png','runtime_menu.png','runtime_input_report.json')
    animation = @(0..35 | ForEach-Object { 'combo_frames/frame_{0:D4}.png' -f $_ })
    r6visual = @('poses.png') + @(0..35 | ForEach-Object { 'motion_frames/frame_{0:D4}.png' -f $_ })
    r6hatchcapture = @('hatch_008.png','hatch_028.png','hatch_056.png','hatch_trajectories.json')
    r7visual = @('joints.png') + @(0..47 | ForEach-Object { 'motion_frames/frame_{0:D4}.png' -f $_ })
}
foreach ($item in $stages) {
    $script = switch ($item) {
        'regression' { 'res://tests/chibi_r5_regression.gd' }
        'temporal' { 'res://tests/chibi_r5_temporal_regression.gd' }
        'pause' { 'res://tests/chibi_r5_pause_regression.gd' }
        'debris' { 'res://tests/chibi_r5_debris_regression.gd' }
        'capture' { 'res://tests/chibi_r5_capture.gd' }
        'master' { 'res://tests/test_runner.gd' }
        'match' { 'res://tests/chibi_r5_match_capture.gd' }
        'runtime' { 'res://tests/chibi_r5_runtime_input.gd' }
        'animation' { 'res://tests/chibi_r5_animation_capture.gd' }
        'r6pose' { 'res://tests/chibi_r6_pose_regression.gd' }
        'r6projectiles' { 'res://tests/chibi_r6_projectile_regression.gd' }
        'r6hatches' { 'res://tests/chibi_r6_hatch_regression.gd' }
        'r6pickups' { 'res://tests/chibi_r6_pickup_regression.gd' }
        'r6integration' { 'res://tests/chibi_r6_integration_regression.gd' }
        'r6visual' { 'res://tests/chibi_r6_visual_capture.gd' }
        'r6hatchcapture' { 'res://tests/chibi_r6_hatch_capture.gd' }
        'r7geometry' { 'res://tests/chibi_r7_geometry_regression.gd' }
        'r7visual' { 'res://tests/chibi_r7_visual_capture.gd' }
        'r7perf' { 'res://tests/chibi_r7_render_perf.gd' }
        'r7perfbaseline' { 'res://tests/chibi_r7_render_perf.gd' }
        'r7style' { 'res://tests/chibi_r7_style_regression.gd' }
    }
    $stdout = Join-Path $reviewRoot ($item + '.stdout.log')
    $stderr = Join-Path $reviewRoot ($item + '.stderr.log')
    $engineArgs = @('--path', ('"' + $productRoot + '"'), '--script', $script, '--audio-driver', 'Dummy')
    if ($item -in @('capture','match','runtime','animation','r6visual','r6hatchcapture','r7visual','r7perf','r7perfbaseline')) { $engineArgs += @('--rendering-method','gl_compatibility','--resolution','1280x720','--position','-32000,-32000') }
    else { $engineArgs += '--headless' }
    if ($item -eq 'r7perfbaseline') { $engineArgs += @('--','--baseline') }
    $started = [DateTime]::UtcNow
    $proc = Start-Process -FilePath $engine -ArgumentList $engineArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    # Windows PowerShell 5.1 (Task Scheduler) must retain the process handle
    # before a short-lived worker exits; otherwise ExitCode may remain null.
    $processHandle = $proc.Handle
    $finished = $proc.WaitForExit(240000)
    if (-not $finished) { $proc.Kill(); $proc.WaitForExit() }
    $actualExit = $proc.ExitCode
    $errorText = [IO.File]::ReadAllText($stderr)
    $outText = [IO.File]::ReadAllText($stdout)
    $markerFound = $outText -match $completionMarkers[$item]
    $evidenceErrors = @()
    $stageOutputs = @()
    if ($expectedOutputs.ContainsKey($item)) { $stageOutputs = @($expectedOutputs[$item]) }
    foreach ($relativeOutput in $stageOutputs) {
        if ([string]::IsNullOrEmpty($relativeOutput)) { continue }
        $evidenceRel = $(if ($item.StartsWith('r7')) { 'docs/chibi-r7/' } elseif ($item.StartsWith('r6')) { 'docs/chibi-r6/' } else { 'docs/chibi-r5/' }) + $relativeOutput
        $evidencePath = Join-Path $productRoot $evidenceRel
        if (-not (Test-Path -LiteralPath $evidencePath)) { $evidenceErrors += ('missing:' + $evidenceRel); continue }
        $fileInfo = Get-Item -LiteralPath $evidencePath
        if ($fileInfo.Length -eq 0 -or $fileInfo.LastWriteTimeUtc -lt $started) { $evidenceErrors += ('empty_or_stale:' + $evidenceRel); continue }
        $producedEvidence[$evidenceRel] = (Get-FileHash -LiteralPath $evidencePath).Hash
    }
    $stageOk = $finished -and $actualExit -eq 0 -and $markerFound -and $evidenceErrors.Count -eq 0 -and ($errorText + $outText) -notmatch '(?m)(SCRIPT ERROR|ERROR:|WARNING:)'
    $rows += @{stage=$item; pid=$proc.Id; started_utc=$started.ToString('o'); elapsed_s=([DateTime]::UtcNow-$started).TotalSeconds; actual_exit=$actualExit; timed_out=(-not $finished); completion_marker_found=$markerFound; evidence_errors=$evidenceErrors; expected_output_count=$stageOutputs.Count; ok=$stageOk; stdout_sha256=(Get-FileHash $stdout).Hash; stderr_sha256=(Get-FileHash $stderr).Hash}
    if (-not $stageOk) { $ok=$false; break }
}
$drift = @()
foreach ($rel in $changedFiles) {
    $path = Join-Path $productRoot $rel
    if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path).Hash -ne $source[$rel]) { $drift += $rel }
}
foreach ($rel in (Get-SourcePaths)) { if (-not $source.ContainsKey($rel)) { $drift += $rel } }
$leftover = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Godot*' -and $_.CommandLine -like ('*' + $productRoot + '*') })
$receipt = @{schema='chibi-r5.host-receipt.v3';run_id=$RunId;command_id=('cmd.'+$RunId);scope='diagnostic/regression - not owner art acceptance';engine=$engine;engine_sha256=(Get-FileHash $engine).Hash;closure_sha256=$closureHash;source_count=$source.Count;source_sha256=$source;source_drift=$drift;stages=$rows;evidence_sha256=$producedEvidence;leftover_count=$leftover.Count;ok=($ok -and $drift.Count -eq 0 -and $leftover.Count -eq 0)}
$receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $reviewRoot 'receipt.json') -Encoding UTF8
Write-Output (@{run_id=$RunId;ok=$receipt.ok;closure_sha256=$closureHash;source_count=$source.Count;stages=$rows;source_drift=$drift;leftovers=$leftover.Count;receipt=(Join-Path $reviewRoot 'receipt.json')} | ConvertTo-Json -Depth 6 -Compress)
if (-not $receipt.ok) { exit 1 }
