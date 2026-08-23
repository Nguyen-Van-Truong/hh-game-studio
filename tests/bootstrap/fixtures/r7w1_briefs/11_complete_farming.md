# PROJECT_BRIEF

## genre

- **value:** farming harvest sim
- **player fantasy:** plant, water, and harvest one crop
- **out of scope:** marriage, festivals, multiplayer

## camera

- **mode:** follow
- **zoom / limits:** 1.0
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** yes

## input

- **devices:** keyboard
- **actions:** move, interact, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** soft tiles, readable crops
- **palette / silhouette notes:** spring greens
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** acoustic loop
- **SFX set:** plant, water, harvest
- **bus layout:** Master / Music / SFX
- **license source:** CC0

## save

- **needed:** yes
- **slots / autosave:** 1 slot
- **location:** user data
- **contents:** plot state and day index

## acceptance

- watering a planted tile advances growth
- harvest yields one item in inventory
- tests define growth ticks before bulk crop sheets
