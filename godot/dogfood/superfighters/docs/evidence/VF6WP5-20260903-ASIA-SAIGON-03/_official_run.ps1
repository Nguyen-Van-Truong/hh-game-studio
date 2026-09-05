$ErrorActionPreference = "Stop"
$root = "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio"
$prod = Join-Path $root "godot\dogfood\superfighters"
$godot = Join-Path $env:LOCALAPPDATA "HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64_console.exe"
$runId = "VF6WP5-20260903-ASIA-SAIGON-03"
$ev = Join-Path $prod "docs\evidence\$runId"
$review = Join-Path $prod "docs\review\$runId"
$hlEv = Join-Path $prod ".evidence\$runId-headless"
$winEv = Join-Path $prod ".evidence\$runId-window"
New-Item -ItemType Directory -Force -Path $ev, $review, $hlEv, $winEv | Out-Null

function Count-Leftover {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match "Godot" -and $_.CommandLine -and
        $_.CommandLine -like "*$prod*" -and
        $_.CommandLine -notlike "*critic-vf6wp5*"
    }).Count
}

function Invoke-Godot {
    param(
        [string]$LogPath,
        [string[]]$GodotArgs
    )
    $errPath = "$LogPath.err"
    if (Test-Path $LogPath) { Remove-Item $LogPath -Force }
    if (Test-Path $errPath) { Remove-Item $errPath -Force }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $godot -ArgumentList $GodotArgs -WorkingDirectory $prod -PassThru -NoNewWindow -RedirectStandardOutput $LogPath -RedirectStandardError $errPath
    $ours = @($p.Id)
    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $p.Id } | ForEach-Object { $ours += $_.ProcessId }
    while (-not $p.HasExited) {
        Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match "Godot" -and $_.CommandLine -like "*$prod*" -and $_.CommandLine -notlike "*critic-vf6wp5*" -and ($ours -notcontains $_.ProcessId)
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 5
    }
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        $kids = @(Get-CimInstance Win32_Process | Where-Object { ($ours -contains $_.ProcessId) -or ($_.ParentProcessId -eq $p.Id) })
        if ($kids.Count -eq 0) { break }
        Start-Sleep -Seconds 2
    }
    $sw.Stop()
    if (Test-Path $errPath) {
        $errText = Get-Content -Raw -Path $errPath -ErrorAction SilentlyContinue
        if ($errText) { Add-Content -Path $LogPath -Value $errText }
    }
    $code = 1
    if ($null -ne $p.ExitCode) { $code = $p.ExitCode }
    [pscustomobject]@{
        ExitCode = $code
        Elapsed  = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    }
}

Set-Location $root
$env:HH_VF_STAGE_STORE = "progress_vf6wp5_stage.json"
$env:HH_VF_SURVIVAL_STORE = "records_vf6wp5.json"
Remove-Item Env:HH_VF_SURVIVAL_SOAK_SEC -ErrorAction SilentlyContinue
Remove-Item Env:HH_VF_BOTS_COMPACT -ErrorAction SilentlyContinue

$before = Count-Leftover
if ($before -ne 0) { throw "leftover=$before before official start" }

$checkLog = Join-Path $ev "check.log"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
python (Join-Path $prod "tests\check_bots.py") | Tee-Object -FilePath $checkLog
$checkExit = $LASTEXITCODE
$sw.Stop()
$afterCheck = Count-Leftover
Write-Output "CHECK_EXIT=$checkExit leftover=$afterCheck elapsed=$([math]::Round($sw.Elapsed.TotalSeconds,1))"
if ($checkExit -ne 0) { throw "check_bots failed" }

python (Join-Path $prod "tests\pack_bots_evidence.py") --write-freeze --product $prod --freeze (Join-Path $ev "freeze.json") --evidence $ev --review $review --headless-evidence $hlEv --window-evidence $winEv --base-head "1567956" --godot-exe $godot --headless-log (Join-Path $ev "official_headless.log") --window-log (Join-Path $ev "official_window.log") --run-all-log (Join-Path $ev "official_run_all.log") --check-log $checkLog --headless-exit 0 --window-exit 0 --run-all-exit 0 --check-exit 0 --leftover 0 --leftover-proof (Join-Path $ev "leftover_proof.json") --exits-proof (Join-Path $ev "exits_proof.json")
if ($LASTEXITCODE -ne 0) { throw "freeze failed" }

$env:HH_VF_EVIDENCE_DIR = $hlEv
$hl = Invoke-Godot -LogPath (Join-Path $ev "official_headless.log") -GodotArgs @(
    "--path", $prod, "--headless", "--script", "res://tests/run_bots.gd"
)
Start-Sleep -Seconds 2
$afterHl = Count-Leftover
Write-Output "HEADLESS_EXIT=$($hl.ExitCode) leftover=$afterHl elapsed=$($hl.Elapsed)"
if ($hl.ExitCode -ne 0 -or $afterHl -ne 0) { throw "headless failed leftover=$afterHl" }

Remove-Item Env:HH_VF_BOTS_COMPACT -ErrorAction SilentlyContinue
$env:HH_VF_EVIDENCE_DIR = $winEv
$win = Invoke-Godot -LogPath (Join-Path $ev "official_window.log") -GodotArgs @(
    "--path", $prod, "--script", "res://tests/run_bots.gd"
)
Start-Sleep -Seconds 2
$afterWin = Count-Leftover
Write-Output "WINDOW_EXIT=$($win.ExitCode) leftover=$afterWin elapsed=$($win.Elapsed)"
if ($win.ExitCode -ne 0 -or $afterWin -ne 0) { throw "window failed leftover=$afterWin" }

Remove-Item Env:HH_VF_EVIDENCE_DIR -ErrorAction SilentlyContinue
Remove-Item Env:HH_VF_BOTS_COMPACT -ErrorAction SilentlyContinue
# Shared suites changed (run_all no compact). Full leftover-0 run_all.
# Survival soak stays run_all.gd default (WP4); do not hide bots behind compact.
$all = Invoke-Godot -LogPath (Join-Path $ev "official_run_all.log") -GodotArgs @(
    "--path", $prod, "--headless", "--script", "res://tests/run_all.gd"
)
Start-Sleep -Seconds 2
$afterAll = Count-Leftover
Write-Output "RUN_ALL_EXIT=$($all.ExitCode) leftover=$afterAll elapsed=$($all.Elapsed)"
if ($all.ExitCode -ne 0 -or $afterAll -ne 0) { throw "run_all failed leftover=$afterAll" }

$leftover = [math]::Max($afterHl, [math]::Max($afterWin, $afterAll))
$proof = @{
    leftover             = $leftover
    after_check          = $afterCheck
    after_headless       = $afterHl
    after_window         = $afterWin
    after_run_all        = $afterAll
    path                 = $prod
    counted_product_path = $prod
    excluded             = "critic-vf6wp5*"
    scan                 = "Win32_Process Name~Godot; CommandLine contains product --path; exclude critic-vf6wp5*"
    window_exe           = $godot
    window_host_exit     = $win.ExitCode
    window_elapsed_sec   = $win.Elapsed
    headless_host_exit   = $hl.ExitCode
    headless_elapsed_sec = $hl.Elapsed
    run_all_host_exit    = $all.ExitCode
    run_all_elapsed_sec  = $all.Elapsed
    host                 = "System.Diagnostics.Process WaitForExit"
    note                 = "leftover-0 on product --path only; critic-vf6wp5 iso excluded"
}
$exits = @{
    check    = $checkExit
    headless = $hl.ExitCode
    window   = $win.ExitCode
    run_all  = $all.ExitCode
    host     = "System.Diagnostics.Process.ExitCode"
}
python -c "import json, sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps(json.loads(sys.argv[2]), indent=2) + chr(10), encoding='utf-8')" (Join-Path $ev "leftover_proof.json") ($proof | ConvertTo-Json -Compress)
python -c "import json, sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps(json.loads(sys.argv[2]), indent=2) + chr(10), encoding='utf-8')" (Join-Path $ev "exits_proof.json") ($exits | ConvertTo-Json -Compress)
Write-Output "PROOF leftover=$leftover hl=$($hl.Elapsed) win=$($win.Elapsed) all=$($all.Elapsed)"

python (Join-Path $prod "tests\pack_bots_evidence.py") `
    --product $prod `
    --evidence $ev `
    --review $review `
    --headless-evidence $hlEv `
    --window-evidence $winEv `
    --base-head "1567956" `
    --godot-exe $godot `
    --headless-log (Join-Path $ev "official_headless.log") `
    --window-log (Join-Path $ev "official_window.log") `
    --run-all-log (Join-Path $ev "official_run_all.log") `
    --check-log $checkLog `
    --headless-exit $hl.ExitCode `
    --window-exit $win.ExitCode `
    --run-all-exit $all.ExitCode `
    --check-exit $checkExit `
    --leftover $leftover `
    --leftover-proof (Join-Path $ev "leftover_proof.json") `
    --exits-proof (Join-Path $ev "exits_proof.json") `
    --freeze (Join-Path $ev "freeze.json")
Write-Output "PACK_EXIT=$LASTEXITCODE"
exit $LASTEXITCODE
