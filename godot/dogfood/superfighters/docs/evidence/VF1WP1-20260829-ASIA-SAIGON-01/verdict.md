# VF1-WP1 verdict

PASS observation ledger (listing pages + honest deferred rows).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No commit by implementer.

## DoD / Verify (quoted from 29-8)

Verify: URL/date/source/hash đầy đủ; reviewer có thể tái lập ghi chú offline.

DoD: mọi tuning/parity claim sau này trỏ tới một row ledger.

## Observed this session (2026-08-29 Asia/Saigon)

- Live Y8 listing HTTP 200. P1 arrows / N punch / M shoot / comma grenade.
  P2 WASD / 1-2-3 punch-shoot-throw. F11 is page fullscreen.
- Live Y8 blurb: Flash→HTML5 remaster, PVP and PVE, 1P/2P, stages/weapons,
  added 23 Jul 2011. HTML5 embed host seen, **not fetched**.
- MythoLogic `/Superfighters` is a live Page not found / empty SPA shell.

## Deferred / secondary / unavailable

- Newgrounds live 403. Developer updates (Stage win-once, Survival, 4 maps,
  random spawns, bullet-time) are search excerpts only.
- Wiki 403. Six map names are a snippet, not a layout study.
- No in-game play: camera, landmarks, sprint/roll/dive/kick, hold-to-aim,
  20s respawn are not `observed`.

## Verify

```
python godot/dogfood/superfighters/tests/check_reference_ledger.py
```

EXIT 0. leftover Godot on product `--path` = 0. Godot not launched.

## Gaps (none blocking this WP)

- Hold-to-aim stays `assumption` (`RL-CTRL-HOLD-AIM`).
- First-playable map display names still echo reference Stage names
  (`RL-DELTA-MAP-NAMES`); VF5 owns the rename.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.
