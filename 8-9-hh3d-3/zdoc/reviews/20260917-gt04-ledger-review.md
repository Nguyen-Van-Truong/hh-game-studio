# GT04 Blender client ledger — bounded independent component review

Review date: 2026-09-17, Asia/Saigon. Hash verification: 2026-09-17T00:08:24Z.
Reviewer: `/root/s56_blender_ledger_review`, separate from the component author.
Baseline Git HEAD: `4b10c533545ff0433738219fade79ff8b11cea93`.
The three reviewed component files were untracked additions at review start.

**Result: one P2 finding on the original hashes below, closed by the bounded
follow-up at the end of this report.** No duplicate
execution, unauthorized native mutation, or false durable COMMITTED return was
demonstrated. This is a component review, not either independent GT04 acceptance
signature. `AUTHORITY=0`; no plan checkbox or acceptance verdict is changed.

## Scope and method

Read `8-9-hh3d-3/AGENTS.md`, the current S55 tool-plan top and GT04 section, the
three component files, immutable core Journal/protocol contracts, and the related
Blender read-session, native queue, durable-session and publication models.
The current plan keeps GT03/04 in progress and this ledger unadvertised.

Only static reads and explicitly inert in-memory execution were performed. No
Godot/Blender process, Registry operation, native journal/storage test, public
route, production source edit, test edit, plan edit or Git mutation was performed.
One existing Godot process was observed at start; it was left untouched.

From `8-9-hh3d-3`, the existing command
`python -B -m unittest studio.tests.blender.test_client_ledger -v` completed with
`Ran 28 tests in 5.479s` and `OK`. This suite replaces storage and locking with
`MemoryJournal`; it is model evidence only. Additional pure guard-exit cuts below
exercised production decorated methods on the same inert backend. No extra
artifact besides this report was created by the reviewer.

## P2 — Normalize errors from the complete journal guard boundary

Locations on the original source:

- `studio/host/blender/client_ledger.py:363-377`: `begin` catches only
  `JournalError` around the decorated `retry`/`admit` calls.
- `studio/host/blender/client_ledger.py:395-399`: `finish` sets its hold on any
  exception, but rethrows a non-`JournalError` without uncertainty provenance.
- `studio/host/core/journal.py:263-283`: the unchanged `_mutating` wrapper only
  normalizes `JournalError`; this wrapper exits its guard *after* the component
  method has completed its append and readback.
- `studio/host/core/journal.py:206-213`: guard cleanup directly invokes
  `os.lseek`, `msvcrt.locking`/`fcntl.flock`, and `os.close`, which can raise a
  plain `OSError`. The inner catches in `_ClientJournal.admit`/`finish` cannot
  catch failures occurring after those method bodies return.

**Trigger and observed behavior.** Inject a plain `OSError` at the exit of the
inert guard after the admission body completes. The actual decorated `admit`
has already appended the intent and reread it, but `begin` raises the raw OS
exception, with no `code` or `outcome_unknown`, and leaves `_held=False`:

```text
exception=OSError code=None outcome_unknown=None held=False
permits=0 rows=2 last_status=ACCEPTED_PENDING
```

The analogous terminal cut occurs after a terminal row and readback:

```text
exception=OSError code=None outcome_unknown=None held=True
permits=1 rows=3 last_status=COMMITTED
```

**Impact is limited but concrete.** The component exposes an unclassified
failure even though persistence may have completed. On admission it also omits
its own uncertainty hold. A caller relying on `JournalError.outcome_unknown`
cannot distinguish this from a pre-admission failure. This conflicts with the
core contract's explicit rule that guard-exit failure cannot revoke an effect
and must preserve UNKNOWN provenance. It is not evidence of a duplicate: after
the admission cut, the retained intent makes exact retry return UNKNOWN with
`dispatch_permitted=false` and no permit. After the terminal cut, an exact
storage retry returns the original bytes and consumes the retained permit.

**Fix within this component's scope.** Preserve the existing classified
`JournalError` handling, including known capacity/conflict refusals. Also catch
non-`JournalError` failures around each *complete decorated* backend call, set
the ledger hold where admission or terminal persistence is uncertain, and raise
a stable `LedgerError(..., outcome_unknown=True)` chained from the internal
error. Terminal failure must retain the same marker and already-pinned response.
This does not require changing the frozen core Journal or weakening any check.
Add pure regression cases for guard exit after admission and terminal readback;
existing tests inject `_append` failures and therefore do not reach this cut.

### Reproduction

Run the following via `python -B -` from `8-9-hh3d-3`. It uses the existing inert
test harness and never constructs the native Journal, Registry, or engine owner.
The two cases below were executed separately against the listed hashes; their
captured output is summarized above.

```python
from contextlib import contextmanager
from studio.tests.blender.test_client_ledger import (
    FacadeLedgerTests, request, response,
)

for phase in ("admission", "terminal"):
    case = FacadeLedgerTests(
        "test_permit_only_after_readback_and_exact_identity_finish"
    )
    case.setUp()
    try:
        marker = case.begin().permit if phase == "terminal" else None
        backend = case.backend
        original = backend._writer_lock
        calls = [0]

        @contextmanager
        def cut_after_guard_body():
            calls[0] += 1
            # begin's first guard is retry; its second is the new admit.
            cut = phase == "terminal" or calls[0] == 2
            with original():
                yield
            if cut:
                raise OSError("inert guard-release failure after readback")

        backend._writer_lock = cut_after_guard_body
        try:
            if phase == "admission":
                case.begin()
            else:
                case.ledger.finish(marker, response(request()))
        except Exception as error:
            print(phase, {
                "exception": type(error).__name__,
                "code": getattr(error, "code", None),
                "outcome_unknown": getattr(error, "outcome_unknown", None),
                "held": case.ledger._held,
                "permits": len(case.ledger._permits),
                "rows": len(backend._records),
                "last_status": backend._records[-1]["status"],
            })
        backend._writer_lock = original
        if phase == "admission":
            repeated = case.begin()
            print(repeated.replayed, repeated.permit,
                  repeated.response.decode())
        else:
            saved = case.ledger.finish(marker, response(request()))
            print("exact_reconciliation", saved == case.begin().response,
                  "remaining_permits", len(case.ledger._permits))
    finally:
        case.doCleanups()
```

## Checks with no additional actionable finding

- Full public identity is hashed into the private alias; equality checks on
  session, public ID, request digest/revision and native bytes reject collisions
  or changed semantic/native translations. Authority-field changes retrieve the
  original intent without renewing it.
- Inspect cannot bind a native write; typed edit payload/context, fixed save
  slots and the separate publication request schema are checked before intent
  admission. Native JSON bytes are retained separately from JCS Request bytes,
  preserving the native integer/float distinction on retries.
- The opaque permit is instance-owned, minted only after append/readback, and
  consumed after exact terminal readback. Duplicate and reopened intents return
  no permit. Terminal conflicts do not replace recorded response bytes.
- The reducer validates the complete supplied chain, pending count, command
  cap, terminal order, hashes and bindings. Its 65-record/17-MiB configuration
  accommodates the unchanged core's one-terminal-row/envelope reservation for
  each of 32 commands. The in-memory capacity tests do not prove native quota
  accounting, OS locking or barriers.
- Unfinished intent lookup is deterministic UNKNOWN; expiry/reopen does not
  authorize re-execution. Recorded terminal bytes are canonical and returned
  exactly. Both required no-public-ACK flags and redaction invariance are checked.

## Explicit gaps, not new implementation findings

1. The real public catalog grants only inspect/lookup/Stop. The tests mock grants
   to exercise future write shapes. This module adds no advertised write scope
   and does not by itself authorize native dispatch.
2. Actual native journal create/reopen, simultaneous independent facade/process
   access, guard failure, fsync/reload durability, configured-capacity reservation
   and owner-path/source/PID/Job binding require coordinator-run evidence against
   a frozen closure. The inert RLock is not native concurrency proof.
3. Native/publication response provenance, fences, actual-effect deadlines,
   Stop/revocation linearization, final transport redaction, dispatch-budget
   reservation and mapping native receipts into common Response remain integration
   requirements already identified in `CLIENT_LEDGER.md`. A caller-supplied
   COMMITTED with the two required flags is a ledger receipt, not native success
   or publication-custody evidence.
4. Local checksums and complete-chain validation do not detect replacement by a
   different valid prefix/history or prove rollback resistance. The document
   explicitly disclaims a rollback witness. Do not interpret its “incomplete
   chain fails closed” sentence as a claim to detect every valid-prefix rollback.
5. There is no standalone historical public-ledger reopen/authentication API:
   `from_owner` requires the original live owner, while the pure backend can read
   old records. Session expiry and owner lifetime still constrain usable public
   lookup. No GUI recovery or post-restart public delivery was established.

These gaps do not request GT07 work. Keep the component unadvertised and keep
GT04 acceptance separate from both this review and the pure unit count.

## Exact reviewed hashes

Paths are relative to `8-9-hh3d-3`. SHA-256 values below name the original bytes
reviewed; a later fix needs its own hash and targeted verification. This is a
file-level review manifest, not a claimed complete runtime acceptance closure.

| File | SHA-256 |
| --- | --- |
| `studio/host/blender/client_ledger.py` | `90b46098eaa42512f83e5bda22a257b5d2704d62cc79aad9a7bc33303d4def7b` |
| `studio/host/blender/CLIENT_LEDGER.md` | `75ddbb746e7fad2df94db489e64b1e95cbd39a71809959c54da918dc2efa78aa` |
| `studio/tests/blender/test_client_ledger.py` | `1082919294efd7337caf0aced01fffdadd228566c1afee33cb96758bd08eaee0` |
| `studio/host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |
| `studio/host/core/JOURNAL.md` | `2513c5a0f9f299e9148ae7bb3201cbe0be42a32c563c029dfa8f70a5fb9f2875` |
| `studio/host/core/limits.py` | `9d01ce56f5976bb034e60e33bf4b7986cdc44b3a8ffad46da738a6ed1b143f3f` |
| `studio/host/core/transport.py` | `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0` |
| `studio/protocol/core.py` | `e8153f5a4dcf639f4d1cbce2fa74f7866d963a692c68e4e8d1477136889bd93e` |
| `studio/host/blender/client_owner.py` | `a4be370b8521d32c215bddd2ebf58b4facd0c0ac7b08abc74173106dd9c472bc` |
| `studio/host/blender/client_session.py` | `6997d7dc916ea33265cadaa71c5d811b6b7c9d3710e073c4b8a6921cf6e7710b` |
| `studio/host/blender/client_catalog.py` | `4834cac712c0ce85b1110972c86ddd1f7e9b4101e13f8f66bf46242862b09450` |
| `studio/host/blender/ui_host.py` | `218215ec59f837a49c1bbdaa1ab701ea473ab3ee1a20bc47147e8c0b3b5d5c77` |
| `studio/host/blender/durable_session.py` | `7ad86bd81872db10c45209ebf6d4a29d9139991842293af3237f7eb159bc341c` |
| `studio/host/blender/writer_journal.py` | `9b3fcec6067c58b9ce8455e550eb3a293a3194418c610769ff48cdc9f7caa54d` |
| `studio/host/blender/publication_state.py` | `8e88b9fe5c93aee37866cb9a963d69de36d3bddfee5efcaf4b3c2495c123638d` |
| `studio/host/blender/publication_owner.py` | `04f00dfbf0b5405fc687f3c18dc5a6ac6d6560825e1351c1c410e202b40b5274` |
| `studio/blender-addon/ui_queue.py` | `1c31c5075e78d6e320b008e550429692c3a0bf2e8350791673c8310e93f94421` |
| `studio/blender-addon/contract.py` | `4bd42efa716a3ff5c6d3fdd1c8b5cf42b683056f8ce0ee5550b969e181df857a` |

## Follow-up — coordinator fix reviewed, P2 closed within component scope

Read-only follow-up completed at 2026-09-17T00:09:56Z. The coordinator, not this
reviewer, changed the runtime source and added two focused model regressions.
No broad suite or native test was rerun by this reviewer.

The final `begin` handler at lines 378-383 catches a generic failure from the
complete decorated call, sets `_held=True`, and raises
`BLENDER_LEDGER_ADMISSION_UNKNOWN` with `outcome_unknown=True` and the original
exception as cause. No marker is minted on this path. Existing classified
`JournalError` refusal handling remains intact.

The final `finish` handlers at lines 403-409 preserve a `JournalError` code while
marking uncertainty, or wrap a generic failure as
`BLENDER_LEDGER_TERMINAL_UNKNOWN` with `outcome_unknown=True`. Both hold admission;
the permit and exact attempted response remain available for reconciliation.

The added tests at `test_client_ledger.py:396` and `:424` inject the error after
the actual decorated method body has appended/read back the intent or terminal.
They assert classified uncertainty, holds, retained journal status, no admission
permit, and exact retry behavior. The coordinator reports **30/30 tests, actual
process exit 0** on these final bytes; that execution result is attributed to the
coordinator, not presented as a second reviewer-run suite.

As a read-only delta check, reversing exactly the two new exception-handler
changes in memory reproduced the original runtime SHA-256
`90b46098eaa42512f83e5bda22a257b5d2704d62cc79aad9a7bc33303d4def7b`.
This verifies that no unrelated runtime edit was folded into the fix. The
documentation and immutable core Journal hashes are unchanged.

| Final file | SHA-256 |
| --- | --- |
| `studio/host/blender/client_ledger.py` | `63124d76fa5ec0e28b8095470c3e9585b9510df88a17a982043850ad5b9e0f44` |
| `studio/tests/blender/test_client_ledger.py` | `21da5ec2e0b11e257c47632c4133fd29acf92acde1dca85cb0ac3589c3701e5a` |
| `studio/host/blender/CLIENT_LEDGER.md` | `75ddbb746e7fad2df94db489e64b1e95cbd39a71809959c54da918dc2efa78aa` |
| `studio/host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |

**Disposition:** the narrow P2 is addressed by this delta. No additional
actionable defect was identified in this follow-up. All explicitly listed
integration/evidence gaps remain open; this is still neither GT04 acceptance nor
permission to advertise writes or durable public ACKs.
