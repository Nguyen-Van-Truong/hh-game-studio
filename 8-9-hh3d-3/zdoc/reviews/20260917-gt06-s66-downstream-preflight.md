# GT06 S66 downstream Android / Linux / CI preflight

STATUS=READ_ONLY_PREFLIGHT
GT08_ACCEPTANCE=NOT_ASSESSED
PHYSICAL_ANDROID=UNVERIFIED_NO_ADB_IN_SCOPED_DISCOVERY

Observed 2026-09-17, approximately 13:55–13:58 UTC (20:55–20:58 Asia/Saigon).
Repository HEAD observed: `3186d40055eb91d3899d6724e94479cf6c5d2fda`.
This identifies the checkout during inspection; it is not a freeze assertion for
the coordinator's continuing GT06 worktree.

Only this report was written. No engine, container, emulator, APK or device
session was launched; no install, pull, device authorization, configuration
change or Git mutation was performed. All subprocess probes had a 12-second
timeout. No device serial was obtained or retained. Environment locations below
use standard variable placeholders rather than a personal home-directory path.

## Plan requirements checked

Authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`, current header
`CURRENT_VALID_WP=GT-06`; GT07 and GT08 remain PLANNED. This inspection does not
open either work package.

- `ANDROID_POLICY` and GT08 require Android target conformance and at least one
  supported physical device, with SKU/OS recorded. Emulator evidence cannot
  replace physical runtime/GPU evidence.
- GT08 requires clean Windows/Android exports and Linux headless fixture launch
  using pinned templates, trusted source closure and hash-keyed cache. Missing
  blobs/dependencies, wrong templates, cache poison and unsupported addons must
  fail. Android native-library ABI and 4 KB / 16 KB compatibility are explicit.
- TQ08-B and TX16-C require build/artifact hashes, actual exits/limits and local
  fixture signer/verifier tests. GT08 requires two critics. A missing physical
  device blocks GT08/09/10 acceptance and the HH World handoff.
- Portability policy records actual host/tool identity and keeps headless/windowed
  evidence separate. Missing SDK/accelerator is an environment gap, not PASS.

## Android / Java observations

Scoped discovery inspected PATH commands, `ANDROID_HOME`, `ANDROID_SDK_ROOT`,
`JAVA_HOME`, standard SDK/application locations and `studio/.local`. It did not
search unrelated projects or every disk directory.

| Read-only check | Observed result |
|---|---|
| `Get-Command adb` | Not found on PATH |
| `Get-Command sdkmanager` | Not found on PATH |
| `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `JAVA_HOME` | All unset |
| `%LOCALAPPDATA%/Android/Sdk` | Absent |
| `%ProgramFiles%/Android` | Absent |
| Exact filename search under `studio/.local`: `adb.exe`, `sdkmanager.bat`, `source.properties` | No matches |
| `Get-Process -Name adb` | Zero matching processes |
| `java -version`, exit 0 | Java 25.0.1, build `25.0.1+8-LTS-27`, 64-bit |
| `javac -version`, exit 0 | `javac 25.0.1` |
| `studio/toolchain.lock.json` Android entry | `{"state":"GAP_UNTIL_GT08"}` |

Java resolves through `%ProgramFiles%/Common Files/Oracle/Java/javapath`.
Its presence is not proof of Android build compatibility or a reviewed JDK pin.
The Android lock contains no SDK/platform-tools/build-tools/target API/NDK/JDK
version matrix or supported-device record.

No `adb devices` command was run because no adb executable was found in the
scoped locations. Therefore authorized physical-device attachment, SKU/OS,
ABIs and page size remain **unverified**. This is not a claim that no device is
physically connected or that no SDK exists elsewhere.

## Export-template availability

The existing archive was read and hashed, without extraction or installation:

```text
studio/.local/tooling/Godot_v4.7.2-stable_export_templates.tpz
size_bytes=1281349702
sha256=f298490b8d44d934be425a5a65a51bf15f422428b229a06a6e11d9ffea248011
templates/version.txt=4.7.2.stable
```

Both size and SHA256 match `studio/toolchain.lock.json`. ZIP directory/readback
contains `templates/android_debug.apk`, `android_release.apk`,
`android_source.zip`, `linux_debug.x86_64`, `linux_release.x86_64`,
`windows_debug_x86_64.exe` and `windows_release_x86_64.exe`.

The lock says `ARCHIVE_VERIFIED_NOT_INSTALLED`; the local override points to the
archive. `%APPDATA%/Godot/export_templates/4.7.2.stable` is absent. No Android
APK build, archive native-library inspection, signing, export or installation
was performed. Archive presence does not establish target-conformance results.

## Linux runtime and helper availability

These commands inspected already available services/images; none created or
started a container or engine. Each command below returned exit 0.

```text
wsl --list --verbose
NAME              STATE           VERSION
* docker-desktop  Running         2

wsl --version
WSL version: 2.6.1.0
Kernel version: 6.6.87.2-1
WSLg version: 1.0.66
Windows version: 10.0.26200.8875

docker version --format <client|server|server-os|server-arch>
29.2.1|29.2.1|linux|amd64

docker context inspect desktop-linux --format <name|docker-endpoint>
desktop-linux|npipe:////./pipe/dockerDesktopLinuxEngine

docker --context desktop-linux info --format <cpus|memory-bytes|os|arch>
12|16728133632|linux|x86_64
```

The pinned image is locally present according to `docker image inspect`:

```text
Id=sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970
Os=linux
Architecture=amd64
RepoDigest=python@sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970
```

The ID, repository digest, context and endpoint match
`studio/godot-addon/validator-toolchain.lock.json`.

| Local file | Bytes | Observed SHA256 |
|---|---:|---|
| `.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64` | 146414384 | `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e` |
| `.local/tooling/Godot_v4.7.2-stable_linux.x86_64.zip` | 77860424 | `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4` |

Both hashes match the Linux validator lock for Godot 4.7.2-stable, source commit
`ed1daf0bf001b61586d9930840f2f1394092c079`.

Existing reusable infrastructure was inspected, not executed:

- `studio/build/bootstrap/`: archive verification, toolchain install helper,
  bounded owned-process fixture runner and lifecycle probe.
- `studio/godot-addon/linux_executor.py` and `LINUX_EXECUTOR.md`: closed internal
  Linux parse/import/profile-validation runner using the pinned local image,
  resource limits and owned cleanup. The lock/README explicitly label this
  diagnostic/internal infrastructure; it is not a GT08 CI/export acceptance.
- `studio/tests/godot/run_linux_probe.py`, `linux_probe_fixtures.py`,
  `test_linux_executor.py`, `test_linux_profile.py` and related evidence tests.
- `studio/tests/ci/` and `8-9-hh3d-3/.github/workflows/` are absent. This does not
  assess unrelated repository workflows or external CI credentials/services.

Selected source hashes observed:

```text
studio/toolchain.lock.json
28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9
studio/godot-addon/validator-toolchain.lock.json
1441452e54279d94fe4a3bd946f2f494426179301bfe3202ae103b5fb469374d
studio/build/bootstrap/run_fixture.py
ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328
studio/godot-addon/linux_executor.py
6516bfb996d540532111160ac729f016247211a8f2de4129a6cac359228779e4
studio/tests/godot/run_linux_probe.py
6157098f9dab723cb830312be41e93839d1df901e0bb23d04fa031477ecd2354
```

The bootstrap runner hash also matches the Linux validator lock. No fresh Linux
launch, supervisor/Yama readback, target export, signing, cache-poison test or
CI execution was attempted during this preflight.

## Downstream gaps and preparation boundary

1. **Android toolchain gap:** identify or provision a reviewed SDK/adb/JDK/build
   profile when GT08 is authorized, with exact hashes/versions and isolated
   locations. Do not substitute the currently observed Java version as a pin.
2. **Physical-device hard gate unverified:** arrange an authorized supported
   physical Android device, then record redacted/hash-bound identity, SKU/OS,
   ABI/page-size facts and actual install/launch/runtime/GPU evidence. Device
   authorization and any install remain future work.
3. **Template integration pending:** verified archive bytes are available, but
   an isolated reviewed install/export profile and target runs remain required.
4. **CI matrix not established:** reusable bootstrap/Linux infrastructure and
   the pinned local image are present; GT08 clean-checkout/cache/target recipes,
   local signer/verifier negatives, artifact collection and two-critic closure
   remain separate work after GT07.

No GT08 feature, benchmark, device compatibility, game readiness or acceptance
claim is made by this report. These environment gaps do not block the ongoing
desktop GT06 implementation, and they do not waive later physical-device gates.
