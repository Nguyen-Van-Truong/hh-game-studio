# Character animation pose checklist (Y8 reference vs Superagent pilot)

Use wiki infobox / in-game capture for **reference silhouettes**. Superagent paths point at
**original** pilot art in `superagent/art/` (not Y8 rip).

## Y8 / Superfighters expected clip families

| Clip / state | Gameplay triggers (reference) | Wiki or tip | Superagent pilot (`visual.json` clips) | Gap |
|--------------|------------------------------|-------------|----------------------------------------|-----|
| idle | standing | — | idle (frames 0–1) | breath/idle subtle motion open |
| run | horizontal move | — | run (4–7) | OK prototype |
| jump / fall | airborne | R02 partial | jump 8, fall 9 | OK |
| crouch | Down held | partial | crouch 3 | roll/dive share low posture |
| climb | ladder | partial | climb 10–11 | OK |
| punch | melee key | Y8-OBS | punch 12 | combo frames open |
| kick | kick key (S Deluxe) | Kicks wiki | jump_kick 13 only | **standing kick clip missing** |
| jump_kick | air + kick | TIP 13 | jump_kick 13 | kneel recovery not authored |
| aim | hold aim | UNVERIFIED Y8 | aim 16 | arm angle articulation pending |
| shoot | fire | Y8-OBS muzzle | shoot 17–16 | recoil ext in fire_throw atlas |
| throw grenade | grenade key | Y8-OBS | throw 19 (follow-through) | windup cell reserved |
| roll | down+direction | TIP 06 | roll → **fallback crouch** | dedicated roll art pending |
| dive / tackle | sprint+crouch | TIP 17 | dive 14 | grab/shield not visual final |
| hit / knockdown | damage | R03 UNVERIFIED | hit → fallback idle | |
| downed / pit | KO / pit | — | downed 15 | |
| burning | on fire DOT | TIP 06 | **not in pose sheet** | need fire overlay VFX |
| power / slow-mo | period/4 | Y8-OBS overlay | power → fallback ready | |
| wield melee (axe/katana) | slot 1 | Katana, Fire Axe wiki | weapon held via `weapon_visuals.gd` | need authored hand poses per weapon |
| wield rifle/pistol | slot 2 | Pistol wiki | pistol/shotgun/rocket procedural | |
| flamethrower spray | primary | Flamethrower wiki | not separate clip | flame stream = VFX |

## Action extension atlas (Superagent original)

`superagent/art/characters/shared/fire_throw_v2.png` — columns: pistol aim two-hand, recoil,
throw windup, throw follow-through (see `superagent/art/production-v2.md`).

## Where to get **Y8** character/item **images** (external, not in repo)

Open rows in `catalog/character-actions-manifest.csv` → each wiki page infobox.
For full-body combat frames: capture from [Y8 Superfighters](https://www.y8.com/games/superfighters) at 60 FPS observation (SA-02 method).
