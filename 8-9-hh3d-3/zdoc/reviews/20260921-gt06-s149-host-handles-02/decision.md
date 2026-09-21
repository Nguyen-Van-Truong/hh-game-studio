# S149: identify the host descriptor class before changing runtime

AUTHORITY=0. No formal retry, F13/F14 or engine launch.

S147 already records the 204 to 205 transition inside HTTP batch 10, before
native cycles. It remains 205 at the original joint sample. The editor is
below its own baseline; RSS and ObjectDB do not trigger this failure.

The outstanding alternatives are a retained file/index descriptor, a request
socket/thread, or another kernel object initialized during the host workload.
The count-only S147 observations cannot distinguish them. The S144 standalone
handle probe ran only seven **10-command groups**, not seven 1000-command
batches, so it did not cover this cardinality. The full S144/S145 coupled
diagnostics cover only seven batches, before S147's batch-10 boundary.

Use one bounded host-only diagnostic with unchanged CommandProducer.run_batch:
up to eleven 1000-command batches, five warmups, original host RSS/handle/status
checks and client timeouts. A separate owning parent records a PSS handle census
at baseline 4 and the first failing sample (or final boundary). It uses a
retained ProcessProbe bound to the helper's target PID and child creation time.
The child pauses only after the original counter/time sample and outside the
command window. Observer effects and the omitted native/ACK/idle workload are
explicit limitations. Never subtract observation costs or claim equivalence to
a complete coupled pair. Preserve failure as failure, even if cleanup succeeds.

Prerequisites: static classifier/identity checks and one owned 10-command smoke
with external census and checked cleanup. The smoke is not a warmup for the
fresh diagnostic. Main driver defaults to check-only, fresh IDs, 1200s child /
1230s outer diagnostic bound, halt at first original host gate failure. No
source/profile/timeout/baseline/workstation adjustment; no other engine runs.

After terminal, compare baseline/failure type counts and redacted entry fields.
Numeric handle reuse and a changed name hash do not prove kernel object
identity. UNKNOWN/cleanup failure stops interpretation and is retained. Only
measured descriptor class evidence can justify a narrower causal experiment or
repair. If no growth recurs, record non-reproduction; do not loop retries.


## S149-02 observer-neutral follow-up

Fresh ID after the smoke showed an external census one handle above the child sample while the child was polling. This copy uses zero-duration scheduler yield during the ACK wait; it does not change CommandProducer or campaign gates. The S149-01 packet remains immutable.

