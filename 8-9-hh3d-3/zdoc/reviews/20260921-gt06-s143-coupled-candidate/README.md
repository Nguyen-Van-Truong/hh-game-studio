# S143 coupled candidate — diagnostic only

Seven original batches, each 1000 HTTP + 100 native, stock native unchanged.
Only `_snapshot` runtime candidate differs from S141. No timing instrumentation.
Original sample gate runs first; a bounded exception after gate index6 enters the
existing child cleanup. The first original failure stops immediately.

Parent bound1230s, passive observer1350s, scheduler1500s; no formal profile edit.
Child runs through the existing BenchmarkProcess owner and original run_child.
A planned boundary may have editor natural exit UNKNOWN; keep helper/actual exits
separate. No F13/F14, formal PASS, root-cause or no-leak conclusion.

Fresh run: gt06-s143-coupled-candidate-01. Supervisor task:
HHStudio.GT06.gt06-s129-s143-candidate-supervisor. Source/native/profile pins are
in freeze.json and validation.json. Source/helper/workstation must stay fixed.

Inputs: S141 sealed timeout boundary and S142 controlled candidate comparisons;
S143 preflight02 completed, 45 affected tests passed. Installed217 binding is
historical/stale after the source change and must be refreshed before its next
affected execution. It is not used to justify this benchmark child.
