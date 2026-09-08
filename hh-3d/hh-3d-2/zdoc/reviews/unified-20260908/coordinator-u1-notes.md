# Coordinator findings pending final critics, U1

1. Static checker found remaining D04 reference in Q04-C after consolidation.
   Replace with scope/mode section3.1. Do not change frozen source until both
   U1 read-only critics finish; U2 must be frozen/reviewed.
2. DB-D2 receipt lookup needs explicit distinction between visible local row
   and synchronous-commit acknowledgement after timeout/cancel. Proposed
   recovery barrier on current fenced primary/timeline: read+lock command row,
   insert durable recovery-confirmation marker in same transaction, require
   synchronous_commit=on and successful protected COMMIT; ordered WAL flush
   includes the original transaction. Failure/unknown keeps UNKNOWN. Mere
   health check or row presence must not return protected success. Implementer
   must pin PG version and verify fault scenarios under P3-01/P3-04/P6-02.
   This is coordinator design proposal, not measured runtime or new source
   documentation claim.
3. Source U1 already clarifies cross-room source-active + target-pending hold
   bounded by one transition while same-room device takeover needs one hold.
4. Source U1 already makes expiry/cancel terminal only before RESULT_RECORDED.
