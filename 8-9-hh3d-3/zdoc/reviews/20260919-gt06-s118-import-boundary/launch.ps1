$ErrorActionPreference = 'Stop'
$s118Launch = Join-Path $PSScriptRoot 'launch-01'
if (Test-Path -LiteralPath $s118Launch) { throw 'S118_LAUNCH_ALREADY_EXISTS' }
[void][System.IO.Directory]::CreateDirectory($s118Launch)
$s118Python = (Get-Command python -ErrorAction Stop).Source
$s118Helper = Join-Path $PSScriptRoot 'import_verbose.py'
$s118Process = $null
function Write-S118Exclusive($Name, $Value) {
    $s118Bytes = [System.Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 10) + "`n")
    $s118Stream = [System.IO.File]::Open((Join-Path $s118Launch $Name), [System.IO.FileMode]::CreateNew)
    try { $s118Stream.Write($s118Bytes, 0, $s118Bytes.Length); $s118Stream.Flush($true) }
    finally { $s118Stream.Dispose() }
}
try {
    $s118Process = Start-Process -FilePath $s118Python -ArgumentList @('-B', ('"' + $s118Helper + '"'), '--launch') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $s118Launch 'supervisor-stdout.txt') -RedirectStandardError (Join-Path $s118Launch 'supervisor-stderr.txt')
    Write-S118Exclusive 'supervisor-start.json' ([ordered]@{pid=$s118Process.Id; executable=$s118Python; process_start_utc=$s118Process.StartTime.ToUniversalTime().ToString('o'); observed_utc=[DateTime]::UtcNow.ToString('o'); helper=$s118Helper; formal_acceptance=$false})
    $s118Process.WaitForExit()
    Write-S118Exclusive 'supervisor-exit.json' ([ordered]@{pid=$s118Process.Id; exit_code=$s118Process.ExitCode; observed_utc=[DateTime]::UtcNow.ToString('o'); actual_process_wait=$true; formal_acceptance=$false})
    exit $s118Process.ExitCode
}
finally { if ($null -ne $s118Process) { $s118Process.Dispose() } }
