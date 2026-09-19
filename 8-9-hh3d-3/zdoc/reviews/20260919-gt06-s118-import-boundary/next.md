# Pending result work (AUTHORITY=0)

`read_lookup_terminal.py` is a prepared, **unvalidated** offline reader. Do not
run tests alongside S117-03 or use its output as an acceptance verdict. After
the run ends, validate bindings and negative cases before interpreting it.

The reader must reject missing terminal state and mismatched run/PID/closure.
For failure windows it matches lookup client/server ports plus lifecycle root
and QPC interval. Multiple matches, missing IDs or evicted needed events are
UNKNOWN. The timing collector retains only the three slowest original calls
per fixed label, so a missing overlap never proves absence of blocking.
Thread IDs come from get_ident versus get_native_id on pinned Windows CPython;
verify actual event/timing thread and interval consistency before attributing.
Nested wall spans must not be summed. Low thread CPU does not distinguish
disk, GIL, page faults, lock waits or scheduler stalls.

After terminal, preserve all run files and frozen copied helpers; record local
journal/cache exclusions separately. Verify raw and portable domains, actual
target/helper exits, all owner Jobs/handles, Stop and source/execution pins.
Do not infer editor target natural exit from parent or forced wrapper exit.
The original benchmark gates still win over a planned diagnostic boundary.

If there is a uniquely matched long SQLite COMMIT or JSONL fsync within a held
journal append, it identifies an observed waiting interval, not its system
cause or permission to weaken durability. Review the narrow affected boundary
before a repair. If no reproduction or incomplete matches, document that limit;
do not automatically rerun the same diagnostic or restart a formal campaign.
