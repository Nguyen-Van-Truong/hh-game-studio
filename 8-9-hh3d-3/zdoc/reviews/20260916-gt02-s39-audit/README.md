# S39 authenticated selector endpoint — CANDIDATE

Frozen candidate: `GT02-S39-20260916-01`, closure
`6972f55fbc72e3095ef4869c69428b89c5aea68ca24532a96d174dbc2c33131f`.
The protocol lane ran **283: 279 pass + 4 explicit skips** and bootstrap ran
**56/56**. The source snapshot and owned process trees were unchanged/clean.
This is coordinator evidence only; independent critics and GT-02 acceptance are
still absent.

S39 adds `selector_pipe.py`: a broker binds one selector, one private store and
one consumer; an endpoint authenticates the retained PID/session before JSON
parsing. The broker admits one typed activation, advances exactly one local
phase at a time, and never pumps a pending command reconstructed after reopen.
The control role remains available for Stop/Cancel/lookup. Cancellation reads
the durable phase again while holding the selector lock, so a late control
request reports UNKNOWN when selection already won instead of claiming no
effect. Broker ownership cannot silently transfer during an active pump.

The focused substituted-frame run passed **16/16**. It covers wrong project,
role, session, token and fence; secret-bearing inert assets; rotation/revocation
between phases; response loss; Stop before and after selection; preserved
partial staging; explicit restore; quota/storage uncertainty; and control
availability while a bounded storage gate is held. It uses the same private
event stream and fixture selector but does not claim OS endpoint proof.

The native run passed **7 AppContainer cases** with actual child exit `61`,
retained endpoint PID/token identity and Job active process/PID lists empty at
close. It drives the selector endpoint through native framed bytes for submit,
wrong token, stale fence, lost reply, cancel, Stop and Stop-after-selection.
Every case records private-root directory read/write and event-stream access
as `ERROR_ACCESS_DENIED` (5), not a mocked result. The submit retry receives
the same durable receipt and consumer adoption count remains one. Profile,
owned temp and runtime snapshot cleanup are checked after the run.

The native program is a fixed fixture client; it cannot supply paths, callbacks,
consumer objects or recovery force bits. It proves this local AppContainer
boundary on this Windows host, not a production Godot/Blender adapter, external
source revision scanner or physical power-loss guarantee. General
`safe_write`/`atomic_replace` remain false. GT-03 through GT-10 remain gated.

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s39-audit/verify_evidence.py
```
