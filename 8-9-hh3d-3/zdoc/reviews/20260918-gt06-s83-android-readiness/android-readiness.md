# S83 Android readiness — bounded preparation only

AUTHORITY=0. Observed **2026-09-18 16:49:56–16:49:58 +07:00**, Asia/Saigon. HEAD: `c1726579759bd1d13799cb2365bf75079b03c3a7`. The scoped tracked tree was clean at 16:48. The current tools plan is S83, `CURRENT_VALID_WP=GT-06`; **GT-08 remains PLANNED and unopened** behind GT-07. This refreshes the S71 inventory without changing its conclusion: Android SDK/tool readiness and an authorized physical device remain **UNVERIFIED**. Existing JDK and template files are present.

This lane wrote only this review directory. No engine/test, Java/tool version command, installer, SDK manager, ADB client/server, emulator, download, device control, process control, large binary hash, commit, plan edit, or runtime edit was performed. The coordinator owns the active GT-06 diagnostic; this report does not assert a fresh diagnostic status or a gate verdict.

## Exact observations

The machine-readable [observations](observations.json) retain the named candidate paths, safe metadata, observation times, and small input hashes. Paths use environment aliases; no serial, PnP instance ID, debugging key, device content, full environment, or process command line was collected.

| Area | Present/configured metadata | Evidence limit |
|---|---|---|
| Reviewed Android pin | `studio/toolchain.lock.json` still contains only `android.state=GAP_UNTIL_GT08`. Local override keys are `schema`, `godot_console`, `export_templates`. | No Android SDK/platform-tools/build-tools/JDK/ABI recipe is pinned. The existing Godot pin is 4.7.2-stable. |
| SDK and platform-tools | `%LOCALAPPDATA%/Android/Sdk` and its `platform-tools/adb.exe` are absent. Also absent: `%ProgramFiles%/Android`, `%ProgramFiles(x86)%/Android`, `C:/Android/{Sdk,android-sdk,platform-tools}`. Immediate `studio/.local/tooling` entries contain no Android SDK directory. | A nonstandard SDK location remains unverified. This bounded search does **not** establish whole-machine absence. |
| PATH/environment | `adb.exe` and `sdkmanager.bat` do not resolve on PATH. `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `JAVA_HOME` are unset at Process/User/Machine levels. | PATH absence is not tool absence. No executable/tool version was verified. |
| JDK candidates | Both `java.exe` and `javac.exe` files exist in all five candidates below. PATH resolves the Oracle `javapath` entries; their file metadata says 25.0.1.0. | File/release metadata only; no candidate was executed or tested with Godot/Gradle. No candidate is an approved Android JDK pin. |
| Godot settings | The Java SDK setting is empty. The Android SDK setting resolves to absent `%LOCALAPPDATA%/Android/Sdk`. Standard Android Studio JBR paths under `%ProgramFiles%/Android/Android Studio/jbr` and `%LOCALAPPDATA%/Programs/Android Studio/jbr` are absent. | No editor/settings mutation or launch occurred. |
| Export templates | `studio/.local/tooling/Godot_v4.7.2-stable_export_templates.tpz` is present, 1,281,349,702 bytes. ZIP central-directory entries include `android_debug.apk` (127,260,725 bytes), `android_release.apk` (104,803,333), and `android_source.zip` (214,418,211). The 13-byte version member reads `4.7.2.stable`. | Archive members were not extracted/executed. Large payload hash was not recomputed. Lock records earlier archive verification; this observation does not renew it. `%APPDATA%/Godot/export_templates/4.7.2.stable` is absent. |
| Physical device | The read-only present-PnP filter returned **0 rows** for WPD or Android/ADB/MTP/Samsung/Xiaomi/Pixel/Huawei/OnePlus/OPPO/Vivo names. | The filter cannot exclude generic, driverless, disconnected, or wireless devices. Physical availability, model/SKU/OS, authorization, install/launch, ABI/page size and GPU behavior remain unverified. |

JDK `release` metadata observed:

| Directory | Declared runtime | Implementor |
|---|---|---|
| `%ProgramFiles%/Java/jdk-25` | 25.0.1+8-LTS-27 | Oracle |
| `%USERPROFILE%/.jdks/corretto-21.0.9` | 21.0.9+10-LTS | Amazon |
| `%USERPROFILE%/.jdks/corretto-23.0.2` | 23.0.2+7-FR | Amazon |
| `%USERPROFILE%/.jdks/ms-21.0.8` | 21.0.8+9-LTS | Microsoft |
| `%USERPROFILE%/.jdks/valhalla-ea-23-valhalla+1-90` | 23-valhalla+1-90 | Oracle |

All five declare Windows/x86_64. No JDK 17 was found in the bounded roots; that does not establish absence elsewhere or prove existing higher JDKs unsuitable.

## Requirements to resolve when GT-08 opens

S83 plan lines 774–788 and 895–903 require the clean target matrix, reviewed recipe/artifact hashes/exits/limits, Android ABI/native-library 4 KB/16 KB proof, and fixture install/launch on at least one supported **physical** Android with SKU/OS. Emulator evidence can support ABI/page-size checks but cannot substitute for runtime/GPU acceptance. Missing device evidence keeps GT-08/09/10 and the HH World handoff closed; no desktop-only acceptance is implied.

The official Godot **stable** Android-export page, checked on 2026-09-18, recommends JDK 17 while supporting higher JDKs. It lists platform-tools 35.0.0+, build-tools 35.0.1, platform 35, command-line tools, CMake 3.10.2.4988404 and NDK 28.1.13356709. This moving documentation is **research input, not a reviewed recipe for the pinned 4.7.2 artifact**. At GT-08, resolve exact versions against that pin, record package provenance/hashes and validate the selected JDK; do not copy the documentation's `latest` selector into this plan's reproducible pin or auto-install now. [Godot Android export requirements](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_android.html).

Native-library alignment and actual runtime page-size behavior need separate proof; merely having the template APK archive is insufficient. The Android guide describes APK/native-library alignment and testing in a verified 16 KB environment. No ABI/alignment inspection or environment launch was performed here. [Android page-size compatibility](https://developer.android.com/guide/practices/page-sizes).

The later agent-owned work is to resolve an existing/nonstandard SDK first, prepare the reviewed scoped toolchain and any required OEM driver, verify executable versions/template integrity, build the fixture, then collect supported device/runtime/GPU/ABI evidence. S83 uses local test signing for this scope; no production signing credential or purchase is currently established as a prerequisite.

## Minimum conditional owner action

No owner action is needed to continue GT-06. **Only if an authorized physical Android is still unavailable when the GT-08 device lane is ready:** make an existing phone available with a data-capable USB cable; unlock it; enable Developer options → USB debugging; and acknowledge this workstation's RSA authorization prompt when the agent begins the reviewed setup. Unlocking and acknowledgment require the person holding the phone. If an existing device or nonstandard SDK is already available, identify that setup first; this inventory does not justify buying a replacement. Windows may need the applicable OEM ADB driver, which remains agent preparation. [Android hardware setup and RSA authorization](https://developer.android.com/studio/run/device).

ADB authorization was not queried because starting an ADB client can start its server when none exists, violating this lane's no-daemon constraint. Device authorization must be checked at the later allowed lane. [Official ADB client/server behavior](https://developer.android.com/tools/adb#howadbworks).

## Reproduction and evidence anchors

Run the scoped collector from `8-9-hh3d-3` only when an equivalent bounded metadata refresh is useful:

```powershell
& 'zdoc/reviews/20260918-gt06-s83-android-readiness/collect-readonly.ps1'
```

The final collector returned actual host exit **0** in 1.88 seconds; this is the inventory command's exit, **not** tool/device/test acceptance. The earlier collector pass only corrected decoding of escaped backslashes in the read-only Godot settings value; it did not change machine settings. The final [collector](collect-readonly.ps1) and [observations](observations.json) are retained together. No broad or performance tests were run for this documentation-only lane.

Small SHA-256 input anchors:

- Scope `AGENTS.md`: `c93a79b7833f8a02246d0373545f05efc680fc299e2090002b756ae9b0e6d49f`.
- S83 tools plan: `d5015d75ebe4ca90eab7ca478df3fe4e010cdfc29c67f80bf16a5ce7d27aa0f4`.
- Toolchain lock: `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`.
- Local override: `6a053047b6c1388dd05c5ef6fab8ee4c90f448cb93c7dba36439f39283a7e420` (values not copied).
- S71 readiness report: `7c618e64093cc9a664a6db8586fceb57e1b22259768f24e844f0e71d651146ba`.

Result: **PREPARATION_RECORDED; SDK/JDK execution and physical-device readiness UNVERIFIED; GT-08 UNOPENED; no acceptance verdict.**
