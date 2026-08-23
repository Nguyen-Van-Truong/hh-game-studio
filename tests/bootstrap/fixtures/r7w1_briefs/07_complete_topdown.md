# PROJECT_BRIEF

## genre

- **value:** top-down 2D action-adventure
- **player fantasy:** explore a small overworld and find a key
- **out of scope:** multiplayer, crafting

## camera

- **mode:** follow
- **zoom / limits:** 2.0, clamp to map
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** no

## input

- **devices:** keyboard
- **actions:** move, interact, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** readable silhouette sprites
- **palette / silhouette notes:** warm earth tones
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** one loop
- **SFX set:** pickup, bump, pause
- **bus layout:** Master / Music / SFX
- **license source:** original

## save

- **needed:** yes
- **slots / autosave:** 1 slot
- **location:** user data
- **contents:** room id and key flag

## acceptance

- vertical slice: player moves, picks up a key, door opens
- play session: 10 minutes with no blocker
- tests: GUT unit + MCP/E2E evidence on 4.7.1-stable
- export: later Windows smoke only
