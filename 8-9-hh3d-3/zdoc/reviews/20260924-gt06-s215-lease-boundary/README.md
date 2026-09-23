# S218 — S215 lease-response uncertainty

The fresh formal campaign `gt06-s215-formal-01` reached batches 0–5 and failed at the start of batch 6 when the host owner received the exact `CONNECTION_LOST_LOOKUP` transport sentinel from `/v1/lease` and `CommandProducer._connect_batch` treated it as an unhandled lease error. Import had actual exit 0; the host owner exited 1; the editor target exit was not independently recorded. Jobs were zero/closed, owned tree was zero, owner was closed, handles were released, and cleanup reported no error.

This is Authority 0 and not a leak, ownership, root-cause, or GT06 acceptance. The next repair is bounded lease-response reconciliation for the same session, without resubmitting a mutation command or changing the formal gate, timeout baseline, profile, counter, or RSS thresholds.
