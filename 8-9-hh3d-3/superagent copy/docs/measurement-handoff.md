# SA-02 measurement fallback — current 2026-10-14

The headed Playwright rig now supports ordinary timed key down/up and CDP
screenshots through `tools/run_guarded.py`. Live CUA play is qualitative only.
Recent CDP captures average below 30 FPS with multi-second gaps; none supplies
A01–A06 samples. A launch/menu capture is never a movement measurement.
The plan section 8.4 fallback is a private owner recording, not acceptance.

## Pilot and capture setup

Use the current Y8-configured game, fixed viewport, 2P VS and zero bots. Show
the selected mode/map and HUD. Keep Stage progress intact. Set Xbox Game Bar
capture to 60 FPS, record with Win+Alt+R and save under
`.local/reference-captures/`. Keep the viewport and audio unchanged per clip.
The Y8 default controls observed here are P1 arrows with N/M/comma/period,
and P2 WASD with 1/2/3/4; verify the selected control profile before recording.

Start with a 30–60 second pilot: idle, walk and release, then one aim/release
shot. The agent checks actual timestamps, duplicate/dropped frames, readable
HUD, unobscured fighters and audio before measuring the remaining clips.
An input camera is not required. Without a synchronized input cue, report
animation intervals only; acceleration/input latency cannot be inferred from
an invisible physical key press. Rig action timestamps may supply that cue
only when they refer to the same capture/session.

## Six clips, each at most two minutes

1. **Walk and sprint:** start idle on clear level ground, walk/release in both
   directions; then double-tap a direction and hold to sprint, exhaust stamina,
   compare idle and walking refill. Leave idle gaps between trials.
2. **Jump, fall and ladder:** standing jump, walking jump, sprint jump, ladder
   up/down and controlled falls with starting height and health visible.
   Record inaccessible/fatal-height cases as pending rather than guessing.
3. **Roll and dive:** isolate a demonstrated roll, then sprint-to-dive on clear
   ground. Show the whole trajectory and landing; avoid combat interference.
4. **Melee and firearms:** bring the two fighters close, record punches to
   defeat and jump kicks separately; then shoot/aim/release with health and
   ammo readable. Start new full-health trials between damage counts.
5. **Grenades and round transitions:** throw from controlled spacing, show
   the complete fuse/explosion and health change, then a death-to-next-round
   sequence. Do not combine several simultaneous damage sources.
6. **Healing and bullet time:** show pre/post health for pills/medkits and
   activation/deactivation of the visible power pickup, including another
   fighter/projectile when possible. Unavailable pickups remain pending.

Each accepted metric needs at least three isolated trials. A clip may cover
only a subset; use another clip of at most two minutes when necessary rather
than compressing or overlapping trials. Keep all outcomes, not only successes.
For A01–A06 the agent records individual values, uncertainty and source/frame
IDs, normalizes lengths to standing character height H, and uses timestamps
rather than assuming Y8 runs at 60 simulation ticks. Below 30 actual FPS only
intervals at least 0.5 seconds may be considered, and gaps must still support
the particular interval and uncertainty. No nominal FPS or elapsed command
duration proves the game advanced at that rate.

Reference recordings are local analysis evidence: never commit them, reuse
them as art, or inspect game internals. Delete captures after measurements
and their audit records are complete. A fallback request, pilot or tool pass
does not freeze the inventory or accept SA-02. No owner recording has been
received as of this update; B/C side-by-side review also remains pending.
