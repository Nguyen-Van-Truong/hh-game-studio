# SA-02 measurement fallback

The current documented browser tools provide taps/chords, UI screenshots and
viewport overrides. They expose neither timed key-down/key-up nor a 60-fps
recorder; native computer control is disabled. Do not inject game events,
inspect reference internals or use another automation channel to bypass this.
The main plan section 8 authorizes an owner recording fallback. This is a
capture script, not acceptance evidence or a request to change scope.

## Validate a pilot before longer recordings

1. Use the current public Y8 game, fixed viewport, 2P VS and zero bots. Show
   the selected mode/map and HUD. Do not reset existing Stage progress.
2. Record 30–60 seconds at verified 60 fps with game audio. Demonstrate one walk
   hold/release and one shoot hold/aim/release.
3. Include an observable press/release cue: a verified input indicator or
   synchronized keyboard camera. Screen-only video can measure animation
   intervals but does not establish exact physical input times.
4. Save privately under `.local/reference-captures/` in the product worktree.
   Never commit reference media or use it as art. Delete when no longer needed.
5. Inspect playable frames, actual cadence/timestamps, game visibility, audio
   and input cue before requesting longer clips. Nominal 60 fps is insufficient
   if the recording duplicates/drops frames or obscures the relevant action.

## Follow-up scripts, each at most 15 minutes

- Controls/movement: at least 3 separate trials per timed/spatial claim for
  walk/brake, jump, ladder, drop and any actually demonstrated roll/dive/ledge.
- Combat: at least 3 trials for measurable melee, aim/release, firing, throw,
  knockdown/get-up and death transitions, with controlled spacing and visible
  health/ammo. Isolate an action and its consequence before the next input.
- Randomness/catalog: at least 10 eligible trials per mechanism for SA-02,
  retaining repetitions and empty outcomes. Existing 10 Random-map launches
  count only for map selection. Later MATCHED requires at least 30, and count
  alone does not establish a probability or independence.
- Platform/feedback: capture functional audio; use actual touch capability
  for touch mapping. Resizing a desktop page proves neither touch nor vibration.

Define visible start/end events before measuring. Record individual values,
range, uncertainty and source/run identifiers; normalize lengths by character
height H. Use video timestamps/frames, not assumed reference simulation ticks.
Record unknown RNG seeds and calibration limits explicitly. Keep unsupported
claims UNVERIFIED; documenting a limitation does not freeze the inventory or
accept SA-02. Continue supported categorical observations in parallel.

Methods reviewed independently by GPT-6 Astra ultra on 2026-10-03. This is not
an acceptance critic signature, and no owner recording has been received.
