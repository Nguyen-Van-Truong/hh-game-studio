# GT04 UI handoff — 2026-09-17

AUTHORITY=0. This is an implementation checkpoint and historical evidence check,
not GT04 acceptance or two independent critic signatures.

The completed capture is `../20260917-gt04-ui-06/`. Its 15 source files match
both current source and frozen snapshot byte for byte. Closure:
`f82734f69558da106732e0f6638d14687c2d9fc71141ad1acb35cc734c2048c8`.
The result SHA256 is
`6f0fa5b7fb159dd8526afa3c3710f736836ad87d28d6e8ea617596c6bd781dce`.

- Python: 40/40, no skips.
- Actual Blender 5.2.1 LTS GUI: 36 edit/history, 9 reopen, 7 checkpoint checks.
- Actual background regression: 27 edit, 9 reopen, 7 checkpoint checks.
- Seven captured target exits and wrapper exits are integer zero; Job tree
  observations are clean. No Blender process remained at handoff inspection.
- All 50 artifact hashes, full source membership, executable pin, exact argv,
  ordered raw markers, strict bool/int types, timestamps, saved bytes and
  semantic save/reopen hashes were checked again read-only. No engine rerun.

The UI lane adds a bounded main-thread timer queue and actual Blender native
undo/redo, including Object/Edit Mesh create and transform, duplicate undo,
two-step edit history, redo branch invalidation, context restoration, queue
expiry, Stop, fixed-slot save and fresh-process reopen. The background adapter
implementation is unchanged. See the source README for exact operation bounds.

Earlier UI-01/02/03 failures are preserved, as are UI-04/05 successes on their
own older source hashes. They are not relabeled as UI-06. The final capture ran
from 2026-09-16T19:39:54Z to 19:40:12Z. `verification.json` records the subsequent
read-only consistency check, not a new native execution.

Remaining GT04 work includes authenticated external IPC, lease/fence ownership,
durable dedupe/journal, constrained export, resource-isolated jobs, hostile
dependency admission and crash/OOM recovery. This fixture requires exclusive
ownership; it does not open arbitrary artist files, claim race-resistant save,
crash durability or public ACK. Both acceptance and public_ack remain false.
The inherited runner still uses equality for some evidence values; this
handoff checked actual raw bool/int types separately rather than assuming its
PASS flag is sufficient. No stronger handle-close proof is inferred from the
accepted bootstrap's Job-tree observation.

One generated Blender compatibility-cache artifact is part of the historical
50-entry capture inventory. Preserve the original report; do not silently
rewrite its inventory when deciding checkpoint artifact packaging.
