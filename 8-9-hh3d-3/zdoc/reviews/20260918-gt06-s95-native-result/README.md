# S95 completed isolated native diagnostic

AUTHORITY=0. `formal_acceptance=false`; `eligible_for_dataset=false`.

`gt06-s95-native-isolation-01` completed all 35 batches × 100 native cycles.
Native elapsed time was 937.112325 seconds; the external owner observed natural
supervisor exit at 2026-09-18T15:32:50Z after 954.157 seconds. Every batch had
71,127 ObjectDB objects and six resources. Maximum native heartbeat gap was
1102.852 ms. Only the baseline sparse snapshot was triggered.

This means the +2 object increase was **not reproduced in this isolated
workload**. HTTP work, host permits, ACK processing and their load/idle durations
were absent. These native counters are prepublication; they must not be compared
with the coupled post-ACK baseline as if both represented the same phase.
The baseline partial inventory included 102 Trees, 4,493 TreeItems and 12
Node3D-family objects (4,607 selected IDs), leaving 66,520 objects outside the
inventory. Later identity stability was not measured. No no-leak claim follows.

Actual import26164/editor11288/native-child32268/supervisor21072 exits were zero.
The three owned-stage captures and the external retained supervisor handle
agree. Native/helper Jobs were zero and closed, process/probe handles released,
and the external Job had zero descendants before cleanup. Scheduler terminal
observation at15:33:13Z independently recorded state3/result0/no instances;
the four known live PIDs were absent. See exact capture records for helper
and target domains; a scheduler return alone is insufficient.

The fixed source40 closure is
`ebed9418490379bb902d2049e4a2f98a96e3378d09b369aef02684e16214c74e`;
helper closure is
`4448ab35a6e087c8756063e0d8a025f4dc60a44329fcf56c4b270e6d1474302b`.
The coupled source51 remains separately pinned at
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`.
All declared67 raw artifacts and40 archived source files were checked;
`evidence/` contains120 exact copies. Its manifest SHA256 is
`e79551bccc6e746a0b6cb50653ec559fd3a1d99c59273d75be1e731deb201f0a`.

Recheck the packet without launching an engine:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s95-native-result/seal.py --verify
```

The separate strict selected-object analyzer completed with actual exit0 and
empty stderr. See `../20260918-gt06-s95-result-prep/object-analysis/check-01/`;
its exact stdout SHA256 is
`97176938356ac4610310830dda513b43cbbf3de3b98a0f7b479f6d5a3f59b294`.
It does not independently inspect OS lifecycle; the retained capture and
scheduler evidence above provide that distinct proof.

After preservation, the fixed task was retired at15:35:43Z. Its deletion
receipt remains in `../20260918-gt06-s95-native-isolation/launch-01/task-deleted.json`,
outside the earlier terminal packet, and is not a replacement for exit proof.

Next: prepare one coupled diagnostic with bounded HTTP phase correlation and
same-phase native sparse capture. Its purpose is to distinguish client/server/
journal delays while preserving a potential object-growth identity snapshot.
No blind campaign retry, timing threshold relaxation or reinterpretation of
the S93 failure is justified by this isolated result. GT06 still needs the
unaltered complete campaign and two independent final critics.
