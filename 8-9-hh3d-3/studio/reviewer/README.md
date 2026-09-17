# Prepared replay reviewer

`model.py` is a pure state reducer. `app.ReviewerWindow(root, client,
initial_state=None, on_close=None)` creates the Tk view. The injected client
implements `perform(UiAction) -> ReviewerEvent` with finite I/O deadlines;
credentials and request identities stay in that client. The view calls it on
bounded independent work, lookup, and Stop workers, never on the Tk thread.

`dispatch(action)` performs one local action. `pump()` consumes correlated
responses and schedules a lookup every second while queued/running/draining.
Unknown/disconnected states require explicit lookup. Reconnect never starts a
new replay. Ctrl+P plays once, Esc latches Stop, Ctrl+L looks up; Tab follows
the buttons and the read-only evidence text.

Window close first latches Stop, then waits for all operation workers before
calling `on_close()` on a cleanup worker. Only its exact `True` return (or a
confirmed Stop without a callback) permits destruction. Failure/timeout keeps
the window and cleanup ownership. A running cleanup callback is never duplicated.

Only typed enums, numeric observations, fixed capture labels and SHA-256
metadata reach the display. Exceptions and raw responses are never rendered.
Evidence is explicitly historical; this is not a live debugger or arbitrary
project launcher. Worker mailboxes retain every admitted response; ignored
stale updates have a visible counter and state history is capped at 12 entries.
