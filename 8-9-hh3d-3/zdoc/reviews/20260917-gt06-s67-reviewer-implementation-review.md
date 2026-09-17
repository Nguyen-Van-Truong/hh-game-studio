# GT06 S67 reviewer implementation review

Finalized 2026-09-17 15:40 UTC. Implementation review only: no acceptance verdict, TICK, engine launch, GUI launch, or runtime/test source edit. The reviewer used source inspection and detached fake-worker/client probes. The coordinator implemented the two GUI fixes during review. The remaining probe-setup finding below applies to driver SHA256 `118cad2412fbaea0d69483cab920d4b4f12687eb0144ad555e50a99105724880`.

## Remaining finding

**P2 — Protect owner acquisition immediately, including evidence staging.** In `studio/tests/reviewer/run_reviewer_probe.py:24–35`, `PreparedReviewer.prepare()` returns an owner before the cleanup `try/finally` begins. Creating `reviewer-probe/` and writing source evidence at lines 25–29 can raise first. A disk/permission/evidence-staging failure therefore bypasses `owner.close()`, leaving prepared service/listener/backend ownership to outer process teardown instead of the explicit lifecycle.

An engine-free probe substituted a prepared fake owner and no-op path object, then raised `OSError` on the first `native.write()`. Result: `owner.close()` was called **zero times**. No Tk window or filesystem artifact was created by that probe. Initialize `root=None` before acquisition, and include every operation after successful acquisition in its cleanup-protected body. Preserve and report a cleanup failure rather than masking it as a clean setup refusal.

## Findings resolved by the coordinator

**P1 — Automatic lookup could starve close cleanup.** Original `app.py:195–198` dispatched a new automatic lookup before `_check_close()`. Cleanup required no active worker or pending request. If every successful lookup took at least the one-second poll interval, each completion caused its replacement in the same pump; the cleanup callback never ran. A deterministic fake-worker probe with two-second completion intervals produced 16 lookups, zero cleanup calls, and an open window. The close deadline could show `CLEANUP_HELD`, then a later lookup overwrite it with DRAINING.

The current `app.py:195–199` skips automatic polling while closing. This allows existing requests to drain before the owned cleanup callback. It does not discard a response or reset Stop. Static sanity review found this correction appropriate.

**P2 — Local no-command lookup conflicted with the reducer and early worker scheduling.** `ReplayClient._lookup()` intentionally returns local `READY/NO_COMMAND` before its Play worker enters. The old reducer converted all READY responses to UNKNOWN/INVALID_RESPONSE. Two engine-free cases reproduced the mismatch: a fresh-window Reconnect disabled Play despite `started=False`, and LOOKUP scheduled before the pending Play worker entered produced UNKNOWN with Play still pending. The existing slow-lease test began after entry into the Play client method and did not exercise that earlier scheduling boundary.

The current app suppresses automatic lookup while local PLAY is pending. The current reducer handles only the local `LOOKUP + READY + NO_COMMAND` combination: it preserves READY before a launch and preserves the newer local state after a launch. Generic READY remains invalid, and Stop still dominates late updates. Static sanity review found these corrections appropriate.

## Evidence and scope

The old app/model logic is also retained in `studio/.local/reviews/gt06-s66-reviewer-complete-01/reviewer-probe/source/`, with manifest hashes:

- `reviewer/app.py`: `d1a8126bc443e43e4d2483b8ce3fe4755b941d6f0209191077555825df317452`.
- `reviewer/model.py`: `895841b6765bbed49ba822986c6c8c863c833d431fe6678e11a09f0a0f4c9ff0`.

Sanity-read fixed source hashes:

- `reviewer/app.py`: `5fad7a8f226176cd64b139afb7334c0d3ad2e630a80bae96b20be02b71e212e9`.
- `reviewer/model.py`: `27459fe77d8307f8848f6d4a9969d17c659259013aa4627aa461582b4a37f7ec`.
- `reviewer/client.py`: `843a6c2743eef5f85ed45f24bbe3054a187afaec1658cb9447ff046e0f83508d`.
- `reviewer/main.py`: `2e6190fb28b81c50aae110694d74fddc6a0f7f1115156333e972311bfa94666a`.

Read-only inspection of coordinator-run `gt06-s67-reviewer-complete-02` and `gt06-s67-reviewer-stop-01` found retained completed probe/driver records with child and wrapper exit 0, `tree_verified=true`, no outer timeout, and closed windows/owners. Both bind native closure `39d4e8429921f08adef94b3fb4035210e98c2a82676c8d1ba4f965a4ff0f7c41` and reviewer closure `665320a25e388c97c5e0db9d910a51fdb09edc6eff90a929ffeb536c32ab66d0`. Complete records keyboard Play, inspection and capture; Stop records keyboard Stop and latch. These existing coordinator results were inspected, not independently rerun here.

The fixed recorded-trace fixture sets `window/size/no_focus=true`, and the trace bridge checks the actual `WINDOW_FLAG_NO_FOCUS` before input. This is an explicit fixture policy that leaves the reviewer available for keyboard Stop; it does not silently reinject held keys or alter the recorded trace. This review did not independently establish focus loss as the cause of the earlier native input failure, nor does a passing fixed-trace probe establish manual gameplay focus behavior.

No further concrete issue was found in the inspected client request deadline, independent Stop worker, bounded response mailbox, or prepared-owner retry retention. Those observations and the actual GUI diagnostic records are not a full UX benchmark or acceptance decision.
