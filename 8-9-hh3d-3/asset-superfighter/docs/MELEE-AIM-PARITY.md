# Melee & aim presentation — Y8 reference vs Superagent fixes

## Bug reports (before fix)

| File | Symptom |
|------|---------|
| `reference/bug-reports/2026-10-17-melee-arc-before.png` | Pink/orange **crescent arc** on punch/kick (procedural debug FX from `fighter_view._draw_action_feedback`) |
| `reference/bug-reports/2026-10-17-aim-backwards-before.png` | **Aim line / tracer** points opposite to facing when sprite faces left |

## How Superfighters (Y8) reads (reference)

| Topic | Y8 / wiki behavior | Superagent target |
|-------|-------------------|-------------------|
| Punch / kick | Character **pose** only; hit reads on contact flash / enemy react | Remove swing **arc overlay**; keep pose clip + optional `arena_fx` hit spark on damage |
| Aim | Gun points with **hold aim**; reticle/laser follows **facing** and up/down | `WeaponVisuals.direction_for(facing, aim_angle, true)` in **canvas space** after sprite mirror |
| Authored sprite mirror | Left = flip atlas once in `draw_set_transform` | Weapon grip: `grip.x *= facing`; direction uses **facing**, not always `+1` |
| Melee speed | Fists ~8.5 HP, 11 WU (Deluxe wiki); kick 3 HP, short range | `attack_cooldown_ticks`: 8 @ 60 Hz — tune via `data/tuning.json` if too fast |
| Kick key | Y8 Simple: context on **S** (Advanced: kneel/roll/dive shares S) | P1: Down+J kick; document in `control-bindings.md` |

## Code changes (2026-10-17)

File: `superagent/game/fighter/fighter_view.gd`

1. **Aim reticle:** `direction_for(facing, aim_angle, true)` (was `facing=1` only).
2. **Held weapon (authored pose):** mirror grip X by `facing`; same direction fix.
3. **Melee arc:** removed `draw_arc` / spokes for punch, kick, combo, grab_punch (b64a40b6-style arcs were presentation-only, not Y8-like).

## Tuning “too fast”

| Parameter | Location | Default | Note |
|-----------|----------|---------|------|
| `attack_cooldown_ticks` | `data/tuning.json` | 8 | Raise to 10–12 for slower combo cadence |
| `punch` clip duration | `visual.json` `duration_ticks.punch` | 3 | Presentation frames only |
| `shoot_cooldown_ticks` | tuning | 20 | Pistol ~0.33 s between shots (wiki pistol ~0.3 s fire rate LEAD) |

## Verification

1. Left-facing + hold aim (K / Numpad 2): reticle and muzzle extend **left**.
2. Punch (J / Numpad 1): **no** pink crescent; only pose animation.
3. Optional: run `tests/presentation_fx.gd`, `tests/fighter_visual_profile.gd`.

## External links

- [Special Movements](https://superfighters.fandom.com/wiki/Special_Movements) — roll, dive, disarm
- [Kicks](https://superfighters.fandom.com/wiki/Kicks) — kick vs jump kick
- [Pistol](https://superfighters.fandom.com/wiki/Pistol) — mag 12, cadence lead
