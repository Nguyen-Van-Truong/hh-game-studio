$ErrorActionPreference = 'Stop'
$s117Launch = Join-Path $PSScriptRoot 'launch-01'
if (Test-Path -LiteralPath $s117Launch) { throw 'S117_LAUNCH_ALREADY_EXISTS' }
[void][System.IO.Directory]::CreateDirectory($s117Launch)
$s117Python = (Get-Command python -ErrorAction Stop).Source
$s117Helper = Join-Path $PSScriptRoot 'lookup_boundary.py'
$s117Process = $null
function Write-S117Exclusive($Name, $Value) {
    $s117Bytes = [System.Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 10) + "`n")
    $s117Stream = [System.IO.File]::Open((Join-Path $s117Launch $Name), [System.IO.FileMode]::CreateNew)
    try { $s117Stream.Write($s117Bytes, 0, $s117Bytes.Length); $s117Stream.Flush($true) }
    finally { $s117Stream.Dispose() }
}
try {
    $s117Process = Start-Process -FilePath $s117Python -ArgumentList @('-B', ('"' + $s117Helper + '"'), '--launch') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $s117Launch 'supervisor-stdout.txt') -RedirectStandardError (Join-Path $s117Launch 'supervisor-stderr.txt')
    Write-S117Exclusive 'supervisor-start.json' ([ordered]@{pid=$s117Process.Id; executable=$s117Python; process_start_utc=$s117Process.StartTime.ToUniversalTime().ToString('o'); observed_utc=[DateTime]::UtcNow.ToString('o'); helper=$s117Helper; formal_acceptance=$false})
    $s117Process.WaitForExit()
    Write-S117Exclusive 'supervisor-exit.json' ([ordered]@{pid=$s117Process.Id; exit_code=$s117Process.ExitCode; observed_utc=[DateTime]::UtcNow.ToString('o'); actual_process_wait=$true; formal_acceptance=$false})
    exit $s117Process.ExitCode
}
finally { if ($null -ne $s117Process) { $s117Process.Dispose() } }
