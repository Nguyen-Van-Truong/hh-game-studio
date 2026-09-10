param([Parameter(Mandatory=$true)][string]$AttemptDir)
$ErrorActionPreference='Stop'
$c=Get-Content -Raw -LiteralPath (Join-Path $AttemptDir 'config.json') | ConvertFrom-Json
$native=$null; $code=$null; $failure=$null; $timedOut=$false
try {
    if (Test-Path -LiteralPath (Join-Path $AttemptDir 'native.json')) { throw 'Attempt already launched; use a fresh directory/session.' }
    $exe=Join-Path $env:USERPROFILE '.grok/bin/grok.exe'
    $argsG=@('--cwd',('"'+$c.workspace+'"'),'--model','grok-4.6','--reasoning-effort','xhigh','--session-id',$c.session,'--prompt-file',('"'+(Join-Path $AttemptDir 'TASK.txt')+'"'),'--output-format','streaming-json','--no-subagents','--no-plan','--max-turns',[string]$c.turn_limit,'--always-approve')
    if (!$c.web_search) { $argsG += '--disable-web-search' }
    $native=Start-Process -FilePath $exe -ArgumentList $argsG -WorkingDirectory $c.workspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $AttemptDir 'events.jsonl') -RedirectStandardError (Join-Path $AttemptDir 'stderr.txt') -PassThru
    $null=$native.Handle
    @{job_id=$c.id;attempt=$c.attempt;session=$c.session;pid=$native.Id;started_utc=$native.StartTime.ToUniversalTime().ToString('o');executable=$exe;requested_model='grok-4.6';requested_effort='xhigh';fast_flag='NOT_EXPOSED_BY_CLI';max_seconds=$c.max_seconds} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $AttemptDir 'native.json') -Encoding utf8
    if (!$native.WaitForExit([int]$c.max_seconds*1000)) {
        $timedOut=$true
        # This process handle owns the exact child, not a process found by name.
        $native.Kill()
        if (!$native.WaitForExit(10000)) { throw 'Owned CLI child did not exit after timeout termination.' }
    }
    $native.WaitForExit(); $code=$native.ExitCode
} catch { $failure=$_.Exception.Message }
finally {
    @{job_id=$c.id;attempt=$c.attempt;session=$c.session;exit_code=$code;timed_out=$timedOut;launcher_error=$failure;finished_utc=[datetime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $AttemptDir 'runner-meta.json') -Encoding utf8
    if ($null -ne $code) { [IO.File]::WriteAllText((Join-Path $AttemptDir 'exit.txt'),[string]$code) }
    if ($c.notify) { try {
        $claim=[IO.File]::Open((Join-Path $AttemptDir 'notification.claim'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None); $claim.Dispose()
        . (Join-Path $c.notification_repo 'scripts/worker-mailbox/lib/WorkerMailbox.Core.ps1')
        . (Join-Path $c.notification_repo 'scripts/worker-mailbox/lib/WorkerMailbox.Notify.ps1')
        $kind='WORKER_INCOMPLETE'
        if (!$timedOut -and $null -eq $failure -and (Test-Path -LiteralPath (Join-Path $c.workspace 'REPORT.md')) -and (Test-Path -LiteralPath (Join-Path $c.workspace 'evidence.json'))) { $kind='NEEDS_REVIEW' }
        Send-MailboxNotification -Title ($c.id+' - '+$kind) -Body ('CLI ended; exit='+$code+'. Coordinator must verify files/tests. Evidence: '+$AttemptDir) -Mode real -EventKind $kind -EvidencePath (Join-Path $AttemptDir 'notice-evidence.json') | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $AttemptDir 'notice-result.json') -Encoding utf8
    } catch { $_.Exception.Message | Set-Content -LiteralPath (Join-Path $AttemptDir 'notice-error.txt') -Encoding utf8 } }
}
if ($null -ne $code) { exit $code } else { exit 99 }
