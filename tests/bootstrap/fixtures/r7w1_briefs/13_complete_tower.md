# PROJECT_BRIEF

## genre

- **value:** tower defense
- **player fantasy:** place two towers and survive one path
- **out of scope:** hero units, card drafts

## camera

- **mode:** fixed
- **zoom / limits:** 1.0
- **multi-camera:** no

## resolution

- **base design resolution:** 1280x720
- **stretch mode:** canvas_items
- **aspect:** keep
- **integer scale:** no

## input

- **devices:** mouse
- **actions:** place, select, pause
- **remap UI:** not in v1

## platform

- **ship target:** Windows desktop
- **also-run:** editor Play
- **store / signing:** never implied

## art

- **style:** readable path and tower icons
- **palette / silhouette notes:** stone path, green grass
- **placeholder policy:** PLACEHOLDER assets must not ship
- **AI / generated assets:** require source/prompt/license manifest

## audio

- **music:** march loop
- **SFX set:** place, shoot, leak
- **bus layout:** Master / Music / SFX
- **license source:** original

## save

- **needed:** no
- **slots / autosave:** none
- **location:** none
- **contents:** none

## acceptance

- a tower deals damage to a creeper on the path
- leaking three creepers fails the slice
- tests define path and leak before bulk tower art
