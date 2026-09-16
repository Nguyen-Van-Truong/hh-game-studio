# S44 coordinator checkpoint — candidate, not acceptance

Frozen candidate: `../20260916-gt02-s44-02/`.
Source closure: `6730c6f54cd682920b7585d139835088ae60f893f68fff8cd24662e268716964`.
90 source files, 9 candidate artifacts. Protocol 326 run, 322 pass, 4 documented
skips; bootstrap 56/56. Python, Node and Godot each agree on 2396 canonical rows.
Native IPC `../20260916-gt02-s44-native/run-02/` and native adversary
`../20260916-gt02-s44-boundary/run-06/` have identical complete source maps.

The fixed file consumer now performs real protected `active.json` replacement.
Seven authenticated native IPC cases start from an existing committed file;
commit/lost reply replace it, auth/lease/cancel/early Stop preserve it, and
selected Stop explicitly restores the baseline release with generation 3.
The separate AppContainer adversary makes 288 denied attempts during 20 real
replacements, with positive scratch controls. Actual child exits are 61/67;
native Jobs and outer owned process trees drain to zero.

Compilation has its own bounded Job. The compiler root exits normally before
remaining **owned compiler helpers** are terminated and drained. This cleanup
is explicitly recorded, and is not presented as native test-child normal exit.

Run from repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s44-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s44-audit/test_native_binding.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s44-audit/verify_git_bytes.py HEAD
```

The first verifier checks current source and exact captured bytes; after later
source changes reproduce it from this checkpoint checkout. The second rejects
eight stale/missing/changed native digest or map variants. Git verification
checks the complete source and captured evidence bytes in the index/commit.
`diagnostic-manifest.json` also retains superseded/failed trials and imported
native helper source; it is an integrity inventory, not a PASS label for every run.

## Requirement coverage and remaining work

| Contract | Tests / evidence | Scope and limit |
| --- | --- | --- |
| §2.2/TQ02 typed JSON/JCS/limits | core, domain, limits, integration, golden suites; candidate golden records | 2396 serializer rows; raw Godot wire parser is separate |
| TX01/11 retry, CAS, retention | journal/CAS/platform/retention/durability and transport recovery suites | 8-process bounded test; no fabricated skip-to-pass |
| TX03/15 paths and handle identity | safe_open/create/replace suites; native boundary run-06 | Protected owner-only NTFS namespace; shared arbitrary writable folders unsupported |
| TX15 authenticated dispatch | transport, endpoint, selector_pipe; native run-02 | Actual AppContainer PID/token-bound work and control pipes |
| TX14 Stop, cancel, response loss | selector/transport tests and native 7 modes | No automatic resume after Stop; late outcome stays UNKNOWN |
| File effect before COMMITTED | file_consumer suite 9 tests; native run-02 | Actual file readback, namespace barrier and terminal journal barrier |
| Crash and reopen baseline | safe_replace 5 real process cuts; file_consumer 3 second-revision cuts | Process termination on this host, not power-loss proof; no blind rewrite |
| Native ownership | private_store/create/replace/pipe tests and owned runner captures | Includes real unclosed token/handle retention; no broad process kills |
| TX17 inert hostile input/redaction | security_vectors/redaction/transport suites | No engine script import sandbox yet; engine-specific checks belong to adapters |
| Public safe-write availability | **OPEN** | Internal file consumer is not yet registered as a supported public operation |
| Recovered mutation admission/custody | **OPEN** | Read-only reopen cannot regain mutation; trusted witnesses still need durable supervisor custody |
| Two independent reviews | Separate `../20260916-gt02-s44-critic-{a,b}.md` | Coordinator verification does not supply independent signatures |

## Failed trials and lessons retained

- S44-01 is superseded by S44-02 after the actual selector crash regression and
  source documentation changes. Its matching native runs are historical only.
- Boundary run-01/02 lacked a clean outer tree because MSVC retained helper
  processes; run-03 child-process restriction prevented compiler startup.
  Subsequent runs use explicitly owned compiler-helper cleanup.
- Consumer-01 setup shared a parent with pinned journal/blob ancestors, blocking
  namespace flush. Use a dedicated file parent and register cleanup immediately
  when each resource is obtained. Consumer-03 test expected stale `game-0` after
  baseline commit; consumer-04 corrected the test to the actual revision.
- The optional command to remove eight TEMP directories left by consumer-01
  was rejected by the tool's automatic policy. They were preserved; no alternate
  deletion path was attempted. Current successful runs clean their own resources.
- A verifier initially assumed drop-reply performs the same native retry as
  submit. It actually confirms via authenticated lookup after `PIPE_IO_FAILED`;
  verification now checks that recorded behavior explicitly.

GT-02 remains CANDIDATE. Public capability is false; production custody,
recovered mutation and independent acceptance remain open. No GT-03 or later
gate is accepted by this package, and no total-plan completion date is inferred.
