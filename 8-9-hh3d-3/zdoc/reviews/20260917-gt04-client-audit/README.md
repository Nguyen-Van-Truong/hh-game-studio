# GT04 authenticated read-client component audit

AUTHORITY=0. FORMAL_ACCEPTANCE=0. This is a bounded file-only component audit,
not either final GT04 acceptance critic and not a public write/recovery grant.

Package `20260917-gt04-client-04` verifies at complete frozen source closure
`bf2236b0229100062ec266b55722db7196fc0af84716bf6e29e01bd7595ef15f`.
The 112-file snapshot matches every declared byte hash and the live source at
audit time. Runtime source-map digest is
`sha256:19be3e24778feb87fa0ebcd7bfabb92a8df0bfc434a5087b305484a11d2fa287`.

The verifier independently checks the raw **233-test** inventory, each raw
unittest result, one completion marker, zero failures/errors/skips, and captured
actual unit target/wrapper exit0 with checked empty process tree. Inventory hash:
`01c0a5d497a43b176f27855f91790340ae80553a70a6e5c7a41f2dec522164aa`.
It does not transfer the earlier 227-test result onto this changed source.

The separate HTTP client PID **19364** has captured exit0 and 32 checks. Native
Blender PID **4320** has its own startup/exit sidecars, exact authenticated native
hello and clean owner close record: actual GUI exit0, wrapper exit0, Job0,
no retained handle, no taint, no overflow and no held cleanup. The native parent
PID **20688** and outer wrapper PID **25320** also have actual exit0/tree proof.
All these role PIDs are distinct. No engine, Job, Registry or journal owner is
opened by this audit; native cleanup facts are captured observations.

The 15 retained HTTP call records are audited directly, including route, client
role, listener, catalog, request and exact canonical response bytes. The audit
recomputes the catalog digest and producer source-map digest; validates common
Discovery/Request/Response; binds project/target, lease/revision, command ID,
native PID/generation, exact scene/context and JCS observation result hash; and
compares duplicate/own-session lookup bytes before and after Stop. It checks
revoked credentials, wrong catalog, write-lease denial, another session's lookup,
unsupported mutation, stale revision and lookup refusal on the canonical Stop
listener. Stop reports an observed native stop in approximately **16 ms** for
this idle workload. That is not a general latency guarantee under contention.

The pinned parent check observes exactly one new native data read despite the
duplicate/lookup/denial calls. The retained calls independently corroborate the
external response sequence; native channel counters were asserted by the pinned
parent and are not separately persisted as a numeric trace.

Secret verification is deliberately scoped: the pinned parent executed its
exact ephemeral-bearer scan before writing captured child output, and its
required successful scanner check is bound to the completed run. The file-only
audit also inspects retained output for bearer headers. Actual bearer values
remain ephemeral and pipe-only, so this audit does not independently reconstruct
them or claim a fingerprint scan of unavailable secrets. Core redaction and
observation-integrity regressions are separate tests within the frozen suite.

The audit suite passes **22/22**, actual subprocess exit0 under a 30-second
timeout: one positive candidate test and 21 incomplete/tampered/history refusal
cases. It rejects changed source hashes, incomplete capture, missing unit rows,
wrong actual/wrapper exits, unverified tree, wrong client exit, active native Job,
catalog/hash/duplicate/lookup/Stop bindings and a retained bearer header.
`audit-tests-process.json` pins the verifier/test sources and exact raw test-log
hashes. `verification.json` and `portable-artifacts.json` cover 151 read artifacts,
including the relevant failed-run metadata.

## Preserved failed attempts

| Package | Observed result | Distinction |
| --- | --- | --- |
| `client-01` | 227 units pass; native parent exit1 | Harness setup used `setup.inspect`/`setup.box`, outside native ID grammar. Failure occurred before setup effect. |
| `client-02` | 227 units pass; native parent exit1 | Setup armed a writer fence; unleased facade registration inspect was rejected. The scoped queue repair permits only exact `scene.inspect` without a lease; explicitly supplied read leases and all mutation fences remain checked. |
| `client-03` | 233 units pass; separate client 32 checks and exit0; native parent exit1 | Parent evidence serialization rejected the secret-shaped key `credential_label`. Child success did not complete the package. |
| `client-04` | 233 units, client32/parent6 and all required exits pass | Uses `client_role` and encodes evidence before file creation. Runtime source is byte-identical to `client-03`; only harness source changed. |

The first three packages remain FAIL. Tests explicitly reject promoting any of
them, including `client-03` with its successful child. No old evidence was edited
or moved, and no failure is hidden by the successful fourth attempt.

Run from `8-9-hh3d-3`:

```powershell
python -B zdoc/reviews/20260917-gt04-client-audit/verify_evidence.py --check-live
python -B -m unittest discover -s zdoc/reviews/20260917-gt04-client-audit -p test_evidence.py -v
```

`--write-derived` refreshes only the derived verification and artifact manifest.
`--package` plus `--expected-closure` allows an explicitly reviewed fresh package;
the default pins `client-04`. The verifier fails closed on incomplete candidates.

This proves the bounded authenticated read-only client component and its cleanup
on this source/workload. `public_ack=false` and `durable=false` remain explicit.
Public mutations, public durable receipt/recovery binding, wider supported
operations, full same-source GT04 regression and two independent acceptance
critics remain separate work. No acceptance verdict or plan tick is issued here.
