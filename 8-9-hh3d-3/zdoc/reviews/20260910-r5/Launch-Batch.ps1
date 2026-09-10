param([string]$BatchFile=(Join-Path $PSScriptRoot 'active-batch.local.json'))
$ErrorActionPreference='Stop'
$batch=Get-Content -Raw -LiteralPath $BatchFile | ConvertFrom-Json
foreach ($job in $batch.jobs) {
    if ($null -ne $job.supervisor_pid) { throw ('Already dispatched: '+$job.role) }
    $script=Join-Path $job.attempt_dir 'Run-Worker.ps1'
    $argv=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$script+'"'),'-AttemptDir',('"'+$job.attempt_dir+'"'))
    $process=Start-Process -FilePath powershell.exe -ArgumentList $argv -WindowStyle Hidden -RedirectStandardOutput (Join-Path $job.attempt_dir 'supervisor.stdout.txt') -RedirectStandardError (Join-Path $job.attempt_dir 'supervisor.stderr.txt') -PassThru
    $job.supervisor_pid=$process.Id
    $batch | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $BatchFile -Encoding utf8
    Write-Output ($job.role+': supervisor PID '+$process.Id)
    Start-Sleep -Seconds 5
}
$batch | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $batch.batch_root 'batch.json') -Encoding utf8
