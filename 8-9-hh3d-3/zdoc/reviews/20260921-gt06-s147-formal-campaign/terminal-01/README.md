# S147 terminal packet (AUTHORITY=0)

`gt06-s147-formal-01` used the stock campaign and original gates with the frozen S145 source closure and S146 installed execution binding. It terminated at batch 10 during `joint_observation` with `CAMPAIGN_RETAINED_COUNTER_GROWTH`; 11 partial batches were recorded and zero full runs were accepted.

The exact raw files copied here are hashed in `manifest.json`. `derived-command-10-counters.json` is a read-only projection of the exact raw `command-10.json`: host held handles changed 204 to 205; editor observation recorded held handles 557, ObjectDB 71128, resources 6, and RSS 209940480 bytes. Cleanup recorded the editor Job closed/zero observed, no retained wrapper handle, producer threads stopped, and no journal/cache/directory/index retention. The editor target exit is UNKNOWN because no target exit record was captured; import exited 0.

This packet is not F13/F14 evidence, does not prove a leak or root cause, and does not authorize a blind formal retry. Preserve the raw run under `studio/.local/reviews/gt06-s147-formal-01`.
The read-only counter comparison is in `attribution-01.json`; it shows the host count increased only at batch 10 and leaves the source unchanged.
