# S69 campaign01 — bounded forensic review

Reviewed on 2026-09-18, Asia/Saigon. This report records surviving evidence and gaps; it is not a GT-06 acceptance verdict. No engines, tests, benchmark modules, or capture verifiers were run. Only this report was written. Official Godot source was read remotely without saving it into the workspace.

**Result: one complete persisted joint sample, which is warm-up batch 0; zero measured samples; zero complete runs out of the required ten.** Batch 1 contains a complete host command batch but an incomplete native batch. Neither process disappearance nor tool-session 88287 establishes a captured exit or cleanup. The stored native stderr also contains a startup error that independently prevents a clean completed run.

Evidence root: `8-9-hh3d-3/studio/.local/reviews/gt06-s69-campaign-01`; attempt-relative paths below refer to its only attempt, `run-00-attempt-01`. Campaign ID is `gt06-s69-campaign-01`; run ID is `gt06-s69-campaign-01.r00.a01`. The campaign declares `formal_acceptance=false`, ten runs and 35 batches per run.

## Durable progress

| Evidence | Completed work retained | Limit |
|---|---|---|
| `command-00.json` | 1,000 commands: 500 inspect, 300 rejected, 200 admitted; 700 COMMITTED / 300 REJECTED; effects 0→200; separate cancellation CANCELED; zero dropped commands | Host component of warm-up batch 0 |
| `project/benchmark/out/batch-00.json` | 100 native cycles and 100 timing rows | Warm-up batch 0 only |
| `joint-00.json`, `batch-capture-00.json`, `sample-preview-00.json` | One persisted joint sample, index 0, `warmup=true`; native cycles match the preview | No full run, final assembly or dataset |
| `command-01.json` | Another 1,000 commands with the same mix/terminal counts; effects 200→400; cancellation CANCELED; zero dropped commands | No matching complete native batch or joint sample |
| Batch 1 READY/START and heartbeat stream | Native work entered batch 1 and reached cycle index 33 / UNDO | Progress markers do not establish a complete cycle record or the required 100-cycle batch |

Batch 0 host duration is 36.219205 seconds, native duration 50.575452 seconds, and joint window 86.979308 seconds. Batch 1 host duration is 43.583097 seconds. These are diagnostic observations, not a campaign performance result. The batch 0 joint maximum heartbeat gap is 606.926 ms. There is no warm-up index 4 baseline from which to determine sustained memory growth.

All six artifact references in `batch-capture-00.json` match their bytes, size and SHA256. The READY→START→command and native→ACK bindings match; native START/ACK receipts match the stdout markers. Independently recomputed sample evidence SHA256 is `878348626f6967e5b7acc216be8ef286a4dc140121db9850dcb615405621f871`, equal to the persisted sample binding. This preserves a useful reproducible partial diagnostic; it does not supply missing lifecycle evidence.

The editor stdout contains 342 lines: 333 HEARTBEAT, two READY, two START, one BATCH and one ACK markers, with no COMPLETE or FAILED marker. Its final line is:

```text
HH_GT06_BENCHMARK_HEARTBEAT {"batch":1,"cycle":33,"main_thread":true,"monotonic_us":180223598,"phase":"UNDO","pid":51916,"run_id":"gt06-s69-campaign-01.r00.a01"}
```

Editor stdout last-write time is `2026-09-17T17:55:15.725045Z` (00:55:15 local). Host stdout ends at line 184 with batch 1 / `native_cycles`, last-write `2026-09-17T17:55:14.982184Z`. Batch 1 START was observed at native monotonic 136965092 μs, so the last heartbeat is 43.258506 seconds later. The raw tail supplies neither a native deadline failure nor a 7,410-second owner timeout. The precise stop time, reason, relationship to the chat turn transition, and process exit codes remain unknown.

## Process lifecycle gaps

Host `process-start.json` records PID 38944; command records bind it to `windows:134341411289143447`. Editor start records PID 51916; joint/native records bind it to `windows:134341411354692408`. Both owner directories contain invocation/start/stdout/stderr but **no `process-exit.json` or `capture.json`**.

The attempt also lacks `child-result.json`, `child-failure.json`, `parent-failure.json`, `cleanup.json`, `assembly-manifest.json`, `assembled-run.json`, `run-capture.json` and `stop-request.json`. The native output directory lacks `batch-01.json`, `index.json` and `failure.json`; batch 1 ACK/joint/preview are absent. Campaign-level `campaign-capture.json`, `dataset.json` and `summary.json` are absent.

A read-only process inventory at `2026-09-18T01:05:02.896+07:00` found no matching campaign Godot/Python processes. This does **not** establish natural exits, retained-handle cleanup, closed owner Jobs, or an observed zero active count for these owners. Tool session 88287 has no authenticated lifecycle result in the inspected package. No exit or cleanup record may be reconstructed from absence alone.

The import is separately complete: PID 47580 has a persisted actual exit code 0. Its capture reports wrapper exit 0, natural tree exit, configured/assigned/closed Job, zero observed, active count 0, no retained handle, no taint, no uncertain create/close and no failed operations. Referenced import logs/start/exit files match their capture hashes; import stderr is empty. These import-specific records remain useful evidence about that import only.

The frozen campaign runner requires each unsuccessful previous attempt to have a parent failure record with `owner_closed=true` and `owned_tree_zero=true` before starting another attempt (frozen `tests/replay/run_benchmark_campaign.py:403–408`). Those records are missing here. Do not manufacture them to resume this attempt. A fresh process cannot continue the old run's state or memory baseline; no partial batch/run should be spliced into a new completed benchmark.

## Source and artifact binding

Initial review HEAD was `e469f58dd2487d103a3e91ed77d7f4bba01f4f7a`. The 46-file map is equal in campaign metadata, attempt context and source manifest. Recomputing the sorted `path + NUL + sha256 + newline` closure gives:

`15945096c0ef3fc42f17f121842060a70ea530ec1cbacd2cba21566d0f3e37eb`

All 46 files match both persisted source copies (`campaign/source/studio` and `attempt/source/studio`). At the initial read all also matched live source. At an intermediate check the coordinator's in-progress change to live `tests/replay/run_benchmark_campaign.py` was the sole live mismatch; the coordinator subsequently also edited the owner implementation. This forensic report therefore binds to the frozen copies, not the changing workspace. Fourteen immutable editor-snapshot files also match the project copy; mutable `scenes/fixture.tscn` was not treated as an immutable source file.

Profile bytes, context and campaign all bind SHA256 `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. The toolchain lock SHA256 is `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`.

| Frozen source | SHA256 |
|---|---|
| `tests/replay/run_benchmark_campaign.py` | `c31bf9a5cc4373a3195c6128e5c86854f1cd12c94ed41159b207843c405ce435` |
| `tests/replay/benchmark_assembly.py` | `16ba15ea1961d78c89d5ea2b8c389e89b960a4df25e6a2783e4cc8a6d0c1111a` |
| `tests/replay/benchmark_commands.py` | `522e91341eda6175704b692cd9bc5454951f93a891657e815a9a2111cd3eb438` |
| `tests/replay/benchmark_job.py` | `9326ac8c76e28125297cfded54fdaccc237bebd9f417db2002d1a2b0f61df339` |
| `tests/replay/benchmark_native.gd` | `da0bb949ebaf3bc3881a1e9ad325d98ac6496fc3a0454b825a28655fdbc37515` |
| `tests/replay/benchmark_profile.py` | `ddbd98583060f791226fca83e275cf01204b37112627383198dcef4ec6f6f233` |

| Artifact | SHA256 |
|---|---|
| Campaign `campaign.json` | `b65ff937eb24fefd1df4a0ac0782b4efcad611f06d5e2b8421a4efa755e5ee63` |
| `context.json` | `dbf23b34640c9ee616a8074e2b6f6638fdf154e619d2011fc74e758f91d36f16` |
| `source-files.json` | `78d4c3fc893aebf90a13fd8ddd5522e02204ace3c6a845788d9c4f8d10df92a5` |
| `command-00.json` | `ad8c9e48bf9f16749dfe76f91a443f328a0f0d22dbe473ad050bac13e1964991` |
| `command-01.json` | `dbb1b5daeb8dd14967d816011be136182b9b232cedbc9b02ff37fa1db8302487` |
| `project/benchmark/out/batch-00.json` | `3e2e9798f8ab60c3e3782f8cebaadc4fcb2b17112dc497b5c4cd83595924a7ca` |
| `batch-capture-00.json` | `76fcf0fb46e1cf1d6873a60a850d237119eafe0e2bd96e7db2a3d7cbab506afe` |
| `sample-preview-00.json` | `7f2ef435801afc770c7bc051135e23ace6b716e653183b427ad0e321ed674556` |
| `host-owner/stdout.txt` | `ad35eb229e448c1767fc73cc55b2444d08ad110a5d0e3627437acf224300017d` |
| `editor-host/stdout.txt` | `7ca6bc278d248044bd6f649861d693b332ec586944d75abc64c7845970866c4c` |
| `editor-host/stderr.txt` | `507cf9c19cb4186c6d27a3f12c04c448b3f1f8004626a77b57dd71e561db4ba0` |

## Startup error and official renderer-source check

Both this S69 attempt and `gt06-s68-campaign-03/run-00-attempt-01` contain exactly the same 268-byte editor stderr (SHA256 above): Godot reports failure to create its own executable with argument `--test-rd-creation`, at `platform/windows/os_windows.cpp:1495`. Both editor stdout banners already identify OpenGL 3.3 / Compatibility on the GTX 1660 Ti. Both import stderr files are empty. S69 host stderr is empty; the earlier campaign03 has its separate host traceback from the controlled stop. This scopes the repeated startup error to the windowed editor evidence; it is not unique to S69 or the final/new-turn event.

In S69 the error file was written at `2026-09-17T17:52:17.222478Z`, before the first READY, and native work continued afterwards. Therefore it does not by itself explain the later abrupt tail. It does independently violate the frozen runner's `CAMPAIGN_NATIVE_STDERR` check (line 656) and assembly's `NATIVE_LOG` check (`benchmark_assembly.py:662`). The frozen polling loop checked stdout only at lines 101–104, allowing this stderr error to remain unnoticed until finalization. No full PASS was demonstrated for either campaign.

**Explicit `--rendering-method gl_compatibility --rendering-driver opengl3` is not a source-supported way to suppress this probe.** Those are supported renderer-selection options, but the pinned engine performs a separate editor capability check. [Official command-line documentation](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html).

At the engine's pinned commit `ed1daf0bf001b61586d9930840f2f1394092c079`, `LightmapGIEditorPlugin` calls `can_create_rendering_device()` in its constructor under `MODULE_LIGHTMAPPER_RD_ENABLED`, without a renderer-option guard. This happens during editor tool initialization, so the observed flag is not evidence of an early fallback before project renderer selection. [Official lightmap editor source, lines 189–201](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/scene/3d/lightmap_gi_editor_plugin.cpp#L189-L201).

The display-server method returns early for headless mode, an existing RenderingDevice, or a cached result. Otherwise its Windows branch invokes a subprocess with only `--test-rd-creation`; explicit OpenGL selection is not an exclusion. Its purpose is checking simultaneous OpenGL/RenderingDevice support without risking the editor process. This directly explains why a Compatibility editor can request the child. [Official display-server source, lines 2174–2205](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/servers/display/display_server.cpp#L2174-L2205).

The child's flag handler tests OpenGL plus RenderingDevice and exits. [Official main source, lines 2208–2217](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/main.cpp#L2208-L2217). The reported Windows error is emitted when `CreateProcessW` returns zero; this log does not include the Windows error code. It therefore proves child creation failure, not the reason. The four-process implementation limit is a causal hypothesis until a bounded owner diagnostic captures a result; renderer flags do not suppress the probe. [Official Windows execution source, lines 1489–1495](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/windows/os_windows.cpp#L1489-L1495).

Preserve the old raw package and frozen source for diagnosis. Import evidence, command receipts and the one bound warm-up sample remain reusable for investigation of that exact attempt. Missing run completion/exit/cleanup, the stderr error and the absent measured samples prevent using this partial package as a completed benchmark or acceptance result.

## Follow-up: bounded assessment of the proposed parent Job composition

The coordinator clarified that four processes is an implementation default, not a hard plan acceptance requirement. The proposed parent-only composition is reasonable for a fresh native diagnostic: retain the editor Job's four-process cap, and allow six in the outer campaign Job (two host processes plus the four nested editor slots). Preserve the 7,410-second wall, 7,200-second CPU and 2 GiB aggregate memory limits. No suspended-process launcher is required to make this correction.

Static topology explains the budget: outer helper + campaign Python already consume two slots; inner helper + Godot consume two more; Godot's RD probe becomes the fifth outer process and third inner process. Windows associates a new descendant with all Jobs in its parent's chain, and parent accounting includes nested processes. The old outer cap of four cannot admit that five-process tree, though the captured error alone lacks the Windows error code needed to prove it caused this particular failure. [Microsoft nested Job documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs), [active-process limit semantics](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).

The read-only inspection of the coordinator's in-progress patch found explicit host-role selection at the outer creation and verification callsites, an exact role-dependent invocation profile, and verification of queried active-process limits. The editor retains its default role/cap. Existing `ui_host.py:64–71` waits on the private stdin gate before launching the target; `benchmark_job.py` assigns/configures the Job before releasing that gate. Replacing this mechanism with a new suspended-launch implementation would introduce additional lifecycle work without addressing a separate demonstrated blocker.

The coordinator-owned diagnostic should exercise the full outer-helper → host → inner-helper → editor → RD-child hierarchy. A standalone editor probe would miss the former outer cap. Required diagnostic observations are empty editor stderr, real target/helper exit records, closed/zero owners and released handles for both levels, plus exact profile/limits/source binding in fresh artifacts. This assessment authorizes no acceptance claim and this reviewer launched no diagnostic.
