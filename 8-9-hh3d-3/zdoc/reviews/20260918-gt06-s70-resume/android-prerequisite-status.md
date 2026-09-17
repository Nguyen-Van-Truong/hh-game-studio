# Android prerequisite status — bounded read-only preflight

Observed 2026-09-18, approximately 01:30–01:33 Asia/Saigon.

**PHYSICAL_ANDROID=UNVERIFIED; AUTHORIZED_ADB_DEVICE=UNVERIFIED.** No authorized physical-device or install/launch/runtime evidence was located in the inspected GT08 preflight references. This does not establish that the user lacks a phone, that no phone is connected, or that no SDK exists elsewhere. It is not a current GT06 blocker and does not open GT08.

The authoritative tools plan, GT08 lines 894–908, requires at least one supported physical Android device with SKU/OS and actual fixture install/launch evidence. Lines 225–226 and 1273 expressly retain UNVERIFIED when SDK/device authorization has not been established. The S66 downstream preflight and S70 critical-path notes use that same distinction.

| Inspected evidence / read-only check | Result and limit |
|---|---|
| S66 downstream Android preflight | Recorded no scoped adb discovery and no device session; physical attachment/authorization remained unverified. |
| `studio/toolchain.lock.json` | Android entry remains `{"state":"GAP_UNTIL_GT08"}`; no reviewed Android SDK/JDK/ABI/device matrix. |
| `studio/.local/toolchain.local.json` | Contains Godot console and export-template paths; no Android SDK/adb override. |
| Immediate `studio/.local/tooling` entries | Godot/Blender tools, archives and GT05 directory; no Android SDK/platform-tools directory identified. Existing export-template archive is preparation, not device evidence. |
| `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `JAVA_HOME` | Unset in this process. |
| `%LOCALAPPDATA%/Android/Sdk`, `%ProgramFiles%/Android` | Both absent at the exact standard locations checked. |
| Read-only command resolution for `adb.exe`, `sdkmanager.bat` | No PATH match. This result alone is not proof of tool/device absence. |
| One filtered Windows present-device inventory | No rows for present WPD-class devices or names containing Android/ADB. This does not detect every generic USB, driverless or wireless phone and says nothing definitive about adb authorization. No serial/instance ID was collected. |
| Immediate local review-root names | No Android/adb/GT08-named root found; inspected preflight references contain no later authorized-device capture. No unrelated project or disk scan was performed. |

The inventory used a read-only `Win32_PnPEntity` query restricted to `Present=TRUE` and the WPD/Android/ADB filter, returning only descriptive fields. No adb client/server, engine, emulator, APK, test or device workload was started. No process/device settings, SDK installation or downloads were changed. Only this report was written. In particular, `adb devices` was not used: an adb client can start its server when none exists. [Official adb documentation](https://developer.android.com/tools/adb).

If a physical device is genuinely unavailable when the GT08 device lane is due, the minimum conditional user action is: **make one authorized Android phone available, connect it to this workstation with a data-capable USB cable, unlock it, enable Developer options → USB debugging, and approve this computer's RSA authorization prompt when the coordinator uses the reviewed adb setup.** The prompt requires device-side acknowledgement; SDK/toolchain preparation and evidence collection remain agent work. If the user already has such a device connected or a nonstandard SDK path, first identify that existing setup rather than infer a need to acquire another phone. [Official hardware-device setup](https://developer.android.com/studio/run/device), [USB debugging and RSA authorization](https://developer.android.com/tools/adb#Enabling).

No immediate user intervention is justified for ongoing GT06 by these observations. Before a later GT08 acceptance claim, resolve the unknown with authorized adb evidence and the required actual physical install/launch/runtime/GPU results; emulator or template availability does not replace that gate.

Reviewed byte anchors:

- `zdoc/reviews/20260917-gt06-s66-downstream-preflight.md`: `a7f78af37495c5f3601314087360fa00b898a32aba7156620f19ed4ae0843c53`.
- `studio/toolchain.lock.json`: `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`.
- `studio/.local/toolchain.local.json`: `6a053047b6c1388dd05c5ef6fab8ee4c90f448cb93c7dba36439f39283a7e420`.
