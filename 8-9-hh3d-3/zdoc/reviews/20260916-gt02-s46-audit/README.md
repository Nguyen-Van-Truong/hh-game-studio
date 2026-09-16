# S46 registered managed fixture candidate

Coordinator closeout: **GT-02 ACCEPTED** on 2026-09-16 after two independent
PASS/TICK=yes reviews of this exact closure. `acceptance.json` binds their
reports/evidence and the pre-acceptance Git HEAD proof. The original candidate
and coordinator verification keep their historical NOT_REVIEWED/non-vote fields.

Frozen source: `f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf`,
106 files. Candidate `GT02-S46-20260916-01` has 417 protocol tests: **413 passed,
4 documented skips**, plus bootstrap **56/56**. All actual target/wrapper exits
are zero, owned trees are empty and source/snapshot hashes stayed unchanged.
Python, Node and Godot agree on 2396 canonical rows each.

This package adds public discovery/inspection, a typed client and bounded
service lifecycle around the existing protected active-release consumer and
durable restart custody. It registers only an exact live ManagedFixtureOwner.
The fixed fixture scope is `fixture.active-release`; it never advertises
arbitrary filesystem paths, raw eval, an engine consumer or generic safe_write.

## Requirement → test → evidence

| Requirement | Executable coverage | Evidence |
| --- | --- | --- |
| Closed typed request/discovery, canonical JSON and limits | `test_core`, `test_limits`, `test_golden_vectors`, `test_domain_contract`; 2396 rows per consumer | S46-01 protocol logs and golden artifacts |
| Public registration binds actual protected file/custody; availability is truthful | `test_selector_public` discovery/readonly/pending/poison/closed binding regressions; actual readback | S46-01 plus native/run-01 create and replace_stop |
| Client negotiates exact schema/scope and binds responses | `test_selector_client`: malformed schema/scope/command ID, bounded snapshot, inert asset graph | S46-01 and selector-client/run-04 |
| Typed client works through actual service and pipe I/O | Native endpoint pair, bootstrap, two active-file replacements, lookup, exact retry, Stop; only peer identity check substituted | `test_real_native_service_bootstrap_two_replacements_retry_and_stop` in S46-01; peer boundary separately below |
| Safe Windows create/atomic replace and namespace isolation | `test_safe_create`, `test_safe_replace`, `test_file_consumer`; actual FileID/hash/barrier checks | boundary/run-01: 20 replacements, 306 denied adversary operations with scratch positive control |
| AppContainer actual token/PID/session, no credential argv/environment | Real compiled worker uses prebound work/control; service handles dispatch and pumping | native/run-01: 3 child exits86, seven denied-right rows per child, no raw bearer in artifacts |
| Durable Registry custody and event high-water | `test_custody_registry`, `test_private_events`, `test_managed_fixture`; actual subprocess crash exits81/87/91 | S46-01; registry-native/run-01: 36 denied operations, 12 updates, same-prefix positive control |
| Stop/Cancel latch before waiting on storage, reject revoked auth | `test_selector_public` held selector mutex; `test_selector_pipe` phase regressions | S46-01; native managed drop_reply uses healthy control lookup/Stop |
| Response loss does not cause duplicate effects | client/service response-loss tests; dedupe and lease/revision checks | Native create/replace exact receipt retry; drop_reply returns UNKNOWN then control Stop |
| Service deadlines independent of blocked pump | blocked phase + independent watchdog and post-read budget regression | `test_managed_service` in S46-01; pre-fix counterexample retained below |
| Retain ownership until joins/native closes complete | startup failure, slow pump, actual endpoint close refusal, separate control | `test_managed_service`, `test_selector_client`; native final threads/endpoints/IO/events/Job PIDs all zero |
| Evidence is bound to exact source, not adjacent run | Recomputed106-file map/digest; all candidate/native artifacts; 12 invalid native bindings rejected | `verify_evidence.py`, `test_native_binding.py`, their JSON results; Git byte proof |

## Native runs on this closure

- `20260916-gt02-s46-native/run-01`: create generation1, close/reopen by
  storage ID then replace generation2, exact retries, Stop; separate work-reply
  loss with control lookup/inspection/Stop. All three actual child exits86,
  owned Job PIDs0; service threads/endpoint/pipe/event owners0. Every child
  demonstrates a package-granted Registry query/set/query control while
  protected access is denied. Three owned test leaves, profile, temp and
  runtime snapshot are removed. No launcher dispatch/advance shortcuts.
- `20260916-gt02-s46-boundary/run-01`: actual AppContainer adversary runs
  concurrently with 20 native replacements; 306 denied attempts and zero
  unexpected errors; outside alias absent; child67/Job0, outerexit0/tree0.
- `20260916-gt02-s46-registry-native/run-01`: 36 denied operations and 12
  broker updates, granted control read/write, protected-state readback;
  child89/Job0, outerexit0/tree0. Two owned leaves removed.

Boundary and Registry helpers are exact copies of previously reviewed probes.
Their `S44`/`S45` marker names identify the probe grammar; the runtime manifests
are S46's exact106-file closure. The verifier checks both maps and outcomes.
Only the managed C fixture dynamically speaks the public route; its bounded
diagnostic JSON extraction is not a production parser. The Python typed client
is exercised separately, including native pipe/service integration.

## Failures and limitations retained

The independent implementation cross-review reproduced a lease admitted50ms
after a700ms service deadline while the pump was blocked (event sequence4→5).
Its report/evidence remain under `20260916-gt02-s46-service-design-review.md`
and `20260916-gt02-s46-service-review-evidence/run-01`. Pre-fix source bytes
are preserved in `20260916-gt02-s46-service/deadline-before`. The frozen
candidate adds an independent deadline watcher plus a check after frame read
and before dispatch. Four service threads share one join budget; native calls
still require the enclosing owned Job's deadline. This failure is not erased
or relabeled PASS by the subsequent regression.

Earlier public attempt-01 used the legacy frame helper's route allowlist,
which does not contain Inspect; the corrected public tests encode the exact
documented frame. Native prototype-01 stopped on a legitimate transitional
UNKNOWN/SELECTED lookup; later probes continue bounded lookup only, without
resubmitting the command. All failed/superseded artifacts remain hash-bound
in `diagnostic-manifest.json`. The file-name-only source paths in the historical
boundary probe are resolved through an explicit five-name allowlist in this
verifier, not guessed from a matching digest.

The four skips are three unavailable symlink creation privileges and the
non-Windows negative-capability test; native Windows junction coverage runs.
No required CAS/golden test was skipped. Generic safe-open mutation remains
unsupported. Unknown pending, stopped and verified-empty restart roots remain
held for explicit reconciliation; GT-07 extends recovery. Native owner reopen
occurs in the same broker process; the full suite separately proves an actual
process exit87 and registry-only restart. No power-loss claim is made.

These checks establish candidate integrity, not acceptance. Only two fresh
independent critics on this exact closure can unlock GT-02; old S44 failures,
S46 implementation feedback and coordinator verification are not those votes.

## Reproduce

From the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s46-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s46-audit/test_native_binding.py
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s46-audit/verify_git_bytes.py HEAD
```

New full/native runs require fresh output names and unchanged frozen source;
never rerun into or overwrite these evidence directories. The authoritative
progress state remains the tools plan, not this report.
