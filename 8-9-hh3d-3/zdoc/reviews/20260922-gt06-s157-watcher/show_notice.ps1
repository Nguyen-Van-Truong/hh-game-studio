param([Parameter(Mandatory=$true)][string]$Notice)
$ErrorActionPreference='Stop'
$noticeData=Get-Content -LiteralPath $Notice -Raw -Encoding utf8 | ConvertFrom-Json
$delivery=@{utc=[DateTime]::UtcNow.ToString('o');notice=$Notice;seen='UNKNOWN';sound='UNKNOWN';popup='UNKNOWN'}
try {
    Add-Type -AssemblyName System
    [System.Media.SystemSounds]::Asterisk.Play()
    $delivery.sound='REQUESTED_NOT_CONFIRMED_HEARD'
    $shell=New-Object -ComObject WScript.Shell
    $popupResult=$shell.Popup([string]$noticeData.message,20,[string]$noticeData.title,0x1040)
    $delivery.popup_return=$popupResult
    $delivery.popup=if($popupResult -eq -1){'TIMED_OUT_SEEN_UNKNOWN'}else{'DISMISSED'}
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
} catch {
    $delivery.error=$_.Exception.Message
} finally {
    $delivery | ConvertTo-Json | Set-Content -LiteralPath ($Notice+'.delivery.json') -Encoding utf8
}
