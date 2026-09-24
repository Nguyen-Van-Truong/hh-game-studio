# S236 — bounded retained-handle boundary diagnostic

This diagnostic ran one fresh editor pair for exactly nine batches on the frozen
formal source behavior. It did not run the formal 10-pair dataset and produced
no acceptance output. At each batch it recorded the existing pre-ACK sample and
an additional sample immediately after ACK through the same identity-checked
editor handle. After batch 8 it issued no new start permit and sampled the handle
for at most two seconds before allowing owned cleanup.

The route reached its intentional nine-batch bound with no screen failure. The
pre-ACK editor counts were 562, 556, 556, 552, 556, 552, 552, 552, 552; the
post-ACK values matched each row. The terminal idle samples after batch 8 stayed
552. Objects/resources stayed 71130/6. This run therefore does not reproduce the
S232 +2 row, and does not prove a measurement defect, leak, ownership, or root
cause. It is useful boundary evidence only.

The wrapper and editor jobs were closed at zero and handles were released. The
child exited through the intentional diagnostic bound; this is not a natural
benchmark success. The run remains Authority 0 and cannot tick GT06 or change
any timeout, baseline, profile, counter, RSS, or gate. A future formal campaign
still requires a fresh source closure and the unchanged 10×35 acceptance.
This diagnostic does not authorize a formal retry by itself; a new campaign requires a distinct supported boundary or an owner-approved ADR.

Raw evidence is sealed at
`studio/.local/reviews/gt06-s236-handle-boundary-01` and
`studio/.local/archives/gt06-s236-handle-boundary-01-s237-terminal.zip`.
Run `python -B zdoc/reviews/20260924-gt06-s236-handle-boundary/verify.py`
from `8-9-hh3d-3` for a read-only check.
