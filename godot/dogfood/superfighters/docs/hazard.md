# Explosive barrels and fire — VF4-WP3

Display title: **Vault Fighters**. This document does **not** claim Y8 parity.

Sidecar evidence: `docs/evidence/VF4WP3-20260830-ASIA-SAIGON-02/`.
`VF4WP3-20260830-ASIA-SAIGON-01` is historical and was **not** reminted.

## Contract

Explosive `Blast Drum` props take bullet/melee/explosion damage. At
zero health they emit one `prop_explode` event, spawn capped VFX, ignite
fighters inside `fire_radius`, release hanging crates, and try to
damage neighbor drums. Chain depth is capped at 2 (`ledger:RL-PROP-CHAIN`).
A fourth/fifth neighbor stays intact.

Fighters gain a flammable burn timer (`ledger:RL-PROP-FIRE`). Damage
ticks every 12 ticks. Timer expiry emits `fire_end` and WorldOwner
clears fire sprites. The selected extinguish rule is **roll**
(`ledger:RL-PROP-EXTINGUISH`). Water is not selected (VF4-WP5).

`Drop Cage` starts hanging (`ledger:RL-PROP-HANG`). A nearby blast or
a direct hit releases it with a downward impulse. Official maps use
`#` floors only.

`WorldOwner` remains the only writer. `PropView` cannot mutate.
Nade blasts may start a barrel chain but still do **not** destroy
glass/wood (`ledger:RL-NADE-PROP` stays `deferred`).

Official MATCH uses `GameSession.apply_frames` on typed `InputFrame`s.
Clock is `ledger:RL-SIM-FIXED-60` (`assumption`).

## Fixtures

- `fx_hazard_chain` display **Blast Row** — five drums + hanging crate
- `fx_hazard_fire` display **Ember Walk** — one drum beside P1
- `fx_hazard_yard` display **Drum Yard** — three drums + hang for the
  visible official window

Live rooftops/storage/police/hazardous still paint ASCII `c`/`b` as
tiles. This WP does not migrate them.

DoD window stills wait for `frame_post_draw` after the matching
`start_fight` and after the frames that produce blast, burn, or drop.
Setup is Drum Yard spawn. Chain/fire/hang must be pairwise-distinct
bytes, not leftover framebuffer copies.

## Honesty

- Chain / fire / hang / extinguish stay assumption:
  `ledger:RL-PROP-EXPL`, `ledger:RL-PROP-CHAIN`,
  `ledger:RL-PROP-FIRE`, `ledger:RL-PROP-HANG`,
  `ledger:RL-PROP-EXTINGUISH`.
- `ledger:RL-NADE-PROP` stays deferred.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Values are tuning. No copied Y8 table. Not a VF7 art rewrite.
- Original explode/fire VFX only. No Y8 rip.
