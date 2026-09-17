# Android readiness — S71 bounded read-only inventory

Observed **2026-09-18 03:40–03:42 +07:00 (Asia/Saigon)**. Baseline HEAD: `29c75c092496d13d29e50cee67b43264b5b62ee8`. Scoped tracked tree was clean; pre-existing untracked review artifacts were left alone. This report is the only write in this lane; no staging, commit, plan edit, gate opening, or acceptance verdict.

**Physical Android and authorized ADB access remain UNVERIFIED.** Local Java installations and the pinned Godot 4.7.2 template archive are present. An approved Android SDK/JDK/ABI recipe is not yet recorded. These are later GT-08 prerequisites, not a reason to interrupt the current GT-06 benchmark.

The S71 tools plan retains `CURRENT_VALID_WP=GT-06`; GT-08 depends on GT-07. Lines 938–952 require actual fixture install/launch on at least one supported physical Android with SKU/OS, plus runtime/GPU and ABI/page-size evidence. Emulator proof does not replace the physical gate. GT-10 lines 973–992 require GT-08/09 acceptance and the complete Windows/Android/Linux-headless target package; local test signing is sufficient for this fixture scope. No production credentials or purchase are presently identified as prerequisites.

| Item | Observed result | What remains unproven |
|---|---|---|
| Toolchain lock / local override | `studio/toolchain.lock.json` has Android `GAP_UNTIL_GT08`; `studio/.local/toolchain.local.json` has Godot and template archive paths only. | Reviewed Android SDK/build-tools/JDK/ABI versions and reproducible build recipe. |
| Export templates | `studio/.local/tooling/Godot_v4.7.2-stable_export_templates.tpz` exists, **1,281,349,702 bytes**. Read-only ZIP directory contains `templates/android_debug.apk` (127,260,725 bytes), `android_release.apk` (104,803,333), `android_source.zip` (214,418,211); tiny `version.txt` reads `4.7.2.stable`. | Archive payload checksum was **not rerun** during benchmark; lock records prior verification. No export or APK execution here. `%APPDATA%/Godot/export_templates/4.7.2.stable` is absent; no global template installation is claimed. |
| Java/JDK | `java.exe` and `javac.exe` resolve to `%ProgramFiles%/Common Files/Oracle/Java/javapath`; file version 25.0.1.0. Java/Javac files and `release` metadata exist for `%ProgramFiles%/Java/jdk-25` (25.0.1), and `%USERPROFILE%/.jdks/{corretto-21.0.9,corretto-23.0.2,ms-21.0.8,valhalla-ea-23-valhalla+1-90}`. | These are installed candidates, **not an approved Android JDK pin**. No Java process or compatibility test was started. Do not infer JDK absence from unset `JAVA_HOME`, or assume the PATH JDK is suitable. |
| Environment | `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `JAVA_HOME` unset at process, user and machine levels. `adb.exe` and `sdkmanager.bat` have no PATH resolution. | Absence on PATH is not global tool absence. |
| Bounded SDK locations | Absent: `%LOCALAPPDATA%/Android/Sdk` (including `platform-tools/adb.exe`), `%ProgramFiles%/Android`, `%ProgramFiles(x86)%/Android`, `C:/Android/{Sdk,android-sdk,platform-tools}`. Immediate `studio/.local/tooling` entries contain no Android SDK/platform-tools directory. | SDK installed at another nonstandard location remains UNVERIFIED; no disk/user-folder scan was done. |
| Godot Android settings | Only the two Android path keys were read from `%APPDATA%/Godot/editor_settings-4.7.tres`: Java SDK path empty; Android SDK path points to the absent `%LOCALAPPDATA%/Android/Sdk`. Standard Android Studio JBR paths under `%ProgramFiles%/Android/Android Studio/jbr` and `%LOCALAPPDATA%/Programs/Android Studio/jbr` are absent. | Existing editor configuration does not establish a working SDK. No settings were changed. |
| Existing processes/network | Zero `adb.exe`, `java.exe`, `javaw.exe`, `emulator.exe` processes; zero listeners on TCP 5037. Existing GT-06 Godot PID 11064 was observed and left untouched. | No ADB authorization state was queried; nondefault server/remote setups remain unverified. |
| Windows present-device inventory | Zero rows for WPD class or names matching Android/ADB/MTP/Samsung/Xiaomi/Pixel/Huawei/OnePlus/OPPO/Vivo. Only descriptive fields were selected. | This filter cannot exclude a generic/driverless/wireless phone. Device presence, authorization, model/OS support, install/launch and GPU behavior remain UNVERIFIED. No serial, instance ID, phone content, or debugging key was read. |

**Minimal conditional owner action later:** if no authorized physical Android is accessible when GT-08 reaches its device lane, make one phone available for the fixture test, connect it with a data-capable USB cable, unlock it, enable Developer options → USB debugging, then approve this workstation's RSA prompt when the agent initiates the reviewed ADB setup. Device-side unlocking and acknowledgement require the person holding the phone. If a phone or nonstandard SDK is already available, identify that existing setup first; this inventory does not justify buying another device. [Android hardware setup](https://developer.android.com/studio/run/device), [USB debugging and RSA authorization](https://developer.android.com/tools/adb#Enabling).

SDK/JDK selection and scoped preparation, any applicable driver diagnosis, template verification, recipe/ABI checks, and fixture evidence remain agent work at the appropriate gate. No immediate owner action is required to keep GT-06 running. No `adb devices` command was used because an ADB client can start its server if none exists. [Official ADB client/server behavior](https://developer.android.com/tools/adb#howadbworks).

## Reproduce the bounded checks

Run PowerShell from the repository root. These checks read metadata only; they do not invoke Java/ADB/Godot, extract archives, or change devices/settings. Restrict results to the named fields; do not collect process command lines, device identifiers or unrelated configuration.

```powershell
$scopeRoot = '8-9-hh3d-3'
Get-Date -Format o
git rev-parse HEAD
git status --short --untracked-files=no -- $scopeRoot
Get-Content -LiteralPath "$scopeRoot/studio/toolchain.lock.json"
(Get-Content -LiteralPath "$scopeRoot/studio/.local/toolchain.local.json" -Raw |
  ConvertFrom-Json).PSObject.Properties.Name
Get-ChildItem -LiteralPath "$scopeRoot/studio/.local/tooling" |
  Select-Object Name,Mode,Length
foreach ($name in 'ANDROID_HOME','ANDROID_SDK_ROOT','JAVA_HOME') {
  foreach ($scope in 'Process','User','Machine') {
    [pscustomobject]@{Name=$name;Scope=$scope;Value=[Environment]::GetEnvironmentVariable($name,$scope)}
  }
}
Get-Command adb.exe,sdkmanager.bat,java.exe,javac.exe -ErrorAction SilentlyContinue |
  Select-Object Name,Source
$sdkCandidates = @(
  "$env:LOCALAPPDATA/Android/Sdk", "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe",
  "$env:ProgramFiles/Android", "${env:ProgramFiles(x86)}/Android",
  'C:/Android/Sdk', 'C:/Android/android-sdk', 'C:/Android/platform-tools',
  "$env:ProgramFiles/Android/Android Studio/jbr", "$env:LOCALAPPDATA/Programs/Android Studio/jbr",
  "$env:APPDATA/Godot/export_templates/4.7.2.stable"
)
$sdkCandidates | ForEach-Object { [pscustomobject]@{Path=$_;Exists=(Test-Path -LiteralPath $_)} }
foreach ($jdkRoot in @("$env:ProgramFiles/Java", "${env:ProgramFiles(x86)}/Java",
    "$env:ProgramFiles/Eclipse Adoptium", "$env:USERPROFILE/.jdks", "$env:ProgramFiles/Microsoft")) {
  if (Test-Path -LiteralPath $jdkRoot) {
    Get-ChildItem -LiteralPath $jdkRoot -Directory |
      Where-Object { $jdkRoot -notlike '*/Microsoft' -or $_.Name -like 'jdk*' } |
      ForEach-Object {
        [pscustomobject]@{Path=$_.FullName;Java=(Test-Path -LiteralPath "$($_.FullName)/bin/java.exe");Javac=(Test-Path -LiteralPath "$($_.FullName)/bin/javac.exe")}
        if (Test-Path -LiteralPath "$($_.FullName)/release") {
          Select-String -LiteralPath "$($_.FullName)/release" -Pattern '^(IMPLEMENTOR|JAVA_VERSION|JAVA_RUNTIME_VERSION|OS_ARCH|OS_NAME)='
        }
      }
  }
}
Select-String -LiteralPath "$env:APPDATA/Godot/editor_settings-4.7.tres" `
  -Pattern '^export/android/(android_sdk_path|java_sdk_path)\s*='
@(Get-CimInstance Win32_Process -Filter "Name = 'adb.exe' OR Name = 'java.exe' OR Name = 'javaw.exe' OR Name = 'emulator.exe'" |
  Select-Object Name,ProcessId,ParentProcessId,ExecutablePath)
@(Get-NetTCPConnection -State Listen -LocalPort 5037 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,OwningProcess)
@(Get-CimInstance Win32_PnPEntity -Filter 'Present=TRUE' |
  Where-Object { $_.PNPClass -eq 'WPD' -or $_.Name -match 'Android|ADB|MTP|Samsung|Xiaomi|Pixel|Huawei|OnePlus|OPPO|Vivo' } |
  Select-Object Name,PNPClass,Status,Manufacturer,ConfigManagerErrorCode)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archivePath = (Resolve-Path -LiteralPath "$scopeRoot/studio/.local/tooling/Godot_v4.7.2-stable_export_templates.tpz").Path
$archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
  $archive.Entries | Where-Object { $_.FullName -match '(^|/)(android_debug\.apk|android_release\.apk|android_source\.zip|version\.txt)$' } |
    Select-Object FullName,Length,CompressedLength
  $reader = [IO.StreamReader]::new($archive.GetEntry('templates/version.txt').Open())
  try { $reader.ReadToEnd() } finally { $reader.Dispose() }
} finally { $archive.Dispose() }
```

Small input SHA-256 anchors (no large binary hashing during GT-06):

- `AGENTS.md`: `c93a79b7833f8a02246d0373545f05efc680fc299e2090002b756ae9b0e6d49f`.
- `zdoc/8-9-godot-blender-agent-studio-plan.txt` (S71): `1f3ca50b8a0931a12f8c334ea2e6cf969d8d667d8af659ac22fa523996390963`.
- `studio/toolchain.lock.json`: `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`.
- `studio/.local/toolchain.local.json`: `6a053047b6c1388dd05c5ef6fab8ee4c90f448cb93c7dba36439f39283a7e420`.
- `zdoc/reviews/20260918-gt06-s70-resume/android-prerequisite-status.md`: `c91c07c587a63d754aeb7cdbeba6650de44439c63285bad99250fb7090c43175`.
