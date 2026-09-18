$ErrorActionPreference = 'Stop'
# Metadata-only readiness collection. Does not execute Java, adb, SDK tools,
# Godot, an emulator, tests, installers, or any device command.
$reviewRoot = $PSScriptRoot
$scopeRoot = [IO.Path]::GetFullPath((Join-Path $reviewRoot '../../..'))
$observationStart = Get-Date -Format o

function Safe-Path([string] $Path) {
    if ([string]::IsNullOrEmpty($Path)) { return $null }
    $normalizedPath = $Path.Replace('\', '/')
    $aliases = [ordered]@{
        '%LOCALAPPDATA%' = $env:LOCALAPPDATA
        '%APPDATA%' = $env:APPDATA
        '%ProgramFiles(x86)%' = ${env:ProgramFiles(x86)}
        '%ProgramFiles%' = $env:ProgramFiles
        '%USERPROFILE%' = $env:USERPROFILE
        '<scope>' = $scopeRoot
    }
    foreach ($alias in $aliases.Keys) {
        $prefix = $aliases[$alias].Replace('\', '/')
        if ($prefix -and $normalizedPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return $alias + $normalizedPath.Substring($prefix.Length)
        }
    }
    return $normalizedPath
}

$environmentRows = @(
    foreach ($name in 'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'JAVA_HOME') {
        foreach ($level in 'Process', 'User', 'Machine') {
            $value = [Environment]::GetEnvironmentVariable($name, $level)
            [pscustomobject]@{ name=$name; scope=$level; is_set=(-not [string]::IsNullOrEmpty($value)); path=(Safe-Path $value) }
        }
    }
)
$commandRows = @(
    foreach ($name in 'adb.exe', 'sdkmanager.bat', 'java.exe', 'javac.exe') {
        $match = Get-Command -Name $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        $version = if ($match) { (Get-Item -LiteralPath $match.Source).VersionInfo.FileVersion } else { $null }
        [pscustomobject]@{ name=$name; resolves_on_path=($null -ne $match); source=(Safe-Path $match.Source); file_version=$version; executed=$false }
    }
)
$candidatePaths = @(
    "$env:LOCALAPPDATA/Android/Sdk", "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe",
    "$env:ProgramFiles/Android", "${env:ProgramFiles(x86)}/Android",
    'C:/Android/Sdk', 'C:/Android/android-sdk', 'C:/Android/platform-tools',
    "$env:ProgramFiles/Android/Android Studio/jbr", "$env:LOCALAPPDATA/Programs/Android Studio/jbr",
    "$env:APPDATA/Godot/export_templates/4.7.2.stable"
)
foreach ($row in $environmentRows) {
    if ($row.is_set) {
        $value = [Environment]::GetEnvironmentVariable($row.name, $row.scope)
        $candidatePaths += $value
    }
}
$pathRows = @($candidatePaths | Select-Object -Unique | ForEach-Object {
    [pscustomobject]@{ path=(Safe-Path $_); exists=(Test-Path -LiteralPath $_) }
})
$jdkRows = @(
    foreach ($jdkRoot in @("$env:ProgramFiles/Java", "${env:ProgramFiles(x86)}/Java", "$env:ProgramFiles/Eclipse Adoptium", "$env:USERPROFILE/.jdks", "$env:ProgramFiles/Microsoft")) {
        if (-not (Test-Path -LiteralPath $jdkRoot -PathType Container)) { continue }
        foreach ($entry in @(Get-ChildItem -LiteralPath $jdkRoot -Directory | Where-Object { $jdkRoot -notlike '*/Microsoft' -or $_.Name -like 'jdk*' })) {
            $releasePath = Join-Path $entry.FullName 'release'
            $release = @{}
            if (Test-Path -LiteralPath $releasePath -PathType Leaf) {
                foreach ($line in (Get-Content -LiteralPath $releasePath | Where-Object { $_ -match '^(IMPLEMENTOR|JAVA_VERSION|JAVA_RUNTIME_VERSION|OS_ARCH|OS_NAME)=' })) {
                    $parts = $line.Split('=', 2)
                    $release[$parts[0]] = $parts[1].Trim('"')
                }
            }
            [pscustomobject]@{
                path=(Safe-Path $entry.FullName)
                java_file_present=(Test-Path -LiteralPath (Join-Path $entry.FullName 'bin/java.exe') -PathType Leaf)
                javac_file_present=(Test-Path -LiteralPath (Join-Path $entry.FullName 'bin/javac.exe') -PathType Leaf)
                release_metadata=$release
                executed=$false
            }
        }
    }
)
$settingsRows = @()
$settingsPath = "$env:APPDATA/Godot/editor_settings-4.7.tres"
if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
    $settingsRows = @(Get-Content -LiteralPath $settingsPath | Where-Object { $_ -match '^export/android/(android_sdk_path|java_sdk_path)\s*=' } | ForEach-Object {
        $parts = $_.Split('=', 2)
        $settingValue = $parts[1].Trim().Trim('"').Replace('\\', '\')
        [pscustomobject]@{ key=$parts[0].Trim(); value=(Safe-Path $settingValue); configured_path_exists=($settingValue -ne '' -and (Test-Path -LiteralPath $settingValue)) }
    })
}
$toolingRows = @(Get-ChildItem -LiteralPath (Join-Path $scopeRoot 'studio/.local/tooling') | ForEach-Object {
    [pscustomobject]@{ name=$_.Name; is_directory=$_.PSIsContainer; length_bytes=$(if ($_.PSIsContainer) {$null} else {$_.Length}) }
})
$archivePath = Join-Path $scopeRoot 'studio/.local/tooling/Godot_v4.7.2-stable_export_templates.tpz'
$archiveInfo = Get-Item -LiteralPath $archivePath
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    $archiveEntries = @($archive.Entries | Where-Object { $_.FullName -match '(^|/)(android_debug\.apk|android_release\.apk|android_source\.zip|version\.txt)$' } | ForEach-Object {
        [pscustomobject]@{ member=$_.FullName; uncompressed_bytes=$_.Length; compressed_bytes=$_.CompressedLength }
    })
    $reader = [IO.StreamReader]::new($archive.GetEntry('templates/version.txt').Open())
    try { $templateVersion = $reader.ReadToEnd().Trim() } finally { $reader.Dispose() }
} finally { $archive.Dispose() }
$deviceFilter = "Present=TRUE AND (PNPClass='WPD' OR Name LIKE '%Android%' OR Name LIKE '%ADB%' OR Name LIKE '%MTP%' OR Name LIKE '%Samsung%' OR Name LIKE '%Xiaomi%' OR Name LIKE '%Pixel%' OR Name LIKE '%Huawei%' OR Name LIKE '%OnePlus%' OR Name LIKE '%OPPO%' OR Name LIKE '%Vivo%')"
$devices = @(Get-CimInstance Win32_PnPEntity -Filter $deviceFilter | Select-Object Name,PNPClass,Status,Manufacturer,ConfigManagerErrorCode)
$smallInputs = @(
    'AGENTS.md', 'zdoc/8-9-godot-blender-agent-studio-plan.txt',
    'studio/toolchain.lock.json', 'studio/.local/toolchain.local.json',
    'zdoc/reviews/20260918-gt06-s71-next/android-readiness.md'
)
$inputRows = @($smallInputs | ForEach-Object {
    $inputPath = Join-Path $scopeRoot $_
    $inputFile = Get-Item -LiteralPath $inputPath
    if ($inputFile.Length -gt 1MB) { throw 'Refusing large-input hashing during active diagnostic.' }
    [pscustomobject]@{ path=$_; bytes=$inputFile.Length; sha256=(Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$lock = Get-Content -LiteralPath (Join-Path $scopeRoot 'studio/toolchain.lock.json') -Raw | ConvertFrom-Json
$localConfig = Get-Content -LiteralPath (Join-Path $scopeRoot 'studio/.local/toolchain.local.json') -Raw | ConvertFrom-Json
$result = [ordered]@{
    schema='S83_ANDROID_BOUNDED_READINESS_1'
    authority=0
    observation_start=$observationStart
    observation_end=(Get-Date -Format o)
    git_head=(& git -C $scopeRoot rev-parse HEAD).Trim()
    current_gate='GT-06'
    future_gate='GT-08_PLANNED_NOT_OPENED'
    android_lock_state=$lock.android.state
    android_versions_pinned=$false
    local_override_keys=@($localConfig.PSObject.Properties.Name)
    environment=$environmentRows
    path_resolution=$commandRows
    bounded_candidate_paths=$pathRows
    jdk_candidates=$jdkRows
    godot_android_settings=$settingsRows
    local_tooling_immediate_entries=$toolingRows
    export_template_archive=@{ path=(Safe-Path $archivePath); bytes=$archiveInfo.Length; payload_hash_recomputed=$false; version_member=$templateVersion; selected_members=$archiveEntries }
    pnp_filter=$deviceFilter
    matching_present_pnp_count=$devices.Count
    matching_present_pnp_descriptions=$devices
    device_authorization='UNVERIFIED_NO_ADB_COMMAND'
    device_runtime_gpu='UNVERIFIED'
    small_input_hashes=$inputRows
    scope_limits=@('No recursive disk crawl', 'No tool/version process launches', 'No device identifiers or content', 'No installs/downloads/SDK manager/ADB daemon/emulator', 'No large binary hashes', 'No runtime/plan edits or gate verdict')
}
$outputPath = Join-Path $reviewRoot 'observations.json'
[IO.File]::WriteAllText($outputPath, ($result | ConvertTo-Json -Depth 12) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Output "Recorded bounded metadata in $outputPath"
