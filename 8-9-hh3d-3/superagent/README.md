# Superagent Classic

The project is a clean-room 2D arena platform shooter. The current product
route is Classic-first: SA-01's technical input contract is accepted, SA-02
reference parity is still under observation, and SA-03's movement room remains
provisional. It does not claim Y8 parity until the ledger and
`tools/check_parity.py --classic` pass on observed evidence.

The owner-approved Classic keyboard layout is documented in
[`docs/control-bindings.md`](docs/control-bindings.md). Ordinary characters
use only the four shared action roles; special-character skills and passives
remain reserved for the locked SA-14 phase.

The movement lab currently supports jump, ladder, double-down platform drop,
and double-tap left/right then hold to sprint. Sprint consumes shared stamina;
standing still restores it faster than moving. These are provisional rules
with data-driven seeds, not accepted reference timing. Combat is now built
provisionally: close punch/jump-kick, aligned shot, knockdown/invulnerability,
and a fuse grenade travel through the same fixed-step input path. Their damage,
range and fuse values remain engineering seeds; the action-key labels alone do
not imply accepted reference behavior.

Run the pinned Godot console executable through `tools/run_guarded.py` after the
shared-machine measurement lock is absent. Do not store reference captures or
generated builds in Git.

## Manual two-player play

Double-click [`tools/play_two_player.bat`](tools/play_two_player.bat) from this
checkout to go directly into a Relay Yard VS match with two local players and
no bots. Keep the console open while playing; close the game window to exit.
The session limit is four hours. P2 uses the numeric keypad with Num Lock on;
weapons are picked up with Down + Punch. See the full
[`controls`](docs/control-bindings.md).

The launcher creates a fresh command id for every run, uses pinned Godot, and
shows any startup error instead of disappearing. A second launch is rejected
while the first is active. Recovery of an abandoned lease uses a read-only
Windows process query under an OS lock; it never signals the recorded PID.
The launcher refreshes the Godot import cache before opening the window;
cached, unchanged assets are reused. Optional command-line
arguments are passed to Godot for bounded diagnostics.
