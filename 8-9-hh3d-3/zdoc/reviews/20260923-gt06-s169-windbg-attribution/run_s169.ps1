$ErrorActionPreference = 'Stop'
$runDir = $PSScriptRoot
$tempRoot = [IO.Path]::GetTempPath()
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$exe = Join-Path $tempRoot ("hh3d-s169-" + $stamp + ".exe")
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$pkg = (Get-AppxPackage -Name Microsoft.WinDbg -ErrorAction Stop).InstallLocation
$cdb = Join-Path $pkg 'amd64\cdb.exe'
$source = Join-Path $runDir 'native_fixture_s169.cs'
$commands = Join-Path $runDir 'cdb-commands.txt'
$compileOut = Join-Path $runDir 'compile.stdout.txt'
$compileErr = Join-Path $runDir 'compile.stderr.txt'
$targetOut = Join-Path $runDir 'target.stdout.jsonl'
$targetErr = Join-Path $runDir 'target.stderr.txt'
$cdbOut = Join-Path $runDir 'cdb.stdout.txt'
$cdbErr = Join-Path $runDir 'cdb.stderr.txt'
$cdbLogo = Join-Path $runDir 'cdb.logo.txt'
$receiptPath = Join-Path $runDir 's169-attribution-result.json'

function New-RedirectedProcess([string]$file, [string[]]$arguments) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $file
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($arg in $arguments) { [void]$info.ArgumentList.Add($arg) }
    $info.WorkingDirectory = $runDir
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    [void]$process.Start()
    $outLines = [Collections.Concurrent.ConcurrentQueue[string]]::new()
    $errLines = [Collections.Concurrent.ConcurrentQueue[string]]::new()
    $process.add_OutputDataReceived({ param($sender, $event) if ($null -ne $event.Data) { $outLines.Enqueue($event.Data) } })
    $process.add_ErrorDataReceived({ param($sender, $event) if ($null -ne $event.Data) { $errLines.Enqueue($event.Data) } })
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    return [pscustomobject]@{ Process = $process; OutLines = $outLines; ErrLines = $errLines }
}

& $csc /nologo /target:exe /out:$exe $source 1> $compileOut 2> $compileErr
$compileExit = $LASTEXITCODE
if ($compileExit -ne 0) { throw "C# compile failed: $compileExit" }

$target = New-RedirectedProcess $exe @()
$targetPid = $target.Process.Id
$targetReady = $false
$readyDeadline = [Diagnostics.Stopwatch]::StartNew()
while ($readyDeadline.Elapsed.TotalSeconds -lt 10) {
    Start-Sleep -Milliseconds 100
    $targetOutText = ($target.OutLines.ToArray() -join "`n")
    if ($targetOutText -match '"kind":"ready"') { $targetReady = $true; break }
}
if (-not $targetReady) { throw 'target did not reach ready marker' }
$targetIdentity = Get-Process -Id $targetPid -ErrorAction Stop | Select-Object Id,ProcessName,Path,StartTime
$cdbArgs = @('-p', [string]$targetPid, '-pd', '-nosqm', '-netsyms', 'no', '-logo', $cdbLogo, '-cf', $commands)
$debugger = New-RedirectedProcess $cdb $cdbArgs
$cdbPid = $debugger.Process.Id
$attached = $false
$attachDeadline = [Diagnostics.Stopwatch]::StartNew()
while ($attachDeadline.Elapsed.TotalSeconds -lt 20) {
    Start-Sleep -Milliseconds 100
    $combined = ($debugger.OutLines.ToArray() -join "`n")
    if (Test-Path $cdbLogo) { $combined += "`n" + (Get-Content -LiteralPath $cdbLogo -Raw) }
    if ($combined -match 'CDB_ATTACHED') { $attached = $true; break }
    if ($debugger.Process.HasExited) { break }
}
if (-not $attached) { throw 'CDB did not emit CDB_ATTACHED' }
$target.Process.StandardInput.WriteLine('break_ready')
$target.Process.StandardInput.WriteLine('open')
$target.Process.StandardInput.Flush()

$deadline = [Diagnostics.Stopwatch]::StartNew()
while ($deadline.Elapsed.TotalSeconds -lt 60 -and (-not $debugger.Process.HasExited)) { Start-Sleep -Milliseconds 100 }
if (-not $debugger.Process.HasExited) { Stop-Process -Id $cdbPid -Force -ErrorAction SilentlyContinue }
$targetDeadline = [Diagnostics.Stopwatch]::StartNew()
while ($targetDeadline.Elapsed.TotalSeconds -lt 15 -and (-not $target.Process.HasExited)) { Start-Sleep -Milliseconds 100 }
if (-not $target.Process.HasExited) { Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue }
if (-not $debugger.Process.HasExited) { $debugger.Process.WaitForExit(2000) | Out-Null }
if (-not $target.Process.HasExited) { $target.Process.WaitForExit(2000) | Out-Null }
$stdoutText = ($debugger.OutLines.ToArray() -join "`n")
$stderrText = ($debugger.ErrLines.ToArray() -join "`n")
$logoText = if (Test-Path $cdbLogo) { Get-Content -LiteralPath $cdbLogo -Raw } else { '' }
$targetText = ($target.OutLines.ToArray() -join "`n")
$targetErrText = ($target.ErrLines.ToArray() -join "`n")
$allDebuggerText = $stdoutText + "`n" + $logoText
$receipt = [ordered]@{
    schema = 'gt06-s169-windbg-attribution-v1'
    run_id = 'gt06-s169-windbg-attribution-01'
    command_id = 'cmd.gt06.s169.windbg-htrace.1'
    authority = 0
    diagnostic_only = $true
    source_closure = 'fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde'
    profile_sha256 = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fc' + 'd6dbf4d85'
    debugger = [ordered]@{ path = $cdb; version = ([Diagnostics.FileVersionInfo]::GetVersionInfo($cdb).FileVersion); sha256 = (Get-FileHash -LiteralPath $cdb -Algorithm SHA256).Hash.ToLowerInvariant(); attached_marker = $attached; cdb_exit = if ($debugger.Process.HasExited) { $debugger.Process.ExitCode } else { $null } }
    target = [ordered]@{ pid = $targetPid; start = $targetIdentity.StartTime.ToUniversalTime().ToString('o'); executable = $targetIdentity.Path; target_exit = if ($target.Process.HasExited) { $target.Process.ExitCode } else { $null } }
    markers = [ordered]@{ htrace_enable = ($allDebuggerText -match '(?i)htrace.*(enabled|enable|success|tracing)'); ready_break = ($allDebuggerText -match 'READY_BREAK'); open_break = ($allDebuggerText -match 'OPEN_BREAK'); close_break = ($allDebuggerText -match 'CLOSE_BREAK'); diff_present = ($allDebuggerText -match '(?i)htrace|handle|stack') }
    target_markers = [ordered]@{ start = ($targetText -match '"kind":"start"'); ready = ($targetText -match '"kind":"ready"'); open = ($targetText -match '"kind":"open"'); close = ($targetText -match '"kind":"close"'); exit = ($targetText -match '"kind":"exit"') }
    stderr = [ordered]@{ debugger = $stderrText; target = $targetErrText }
    forced_cleanup = [ordered]@{ debugger = (-not $debugger.Process.HasExited); target = (-not $target.Process.HasExited) }
    status = 'DIAGNOSTIC_RETAINED_AUTHORITY_0'
    exclusions = @('F13','F14','GT06_DATASET','LEAK_PROOF','ROOT_CAUSE','REPAIR_AUTHORIZATION','GT06_ACCEPTANCE')
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output ('RUN_DIR=' + $runDir)
Write-Output ('TARGET_PID=' + $targetPid)
Write-Output ('CDB_PID=' + $cdbPid)
Write-Output ('TARGET_EXIT=' + $receipt.target.target_exit)
Write-Output ('CDB_EXIT=' + $receipt.debugger.cdb_exit)
Write-Output ('RECEIPT=' + $receiptPath)
