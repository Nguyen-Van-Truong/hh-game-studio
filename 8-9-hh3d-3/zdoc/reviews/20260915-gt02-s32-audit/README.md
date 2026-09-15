# S32 solo implementation checkpoint

GT-02 remains CANDIDATE. This package adds experimental broker-local staging;
public safe-write/atomic-replace and consumer mutation remain unavailable.
The owner paused subagents. No independent final review is claimed for S32.
Source/evidence checkpoint: `957ea889125eeb34a1df99771e965fad90552b61`.
`git-byte-verification-head.json` proves reconstruction from that exact commit.

Frozen run: `GT02-S32-20260915-01`, command `cmd.GT02-S32-20260915-01`.
Source closure (65 files):
`983e205a2c815c6e530bf6ef4255d84cc17b4fae0e05a5e9a2848960515d82b1`.
Protocol **169 passed /173 run,4 explicit platform skips**; bootstrap **56/56**.
19 new native private-store tests passed. Actual host exits, owned process tree,
source/snapshot stability,9 artifact hashes and2396 Python/Node/Godot rows
(plus9 Godot negative cases) were verified. `verification.json` maps the earlier
P01–P22 baseline and the narrower S32-STAGING subset to exact passing test IDs.
This mapping is not a new gate or acceptance checklist.

Implementation: `studio/host/core/private_store.py`, its `PRIVATE_STORE.md`
contract and `studio/tests/protocol/test_private_store.py`. The candidate runner's
gap wording now distinguishes experimental staging from unavailable public
mutation. Storage uses protected owner DACLs, retained no-follow handles, a
single writer guard, size/count quotas, checked write-through/flush/readback and
no collision overwrite. Uncertain partial staging preserves bytes and blocks
further writes on that instance. Reopen does not authorize old-command replay.

The interrupted design review in `../20260915-gt02-s32-native-store-audit.md`
binds earlier draft hashes. Coordinator fixes after that inspected draft:

- Every ancestor/root/guard/blob handle now shares a tracked native ownership
  registry. A failed native close retains the live handle; another `close()`
  finishes cleanup. Tests inject failure before the OS call, verify the handle
  is still valid, then verify real closure after retry.
- NTFS is checked before creating a root. Failure after creation reports
  uncertainty; constructor exceptions retain local cleanup ownership.
- Operations recheck ancestor, root, guard identity and private security;
  directory handles use READ sharing only. Impersonation is refused.

These fixes were tested by the coordinator; the paused reviewer did not issue a
new verdict on the final source. S30 critics remain bound to S30, not inherited
by this candidate. The source/test author is not an independent reviewer.

Diagnostic mistakes retained as lessons: the initial hardlink setup tried
`os.link` while ancestors remained held and got Windows32; the corrected test
closes the store, seeds the alias, and reopens to test rejection. The initial
constructor-cleanup fault mock also intercepted token initialization; the
corrected injection targets only tracked file/directory handles. Neither failed
setup is represented as acceptance evidence or an OS isolation guarantee.

S31 AppContainer proof is committed at52def92. The resumed S32 fixed native
boundary separately completed run05; see `../20260915-gt02-s32-boundary.md`.
The next integration must bind a real confined worker through bytes-only IPC,
exercise private_store under that boundary, then implement durable expected-
generation activation and command recovery. The append-only selector proposal
is in `../20260915-gt02-s32-activation-contract.md`; it preserves the active
manifest semantics and is not implemented by the existing generic Journal.

`verify_evidence.py` verifies saved bytes/markers and creates only the coordinator
verification result. It does not rerun engines or sign acceptance. The Git-byte
verifier reconstructs staged/committed source and artifacts before applying that
verification. Earlier candidate/review packages remain immutable.
