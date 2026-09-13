# GT-01 lifecycle candidate audit (r12)

Command: `python 8-9-hh3d-3/zdoc/reviews/20260913-r12/test_lifecycle_candidate.py`

Result: **5/5 passed** using synthetic temporary roots; no engine, archive, network, or process termination was used.

Covered cases:

- Manual metadata edit: stale recovery rejects the original CAS token and preserves the lock.
- Live owner: an old lease whose recorded process identity is still live is refused.
- Crashed owner: a lease with a missing owner and satisfied age threshold is reclaimed.
- Replacement race: if metadata is replaced between observation and unlink, recovery fails closed and preserves the replacement.
- TTL: a recent lock is refused even when age threshold is larger.

Limits: these are candidate unit checks only. They do not prove Windows handle semantics, crash power-loss durability, true PID reuse, multi-process contention timing, or official GT-01 acceptance. A coordinator must rerun the full bootstrap suite and bind any acceptance evidence to a frozen source hash with independent critics.
