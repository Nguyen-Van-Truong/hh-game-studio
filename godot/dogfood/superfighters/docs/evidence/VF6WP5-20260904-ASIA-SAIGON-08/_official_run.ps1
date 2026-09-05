$ErrorActionPreference = "Stop"
$root = "D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio"
$prod = Join-Path $root "godot\dogfood\superfighters"
$godotConsole = Join-Path $env:LOCALAPPDATA "HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64_console.exe"
$godotEngine = Join-Path $env:LOCALAPPDATA "HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64.exe"
$godot = $godotConsole
$runId = "VF6WP5-20260904-ASIA-SAIGON-08"
$commandId = "cmd.vf6-wp5.bots.8"
$ev = Join-Path $prod "docs\evidence\$runId"
$review = Join-Path $prod "docs\review\$runId"
$hlEv = Join-Path $prod ".evidence\$runId-headless"
$winEv = Join-Path $prod ".evidence\$runId-window"
New-Item -ItemType Directory -Force -Path $ev, $review, $hlEv, $winEv | Out-Null

if (-not ("HhGodotHost.Runner" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
namespace HhGodotHost {
  public static class Runner {
    public static int Run(string exe, string args, string workdir, string stdoutPath, string stderrPath, bool createNoWindow) {
      var psi = new ProcessStartInfo();
      psi.FileName = exe;
      psi.Arguments = args;
      psi.WorkingDirectory = workdir;
      psi.UseShellExecute = false;
      psi.RedirectStandardOutput = true;
      psi.RedirectStandardError = true;
      psi.CreateNoWindow = createNoWindow;
      psi.StandardOutputEncoding = new UTF8Encoding(false);
      psi.StandardErrorEncoding = new UTF8Encoding(false);
      using (var p = new Process()) {
        p.StartInfo = psi;
        using (var outFile = new StreamWriter(stdoutPath, false, new UTF8Encoding(false)))
        using (var errFile = new StreamWriter(stderrPath, false, new UTF8Encoding(false))) {
          outFile.AutoFlush = true;
          errFile.AutoFlush = true;
          var gate = new object();
          p.OutputDataReceived += (s, e) => {
            if (e.Data == null) return;
            lock (gate) { outFile.WriteLine(e.Data); }
          };
          p.ErrorDataReceived += (s, e) => {
            if (e.Data == null) return;
            lock (gate) { errFile.WriteLine(e.Data); }
          };
          if (!p.Start()) {
            return 1;
          }
          Console.WriteLine("GODOT_PID=" + p.Id + " exe=" + exe);
          p.BeginOutputReadLine();
          p.BeginErrorReadLine();
          p.WaitForExit();
          p.WaitForExit(10000);
          lock (gate) {
            outFile.Flush();
            errFile.Flush();
          }
          return p.ExitCode;
        }
      }
    }
  }
}
"@
}

function Count-Leftover {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match "Godot" -and $_.CommandLine -and
        $_.CommandLine -like "*$prod*"
    }).Count
}

function Quote-Arg([string]$value) {
    if ($value -match '[\s"]') {
        return '"' + ($value -replace '"', '\"') + '"'
    }
    return $value
}

function Invoke-Godot {
    param(
        [string]$LogPath,
        [string[]]$GodotArgs,
        [string]$Exe,
        [switch]$ShowWindow
    )
    $errPath = "$LogPath.err"
    if (Test-Path $LogPath) { Remove-Item $LogPath -Force }
    if (Test-Path $errPath) { Remove-Item $errPath -Force }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    ## Host is System.Diagnostics.Process.WaitForExit on the engine/console
    ## worker. Nested host wrappers can leave ExitCode unset (fake 1).
    ## Do not remap PASS banners to 0.
    $argStr = ($GodotArgs | ForEach-Object { Quote-Arg $_ }) -join " "
    $createNoWindow = -not [bool]$ShowWindow
    $code = [HhGodotHost.Runner]::Run($Exe, $argStr, $prod, $LogPath, $errPath, $createNoWindow)
    $sw.Stop()
    if (Test-Path $errPath) {
        $errText = Get-Content -Raw -Path $errPath -ErrorAction SilentlyContinue
        if ($errText) { Add-Content -Path $LogPath -Value $errText }
    }
    [pscustomobject]@{
        ExitCode = [int]$code
        Elapsed  = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    }
}

Set-Location $root
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "_resume_window"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
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

Copy-Item -Force -Path (Join-Path $prod "tests\run_bots_official.ps1") -Destination (Join-Path $ev "_official_run.ps1")

$freezeArgs = @(
    (Join-Path $prod "tests\pack_bots_evidence.py"),
    "--write-freeze",
    "--product", $prod,
    "--freeze", (Join-Path $ev "freeze.json"),
    "--evidence", $ev,
    "--review", $review,
    "--headless-evidence", $hlEv,
    "--window-evidence", $winEv,
    "--base-head", "04cb6ca",
    "--godot-exe", $godotConsole,
    "--headless-log", (Join-Path $ev "official_headless.log"),
    "--window-log", (Join-Path $ev "official_window.log"),
    "--run-all-log", (Join-Path $ev "official_run_all.log"),
    "--check-log", $checkLog,
    "--headless-exit", "0",
    "--window-exit", "0",
    "--run-all-exit", "0",
    "--check-exit", "0",
    "--leftover", "0",
    "--leftover-proof", (Join-Path $ev "leftover_proof.json"),
    "--exits-proof", (Join-Path $ev "exits_proof.json")
)
python @freezeArgs
if ($LASTEXITCODE -ne 0) { throw "freeze failed" }

$env:HH_VF_EVIDENCE_DIR = $hlEv
$hl = Invoke-Godot -Exe $godotEngine -LogPath (Join-Path $ev "official_headless.log") -GodotArgs @(
    "--path", $prod, "--headless", "--script", "res://tests/run_bots.gd"
)
Start-Sleep -Seconds 2
$afterHl = Count-Leftover
Write-Output "HEADLESS_EXIT=$($hl.ExitCode) leftover=$afterHl elapsed=$($hl.Elapsed)"
if ($hl.ExitCode -ne 0 -or $afterHl -ne 0) { throw "headless failed leftover=$afterHl" }

Remove-Item Env:HH_VF_BOTS_COMPACT -ErrorAction SilentlyContinue
$env:HH_VF_EVIDENCE_DIR = $winEv
$win = Invoke-Godot -Exe $godotConsole -ShowWindow -LogPath (Join-Path $ev "official_window.log") -GodotArgs @(
    "--path", $prod, "--script", "res://tests/run_bots.gd"
)
Start-Sleep -Seconds 2
$afterWin = Count-Leftover
Write-Output "WINDOW_EXIT=$($win.ExitCode) leftover=$afterWin elapsed=$($win.Elapsed)"
if ($win.ExitCode -ne 0 -or $afterWin -ne 0) { throw "window failed leftover=$afterWin" }

Remove-Item Env:HH_VF_EVIDENCE_DIR -ErrorAction SilentlyContinue
Remove-Item Env:HH_VF_BOTS_COMPACT -ErrorAction SilentlyContinue
$all = Invoke-Godot -Exe $godotEngine -LogPath (Join-Path $ev "official_run_all.log") -GodotArgs @(
    "--path", $prod, "--headless", "--script", "res://tests/run_all.gd"
)
Start-Sleep -Seconds 2
$afterAll = Count-Leftover
Write-Output "RUN_ALL_EXIT=$($all.ExitCode) leftover=$afterAll elapsed=$($all.Elapsed)"
if ($all.ExitCode -ne 0 -or $afterAll -ne 0) { throw "run_all failed leftover=$afterAll" }

$leftover = [math]::Max($afterHl, [math]::Max($afterWin, $afterAll))
$proof = [ordered]@{
    leftover             = $leftover
    after_check          = $afterCheck
    after_headless       = $afterHl
    after_window         = $afterWin
    after_run_all        = $afterAll
    path                 = $prod
    counted_product_path = $prod
    scan                 = "Win32_Process Name~Godot; CommandLine contains product --path"
    window_exe           = $godotConsole
    engine_exe           = $godotEngine
    window_host_exit     = $win.ExitCode
    window_elapsed_sec   = $win.Elapsed
    headless_host_exit   = $hl.ExitCode
    headless_elapsed_sec = $hl.Elapsed
    run_all_host_exit    = $all.ExitCode
    run_all_elapsed_sec  = $all.Elapsed
    host                 = "System.Diagnostics.Process.WaitForExit"
    note                 = "leftover-0 on product --path only; .NET WaitForExit on engine/console worker; no banner remap"
}
$exits = [ordered]@{
    check    = $checkExit
    headless = $hl.ExitCode
    window   = $win.ExitCode
    run_all  = $all.ExitCode
    host     = "System.Diagnostics.Process.WaitForExit"
}
[System.IO.File]::WriteAllText((Join-Path $ev "leftover_proof.json"), (($proof | ConvertTo-Json -Depth 6) + "`n"))
[System.IO.File]::WriteAllText((Join-Path $ev "exits_proof.json"), (($exits | ConvertTo-Json -Depth 6) + "`n"))
Write-Output "PROOF leftover=$leftover hl=$($hl.Elapsed) win=$($win.Elapsed) all=$($all.Elapsed) command=$commandId"

python (Join-Path $prod "tests\pack_bots_evidence.py") `
    --product $prod `
    --evidence $ev `
    --review $review `
    --headless-evidence $hlEv `
    --window-evidence $winEv `
    --base-head "04cb6ca" `
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
$packExit = $LASTEXITCODE
Write-Output "PACK_EXIT=$packExit"
if ($packExit -ne 0) {
    $verdictPath = Join-Path $ev "verdict.md"
    if (Test-Path $verdictPath) {
        $txt = Get-Content -Raw -Path $verdictPath
        if ($txt -match "READY_FOR_CRITICS=yes") {
            throw "packer exit $packExit but verdict said READY=yes"
        }
    }
}
exit $packExit
