$ErrorActionPreference = 'Stop'
$s115Launch = Join-Path $PSScriptRoot 'launch-01'
if (Test-Path -LiteralPath $s115Launch) { throw 'S115_LAUNCH_ALREADY_EXISTS' }
[void][System.IO.Directory]::CreateDirectory($s115Launch)
$s115Python = (Get-Command python -ErrorAction Stop).Source
$s115Helper = Join-Path $PSScriptRoot 'coupled_journal.py'
$s115Process = $null
function Write-S115Exclusive($Name, $Value) {
    $s115Bytes = [System.Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 10) + "`n")
    $s115Stream = [System.IO.File]::Open((Join-Path $s115Launch $Name), [System.IO.FileMode]::CreateNew)
    try { $s115Stream.Write($s115Bytes, 0, $s115Bytes.Length); $s115Stream.Flush($true) }
    finally { $s115Stream.Dispose() }
}
try {
    $s115Process = Start-Process -FilePath $s115Python -ArgumentList @('-B', ('"' + $s115Helper + '"'), '--launch') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $s115Launch 'supervisor-stdout.txt') -RedirectStandardError (Join-Path $s115Launch 'supervisor-stderr.txt')
    Write-S115Exclusive 'supervisor-start.json' ([ordered]@{pid=$s115Process.Id; executable=$s115Python; process_start_utc=$s115Process.StartTime.ToUniversalTime().ToString('o'); observed_utc=[DateTime]::UtcNow.ToString('o'); helper=$s115Helper; formal_acceptance=$false})
    $s115Process.WaitForExit()
    Write-S115Exclusive 'supervisor-exit.json' ([ordered]@{pid=$s115Process.Id; exit_code=$s115Process.ExitCode; observed_utc=[DateTime]::UtcNow.ToString('o'); actual_process_wait=$true; formal_acceptance=$false})
    exit $s115Process.ExitCode
}
finally { if ($null -ne $s115Process) { $s115Process.Dispose() } }
