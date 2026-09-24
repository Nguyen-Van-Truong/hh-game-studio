# S231 — read-only S229 object-counter boundary review

This packet is a read-only derivation from the sealed S229 raw campaign. It
does not start Godot, Blender, the benchmark harness, or a formal attempt.

The S229 joint observations contain batches 0 through 16. The batch-4
baseline is `objects=71128`, `resources=6`, and `editor held_handles=558`.
Objects remain 71128 for batches 5 through 15. Batch 16 is the first and only
observed object-counter change: `71128 -> 71130` (+2). At that same row,
resources remain 6, editor handles are 554, host handles are 204, and the
status gap is 759.320 ms, below the 2000 ms screen limit. Batch 15 and batch
16 use the same 1000-command mix (500 inspect, 300 rejected, 200 admitted) and
the same 200-effect increment, so this packet does not identify a
batch-specific command mix as the cause.

This is boundary evidence only. It does not prove a measurement defect, leak,
ownership, or root cause. It does not authorize a formal retry, a threshold
change, or GT06 acceptance. The next valid formal attempt still requires a
distinct supported object-counter measurement boundary or an owner ADR.

Inputs remain immutable: S229 raw manifest SHA256 is
`30f0bba3ba413754d8055db62ecf1de36e1c6b43b547a99a8bb31ab393df949f` and its
sealed archive SHA256 is
`391f0e6347f1fd1112366144b00622ac5d895ba669ad81a718e6918a4e29c92b`.
