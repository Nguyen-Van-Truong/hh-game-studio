# GT04 S59 file preview and native regression candidate

Status: **CANDIDATE, NOT ACCEPTED; no independent critic verdicts for S59.**
Owner requested solo execution. This audit is coordinator verification, not
two independent reviews. GT05 remains unopened.

Runtime/test closure (139 files):
`943cff74f23a61427765071f7fd6661acbdad23c0e8386364f5615a2a0016134`.
The final review inventory is `review-closure.json`; Git byte inventory is
`files.json`. Exact earlier attempts remain separate.

| Requirement | Proof |
|---|---|
| Typed mutation preview, no effect or ID reservation | 21 new publication preview tests; three real HTTP profile probes each repeat file preview then apply the same command ID |
| Native UI/Edit context, selection, history and duplicate safety | Matrix UI: 95 checks across six GUI/background edit/reopen/checkpoint phases |
| Separate IPC/background job, native material geometry readback | IPC 31 checks; material 16; all three public file profiles |
| Stop/deadline/OOM, exact process ownership | IPC fault cases, deadline 19, cleanup retry 13, four publication Stop cuts |
| Durable receipt/fencing/FIFO | Durable 16, FIFO 19; public ledger nine intent/terminal pairs per profile |
| Closed protected publication/reopen, no effect replay | Checkpoint recovery 22; five crash cuts around intent, selector and terminal witness |
| Exact source/process/artifact evidence | Three profile audits, matrix audit, 15 negative evidence cases, Git byte proof |

`20260917-gt04-s59-scene-01` ran **594/594** complete Blender unit tests.
Checkpoint/export profiles each ran **328/328** focused tests. Each of the
three profiles has **49 HTTP checks, 36 calls, 10 parent/native checks**, and
17 native data requests. All three GUI/background/client/host wrapper paths
exited cleanly and drained their owned Jobs. The common ledger retains eight
COMMITTED receipts plus one known pre-effect capacity rejection.

The native matrix has **17 completed lanes / 240 top-level checks**. First 15
lanes use matrix-02 execution closure
`039dcc977b11c9a119f618517f2c61523c1bf4a8ae2beaac43b14f3fde3dee3f`;
the two final Stop lanes use matrix-03
`21469e6d76ba40c246462b99ac6d86a51d2944100c73b3517f4f701355ea1a5e`.
Both contain the same runtime; each recursively launched crash observer checks
the bound runtime and supplement source. No old verdict is transferred.

File preview checks live native fence/revision/context, supported profile,
fixed save slot, publication capacity and protected namespace. It does not
write files, reserve the apply ID, append INTENT or predict artifact hashes.
Application independently rechecks admission. Stop after selector but before
terminal leaves UNKNOWN/SELECTING/hold; Stop after terminal preserves the exact
COMMITTED receipt. Read-only reopen never replays either effect.

## Retained failures and corrections

- Matrix-01 failed before mutation because the supplement placed TEMP/user
  directories inside a fixture required to be empty. Matrix-02 moves them
  outside that fixture; runtime remains unchanged.
- Matrix-02 `stop_after_selector` used the obsolete publication03 expectation
  of COMMITTED immediately after selection. The current phase guard and
  `test_expiry_during_selector_write_retains_unknown_without_rollback` require
  an incomplete prefix to remain UNKNOWN. Matrix-03 verifies exact SELECTING
  state/absence of terminal, and adds a separate after-terminal success case.
  It changes the test driver, not runtime behavior or the terminal requirement.
- Embedded Blender Python emitted seven `.pyc` files during direct probes.
  All 139 pinned source files remained identical. `generated-cache.json`
  records their paths/hashes; only these derived files were removed after owned
  exits. The first negative-audit attempt stopped at this inventory mismatch;
  it is retained as incomplete and is not counted among the 15 passing cases.
- One preliminary pure test tried to inspect an already closed in-memory gate.
  Its assertion now checks gate closure and exact retained Job ownership.
- Public documentation fetches returned HTTP 402/403 in this session; no new
  external API claim was treated as verified from those failed requests.

Native `.writer` sentinels and live `.guard`/generated cache paths are not
installed as portable authority. Closed guard/cache bytes are copied under
`closed-artifacts/` and hash checked; empty writer sentinels have no recovery
content. Raw process logs retain their observed local paths. This candidate
is developer evidence, not a sanitized distributable package.

## Reproduce verification without opening native owners

From the repository root, run `python -B` on these scripts in this directory:

- `verify_evidence.py scene`, then `checkpoint`, then `export`.
- `verify_matrix.py`.
- `test_evidence_rejection.py` and `test_matrix_rejection.py`.
- `checkpoint.py HEAD` after the checkpoint is committed.

Formal gates remain unchanged: GT04 final coverage/review acceptance requires
two independent critics on one final review inventory. Public ACK/live scene
durability, arbitrary external files, writable restart/restored Undo and
cross-app recovery are not claimed. GT05–GT10 and real-device Android remain
future gates; HH World has its own subsequent plan.
